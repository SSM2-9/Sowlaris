# Data Dictionary

All processed outputs are written by `scripts/run_pipeline.py` to `data/processed/` (tables) and
`reports/` (JSON). Numeric prefixes match the dataset numbers in `docs/DATA_SOURCES.md`; 00 and 11–16
are analysis products.

## Core table

### `00_MASTER_monthly_farm_table.csv` — 252 rows (21 years × 12 months), 49 columns
| Column | Unit | Description | Source |
|---|---|---|---|
| year, month | – | Calendar year and month | – |
| lat, lon | ° | Farm coordinates | – |
| temp_mean_c | °C | Monthly mean of daily mean temperature | POWER T2M |
| temp_max_of_month_c / temp_min_of_month_c | °C | Highest daily max / lowest daily min in month | POWER |
| rain_gpm_imerg_mm | mm | Monthly rain total | GPM IMERG |
| rain_merra2_mm | mm | Monthly rain total (bias-corrected reanalysis, comparison only) | POWER PRECTOTCORR |
| humidity_pct | % | Mean relative humidity at 2 m | POWER RH2M |
| wind_2m_m_s | m/s | Mean wind speed at 2 m | POWER WS2M |
| solar_mj_m2_day | MJ m⁻² d⁻¹ | Mean all-sky surface solar radiation | POWER (CERES) |
| soil_wetness_top_0_1 / soil_wetness_root_0_1 | 0–1 | Surface / root-zone soil wetness | POWER GWETTOP / GWETROOT |
| et0_hargreaves_mm | mm | Reference evapotranspiration (crop water demand) | FAO-56 Hargreaves |
| water_balance_mm | mm | rain_gpm_imerg_mm − et0_hargreaves_mm | derived |
| gdd_base10_c | °C·day | Growing degree days (base 10, cap 30) | derived |
| heat_stress_days / frost_days / heavy_rain_days / dry_days | days | Days with Tmax ≥ 35 °C / Tmin ≤ 0 °C / rain ≥ 25 mm / rain < 1 mm | derived |
| *_anomaly | as variable | Difference from the 2005–2025 mean of the same month | derived |
| smap_soil_moisture_m3m3 | m³/m³ | Mean quality-filtered daily soil moisture (top 5 cm) | SMAP |
| smap_soil_moisture_m3m3_n_obs | days | Days with a valid SMAP value | SMAP |
| ndvi, evi | – | Mean of valid 16-day composites | MODIS |
| ndvi_n_obs | count | Valid composites in month | MODIS |
| eco_lst_day_c | °C | Median daytime clear-sky land-surface temperature | ECOSTRESS LSTE |
| eco_lst_day_c_n_obs | count | Daytime overpasses used | ECOSTRESS |
| eco_et_mm_day | mm/day | Median actual evapotranspiration | ECOSTRESS JET |
| eco_et_mm_day_n_obs | count | Overpasses used | ECOSTRESS |
| et0_mm_day | mm/day | et0_hargreaves_mm ÷ days in month | derived |
| eco_et_to_et0_ratio | – | ECOSTRESS ET ÷ POWER ET0 of the same day, monthly median (< ~0.8 = water-limited) | derived |
| eco_et_to_et0_ratio_monthly_means | – | old method: monthly median ET ÷ monthly mean ET0 (kept for comparison) | derived |
| crop_grown | – | Crop on the field that year | CropScape |
| soil_* | various | Area-weighted field-average soil properties | SSURGO |
| elevation_m | m | Elevation | SRTM |
| county_{corn,soybeans,sorghum,wheat,hay}_yield | bu/ac (hay: tons/ac) | Riley County yield that year | NASS |

## Cleaned source tables

| File | Rows | Key columns |
|---|---|---|
| `01_nasa_power_daily.csv` | 7 670 | date, temp_mean/max/min_c, rain_gpm_imerg_mm, rain_merra2_mm, humidity_pct, wind_2m_m_s, solar_mj_m2_day, soil_wetness_*, et0_hargreaves_mm, water_balance_mm, gdd_base10_c, heat_stress_day, frost_day, heavy_rain_day, dry_day (0/1 flags) |
| `01_nasa_power_monthly.csv` | 252 | Same variables aggregated by month + anomalies |
| `01_nasa_power_yearly.csv` | 21 | Annual totals/means and event-day counts |
| `02_smap_soil_moisture_daily.csv` | 3 845 | date, smap_am_m3m3, smap_pm_m3m3, smap_soil_moisture_m3m3 (blank when no valid retrieval), n_retrievals |
| `04_modis_vegetation_16day.csv` | 595 | date, ndvi, evi (blank if rejected), pixel_reliability, quality_ok |
| `05a_ecostress_lst_observations.csv` | 589 | datetime_utc, lst_c, local_hour (UTC−6), daytime, date |
| `05b_ecostress_et_observations.csv` | 279 | datetime_utc, et_daily_mm, date |
| `06_srtm_terrain.csv` | 1 | lat, lon, elevation_m, srtm_tile, acquired |
| `07_cropscape_crop_history.csv` | 20 | year, cdl_code, crop, previous_crop |
| `08_ssurgo_soil_horizons.csv` | 21 | map_unit, soil_name, pct_of_field, top_in, bottom_in, sand/silt/clay_pct, ksat, awc, organic matter, kw, kf, CEC, pH, CaCO3, t_factor, wind erodibility |
| `08_ssurgo_soil_summary.csv` | 5 | One row per map unit + **FIELD_AVG** (area-weighted) |
| `09_gaez_crop_suitability.csv` | 25 | crop, suitability_index_0_10000, suitability_0_1, suitability_class |
| `10_nass_riley_all_years_tidy.csv` | 2 931 | year, crop, crop_detail, metric (yield, acres_harvested, production…), unit, value, cv_pct |
| `10_nass_riley_2005_2025_wide.csv` | 21 | year × {crop}_{acres_harvested, production, yield} |

## Analysis products

| File | Rows | Description |
|---|---|---|
| `11_monthly_climatology.csv` | 12 | Mean, standard deviation and count per calendar month for every key variable |
| `12_long_term_trends.csv` | 13 | indicator, unit, mean, Theil–Sen slope_per_decade with 95 % CI, kendall_tau, p_value, significant_5pct |
| `13_ndvi_bare_soil_by_year.csv` | 21 | months_with_ndvi, bare_months_observed (NDVI < 0.30), bare_months_scaled_to_12, peak_ndvi, winter_ndvi_mean, crop_grown |
| `14_climate_regimes_kmeans.csv` | 21 | Season features, cluster, regime name, county yields |
| `15_risk_heatmap_matrices.csv` | 1 386 | Long format year × month × variable (6 variables) with a display label |
| `16_yield_climate_dataset.csv` | 54 | County yields (corn, soybean, sorghum, wheat) with summer climate features, trend yield and yield_pct_of_normal |
| `16_yield_model_cv_predictions.csv` | 42 | Leave-one-year-out rows: fold trend (`trend_yield_fold`), observed `yield_pct_of_normal` (fold-normalised), `predicted_pct_of_normal` (RF) and every model's prediction |
| `16_yield_model_forward_predictions.csv` | 20 | Train-on-past-years predictions 2015–2025 (RF and baseline) |

## Reports (`reports/`)

| File | Content |
|---|---|
| `analysis_summary.json` | Headline statistics, NDVI cycle, agreement checks, trend results, climate-regime profiles |
| `yield_model_results.json` | Leakage-free validation (overall, by crop, by severity, forward, bootstrap), 2012 observed / held-out / in-sample, feature importance, scenarios (labelled in-sample), caveats |
| `example_recommendation.json` | Full `recommend()` output for default priorities (farm diagnosis, all scores, 3 strategies) |
| `pipeline_report.json` | Version, farm, validation results, freshness, per-step results, manifest |
| `run_manifest.json` | SHA-256 of every raw file, source URL, acquisition date, package versions, settings, seeds |
| `water_balance_validation.json` | ET0 method check, ECOSTRESS matched-day comparison, SMAP / yield correlations, storage settings |
| `ranking_sensitivity.json` | 300-draw ranking stability for four farmer profiles |
| `runoff_sensitivity.json` | Experimental runoff scenarios (not used in production) |

## Engine inputs

`fieldshift/engine/crop_requirements.csv` — sowing and harvest months, pH optimum and K-State lime threshold, drainage
need, forage outlet, irrigation; `value_type` and `source` per row.
`fieldshift/engine/parameter_registry.csv` — every crop trait and engine coefficient: value, unit, value_type, source,
range, flag (built by `scripts/build_parameter_registry.py`).

## Engine input (traits)

`fieldshift/engine/crop_traits.csv` — one row per crop: label, role, months in field (`5-9` = May–Sep;
`10-6` wraps the year), water_need_mm, drought_tol, heat_tol, waterlog_tol (0–1), n_fixer (0/1),
n_demand, root_depth_m, residue_om, ground_cover, pest_family, market, forage_value, gaez_crop,
risk_note, **source**.
