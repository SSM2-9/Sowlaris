"""
Rotation recommendation engine.

    diagnose_farm()     what the 10 datasets say about the farm
    CANDIDATES          agronomically sequenced rotation options
    score_rotation()    0–1 scores: water, climate fit, soil health, erosion
                        protection, pest break, market potential
    recommend()         current rotation + best two alternatives for the
                        farmer's priorities, each with why / evidence /
                        benefits / information gaps / risks for local review
"""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from .. import config as C
from . import feasibility as F

SCORE_KEYS = ["water", "climate_fit", "soil_health", "erosion_protection", "pest_break", "market_potential"]
DEFAULT_PRIORITIES = {"water": 3, "market_potential": 3, "soil_health": 3, "erosion_protection": 3}
DEPRECATED_KEYS = {"income": "market_potential"}   # accepted for backward compatibility
FIXED_WEIGHTS = {"climate_fit": 2, "pest_break": 1}
NEAR_TIE = 0.02   # presentation heuristic, NOT a statistical confidence interval
PRIORITY_RANGE = (0, 5)
DEFAULT_CONSTRAINTS = {
    "irrigation_available": False,                # dryland unless the farmer says otherwise
    "limit_water_to_current": False,              # exclude rotations with higher modelled crop-water demand
    "can_establish_cover_before_harvest": False,  # interseeding equipment / ability
    "forage_market_or_livestock": False,          # outlet for alfalfa / forage
}


def validate_priorities(priorities: dict | None) -> dict:
    """Return complete, checked farmer weights or raise ValueError with a readable message."""
    priorities = {} if priorities is None else priorities
    if not isinstance(priorities, dict):
        raise ValueError("priorities must be a dict like {'water': 3, ...}")
    priorities = {DEPRECATED_KEYS.get(k, k): v for k, v in priorities.items()}
    unknown = set(priorities) - set(DEFAULT_PRIORITIES)
    if unknown:
        raise ValueError(f"unknown priority key(s) {sorted(unknown)}; allowed: {sorted(DEFAULT_PRIORITIES)}")
    out = {**DEFAULT_PRIORITIES, **priorities}
    lo, hi = PRIORITY_RANGE
    for k, v in out.items():
        if isinstance(v, bool) or not isinstance(v, (int, float, np.integer, np.floating)):
            raise ValueError(f"priority '{k}' must be a number, got {v!r}")
        if not np.isfinite(v) or not lo <= v <= hi:
            raise ValueError(f"priority '{k}' must be between {lo} and {hi}, got {v!r}")
    if sum(out.values()) == 0:
        raise ValueError("at least one priority must be above 0")
    return {k: float(v) for k, v in out.items()}


def validate_constraints(constraints: dict | None) -> dict:
    constraints = {} if constraints is None else constraints
    if not isinstance(constraints, dict):
        raise ValueError("constraints must be a dict of yes/no values")
    unknown = set(constraints) - set(DEFAULT_CONSTRAINTS)
    if unknown:
        raise ValueError(f"unknown constraint key(s) {sorted(unknown)}; allowed: {sorted(DEFAULT_CONSTRAINTS)}")
    for k, v in constraints.items():
        if not isinstance(v, (bool, np.bool_)):
            raise ValueError(f"constraint '{k}' must be True or False, got {v!r}")
    return {**DEFAULT_CONSTRAINTS, **{k: bool(v) for k, v in constraints.items()}}

# Each year = (main crop, crop that follows in the same year: cover crop / double crop / None).
# Sequencing rules (docs/METHODOLOGY.md §5): cereal rye after corn and before soybean (soybean fixes
# its own N, so rye's N tie-up does not hurt it); hairy vetch after soybean and before the grass crop
# (its N feeds corn/sorghum); nothing fall-sown directly after sorghum (poor establishment).
CANDIDATES = {
    "current_corn_soy": {
        "name": "Current: Corn → Soybean",
        "years": [("corn", None), ("soybean", None)]},
    "corn_soy_covers": {
        "name": "Corn → Soybean with winter cover crops",
        "years": [("corn", "cereal_rye_cover"), ("soybean", "hairy_vetch_cover")]},
    "corn_soy_rye": {   # added in audit Phase 2 (feasibility gap: vetch cannot follow soybean without interseeding)
        "name": "Corn → Soybean + cereal rye cover",
        "years": [("corn", None), ("soybean", "cereal_rye_cover")]},
    "sorghum_soy_vetch": {
        "name": "Sorghum → Soybean with a legume cover crop",
        "years": [("sorghum", None), ("soybean", "hairy_vetch_cover")]},
    "sorghum_soy_wheat_dc": {
        "name": "Sorghum → Soybean → Winter wheat + double-crop soybean",
        "years": [("sorghum", None), ("soybean", None), ("winter_wheat", "dc_soybean")]},
    "corn_soy_wheat_vetch": {
        "name": "Corn → Soybean → Winter wheat + hairy vetch",
        "years": [("corn", "cereal_rye_cover"), ("soybean", None), ("winter_wheat", "hairy_vetch_cover")]},
    "alfalfa_corn_soy": {
        "name": "Alfalfa (3 yrs) → Corn → Soybean",
        "years": [("alfalfa", None)] * 3 + [("corn", "cereal_rye_cover"), ("soybean", None)]},
}


# ============================================================================ helpers
WATER_MODEL = "daily_water_balance"
WATER_MODEL_NOTE = ("EXPLORATORY CALIBRATED MODEL: water and drought-risk scores come from a daily soil-water balance "
                    "(NASA GPM IMERG rain, NASA POWER ET0, SSURGO soil water above an inferred claypan rooting limit, "
                    "FAO-56 stress, FAO-33 yield response). It reproduces county yield swings (r ≈ 0.7–0.8) but "
                    "over-estimates ECOSTRESS crop water use (0.71 vs 0.52); runoff and irrigation are not modelled.")
# Water score scale: mean annual May–Sep reference ET0 of the OBSERVED climate (NASA POWER), a rotation-independent
# physical yardstick. Shortfall is linear in mm, so a drier climate can never compress differences to zero.
# Soil relevance (item 10). ASSUMPTIONS, labelled: anchors are round reference values, not calibrated.
SOIL_PARAMS = {
    "om_adequate_pct": 3.5,   # organic matter above which soil-building matters less (assumption)
    "om_low_pct": 0.5,
    "kw_high": 0.55,          # high water erodibility (USLE K range ~0.02–0.69)
    "wind_index_high": 310,   # NRCS wind erodibility index of WEG 1 (t/ac/yr)
    "slow_ksat_um_s": 1.0,    # NRCS 'moderately low' Ksat class and slower
    "relevance_floor": 0.5,   # half of each criterion's spread is always kept (assumption)
}


def month_list(spec: str) -> list[int]:
    """'5-9' → [5..9];  '10-6' → [10, 11, 12, 1 … 6]."""
    a, b = map(int, spec.split("-"))
    return list(range(a, b + 1)) if a <= b else list(range(a, 13)) + list(range(1, b + 1))


def _load_json(path):
    return json.loads(path.read_text()) if path.exists() else None


@lru_cache(maxsize=1)
def load_data() -> dict:
    traits = pd.read_csv(C.ENGINE_DIR / "crop_traits.csv").set_index("crop")
    traits["month_set"] = traits.months.map(month_list)
    d = {
        "master": pd.read_csv(C.OUT["master_monthly"]),
        "yearly": pd.read_csv(C.OUT["power_yearly"]),
        "cdl": pd.read_csv(C.OUT["cdl"]),
        "soil": pd.read_csv(C.OUT["soil_summary"]),
        "horizons": pd.read_csv(C.OUT["soil_horizons"]),
        "gaez": pd.read_csv(C.OUT["gaez"]),
        "nass": pd.read_csv(C.OUT["nass_wide"]),
        "bare": pd.read_csv(C.OUT["bare_soil"]),
        "trends": pd.read_csv(C.OUT["trends"]),
        "regimes": pd.read_csv(C.OUT["regimes"]),
        "traits": traits,
        "yield_model": _load_json(C.OUT["yield_results"]),
        "analysis": _load_json(C.OUT["analysis_summary"]),
    }
    d["crop_losses"] = crop_loss_table(d["yield_model"])     # evidence text only — NOT used in scoring
    d["hot_dry_loss"] = hot_dry_losses(d["yield_model"])
    field = d["soil"][d["soil"].map_unit == "FIELD_AVG"].iloc[0]
    d["soil_factors"] = soil_factors(d["horizons"], field)
    gs = d["master"][d["master"].month.isin(C.GROWING_SEASON)]
    d["water_reference_mm"] = float(gs.groupby("year").et0_hargreaves_mm.sum().mean())
    d["water"] = water_metrics(d)
    return d


def water_metrics(d: dict, rain=None, et0=None, storage_scale: float = 1.0, profile=None,
                  effective_rooting: bool = True, runoff: dict | None = None) -> dict:
    """NASA daily water-balance metrics for every candidate rotation (see models/water_balance.py)."""
    from ..models import water_balance as W
    return {k: W.rotation_metrics(r, d["traits"], rain=rain, et0=et0, storage_scale=storage_scale,
                                  profile=profile, effective_rooting=effective_rooting, runoff=runoff)
            for k, r in CANDIDATES.items()}


def soil_factors(horizons: pd.DataFrame, field: pd.Series | dict) -> dict:
    """Soil relevance factors (0–1) and the facts they come from. Missing values give None (not invented)."""
    P = SOIL_PARAMS
    w = horizons.drop_duplicates("map_unit").set_index("map_unit").pct_of_field
    slow = horizons.groupby("map_unit").ksat_um_s_low.min() < P["slow_ksat_um_s"]
    slow_share = float((w * slow.reindex(w.index).fillna(False)).sum() / w.sum())
    top = horizons[horizons.top_in == 0]
    def wavg(col):
        if col not in top or top[col].isna().all():
            return None
        v = top.set_index("map_unit")[col].dropna()
        return float((v * w.reindex(v.index)).sum() / w.reindex(v.index).sum())
    kw, wind = wavg("kw"), wavg("wind_erod_index")
    om = _num(field.get("topsoil_organic_matter_pct"), 2)
    lo, hi = P["om_low_pct"], P["om_adequate_pct"]
    om_deficit = None if om is None else float(np.clip((hi - om) / (hi - lo), 0, 1))
    erod = max(v for v in [None if kw is None else kw / P["kw_high"], None if wind is None else wind / P["wind_index_high"], 0]
               if v is not None)
    f = P["relevance_floor"]
    return {
        "slow_drainage_share": round(slow_share, 3),
        "drainage_relevance": round(slow_share, 3),                       # 0 = free draining: wet-soil tolerance irrelevant
        "erosion_susceptibility": round(float(np.clip(erod, 0, 1)), 3),
        "erosion_relevance": round(f + (1 - f) * float(np.clip(erod, 0, 1)), 3),
        "om_deficit": None if om_deficit is None else round(om_deficit, 3),
        "soil_health_relevance": round(f + (1 - f) * (om_deficit if om_deficit is not None else 1.0), 3),
        "kw": None if kw is None else round(kw, 3), "wind_erodibility_index": wind, "organic_matter_pct": om,
    }


LOSS_PROVENANCE = {
    "rf_full_sample_estimate": "Random Forest trained on all years (in-sample estimate, not validated)",
    "historical_observation": "Calculated from USDA NASS county yields (observed, not a prediction)",
    "proxy": "Borrowed from another crop's estimate (assumption)",
    "assumption": "Developer assumption",
}


def crop_loss_table(ym: dict | None) -> dict:
    """Every 2012-like crop-loss value with its provenance (audit item 15). Evidence text only — not scored."""
    if not ym:
        return {}
    sc = ym["scenarios_yield_change_pct_vs_normal_summer"]["hot_dry_like_2012"]
    y12 = ym.get("year_2012", {})
    summer = float(np.mean([sc[c] for c in ("corn", "soybean", "sorghum")]))
    wheat_hot = ym["crop_sensitivity"]["wheat"]["avg_yield_pct_in_hottest_quarter_of_years"]
    t = {}
    for c in ("corn", "soybean", "sorghum"):
        t[c] = {"value_pct": sc[c], "provenance": "rf_full_sample_estimate",
                "held_out_2012_prediction_pct": y12.get(c, {}).get("held_out_rf_prediction_pct_change"),
                "observed_2012_pct": y12.get(c, {}).get("observed_pct_change_vs_trend")}
    t["dc_soybean"] = {"value_pct": sc["soybean"], "provenance": "proxy", "from": "soybean"}
    t["sunflower"] = {"value_pct": round(summer, 1), "provenance": "proxy", "from": "mean of corn, soybean, sorghum"}
    t["alfalfa"] = {"value_pct": round(summer, 1), "provenance": "proxy", "from": "mean of corn, soybean, sorghum"}
    t["oats"] = {"value_pct": round(summer / 2, 1), "provenance": "assumption", "from": "half the summer-crop mean"}
    t["winter_wheat"] = {"value_pct": round(min(0.0, wheat_hot - 100), 1), "provenance": "historical_observation",
                         "from": f"county wheat averaged {wheat_hot:.0f}% of trend in the hottest quarter of years; capped at 0"}
    for v in t.values():
        v["provenance_text"] = LOSS_PROVENANCE[v["provenance"]]
    return t


def hot_dry_losses(ym: dict | None) -> dict:
    """Back-compatible {crop: value} view of crop_loss_table (evidence text only)."""
    return {c: v["value_pct"] for c, v in crop_loss_table(ym).items()}


def _trend(d, indicator):
    return d["trends"].set_index("indicator").loc[indicator]


def _ok(v) -> bool:
    return v is not None and not (isinstance(v, float) and not np.isfinite(v))


def _num(v, nd=1):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return round(v, nd) if np.isfinite(v) else None


def _trend_text(t, unit, decimals=1):
    if not _ok(t.slope_per_decade):
        return "not available (dataset missing or too short)"
    sig = "statistically significant" if t.significant_5pct else "not statistically significant"
    p = "p < 0.001" if t.p_value < 0.001 else f"p = {t.p_value:.2f}"
    return f"{t.slope_per_decade:+.{decimals}f} {unit}/decade (Theil–Sen; Mann–Kendall {p}, {sig})"


# ============================================================================ 1. diagnosis
def diagnose_farm(d: dict) -> dict:
    m, soil = d["master"], d["soil"]
    field = soil[soil.map_unit == "FIELD_AVG"].iloc[0]
    a = d["analysis"] or {}
    last = d["cdl"].sort_values("year").tail(6)
    regimes = d["regimes"].sort_values("year")
    recent = regimes.tail(5)
    nass = d["nass"][d["nass"].year >= 2016]
    county_crops = sorted({c.split("_")[0] for c in nass.columns
                           if c.endswith("_acres_harvested") and nass[c].notna().any()})
    gs = m[m.month.isin(C.GROWING_SEASON)].groupby("year")
    dry_cut = gs.water_balance_mm.sum().quantile(0.25)
    bare = d["bare"]
    return {
        "location": f"{C.FARM['name']} ({C.FARM['lat']}, {C.FARM['lon']})",
        "elevation_m": _num(m.elevation_m.iloc[0], 0),
        "annual_rain_mm": round(float(d["yearly"].rain_gpm_imerg_mm.mean()), 0),
        "gs_rain_mm": a.get("gs_rain_mm_mean"),
        "gs_et0_mm": a.get("gs_et0_mm_mean"),
        "gs_water_balance_mm": a.get("gs_water_balance_mm_mean"),
        "dry_years": [int(y) for y, v in gs.water_balance_mm.sum().items() if v <= dry_cut],
        "trend_temperature": _trend_text(_trend(d, "Mean annual temperature"), "°C", 2),
        "trend_heat_days": _trend_text(_trend(d, "Heat-stress days per year"), "days"),
        "trend_gs_water_balance": _trend_text(_trend(d, "Growing-season water balance"), "mm", 0),
        "trend_winter_ndvi": _trend_text(_trend(d, "Winter NDVI (MODIS, Dec–Feb mean)"), "NDVI", 3),
        "heat_days_mean": round(float(d["yearly"].heat_stress_day.mean()), 1),
        "frost_days_mean": round(float(d["yearly"].frost_day.mean()), 0),
        "offseason_rain_mm": a.get("offseason_rain_mm_mean"),
        "observed_bare_months_2005_2007": _num(bare[bare.year <= 2007].bare_months_scaled_to_12.mean()),
        "observed_bare_months_since_2015": _num(bare[bare.year >= 2015].bare_months_scaled_to_12.mean()),
        "eco_et_to_et0_jul_aug": a.get("eco_et_to_et0_jul_aug_mean"),
        "smap_jul_aug": a.get("smap_jul_aug_mean"),
        "smap_apr_may": a.get("smap_apr_may_mean"),
        "summer_lst_day_c": a.get("summer_lst_day_c_mean"),
        "recent_regimes": dict(zip(recent.year.astype(int), recent.regime)),
        "hot_dry_seasons": int((regimes.regime == "Hot & dry").sum()),
        "soil_om_pct": _num(field.topsoil_organic_matter_pct, 2),
        "soil_ph": _num(field.topsoil_ph, 2),
        "soil_awc_in": _num(field.plant_available_water_in_0_79in, 2),
        "subsoil_max_clay_pct": _num(field.max_clay_pct, 2),
        "soil_kw": _num(field.topsoil_erodibility_kw, 3),
        "soil_min_ksat_um_s": _num(field.get("min_ksat_um_s"), 3),
        "current_rotation": " ↔ ".join(sorted(dict.fromkeys(last.crop))),
        "current_rotation_years": f"{int(last.year.min())}–{int(last.year.max())}",
        "county_crops_recent": county_crops,
        "data_availability": (a.get("data_availability") or {}),
    }


# ============================================================================ 2. scoring
def score_rotation(rot: dict, d: dict, farm: dict, livestock: bool = False, water: dict | None = None,
                   irrigation: bool = False, soil: dict | None = None) -> dict:
    """Six 0–1 scores. Water and drought risk come from the NASA daily water balance (`water`, from
    water_metrics); soil sets how much drainage, erosion and organic-matter differences matter (`soil`)."""
    from ..models import water_balance as W
    t, gaez = d["traits"], d["gaez"].set_index("crop").suitability_index_0_10000
    mains = [m for m, _ in rot["years"]]
    allc = [c for pair in rot["years"] for c in pair if c]
    n = len(mains)
    T = lambda col, crops: float(np.mean([t.loc[c, col] for c in crops]))
    water = water if water is not None else W.rotation_metrics(rot, t)
    soil = soil if soil is not None else d.get("soil_factors") or {
        "drainage_relevance": 1.0, "erosion_relevance": 1.0, "soil_health_relevance": 1.0}

    # WATER — farmer objective "avoid water shortage": mean annual cash-crop water demand that NASA rain and
    # soil storage could not meet (mm, from the daily balance), as a share of summer ET0; + literature drought tolerance.
    ref = d.get("water_reference_mm") or 769.0
    deficit_index = float(np.clip(1 - water["unmet_mm_cash_per_year"] / ref, 0, 1))
    w_score = 0.5 * deficit_index + 0.5 * T("drought_tol", mains)

    # CLIMATE FIT — FAO GAEZ suitability, heat tolerance, wet-soil tolerance where drainage is slow, and
    # DROUGHT YIELD RISK = relative yield (FAO-33 Ky) in the driest quarter of crop-seasons (downside, not mean).
    # Overlap with WATER is intentional and documented: water = average shortage, this = bad-year yield risk.
    gmax = gaez.max()
    g = float(np.mean([gaez.get(t.loc[c, "gaez_crop"], np.nan) / gmax for c in mains]))
    wet = 1 - soil["drainage_relevance"] * (1 - T("waterlog_tol", mains))
    drought_risk = 1.0 if irrigation else water["rel_yield_p25"]
    climate = 0.4 * g + 0.2 * T("heat_tol", mains) + 0.2 * wet + 0.2 * drought_risk

    # SOIL HEALTH — residue, N fixing, roots, living cover, low N demand; scaled by organic-matter need
    cover_years = sum(1 for _, a in rot["years"] if a) / n
    soil_raw = (0.30 * T("residue_om", allc) + 0.20 * float(np.mean([t.loc[c, "n_fixer"] for c in allc]))
                + 0.20 * min(T("root_depth_m", allc) / 2.0, 1) + 0.20 * cover_years + 0.10 * (1 - T("n_demand", mains)))
    soil_score = 1 - soil["soil_health_relevance"] * (1 - soil_raw)

    # EROSION — months with living cover from the field timeline + canopy quality; scaled by erodibility
    bare_months = water["bare_months_per_year"]
    ero_raw = 0.7 * (1 - bare_months / 12) + 0.3 * T("ground_cover", allc)
    erosion = 1 - soil["erosion_relevance"] * (1 - ero_raw)

    # PEST BREAK — no same family back-to-back, more families
    fam = [t.loc[c, "pest_family"] for c in mains]
    repeats = sum(fam[i] == fam[(i + 1) % n] for i in range(n)) if n > 1 else 1
    pests = 0.5 * (1 - repeats / n) + 0.5 * min(len(set(fam)) / 3, 1)

    # MARKET POTENTIAL — county market presence (NASS) − cover-crop cost assumption (+ forage with livestock).
    # Contains no price, cost or predicted yield.
    market = T("market", mains) - 0.08 * cover_years + (0.15 * T("forage_value", mains) if livestock else 0)

    need = water["crop_water_demand_mm_yr"]
    return {
        "water": round(float(w_score), 3), "climate_fit": round(float(climate), 3),
        "soil_health": round(float(soil_score), 3), "erosion_protection": round(float(erosion), 3),
        "pest_break": round(float(pests), 3), "market_potential": round(float(np.clip(market, 0, 1)), 3),
        "_bare_months": round(bare_months, 1), "_water_need_mm": round(need, 0),
        "_unmet_water_pct": round(100 * water["unmet_fraction_cash"], 1),
        "_unmet_water_mm": round(water["unmet_mm_cash_per_year"], 0),
        "_drought_rel_yield_p25": round(water["rel_yield_p25"], 3),
        "_rel_yield_mean": round(water["rel_yield_mean"], 3),
        "_water_model": WATER_MODEL,
        "_gaez_mean": round(g * gmax, 0),
        "_hot_dry_year_yield_change_pct": _rf_loss(d, mains),
    }


def _rf_loss(d, mains):
    """Random Forest 2012-like loss, kept for the evidence text only (not a score input)."""
    loss = d.get("hot_dry_loss", {})
    v = [loss[c] for c in mains if c in loss]
    return round(float(np.mean(v)), 1) if v else None


def total_score(s: dict, priorities: dict) -> float:
    w = {**FIXED_WEIGHTS, **priorities}
    return round(sum(s[k] * w[k] for k in w) / sum(w.values()), 3)


# ============================================================================ 3. explanations
def explain(key: str, rot: dict, s: dict, base: dict, farm: dict, d: dict) -> dict:
    t, ym = d["traits"], d.get("yield_model")
    crops = list(dict.fromkeys(c for pair in rot["years"] for c in pair if c))
    new = [c for c in crops if c not in ("corn", "soybean")]
    labels = ", ".join(t.loc[c, "label"] for c in new)
    diff = {k: s[k] - base[k] for k in SCORE_KEYS}
    nice = lambda k: k.replace("_", " ")
    up = [nice(k) for k, v in sorted(diff.items(), key=lambda x: -x[1]) if v > 0.03][:3]
    down = [nice(k) for k, v in sorted(diff.items(), key=lambda x: x[1]) if v < -0.03][:2]

    if key == "current_corn_soy":
        why = (f"This is what the field has grown every year {farm['current_rotation_years']} "
               "(USDA CropScape). It is shown as the baseline to compare against.")
    else:
        why = (f"Adds {labels} to address the farm's main problems. "
               f"Better than the current rotation on: {', '.join(up) or 'similar overall'}.")

    reg = farm["recent_regimes"]
    na = "not available (dataset missing)"
    evidence = []
    if _ok(farm["observed_bare_months_since_2015"]):
        evidence.append(
            f"Field cover from space (NASA MODIS NDVI): the field was bare ~{farm['observed_bare_months_2005_2007']} "
            f"months/yr in 2005–07 (pasture) but ~{farm['observed_bare_months_since_2015']} months/yr since 2015 under "
            f"corn–soybean; winter greenness trend {farm['trend_winter_ndvi']}. "
            f"This rotation would leave it bare ~{s['_bare_months']} months/yr (current: {base['_bare_months']}).")
    else:
        evidence.append(f"Field cover from space (NASA MODIS): {na}. Modelled bare months from crop calendars: "
                        f"~{s['_bare_months']} months/yr (current: {base['_bare_months']}).")
    eco = (f" NASA ECOSTRESS shows crops used only {100 * farm['eco_et_to_et0_jul_aug']:.0f}% of demand in Jul–Aug "
           "(water-limited)." if _ok(farm["eco_et_to_et0_jul_aug"]) else f" NASA ECOSTRESS crop water use: {na}.")
    evidence.append(
        f"Water: May–Sep crop water demand (ET0, NASA POWER) {farm['gs_et0_mm']:.0f} mm vs rain (NASA GPM IMERG) "
        f"{farm['gs_rain_mm']:.0f} mm → shortfall {-farm['gs_water_balance_mm']:.0f} mm.{eco} "
        f"NASA daily water balance: this rotation's cash crops lack {s['_unmet_water_pct']:.0f}% of their water demand "
        f"(current: {base['_unmet_water_pct']:.0f}%); modelled crop-water demand {s['_water_need_mm']:.0f} mm/yr "
        f"(current: {base['_water_need_mm']:.0f} mm).")
    if _ok(farm["smap_apr_may"]) and _ok(farm["smap_jul_aug"]):
        evidence.append(f"Soil moisture (NASA SMAP): {farm['smap_apr_may']:.2f} m³/m³ in Apr–May falling to "
                        f"{farm['smap_jul_aug']:.2f} m³/m³ in Jul–Aug, when corn silks and soybeans fill pods.")
    else:
        evidence.append(f"Soil moisture (NASA SMAP): {na}.")
    evidence += [
        f"Climate regimes (K-means on 21 growing seasons): {farm['hot_dry_seasons']} of 21 were 'Hot & dry', "
        f"including {sum(v == 'Hot & dry' for v in reg.values())} of the last 5 ({', '.join(map(str, reg))}). "
        f"Temperature trend {farm['trend_temperature']}.",
        f"FAO GAEZ climate suitability of the main crops: {s['_gaez_mean']:.0f}/10000 (current: {base['_gaez_mean']:.0f}).",
        "Soil (USDA SSURGO): " + ", ".join(x for x in [
            f"{farm['soil_om_pct']:.1f}% organic matter" if _ok(farm["soil_om_pct"]) else "organic matter not available",
            f"subsoil up to {farm['subsoil_max_clay_pct']:.0f}% clay" if _ok(farm["subsoil_max_clay_pct"]) else None,
            f"pH {farm['soil_ph']:.1f}" if _ok(farm["soil_ph"]) else "pH not available",
            f"erodibility Kw {farm['soil_kw']:.2f}" if _ok(farm["soil_kw"]) else None] if x) + ".",
    ]
    if ym and ym.get("year_2012"):
        v = ym["validation"]["overall"][ym["model_of_record"]]
        y = ym["year_2012"]
        cl = d.get("crop_losses", {})
        prov = sorted({cl[c]["provenance"] for c in dict.fromkeys(m for m, _ in rot["years"]) if c in cl})
        evidence.append(
            f"Yield history (USDA NASS, observed): in 2012 county yields fell {-y['corn']['observed_pct_change_vs_trend']:.0f}% "
            f"(corn), {-y['soybean']['observed_pct_change_vs_trend']:.0f}% (soybean), {-y['sorghum']['observed_pct_change_vs_trend']:.0f}% "
            f"(sorghum) below trend; winter wheat averaged "
            f"{ym['crop_sensitivity']['wheat']['avg_yield_pct_in_hottest_quarter_of_years']:.0f}% of trend in the hottest years. "
            f"Secondary Random Forest check (held-out error ±{v['MAE_pct_points']:.0f} points): with 2012 held out it predicted only "
            f"{-y['corn']['held_out_rf_prediction_pct_change']:.0f}% / {-y['soybean']['held_out_rf_prediction_pct_change']:.0f}% / "
            f"{-y['sorghum']['held_out_rf_prediction_pct_change']:.0f}% — it under-estimates extreme losses. "
            f"Sources of the crop-loss values for this rotation's crops: {'; '.join(LOSS_PROVENANCE[p] for p in prov)}.")

    benefits = []
    if diff["erosion_protection"] > 0.03:
        benefits.append(f"Cuts bare-soil time by {base['_bare_months'] - s['_bare_months']:.1f} months/yr, protecting the soil "
                        f"from ~{farm['offseason_rain_mm']:.0f} mm of off-season rain.")
    if diff["soil_health"] > 0.03:
        benefits.append("More roots and residue → builds organic matter and improves infiltration into the dense clay subsoil.")
    if any(t.loc[c, "n_fixer"] for c in new):
        benefits.append("A legume in the rotation fixes nitrogen → lower fertilizer need for the following grass crop.")
    if s["_unmet_water_pct"] < base["_unmet_water_pct"] - 1:
        benefits.append(f"Less crop water stress in the NASA daily water balance: {s['_unmet_water_pct']:.0f}% of cash-crop "
                        f"water demand unmet vs {base['_unmet_water_pct']:.0f}% for the current rotation (2006–2025).")
    if s["_drought_rel_yield_p25"] > base["_drought_rel_yield_p25"] + 0.02:
        benefits.append(f"Lower drought-year risk: modelled relative yield in the driest quarter of seasons "
                        f"{100 * s['_drought_rel_yield_p25']:.0f}% vs {100 * base['_drought_rel_yield_p25']:.0f}% (FAO-33 Ky; "
                        "modelled estimate, not a forecast).")
    if diff["pest_break"] > 0.03:
        benefits.append("More crop families → breaks corn rootworm and soybean pest cycles"
                        + (" (sorghum is not a rootworm host)." if "sorghum" in crops else "."))
    if diff["market_potential"] > 0.03:
        benefits.append("Higher market potential (crops widely traded in the county, or forage value).")
    if not benefits and key != "current_corn_soy":
        benefits.append("Similar to the current rotation overall.")

    gaps = [
        "Market potential is not income: crop prices, input costs and contracts are not modelled; the score reflects which crops are traded in Riley County (USDA NASS).",
        "The water balance is an exploratory calibrated model: runoff and irrigation are not modelled and the claypan rooting limit is inferred from SSURGO.",
        "County yields include irrigated fields, so the yield model cannot fairly rank corn vs. sorghum heat tolerance.",
        "SMAP soil moisture is a 9 km average that mixes this field with its neighbours; ECOSTRESS observes on irregular days.",
        "Crop-trait values are regional figures from K-State, UNL, USDA and peer-reviewed sources, not trials on this field.",
    ]
    risks = [f"{t.loc[c, 'label']}: {t.loc[c, 'risk_note']}" for c in (new if new else crops)]
    if down:
        risks.insert(0, f"Scores lower than the current rotation on: {', '.join(down)}.")
    return {"why": why, "evidence": evidence, "benefits": benefits,
            "information_gaps": gaps, "risks_for_local_review": risks}


# ============================================================================ 4. recommend
def recommend(priorities: dict | None = None, livestock: bool | None = None, d: dict | None = None,
              constraints: dict | None = None) -> dict:
    """priorities: farmer weights 0–5; constraints: see DEFAULT_CONSTRAINTS.
    `livestock` is kept for backward compatibility and maps to constraints['forage_market_or_livestock']."""
    priorities = validate_priorities(priorities)
    if livestock is not None:
        constraints = {**(constraints or {}), "forage_market_or_livestock": bool(livestock)}
    constraints = validate_constraints(constraints)
    livestock = constraints["forage_market_or_livestock"]
    d = d or load_data()
    farm = diagnose_farm(d)
    water = d.get("water") or water_metrics(d)
    scored = {k: score_rotation(r, d, farm, livestock, water=water[k], irrigation=constraints["irrigation_available"],
                                soil=d.get("soil_factors")) for k, r in CANDIDATES.items()}
    for k in scored:
        scored[k]["total"] = total_score(scored[k], priorities)
    soil = {"ph": farm["soil_ph"], "min_ksat_um_s": farm["soil_min_ksat_um_s"], "max_clay_pct": farm["subsoil_max_clay_pct"]}
    cur_need = scored["current_corn_soy"]["_water_need_mm"]
    feas = {k: F.evaluate(k, r, d["traits"], soil, constraints, scored[k]["_water_need_mm"], cur_need)
            for k, r in CANDIDATES.items()}
    ranking = sorted(scored, key=lambda k: -scored[k]["total"])
    eligible = [k for k in ranking if k != "current_corn_soy" and feas[k]["status"] != F.INFEASIBLE]
    base = scored["current_corn_soy"]
    chosen = ["current_corn_soy"] + eligible[:2]
    notices = []
    alts = eligible[:2]
    if len(alts) == 2 and abs(scored[alts[0]]["total"] - scored[alts[1]]["total"]) < NEAR_TIE:
        notices.append(f"Near-tie: '{CANDIDATES[alts[0]]['name']}' and '{CANDIDATES[alts[1]]['name']}' differ by "
                       f"{abs(scored[alts[0]]['total'] - scored[alts[1]]['total']):.3f} (< {NEAR_TIE}); treat them as equally "
                       "good and choose on the trade-offs, not the order.")
    if len(eligible) < 2:
        notices.append(f"Only {len(eligible)} alternative rotation(s) passed the feasibility checks for your situation.")
    excluded = [k for k in ranking if k != "current_corn_soy" and feas[k]["status"] == F.INFEASIBLE]
    if excluded:
        notices.append("Not shown because they are infeasible for your situation: "
                       + "; ".join(f"{CANDIDATES[k]['name']} (" + ", ".join(dict.fromkeys(
                           i["check"].replace("_", " ") for i in feas[k]["issues"] if i["severity"] == F.INFEASIBLE)) + ")"
                           for k in excluded) + ".")
    def tie_partners(k):
        return [o for o in eligible if o != k and abs(scored[o]["total"] - scored[k]["total"]) < NEAR_TIE]

    strategies = []
    for k in chosen:
        strategies.append({
            "id": k, "name": CANDIDATES[k]["name"],
            "rotation": [[d["traits"].loc[c, "label"] if c else None for c in pair] for pair in CANDIDATES[k]["years"]],
            "rank": ranking.index(k) + 1,
            "rank_among_eligible": (eligible.index(k) + 1) if k in eligible else None,
            "scores": {kk: v for kk, v in scored[k].items() if not kk.startswith("_")},
            "bare_months_per_year": scored[k]["_bare_months"],
            "water_need_mm_per_year": scored[k]["_water_need_mm"],
            "hot_dry_year_yield_change_pct": scored[k]["_hot_dry_year_yield_change_pct"],
            "feasibility": feas[k],
            "near_tie": bool(tie_partners(k)) if k != "current_corn_soy" else False,
            "near_tie_with": tie_partners(k) if k != "current_corn_soy" else [],
            "strongest": max(SCORE_KEYS, key=lambda x: scored[k][x]),
            "weakest": min(SCORE_KEYS, key=lambda x: scored[k][x]),
            "change_vs_current": {x: round(scored[k][x] - base[x], 3) for x in SCORE_KEYS + ["total"]},
            **explain(k, CANDIDATES[k], scored[k], base, farm, d),
        })
    return {"farm": farm, "priorities": priorities, "constraints": constraints, "livestock": livestock,
            "all_scores": scored, "ranking": ranking, "eligible_ranking": eligible,
            "feasibility": feas, "notices": notices, "strategies": strategies,
            "soil_factors": d.get("soil_factors"),
            "known_limitations": [WATER_MODEL_NOTE] + [
                f"Optional dataset '{k}' was not available; evidence that depends on it is omitted."
                for k, v in farm.get("data_availability", {}).items() if v != "ok"],
            "data_availability": farm.get("data_availability", {}),
            "disclaimer": "Decision support only. Review every suggestion with the farmer and a local agronomist."}
