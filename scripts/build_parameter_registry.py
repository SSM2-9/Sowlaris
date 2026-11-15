"""
Builds fieldshift/engine/parameter_registry.csv — one row per influential number (audit item 17).

value_type:
    measured            measured on/for this field or county (none of the crop traits are)
    literature          a number (or range) stated by the cited source
    literature_range    the value is chosen inside a published range
    expert_estimate     0–1 score set by the team, informed by the cited literature (not calibrated)
    regional_practice   typical calendar; to be verified with K-State planting-date guidance
    assumption          developer choice with no direct source
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from fieldshift import config as C  # noqa: E402

IN2MM = 25.4
# Published ranges for literature values (source text is in crop_traits.csv `source`)
WATER_RANGE_MM = {"corn": (24 * IN2MM, 30 * IN2MM), "soybean": (18 * IN2MM, 24 * IN2MM),
                  "sorghum": (18 * IN2MM, 22 * IN2MM), "winter_wheat": (16 * IN2MM, 19 * IN2MM),
                  "alfalfa": (34 * IN2MM, 36 * IN2MM), "sunflower": (20 * IN2MM, 24 * IN2MM)}
ROOT_RANGE_M = {  # source → range (m)
    "corn": ((1.5, 1.8), "UW-Madison 5–6 ft; FAO-56 Table 22: 1.0–1.7 m"),
    "sorghum": ((0.9, 1.2), "UW-Madison 3–4 ft; FAO-56 Table 22: 1.0–2.0 m"),
    "winter_wheat": ((1.5, 1.8), "FAO-56 Table 22: 1.5–1.8 m (literature reference; 1.5 m used, changed from 1.2 m)"),
    "alfalfa": ((1.0, 2.4), "FAO-56 Table 22 hay 1.0–2.0 m; Stone et al. 1982 water extraction to ~8 ft (2.4 m)"),
    "soybean": ((0.6, 1.5), "FAO-56 Table 22: 0.6–1.3 m; Martin et al. 1990: 2.6–5.0 ft — VALUE 1.5 m AT THE TOP (flagged)"),
    "sunflower": ((0.8, 1.5), "FAO-56 Table 22: 0.8–1.5 m — VALUE 2.0 m ABOVE THIS RANGE (flagged; crop not in candidates)"),
}
EXPERT_COLS = {"drought_tol": "0–1", "heat_tol": "0–1", "waterlog_tol": "0–1", "n_demand": "0–1",
               "residue_om": "0–1", "ground_cover": "0–1", "forage_value": "0–1"}


def crop_rows(t: pd.DataFrame):
    for crop, r in t.iterrows():
        src = r.source
        lo, hi = WATER_RANGE_MM.get(crop, (None, None))
        yield dict(parameter="water_need_mm", crop=crop, value=r.water_need_mm, unit="mm/season",
                   value_type="literature_range" if lo else "assumption", source=src if lo else
                   ("ASSUMPTION — no direct source" + (f"; {src}" if isinstance(src, str) else "")),
                   range_low=round(lo) if lo else None, range_high=round(hi) if hi else None)
        rr = ROOT_RANGE_M.get(crop)
        yield dict(parameter="root_depth_m", crop=crop, value=r.root_depth_m, unit="m",
                   value_type="literature_range" if rr else "assumption", source=rr[1] if rr else "ASSUMPTION",
                   range_low=rr[0][0] if rr else None, range_high=rr[0][1] if rr else None)
        for col, unit in EXPERT_COLS.items():
            yield dict(parameter=col, crop=crop, value=r[col], unit=unit, value_type="expert_estimate",
                       source=f"team estimate informed by: {src}", range_low=max(0, r[col] - 0.15),
                       range_high=min(1, r[col] + 0.15))
        yield dict(parameter="market", crop=crop, value=r.market, unit="0–1", value_type="assumption",
                   source="team judgement of county market presence (USDA NASS acreage); no prices",
                   range_low=max(0, r.market - 0.15), range_high=min(1, r.market + 0.15))
        yield dict(parameter="n_fixer", crop=crop, value=r.n_fixer, unit="0/1", value_type="literature",
                   source="legume / non-legume (botanical fact)", range_low=r.n_fixer, range_high=r.n_fixer)
        yield dict(parameter="months", crop=crop, value=r.months, unit="month range", value_type="regional_practice",
                   source="typical NE Kansas calendar; see crop_requirements.csv", range_low=None, range_high=None)


def engine_rows():
    from fieldshift.engine import recommender as R
    from fieldshift.models import water_balance as W
    rows = [
        ("fixed_weight_climate_fit", R.FIXED_WEIGHTS["climate_fit"], "weight", "assumption", 1.5, 2.5),
        ("fixed_weight_pest_break", R.FIXED_WEIGHTS["pest_break"], "weight", "assumption", 0.5, 1.5),
        ("water_score_split_balance_vs_drought_tol", 0.5, "share", "assumption", 0.3, 0.7),
        ("climate_fit_gaez_share", 0.4, "share", "assumption", None, None),
        ("climate_fit_heat_share", 0.2, "share", "assumption", None, None),
        ("climate_fit_wet_share", 0.2, "share", "assumption", None, None),
        ("climate_fit_drought_risk_share", 0.2, "share", "assumption", None, None),
        ("soil_health_residue_share", 0.30, "share", "assumption", None, None),
        ("soil_health_nfix_share", 0.20, "share", "assumption", None, None),
        ("soil_health_root_share", 0.20, "share", "assumption", None, None),
        ("soil_health_cover_share", 0.20, "share", "assumption", None, None),
        ("soil_health_low_n_share", 0.10, "share", "assumption", None, None),
        ("erosion_cover_months_share", 0.7, "share", "assumption", None, None),
        ("cover_crop_cost_penalty", 0.08, "score", "assumption", 0.0, 0.16),
        ("forage_bonus_with_livestock", 0.15, "score", "assumption", 0.05, 0.25),
        ("near_tie_threshold", R.NEAR_TIE, "score", "assumption", None, None),
        ("water_bare_soil_evaporation_K", W.K_BARE, "–", "literature_range", 0.2, 0.4),
        ("water_total_evaporable_water_mm", W.TEW_MM, "mm", "literature_range", 18, 30),
        ("claypan_clay_pct", W.CLAYPAN_CLAY_PCT, "%", "assumption", None, None),
        ("claypan_ksat_um_s", W.CLAYPAN_KSAT_UM_S, "µm/s", "literature", None, None),
        ("claypan_clay_jump_pct", W.CLAYPAN_CLAY_JUMP, "%", "assumption", None, None),
    ] + [(f"soil_param_{k}", v, "–", "assumption", None, None) for k, v in R.SOIL_PARAMS.items()]
    for k, v in W.PARAMS["Ky"].items():
        rows.append((f"Ky_{k}", v, "–", "literature", v, v))
    for k, v in W.PARAMS["p"].items():
        rows.append((f"p_{k}", v, "–", "assumption" if "cover" in k else "literature", None, None))
    src = {"Ky": W.PARAMS["Ky_source"], "p_": W.PARAMS["p_source"], "water_": "FAO-56 (Allen et al. 1998)",
           "claypan_ksat": "NRCS Ksat classes"}
    for name, val, unit, vt, lo, hi in rows:
        s = next((v for k, v in src.items() if name.startswith(k)), "engine code (recommender.py / water_balance.py)")
        yield dict(parameter=name, crop="", value=val, unit=unit, value_type=vt, source=s, range_low=lo, range_high=hi)


def main():
    t = pd.read_csv(C.ENGINE_DIR / "crop_traits.csv").set_index("crop")
    reg = pd.DataFrame(list(crop_rows(t)) + list(engine_rows()))
    reg["flag"] = [("OUTSIDE published range" if (pd.notna(lo) and pd.notna(hi) and isinstance(v, (int, float))
                    and not lo - 1e-9 <= float(v) <= hi + 1e-9) else "")
                   for v, lo, hi in zip(reg.value, reg.range_low, reg.range_high)]
    out = C.ENGINE_DIR / "parameter_registry.csv"
    reg.to_csv(out, index=False)
    print(reg.value_type.value_counts().to_string())
    print(reg[reg.flag != ""][["parameter", "crop", "value", "range_low", "range_high"]].to_string(index=False))
    return reg


if __name__ == "__main__":
    main()
