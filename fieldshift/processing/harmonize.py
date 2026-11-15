"""
Builds the MASTER monthly table: one row per month (2005-01 … 2025-12) joining
NASA POWER/IMERG climate, the satellite series (SMAP, MODIS, ECOSTRESS), the
crop grown that year (CropScape), static soil (SSURGO), terrain (SRTM) and
county yields (NASS).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config as C


def build_master(power_monthly: pd.DataFrame, sat_monthly: pd.DataFrame) -> pd.DataFrame:
    m = power_monthly.merge(sat_monthly, on=["year", "month"], how="left")
    m = m[(m.year >= C.PERIOD[0]) & (m.year <= C.PERIOD[1])].copy()

    cdl = pd.read_csv(C.OUT["cdl"])[["year", "crop"]].rename(columns={"crop": "crop_grown"})
    m = m.merge(cdl, on="year", how="left")

    soil = pd.read_csv(C.OUT["soil_summary"])
    fa = soil[soil.map_unit == "FIELD_AVG"].iloc[0]
    for c in ["topsoil_organic_matter_pct", "topsoil_ph", "plant_available_water_in_0_79in",
              "max_clay_pct", "topsoil_erodibility_kw"]:
        m["soil_" + c] = fa[c]
    m["elevation_m"] = pd.to_numeric(pd.read_csv(C.OUT["terrain"]).elevation_m, errors="coerce").iloc[0]

    nass = pd.read_csv(C.OUT["nass_wide"])
    keep = ["year"] + [c for c in nass.columns if c.endswith("_yield")]
    m = m.merge(nass[keep].add_prefix("county_").rename(columns={"county_year": "year"}), on="year", how="left")

    # crop water stress index from ECOSTRESS: actual ET / reference ET0 (0 = stressed / bare, ~1 = unstressed)
    days = pd.to_datetime(dict(year=m.year, month=m.month, day=1)).dt.days_in_month
    m["et0_mm_day"] = (m.et0_hargreaves_mm / days).round(3)
    # ECOSTRESS ET ÷ ET0 of the SAME DAY (matched dates), monthly median; the monthly-mean ratio is kept for comparison
    m["eco_et_to_et0_ratio_monthly_means"] = (m.eco_et_mm_day / m["et0_mm_day"]).round(3)
    m["eco_et_to_et0_ratio"] = np.nan
    if C.OUT["eco_et_obs"].exists():
        eco = pd.read_csv(C.OUT["eco_et_obs"], parse_dates=["date"])
        day = pd.read_csv(C.OUT["power_daily"], parse_dates=["date"])[["date", "et0_hargreaves_mm"]]
        e = eco.merge(day, on="date")
        e = e[e.et0_hargreaves_mm > 0.5]                       # avoid dividing by near-zero winter ET0
        e["ratio"] = e.et_daily_mm / e.et0_hargreaves_mm
        r = e.groupby([e.date.dt.year.rename("year"), e.date.dt.month.rename("month")]).ratio.median().round(3)
        m = m.drop(columns="eco_et_to_et0_ratio").merge(r.rename("eco_et_to_et0_ratio").reset_index(),
                                                         on=["year", "month"], how="left")
    m.insert(2, "lat", C.FARM["lat"])
    m.insert(3, "lon", C.FARM["lon"])
    return m.reset_index(drop=True)
