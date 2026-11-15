"""Reproducibility (audit item 24): manifest matches the inputs; same data + seeds → same results."""
import json

import pandas as pd

from fieldshift import config as C
from fieldshift import manifest as M
from fieldshift.engine import recommender as R


def test_manifest_checksums_match_raw_files():
    man = json.loads((C.REPORTS / "run_manifest.json").read_text())
    assert M.verify(man) == []
    assert set(man["raw_inputs"]) == set(C.RAW)
    assert man["random_seeds"]["random_forest"] == 0 and man["python"]


def test_manifest_detects_a_changed_file(tmp_path, monkeypatch):
    man = M.build()
    fake = tmp_path / "cdl.csv"
    fake.write_text(C.RAW["cdl"].read_text() + "\n")
    monkeypatch.setitem(C.RAW, "cdl", fake)
    assert M.verify(man) == ["cdl"]


def test_engine_is_deterministic():
    a = R.recommend()
    R.load_data.cache_clear()
    b = R.recommend()
    assert [s["id"] for s in a["strategies"]] == [s["id"] for s in b["strategies"]]
    assert all(a["all_scores"][k]["total"] == b["all_scores"][k]["total"] for k in a["all_scores"])


def test_yield_model_predictions_reproducible():
    from fieldshift.models import yield_model as Y
    raw, _ = Y.build_dataset()
    p1 = Y.evaluate_loyo(raw[["year", "crop", "yield"] + Y.FEATURES])
    p2 = Y.evaluate_loyo(raw[["year", "crop", "yield"] + Y.FEATURES])
    pd.testing.assert_frame_equal(p1, p2)


def test_sensitivity_script_same_seed_same_output():
    from scripts.sensitivity import run
    assert run(runs=2, seed=7, write=False) == run(runs=2, seed=7, write=False)
