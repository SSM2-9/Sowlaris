"""Recommendation engine: output contract and behaviour."""
from fieldshift.engine import recommender as R

REQUIRED = {"id", "name", "rotation", "rank", "scores", "bare_months_per_year", "why", "evidence",
            "benefits", "information_gaps", "risks_for_local_review"}


def test_three_strategies_with_all_fields():
    r = R.recommend()
    assert len(r["strategies"]) == 3
    assert r["strategies"][0]["id"] == "current_corn_soy"          # current rotation always shown
    assert len({s["id"] for s in r["strategies"]}) == 3
    for s in r["strategies"]:
        assert REQUIRED <= set(s)
        assert all(0 <= v <= 1 for v in s["scores"].values())
        assert s["evidence"] and s["information_gaps"] and s["risks_for_local_review"]


def test_priorities_change_the_ranking():
    water = R.recommend({"water": 5, "market_potential": 0, "soil_health": 0, "erosion_protection": 0})
    soil = R.recommend({"water": 0, "market_potential": 0, "soil_health": 5, "erosion_protection": 5})
    assert water["ranking"] != soil["ranking"]


def test_covers_reduce_bare_soil():
    s = R.recommend()["all_scores"]
    assert s["corn_soy_covers"]["_bare_months"] < s["current_corn_soy"]["_bare_months"]
    assert s["corn_soy_covers"]["erosion_protection"] > s["current_corn_soy"]["erosion_protection"]


def test_forage_outlet_raises_alfalfa_market_potential():
    a = R.recommend(constraints={"forage_market_or_livestock": False})["all_scores"]["alfalfa_corn_soy"]["market_potential"]
    b = R.recommend(constraints={"forage_market_or_livestock": True})["all_scores"]["alfalfa_corn_soy"]["market_potential"]
    assert b > a


def test_deprecated_income_key_still_accepted():
    r = R.recommend({"income": 5})
    assert r["priorities"]["market_potential"] == 5


def test_month_list_wraps_year():
    assert R.month_list("5-9") == [5, 6, 7, 8, 9]
    assert R.month_list("10-6") == [10, 11, 12, 1, 2, 3, 4, 5, 6]


def test_near_tie_flagged_for_default_pair():
    r = R.recommend()
    a, b = r["strategies"][1], r["strategies"][2]
    if abs(a["scores"]["total"] - b["scores"]["total"]) < R.NEAR_TIE:
        assert a["near_tie"] and b["near_tie"] and any("Near-tie" in n for n in r["notices"])
    for s in r["strategies"][1:]:
        assert s["weakest"] in R.SCORE_KEYS and s["strongest"] in R.SCORE_KEYS
        assert "total" in s["change_vs_current"]
