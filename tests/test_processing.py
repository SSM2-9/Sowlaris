"""Cleaning and quality-control rules for every dataset."""
import numpy as np
import pandas as pd
import pytest

from fieldshift import config as C
from fieldshift.processing import power, satellite


# ------------------------------------------------------------- NASA POWER / FAO-56
def test_extraterrestrial_radiation_matches_fao56_example():
    # FAO-56 Example 8: 20°S, 3 September (DOY 246) → Ra = 32.2 MJ m-2 day-1
    assert power.extraterrestrial_radiation(246, -20.0) == pytest.approx(32.2, abs=0.1)


def test_hargreaves_et0_is_physical():
    et0 = power.hargreaves_et0(np.array([25.0]), np.array([32.0]), np.array([18.0]), np.array([200]), 39.12)
    assert 4.0 < et0[0] < 8.0                 # typical Kansas July value, mm/day
    zero_range = power.hargreaves_et0(np.array([10.0]), np.array([10.0]), np.array([10.0]), np.array([200]), 39.12)
    assert zero_range[0] == 0                 # no temperature range → no Hargreaves demand


def test_power_daily_complete():
    d = pd.read_csv(C.OUT["power_daily"])
    assert len(d) == 7670                     # every day 2005-01-01 … 2025-12-31
    assert d.isna().sum().sum() == 0
    assert (d.temp_max_c >= d.temp_min_c).all()
    assert (d.rain_gpm_imerg_mm >= 0).all()


# ------------------------------------------------------------- satellites
def test_smap_quality_filter():
    raw = pd.read_csv(C.RAW["smap"])
    s = satellite.clean_smap(raw)
    v = s.smap_soil_moisture_m3m3.dropna()
    assert v.between(0.02, 0.6).all()         # no -9999 fill or impossible values
    assert s.date.is_unique
    p = "SPL3SMP_E_006_Soil_Moisture_Retrieval_Data_"
    bad = raw[~raw[p + "AM_retrieval_qual_flag"].isin(C.SMAP_OK_FLAGS) & ~raw[p + "PM_retrieval_qual_flag_pm"].isin(C.SMAP_OK_FLAGS)]
    bad_dates = set(pd.to_datetime(bad.Date.astype(str).str[:10]))
    assert s[s.date.isin(bad_dates)].smap_soil_moisture_m3m3.isna().all()


def test_modis_quality_filter():
    m = satellite.clean_modis(pd.read_csv(C.RAW["modis"]))
    assert m.loc[~m.quality_ok, "ndvi"].isna().all()
    assert m.ndvi.dropna().between(-0.2, 1.0).all()


def test_ecostress_filters():
    lst = satellite.clean_ecostress_lst(pd.read_csv(C.RAW["eco_lst"]))
    lo, hi = (k - 273.15 for k in C.ECO_LST_VALID_K)
    assert lst.lst_c.between(lo, hi).all()
    assert lst.datetime_utc.is_unique           # tile duplicates averaged
    et = satellite.clean_ecostress_et(pd.read_csv(C.RAW["eco_et"]))
    assert et.et_daily_mm.between(0, 15).all()


# ------------------------------------------------------------- harmonised table
def test_master_table(master):
    assert len(master) == 21 * 12
    assert master[["year", "month"]].duplicated().sum() == 0
    for col in ["rain_gpm_imerg_mm", "et0_hargreaves_mm", "smap_soil_moisture_m3m3", "ndvi",
                "eco_et_mm_day", "crop_grown", "elevation_m", "county_corn_yield"]:
        assert col in master.columns, col
    assert master.smap_soil_moisture_m3m3.notna().sum() > 100
    assert master[master.year < 2015].smap_soil_moisture_m3m3.isna().all()   # SMAP launched 2015


def test_hargreaves_never_negative_in_extreme_cold():
    et0 = power.hargreaves_et0(np.array([-25.0]), np.array([-18.0]), np.array([-32.0]), np.array([15]), 39.12)
    assert et0[0] == 0


def test_footprint_table_covers_every_dataset():
    names = " ".join(f[0] for f in C.FOOTPRINTS)
    for key in ["POWER", "IMERG", "SMAP", "MODIS", "ECOSTRESS", "SRTM", "CropScape", "SSURGO", "GAEZ", "NASS"]:
        assert key in names
    assert all(len(f) == 5 and all(f) for f in C.FOOTPRINTS)


def test_modis_assigned_to_composite_midpoint():
    m = satellite.clean_modis(pd.read_csv(C.RAW["modis"]))
    assert ((m.date - m.composite_start).dt.days == 8).all()
