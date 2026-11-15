"""Drought counterfactuals (audit Q4). Rain is changed in the DAILY NASA GPM IMERG series that drives the
water balance; everything else is held constant.

Retired test (see docs/AUDIT_LOG.md, "Retired test"): "a drier climate must never favour a rotation with higher
ANNUAL water demand". Scientifically invalid — a rotation whose extra demand falls in autumn–winter can cope
better with a SUMMER drought than one with lower annual demand concentrated in summer.

The tests below are precise invariants of the current water-balance model, plus one targeted regression case.
Overall scores and rankings are NOT required to fall: a rotation may rise because competitors suffer more.
"""
import numpy as np
import pytest

from fieldshift.engine import recommender as R
from fieldshift.models import water_balance as W

RAIN_FACTORS = [0.8, 0.5, 0.3]
D = dict(R.load_data())
FARM = R.diagnose_farm(D)
P0 = W.daily_climate().rain_gpm_imerg_mm.to_numpy()
_CACHE = {}


def _water(factor):
    if factor not in _CACHE:
        _CACHE[factor] = R.water_metrics(D, rain=P0 * factor)
    return _CACHE[factor]


@pytest.mark.parametrize("factor", RAIN_FACTORS)
@pytest.mark.parametrize("key", list(R.CANDIDATES))
def test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation(key, factor):
    """For an otherwise identical rotation, less rain must not increase the share of crop demand met,
    must not reduce the shortfall (mm), and must not raise drought-year relative yield."""
    base, dry = _water(1.0)[key], _water(factor)[key]
    assert dry["unmet_mm_cash_per_year"] >= base["unmet_mm_cash_per_year"]
    assert dry["unmet_fraction_cash"] >= base["unmet_fraction_cash"]
    assert dry["rel_yield_p25"] <= base["rel_yield_p25"] + 1e-12


@pytest.mark.parametrize("factor", [1.0] + RAIN_FACTORS)
@pytest.mark.parametrize("with_cover,without", [("corn_soy_covers", "current_corn_soy"), ("corn_soy_rye", "current_corn_soy")])
def test_adding_a_cover_crop_never_reduces_the_modelled_deficit(with_cover, without, factor):
    """Narrow model invariant: same cash crops, same climate, an added cover crop with positive water demand,
    unmodelled soil benefits (infiltration, structure, residue mulch) excluded → shortfall must not fall."""
    w = _water(factor)
    assert w[with_cover]["unmet_mm_cash_per_year"] >= w[without]["unmet_mm_cash_per_year"] - 1e-6


def test_regression_alfalfa_does_not_rise_when_rain_is_halved():
    """Targeted regression for the case that exposed the saturation bug: with the provisional proxy, halving
    rain lifted alfalfa (highest water demand) to #2 under default priorities. Not a universal rule."""
    rank = lambda r: r["ranking"].index("alfalfa_corn_soy")
    base = R.recommend(d=D)
    d2 = dict(D)
    d2["water"] = _water(0.5)
    assert rank(R.recommend(d=d2)) >= rank(base)
    # and its water component falls by more than that of the lowest-demand rotation
    s0 = {k: R.score_rotation(r, D, FARM, water=_water(1.0)[k], soil=D["soil_factors"]) for k, r in R.CANDIDATES.items()}
    s1 = {k: R.score_rotation(r, D, FARM, water=_water(0.5)[k], soil=D["soil_factors"]) for k, r in R.CANDIDATES.items()}
    low = min(s0, key=lambda k: s0[k]["_water_need_mm"])
    assert s0["alfalfa_corn_soy"]["water"] - s1["alfalfa_corn_soy"]["water"] > s0[low]["water"] - s1[low]["water"]


@pytest.mark.parametrize("factor", RAIN_FACTORS)
def test_no_saturation_rotations_with_different_crops_stay_distinct(factor):
    s = {k: R.score_rotation(r, D, FARM, water=_water(factor)[k], soil=D["soil_factors"]) for k, r in R.CANDIDATES.items()}
    distinct_cash = ["current_corn_soy", "sorghum_soy_vetch", "sorghum_soy_wheat_dc", "corn_soy_wheat_vetch", "alfalfa_corn_soy"]
    vals = [s[k]["water"] for k in distinct_cash]
    assert len(set(vals)) == len(vals) and min(vals) > 0


def test_water_score_order_changes_are_explained_by_modelled_shortfall():
    """If two rotations swap order on the water score between climates, the one that fell behind must be the one
    whose modelled shortfall grew more (drought tolerance is unchanged between climates)."""
    s0 = {k: R.score_rotation(r, D, FARM, water=_water(1.0)[k], soil=D["soil_factors"]) for k, r in R.CANDIDATES.items()}
    s1 = {k: R.score_rotation(r, D, FARM, water=_water(0.5)[k], soil=D["soil_factors"]) for k, r in R.CANDIDATES.items()}
    keys = list(R.CANDIDATES)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            before, after = s0[a]["water"] - s0[b]["water"], s1[a]["water"] - s1[b]["water"]
            if before * after < 0:
                grow = {k: s1[k]["_unmet_water_mm"] - s0[k]["_unmet_water_mm"] for k in (a, b)}
                loser = a if after < before else b
                other = b if loser == a else a
                assert grow[loser] > grow[other]


def test_engine_states_water_model_limitation():
    r = R.recommend()
    assert any("EXPLORATORY CALIBRATED MODEL" in x for x in r["known_limitations"])
