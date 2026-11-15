"""Regression tests for missing datasets (audit Q7: deleting SMAP crashed the pipeline although SMAP
does not affect any score). Each test rebuilds a copy of the project in a temp folder."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OPTIONAL = {"smap": "02_nasa_smap_SPL3SMP_E_006.csv", "modis": "04_nasa_modis_MOD13Q1_061.csv",
            "eco_lst": "05a_nasa_ecostress_ECO_L2T_LSTE_002.csv", "eco_et": "05b_nasa_ecostress_ECO_L3T_JET_002.csv",
            "srtm": "06_nasa_srtm_SRTMGL1_NC_003.csv"}


def _copy(tmp_path):
    dst = tmp_path / "proj"
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "processed", "reports"))
    (dst / "data" / "processed").mkdir()
    (dst / "reports").mkdir()
    return dst


def _run(proj):
    return subprocess.run([sys.executable, "scripts/run_pipeline.py"], cwd=proj, capture_output=True, text=True, timeout=300)


@pytest.mark.parametrize("missing", [["smap"], list(OPTIONAL)], ids=["smap_only", "all_optional"])
def test_pipeline_runs_without_optional_datasets(tmp_path, missing):
    proj = _copy(tmp_path)
    for k in missing:
        (proj / "data" / "raw" / OPTIONAL[k]).unlink()
    res = _run(proj)
    assert res.returncode == 0, res.stderr[-2000:]
    rec = json.loads((proj / "reports" / "example_recommendation.json").read_text())
    assert len(rec["strategies"]) == 3
    for k in missing:
        assert rec["data_availability"][k] == "missing"
        assert any(f"'{k}'" in x for x in rec["known_limitations"])
    text = json.dumps(rec)
    assert "NaN" not in text                                      # no invented or broken numbers
    if "smap" in missing:
        assert all("SMAP): not available" in " ".join(s["evidence"]) for s in rec["strategies"])


def test_pipeline_stops_with_clear_error_without_required_dataset(tmp_path):
    proj = _copy(tmp_path)
    (proj / "data" / "raw" / "01_03_nasa_power_gpm_imerg_daily.csv").unlink()
    res = _run(proj)
    assert res.returncode != 0
    assert "required dataset 'power' not found" in res.stderr


def test_stale_data_is_reported():
    from fieldshift.validation import freshness
    old = freshness(today="2028-06-01")
    assert any("refresh the download" in w for w in old["warnings"])
    assert any("CropScape" in w for w in old["warnings"])
    fresh = freshness(today="2026-03-01")
    assert fresh["warnings"] == []
