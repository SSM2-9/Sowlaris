"""
Raw-data validation at the loading boundary.

Every raw file is checked BEFORE processing for:
    * expected columns, and declared units where the file states them (NASA POWER header)
    * location (the file must describe the farm point) and date coverage
    * physical plausibility of values (catches wrong units, e.g. rain in inches,
      NDVI not scaled, LST in °C instead of K)
    * cross-source consistency (GPM IMERG vs MERRA-2 annual rain)
    * missing-value proportions

A failed HARD check raises DataValidationError and stops the pipeline: a wrong unit must
never silently become a recommendation. SOFT checks are recorded as warnings.

Datasets are REQUIRED or OPTIONAL (see DATASET_ROLES). A missing optional file is reported
and its dependent diagnostics are skipped; a missing required file is an error.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C

COORD_TOL_DEG = 0.01

# Required: the recommendation cannot be computed without it.
# Optional: diagnostics / evidence only (the engine runs without it and says so).
DATASET_ROLES = {
    "power": "required",   # climate, ET0, rain → water score, yield model
    "cdl": "required",     # current rotation
    "ssurgo": "required",  # soil facts, feasibility (pH, drainage)
    "gaez": "required",    # climate-fit score
    "nass": "required",    # yield model, county crops
    "smap": "optional",
    "modis": "optional",
    "eco_lst": "optional",
    "eco_et": "optional",
    "srtm": "optional",
}

POWER_UNITS = {
    "ALLSKY_SFC_SW_DWN": "MJ/m^2/day", "T2M": "C", "T2M_MAX": "C", "T2M_MIN": "C", "RH2M": "%",
    "WS2M": "m/s", "GWETTOP": "1", "GWETROOT": "1", "PRECTOTCORR": "mm/day", "IMERG_PRECTOT": "mm/day",
}
POWER_DAILY_RANGES = {  # physically possible daily values, not climate-specific
    "ALLSKY_SFC_SW_DWN": (0, 40), "T2M": (-50, 50), "T2M_MAX": (-45, 55), "T2M_MIN": (-55, 45),
    "RH2M": (0, 100), "WS2M": (0, 40), "GWETTOP": (0, 1), "GWETROOT": (0, 1),
    "PRECTOTCORR": (0, 500), "IMERG_PRECTOT": (0, 500),
}
ANNUAL_RAIN_PLAUSIBLE_MM = (150, 3000)   # any rain-fed cropland; 36 mm/yr (inches mistaken for mm) fails
IMERG_MERRA2_RATIO = (0.5, 2.0)          # two independent rain products must agree within a factor of 2
NASS_YIELD_RANGES = {                    # bu/ac, county averages (catches t/ha or kg/ha)
    "CORN, GRAIN - YIELD, MEASURED IN BU / ACRE": (20, 300),
    "SOYBEANS - YIELD, MEASURED IN BU / ACRE": (5, 100),
    "SORGHUM, GRAIN - YIELD, MEASURED IN BU / ACRE": (10, 220),
    "WHEAT, WINTER - YIELD, MEASURED IN BU / ACRE": (5, 130),
}


class DataValidationError(ValueError):
    """A raw file failed a hard check (wrong units, location, columns or impossible values)."""


@dataclass
class Report:
    dataset: str
    path: str
    role: str
    status: str = "ok"                          # ok | missing | failed
    checks: list = field(default_factory=list)  # (name, passed, detail)
    warnings: list = field(default_factory=list)

    def hard(self, name, passed, detail=""):
        self.checks.append((name, bool(passed), detail))
        if not passed:
            self.status = "failed"

    def soft(self, name, passed, detail=""):
        self.checks.append((name + " (soft)", bool(passed), detail))
        if not passed:
            self.warnings.append(f"{name}: {detail}")

    def as_dict(self):
        return {"dataset": self.dataset, "role": self.role, "status": self.status,
                "failed_checks": [f"{n}: {d}" for n, p, d in self.checks if not p and "(soft)" not in n],
                "warnings": self.warnings, "n_checks": len(self.checks)}


def _near(a, b):
    return abs(float(a) - float(b)) <= COORD_TOL_DEG


def _coords(rep, df, lat_col="Latitude", lon_col="Longitude"):
    ok = df[lat_col].map(lambda v: _near(v, C.FARM["lat"])).all() and df[lon_col].map(lambda v: _near(v, C.FARM["lon"])).all()
    rep.hard("location matches farm", ok, f"expected {C.FARM['lat']}, {C.FARM['lon']}")


def _columns(rep, df, cols):
    missing = [c for c in cols if c not in df.columns]
    rep.hard("required columns present", not missing, f"missing {missing}" if missing else "")
    return not missing


def _share_in(rep, name, s, lo, hi, min_share=0.95, hard=True):
    s = pd.to_numeric(s, errors="coerce").dropna()
    share = float(s.between(lo, hi).mean()) if len(s) else 0.0
    (rep.hard if hard else rep.soft)(name, share >= min_share, f"{100 * share:.1f}% of values in [{lo}, {hi}]")


# ---------------------------------------------------------------------------------- per dataset
def check_power(path) -> Report:
    rep = Report("power", str(path), DATASET_ROLES["power"])
    text = Path(path).read_text().splitlines()
    try:
        end = next(i for i, l in enumerate(text) if l.startswith("-END HEADER-"))
    except StopIteration:
        rep.hard("POWER header present", False, "no -END HEADER- line")
        return rep
    header = "\n".join(text[:end])
    m = re.search(r"latitude\s+(-?[\d.]+)\s+longitude\s+(-?[\d.]+)", header)
    rep.hard("location matches farm", bool(m) and _near(m.group(1), C.FARM["lat"]) and _near(m.group(2), C.FARM["lon"]),
             m.group(0) if m else "no location line")
    rep.hard("time standard is UTC", " in UTC" in header, "IMERG_PRECTOT requires UTC")
    for p, unit in POWER_UNITS.items():
        um = re.search(rf"^{p}\s+.*\(([^)]*)\)\s*$", header, flags=re.M)
        rep.hard(f"unit of {p} is {unit}", bool(um) and um.group(1) == unit, um.group(1) if um else "parameter not listed")
    df = pd.read_csv(path, skiprows=end + 1)
    if not _columns(rep, df, ["YEAR", "DOY", *POWER_UNITS]):
        return rep
    raw = df.copy()
    df = df.replace(-999, np.nan)
    for p, (lo, hi) in POWER_DAILY_RANGES.items():
        _share_in(rep, f"{p} physically plausible", df[p], lo, hi, min_share=1.0)
        miss = float(df[p].isna().mean())
        rep.hard(f"{p} missing ≤ 1%", miss <= 0.01, f"{100 * miss:.2f}% missing (-999)")
    rep.hard("T2M_MAX ≥ T2M_MIN", bool((df.T2M_MAX >= df.T2M_MIN - 1e-6).all()))
    years = range(C.PERIOD[0], C.PERIOD[1] + 1)
    expected = sum(366 if pd.Timestamp(y, 12, 31).day_of_year == 366 else 365 for y in years)
    rep.hard("complete daily coverage of study period", len(raw) == expected, f"{len(raw)} of {expected} days")
    annual = df.groupby("YEAR")[["IMERG_PRECTOT", "PRECTOTCORR"]].sum()
    lo, hi = ANNUAL_RAIN_PLAUSIBLE_MM
    rep.hard("annual IMERG rain plausible (unit check)", annual.IMERG_PRECTOT.between(lo, hi).all(),
             f"range {annual.IMERG_PRECTOT.min():.0f}–{annual.IMERG_PRECTOT.max():.0f} mm/yr, expected {lo}–{hi}")
    ratio = annual.IMERG_PRECTOT.sum() / annual.PRECTOTCORR.sum()
    rep.hard("IMERG vs MERRA-2 rain consistent (unit check)", IMERG_MERRA2_RATIO[0] <= ratio <= IMERG_MERRA2_RATIO[1],
             f"ratio {ratio:.2f}")
    # header text from POWER labels IMERG_PRECTOT with a MERRA-2 prefix; the values differ from PRECTOTCORR,
    # so it is a separate product. Recorded so a reviewer can check provenance.
    lab = re.search(r"^IMERG_PRECTOT\s+(.*)$", header, flags=re.M)
    rep.soft("IMERG_PRECTOT header description names IMERG", bool(lab) and "IMERG" in lab.group(1).upper(),
             f"header says: {lab.group(1).strip() if lab else 'n/a'}")
    return rep


def check_smap(path) -> Report:
    rep = Report("smap", str(path), DATASET_ROLES["smap"])
    p = "SPL3SMP_E_006_Soil_Moisture_Retrieval_Data_"
    df = pd.read_csv(path)
    if not _columns(rep, df, ["Latitude", "Longitude", "Date", p + "AM_soil_moisture", p + "PM_soil_moisture_pm",
                              p + "AM_retrieval_qual_flag", p + "PM_retrieval_qual_flag_pm"]):
        return rep
    _coords(rep, df)
    for c in [p + "AM_soil_moisture", p + "PM_soil_moisture_pm"]:
        v = df[c][df[c] != C.SMAP_FILL]
        _share_in(rep, f"{c.split('_Data_')[1]} in m³/m³ range", v, 0.0, 0.7, min_share=1.0)
    rep.hard("dates parse", pd.to_datetime(df.Date, errors="coerce").notna().all())
    return rep


def check_modis(path) -> Report:
    rep = Report("modis", str(path), DATASET_ROLES["modis"])
    p = "MOD13Q1_061__250m_16_days_"
    df = pd.read_csv(path)
    if not _columns(rep, df, ["Latitude", "Longitude", "Date", p + "NDVI", p + "EVI", p + "pixel_reliability"]):
        return rep
    _coords(rep, df)
    _share_in(rep, "NDVI scaled to −0.2…1 (not ×10000)", df[p + "NDVI"], -0.2, 1.0, min_share=1.0)
    _share_in(rep, "EVI scaled to −0.2…1", df[p + "EVI"], -0.2, 1.0, min_share=1.0)
    rep.hard("pixel reliability codes valid", df[p + "pixel_reliability"].isin([-1, 0, 1, 2, 3]).all())
    return rep


def check_eco_lst(path) -> Report:
    rep = Report("eco_lst", str(path), DATASET_ROLES["eco_lst"])
    df = pd.read_csv(path)
    col = "ECO_L2T_LSTE_002_LST"
    if not _columns(rep, df, ["Latitude", "Longitude", "Date", col, "ECO_L2T_LSTE_002_QC", "ECO_L2T_LSTE_002_cloud"]):
        return rep
    _coords(rep, df)
    v = pd.to_numeric(df[col], errors="coerce")
    v = v[v > 0]                                                   # 0 = fill
    _share_in(rep, "LST in kelvin (not °C)", v, 150, 400, min_share=0.99)
    rep.hard("timestamps are UTC", df.Date.astype(str).str.endswith("UTC").all())
    return rep


def check_eco_et(path) -> Report:
    rep = Report("eco_et", str(path), DATASET_ROLES["eco_et"])
    df = pd.read_csv(path)
    col = "ECO_L3T_JET_002_ETdaily"
    if not _columns(rep, df, ["Latitude", "Longitude", "Date", col]):
        return rep
    _coords(rep, df)
    _share_in(rep, "daily ET in mm/day range", df[col], 0, 15, min_share=0.9)
    rep.hard("timestamps are UTC", df.Date.astype(str).str.endswith("UTC").all())
    return rep


def check_srtm(path) -> Report:
    rep = Report("srtm", str(path), DATASET_ROLES["srtm"])
    df = pd.read_csv(path)
    col = "SRTMGL1_NC_003_SRTMGL1_DEM"
    if not _columns(rep, df, ["Latitude", "Longitude", col]):
        return rep
    _coords(rep, df)
    _share_in(rep, "elevation in metres", df[col], -100, 9000, min_share=1.0)
    return rep


def check_cdl(path) -> Report:
    rep = Report("cdl", str(path), DATASET_ROLES["cdl"])
    df = pd.read_csv(path)
    if not _columns(rep, df, ["year", "lat", "lon", "cdl_code", "crop"]):
        return rep
    _coords(rep, df, "lat", "lon")
    rep.hard("one record per year", df.year.is_unique)
    rep.hard("covers the most recent study year", df.year.max() == C.PERIOD[1], f"last year {df.year.max()}")
    return rep


def check_ssurgo(path) -> Report:
    rep = Report("ssurgo", str(path), DATASET_ROLES["ssurgo"])
    df = pd.read_csv(path)
    cols = ["map_unit", "pct_of_field", "top_in", "bottom_in", "sand_pct", "silt_pct", "clay_pct",
            "organic_matter_pct_low", "organic_matter_pct_high", "ph_low", "ph_high", "awc_in_in_low", "awc_in_in_high", "kw"]
    if not _columns(rep, df, cols):
        return rep
    tex = df.sand_pct + df.silt_pct + df.clay_pct
    rep.hard("sand + silt + clay = 100 %", tex.between(97, 103).all(), f"range {tex.min()}–{tex.max()}")
    rep.hard("pH between 3 and 10", df[["ph_low", "ph_high"]].stack().between(3, 10).all())
    rep.hard("organic matter 0–100 %", df[["organic_matter_pct_low", "organic_matter_pct_high"]].stack().between(0, 100).all())
    rep.hard("available water capacity in in/in (0–0.5)", df[["awc_in_in_low", "awc_in_in_high"]].stack().between(0, 0.5).all())
    rep.hard("horizon depths increase", (df.bottom_in > df.top_in).all())
    share = df.drop_duplicates("map_unit").pct_of_field.sum()
    rep.hard("map-unit shares sum to ~100 %", 95 <= share <= 105, f"{share:.1f}%")
    return rep


def check_gaez(path) -> Report:
    rep = Report("gaez", str(path), DATASET_ROLES["gaez"])
    df = pd.read_csv(path)
    if not _columns(rep, df, ["crop", "suitability_index_0_10000", "lat", "lon"]):
        return rep
    _coords(rep, df, "lat", "lon")
    rep.hard("suitability index 0–10000", df.suitability_index_0_10000.between(0, 10000).all())
    return rep


def check_nass(path) -> Report:
    rep = Report("nass", str(path), DATASET_ROLES["nass"])
    df = pd.read_csv(path, dtype=str)
    if not _columns(rep, df, ["Year", "County", "State", "Data Item", "Value"]):
        return rep
    rep.hard("county is RILEY, KANSAS", set(df.County) == {"RILEY"} and set(df.State) == {"KANSAS"},
             f"{sorted(set(df.County))[:3]} {sorted(set(df.State))[:3]}")
    for item, (lo, hi) in NASS_YIELD_RANGES.items():
        v = pd.to_numeric(df.loc[df["Data Item"] == item, "Value"].str.replace(",", ""), errors="coerce").dropna()
        rep.hard(f"{item.split(' -')[0]} yield in bu/ac", len(v) > 0 and v.between(lo, hi).all(),
                 f"{len(v)} values, range {v.min() if len(v) else 'n/a'}–{v.max() if len(v) else 'n/a'}")
    return rep


CHECKS = {"power": check_power, "smap": check_smap, "modis": check_modis, "eco_lst": check_eco_lst,
          "eco_et": check_eco_et, "srtm": check_srtm, "cdl": check_cdl, "ssurgo": check_ssurgo,
          "gaez": check_gaez, "nass": check_nass}


def validate_raw(paths: dict | None = None, strict: bool = True) -> dict:
    """Validate every raw file. Returns {dataset: report-dict}.
    strict=True raises DataValidationError if any file fails a hard check or a REQUIRED file is missing."""
    paths = paths or C.RAW
    out, errors = {}, []
    for key, fn in CHECKS.items():
        path = Path(paths[key])
        if not path.exists():
            rep = Report(key, str(path), DATASET_ROLES[key], status="missing")
            if DATASET_ROLES[key] == "required":
                errors.append(f"required dataset '{key}' not found: {path}")
            else:
                rep.warnings.append(f"optional dataset not found ({path.name}); its diagnostics are skipped")
        else:
            try:
                rep = fn(path)
            except Exception as e:                                  # unreadable / malformed file
                rep = Report(key, str(path), DATASET_ROLES[key])
                rep.hard("file readable", False, f"{type(e).__name__}: {e}")
            if rep.status == "failed":
                errors.append(f"{key}: " + "; ".join(f"{n} ({d})" for n, p, d in rep.checks if not p and "(soft)" not in n))
        out[key] = rep.as_dict()
    if strict and errors:
        raise DataValidationError("Raw-data validation failed:\n  - " + "\n  - ".join(errors))
    return out


def available(report: dict, key: str) -> bool:
    return report.get(key, {}).get("status") == "ok"


STALE_AFTER_DAYS = 400   # NASA POWER/IMERG final products lag by months; >~13 months means the data were not refreshed


def freshness(today=None) -> dict:
    """How old the newest climate observation and the newest crop map are."""
    today = pd.Timestamp(today or pd.Timestamp.today().normalize())
    out = {"checked_on": str(today.date()), "warnings": []}
    try:
        lines = Path(C.RAW["power"]).read_text().splitlines()
        i = next(i for i, l in enumerate(lines) if l.startswith("YEAR"))
        last = pd.read_csv(C.RAW["power"], skiprows=i, usecols=["YEAR", "DOY"]).iloc[-1]
        last_day = pd.Timestamp(int(last.YEAR), 1, 1) + pd.Timedelta(days=int(last.DOY) - 1)
        out["power_last_day"] = str(last_day.date())
        age = (today - last_day).days
        out["power_age_days"] = int(age)
        if age > STALE_AFTER_DAYS:
            out["warnings"].append(f"NASA POWER/IMERG data end on {last_day.date()} ({age} days ago): refresh the download.")
    except Exception as e:                                         # reported, not fatal
        out["warnings"].append(f"could not read POWER dates: {e}")
    try:
        cdl_last = int(pd.read_csv(C.RAW["cdl"]).year.max())
        out["cdl_last_year"] = cdl_last
        if today.year - cdl_last > 1:
            out["warnings"].append(f"CropScape crop history ends in {cdl_last}: the 'current rotation' may be out of date.")
    except Exception as e:
        out["warnings"].append(f"could not read CropScape years: {e}")
    return out
