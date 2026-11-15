"""
Time-series analysis of the master monthly table.

- Monthly climatology (mean seasonal cycle) of every key variable.
- Long-term trends with the Theil–Sen estimator and the Mann–Kendall test
  (robust to outliers and non-normal data; standard in climate analysis).
- Observed bare-soil months from MODIS NDVI, per year, and the measured effect
  of the off-season on soil cover.
- Satellite agreement checks (SMAP vs. POWER soil wetness; ECOSTRESS ET vs. ET0).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .. import config as C

CLIM_VARS = ["temp_mean_c", "rain_gpm_imerg_mm", "et0_hargreaves_mm", "water_balance_mm",
             "heat_stress_days", "frost_days", "heavy_rain_days", "soil_wetness_root_0_1",
             "smap_soil_moisture_m3m3", "ndvi", "evi", "eco_lst_day_c", "eco_et_mm_day",
             "eco_et_to_et0_ratio"]


def climatology(master: pd.DataFrame) -> pd.DataFrame:
    g = master.groupby("month")[CLIM_VARS]
    out = g.mean().round(3).add_suffix("_mean").join(g.std().round(3).add_suffix("_std"))
    out = out.join(g.count().add_suffix("_n"))
    return out.reset_index()


MIN_YEARS_FOR_TREND = 5


def _num(v, nd=None):
    """float or None (JSON-safe; NaN never written as a number)."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(v):
        return None
    return round(v, nd) if nd is not None else v


def mann_kendall_theil_sen(years, values) -> dict:
    s = pd.Series(np.asarray(values, float), index=np.asarray(years, float)).dropna()
    if len(s) < 6:
        return {"n_years": len(s), "slope_per_decade": np.nan, "p_value": np.nan, "significant_5pct": False}
    res = stats.theilslopes(s.values, s.index.values)
    tau, p = stats.kendalltau(s.index.values, s.values)
    return {"n_years": int(len(s)), "slope_per_decade": round(float(res.slope * 10), 3),
            "slope_ci95_low": round(float(res.low_slope * 10), 3), "slope_ci95_high": round(float(res.high_slope * 10), 3),
            "kendall_tau": round(float(tau), 3), "p_value": round(float(p), 4), "significant_5pct": bool(p < 0.05)}


TREND_SPECS = [
    # (label, variable, months, aggregation, unit)
    ("Mean annual temperature", "temp_mean_c", range(1, 13), "mean", "°C"),
    ("Summer (Jun–Aug) mean temperature", "temp_mean_c", [6, 7, 8], "mean", "°C"),
    ("Heat-stress days per year", "heat_stress_days", range(1, 13), "sum", "days"),
    ("Frost days per year", "frost_days", range(1, 13), "sum", "days"),
    ("Annual rain (GPM IMERG)", "rain_gpm_imerg_mm", range(1, 13), "sum", "mm"),
    ("Growing-season rain (May–Sep)", "rain_gpm_imerg_mm", C.GROWING_SEASON, "sum", "mm"),
    ("Growing-season crop water demand ET0", "et0_hargreaves_mm", C.GROWING_SEASON, "sum", "mm"),
    ("Growing-season water balance", "water_balance_mm", C.GROWING_SEASON, "sum", "mm"),
    ("Heavy-rain days per year (≥25 mm)", "heavy_rain_days", range(1, 13), "sum", "days"),
    ("Root-zone soil wetness, Jul–Aug (POWER)", "soil_wetness_root_0_1", [7, 8], "mean", "0–1"),
    ("SMAP soil moisture, Jul–Aug (2015–2025)", "smap_soil_moisture_m3m3", [7, 8], "mean", "m³/m³"),
    ("Peak summer NDVI (MODIS, Jun–Aug max)", "ndvi", [6, 7, 8], "max", "NDVI"),
    ("Winter NDVI (MODIS, Dec–Feb mean)", "ndvi", [12, 1, 2], "mean", "NDVI"),
]


def trends(master: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for label, var, months, how, unit in TREND_SPECS:
        sub = master[master.month.isin(list(months))].dropna(subset=[var])
        yearly = sub.groupby("year")[var].agg(how)
        counts = sub.groupby("year")[var].count()
        yearly = yearly[counts >= max(1, len(list(months)) // 2)]
        if len(yearly) < MIN_YEARS_FOR_TREND:          # dataset missing or too short: report, don't compute
            rows.append({"indicator": label, "variable": var, "unit": unit, "first_year": None, "last_year": None,
                         "mean": None, "n_years": int(len(yearly)), "slope_per_decade": None, "slope_ci95_low": None,
                         "slope_ci95_high": None, "kendall_tau": None, "p_value": None, "significant_5pct": False,
                         "available": False})
            continue
        r = mann_kendall_theil_sen(yearly.index, yearly.values)
        rows.append({"indicator": label, "variable": var, "unit": unit,
                     "first_year": int(yearly.index.min()), "last_year": int(yearly.index.max()),
                     "mean": round(float(yearly.mean()), 3), **r, "available": True})
    return pd.DataFrame(rows)


def bare_soil_by_year(master: pd.DataFrame) -> pd.DataFrame:
    """Months per year with NDVI below the bare-soil threshold (observed, MODIS)."""
    m = master.dropna(subset=["ndvi"])
    g = m.groupby("year")
    out = pd.DataFrame({
        "months_with_ndvi": g.ndvi.count(),
        "bare_months_observed": g.ndvi.apply(lambda s: int((s < C.NDVI_BARE).sum())),
        "peak_ndvi": g.ndvi.max().round(3),
        "winter_ndvi_mean": m[m.month.isin([12, 1, 2])].groupby("year").ndvi.mean().round(3),
        "crop_grown": g.crop_grown.first(),
    })
    out["bare_months_scaled_to_12"] = (out.bare_months_observed * 12 / out.months_with_ndvi).round(1)
    return out.reset_index()


def agreement_checks(master: pd.DataFrame) -> dict:
    def pair(a, b):
        m = master.dropna(subset=[a, b])
        if len(m) < 10:
            return {"pearson_r": None, "p": None, "n_months": int(len(m)), "available": False}
        r = stats.pearsonr(m[a], m[b])
        return {"pearson_r": round(float(r[0]), 3), "p": float(r[1]), "n_months": int(len(m)), "available": True}
    return {
        "smap_vs_power_surface_wetness": pair("smap_soil_moisture_m3m3", "soil_wetness_top_0_1"),
        "ecostress_et_vs_et0": pair("eco_et_mm_day", "et0_mm_day"),
        "ndvi_vs_ecostress_et": pair("ndvi", "eco_et_mm_day"),
    }


def summarise(master, clim, trend_df, bare) -> dict:
    """Headline numbers. Values from a missing optional dataset are None, never NaN or invented."""
    tr = trend_df.set_index("indicator")
    get = lambda k: {kk: (_num(v) if isinstance(v, (float, np.floating)) else v) for kk, v in tr.loc[k].to_dict().items()}
    gs = master[master.month.isin(C.GROWING_SEASON)].groupby("year")
    off = master[master.month.isin(C.OFF_SEASON)]
    ndvi_clim = clim.set_index("month").ndvi_mean.dropna()
    mean_of = lambda months, col, nd: _num(master[master.month.isin(months)][col].mean(), nd)
    has_bare = len(bare) > 0
    return {
        "observed_bare_months_per_year_mean": _num(bare.bare_months_scaled_to_12.mean(), 1) if has_bare else None,
        "observed_bare_months_since_2010": _num(bare[bare.year >= 2010].bare_months_scaled_to_12.mean(), 1) if has_bare else None,
        "ndvi_seasonal_cycle": {int(k): round(float(v), 3) for k, v in ndvi_clim.items()},
        "months_below_bare_threshold_climatology": [int(k) for k, v in ndvi_clim.items() if v < C.NDVI_BARE],
        "offseason_rain_mm_mean": _num(off.groupby("year").rain_gpm_imerg_mm.sum().mean(), 0),
        "offseason_heavy_rain_days_mean": _num(off.groupby("year").heavy_rain_days.sum().mean(), 1),
        "gs_rain_mm_mean": _num(gs.rain_gpm_imerg_mm.sum().mean(), 0),
        "gs_et0_mm_mean": _num(gs.et0_hargreaves_mm.sum().mean(), 0),
        "gs_water_balance_mm_mean": _num(gs.water_balance_mm.sum().mean(), 0),
        "eco_et_to_et0_jul_aug_mean": mean_of([7, 8], "eco_et_to_et0_ratio", 2),
        "smap_jul_aug_mean": mean_of([7, 8], "smap_soil_moisture_m3m3", 3),
        "smap_apr_may_mean": mean_of([4, 5], "smap_soil_moisture_m3m3", 3),
        "summer_lst_day_c_mean": mean_of([6, 7, 8], "eco_lst_day_c", 1),
        "trend_temperature": get("Mean annual temperature"),
        "trend_heat_days": get("Heat-stress days per year"),
        "trend_gs_water_balance": get("Growing-season water balance"),
        "trend_gs_rain": get("Growing-season rain (May–Sep)"),
        "trend_peak_ndvi": get("Peak summer NDVI (MODIS, Jun–Aug max)"),
        "agreement": agreement_checks(master),
    }
