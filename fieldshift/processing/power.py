"""
Datasets 1 + 3 — NASA POWER (MERRA-2 / CERES) and GPM IMERG precipitation.

Raw:   daily point file from the POWER Data Access Viewer (Agroclimatology,
       UTC, 2005-01-01 … 2025-12-31, lat 39.12 lon -96.63).
Out:   daily table with derived agro-climatic indicators, monthly features
       with anomalies, and a yearly summary.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config as C

RENAME = {
    "ALLSKY_SFC_SW_DWN": "solar_mj_m2_day",
    "T2M": "temp_mean_c",
    "T2M_MAX": "temp_max_c",
    "T2M_MIN": "temp_min_c",
    "RH2M": "humidity_pct",
    "WS2M": "wind_2m_m_s",
    "GWETTOP": "soil_wetness_top_0_1",
    "GWETROOT": "soil_wetness_root_0_1",
    "PRECTOTCORR": "rain_merra2_mm",
    "IMERG_PRECTOT": "rain_gpm_imerg_mm",
}


def read_power_csv(path) -> pd.DataFrame:
    """Read a POWER CSV, skipping the text header block, with -999 → NaN."""
    with open(path) as fh:
        lines = fh.readlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("-END HEADER-")) + 1
    return pd.read_csv(path, skiprows=start).replace(-999, np.nan)


def extraterrestrial_radiation(doy, lat_deg: float):
    """FAO-56 eq. 21: extraterrestrial radiation Ra (MJ m-2 day-1)."""
    phi = np.radians(lat_deg)
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
    delta = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
    ws = np.arccos(-np.tan(phi) * np.tan(delta))
    return (24 * 60 / np.pi) * 0.0820 * dr * (
        ws * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(ws))


def hargreaves_et0(tmean, tmax, tmin, doy, lat_deg: float):
    """FAO-56 eq. 52 Hargreaves reference evapotranspiration (mm day-1).
    Clipped at 0: below a mean of −17.8 °C the empirical formula turns negative, which is not physical
    (6 such days in 2005–2025; found by tests/test_water_balance.py)."""
    ra = extraterrestrial_radiation(doy, lat_deg)
    return np.clip(0.0023 * (tmean + 17.8) * np.sqrt(np.clip(tmax - tmin, 0, None)) * ra * 0.408, 0, None)


def build_daily(raw: pd.DataFrame) -> pd.DataFrame:
    d = raw.copy()
    d["date"] = pd.to_datetime(d.YEAR.astype(str), format="%Y") + pd.to_timedelta(d.DOY - 1, unit="D")
    d = d.rename(columns=RENAME)
    d["et0_hargreaves_mm"] = hargreaves_et0(d.temp_mean_c, d.temp_max_c, d.temp_min_c, d.DOY, C.FARM["lat"]).round(2)
    d["water_balance_mm"] = (d.rain_gpm_imerg_mm - d.et0_hargreaves_mm).round(2)
    d["gdd_base10_c"] = (((d.temp_max_c.clip(upper=C.GDD_CAP_C) + d.temp_min_c.clip(lower=C.GDD_BASE_C)) / 2)
                         - C.GDD_BASE_C).clip(lower=0).round(2)
    d["heat_stress_day"] = (d.temp_max_c >= C.HEAT_STRESS_C).astype(int)
    d["frost_day"] = (d.temp_min_c <= C.FROST_C).astype(int)
    d["heavy_rain_day"] = (d.rain_gpm_imerg_mm >= C.HEAVY_RAIN_MM).astype(int)
    d["dry_day"] = (d.rain_gpm_imerg_mm < C.DRY_DAY_MM).astype(int)
    cols = ["date", "temp_mean_c", "temp_max_c", "temp_min_c", "rain_gpm_imerg_mm", "rain_merra2_mm",
            "humidity_pct", "wind_2m_m_s", "solar_mj_m2_day", "soil_wetness_top_0_1",
            "soil_wetness_root_0_1", "et0_hargreaves_mm", "water_balance_mm", "gdd_base10_c",
            "heat_stress_day", "frost_day", "heavy_rain_day", "dry_day"]
    return d[cols]


MONTHLY_AGG = {
    "temp_mean_c": "mean", "temp_max_c": "max", "temp_min_c": "min",
    "rain_gpm_imerg_mm": "sum", "rain_merra2_mm": "sum", "humidity_pct": "mean",
    "wind_2m_m_s": "mean", "solar_mj_m2_day": "mean", "soil_wetness_top_0_1": "mean",
    "soil_wetness_root_0_1": "mean", "et0_hargreaves_mm": "sum", "water_balance_mm": "sum",
    "gdd_base10_c": "sum", "heat_stress_day": "sum", "frost_day": "sum",
    "heavy_rain_day": "sum", "dry_day": "sum",
}


def build_monthly(daily: pd.DataFrame) -> pd.DataFrame:
    m = daily.set_index("date").resample("MS").agg(MONTHLY_AGG).round(2)
    m = m.rename(columns={"temp_max_c": "temp_max_of_month_c", "temp_min_c": "temp_min_of_month_c",
                          "heat_stress_day": "heat_stress_days", "frost_day": "frost_days",
                          "heavy_rain_day": "heavy_rain_days", "dry_day": "dry_days"})
    m.insert(0, "year", m.index.year)
    m.insert(1, "month", m.index.month)
    for c in ["temp_mean_c", "rain_gpm_imerg_mm", "soil_wetness_root_0_1", "water_balance_mm"]:
        m[c + "_anomaly"] = (m[c] - m.groupby("month")[c].transform("mean")).round(2)
    return m.reset_index(drop=True)


def build_yearly(daily: pd.DataFrame) -> pd.DataFrame:
    y = daily.set_index("date").resample("YS").agg({
        "temp_mean_c": "mean", "rain_gpm_imerg_mm": "sum", "et0_hargreaves_mm": "sum",
        "water_balance_mm": "sum", "heat_stress_day": "sum", "frost_day": "sum",
        "heavy_rain_day": "sum", "gdd_base10_c": "sum", "soil_wetness_root_0_1": "mean"}).round(2)
    y.insert(0, "year", y.index.year)
    return y.reset_index(drop=True)


def run() -> dict:
    daily = build_daily(read_power_csv(C.RAW["power"]))
    monthly, yearly = build_monthly(daily), build_yearly(daily)
    daily.to_csv(C.OUT["power_daily"], index=False)
    monthly.to_csv(C.OUT["power_monthly"], index=False)
    yearly.to_csv(C.OUT["power_yearly"], index=False)
    return {"days": len(daily), "missing_values": int(daily.isna().sum().sum()),
            "first": str(daily.date.min().date()), "last": str(daily.date.max().date())}
