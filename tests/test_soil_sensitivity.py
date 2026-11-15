"""Soil sensitivity (audit Q2: sandy and clay soils gave identical scores). Each soil changes only the
scores it should, through a traceable route: storage → water & drought risk; drainage → wet-soil part of
climate fit and feasibility; erodibility → erosion; organic matter → soil health; pH → feasibility."""
import numpy as np
import pandas as pd
import pytest

from fieldshift import config as C
from fieldshift.engine import recommender as R
from fieldshift.models import water_balance as W

BASE = R.load_data()


def horizons(sand, clay, awc, ksat, kw, wind, om=3.0, ph=6.5):
    rows = []
    for top, bot in [(0, 8), (8, 30), (30, 79)]:
        rows.append(dict(map_unit=1, soil_name="synthetic", pct_of_field=100, top_in=top, bottom_in=bot, sand_pct=sand,
                         silt_pct=100 - sand - clay, clay_pct=clay, awc_in_in_low=awc, awc_in_in_high=awc,
                         ksat_um_s_low=ksat, ksat_um_s_high=ksat * 3, kw=kw, wind_erod_index=wind,
                         organic_matter_pct_low=om, organic_matter_pct_high=om, ph_low=ph, ph_high=ph))
    return pd.DataFrame(rows)


SOILS = {
    "sandy_fast_draining": horizons(85, 5, 0.06, 40, 0.15, 220, om=0.8),
    "clay_poorly_draining": horizons(10, 50, 0.14, 0.05, 0.28, 48, om=4.5),
    "moderate_loam": horizons(40, 20, 0.17, 5, 0.32, 86),
}


def run_with(h, om=3.0, ph=6.5):
    d = dict(BASE)
    field = pd.Series({"topsoil_organic_matter_pct": om, "topsoil_ph": ph, "max_clay_pct": h.clay_pct.max(),
                       "min_ksat_um_s": h.ksat_um_s_low.min(), "plant_available_water_in_0_79in": 10,
                       "topsoil_erodibility_kw": h.kw.iloc[0], "map_unit": "FIELD_AVG"})
    soil = pd.concat([d["soil"][d["soil"].map_unit != "FIELD_AVG"].iloc[:0], field.to_frame().T])
    d["soil"], d["horizons"] = soil, h
    d["soil_factors"] = R.soil_factors(h, field)
    d["water"] = R.water_metrics(d, profile=W.profile_from_horizons(h))
    return R.recommend(d=d)


@pytest.fixture(scope="module")
def results():
    out = {k: run_with(h, om=float(h.organic_matter_pct_low.iloc[0])) for k, h in SOILS.items()}
    out["field"] = R.recommend()
    return out


def test_scores_differ_between_sandy_and_clay(results):
    a, b = results["sandy_fast_draining"]["all_scores"], results["clay_poorly_draining"]["all_scores"]
    assert any(a[k]["total"] != b[k]["total"] for k in R.CANDIDATES)


def test_low_storage_sand_has_more_water_stress(results):
    s, c = results["sandy_fast_draining"]["all_scores"], results["clay_poorly_draining"]["all_scores"]
    for k in R.CANDIDATES:
        assert s[k]["_unmet_water_mm"] > c[k]["_unmet_water_mm"]
        assert s[k]["water"] < c[k]["water"]


def test_wet_soil_tolerance_only_matters_on_slow_drainage(results):
    sand = results["sandy_fast_draining"]["soil_factors"]
    clay = results["clay_poorly_draining"]["soil_factors"]
    assert sand["drainage_relevance"] == 0 and clay["drainage_relevance"] == 1


def test_low_organic_matter_raises_soil_health_relevance(results):
    assert results["sandy_fast_draining"]["soil_factors"]["soil_health_relevance"] > \
        results["clay_poorly_draining"]["soil_factors"]["soil_health_relevance"]


def test_acidic_soil_flags_alfalfa_conditional_not_excluded():
    r = run_with(SOILS["moderate_loam"], ph=5.2)
    f = r["feasibility"]["alfalfa_corn_soy"]
    assert f["status"] == "conditional"
    assert "lime before seeding" in str(f["issues"])


def test_free_draining_soil_clears_alfalfa_drainage_warning(results):
    issues = results["sandy_fast_draining"]["feasibility"]["alfalfa_corn_soy"]["issues"]
    assert not any(i["check"] == "drainage" for i in issues)


def test_missing_soil_measurements_are_reported_not_invented():
    h = SOILS["moderate_loam"].copy()
    h["kw"] = np.nan
    r = run_with(h, om=np.nan, ph=np.nan)
    assert r["soil_factors"]["organic_matter_pct"] is None and r["soil_factors"]["kw"] is None
    assert any("pH not available" in i["message"] for i in r["feasibility"]["alfalfa_corn_soy"]["issues"])
    assert all(np.isfinite(s["scores"]["total"]) for s in r["strategies"])
