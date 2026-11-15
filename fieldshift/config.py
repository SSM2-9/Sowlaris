"""
Central configuration for the Field Shift project.

Every path, constant and threshold used by the pipeline lives here, so that
results are reproducible and assumptions are visible in one place.
"""
from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
ENGINE_DIR = Path(__file__).resolve().parent / "engine"

# --------------------------------------------------------------------------- study site
FARM = {
    "name": "Demonstration farm, Riley County, Kansas, USA",
    "lat": 39.12,
    "lon": -96.63,
    "albers_x": -53966,          # EPSG:5070, used for the USDA CropScape web service
    "albers_y": 1788539,
    "county": "Riley",
    "state": "Kansas",
    "ssurgo_aoi_acres": 18.7,
}
PERIOD = (2005, 2025)            # analysis years (inclusive)

# --------------------------------------------------------------------------- raw files
RAW = {
    "power": DATA_RAW / "01_03_nasa_power_gpm_imerg_daily.csv",
    "smap": DATA_RAW / "02_nasa_smap_SPL3SMP_E_006.csv",
    "modis": DATA_RAW / "04_nasa_modis_MOD13Q1_061.csv",
    "eco_lst": DATA_RAW / "05a_nasa_ecostress_ECO_L2T_LSTE_002.csv",
    "eco_et": DATA_RAW / "05b_nasa_ecostress_ECO_L3T_JET_002.csv",
    "srtm": DATA_RAW / "06_nasa_srtm_SRTMGL1_NC_003.csv",
    "cdl": DATA_RAW / "07_usda_cropscape_cdl.csv",
    "ssurgo": DATA_RAW / "08_usda_ssurgo_horizons.csv",
    "gaez": DATA_RAW / "09_fao_gaez_v4_suitability.csv",
    "nass": DATA_RAW / "10_usda_nass_quickstats_riley.csv",
}

# --------------------------------------------------------------------------- processed files
OUT = {
    "power_daily": DATA_PROCESSED / "01_nasa_power_daily.csv",
    "power_monthly": DATA_PROCESSED / "01_nasa_power_monthly.csv",
    "power_yearly": DATA_PROCESSED / "01_nasa_power_yearly.csv",
    "smap_daily": DATA_PROCESSED / "02_smap_soil_moisture_daily.csv",
    "modis_16day": DATA_PROCESSED / "04_modis_vegetation_16day.csv",
    "eco_lst_obs": DATA_PROCESSED / "05a_ecostress_lst_observations.csv",
    "eco_et_obs": DATA_PROCESSED / "05b_ecostress_et_observations.csv",
    "terrain": DATA_PROCESSED / "06_srtm_terrain.csv",
    "cdl": DATA_PROCESSED / "07_cropscape_crop_history.csv",
    "soil_horizons": DATA_PROCESSED / "08_ssurgo_soil_horizons.csv",
    "soil_summary": DATA_PROCESSED / "08_ssurgo_soil_summary.csv",
    "gaez": DATA_PROCESSED / "09_gaez_crop_suitability.csv",
    "nass_tidy": DATA_PROCESSED / "10_nass_riley_all_years_tidy.csv",
    "nass_wide": DATA_PROCESSED / "10_nass_riley_2005_2025_wide.csv",
    "master_monthly": DATA_PROCESSED / "00_MASTER_monthly_farm_table.csv",
    "climatology": DATA_PROCESSED / "11_monthly_climatology.csv",
    "trends": DATA_PROCESSED / "12_long_term_trends.csv",
    "bare_soil": DATA_PROCESSED / "13_ndvi_bare_soil_by_year.csv",
    "regimes": DATA_PROCESSED / "14_climate_regimes_kmeans.csv",
    "heatmaps": DATA_PROCESSED / "15_risk_heatmap_matrices.csv",
    "yield_dataset": DATA_PROCESSED / "16_yield_climate_dataset.csv",
    "yield_predictions": DATA_PROCESSED / "16_yield_model_cv_predictions.csv",
    "yield_results": REPORTS / "yield_model_results.json",
    "analysis_summary": REPORTS / "analysis_summary.json",
    "recommendation": REPORTS / "example_recommendation.json",
    "pipeline_report": REPORTS / "pipeline_report.json",
}

# --------------------------------------------------------------------------- thresholds
HEAT_STRESS_C = 35.0             # daily max temperature counted as a heat-stress day
FROST_C = 0.0                    # daily min temperature counted as a frost day
HEAVY_RAIN_MM = 25.0             # daily rain counted as a heavy-rain (erosive) day
DRY_DAY_MM = 1.0
GDD_BASE_C, GDD_CAP_C = 10.0, 30.0
GROWING_SEASON = [5, 6, 7, 8, 9]
OFF_SEASON = [11, 12, 1, 2, 3, 4]

# Satellite quality rules (see docs/METHODOLOGY.md §2)
SMAP_FILL = -9999.0
SMAP_OK_FLAGS = {0, 1}           # bit1 (attempted) & bit2 (success) clear; bit0 (recommended) never 0 at this cropland pixel
MODIS_OK_RELIABILITY = {0, 1}    # 0 good, 1 marginal; 2 snow/ice, 3 cloudy excluded
ECO_LST_VALID_K = (240.0, 345.0)
ECO_MANDATORY_QA_OK = {0, 1}     # bits 0-1 of QC: 00 best, 01 nominal
NDVI_BARE = 0.30                 # monthly NDVI below this = little or no living cover
NDVI_WINTER_COVER = 0.35         # Nov–Apr NDVI above this = living winter cover present

# Palette (validated reference categorical palette, fixed order)
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
NEUTRAL = "#c9c8c2"


# ------------------------------------------------------------------ spatial / temporal footprint (audit item 11)
# What area and time each value really represents. Shown in the app and docs so no number is read as field-exact.
FOOTPRINTS = [
    # dataset, spatial footprint, temporal sampling, what it can tell us about THIS field, what it cannot
    ("NASA POWER (MERRA-2 / CERES)", "0.5° × 0.625° cell (~55 × 55 km)", "daily", "regional weather, heat days, ET0",
     "field-scale microclimate"),
    ("GPM IMERG rain", "0.1° cell (~10 km)", "daily (from half-hourly)", "rain amount and timing over the area",
     "rain on this exact field (storms are patchy)"),
    ("SMAP SPL3SMP_E", "9 km EASE-Grid cell, top ~5 cm", "daily AM/PM, gaps", "seasonal and year-to-year soil-moisture swings",
     "root-zone water of this field; it mixes many fields and land uses"),
    ("MODIS MOD13Q1 NDVI", "250 m pixel (~6 ha)", "16-day composite, assigned to its midpoint", "green vs bare months on and around the field",
     "exact planting/harvest dates; the pixel can include field edges"),
    ("ECOSTRESS LST / JET ET", "70 m pixel", "irregular ISS overpasses, clear sky only, 2018+", "crop water use on overpass days",
     "a complete daily record; overpass time varies"),
    ("SRTM elevation", "30 m pixel", "single acquisition (Feb 2000)", "elevation", "slope detail (taken from SSURGO classes)"),
    ("USDA CropScape (CDL)", "30 m pixel at the farm point", "annual", "crop grown on the field each year", "management (tillage, covers)"),
    ("USDA SSURGO", "4 map units in an 18.7-acre area of interest", "static survey", "soil texture, water storage, pH, drainage, erodibility",
     "within-field variation below map-unit scale; current pH (needs a soil test)"),
    ("FAO GAEZ v4", "5 arc-min cell (~9 km)", "1981–2010 baseline climate", "broad climate suitability of crops", "field soil or recent climate"),
    ("USDA NASS QuickStats", "whole Riley County (~1,600 km²)", "annual", "county yield swings and crops traded locally",
     "this field's yields; county data mix irrigated and dryland fields"),
]
