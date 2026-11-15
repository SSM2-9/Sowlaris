"""
Datasets 2, 4, 5, 6 — NASA satellite products extracted with AppEEARS (point sample
at the farm, request "FieldShift_Farm_All").

    2  SMAP  SPL3SMP_E.006   enhanced L3 radiometer soil moisture, 9 km, daily (AM + PM)
    4  MODIS MOD13Q1.061     NDVI / EVI, 250 m, 16-day composites
    5a ECOSTRESS ECO_L2T_LSTE.002   land surface temperature, 70 m, ISS overpasses
    5b ECOSTRESS ECO_L3T_JET.002    daily evapotranspiration, 70 m, ISS overpasses
    6  SRTM  SRTMGL1_NC.003  elevation, 30 m (single acquisition, Feb 2000)

Quality rules are documented in docs/METHODOLOGY.md §2 and set in config.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config as C


def _round(df: pd.DataFrame, n: int) -> pd.DataFrame:
    num = df.select_dtypes("number").columns
    df[num] = df[num].round(n)
    return df


def _date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.astype(str).str[:10])


# --------------------------------------------------------------------------- 2. SMAP
def clean_smap(raw: pd.DataFrame) -> pd.DataFrame:
    """Daily soil moisture (m3/m3): mean of quality-passing AM and PM retrievals.

    The retrieval_qual_flag bit 0 ('recommended quality') is never 0 at this
    densely vegetated cropland pixel, so we keep retrievals that were attempted
    and successful (flag 0 or 1) and drop skipped/failed ones (flags 5, 7) and
    the -9999 fill value.
    """
    p = "SPL3SMP_E_006_Soil_Moisture_Retrieval_Data_"
    am, pm = raw[p + "AM_soil_moisture"], raw[p + "PM_soil_moisture_pm"]
    am_ok = raw[p + "AM_retrieval_qual_flag"].isin(C.SMAP_OK_FLAGS) & (am > 0) & (am != C.SMAP_FILL)
    pm_ok = raw[p + "PM_retrieval_qual_flag_pm"].isin(C.SMAP_OK_FLAGS) & (pm > 0) & (pm != C.SMAP_FILL)
    d = pd.DataFrame({
        "date": _date(raw.Date),
        "smap_am_m3m3": am.where(am_ok),
        "smap_pm_m3m3": pm.where(pm_ok),
    })
    d["smap_soil_moisture_m3m3"] = d[["smap_am_m3m3", "smap_pm_m3m3"]].mean(axis=1)
    d["n_retrievals"] = d[["smap_am_m3m3", "smap_pm_m3m3"]].notna().sum(axis=1)
    return _round(d.groupby("date", as_index=False).mean(numeric_only=True), 4)


# --------------------------------------------------------------------------- 4. MODIS
def clean_modis(raw: pd.DataFrame) -> pd.DataFrame:
    """16-day NDVI/EVI; composites with pixel reliability 2 (snow/ice) or 3 (cloudy) are removed."""
    p = "MOD13Q1_061__250m_16_days_"
    rel = raw[p + "pixel_reliability"].astype(int)
    ok = rel.isin(C.MODIS_OK_RELIABILITY)
    start = _date(raw.Date)
    d = pd.DataFrame({
        # a MOD13Q1 composite covers 16 days from its start date; it is assigned to its MIDPOINT (start + 8 d)
        # so that composites straddling a month boundary are not all credited to the earlier month
        "date": start + pd.Timedelta(days=8),
        "composite_start": start,
        "ndvi": raw[p + "NDVI"].where(ok),
        "evi": raw[p + "EVI"].where(ok),
        "pixel_reliability": rel,
        "quality_ok": ok,
    })
    return d.sort_values("date").reset_index(drop=True)


# --------------------------------------------------------------------------- 5a. ECOSTRESS LST
def clean_ecostress_lst(raw: pd.DataFrame) -> pd.DataFrame:
    """Clear-sky LST (°C) per overpass. The farm lies in the overlap of tiles
    14SPJ and 14SQJ, so the same overpass can appear twice: values are averaged."""
    p = "ECO_L2T_LSTE_002_"
    lst_k = pd.to_numeric(raw[p + "LST"], errors="coerce")
    qc = pd.to_numeric(raw[p + "QC"], errors="coerce").fillna(65535).astype(int)
    ok = ((raw[p + "cloud"] == 0)
          & ((qc & 3).isin(C.ECO_MANDATORY_QA_OK))
          & lst_k.between(*C.ECO_LST_VALID_K))
    d = pd.DataFrame({"datetime_utc": pd.to_datetime(raw.Date.str.replace(" UTC", "")),
                      "lst_c": (lst_k - 273.15).where(ok)})
    d = d.dropna().groupby("datetime_utc", as_index=False).lst_c.mean()
    d["local_hour"] = (d.datetime_utc.dt.hour - 6) % 24          # CST = UTC-6
    d["daytime"] = d.local_hour.between(9, 17)
    d["date"] = d.datetime_utc.dt.normalize()
    return _round(d, 2)


# --------------------------------------------------------------------------- 5b. ECOSTRESS ET
def clean_ecostress_et(raw: pd.DataFrame) -> pd.DataFrame:
    """Daily ET (mm/day) per overpass, tile duplicates averaged."""
    d = pd.DataFrame({"datetime_utc": pd.to_datetime(raw.Date.str.replace(" UTC", "")),
                      "et_daily_mm": pd.to_numeric(raw.ECO_L3T_JET_002_ETdaily, errors="coerce")})
    d = d[d.et_daily_mm.between(0, 15)]
    d = d.groupby("datetime_utc", as_index=False).et_daily_mm.mean()
    d["date"] = d.datetime_utc.dt.normalize()
    return _round(d, 3)


# --------------------------------------------------------------------------- 6. SRTM
def clean_srtm(raw: pd.DataFrame) -> pd.DataFrame:
    r = raw.iloc[0]
    return pd.DataFrame([{
        "lat": r.Latitude, "lon": r.Longitude,
        "elevation_m": float(r.SRTMGL1_NC_003_SRTMGL1_DEM),
        "srtm_tile": r.SRTM_Tile,
        "swath_count": r.get("SRTMGL1_NUMNC_003_SRTMGL1_NUM", np.nan),
        "acquired": str(r.Date)[:10],
        "note": "Point elevation only; slope is taken from SSURGO map-unit slope classes (0–1 % and 1–3 %).",
    }])


# --------------------------------------------------------------------------- monthly harmonisation
MONTHLY_COLUMNS = ["smap_soil_moisture_m3m3", "smap_soil_moisture_m3m3_n_obs", "ndvi", "ndvi_n_obs", "evi",
                   "eco_lst_day_c", "eco_lst_day_c_n_obs", "eco_et_mm_day", "eco_et_mm_day_n_obs"]


def to_monthly(smap=None, modis=None, lst=None, et=None) -> pd.DataFrame:
    """Bring all satellite series to a common monthly grid (year, month) covering the study period.
    A missing (None) or empty product gives NaN values and 0 observation counts — never invented data."""
    idx = pd.date_range(f"{C.PERIOD[0]}-01-01", f"{C.PERIOD[1]}-12-01", freq="MS", name="date")

    def monthly(df, col, how="mean", count=False, date="date", name=None):
        name = name or col
        cols = [name] + ([name + "_n_obs"] if count else [])
        if df is None or df.empty or df[col].notna().sum() == 0:
            return pd.DataFrame(index=idx, columns=cols, dtype=float)
        g = df.dropna(subset=[col]).set_index(date)[col].resample("MS")
        out = g.agg(how).rename(name).to_frame()
        if count:
            out[name + "_n_obs"] = g.count()
        return out.reindex(idx)

    parts = [
        monthly(smap, "smap_soil_moisture_m3m3", count=True),
        monthly(modis, "ndvi", count=True),
        monthly(modis, "evi"),
        monthly(None if lst is None else lst[lst.daytime], "lst_c", how="median", count=True, name="eco_lst_day_c"),
        monthly(et, "et_daily_mm", how="median", count=True, name="eco_et_mm_day"),
    ]
    m = pd.concat(parts, axis=1).reset_index()
    m.insert(0, "year", m.date.dt.year)
    m.insert(1, "month", m.date.dt.month)
    for c in [c for c in m.columns if c.endswith("_n_obs")]:
        m[c] = m[c].fillna(0).astype(int)
    for c in MONTHLY_COLUMNS:
        if c not in m.columns:
            m[c] = np.nan
    return m.drop(columns="date").round(4)


def _load(key, reader, cleaner, available):
    if key not in available:
        return None
    return cleaner(reader(C.RAW[key]))


def run(available: set | None = None) -> tuple[pd.DataFrame, dict]:
    """available: datasets that passed validation (default: all). Missing optional products are skipped."""
    available = set(C.RAW) if available is None else set(available)
    smap = _load("smap", pd.read_csv, clean_smap, available)
    modis = _load("modis", pd.read_csv, clean_modis, available)
    lst = _load("eco_lst", pd.read_csv, clean_ecostress_lst, available)
    et = _load("eco_et", pd.read_csv, clean_ecostress_et, available)
    terrain = _load("srtm", pd.read_csv, clean_srtm, available)
    if terrain is None:
        terrain = pd.DataFrame([{"lat": C.FARM["lat"], "lon": C.FARM["lon"], "elevation_m": np.nan,
                                 "note": "SRTM not available"}])
    for df, key in [(smap, "smap_daily"), (modis, "modis_16day"), (lst, "eco_lst_obs"), (et, "eco_et_obs")]:
        if df is not None:
            df.to_csv(C.OUT[key], index=False)
        elif C.OUT[key].exists():
            C.OUT[key].unlink()                       # never leave a stale product from an earlier run
    terrain.to_csv(C.OUT["terrain"], index=False)
    monthly = to_monthly(smap, modis, lst, et)
    report = {"skipped_optional": sorted({"smap", "modis", "eco_lst", "eco_et", "srtm"} - available)}
    if smap is not None:
        report.update(smap_days_with_data=int(smap.smap_soil_moisture_m3m3.notna().sum()),
                      smap_period=[str(smap.date.min().date()), str(smap.date.max().date())])
    if modis is not None:
        report.update(modis_composites_kept=int(modis.quality_ok.sum()), modis_composites_total=len(modis))
    if lst is not None:
        report.update(ecostress_lst_clear_overpasses=int(len(lst)), ecostress_lst_daytime=int(lst.daytime.sum()))
    if et is not None:
        report.update(ecostress_et_overpasses=int(len(et)))
    report["elevation_m"] = None if pd.isna(terrain.elevation_m.iloc[0]) else float(terrain.elevation_m.iloc[0])
    return monthly, report
