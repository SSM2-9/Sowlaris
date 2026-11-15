"""Physical consistency and plausibility of the NASA daily water balance (audit items 7–9)."""
import numpy as np
import pandas as pd
import pytest

from fieldshift.engine import recommender as R
from fieldshift.models import water_balance as W

T = R.load_data()["traits"]
ROT = R.CANDIDATES["current_corn_soy"]
P0 = W.daily_climate().rain_gpm_imerg_mm.to_numpy()
E0 = W.daily_climate().et0_hargreaves_mm.to_numpy()


@pytest.mark.parametrize("key", list(R.CANDIDATES))
def test_water_is_conserved_and_storage_bounded(key):
    sim = W.simulate(R.CANDIDATES[key], T)
    assert abs(W.water_conservation_error(sim)) < 1e-6           # Σrain = ΣETa + Σdrainage + ΔS
    cap = W.taw_mm(W.PROFILE_DEPTH_M)
    assert sim.storage.between(-1e-9, cap + 1e-9).all()
    assert (sim.eta <= np.maximum(sim.etc, W.K_BARE * sim.et0) + 1e-9).all()   # ETa ≤ max(crop demand, bare evaporation)
    assert (sim.eta >= 0).all() and (sim.drainage >= 0).all()


def test_no_rain_dries_the_soil_and_stresses_crops():
    sim = W.simulate(ROT, T, rain=np.zeros_like(P0))
    assert sim.storage.iloc[-1] < 1.0
    assert sim.drainage.sum() == 0
    m = W.rotation_metrics(ROT, T, rain=np.zeros_like(P0))
    assert m["unmet_fraction_cash"] > 0.9


def test_saturating_rain_removes_stress():
    m = W.rotation_metrics(ROT, T, rain=np.full_like(P0, 30.0))
    assert m["unmet_fraction_cash"] < 0.01
    assert m["rel_yield_mean"] > 0.99


@pytest.mark.parametrize("key", list(R.CANDIDATES))
def test_less_rain_more_shortfall_more_heat_more_shortfall(key):
    rot = R.CANDIDATES[key]
    f = [W.rotation_metrics(rot, T, rain=P0 * k)["unmet_mm_cash_per_year"] for k in (1.25, 1.0, 0.75, 0.5)]
    assert all(b > a for a, b in zip(f, f[1:]))
    hot = W.rotation_metrics(rot, T, et0=E0 * 1.1)["unmet_mm_cash_per_year"]
    assert hot > f[1]


def test_more_storage_less_stress():
    u = [W.rotation_metrics(ROT, T, storage_scale=s)["unmet_fraction_cash"] for s in (0.5, 1.0, 1.5)]
    assert u[0] > u[1] > u[2]


def test_relative_yield_bounded_and_uses_fao33_ky():
    assert W.relative_yield("corn", 1.0) == 1.0
    assert W.relative_yield("corn", 0.6) == pytest.approx(1 - 1.25 * 0.4)
    assert W.relative_yield("corn", 0.0) == 0.0
    assert W.relative_yield("cereal_rye_cover", 0.5) is None      # no Ky for cover crops: not invented


def test_claypan_rooting_limit_inferred_from_ssurgo():
    lim = W.soil_profile(True).attrs["rooting_limit_cm"]
    assert lim[7680] == 28 and lim[7682] == 15                  # Wymore claypan tops (11 in, 6 in)
    assert lim[4018] == 200 and lim[7213] == 200
    assert W.taw_mm(1.7) < W.taw_mm(1.7, effective_rooting=False)


def test_winter_wheat_sown_the_autumn_before_harvest():
    g = W.timeline(R.CANDIDATES["sorghum_soy_wheat_dc"], T)
    assert g[1][10] == "winter_wheat" and g[2][0] == "winter_wheat"   # sown after soybean, harvested next June
    assert g[2][9] == "dc_soybean" and g[2][11] is None


def test_hargreaves_et0_close_to_penman_monteith():
    """Independent check of the ET0 method (FAO-56 Penman–Monteith from POWER radiation, humidity, wind)."""
    from fieldshift.models.water_balance import daily_climate
    import fieldshift.config as C
    d = pd.read_csv(C.OUT["power_daily"], parse_dates=["date"])
    from scripts.validate_water_balance import penman_monteith
    pm = penman_monteith(d)
    gs = d.date.dt.month.isin([5, 6, 7, 8, 9])
    ratio = d.et0_hargreaves_mm[gs].sum() / pm[gs].sum()
    assert 0.85 < ratio < 1.15


@pytest.mark.parametrize("name", [k for k, v in W.RUNOFF_SCENARIOS.items() if v])
def test_experimental_runoff_conserves_water(name):
    sim = W.simulate(ROT, T, runoff=W.RUNOFF_SCENARIOS[name])
    assert abs(W.water_conservation_error(sim)) < 1e-6      # rain = runoff + ETa + drainage + ΔS
    assert (sim.runoff >= 0).all() and (sim.runoff <= sim.rain + 1e-9).all()
    assert sim.runoff.sum() > 0


def test_scs_runoff_matches_curve_number_equation():
    # CN 85: S = 44.82 mm, Ia = 8.96 mm; P = 50 mm → Q = (41.04)² / (41.04 + 44.82) = 19.62 mm
    assert W.scs_runoff(50, 85) == pytest.approx(19.62, abs=0.01)
    assert W.scs_runoff(5, 85) == 0.0


def test_production_scoring_has_no_runoff():
    sim = W.simulate(ROT, T)
    assert sim.runoff.sum() == 0
    d = R.load_data()
    assert R.recommend(d=d)["all_scores"] == R.recommend(d={**d, "water": R.water_metrics(d, runoff=None)})["all_scores"]
