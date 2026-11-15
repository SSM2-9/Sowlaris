"""
Ranking stability under uncertain parameters (audit gap 16).   python scripts/sensitivity.py [--runs 300]

Each run draws every uncertain number from its range in engine/parameter_registry.csv:
    literature_range → uniform within the published range (e.g. corn water use 610–762 mm)
    expert_estimate / market → value ± 0.15, clipped to 0–1 (a labelled ASSUMPTION, not a measured uncertainty)
    fixed weights → climate fit 1.5–2.5, pest break 0.5–1.5
The NASA water balance is re-run with the drawn water needs and root depths. Output: how often each rotation is
#1 / in the shown pair, for four farmer profiles → reports/ranking_sensitivity.json.

Frequencies describe STABILITY UNDER THESE ASSUMPTIONS, not probabilities of real-world success.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from fieldshift import config as C  # noqa: E402
from fieldshift.engine import recommender as R  # noqa: E402

PROFILES = {
    "default (all 3)": None,
    "water first": {"water": 5, "market_potential": 1, "soil_health": 1, "erosion_protection": 1},
    "market first": {"water": 1, "market_potential": 5, "soil_health": 1, "erosion_protection": 1},
    "soil & erosion first": {"water": 1, "market_potential": 1, "soil_health": 5, "erosion_protection": 5},
}
TRAIT_PARAMS = ["water_need_mm", "root_depth_m", "drought_tol", "heat_tol", "waterlog_tol", "n_demand",
                "residue_om", "ground_cover", "forage_value", "market"]


def draw(base: dict, reg: pd.DataFrame, rng) -> tuple[dict, dict]:
    t = base["traits"].copy()
    t[[c for c in TRAIT_PARAMS if c in t]] = t[[c for c in TRAIT_PARAMS if c in t]].astype(float)
    for _, r in reg[reg.parameter.isin(TRAIT_PARAMS) & reg.range_low.notna()].iterrows():
        if r.crop in t.index:
            t.loc[r.crop, r.parameter] = rng.uniform(r.range_low, r.range_high)
    w = {"climate_fit": rng.uniform(1.5, 2.5), "pest_break": rng.uniform(0.5, 1.5)}
    d = dict(base)
    d["traits"] = t
    d["water"] = R.water_metrics(d)
    return d, w


def run(runs: int = 300, seed: int = 0, write: bool = True) -> dict:
    rng = np.random.default_rng(seed)
    reg = pd.read_csv(C.ENGINE_DIR / "parameter_registry.csv")
    base = R.load_data()
    ref = {p: [s["id"] for s in R.recommend(pri, d=base)["strategies"][1:]] for p, pri in PROFILES.items()}
    first = {p: Counter() for p in PROFILES}
    shown = {p: Counter() for p in PROFILES}
    same_pair = Counter()
    saved = dict(R.FIXED_WEIGHTS)
    try:
        for _ in range(runs):
            d, w = draw(base, reg, rng)
            R.FIXED_WEIGHTS.update(w)
            for p, pri in PROFILES.items():
                ids = [s["id"] for s in R.recommend(pri, d=d)["strategies"][1:]]
                if ids:
                    first[p][ids[0]] += 1
                shown[p].update(ids)
                same_pair[p] += set(ids) == set(ref[p])
    finally:
        R.FIXED_WEIGHTS.clear()
        R.FIXED_WEIGHTS.update(saved)
    out = {"runs": runs, "seed": seed,
           "note": "Stability under the assumed parameter ranges — NOT probability of real-world success.",
           "profiles": {p: {"reference_pair": ref[p],
                            "share_same_pair": round(same_pair[p] / runs, 3),
                            "share_ranked_first": {k: round(v / runs, 3) for k, v in first[p].most_common()},
                            "share_shown": {k: round(v / runs, 3) for k, v in shown[p].most_common()}}
                        for p in PROFILES}}
    if write:
        C.REPORTS.mkdir(exist_ok=True)
        (C.REPORTS / "ranking_sensitivity.json").write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    print(json.dumps(run(a.runs, a.seed), indent=2))
