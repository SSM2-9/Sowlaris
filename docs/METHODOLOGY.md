# Methodology


This document specifies every processing step, threshold, statistical method and modelling
assumption used by Field Shift. All constants live in `fieldshift/config.py`; section numbers
are referenced from the code.

---

## 1. Study site and period

| Item | Value |
|---|---|
| Location | Cropland, Riley County, Kansas, USA — **39.12 °N, −96.63 °E** (WGS 84) |
| Albers (EPSG:5070) | x = −53 966, y = 1 788 539 (used for the CropScape point query) |
| Elevation | 322 m (SRTM) |
| Soil area of interest | 18.7 acres around the point (Web Soil Survey) |
| Period | 1 Jan 2005 – 31 Dec 2025 (21 years); SMAP from 31 Mar 2015, ECOSTRESS from 2018 |
| Growing season | May–September; off-season November–April |

The first candidate point (39.18, −96.57) fell inside the city of Manhattan, KS; it was moved
to the nearest cropland pixel and every dataset was downloaded for the new point.

---

## 2. Data cleaning and quality control

### 2.1 NASA POWER + GPM IMERG (datasets 1 and 3) — `processing/power.py`
- Daily Agroclimatology community data, **UTC** time standard (required for the `IMERG_PRECTOT` column).
- Fill value −999 → missing. Result: 7 670 days, **0 missing values**. All raw files first pass
  `fieldshift/validation.py` (declared units, location, coverage, physical ranges, IMERG vs MERRA-2 consistency);
  a failure stops the pipeline. Note: the POWER header labels `IMERG_PRECTOT` "MERRA-2 Total Precipitation"; its values
  differ from MERRA-2 `PRECTOTCORR`, but the GPM IMERG attribution should be confirmed in the POWER documentation.
- **Rain** uses GPM IMERG (`IMERG_PRECTOT`); MERRA-2 rain (`PRECTOTCORR`) is kept for comparison.
- **Reference evapotranspiration ET0** — FAO-56 Hargreaves equation (Allen et al., 1998, Eq. 52):
  `ET0 = 0.0023 · (Tmean + 17.8) · √(Tmax − Tmin) · 0.408 · Ra`,
  where Ra is extraterrestrial radiation (FAO-56 Eq. 21) from latitude and day of year.
  Hargreaves was chosen because it needs only temperature and is robust where humidity and wind are
  reanalysis estimates. It is validated in `tests/` against FAO-56 Example 8 (Ra = 32.2 MJ m⁻² d⁻¹).
- **Water balance** = IMERG rain − ET0 (mm). Negative = crop depends on stored soil water.
- **Growing degree days** base 10 °C, daily Tmax capped at 30 °C.
- Daily event flags: **heat-stress day** Tmax ≥ 35 °C; **frost day** Tmin ≤ 0 °C;
  **heavy-rain day** ≥ 25 mm; **dry day** < 1 mm.
- Monthly and yearly aggregates; monthly **anomalies** = value − the 2005–2025 mean for that calendar month.

### 2.2 NASA SMAP SPL3SMP_E v6 (dataset 2) — `processing/satellite.py`
- Enhanced L3 passive soil moisture, 9 km EASE-Grid 2.0, AM (descending) and PM (ascending) passes.
- Keep a retrieval only if `retrieval_qual_flag ∈ {0, 1}`, value > 0 and ≠ −9999.
- **Note:** flag 0 ("recommended quality") never occurs at this pixel because vegetation water content
  over summer cropland exceeds the recommended threshold. Restricting to flag 0 would remove every
  observation, so flag 1 (retrieval attempted and successful, VWC above threshold) is accepted; flags 5
  and 7 (retrieval skipped/failed) are rejected. Results are therefore best read as **relative**
  seasonal and inter-annual changes.
- Daily value = mean of the passing AM and PM retrievals. Result: 2 613 days with data.

### 2.3 NASA MODIS MOD13Q1 v6.1 (dataset 4)
- 250 m, 16-day NDVI and EVI composites, assigned to the composite **midpoint** (start + 8 days).
- Keep pixel reliability ∈ {0 good, 1 marginal}; remove 2 (snow/ice) and 3 (cloud). 563 of 595 composites kept.

### 2.4 NASA ECOSTRESS L2T LSTE v2 and L3T JET v2 (dataset 5)
- Land-surface temperature: keep `cloud = 0`, mandatory QA bits (`QC & 3`) ∈ {0, 1}, and 240 K ≤ LST ≤ 345 K.
- The farm lies in the overlap of tiles 14SPJ and 14SQJ, so identical overpasses appear twice: they are averaged.
- Local time = UTC − 6 h; **daytime** overpasses are those between 09:00 and 17:00 local time.
- Daily ET (`ETdaily`, mm/day): keep 0–15 mm/day; tile duplicates averaged.
- Results: 589 clear LST overpasses (260 daytime), 279 ET overpasses.
- Monthly values use the **median** of overpasses because ECOSTRESS samples irregular days and times.

### 2.5 NASA SRTM SRTMGL1_NC v3 (dataset 6)
- 30 m elevation; one value (322 m) attached to the farm.

### 2.6 USDA and FAO datasets (7–10) — `processing/usda_fao.py`
- **CropScape CDL:** crop class at the point for each year 2006–2025; `previous_crop` added.
- **SSURGO:** horizon table for the 4 map units in the area of interest; an area-weighted
  `FIELD_AVG` row summarises topsoil organic matter, pH, plant-available water (0–79 in),
  maximum clay and erodibility Kw.
- **GAEZ v4:** crop suitability index (0–10 000) for rainfed, high-input management, baseline 1981–2010,
  read from the res05 ImageServer at the point.
- **NASS QuickStats:** Riley County survey data; tidy long table and a 2005–2025 wide table for the
  series CORN, GRAIN / SOYBEANS / SORGHUM, GRAIN / WHEAT, WINTER / HAY.

### 2.7 Harmonisation — `processing/harmonize.py`
One **master monthly table** (252 months × 49 columns) joining climate, satellites (with observation
counts), crop grown, field-average soil, elevation and county yields. The crop-water-stress ratio
`eco_et_to_et0_ratio` is ECOSTRESS ET ÷ POWER ET0 **of the same day**, summarised as a monthly median (the old
monthly-means ratio is kept as `eco_et_to_et0_ratio_monthly_means`). Missing optional datasets give empty columns
with 0 observation counts; nothing is gap-filled. Spatial and temporal footprints: `docs/DATA_SOURCES.md`.

---

## 3. Time-series analysis — `analysis/timeseries.py`

- **Climatology:** monthly means over 2005–2025 for every variable.
- **Trends:** Theil–Sen slope (median of pairwise slopes, robust to outliers) with a 95 % confidence
  interval; significance from the **Mann–Kendall test** (Kendall's τ, two-sided, α = 0.05) on 13
  annual indicators.
- **Results:** only the NDVI trends are significant — winter NDVI −0.048/decade (p < 0.001) and peak
  summer NDVI +0.080/decade (p < 0.001). Warming (+0.86 °C/decade, p = 0.085), more heat days
  (+6.5 days/decade, p = 0.30) and a drier water balance (−73 mm/decade, p = 0.49) are **signals that
  are not statistically confirmed** over 21 years, and are reported that way everywhere in the app.
- **Bare soil from space:** a month is "bare" if its mean NDVI < 0.30; counts are scaled to 12 months
  where composites are missing. Mean: 0.7 bare months/yr in 2005–07 (grass/pasture) vs 6.4 since 2015.
- **Cross-sensor agreement** (Pearson r on monthly values): SMAP vs POWER surface wetness 0.64
  (n = 130), ECOSTRESS ET vs ET0 0.80 (n = 73), NDVI vs ECOSTRESS ET 0.76 (n = 71). Independent
  instruments agreeing is the main evidence that the cleaned satellite series are trustworthy.

---

## 4. Climate regimes and risk maps — `analysis/clustering.py`

- Spatial clustering is meaningless for one point, so the **21 growing seasons** are clustered on:
  May–Sep heat-stress days, water balance, rain, heavy-rain days and Jul–Aug root-zone wetness.
- Features are standardised; K-means (n_init = 50, random_state = 0) for k = 2…5; **k is chosen by the silhouette
  score** (k = 2, silhouette 0.50).
- Clusters are named from their centroids (±0.5 SD rules): **Hot & dry** (12 seasons) and
  **Wet & mild** (9 seasons). Every season of 2021–2025 was Hot & dry.
- Each regime is linked to Riley County yields (corn 130 vs 146 bu/ac, soybean 39 vs 45, sorghum 85 vs 100;
  wheat 45 vs 40 — wheat does *better* in hot, dry years because it is harvested in June).
- Month × year matrices of water balance, heat, frost, heavy rain, NDVI and SMAP are exported for heat maps.

---

## 5. Candidate rotations and feasibility — `engine/recommender.py`, `engine/feasibility.py`

| ID | Rotation | Sequencing logic |
|---|---|---|
| current_corn_soy | Corn → Soybean | Observed on the field since 2010 (CropScape) |
| corn_soy_covers | Corn + cereal rye → Soybean + hairy vetch | Rye after corn before soybean; vetch after soybean feeds corn |
| corn_soy_rye | Corn → Soybean + cereal rye | Added in the audit: rye can be drilled after soybean harvest (by ~1 Nov) |
| sorghum_soy_vetch | Sorghum → Soybean + hairy vetch | Drought-tolerant grass crop; vetch N for sorghum |
| sorghum_soy_wheat_dc | Sorghum → Soybean → Winter wheat + double-crop soybean | Local K-State 12-year no-till system |
| corn_soy_wheat_vetch | Corn + rye → Soybean → Winter wheat + hairy vetch | Wheat breaks pest cycles; vetch after wheat feeds corn |
| alfalfa_corn_soy | Alfalfa ×3 → Corn + rye → Soybean | Perennial legume, deep roots, forage |

**Field timeline.** Each rotation is laid out month by month: a main crop whose window wraps the year end (winter
wheat 10–6) is sown the autumn before; a following crop that wraps (rye 10–4, vetch 9–4) continues into the next year;
when two crops claim a month the crop being harvested keeps it. Bare months and the water balance use this timeline.

**Feasibility** (before ranking; `engine/crop_requirements.csv`, each row sourced and typed):
- *Planting window:* a crop sown in late summer/autumn must be sowable after the previous crop's harvest; otherwise it
  needs interseeding → **infeasible**, or **conditional** if the farmer can interseed. A spring cover crop must be
  terminable before the next crop's sowing deadline.
- *Soil pH:* below the crop optimum → **conditional** (liming can correct it); the K-State lime threshold for the
  Flint Hills (5.8) is quoted. *Drainage:* crops needing well-drained soil on slow subsoil (Ksat < 1 µm/s) → conditional.
- *Farmer constraints:* irrigation, "no more modelled crop-water demand than the current rotation", interseeding
  ability, forage outlet (alfalfa without one → conditional).
- Infeasible rotations are never shown as alternatives; the current rotation is always shown; notices explain exclusions.

## 6. NASA daily water balance — `models/water_balance.py` (EXPLORATORY CALIBRATED MODEL)

Daily, 2005–2025, one soil reservoir:
S(t+1) = S(t) + P − ETa − D, with 0 ≤ S ≤ TAW_profile; P = GPM IMERG rain, D = drainage above capacity;
irrigation = 0 (dryland); runoff = 0 in production.

- **Storage:** SSURGO plant-available water (mean of low/high AWC), area-weighted over map units on a 1-cm grid. An
  **inferred rooting limit** stops counting water below a claypan (a horizon with ≥ 8 % more clay than the one above,
  ≥ 40 % clay and lowest Ksat < 0.1 µm/s): Wymore at 11 in and 6 in (eroded). Corn root zone: 109 mm (303 mm for the full profile).
- **Crop demand:** ETc = Kc · ET0 with a seasonal-average Kc = literature seasonal water use ÷ climatological ET0
  over the crop's months (calibrated on the observed climate; scenarios change ETc through ET0).
- **Stress:** FAO-56 Ks = 1 while accessible water ≥ (1 − p)·TAW_crop, then linear to 0; p from FAO-56 Table 22.
  Accessible water = S × TAW_crop / TAW_profile (uniform-profile assumption). Effective depth = min(crop depth, rooting limit).
- **Bare soil:** evaporation = min(0.3·ET0, water in the top 25 mm); a cover crop's ET is never below bare-soil
  evaporation (it includes soil evaporation).
- **Yield response:** FAO-33 seasonal Ky (corn 1.25, soybean 0.85, sorghum 0.9, winter wheat 1.05, alfalfa 1.1):
  Ya/Ym = 1 − Ky(1 − ΣETa/ΣETc), bounded 0–1; seasons beyond 50 % deficit are flagged.
- **Outputs per rotation** (averaged over every starting phase): cash-crop shortfall (mm/yr and %), relative yield
  (mean and 25th percentile = driest quarter of seasons), modelled crop-water demand (incl. covers), bare months.

**Checks** (`scripts/validate_water_balance.py`, `reports/water_balance_validation.json`):

| Check | Claypan-limited storage (used) | Full profile |
|---|---|---|
| ECOSTRESS ET/ET0, 64 matched overpasses Jul–Aug 2018–25 (observed 0.52) | 0.71 | 0.76 |
| r with SMAP monthly soil moisture | 0.60 | 0.55 |
| r of seasonal ETa/ETc with county yield, corn / soybean / sorghum | 0.78 / 0.76 / 0.69 | 0.74 / 0.67 / 0.61 |

Correlations are **supporting evidence, not proof of field-level accuracy**. The ECOSTRESS gap is unresolved.
Experimental runoff (`scripts/runoff_sensitivity.py`, SCS Curve Number, TR-55 CNs for hydrologic groups C/D, **off in
production**): 128–166 mm/yr runoff (14–18 % of rain) lowers modelled ET/ET0 to 0.62–0.59; only a "poor condition"
scenario (32 % of rain) reaches 0.49 and it weakens the yield correlations. Runoff is a plausible partial
explanation, not an established cause. Other candidates: seasonal-average Kc, ECOSTRESS sampling (70 m pixel,
overpass time, clear days), irrigated fields in county yields, the inferred rooting limit.

## 7. Scoring (each score 0–1) and ranking

| Score | Formula | Data |
|---|---|---|
| **Water** | 0.5·(1 − cash-crop shortfall mm/yr ÷ mean May–Sep ET0) + 0.5·drought tolerance | NASA water balance; traits |
| **Climate fit** | 0.4·GAEZ (normalised) + 0.2·heat tolerance + 0.2·wet-soil term + 0.2·drought-year relative yield (1 if irrigated) | FAO GAEZ; traits; water balance |
| **Soil health** | 1 − r_OM·(1 − raw); raw = 0.30 residue + 0.20 N-fixers + 0.20 roots + 0.20 cover share + 0.10 (1 − N demand) | traits; SSURGO organic matter |
| **Erosion** | 1 − r_E·(1 − raw); raw = 0.7·(1 − bare months/12) + 0.3·canopy cover | field timeline; SSURGO Kw / wind index |
| **Pest break** | 0.5·(1 − repeated families / n) + 0.5·min(families / 3, 1) | traits |
| **Market potential** | market presence − 0.08·cover share (+0.15·forage value with a forage outlet) | NASS county crops; **no prices or costs** |

- Wet-soil term = 1 − r_D·(1 − waterlog tolerance), r_D = share of the field with slow subsoil (here 0.97).
  Soil relevance factors r_OM, r_E, r_D never invent effects; they scale how much existing differences matter (anchors
  in `SOIL_PARAMS` are labelled assumptions).
- **Overlap (documented):** water = average shortage; climate-fit drought term = bad-year yield risk. Removing both
  changes the top-2 in 30 of 255 priority settings.
- **Random Forest:** not a scoring input (team decision); its estimate appears only in evidence text and the what-if tab.
- **Total** = Σ wᵢ·scoreᵢ / Σ wᵢ; farmer weights 0–5 (validated) for water, market potential, soil health and erosion;
  fixed climate fit = 2, pest break = 1.
- **Shown:** current rotation + the two best non-infeasible alternatives; alternatives within 0.02 are a **near-tie**
  (display heuristic, not a statistical test). Each card lists feasibility, strongest/weakest criterion and change vs current.
- **Sensitivity** (`scripts/sensitivity.py`, 300 draws: literature ranges, ±0.15 for expert estimates, fixed weights
  1.5–2.5 / 0.5–1.5): same suggested pair in 79 % (default), 79 % (water first), **42 % (market first)**, 100 % (soil &
  erosion first). Stability under assumptions, not probability of success. Every number with its type and source:
  `engine/parameter_registry.csv` (70 expert estimates, 44 assumptions, 26 literature, 14 literature ranges, 10 regional practice).

## 8. Yield model — `models/yield_model.py` (secondary diagnostic)

- **Target:** yield as % of the crop's linear trend; **in validation the trend is fitted inside each fold on training
  years only** (a held-out year never enters preprocessing). Features: Jun–Aug heat days, May–Sep water balance,
  Jul–Aug rain, Jul–Aug root-zone wetness. 42 crop-years (corn 14, soybean 17, sorghum 11), 20 independent seasons.
- **Model of record:** Random Forest (500 trees, min leaf 3, seed 0), pre-specified — not chosen by CV score.

| Leave-one-year-out (fold-wise detrending) | MAE (% points) | R² |
|---|---|---|
| Baseline (always 100 %) | 15.4 | 0.00 |
| Ridge regression | 13.1 | 0.30 |
| **Random Forest** | **11.2** (11.3 on macOS) | **0.44** |
| Forward in time 2015–25 (RF vs baseline) | 13.6 vs 16.5 | 0.20 |

By crop: corn 9.1 (R² 0.49), soybean 11.9 (0.45), sorghum 12.9 (0.36) % points (≈ ±12, ±5, ±12 bu/ac).
The old, leaky evaluation reported 9.8 / 0.43.

**2012 drought:** observed corn −34 %, soybean −27 %, sorghum −30 % vs trend; **held-out** RF predicted −16 %, −18 %,
−16 %; the full-sample (in-sample) estimate −29 %, −32 %, −29 % is used only in the what-if tab, labelled as such.
In poor years (< 85 % of normal) the RF is too optimistic by ~17 points; in good years (> 110 %) too pessimistic by
~16. Year-bootstrap of held-out errors: MAE gain over baseline 4.2 points (2.5–97.5 %: 0.8–7.5) — exploratory, not a
prediction interval. What-if scenarios outside the 2005–2025 range carry an extrapolation warning.

**Crop-loss provenance:** corn/soybean/sorghum = RF (in-sample, with held-out and observed values attached);
double-crop soybean, sunflower, alfalfa = proxies; oats = assumption; winter wheat = historical observation
(108 % of trend in the hottest quarter of years, capped at 0 loss); cover crops = not estimated.

## 9. Validation status

- **Software:** 162 automated tests including 8 Streamlit app tests (macOS, Python 3.14); `reports/run_manifest.json`
  records input checksums, versions, settings and seeds for every run.
- **Literature:** 14 agronomic claims compared with published research (`docs/templates/literature_comparison_table.md`):
  9 agree, 4 partly, 1 untested. Literature checks the *direction* of rules, not the 0–1 scores.
- **Expert review:** form prepared (`docs/templates/agronomist_blind_review_form.md`); **independent review pending**.

## 10. Honesty rules applied in the text

1. Trends are "statistically significant" only when Mann–Kendall p < 0.05.
2. Observed history, held-out predictions and in-sample model estimates are always labelled separately.
3. Literature claims, expert estimates and assumptions are labelled as such (parameter registry).
4. Each strategy lists feasibility issues, information gaps and risks for local review; near-ties and unstable
   rankings are shown as such.
5. The app states that it supports, and does not replace, the farmer's and agronomist's judgement.

## References

- Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998). *Crop evapotranspiration — FAO Irrigation and Drainage Paper 56.* FAO, Rome.
- Steduto, P., Hsiao, T.C., Fereres, E., Raes, D. (2012). *Crop yield response to water — FAO Irrigation and Drainage Paper 66* (Table 1: FAO-33 seasonal Ky).
- USDA NRCS (1986). *Urban Hydrology for Small Watersheds, TR-55*, 2nd ed., Table 2-2b.
- Hargreaves, G.H., Samani, Z.A. (1985). Reference crop evapotranspiration from temperature. *Applied Engineering in Agriculture* 1(2), 96–99.
- Sen, P.K. (1968); Mann, H.B. (1945); Kendall, M.G. (1975) — trend tests. Rousseeuw, P.J. (1987) — silhouettes. Breiman, L. (2001) — random forests.
- Agronomic sources: `crop_traits.csv`, `crop_requirements.csv`, `docs/templates/literature_comparison_table.md`.
