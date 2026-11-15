"""Plain-language views of the real NASA / USDA numbers produced by Ekram's pipeline (nothing is simulated)."""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

import pandas as pd

from core import engine

C = engine.C
FARM = C.FARM
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# One row per dataset the engine really uses (same ten as Data & methods in Ekram's app).
DATA_LINEAGE = [
    ("NASA POWER (MERRA-2, CERES)", "Weather and evaporation demand", "Daily temperature, humidity, wind, sunlight, soil wetness", "2005-2025"),
    ("NASA SMAP SPL3SMP_E", "Soil moisture", "Satellite soil moisture, 9 km, daily", "2015-2025"),
    ("NASA GPM IMERG", "Rainfall", "Satellite rainfall and heavy storms", "2005-2025"),
    ("NASA MODIS MOD13Q1", "Vegetation index (NDVI)", "Crop greenness, 250 m, every 16 days", "2000-2025"),
    ("NASA ECOSTRESS LSTE and JET", "Surface temperature, crop water use", "Heat and water stress, 70 m", "2018-2025"),
    ("NASA SRTM", "Elevation", "Terrain, 30 m", "2000"),
    ("USDA CropScape (CDL)", "Crop history", "Crop grown on the field each year", "2006-2025"),
    ("USDA SSURGO", "Soil", "Texture, organic matter, pH, drainage, erosion", "static"),
    ("FAO GAEZ v4", "Crop suitability", "Climate suitability of 25 crops", "1981-2010"),
    ("USDA NASS QuickStats", "County crops and yields", "Riley County crop areas and yields", "1926-2025"),
]

# Footprint of each satellite product around the farm (radius in metres), from C.FOOTPRINTS.
SATELLITE_LAYERS = [
    ("Soil moisture, SMAP (9 km cell)", 4500, "#3F5A3A", True),
    ("Rainfall, GPM IMERG (10 km cell)", 5000, "#7FA3A6", False),
    ("Greenness, MODIS (250 m pixel)", 125, "#5F7F4F", False),
    ("Crop water use, ECOSTRESS (70 m pixel)", 35, "#D2A441", False),
]


def km_from_farm(lat: float, lon: float) -> float:
    """Great-circle distance from the demonstration farm."""
    la1, lo1, la2, lo2 = map(radians, (FARM["lat"], FARM["lon"], lat, lon))
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(h))


def moisture_series(master: pd.DataFrame) -> pd.DataFrame:
    """July-August SMAP soil moisture by year (m3/m3)."""
    s = master[master.month.isin([7, 8])].dropna(subset=["smap_soil_moisture_m3m3"])
    return s.groupby("year").smap_soil_moisture_m3m3.mean().round(3).rename("July-August soil moisture (m3/m3)").to_frame()


def trend_alerts(farm: dict) -> list[tuple[str, str, str]]:
    """(style, title, text). Words in {braces} become hover tooltips. Every number comes from the pipeline."""
    short = -farm["gs_water_balance_mm"]
    eco = 100 * farm["eco_et_to_et0_jul_aug"]
    return [
        ("warn", "Crops need more water than rain provides",
         f"From May to September the air demands about {farm['gs_et0_mm']:.0f} mm ({{evapotranspiration}}) while "
         f"{farm['gs_rain_mm']:.0f} mm falls as rain: a shortfall of {short:.0f} mm in an average year."),
        ("note", "Crops are water-limited in midsummer",
         f"In July and August satellites show crops using {eco:.0f}% of the water the air demands. Below about 80% means "
         f"the crop is short of water."),
        ("note", "Soil dries out just when crops need it",
         f"Satellite {{soil moisture anomaly}} data show the top soil falling from {farm['smap_apr_may']:.2f} (April-May) to "
         f"{farm['smap_jul_aug']:.2f} m3/m3 (July-August)."),
        ("soil", "More months with bare soil",
         f"Soil was bare {farm['observed_bare_months_since_2015']:.1f} months a year since 2015, up from "
         f"{farm['observed_bare_months_2005_2007']:.1f} in 2005-07 (MODIS {{NDVI}} below 0.30, the {{bare-field period}}). "
         f"Winter greenness trend: {farm['trend_winter_ndvi']}."),
        ("warn", "Warming signal, not yet confirmed",
         f"Temperature trend: {farm['trend_temperature']}. Twenty-one years is short, so treat this as a signal to watch."),
    ]
