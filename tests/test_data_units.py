"""Regression tests: wrong units / locations / impossible values must stop the pipeline
(audit Q7: rain divided by 25.4 → 36 mm/yr passed all 18 original tests)."""
import shutil

import pandas as pd
import pytest

from fieldshift import config as C
from fieldshift.validation import DataValidationError, validate_raw


@pytest.fixture
def raw_copy(tmp_path):
    paths = {}
    for k, p in C.RAW.items():
        dst = tmp_path / p.name
        shutil.copy(p, dst)
        paths[k] = dst
    return paths


def _edit_power(path, fn):
    lines = path.read_text().splitlines()
    i = next(i for i, l in enumerate(lines) if l.startswith("YEAR"))
    df = pd.read_csv(path, skiprows=i)
    df = fn(df)
    path.write_text("\n".join(lines[:i]) + "\n" + df.to_csv(index=False))


def test_real_data_passes():
    rep = validate_raw()
    assert all(r["status"] == "ok" for r in rep.values())


def test_rain_in_inches_is_rejected(raw_copy):
    _edit_power(raw_copy["power"], lambda d: d.assign(IMERG_PRECTOT=d.IMERG_PRECTOT / 25.4))
    with pytest.raises(DataValidationError, match="IMERG"):
        validate_raw(raw_copy)


def test_both_rain_products_in_inches_rejected(raw_copy):
    _edit_power(raw_copy["power"], lambda d: d.assign(IMERG_PRECTOT=d.IMERG_PRECTOT / 25.4,
                                                      PRECTOTCORR=d.PRECTOTCORR / 25.4))
    with pytest.raises(DataValidationError, match="annual IMERG rain plausible"):
        validate_raw(raw_copy)


def test_temperature_in_fahrenheit_rejected(raw_copy):
    _edit_power(raw_copy["power"], lambda d: d.assign(T2M_MAX=d.T2M_MAX * 9 / 5 + 32))
    with pytest.raises(DataValidationError, match="T2M_MAX"):
        validate_raw(raw_copy)


def test_wrong_declared_unit_rejected(raw_copy):
    p = raw_copy["power"]
    p.write_text(p.read_text().replace("Precipitation Corrected (mm/day)", "Precipitation Corrected (in/day)"))
    with pytest.raises(DataValidationError, match="unit of PRECTOTCORR"):
        validate_raw(raw_copy)


def test_power_for_another_location_rejected(raw_copy):
    p = raw_copy["power"]
    p.write_text(p.read_text().replace("latitude  39.12   longitude -96.63", "latitude  23.50   longitude -102.10"))
    with pytest.raises(DataValidationError, match="location"):
        validate_raw(raw_copy)


def test_unscaled_ndvi_rejected(raw_copy):
    df = pd.read_csv(raw_copy["modis"])
    df["MOD13Q1_061__250m_16_days_NDVI"] *= 10000
    df.to_csv(raw_copy["modis"], index=False)
    with pytest.raises(DataValidationError, match="NDVI"):
        validate_raw(raw_copy)


def test_lst_in_celsius_rejected(raw_copy):
    df = pd.read_csv(raw_copy["eco_lst"])
    df["ECO_L2T_LSTE_002_LST"] = pd.to_numeric(df["ECO_L2T_LSTE_002_LST"], errors="coerce") - 273.15
    df.to_csv(raw_copy["eco_lst"], index=False)
    with pytest.raises(DataValidationError, match="kelvin"):
        validate_raw(raw_copy)


def test_yield_in_tonnes_per_hectare_rejected(raw_copy):
    df = pd.read_csv(raw_copy["nass"], dtype=str)
    m = df["Data Item"] == "CORN, GRAIN - YIELD, MEASURED IN BU / ACRE"
    df.loc[m, "Value"] = (pd.to_numeric(df.loc[m, "Value"].str.replace(",", "")) * 0.0628).round(2).astype(str)
    df.to_csv(raw_copy["nass"], index=False)
    with pytest.raises(DataValidationError, match="CORN, GRAIN yield"):
        validate_raw(raw_copy)


def test_soil_texture_not_summing_to_100_rejected(raw_copy):
    df = pd.read_csv(raw_copy["ssurgo"])
    df.loc[0, "clay_pct"] = 80
    df.to_csv(raw_copy["ssurgo"], index=False)
    with pytest.raises(DataValidationError, match="sand \\+ silt \\+ clay"):
        validate_raw(raw_copy)


def test_pipeline_stops_before_processing_on_bad_units(raw_copy, monkeypatch):
    _edit_power(raw_copy["power"], lambda d: d.assign(IMERG_PRECTOT=d.IMERG_PRECTOT / 25.4))
    monkeypatch.setattr(C, "RAW", raw_copy)
    from scripts import run_pipeline
    with pytest.raises(DataValidationError):
        run_pipeline.validate_inputs()
