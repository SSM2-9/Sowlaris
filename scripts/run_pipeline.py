"""
Field Shift — full reproducible pipeline.

    python scripts/run_pipeline.py

raw data (data/raw) → cleaning & harmonisation → time-series analysis →
climate-regime clustering → yield model → recommendation engine →
outputs in data/processed and reports/.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from fieldshift import __version__, config as C  # noqa: E402
from fieldshift.analysis import clustering, timeseries  # noqa: E402
from fieldshift.engine import recommender  # noqa: E402
from fieldshift.models import yield_model  # noqa: E402
from fieldshift.processing import harmonize, power, satellite, usda_fao  # noqa: E402
from fieldshift.validation import freshness, validate_raw  # noqa: E402


def step(name):
    print(f"\n▶ {name}")
    return time.time()


def validate_inputs() -> dict:
    """Stops with DataValidationError before any processing if a raw file has wrong units,
    location, columns or impossible values, or if a REQUIRED dataset is missing."""
    rep = validate_raw(C.RAW, strict=True)
    for k, r in rep.items():
        for w in r["warnings"]:
            print(f"  ⚠ {k}: {w}")
    return rep


def main() -> dict:
    C.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    C.REPORTS.mkdir(parents=True, exist_ok=True)
    report = {"version": __version__, "farm": C.FARM, "period": C.PERIOD, "steps": {}}

    step("0/7  Validating raw data (units, location, ranges, required files)")
    report["validation"] = validate_inputs()
    report["freshness"] = freshness()
    for w in report["freshness"]["warnings"]:
        print(f"  ⚠ {w}")

    t = step("1/7  NASA POWER + GPM IMERG (datasets 1, 3)")
    report["steps"]["power"] = power.run()

    t = step("2/7  USDA CropScape, SSURGO, FAO GAEZ, USDA NASS (datasets 7–10)")
    report["steps"]["usda_fao"] = usda_fao.run()

    t = step("3/7  NASA SMAP, MODIS, ECOSTRESS, SRTM (datasets 2, 4, 5, 6) + monthly harmonisation")
    ok = {k for k, r in report["validation"].items() if r["status"] == "ok"}
    sat_monthly, report["steps"]["satellite"] = satellite.run(available=ok)
    master = harmonize.build_master(pd.read_csv(C.OUT["power_monthly"]), sat_monthly)
    master.to_csv(C.OUT["master_monthly"], index=False)
    report["steps"]["master_table"] = {"rows": len(master), "columns": len(master.columns)}

    t = step("4/7  Time-series analysis (climatology, Theil–Sen / Mann–Kendall trends, NDVI bare soil)")
    clim = timeseries.climatology(master)
    trends = timeseries.trends(master)
    bare = timeseries.bare_soil_by_year(master)
    clim.to_csv(C.OUT["climatology"], index=False)
    trends.to_csv(C.OUT["trends"], index=False)
    bare.to_csv(C.OUT["bare_soil"], index=False)

    t = step("5/7  Climate-regime clustering (K-means) and risk heat-map matrices")
    regimes, regime_meta = clustering.climate_regimes(master)
    regimes.to_csv(C.OUT["regimes"], index=False)
    clustering.risk_matrices(master).to_csv(C.OUT["heatmaps"], index=False)

    summary = timeseries.summarise(master, clim, trends, bare)
    summary["climate_regimes"] = regime_meta
    summary["data_availability"] = {k: r["status"] for k, r in report["validation"].items()}
    C.OUT["analysis_summary"].write_text(json.dumps(summary, indent=2, default=str))
    report["steps"]["analysis"] = {"significant_trends": trends[trends.significant_5pct].indicator.tolist(),
                                   "k_regimes": regime_meta["k_selected"]}

    t = step("6/7  Yield model (Random Forest vs Ridge vs baseline, leave-one-year-out CV)")
    ym = yield_model.run()
    report["steps"]["yield_model"] = {"best": ym["best_model"],
                                      "scores": ym["model_comparison_leave_one_year_out"]}

    t = step("7/7  Recommendation engine")
    recommender.load_data.cache_clear()
    rec = recommender.recommend()
    rec["known_limitations"] += report["freshness"]["warnings"]
    C.OUT["recommendation"].write_text(json.dumps(rec, indent=2, default=str))
    report["steps"]["recommendation"] = {
        "ranking": [recommender.CANDIDATES[k]["name"] for k in rec["ranking"]],
        "top_alternative": rec["strategies"][1]["name"]}

    from scripts.validate_water_balance import run as validate_wb
    report["steps"]["water_balance_validation"] = {k: v for k, v in validate_wb().items() if k != "interpretation"}
    from fieldshift.manifest import build as build_manifest
    report["manifest"] = build_manifest()
    (C.REPORTS / "run_manifest.json").write_text(json.dumps(report["manifest"], indent=2, default=str))
    C.OUT["pipeline_report"].write_text(json.dumps(report, indent=2, default=str))
    print("\n✔ Pipeline complete.")
    print("  Top suggestion (default priorities):", rec["strategies"][1]["name"])
    print("  Outputs:", C.DATA_PROCESSED.relative_to(ROOT), "and", C.REPORTS.relative_to(ROOT))
    return report


if __name__ == "__main__":
    main()
