"""
EXPERIMENTAL runoff sensitivity (audit items 8–9). Production scoring keeps runoff OFF.
    python scripts/runoff_sensitivity.py   → reports/runoff_sensitivity.json

For each TR-55 curve-number scenario: annual runoff, ECOSTRESS-matched ETa/ET0 (field history), mean root-zone storage,
cash-crop shortfall per rotation, SMAP and county-yield correlations, and how many of the 255 priority settings would
show a different pair of suggestions. A closer match to ECOSTRESS is NOT validation.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from fieldshift import config as C  # noqa: E402
from fieldshift.engine import recommender as R  # noqa: E402
from fieldshift.models import water_balance as W  # noqa: E402

K = ["water", "market_potential", "soil_health", "erosion_protection"]
GRID = [dict(zip(K, x)) for x in itertools.product([0, 1, 3, 5], repeat=4) if sum(x) > 0]


def run() -> dict:
    d0 = R.load_data()
    t = d0["traits"]
    daily = pd.read_csv(C.OUT["power_daily"], parse_dates=["date"])
    eco = pd.read_csv(C.OUT["eco_et_obs"], parse_dates=["date"])
    # same matching as scripts/validate_water_balance.py: one row per overpass (a day can have two), Jul–Aug 2018+
    e = eco.merge(daily[["date"]], on="date")
    e = e[e.date.dt.month.isin([7, 8]) & (e.date.dt.year >= 2018)]
    smap = pd.read_csv(C.OUT["smap_daily"], parse_dates=["date"]).dropna(subset=["smap_soil_moisture_m3m3"])
    nass = pd.read_csv(C.OUT["yield_dataset"])
    hist = {"years": [("corn", None), ("soybean", None)]}
    base_pairs = [{s["id"] for s in R.recommend(p, d=d0)["strategies"][1:]} for p in GRID]
    out = {"note": "Experimental. Production scoring uses no runoff. Matching ECOSTRESS better is not validation.",
           "ecostress_observed_median_et_to_et0": json.loads((C.REPORTS / "water_balance_validation.json").read_text())
           ["ecostress_matched"]["observed_median_et_to_et0"], "scenarios": []}
    for name, cn in W.RUNOFF_SCENARIOS.items():
        sim = W.simulate(hist, t, 0, runoff=cn)
        cons = W.water_conservation_error(sim)
        m = sim.merge(e[["date"]], on="date")
        ms = sim.set_index("date").storage.resample("MS").mean()
        ss = smap.set_index("date").smap_soil_moisture_m3m3.resample("MS").mean()
        j = pd.concat([ms, ss], axis=1).dropna()
        ry = {}
        for crop in ["corn", "soybean", "sorghum"]:
            sz = W.seasons(W.simulate({"years": [(crop, None)]}, t, 0, runoff=cn))
            y = nass[nass.crop == crop].merge(sz[["harvest_year", "et_ratio"]], left_on="year", right_on="harvest_year")
            y = y[y.year > C.PERIOD[0]]
            ry[crop] = round(float(np.corrcoef(y.et_ratio, y.yield_pct_of_normal)[0, 1]), 3)
        d = dict(d0)
        d["water"] = R.water_metrics(d0, runoff=cn)
        pairs = [{s["id"] for s in R.recommend(p, d=d)["strategies"][1:]} for p in GRID]
        rec = R.recommend(d=d)
        yrs = sim[sim.year > C.PERIOD[0]]
        out["scenarios"].append({
            "scenario": name, "curve_numbers": cn,
            "runoff_mm_per_year": round(float(yrs.groupby("year").runoff.sum().mean()), 0),
            "runoff_share_of_rain": round(float(yrs.runoff.sum() / yrs.rain.sum()), 3),
            "water_conservation_error_mm": round(cons, 9),
            "ecostress_days_modelled_median_et_to_et0": round(float((m.eta / m.et0).median()), 3),
            "mean_storage_mm": round(float(yrs.storage.mean()), 1),
            "r_smap_monthly": round(float(np.corrcoef(j.storage, j.smap_soil_moisture_m3m3)[0, 1]), 3),
            "r_yield": ry,
            "cash_shortfall_mm_per_year": {k: round(v["unmet_mm_cash_per_year"]) for k, v in d["water"].items()},
            "default_pair": [s["id"] for s in rec["strategies"][1:]],
            "top2_changed_vs_production": int(sum(a != b for a, b in zip(base_pairs, pairs))),
        })
    (C.REPORTS / "runoff_sensitivity.json").write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
