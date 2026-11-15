"""Bridge between the Sowlaris interface and Ekram's Field Shift engine.

Rule of this file: the interface never computes a score, ranking or recommendation itself.
Everything comes from `fieldshift/` (untouched). Only plain Python here, so it can be tested without Streamlit.
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # <repo>/sowlaris/core/engine.py -> <repo>
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from fieldshift import config as C  # noqa: E402
from fieldshift.engine.recommender import CANDIDATES, NEAR_TIE, load_data, recommend as _recommend  # noqa: E402
from fieldshift.models.water_balance import timeline  # noqa: E402
from fieldshift.models.yield_model import heat_days_per_degree, what_if as _what_if  # noqa: E402

SCORE_LABELS = {"water": "Water", "climate_fit": "Climate fit", "soil_health": "Soil health",
                "erosion_protection": "Erosion protection", "pest_break": "Pest break", "market_potential": "Market potential"}
FEASIBILITY = {"feasible": "Feasible", "conditional": "Conditional", "infeasible": "Infeasible"}
__all__ = ["C", "CANDIDATES", "NEAR_TIE", "SCORE_LABELS", "FEASIBILITY", "timeline", "heat_days_per_degree",
           "ensure_pipeline", "data", "csv", "recommend", "sensitivity_note", "what_if"]


@lru_cache(maxsize=1)
def ensure_pipeline() -> bool:
    """Same rule as Ekram's app: rebuild the data products if they are missing or older than the raw downloads."""
    out = C.OUT["recommendation"]
    raw_newer = out.exists() and any(p.exists() and p.stat().st_mtime > out.stat().st_mtime for p in C.RAW.values())
    if not out.exists() or raw_newer:
        from scripts.run_pipeline import main
        main()
    return True


@lru_cache(maxsize=1)
def data() -> dict:
    ensure_pipeline()
    load_data.cache_clear()
    return load_data()


@lru_cache(maxsize=16)
def csv(key: str) -> pd.DataFrame:
    return pd.read_csv(C.OUT[key])


@lru_cache(maxsize=128)
def recommend(water: int, market: int, soil: int, erosion: int, irrigation: bool = False,
              water_limit: bool = False, interseed: bool = False, forage: bool = False) -> dict:
    """Priorities are 0-5 (as in Ekram's app). Do not modify the returned dict: it is cached."""
    return _recommend(priorities={"water": water, "market_potential": market, "soil_health": soil, "erosion_protection": erosion},
                      constraints={"irrigation_available": irrigation, "limit_water_to_current": water_limit,
                                   "can_establish_cover_before_harvest": interseed, "forage_market_or_livestock": forage},
                      d=data())


@lru_cache(maxsize=1)
def _sensitivity():
    p = C.REPORTS / "ranking_sensitivity.json"
    return json.loads(p.read_text()) if p.exists() else None


def sensitivity_note(priorities: dict):
    """(profile name, share of runs with the same top pair, number of runs) or None. Logic copied from Ekram's app."""
    sens = _sensitivity()
    if not sens:
        return None
    top = max(priorities, key=priorities.get)
    if sorted(priorities.values()) == [priorities[top]] * 4:
        prof = "default (all 3)"
    else:
        prof = {"water": "water first", "market_potential": "market first", "soil_health": "soil & erosion first",
                "erosion_protection": "soil & erosion first"}[top]
    return prof, sens["profiles"][prof]["share_same_pair"], sens["runs"]


@lru_cache(maxsize=64)
def what_if(dt: float, rain: int) -> dict:
    return _what_if(dt, rain)
