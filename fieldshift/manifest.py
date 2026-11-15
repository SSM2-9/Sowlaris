"""Reproducibility manifest (audit item 24): exact inputs, software, settings and seeds of a pipeline run."""
from __future__ import annotations

import hashlib
import importlib.metadata as md
import platform
import sys
from datetime import datetime, timezone

from . import __version__, config as C

PACKAGES = ["numpy", "pandas", "scipy", "scikit-learn", "streamlit", "plotly", "pytest"]
ACQUISITION = {  # approximate: recorded from the download sessions, not from the providers
    "power": "NASA POWER Data Access Viewer, Nov 2026 (approx.)", "smap": "AppEEARS point request, Nov 2026 (approx.)",
    "modis": "AppEEARS point request, Nov 2026 (approx.)", "eco_lst": "AppEEARS point request, Nov 2026 (approx.)",
    "eco_et": "AppEEARS point request, Nov 2026 (approx.)", "srtm": "AppEEARS point request, Nov 2026 (approx.)",
    "cdl": "CropScape point service, Nov 2026 (approx.)", "ssurgo": "Web Soil Survey export, Nov 2026 (approx.)",
    "gaez": "GAEZ v4 ImageServer identify, Nov 2026 (approx.)", "nass": "QuickStats query, Nov 2026 (approx.)",
}
SOURCE_URLS = {
    "power": "https://power.larc.nasa.gov/data-access-viewer/", "smap": "https://appeears.earthdatacloud.nasa.gov/",
    "modis": "https://appeears.earthdatacloud.nasa.gov/", "eco_lst": "https://appeears.earthdatacloud.nasa.gov/",
    "eco_et": "https://appeears.earthdatacloud.nasa.gov/", "srtm": "https://appeears.earthdatacloud.nasa.gov/",
    "cdl": "https://nassgeodata.gmu.edu/CropScape/", "ssurgo": "https://websoilsurvey.nrcs.usda.gov/",
    "gaez": "https://gaez.fao.org/", "nass": "https://quickstats.nass.usda.gov/",
}


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def versions() -> dict:
    out = {}
    for p in PACKAGES:
        try:
            out[p] = md.version(p)
        except md.PackageNotFoundError:
            out[p] = None
    return out


def build() -> dict:
    from .models import water_balance as W, yield_model as Y
    from .engine import recommender as R
    files = {}
    for k, p in C.RAW.items():
        files[k] = ({"file": p.name, "sha256": sha256(p), "bytes": p.stat().st_size,
                     "source_url": SOURCE_URLS[k], "acquired": ACQUISITION[k]} if p.exists() else {"file": p.name, "missing": True})
    engine_files = {p.name: sha256(p) for p in sorted(C.ENGINE_DIR.glob("*.csv"))}
    return {
        "fieldshift_version": __version__,
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0], "platform": platform.platform(), "packages": versions(),
        "raw_inputs": files, "engine_tables": engine_files,
        "settings": {"farm": C.FARM, "period": C.PERIOD, "heat_stress_c": C.HEAT_STRESS_C, "frost_c": C.FROST_C,
                     "heavy_rain_mm": C.HEAVY_RAIN_MM, "ndvi_bare": C.NDVI_BARE, "smap_ok_flags": sorted(C.SMAP_OK_FLAGS),
                     "modis_ok_reliability": sorted(C.MODIS_OK_RELIABILITY), "eco_lst_valid_k": C.ECO_LST_VALID_K,
                     "water_model": R.WATER_MODEL, "k_bare": W.K_BARE, "tew_mm": W.TEW_MM,
                     "near_tie": R.NEAR_TIE, "fixed_weights": R.FIXED_WEIGHTS},
        "random_seeds": {"random_forest": Y.SEED, "kmeans": 0, "bootstrap": Y.SEED, "sensitivity_default": 0},
    }


def verify(manifest: dict) -> list[str]:
    """Return a list of raw files whose current checksum differs from the manifest."""
    bad = []
    for k, m in manifest["raw_inputs"].items():
        p = C.RAW[k]
        if m.get("missing"):
            continue
        if not p.exists() or sha256(p) != m["sha256"]:
            bad.append(k)
    return bad
