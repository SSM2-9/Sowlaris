"""
Feasibility checks, run on every candidate rotation BEFORE ranking.

Status per rotation
    feasible     no known blocking constraint
    conditional  possible, but needs management or verification (shown with warnings)
    infeasible   violates a hard constraint (never shown as a recommendation;
                 the current rotation is still shown as the baseline)

Checks
    1. planting window  — can each crop be sown after the previous crop is harvested?
                          If not, it needs interseeding into the standing crop.
    2. soil pH          — crop optimum and the K-State lime threshold for the region.
                          Low pH is CONDITIONAL (liming can correct it), never a permanent exclusion.
    3. drainage         — crops that need well-drained soil vs. slow subsoil permeability (SSURGO).
    4. farmer constraints — forage outlet, irrigation, "no more water than now".

Calendars and requirements: engine/crop_requirements.csv (every row has a source and a value_type).
Month granularity: a sowing deadline in month M is met by a harvest in month ≤ M.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from .. import config as C

FEASIBLE, CONDITIONAL, INFEASIBLE = "feasible", "conditional", "infeasible"
INFO = "info"                                   # issue severity that does not change the status
_RANK = {INFO: 0, FEASIBLE: 0, CONDITIONAL: 1, INFEASIBLE: 2}

# NRCS saturated hydraulic conductivity classes: < 1 µm/s = "moderately low" or slower.
SLOW_PERMEABILITY_KSAT_UM_S = 1.0


@lru_cache(maxsize=1)
def requirements() -> pd.DataFrame:
    return pd.read_csv(C.ENGINE_DIR / "crop_requirements.csv").set_index("crop")


def _issue(check, severity, message):
    return {"check": check, "severity": severity, "message": message}


def _label(traits, crop):
    return traits.loc[crop, "label"] if crop in traits.index else crop


def sowing_sequence(rot: dict):
    """Yield (previous crop, next crop) pairs in field order, including the wrap to the next cycle."""
    seq = [c for main, after in rot["years"] for c in (main, after) if c]
    for i, nxt in enumerate(seq):
        yield seq[i - 1] if len(seq) > 1 else None, nxt


def check_planting_windows(rot, traits, constraints):
    req, issues = requirements(), []
    for prev, nxt in sowing_sequence(rot):
        if prev is None or prev == nxt:
            continue
        p, n = req.loc[prev], req.loc[nxt]
        if n.sow_earliest_month < 6:          # spring-sown crop: only a cover crop terminated in spring can conflict
            if traits.loc[prev, "role"] == "cover" if prev in traits.index else False:
                if p.harvest_earliest_month > n.sow_latest_month:
                    issues.append(_issue("termination", INFEASIBLE,
                        f"{_label(traits, prev)} cannot be terminated before {_label(traits, nxt)} must be planted."))
                elif p.harvest_latest_month >= n.sow_earliest_month:
                    issues.append(_issue("termination", INFO,
                        f"Terminate {_label(traits, prev)} before planting {_label(traits, nxt)} "
                        f"(months {int(p.harvest_earliest_month)}–{int(p.harvest_latest_month)} vs sowing "
                        f"{int(n.sow_earliest_month)}–{int(n.sow_latest_month)}); see the crop's risk note."))
            continue
        if p.harvest_earliest_month > n.sow_latest_month or p.harvest_latest_month > n.sow_latest_month:
            msg = (f"{_label(traits, nxt)} should be sown by month {int(n.sow_latest_month)}, but "
                   f"{_label(traits, prev)} is usually harvested in months {int(p.harvest_earliest_month)}–"
                   f"{int(p.harvest_latest_month)}. It needs interseeding into the standing crop "
                   f"(or an early-maturing variety). Source: {n.source}")
            if constraints["can_establish_cover_before_harvest"]:
                issues.append(_issue("planting_window", CONDITIONAL,
                                     msg + " Farmer reports interseeding ability; establishment still uncertain."))
            else:
                issues.append(_issue("planting_window", INFEASIBLE, msg + " Farmer cannot interseed."))
        elif p.harvest_latest_month == n.sow_latest_month:
            issues.append(_issue("planting_window", INFO,
                                 f"Tight window: sow {_label(traits, nxt)} immediately after {_label(traits, prev)} harvest."))
    return issues


def check_soil(rot, traits, soil):
    req, issues = requirements(), []
    mains = dict.fromkeys(c for pair in rot["years"] for c in pair if c)
    for crop in mains:
        r = req.loc[crop]
        if pd.notna(r.ph_optimum_min) and soil.get("ph") is None:
            issues.append(_issue("soil_ph", CONDITIONAL, f"{_label(traits, crop)}: soil pH not available — test before planting."))
        if pd.notna(r.ph_optimum_min) and soil.get("ph") is not None and soil["ph"] < r.ph_optimum_min:
            lime = pd.notna(r.ph_lime_threshold_flint_hills) and soil["ph"] < r.ph_lime_threshold_flint_hills
            issues.append(_issue("soil_ph", CONDITIONAL,
                f"{_label(traits, crop)}: topsoil pH {soil['ph']:.2f} is below the {r.ph_optimum_min} optimum. "
                + ("Below the K-State lime threshold (5.8, Flint Hills and west): lime before seeding. " if lime else
                   "Above the K-State lime threshold for the Flint Hills (5.8), so lime may not be required — confirm "
                   "with a soil test; east of the Flint Hills K-State recommends lime below 6.4. ")
                + f"Source: {r.source}"))
        if isinstance(r.drainage_need, str) and soil.get("min_ksat_um_s") is not None \
                and soil["min_ksat_um_s"] < SLOW_PERMEABILITY_KSAT_UM_S:
            issues.append(_issue("drainage", CONDITIONAL,
                f"{_label(traits, crop)} needs {r.drainage_need} soil; the slowest SSURGO layer drains at "
                f"{soil['min_ksat_um_s']:.2f} µm/s (max clay {soil.get('max_clay_pct', float('nan')):.0f}%). "
                "Drainage class is not in our soil export — verify before planting (root-rot risk)."))
    return issues


def check_constraints(key, rot, traits, constraints, water_need, current_water_need):
    req, issues = requirements(), []
    crops = dict.fromkeys(c for pair in rot["years"] for c in pair if c)
    for crop in crops:
        if req.loc[crop, "needs_forage_outlet"] and not constraints["forage_market_or_livestock"]:
            issues.append(_issue("forage_outlet", CONDITIONAL,
                f"{_label(traits, crop)} is a forage crop: needs livestock or a hay buyer (farmer reports neither)."))
        if req.loc[crop, "irrigation_required"] and not constraints["irrigation_available"]:
            issues.append(_issue("irrigation", INFEASIBLE, f"{_label(traits, crop)} requires irrigation."))
    if constraints["limit_water_to_current"] and key != "current_corn_soy" and water_need > current_water_need + 1e-9:
        issues.append(_issue("water_limit", INFEASIBLE,
            f"Modelled crop-water demand {water_need:.0f} mm/yr exceeds the current rotation's "
            f"{current_water_need:.0f} mm/yr (farmer limit)."))
    return issues


def evaluate(key, rot, traits, soil, constraints, water_need, current_water_need) -> dict:
    issues = (check_planting_windows(rot, traits, constraints) + check_soil(rot, traits, soil)
              + check_constraints(key, rot, traits, constraints, water_need, current_water_need))
    worst = max((_RANK[i["severity"]] for i in issues), default=0)
    status = {0: FEASIBLE, 1: CONDITIONAL, 2: INFEASIBLE}[worst]
    return {"status": status, "issues": issues}
