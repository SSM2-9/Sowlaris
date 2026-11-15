"""Every influential number is traceable: value, unit, value type and source (audit item 17)."""
import pandas as pd

from fieldshift import config as C
from scripts.build_parameter_registry import main as build

ALLOWED = {"measured", "literature", "literature_range", "expert_estimate", "regional_practice", "assumption"}


def test_registry_is_current_and_complete():
    reg = build()
    saved = pd.read_csv(C.ENGINE_DIR / "parameter_registry.csv")
    assert len(saved) == len(reg)
    assert set(reg.value_type) <= ALLOWED
    assert reg.source.fillna("").str.len().gt(0).all()
    traits = pd.read_csv(C.ENGINE_DIR / "crop_traits.csv")
    for col in ["water_need_mm", "root_depth_m", "drought_tol", "heat_tol", "waterlog_tol", "market"]:
        assert set(reg[reg.parameter == col].crop) == set(traits.crop), col


def test_literature_ranges_respected_or_flagged():
    reg = build()
    lit = reg[(reg.value_type == "literature_range") & reg.range_low.notna()]
    out = lit[(pd.to_numeric(lit.value) < lit.range_low - 1e-9) | (pd.to_numeric(lit.value) > lit.range_high + 1e-9)]
    assert (out.flag == "OUTSIDE published range").all()
    assert set(zip(out.parameter, out.crop)) <= {("root_depth_m", "sunflower")}   # sunflower is not in any candidate


def test_assumptions_are_not_labelled_as_literature():
    reg = build()
    for name in ["cover_crop_cost_penalty", "fixed_weight_climate_fit", "near_tie_threshold"]:
        assert reg.loc[reg.parameter == name, "value_type"].iloc[0] == "assumption"
    assert (reg[reg.parameter == "market"].value_type == "assumption").all()
