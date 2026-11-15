"""Sowlaris interface <-> Field Shift engine. Pure Python: runs without Streamlit.
Guards three promises: the UI shows exactly what the engine computes; no random/fake data; no emojis."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from core import data, engine  # noqa: E402
from fieldshift.engine import recommender as R  # noqa: E402

EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\uFE0F]")


def test_default_result_is_identical_to_the_engine():
    ours, theirs = engine.recommend(3, 3, 3, 3), R.recommend()
    assert ours["ranking"] == theirs["ranking"]
    assert [s["scores"]["total"] for s in ours["strategies"]] == [s["scores"]["total"] for s in theirs["strategies"]]


def test_sliders_and_checkboxes_reach_the_engine():
    r = engine.recommend(5, 0, 1, 2, True, True, True, True)
    assert r["priorities"] == {"water": 5, "market_potential": 0, "soil_health": 1, "erosion_protection": 2}
    assert r["constraints"] == {"irrigation_available": True, "limit_water_to_current": True,
                                "can_establish_cover_before_harvest": True, "forage_market_or_livestock": True}


def test_every_engine_score_has_a_label():
    assert set(engine.SCORE_LABELS) <= set(engine.recommend(3, 3, 3, 3)["strategies"][0]["scores"])


def test_alert_numbers_come_from_the_pipeline():
    farm = engine.recommend(3, 3, 3, 3)["farm"]
    text = " ".join(t for _, _, t in data.trend_alerts(farm))
    assert f"{-farm['gs_water_balance_mm']:.0f} mm" in text and f"{100 * farm['eco_et_to_et0_jul_aug']:.0f}%" in text
    assert farm["trend_temperature"] in text            # keeps Ekram's 'not statistically significant' wording


def test_distance_from_the_demonstration_farm():
    assert data.km_from_farm(data.FARM["lat"], data.FARM["lon"]) < 0.01
    assert data.km_from_farm(42.03, -93.62) > 400       # Ames, Iowa is outside the data's coverage


def test_soil_moisture_series_is_real_smap():
    s = data.moisture_series(engine.data()["master"])
    assert len(s) >= 8 and s.iloc[:, 0].between(0.05, 0.5).all()


def test_sowlaris_code_has_no_emojis_and_no_random_data():
    for p in (ROOT / "app").rglob("*.py"):
        src = p.read_text()
        assert not EMOJI.search(src), f"emoji in {p}"
        if p.parts[-2:] in {("core", "data.py"), ("core", "engine.py"), ("views", "dashboard.py"), ("views", "charts.py")}:
            assert not re.search(r"np\.random|numpy\.random|default_rng|import random|dummy", src), f"random/dummy data in {p}"


# ---- behaviours Ekram's old interface tests checked, now asserted through the bridge the new interface uses ----
def test_interseeding_makes_vetch_rotations_conditional():
    r = engine.recommend(3, 3, 3, 3, False, False, True, False)
    assert "conditional" in {f["status"] for f in r["feasibility"].values()}


def test_water_limit_can_leave_no_alternative_without_crashing():
    r = engine.recommend(3, 3, 3, 3, False, True, False, False)
    assert r["strategies"][0]["id"] == "current_corn_soy"      # current rotation is always shown


def test_market_first_triggers_the_sensitivity_warning():
    r = engine.recommend(1, 5, 1, 1)
    note = engine.sensitivity_note(r["priorities"])
    assert note and note[1] < 0.6


def test_default_near_tie_is_reported():
    r = engine.recommend(3, 3, 3, 3)
    assert r["strategies"][1]["near_tie"] == R.recommend()["strategies"][1]["near_tie"]
    assert any(n.startswith("Near-tie") for n in r["notices"]) == r["strategies"][1]["near_tie"]


def test_no_income_label_in_the_interface():
    src = (ROOT / "app" / "views" / "dashboard.py").read_text()
    assert "Market potential" in src and "Income" not in src
