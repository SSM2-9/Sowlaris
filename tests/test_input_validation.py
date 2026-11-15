"""Regression tests: invalid farmer inputs must be rejected (audit Q7: −5 gave a total of 1.04, NaN propagated)."""
import math

import pytest

from fieldshift.engine import recommender as R


@pytest.mark.parametrize("bad", [
    {"water": -5}, {"water": 6}, {"water": 100}, {"water": float("nan")}, {"water": math.inf},
    {"water": "3"}, {"water": None}, {"water": True}, {"wter": 3},
    {"water": 0, "market_potential": 0, "soil_health": 0, "erosion_protection": 0},
])
def test_invalid_priorities_rejected(bad):
    with pytest.raises(ValueError):
        R.recommend(bad)


def test_valid_priorities_give_scores_in_range():
    for w in [0, 1, 2.5, 5]:
        r = R.recommend({"water": w})
        for s in r["all_scores"].values():
            assert 0 <= s["total"] <= 1


@pytest.mark.parametrize("bad", [{"irrigation_available": "yes"}, {"irrigation": True}, {"limit_water_to_current": 1}])
def test_invalid_constraints_rejected(bad):
    with pytest.raises(ValueError):
        R.recommend(constraints=bad)
