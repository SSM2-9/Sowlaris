"""Every crop-loss value carries its provenance; observed history is never presented as a validated forecast."""
import json

from fieldshift import config as C
from fieldshift.engine import recommender as R
from fieldshift.models import yield_model as Y

YM = json.loads(C.OUT["yield_results"].read_text())


def test_every_crop_loss_has_a_known_provenance():
    t = R.crop_loss_table(YM)
    allowed = set(R.LOSS_PROVENANCE)
    assert {c for c in R.load_data()["traits"].index if R.load_data()["traits"].loc[c, "role"] != "cover"} <= set(t)
    for crop, v in t.items():
        assert v["provenance"] in allowed, crop
        assert v["provenance_text"]


def test_only_corn_soybean_sorghum_are_rf_estimates():
    t = R.crop_loss_table(YM)
    rf = {c for c, v in t.items() if v["provenance"] == "rf_full_sample_estimate"}
    assert rf == {"corn", "soybean", "sorghum"}
    assert t["winter_wheat"]["provenance"] == "historical_observation"
    assert t["dc_soybean"]["provenance"] == "proxy"


def test_2012_reports_observed_held_out_and_full_sample_separately():
    for c in Y.SUMMER_CROPS:
        e = YM["year_2012"][c]
        assert {"observed_pct_change_vs_trend", "held_out_rf_prediction_pct_change",
                "full_sample_rf_estimate_pct_change_vs_median_summer"} <= set(e)
        assert e["held_out_rf_prediction_pct_change"] > e["observed_pct_change_vs_trend"]   # under-predicts the loss


def test_scenarios_are_labelled_in_sample():
    assert "NOT validated" in YM["scenarios_yield_change_pct_vs_normal_summer"]["provenance"]


def test_what_if_flags_extrapolation():
    w = Y.what_if(3.0, -40)
    assert w["provenance"] == "rf_full_sample_estimate"
    assert w["out_of_training_range"] and any("cannot extrapolate" in x for x in w["warnings"])
    assert not Y.what_if(0.0, 0)["out_of_training_range"]


def test_random_forest_not_used_in_scoring():
    d = dict(R.load_data())
    a = R.recommend(d=d)["all_scores"]
    d["hot_dry_loss"] = {k: -90.0 for k in d["hot_dry_loss"]}
    d["crop_losses"] = {}
    b = R.recommend(d=d)["all_scores"]
    assert all(a[k]["total"] == b[k]["total"] for k in a)
