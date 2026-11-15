"""Regression tests for the yield-model evaluation (audit item 13: the yield trend was fitted on all years,
so each held-out year's own yield shaped its normalised target)."""
import numpy as np
import pandas as pd
import pytest

from fieldshift import config as C
from fieldshift.models import yield_model as Y

RAW, _ = Y.build_dataset()
RAW = RAW[["year", "crop", "yield"] + Y.FEATURES]


@pytest.mark.parametrize("year", [2008, 2012, 2023])
def test_held_out_yield_does_not_enter_detrending(year):
    s = RAW[RAW.crop.isin(Y.SUMMER_CROPS)]
    tr1, te1, t1 = Y.fold_data(s, year)
    s2 = s.copy()
    s2.loc[s2.year == year, "yield"] *= 3                     # wildly change ONLY the held-out year
    tr2, te2, t2 = Y.fold_data(s2, year)
    for c in t1:
        np.testing.assert_allclose(t1[c], t2[c])               # trend unchanged
    pd.testing.assert_frame_equal(tr1, tr2)                    # training targets unchanged
    np.testing.assert_allclose(te1.trend_yield, te2.trend_yield)


def test_held_out_yield_does_not_change_its_prediction():
    s = RAW.copy()
    p1 = Y.evaluate_loyo(s)
    s.loc[s.year == 2012, "yield"] *= 0.5
    p2 = Y.evaluate_loyo(s)
    a = p1[p1.year == 2012].sort_values("crop")[f"pred_{Y.MODEL_OF_RECORD}"].to_numpy()
    b = p2[p2.year == 2012].sort_values("crop")[f"pred_{Y.MODEL_OF_RECORD}"].to_numpy()
    np.testing.assert_allclose(a, b)                           # prediction depends only on the other years


def test_saved_out_of_sample_predictions_reproduce_metrics():
    import json
    res = json.loads(C.OUT["yield_results"].read_text())
    p = pd.read_csv(C.OUT["yield_predictions"])
    mae = (p.predicted_pct_of_normal - p.yield_pct_of_normal).abs().mean()
    assert mae == pytest.approx(res["validation"]["overall"]["Random Forest"]["MAE_pct_points"], abs=0.01)
    assert res["random_seed"] == Y.SEED


def test_model_of_record_beats_baseline_out_of_sample():
    import json
    v = json.loads(C.OUT["yield_results"].read_text())["validation"]
    assert v["overall"]["Random Forest"]["MAE_pct_points"] < v["overall"]["Baseline (always 100% of normal)"]["MAE_pct_points"]
    assert v["forward_chaining_2015_2025"]["model"]["MAE_pct_points"] < v["forward_chaining_2015_2025"]["baseline"]["MAE_pct_points"]
