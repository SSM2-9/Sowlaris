"""
Daily soil-water balance driven by NASA data (audit item 7).  EXPLORATORY CALIBRATED MODEL.

Inputs
    rain  P   NASA GPM IMERG daily precipitation (POWER IMERG_PRECTOT), mm/day
    ET0       FAO-56 Hargreaves reference evapotranspiration from NASA POWER temperature, mm/day
    soil      USDA SSURGO horizons → plant-available water within each crop's root zone

Daily accounting (one profile reservoir, 0–2 m)
    S_{t+1} = S_t + P_t − ETa_t − D_t          irrigation I = 0 (dryland) · runoff R = 0 (not modelled)
    0 ≤ S ≤ TAW_profile;   D = water above TAW_profile (deep drainage)
    crop on the field:  ETc = Kc · ET0
                        accessible water  S_c = S · TAW_c / TAW_profile   (uniform-profile assumption)
                        FAO-56 water-stress coefficient  Ks = 1 if S_c ≥ (1−p)·TAW_c else S_c / ((1−p)·TAW_c)
                        ETa = min(Ks · ETc, S_c)
    bare soil:          Ea = min(K_bare · ET0, water in the top evaporable layer)

Crop yield response (FAO-33, as reproduced in FAO-66 Table 1, seasonal Ky)
    Ya/Ym = 1 − Ky · (1 − ΣETa / ΣETc)   per crop-season, bounded to [0, 1]; FAO notes linearity holds
    up to ~50 % ET deficit — seasons beyond that are flagged.

Every parameter, its value and its source is in PARAMS below and in docs/METHODOLOGY.md.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from .. import config as C

PROFILE_DEPTH_M = 2.0           # SSURGO export covers 0–79 in (2.0 m)
K_BARE = 0.3                    # ASSUMPTION: bare-soil evaporation coefficient (FAO-56 Kc_ini range ~0.2–0.4)
TEW_MM = 25.0                   # ASSUMPTION: total evaporable water of the top layer, silty clay loam (FAO-56 Table 19 range)

# EXPERIMENTAL runoff (audit items 8–9). OFF in production (runoff=None). SCS Curve Number method,
# Q = (P − Ia)² / (P − Ia + S), Ia = 0.2·S, S = 25400/CN − 254 (mm), applied to DAILY rain (a known simplification:
# CN was developed for storm totals; antecedent-moisture adjustment not applied). CN values: USDA NRCS TR-55 (1986)
# Table 2-2b, cultivated land, average moisture (AMC II). Hydrologic soil group of the field is NOT in our SSURGO
# export; Wymore (claypan, Aquic Argiudoll) is tested as group C and D.
RUNOFF_SCENARIOS = {
    "none (production)": None,
    "HSG C, good condition": {"row": 82, "close": 81, "bare": 88},   # SR+CR good; close-seeded SR good; fallow CR good
    "HSG D, good condition": {"row": 85, "close": 85, "bare": 90},
    "HSG D, poor condition": {"row": 91, "close": 89, "bare": 94},   # SR poor; close-seeded SR poor; bare soil
}
CLOSE_SEEDED = {"winter_wheat", "alfalfa", "oats", "cereal_rye_cover", "hairy_vetch_cover"}


def scs_runoff(p_mm: float, cn: float) -> float:
    s = 25400.0 / cn - 254.0
    ia = 0.2 * s
    return (p_mm - ia) ** 2 / (p_mm - ia + s) if p_mm > ia else 0.0


# value, source / type
PARAMS = {
    "Ky": {  # FAO-33 seasonal yield-response factors (FAO-66 Table 1)
        "corn": 1.25, "soybean": 0.85, "sorghum": 0.9, "winter_wheat": 1.05, "dc_soybean": 0.85,
        "alfalfa": 1.1, "sunflower": 0.95,
    },
    "Ky_source": "FAO Irrigation & Drainage Paper 33 seasonal Ky, reproduced in FAO-66 (2012) Table 1",
    "p": {   # FAO-56 Table 22 soil-water depletion fraction for no stress (ET ≈ 5 mm/day)
        "corn": 0.55, "sorghum": 0.55, "winter_wheat": 0.55, "alfalfa": 0.55, "oats": 0.55, "sunflower": 0.45,
        "soybean": 0.50, "dc_soybean": 0.50,                     # soybean: FAO-56 Table 22 (to verify)
        "cereal_rye_cover": 0.55, "hairy_vetch_cover": 0.50,     # ASSUMPTION: cereal / legume defaults
    },
    "p_source": "FAO-56 Table 22 (Allen et al. 1998); cover-crop values assumed",
    "Kc": "seasonal-average Kc = literature seasonal water use (crop_traits.water_need_mm) ÷ climatological "
          "NASA POWER ET0 over the crop's months (calibrated, not FAO-56 stage curves)",
}


# --------------------------------------------------------------------------- inputs
@lru_cache(maxsize=1)
def daily_climate() -> pd.DataFrame:
    d = pd.read_csv(C.OUT["power_daily"], parse_dates=["date"])
    d["year"], d["month"] = d.date.dt.year, d.date.dt.month
    return d[["date", "year", "month", "rain_gpm_imerg_mm", "et0_hargreaves_mm"]].reset_index(drop=True)


# INFERRED effective rooting limit: the top of a claypan horizon (clay ≥ 40 % and lowest Ksat < 0.1 µm/s,
# NRCS "low" conductivity). In this field it is the Wymore claypan at 11 in (0–1 % slope unit) and 6 in
# (eroded 1–3 % unit). Roots can enter claypans, but slowly; treating the claypan top as the effective
# limit is a labelled assumption, tested in tests/test_water_balance.py and in the storage-sensitivity table.
CLAYPAN_CLAY_PCT = 40
CLAYPAN_KSAT_UM_S = 0.1
CLAYPAN_CLAY_JUMP = 8           # % clay increase over the horizon above (abrupt textural change); a uniformly
                                # clayey soil is slow-draining but has no claypan rooting limit


def profile_from_horizons(h: pd.DataFrame, effective_rooting: bool = True) -> pd.DataFrame:
    """Area-weighted plant-available water (mm per cm of depth) on a 1-cm grid, 0–200 cm.
    effective_rooting=True stops counting water below an inferred claypan limit in each map unit."""
    h = h.copy()
    h["awc"] = (h.awc_in_in_low + h.awc_in_in_high) / 2          # in/in = cm/cm
    w = h.drop_duplicates("map_unit").set_index("map_unit").pct_of_field
    depth = np.arange(0, 200)                                     # cm
    out = np.zeros(len(depth))
    limits = {}
    for mu, g in h.groupby("map_unit"):
        col = np.zeros(len(depth))
        for _, r in g.iterrows():
            top, bot = int(round(r.top_in * 2.54)), int(round(r.bottom_in * 2.54))
            col[top:min(bot, 200)] = r.awc * 10                    # mm of water per cm of soil
        g = g.sort_values("top_in")
        jump = g.clay_pct.diff() >= CLAYPAN_CLAY_JUMP                 # abrupt increase over the horizon above
        pan = g[(g.top_in > 0) & jump & (g.clay_pct >= CLAYPAN_CLAY_PCT) & (g.ksat_um_s_low < CLAYPAN_KSAT_UM_S)]
        limits[mu] = int(round(pan.top_in.min() * 2.54)) if len(pan) else 200
        if effective_rooting:
            col[limits[mu]:] = 0
        out += col * w[mu] / w.sum()
    df = pd.DataFrame({"depth_cm": depth, "awc_mm_per_cm": out})
    df.attrs["rooting_limit_cm"] = limits
    return df


@lru_cache(maxsize=2)
def soil_profile(effective_rooting: bool = True) -> pd.DataFrame:
    return profile_from_horizons(pd.read_csv(C.RAW["ssurgo"]), effective_rooting)


def taw_mm(depth_m: float, scale: float = 1.0, effective_rooting: bool = True, profile: pd.DataFrame | None = None) -> float:
    """Total available water (mm) from the surface to depth_m. `scale` is for sensitivity runs only."""
    p = soil_profile(effective_rooting) if profile is None else profile
    return float(p.awc_mm_per_cm[p.depth_cm < depth_m * 100].sum()) * scale


_KC_CACHE: dict = {}


def crop_coefficients(traits: pd.DataFrame) -> dict:
    """Seasonal-average Kc = literature seasonal water use ÷ climatological NASA POWER ET0 over the crop's months.
    Always calibrated on the OBSERVED climate (so counterfactual climates change ETc through ET0, not Kc)."""
    key = tuple(traits.index), tuple(traits.water_need_mm), tuple(traits.months)
    if key not in _KC_CACHE:
        clim = daily_climate().groupby("month").et0_hargreaves_mm.sum() / (C.PERIOD[1] - C.PERIOD[0] + 1)
        _KC_CACHE[key] = {c: float(traits.loc[c, "water_need_mm"] / clim[traits.loc[c, "month_set"]].sum())
                          for c in traits.index}
    return _KC_CACHE[key]


# --------------------------------------------------------------------------- field timeline
def timeline(rot: dict, traits: pd.DataFrame) -> list[list]:
    """Crop on the field in each month of each rotation year (None = bare).

    A main crop whose window wraps the year end (winter wheat, 10-6) was sown the previous autumn, so its
    Oct–Dec months belong to the previous rotation year. A following crop that wraps (rye 10-4, vetch 9-4)
    continues into the next year. If two crops claim the same month, the crop being harvested keeps it.
    """
    n = len(rot["years"])
    grid = [[None] * 12 for _ in range(n)]

    def months(crop):
        a, b = map(int, traits.loc[crop, "months"].split("-"))
        return (list(range(a, b + 1)), []) if a <= b else (list(range(a, 13)), list(range(1, b + 1)))

    def put(y, m, crop):
        y %= n
        if grid[y][m - 1] is None:
            grid[y][m - 1] = crop

    for i, (main, after) in enumerate(rot["years"]):          # first pass: main crops (harvest owners)
        head, tail = months(main)
        if tail:                                               # wrapping main crop: sown in year i−1
            for m in tail:
                put(i, m, main)
        else:
            for m in head:
                put(i, m, main)
    for i, (main, after) in enumerate(rot["years"]):          # autumn part of wrapping main crops
        head, tail = months(main)
        if tail:
            for m in head:
                put(i - 1, m, main)
    for i, (main, after) in enumerate(rot["years"]):          # following crops
        if not after:
            continue
        head, tail = months(after)
        for m in head:
            put(i, m, after)
        for m in tail:
            put(i + 1, m, after)
    return grid


# --------------------------------------------------------------------------- simulation
def simulate(rot: dict, traits: pd.DataFrame, phase: int = 0, rain=None, et0=None,
             storage_scale: float = 1.0, effective_rooting: bool = True,
             profile: pd.DataFrame | None = None, runoff: dict | None = None) -> pd.DataFrame:
    """Daily water balance for one rotation started at `phase`. Returns a daily DataFrame."""
    clim = daily_climate()
    P = clim.rain_gpm_imerg_mm.to_numpy(float) if rain is None else np.asarray(rain, float)
    E = clim.et0_hargreaves_mm.to_numpy(float) if et0 is None else np.asarray(et0, float)
    yrs, mon = clim.year.to_numpy(), clim.month.to_numpy()
    grid, n = timeline(rot, traits), len(rot["years"])
    kc = crop_coefficients(traits)
    taw_prof = taw_mm(PROFILE_DEPTH_M, storage_scale, effective_rooting, profile)
    taw_c = {c: taw_mm(min(traits.loc[c, "root_depth_m"], PROFILE_DEPTH_M), storage_scale, effective_rooting, profile)
             for c in traits.index}
    is_cover = {c: traits.loc[c, "role"] == "cover" for c in traits.index}
    S = taw_prof                                               # start at field capacity (1 Jan 2005)
    out_crop = np.empty(len(P), dtype=object)
    etc, eta, drain, store, roff = (np.zeros(len(P)) for _ in range(5))
    for i in range(len(P)):
        crop = grid[(yrs[i] - C.PERIOD[0] + phase) % n][mon[i] - 1]
        out_crop[i] = crop
        infil = P[i]
        if runoff is not None and P[i] > 0:          # experimental: rain = runoff + infiltration
            cls = "bare" if crop is None else ("close" if crop in CLOSE_SEEDED else "row")
            roff[i] = scs_runoff(P[i], runoff[cls])
            infil = P[i] - roff[i]
        S += infil
        if S > taw_prof:
            drain[i] = S - taw_prof
            S = taw_prof
        bare_e = min(K_BARE * E[i], max(0.0, S - (taw_prof - TEW_MM)))
        if crop is None:
            a = bare_e
        else:
            tc, p = taw_c[crop], PARAMS["p"].get(crop, 0.5)
            s_acc = S * tc / taw_prof if taw_prof > 0 else 0.0
            ks = 1.0 if s_acc >= (1 - p) * tc else (s_acc / ((1 - p) * tc) if tc > 0 else 0.0)
            etc[i] = kc[crop] * E[i]
            a = min(ks * etc[i], s_acc)
            if is_cover[crop]:
                # a cover crop's ET includes soil evaporation: it cannot be below bare-soil evaporation
                # (otherwise the model would credit covers with saving water, an effect it does not represent)
                a = max(a, bare_e)
        eta[i] = a
        S -= a
        store[i] = S
    df = pd.DataFrame({"date": clim.date, "year": yrs, "month": mon, "crop": out_crop, "rain": P, "et0": E,
                       "etc": etc, "eta": eta, "drainage": drain, "storage": store, "runoff": roff})
    df.attrs["taw_profile_mm"] = taw_prof
    return df


def water_conservation_error(sim: pd.DataFrame, storage_scale: float = 1.0, effective_rooting: bool = True) -> float:
    """Σrain − Σrunoff − ΣETa − Σdrainage − ΔS (mm). Exactly 0 for a conserving model."""
    s0 = sim.attrs.get("taw_profile_mm", taw_mm(PROFILE_DEPTH_M, storage_scale, effective_rooting))
    roff = sim["runoff"].sum() if "runoff" in sim else 0.0
    return float(sim.rain.sum() - roff - sim.eta.sum() - sim.drainage.sum() - (sim.storage.iloc[-1] - s0))


def seasons(sim: pd.DataFrame) -> pd.DataFrame:
    """One row per crop-season (contiguous days of the same crop)."""
    s = sim[sim.crop.notna()].copy()
    s["block"] = (s.crop != s.crop.shift()).cumsum() + (s.index.to_series().diff() > 1).cumsum()
    g = s.groupby("block").agg(crop=("crop", "first"), start=("date", "first"), end=("date", "last"),
                               etc=("etc", "sum"), eta=("eta", "sum"))
    g["harvest_year"] = g.end.dt.year
    g["et_ratio"] = (g.eta / g.etc).where(g.etc > 0)
    return g.reset_index(drop=True)


def relative_yield(crop: str, et_ratio: float) -> float | None:
    ky = PARAMS["Ky"].get(crop)
    if ky is None or et_ratio is None or not np.isfinite(et_ratio):
        return None
    return float(np.clip(1 - ky * (1 - et_ratio), 0, 1))


def rotation_metrics(rot: dict, traits: pd.DataFrame, rain=None, et0=None, storage_scale: float = 1.0,
                     years: list | None = None, effective_rooting: bool = True,
                     profile: pd.DataFrame | None = None, runoff: dict | None = None) -> dict:
    """Water metrics for a rotation, averaged over every starting phase so each crop meets every year."""
    seas, demand, bare = [], [], []
    for ph in range(len(rot["years"])):
        sim = simulate(rot, traits, ph, rain, et0, storage_scale, effective_rooting, profile, runoff)
        if years is not None:
            sim_y = sim[sim.year.isin(years)]
        else:
            sim_y = sim[sim.year > C.PERIOD[0]]                 # first year = spin-up
        sz = seasons(sim_y)
        sz["phase"] = ph
        seas.append(sz)
        demand.append(sim_y.groupby("year").etc.sum().mean())
    s = pd.concat(seas, ignore_index=True)
    s = s[s.etc > 1]                                           # drop slivers cut by the period boundary
    role = traits.role.to_dict()
    cash = s[s.crop.map(lambda c: role.get(c) in ("cash", "forage"))].copy()
    cash["rel_yield"] = [relative_yield(c, r) for c, r in zip(cash.crop, cash.et_ratio)]
    unmet = 1 - cash.eta.sum() / cash.etc.sum()
    n_years = len(rot["years"]) * (len(years) if years is not None else (C.PERIOD[1] - C.PERIOD[0]))
    unmet_mm = float((cash.etc - cash.eta).sum() / n_years)        # mean annual cash-crop shortfall, mm/yr
    ry = cash.rel_yield.dropna()
    grid = timeline(rot, traits)
    return {
        "unmet_fraction_cash": float(unmet),
        "unmet_mm_cash_per_year": unmet_mm,
        "rel_yield_mean": float(ry.mean()),
        "rel_yield_p25": float(ry.quantile(0.25)),              # downside risk: driest quarter of crop-seasons
        "crop_water_demand_mm_yr": float(np.mean(demand)),     # modelled ETc incl. cover crops
        "bare_months_per_year": float(np.mean([sum(c is None for c in row) for row in grid])),
        "seasons_beyond_ky_validity": int((cash.et_ratio < 0.5).sum()),
        "n_cash_seasons": int(len(cash)),
        "per_crop_et_ratio": cash.groupby("crop").apply(lambda g: g.eta.sum() / g.etc.sum(), include_groups=False).round(3).to_dict(),
    }
