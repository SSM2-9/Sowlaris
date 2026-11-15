"""Shared fixtures. Tests use the processed outputs; run scripts/run_pipeline.py first (done automatically if missing)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fieldshift import config as C  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def pipeline_outputs():
    if not C.OUT["recommendation"].exists():
        from scripts.run_pipeline import main
        main()


@pytest.fixture(scope="session")
def master():
    return pd.read_csv(C.OUT["master_monthly"])
