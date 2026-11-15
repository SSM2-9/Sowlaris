# Data Sources

All ten datasets are stored unchanged in `data/raw/`. Each was extracted for the farm point
**39.12 °N, −96.63 °E** (Riley County, Kansas).

| # | File in `data/raw/` | Product / version | Provider | Access tool | Resolution | Period | Records |
|---|---|---|---|---|---|---|---|
| 1 + 3 | `01_03_nasa_power_gpm_imerg_daily.csv` | NASA POWER Agroclimatology (MERRA-2, CERES) incl. **GPM IMERG** precipitation `IMERG_PRECTOT` | NASA LaRC / NASA GSFC | POWER Data Access Viewer | 0.5° × 0.625° (meteorology), 0.1° (IMERG), daily | 2005-01-01 → 2025-12-31 | 7 670 days |
| 2 | `02_nasa_smap_SPL3SMP_E_006.csv` | **SMAP** Enhanced L3 Radiometer Global Daily 9 km EASE-Grid Soil Moisture, SPL3SMP_E v006 | NASA / NSIDC DAAC | AppEEARS point sample | 9 km, daily AM/PM | 2015-03-31 → 2025-12-31 | 3 845 rows |
| 4 | `04_nasa_modis_MOD13Q1_061.csv` | **MODIS** Terra Vegetation Indices 16-Day L3 Global 250 m, MOD13Q1 v061 | NASA LP DAAC | AppEEARS | 250 m, 16-day | 2000–2025 | 595 composites |
| 5a | `05a_nasa_ecostress_ECO_L2T_LSTE_002.csv` | **ECOSTRESS** Tiled Land Surface Temperature and Emissivity, ECO_L2T_LSTE v002 | NASA JPL / LP DAAC | AppEEARS | 70 m, ISS overpasses | 2018–2025 | 3 323 rows |
| 5b | `05b_nasa_ecostress_ECO_L3T_JET_002.csv` | **ECOSTRESS** Tiled Ensemble Evapotranspiration (JET), ECO_L3T_JET v002 | NASA JPL / LP DAAC | AppEEARS | 70 m, ISS overpasses | 2018–2025 | 511 rows |
| 6 | `06_nasa_srtm_SRTMGL1_NC_003.csv` | **SRTM** Global 1 arc-second, SRTMGL1_NC v003 | NASA LP DAAC | AppEEARS | 30 m | Feb 2000 | 1 |
| 7 | `07_usda_cropscape_cdl.csv` | **Cropland Data Layer** (CDL) | USDA NASS | CropScape point service | 30 m, annual | 2006–2025 | 20 years |
| 8 | `08_usda_ssurgo_horizons.csv` | **SSURGO** soil survey, horizons of 4 map units (18.7 ac AOI) | USDA NRCS | Web Soil Survey | 1:12 000–1:24 000 | static | 21 horizons |
| 9 | `09_fao_gaez_v4_suitability.csv` | **GAEZ v4** crop suitability index, rainfed, high input, baseline climate | FAO / IIASA | GAEZ Data Portal (res05 ImageServer) | 5 arc-min (~9 km) | 1981–2010 | 25 crops |
| 10 | `10_usda_nass_quickstats_riley.csv` | **QuickStats** survey data, Riley County, KS: area planted/harvested, yield, production | USDA NASS | QuickStats | county, annual | 1926–2025 | 2 931 records |

## Spatial and temporal footprint (what each value really represents)

The farm is a single point (39.12, −96.63). No product was resampled to a field polygon: each value is the
nearest pixel / cell / map unit / county. Read every number at the scale in this table, not as a field measurement.

| Dataset | Spatial footprint | Temporal sampling | Can tell us about this field | Cannot tell us |
|---|---|---|---|---|
| NASA POWER (MERRA-2 / CERES) | 0.5° × 0.625° cell (~55 × 55 km) | daily | regional weather, heat days, ET0 | field-scale microclimate |
| GPM IMERG rain | 0.1° cell (~10 km) | daily (from half-hourly) | rain amount and timing over the area | rain on this exact field (storms are patchy) |
| SMAP SPL3SMP_E | 9 km EASE-Grid cell, top ~5 cm | daily AM/PM, gaps | seasonal and year-to-year soil-moisture swings | root-zone water of this field; it mixes many fields and land uses |
| MODIS MOD13Q1 NDVI | 250 m pixel (~6 ha) | 16-day composite, assigned to its midpoint | green vs bare months on and around the field | exact planting/harvest dates; the pixel can include field edges |
| ECOSTRESS LST / JET ET | 70 m pixel | irregular ISS overpasses, clear sky only, 2018+ | crop water use on overpass days | a complete daily record; overpass time varies |
| SRTM elevation | 30 m pixel | single acquisition (Feb 2000) | elevation | slope detail (taken from SSURGO classes) |
| USDA CropScape (CDL) | 30 m pixel at the farm point | annual | crop grown on the field each year | management (tillage, covers) |
| USDA SSURGO | 4 map units in an 18.7-acre area of interest | static survey | soil texture, water storage, pH, drainage, erodibility | within-field variation below map-unit scale; current pH (needs a soil test) |
| FAO GAEZ v4 | 5 arc-min cell (~9 km) | 1981–2010 baseline climate | broad climate suitability of crops | field soil or recent climate |
| USDA NASS QuickStats | whole Riley County (~1,600 km²) | annual | county yield swings and crops traded locally | this field's yields; county data mix irrigated and dryland fields |

**Temporal harmonisation** (`processing/satellite.py`, `processing/harmonize.py`): daily POWER/IMERG are summed or
averaged by calendar month (UTC days); SMAP = mean of passing AM/PM retrievals per day, then monthly mean, with a
day count; MODIS composites are assigned to their midpoint date (start + 8 days); ECOSTRESS overpasses are converted to
local time (UTC − 6 h), daytime LST is the monthly median, and ET/ET0 is computed on the same day as the overpass and
summarised as a monthly median. Every monthly satellite value carries an `_n_obs` count; months without observations
are left empty, never filled. Products cover different periods (POWER 2005–25, SMAP 2015–25, ECOSTRESS 2018–25), so
cross-product statistics use only overlapping months.

## Download settings

**NASA POWER** — Single point · Community *Agroclimatology* · Temporal *Daily* · Time standard **UTC**
(required for IMERG) · CSV. Parameters: T2M, T2M_MAX, T2M_MIN, PRECTOTCORR, IMERG_PRECTOT, RH2M,
WS2M, ALLSKY_SFC_SW_DWN, GWETTOP, GWETROOT (and related).

**AppEEARS** — Point sample, coordinates 39.12, −96.63, CSV output. Layers: SMAP soil moisture AM/PM
and retrieval quality flags; MODIS NDVI, EVI, pixel reliability; ECOSTRESS LST, QC, cloud mask, ETdaily;
SRTM elevation.

**CropScape** — CDL value at Albers point (−53 966, 1 788 539) for each year.

**Web Soil Survey** — Area of interest drawn around the point; exported map-unit and horizon properties
(sand/silt/clay, organic matter, pH, available water capacity, Kw, drainage class).

**GAEZ v4** — Theme 4 suitability, rainfed, high input, 1981–2010 climate; value identified at the point for each crop.

**QuickStats** — Survey · Crops · Field crops · all commodities · County level · Kansas · Riley · all years.

## Product pages

- NASA POWER — https://power.larc.nasa.gov/
- GPM IMERG — https://gpm.nasa.gov/data/imerg
- SMAP SPL3SMP_E v6 — https://nsidc.org/data/spl3smp_e/versions/6
- MODIS MOD13Q1 v061 — https://lpdaac.usgs.gov/products/mod13q1v061/
- ECOSTRESS ECO_L2T_LSTE v002 — https://lpdaac.usgs.gov/products/eco_l2t_lstev002/
- ECOSTRESS ECO_L3T_JET v002 — https://lpdaac.usgs.gov/products/eco_l3t_jetv002/
- SRTMGL1_NC v003 — https://lpdaac.usgs.gov/products/srtmgl1_ncv003/
- AppEEARS — https://appeears.earthdatacloud.nasa.gov/
- USDA CropScape — https://nassgeodata.gmu.edu/CropScape/
- USDA Web Soil Survey — https://websoilsurvey.nrcs.usda.gov/
- FAO GAEZ v4 — https://gaez.fao.org/
- USDA NASS QuickStats — https://quickstats.nass.usda.gov/

## Acknowledgement

The POWER data were obtained from the NASA Langley Research Center POWER Project, funded through the
NASA Earth Science Directorate Applied Science Program. SMAP, MODIS, ECOSTRESS and SRTM data were
retrieved via AppEEARS, courtesy of the NASA Land Processes Distributed Active Archive Center (LP DAAC)
and the NASA National Snow and Ice Data Center DAAC. GPM IMERG is provided by NASA GSFC. USDA NASS,
USDA NRCS and FAO/IIASA data are used under their public terms.
