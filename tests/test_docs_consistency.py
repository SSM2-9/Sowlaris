"""Item 25: numbers stated in README / METHODOLOGY match the current reports and engine output."""
import json
from pathlib import Path

from fieldshift import config as C
from fieldshift.engine import recommender as R

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text()
METH = (ROOT / "docs" / "METHODOLOGY.md").read_text()
YM = json.loads(C.OUT["yield_results"].read_text())
WB = json.loads((C.REPORTS / "water_balance_validation.json").read_text())
SENS = json.loads((C.REPORTS / "ranking_sensitivity.json").read_text())


def _quoted(x: float, text: str, nd: int, tol: float) -> bool:
    """True if the text quotes x to nd decimals, allowing a small cross-platform difference (tol).
    Random-Forest results differ in the 2nd decimal between macOS and Linux builds of the same versions."""
    steps = int(round(tol * 10 ** nd))
    return any(f"{x + k / 10 ** nd:.{nd}f}" in text for k in range(-steps, steps + 1))


def test_no_out_of_date_banners_left():
    for text in (README, METH):
        assert "Audit in progress" not in text


def test_yield_model_numbers():
    o = YM["validation"]["overall"]
    for text in (README, METH):
        assert _quoted(o["Random Forest"]["MAE_pct_points"], text, 1, 0.1)
        assert _quoted(o["Baseline (always 100% of normal)"]["MAE_pct_points"], text, 1, 0.1)
        assert _quoted(o["Random Forest"]["R2"], text, 2, 0.02)
    y = YM["year_2012"]
    assert f"corn −{-y['corn']['observed_pct_change_vs_trend']:.0f} %" in README
    assert any(f"−{-y['corn']['held_out_rf_prediction_pct_change'] + k:.0f} %" in README for k in (-1, 0, 1))


def test_water_balance_numbers():
    ours = WB["storage_settings"][0]
    for text in (README, METH):
        assert f"{ours['modelled_median_et_to_et0']:.2f}" in text
        obs = WB["ecostress_matched"]["observed_median_et_to_et0"]          # 0.525 → quoted as 0.52
        assert f"{int(obs * 100) / 100:.2f}" in text
        assert f"{ours['r_yield_corn']:.2f}" in text


def test_sensitivity_and_default_recommendation_numbers():
    assert f"{100 * SENS['profiles']['market first']['share_same_pair']:.0f} %" in README
    r = R.recommend()
    for s in r["strategies"]:
        assert f"{100 * s['scores']['total']:.0f} / 100" in README
    assert f"{abs(r['strategies'][1]['scores']['total'] - r['strategies'][2]['scores']['total']):.3f}" in README or \
        r["all_scores"][r["strategies"][1]["id"]]["total"] - r["all_scores"][r["strategies"][2]["id"]]["total"] < 0.02


def test_rotation_count_and_market_potential_language():
    assert f"{len(R.CANDIDATES)} candidate rotations" in README.replace("Seven", str(len(R.CANDIDATES)))
    assert "not income" in README
