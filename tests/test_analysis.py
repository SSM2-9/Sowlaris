"""Time-series statistics, clustering and the yield model."""
import json

import numpy as np
import pandas as pd

from fieldshift import config as C
from fieldshift.analysis import timeseries


def test_theil_sen_recovers_known_slope():
    yrs = np.arange(2005, 2026)
    r = timeseries.mann_kendall_theil_sen(yrs, 2.0 * (yrs - 2005) + 5)
    assert abs(r["slope_per_decade"] - 20.0) < 1e-6
    assert r["p_value"] < 0.001 and r["significant_5pct"]


def test_theil_sen_no_trend_in_noise():
    rng = np.random.default_rng(0)
    r = timeseries.mann_kendall_theil_sen(np.arange(2005, 2026), rng.normal(size=21))
    assert not r["significant_5pct"]


def test_trends_table_reports_significance():
    tr = pd.read_csv(C.OUT["trends"])
    assert {"slope_per_decade", "p_value", "significant_5pct"} <= set(tr.columns)
    assert tr.set_index("indicator").loc["Winter NDVI (MODIS, Dec–Feb mean)", "significant_5pct"]


def test_regimes_cover_every_season():
    reg = pd.read_csv(C.OUT["regimes"])
    assert sorted(reg.year) == list(range(2005, 2026))
    assert reg.regime.nunique() >= 2


def test_yield_model_beats_baseline():
    ym = json.loads(C.OUT["yield_results"].read_text())
    cv = ym["model_comparison_leave_one_year_out"]
    best = cv[ym["best_model"]]
    assert best["MAE_pct_points"] < cv["Baseline (always 100% of normal)"]["MAE_pct_points"]
    assert best["R2"] > 0
    assert all(v < 0 for v in ym["scenarios_yield_change_pct_vs_normal_summer"]["hot_dry_like_2012"].values())


def test_what_if_is_monotonic():
    from fieldshift.models.yield_model import what_if
    a, b = what_if(0.0, 0), what_if(2.0, -20)
    assert all(b[c] <= a[c] for c in ["corn", "soybean", "sorghum"])
