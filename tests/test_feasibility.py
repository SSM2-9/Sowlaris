"""Regression tests for feasibility (audit Q5: alfalfa shown in 96/256 priority settings despite pH and
drainage concerns; hairy vetch after soybean shown in 242/256 despite the establishment-window conflict)."""
import itertools

import pytest

from fieldshift.engine import feasibility as F
from fieldshift.engine import recommender as R

K = ["water", "income", "soil_health", "erosion_protection"]
GRID = [dict(zip(K, x)) for x in itertools.product([0, 1, 3, 5], repeat=4) if sum(x) > 0]
FARM_SOIL = {"ph": 6.13, "min_ksat_um_s": 0.14, "max_clay_pct": 45.2}


def _eval(key, soil=FARM_SOIL, **cons):
    d = R.load_data()
    return F.evaluate(key, R.CANDIDATES[key], d["traits"], soil, {**R.DEFAULT_CONSTRAINTS, **cons}, 600, 610)


def test_vetch_after_soybean_needs_interseeding():
    assert _eval("corn_soy_covers")["status"] == F.INFEASIBLE
    assert _eval("corn_soy_covers", can_establish_cover_before_harvest=True)["status"] == F.CONDITIONAL


def test_vetch_after_wheat_and_rye_after_corn_are_fine():
    st = _eval("corn_soy_wheat_vetch")
    assert st["status"] == F.FEASIBLE
    assert not [i for i in st["issues"] if i["severity"] == F.INFEASIBLE]


def test_low_ph_is_conditional_not_excluded():
    for ph in [6.13, 5.5]:
        e = _eval("alfalfa_corn_soy", soil={**FARM_SOIL, "ph": ph}, forage_market_or_livestock=True)
        assert e["status"] == F.CONDITIONAL
        assert any(i["check"] == "soil_ph" for i in e["issues"])
    assert "lime before seeding" in str(_eval("alfalfa_corn_soy", soil={**FARM_SOIL, "ph": 5.5})["issues"])


def test_good_soil_clears_alfalfa_soil_checks():
    e = _eval("alfalfa_corn_soy", soil={"ph": 6.8, "min_ksat_um_s": 5.0, "max_clay_pct": 25}, forage_market_or_livestock=True)
    assert e["status"] == F.FEASIBLE


def test_alfalfa_without_forage_outlet_is_flagged():
    assert any(i["check"] == "forage_outlet" for i in _eval("alfalfa_corn_soy")["issues"])


def test_infeasible_rotation_never_shown_as_alternative():
    for cons in [{}, {"can_establish_cover_before_harvest": True}, {"limit_water_to_current": True}]:
        for p in GRID:
            r = R.recommend(p, constraints=cons)
            for s in r["strategies"][1:]:
                assert s["feasibility"]["status"] != F.INFEASIBLE


def test_current_rotation_always_shown_first():
    r = R.recommend(constraints={"limit_water_to_current": True})
    assert r["strategies"][0]["id"] == "current_corn_soy"


def test_water_limit_excludes_thirstier_rotations():
    r = R.recommend(constraints={"limit_water_to_current": True})
    cur = r["all_scores"]["current_corn_soy"]["_water_need_mm"]
    for s in r["strategies"][1:]:
        assert s["water_need_mm_per_year"] <= cur
    assert any("water limit" in n for n in r["notices"])


def test_fewer_than_two_alternatives_gives_notice():
    r = R.recommend(constraints={"limit_water_to_current": True})
    alts = len(r["strategies"]) - 1
    if alts < 2:
        assert any("passed the feasibility checks" in n for n in r["notices"])
