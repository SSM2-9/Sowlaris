# Audit fix log

Each fix records: the code change, a regression test that failed before the change, the test result
after it, and the limitation that remains. "Baseline" = version 1.0.0 before the audit.

---

## Phase 1 — reliability and immediate correctness

### Item 1 · Invalid farmer inputs
- **Change:** `recommender.validate_priorities()` and `validate_constraints()`. Weights must be numbers in 0–5
  (not bool, NaN, ∞ or text), keys must be known, at least one weight must be above 0. Constraints must be booleans.
- **Test:** `tests/test_input_validation.py`. Before: 13 of 14 failed (−5 produced a total of 1.04; NaN propagated;
  a misspelt key raised KeyError). After: all pass.
- **Remaining limitation:** fractional weights (e.g. 2.5) are accepted on purpose; the app sliders only send integers.

### Item 2 · Units and physical ranges
- **Change:** new `fieldshift/validation.py`, called by `scripts/run_pipeline.py` before any processing.
  Checks columns, declared POWER units, location, date coverage, missing-value share, physical ranges and
  cross-source consistency (IMERG vs MERRA-2 annual rain within a factor of 2). Hard failures stop the pipeline.
- **Test:** `tests/test_data_units.py` (11 tests: rain in inches, both rain products in inches, °F temperature,
  wrong declared unit, wrong location, unscaled NDVI, LST in °C, yield in t/ha, texture ≠ 100 %).
  Before: rain ÷ 25.4 passed the pipeline and all 18 original tests and produced a recommendation (36 mm/yr).
  After: the pipeline stops with `DataValidationError`.
- **Remaining limitation:** only NASA POWER declares units in the file; other datasets are checked by range,
  which catches gross unit errors (×10, ×25.4, K/°C) but not subtle ones.
- **Open provenance question:** the POWER header describes `IMERG_PRECTOT` as "MERRA-2 Total Precipitation
  (mm/day)". Its values differ from MERRA-2 `PRECTOTCORR`, so it is a separate series, but the GPM IMERG
  attribution should be confirmed with the POWER parameter documentation. Recorded as a validation warning.

### Item 3 · Drought water-score saturation (interim)
- **Change:** the clipped linear term was replaced by `water_availability()`, a logistic in demand ÷ rain that
  matches the old rule in the normal range but never clips. Labelled **PROVISIONAL** in code, in the output
  (`_water_model`, `known_limitations`) and here. The proper fix is item 7.
- **Tests:** `tests/test_water_score.py` (16 tests: strictly decreasing in demand, increasing in rain, rotations
  stay distinct at 30–125 % of rain). Before: 16 failed. After: all pass.
  `tests/test_drought_counterfactual.py` keeps the scientific criterion: *a drier climate must never let a
  thirstier rotation gain on a less thirsty one*. It is marked `xfail(strict=True)` — it fails with the proxy
  (e.g. alfalfa still rises to #2 when rain is halved) and must pass after item 7.
- **Remaining limitation:** the engine does **not** reliably rank rotations under extreme drought until item 7.

### Item 12 · Missing and stale datasets
- **Change:** datasets are classed required (POWER, CDL, SSURGO, GAEZ, NASS) or optional (SMAP, MODIS,
  ECOSTRESS LST/ET, SRTM). Missing optional data → NaN columns with 0 observation counts, skipped
  diagnostics, `data_availability` and a limitation in the output; no stale processed file is left behind.
  Missing required data → clear error. `validation.freshness()` warns when POWER data are > 400 days old or
  CropScape ends more than a year ago. The app rebuilds if any raw file is newer than the outputs.
- **Tests:** `tests/test_missing_data.py`. Before: deleting SMAP crashed the pipeline (`FileNotFoundError`).
  After: the pipeline runs without SMAP and without all five optional datasets, writes no NaN, states the gap;
  missing POWER stops with "required dataset 'power' not found".
- **Remaining limitation:** freshness is a date check only; it does not detect a revised NASA product version.

### Items 4, 5, 6, 19 (engine side) · Feasibility and farmer constraints
- **Change:** new `fieldshift/engine/feasibility.py` and `engine/crop_requirements.csv` (sowing / harvest months,
  pH optimum and K-State lime threshold, drainage need, forage outlet, irrigation, each with source and value type).
  Every rotation is checked before ranking: planting windows (incl. wrap to the next cycle), pH, drainage,
  forage outlet, irrigation, "no more water than now". Infeasible rotations are never shown as alternatives;
  the current rotation is always shown; notices explain exclusions and fewer-than-two cases.
- **Tests:** `tests/test_feasibility.py` (9 tests). Baseline: vetch after soybean shown in 242 / 256 priority
  settings, alfalfa in 96 / 256, always as ordinary recommendations.
  After (default: no interseeding): vetch after soybean shown 0 / 255; alfalfa is shown only with status
  *conditional* and its pH, drainage and forage warnings.
- **Effect on results (reported, not tuned):** with the default constraints the two cover-crop rotations that put
  hairy vetch after soybean are excluded, so the default suggestions change to *Alfalfa → Corn → Soybean
  (conditional)* and *Corn → Soybean → Winter wheat + hairy vetch*.
- **Remaining limitations:** calendars for corn, soybean, sorghum, wheat and double-crop soybean are typical
  regional practice, labelled "assumed", to be verified; month granularity; the soil drainage class is inferred
  from Ksat because it is not in our SSURGO export; herbicide carry-over and equipment are not modelled.

**Note on 255 vs 256 priority combinations.** The audit grid is every combination of the four farmer weights
in {0, 1, 3, 5} = 4⁴ = 256. One of them, all four weights = 0, is now rejected as invalid input (item 1),
so every post-fix comparison uses the remaining 255. The baseline numbers quoted from the audit (e.g. 242/256)
included that combination, which the old engine silently scored on climate fit and pest break only.

**Expected failures are tracked, not skipped.** Known failures use `pytest.mark.xfail(strict=True)`: pytest
reports them as `XFAIL`, and if one unexpectedly passes it is reported as a FAILURE (`XPASS(strict)`) so it is
reviewed and the marker removed.

---

## Phase 2 — scientific scoring

### Seventh rotation · Corn → Soybean + cereal rye cover (team decision)
- **Change:** `corn_soy_rye` added to `CANDIDATES`. Rye trait sources extended (K-State eUpdate and MF3504:
  plant by Nov 1, N scavenging, erosion/evaporation reduction, wheat-streak-mosaic host risk; water use 120 mm is
  an assumption consistent with Nebraska on-farm data). New feasibility rule: a spring-terminated cover crop must
  be terminable before the next crop's sowing deadline (`termination` check).
- **Result:** feasible (two *info* notes: sow rye immediately after soybean harvest; terminate before corn).
  Shown in 39 / 255 priority settings, #1 in 22; not in the default pair. Versus the current rotation it scores
  higher on erosion protection (0.73 vs 0.57) and soil health (0.72 vs 0.69), equal on water (0.61 vs 0.61 — in
  the observed climate the profile refills after rye; under −50 % rain its cash-crop shortfall is 284 vs 270 mm/yr),
  lower on market potential (0.94 vs 0.98, cover-crop cost). Nitrogen tie-up before corn is stated in its risk
  note; it is **not** given a numeric penalty because no sourced magnitude is available.

### Items 7, 8 · NASA daily water balance in scoring
- **Change:** new `fieldshift/models/water_balance.py` (daily bucket, FAO-56 Ks stress, FAO-33 Ky, field timeline
  with correct autumn sowing of winter wheat). Scores now use it:
  - **water** = 0.5 × (1 − cash-crop shortfall mm/yr ÷ mean May–Sep ET0) + 0.5 × drought tolerance (linear in mm: cannot saturate)
  - **climate fit** drought term = relative yield in the driest quarter of crop-seasons (FAO-33); the Random Forest
    term was **removed** from scoring (team decision A); its estimate stays in the evidence text only
  - **erosion** uses bare months from the corrected field timeline
  - **market potential** replaces income (no price, cost or yield inside it); `income` is accepted as a deprecated alias
- **Tests:** `tests/test_water_balance.py` (conservation to 1e-6 mm, 0 ≤ S ≤ capacity, no-rain and saturating-rain
  scenarios, monotonic in rain / ET0 / storage, Ky bounds, claypan limits, wheat timeline, Hargreaves vs
  Penman–Monteith). A test found 6 days with negative Hargreaves ET0 (mean < −17.8 °C) → `hargreaves_et0` now clips at 0.

### Item 9 · ECOSTRESS vs SSURGO storage
Run `python scripts/validate_water_balance.py` → `reports/water_balance_validation.json`.

| Check | Result |
|---|---|
| ET0 method | Hargreaves 769 vs Penman–Monteith 789 mm (May–Sep): ratio 0.975 — not the cause |
| ECOSTRESS, matched days (n = 64, Jul–Aug 2018–25) | observed ET/ET0 median 0.52 — same as the monthly method; clear-sky days have ET0 5.61 vs 5.51 mm/d (2 % bias) — not the cause |
| Root-zone storage | full SSURGO 0–2 m = 360 mm (corn root zone 303 mm). Inferred claypan limit (Wymore, clay jump ≥ 8 %, ≥ 40 % clay, Ksat < 0.1 µm/s at 11 in / 6 in) → corn root zone **109 mm** |

| Storage setting | Corn TAW | ECOSTRESS ET/ET0 (obs 0.52) | r SMAP | r yield corn / soy / sorghum |
|---|---|---|---|---|
| claypan-limited (used) | 109 mm | 0.71 | 0.60 | 0.78 / 0.76 / 0.69 |
| claypan ×0.5 | 54 mm | 0.65 | 0.62 | 0.80 / 0.74 / 0.75 |
| claypan ×1.5 | 163 mm | 0.76 | 0.58 | 0.79 / 0.74 / 0.64 |
| full SSURGO profile | 303 mm | 0.76 | 0.55 | 0.74 / 0.67 / 0.61 |

- **Conclusion:** the claypan-limited storage agrees better than the full profile with all three independent
  observations, but the model still over-estimates ECOSTRESS crop water use (0.71 vs 0.52). **Unresolved**; likely
  causes: no runoff (K-State/USDA-ARS report only ~25 % of fallow-season rain is stored), seasonal-average Kc,
  ECOSTRESS sampling, irrigated fields in county yields. The storage was **not** tuned to match ECOSTRESS.
  Label: *exploratory calibrated model*.

### Item 10 · Soil characteristics in scoring
- **Change:** `recommender.soil_factors()` from SSURGO; one principle — soil sets how much a criterion's
  differences matter, it does not invent new effects: storage → water & drought risk (physical, via the water
  balance); slow-draining share → weight of wet-soil tolerance; water/wind erodibility → erosion; organic-matter
  deficit → soil health. Anchors are labelled assumptions (`SOIL_PARAMS`). Missing values → `None` and a pH
  "test before planting" condition, never invented.
- **Tests:** `tests/test_soil_sensitivity.py` (sandy, poorly drained clay, loam, acidic, missing values).
  Baseline: sandy and clay soils gave identical scores. After: scores differ, each through its documented route.

### Item 11 · Temporal harmonisation
- MODIS composites assigned to their midpoint (start + 8 days); ECOSTRESS ET/ET0 computed on matched days
  (monthly median of daily ratios; the old monthly-means ratio is kept as `eco_et_to_et0_ratio_monthly_means`).
- Effect: Jul–Aug ET/ET0 0.52 → 0.50; bare months since 2015 6.8 → 6.4; NDVI–ET r 0.78 → 0.76.

### Drought counterfactuals (rain changed in the daily IMERG series, 255 settings)

| Scenario | Top-2 changed | #1 changed |
|---|---|---|
| rain −20 % | 19 | 12 |
| rain −50 % | 41 | 37 |
| +2 °C (ET0 +10 %) | 10 | 8 |
| +2 °C and May–Sep rain −20 % | 24 | 17 |
| hot & dry seasons only | 11 | – |
| wet & mild seasons only | 25 | – |

- **Original criterion** ("a drier climate never favours a rotation with higher ANNUAL demand"): still fails, now
  only for pairs whose extra demand is in autumn–spring (winter wheat, cover crops) — a drier summer hurts
  summer-only rotations more, which is physically expected. Kept as `xfail(strict=True)` pending team decision.
- **Refined criteria (pass):** every rotation gets worse when rain falls; adding a cover crop never helps in
  drought; alfalfa (the audit case) never gains; no saturation at 30 % rain; every change in water-score order
  is explained by the modelled change in shortfall (mm).

### Influence of drought-related terms (overlap check, team adjustment 1)
Flattening the drought-risk term changes the top-2 in 10 / 255 settings; flattening the water-balance part of the
water score, 22; both, 30. Re-adding the old Random Forest term would change 32. With default weights the two
water-derived terms explain ~0.009 of a 0.072 spread in total score — drought stress is **not** over-weighted;
if anything NASA water data remains a modest driver compared with erosion / soil-health differences.


### Retired test · original drought rule (team decision 1)
`test_original_criterion_drier_climate_never_favours_higher_annual_demand` (and its proxy-era predecessor
`test_drier_climate_never_favours_thirstier_rotation`) is **retired as scientifically invalid**: annual water demand
does not determine drought sensitivity — a rotation whose extra demand falls in autumn–winter (winter wheat, cover
crops) can cope better with a summer drought than one with lower annual demand concentrated in summer. Its three
expected failures are removed and replaced in `tests/test_drought_counterfactual.py` by precise invariants:
1. for the **same rotation**, less rain never increases the share of crop demand met, never reduces the shortfall
   (mm) and never raises drought-year relative yield — the overall score or rank MAY rise because competitors suffer more;
2. under the current model, adding a cover crop with positive water demand (same cash crops and climate,
   unmodelled infiltration/structure/mulch benefits excluded) never reduces the modelled deficit. Writing this test
   exposed a model inconsistency — a cover crop's ET could fall below bare-soil evaporation, silently crediting
   covers with saving water. Fixed physically: cover-crop ET ≥ bare-soil evaporation (it includes soil evaporation);
3. targeted regression: with rain halved and default priorities, alfalfa does not rise in the ranking, and its water
   component falls more than that of the lowest-demand rotation (the case that exposed the saturation bug —
   not a universal "alfalfa never gains" rule);
4. no saturation at 30 % of rain; every swap in water-score order is explained by the modelled shortfall.
The scoring formula was not changed to satisfy any test.

### Ranking-change attribution (255 settings, marginal effect of reverting one change at a time)
| Reverted change | Top-2 pair changes |
|---|---|
| feasibility checks off | 215 |
| soil relevance factors off | 42 |
| rye rotation removed | 39 |
| full-profile storage instead of the claypan limit | 19 |
Effects overlap (not additive). The feasibility rules (vetch after soybean excluded) explain most of the
245 changes versus the baseline; the corrected winter-wheat calendar is included in all post-fix runs.

---

## Phase 3 — machine learning and uncertainty

### Item 13 · Detrending leakage removed
- **Change:** `yield_model.fold_data()` fits each crop's yield trend on the training years of every fold only;
  training and test targets use that fold's trend (`evaluate_loyo`). A forward-in-time test trains only on earlier
  years (`evaluate_forward`). The Random Forest is the pre-specified model of record (not chosen by CV score).
  Seed 0; out-of-sample predictions saved to `data/processed/16_yield_model_cv_predictions.csv` and
  `16_yield_model_forward_predictions.csv`.
- **Evidence:** `tests/test_ml_leakage.py` — multiplying only the held-out year's yield by 3 leaves the fold's trend,
  all training targets and that year's prediction unchanged; saved predictions reproduce the reported MAE.

| Leave-one-year-out | Old (leaky) | Corrected |
|---|---|---|
| Random Forest MAE | 9.82 | **11.24** % points |
| Random Forest R² | 0.429 | **0.44** |
| Ridge MAE / R² | 11.94 / 0.197 | 13.06 / 0.3 |
| Baseline MAE | 13.14 | 15.42 |
| Forward-chaining 2015–25 (RF vs baseline) | – | 13.55 vs 16.54 (R² 0.198) |

| Crop | RF MAE (% pts) | RF R² | Baseline MAE | RF MAE (bu/ac) | n |
|---|---|---|---|---|---|
| corn | 9.11 | 0.487 | 12.09 | 11.6 | 14 |
| soybean | 11.9 | 0.453 | 18.27 | 4.9 | 17 |
| sorghum | 12.94 | 0.362 | 15.26 | 11.8 | 11 |

### Item 14 · 2012 drought, three separate numbers
| Crop | Observed (NASS, vs fold trend) | Held-out RF prediction | Full-sample RF estimate (in-sample, not validated) |
|---|---|---|---|
| corn | -33.9 % | -15.5 % | -29.0 % |
| soybean | -26.6 % | -18.2 % | -32.3 % |
| sorghum | -29.8 % | -15.6 % | -29.3 % |

The engine and app now quote the **observed** loss as history and the **held-out** prediction as the model check;
the full-sample estimate is labelled in-sample and used only in the what-if tab.

### Item 15 · Crop-loss provenance (`recommender.crop_loss_table`, evidence text only — not scored)
| Crop | Value used | Provenance |
|---|---|---|
| corn, soybean, sorghum | full-sample RF 2012-like estimate | Random Forest (in-sample); held-out and observed values attached |
| double-crop soybean | soybean value | proxy |
| sunflower, alfalfa | mean of corn/soybean/sorghum | proxy |
| oats | half that mean | developer assumption |
| winter wheat | min(0, hottest-quarter county average − 100) | historical observation (USDA NASS) |
| cover crops | none | not estimated |

### Item 16 · Uncertainty and limits
| Severity group (held-out) | | RF MAE | Baseline MAE | RF mean bias |
|---|---|---|---|---|
| jja_heat_days | fewest heat days | 12.06 | 16.95 | -4.8 |
| jja_heat_days | middle | 10.77 | 11.34 | -0.7 |
| jja_heat_days | most heat days | 10.89 | 17.97 | +6.1 |
| gs_water_balance_mm | driest | 9.16 | 16.97 | +6.0 |
| gs_water_balance_mm | middle | 11.19 | 15.82 | -7.3 |
| gs_water_balance_mm | wettest | 13.38 | 13.47 | +1.8 |

- Poor years (observed < 85 %, n = 8): RF over-predicts by +17.5 points on average;
  good years (> 110 %, n = 13): under-predicts by -15.8 points. Predictions shrink toward normal.
- Year-bootstrap of held-out errors (exploratory, not a prediction interval): MAE gain over baseline
  4.18 points (2.5–97.5 %: [0.75, 7.48]; gain in 99 % of resamples).
- Held-out residual 10th–90th percentile: [-17.5, 18.8] points (coverage for future years not validated).
- `what_if()` now returns `provenance`, `out_of_training_range` and `warnings` (a Random Forest cannot extrapolate);
  the app's what-if tab shows them with the 2012 observed / held-out / in-sample table.
- **Recommendations changed by the ML corrections: none** (0 / 255; the RF is not a scoring input —
  `tests/test_scenario_provenance.py::test_random_forest_not_used_in_scoring`).

### Near-tie flag (engine side of item 20)
Each strategy now carries `near_tie`, `near_tie_with`, `strongest`, `weakest` and `change_vs_current`; a notice
is added when the two alternatives differ by < 0.02 (presentation heuristic). Default pair: 0.775 vs 0.769 → near-tie.

---

## Phase 4A — traceability, sensitivity, reproducibility, footprint

### Item 17 · Parameter registry
- **Change:** `scripts/build_parameter_registry.py` → `fieldshift/engine/parameter_registry.csv`: every crop trait and
  engine coefficient with value, unit, value type (literature / literature_range / expert_estimate /
  regional_practice / assumption), source, range, and an "OUTSIDE published range" flag.
  Counts: 70 expert estimates, 44 assumptions, 26 literature, 14 literature ranges, 10 regional practice.
  **Traceability is not validation:** the 70 expert estimates and 44 assumptions remain unvalidated.
- **Tests:** `tests/test_parameter_registry.py` (complete, sourced, ranges respected or flagged, assumptions not
  labelled literature).
- **Winter wheat root depth (team decision):** 1.2 m was below the FAO-56 Table 22 range (1.5–1.8 m, the same
  "maximum effective rooting depth" definition the model uses). Changed to **1.5 m, labelled a literature reference
  value**. The soil limit stays separate: effective depth = min(crop depth, inferred claypan limit).

  | Wheat depth | Effective TAW (claypan-limited) | Wheat ETa/ETc | Shortfall wheat rotations (mm/yr) | Default pair | Top-2 changes vs 1.2 m |
  |---|---|---|---|---|---|
  | 1.2 m | 88 mm | 0.965 | 66 / 74 | wheat+vetch, alfalfa | – |
  | 1.5 m (used) | 100 mm | 0.965 | 66 / 74 | wheat+vetch, alfalfa | 5 / 255 |
  | 1.8 m | 113 mm | 0.965 | 66 / 74 | wheat+vetch, alfalfa | 3 / 255 vs 1.5 m |

  Winter wheat is almost unstressed (it grows in the low-ET season), so depth barely affects water; the small
  ranking changes come through the root-depth term of the soil-health score.

### Gap 16 · Ranking sensitivity — `python scripts/sensitivity.py` → `reports/ranking_sensitivity.json`
300 draws (seed 0): literature ranges, ±0.15 for expert estimates and market (assumption), fixed weights 1.5–2.5 / 0.5–1.5;
the NASA water balance is re-run each draw. Share of draws with the same two suggestions: default 79 %, water-first 79 %,
**market-first 42 % (unstable)**, soil & erosion-first 100 %. Frequencies = stability under these assumptions, not
real-world success probabilities.

### Item 24 · Reproducibility
- `fieldshift/manifest.py` writes `reports/run_manifest.json` on every pipeline run: SHA-256 and size of every raw file,
  source URL and (approximate) acquisition date, engine-table checksums, Python / platform / package versions, settings
  and random seeds. `manifest.verify()` reports any raw file that changed.
- `requirements-lock-sandbox.txt`: exact versions of the environment where the 144 tests were run (Python 3.13).
  **Still needed:** `pip3 freeze > requirements-lock-mac.txt` on the Mac (Python 3.14) — the two environments are
  recorded separately; neither guarantees the other.
- **Tests:** `tests/test_reproducibility.py` (checksums, change detection, deterministic engine, model and sensitivity).

### Item 11 · Spatial and temporal footprint
`config.FOOTPRINTS` + table in `docs/DATA_SOURCES.md`: footprint, sampling, and what each dataset can / cannot say
about the field; temporal harmonisation rules written out (UTC days, MODIS midpoint, ECOSTRESS local time and matched
days, `_n_obs` counts, no gap filling, overlapping periods only). Tests check every dataset is covered.

---

## Phase 4B — farmer-facing application

### Items 18, 19, 20, 21 · Interface
- **18 Market potential:** the slider is "💰 Market potential" with help text "NOT income: prices and costs are not
  modelled"; method text, table and cards use the new name; the engine key is `market_potential`.
- **19 Four farm-situation controls** (sidebar, keys `c_irrigation`, `c_water_limit`, `c_interseed`, `c_forage`, all
  default off) passed to `recommend(constraints=…)` exactly as in the contract sent to Sakina.
- **20 Near-ties and instability:** header says "Close call" when the two alternatives differ by < 0.02 and shows the
  engine's notices; a "Sensitive result" warning appears when the farmer's dominant priority matches a profile whose
  suggested pair was stable in < 60 % of the 300 sensitivity runs (market-first: 42 %).
- **21 Cards:** each card shows overall score with change vs current, a close-call tag, the feasibility badge
  (✅ / ⚠️ / ⛔), strongest and weakest criterion, rotation, bare months and NASA water shortfall; the expander holds
  feasibility issues, evidence, benefits, gaps and risks. The cards work with 0, 1 or 2 alternatives. The field-cover
  calendar now uses the same timeline as the water model (fall-sown wheat in the right year). The ranked table lists
  all 7 rotations with feasibility. The Data tab shows the footprint table and the new 7-step method. A
  "Known limitations" expander shows the engine's limitations (water-model label, missing data, stale data).
- **Item 16 display:** the what-if tab shows the RF warnings and the 2012 observed / held-out / in-sample table.

### Item 23 · App tests
- `tests/test_app.py` (8 tests, Streamlit `AppTest`): app runs; displayed scores equal engine output; near-tie shown;
  no "Income" label; four controls exist; interseeding → conditional vetch rotations; water limit with zero
  alternatives does not crash; market-first shows the sensitivity warning; what-if shows model limits.
- **Status:** skipped in the build sandbox (Streamlit not installed); **must be run on the Mac**. In the sandbox the
  app was executed end-to-end with stand-in Streamlit/Plotly modules for 6 control combinations without errors.

### Mac run of Phase 4B (Python 3.14, pandas 3.1.1, Streamlit 1.67)
- Result: 144 engine/data tests passed; the 8 app tests failed with `FileNotFoundError` because `AppTest.from_file`
  resolves a relative path against the test file (`tests/app/...`). Fixed: the test uses an absolute path.
- pandas 3.1 deprecation warnings (`dayofyear`) fixed to `day_of_year` in `validation.py` and `validate_water_balance.py`.
- **Re-run on the Mac with the fix (folder "FINAL 3", 14 Nov 2026 22:33):** pipeline complete; **152 passed** in 30.6 s —
  the 144 engine/data tests plus all 8 Streamlit `AppTest` tests (app runs; displayed scores match the engine; near-tie
  shown; "Market potential" label; four controls; interseeding → conditional vetch rotations; water limit with zero
  alternatives; market-first sensitivity warning; what-if model limits). `requirements-lock-mac.txt` generated on the Mac.
- `requirements-lock-mac.txt` (Python 3.14, Streamlit 1.67, pandas 3.1.1, numpy 2.5.4, scikit-learn 1.9.1) added — the
  tested Mac environment. `requirements-lock-sandbox.txt` stays as the build-sandbox record.
- Visual check (screenshot, Rotation strategies tab): header "Close call", near-tie and exclusion notices, cards with
  score, change vs current, feasibility badge, strongest/weakest — all as specified. Small fix: the near-tie notice
  repeated the header, so it is now a caption with the exact difference.


---

## Phase 5 — final investigations, validation materials, documentation

### Items 8–9 · Experimental runoff sensitivity (team decision: research setting only)
- **Change:** optional SCS Curve Number runoff in `water_balance.simulate(runoff=…)`; rain is split into runoff and
  infiltration before it enters storage. **Production scoring keeps `runoff=None`** (test
  `test_production_scoring_has_no_runoff`). Curve numbers from USDA NRCS TR-55 Table 2-2b (AMC II); the field's
  hydrologic soil group is not in our SSURGO export, so HSG C and D are both tested. Cover class per day: row crop,
  close-seeded (wheat, alfalfa, covers) or bare. Water accounting test: rain = runoff + ETa + drainage + ΔS to 1e-6 mm.
- `python scripts/runoff_sensitivity.py` → `reports/runoff_sensitivity.json` (observed ECOSTRESS ET/ET0 = 0.52):

| Scenario | CN row/close/bare | Runoff mm/yr (share) | Modelled ET/ET0 on ECOSTRESS days | Mean storage mm | Shortfall current / sorghum–wheat (mm/yr) | r SMAP | r yield corn/soy/sorghum | Top-2 changes (of 255) |
|---|---|---|---|---|---|---|---|---|
| none (production) | – | 0 (0 %) | 0.71 | 93 | 103 / 66 | 0.60 | 0.78 / 0.76 / 0.69 | 0 |
| HSG C, good condition | 82/81/88 | 128 (14 %) | 0.62 | 88 | 125 / 84 | 0.62 | 0.75 / 0.73 / 0.75 | 4 |
| HSG D, good condition | 85/85/90 | 166 (18 %) | 0.59 | 86 | 135 / 94 | 0.62 | 0.73 / 0.72 / 0.77 | 14 |
| HSG D, poor condition | 91/89/94 | 286 (32 %) | 0.49 | 80 | 181 / 134 | 0.60 | 0.69 / 0.68 / 0.84 | 16 |

- **Interpretation:** plausible runoff (14–18 % of rain for HSG C/D in good condition) lowers modelled ET/ET0 from
  0.71 to 0.59–0.62 — part, not all, of the gap. Only the "poor condition" scenario (32 % of rain) reaches ~0.49, and it
  worsens the corn and soybean yield correlations. Runoff is therefore a **plausible partial explanation, not an
  established cause**; a closer ECOSTRESS match is not validation. Rankings are robust: the default pair is unchanged in
  every scenario and at most 16 / 255 priority settings change.
- **Status of items 8–9:** complete as **investigations**; the ECOSTRESS discrepancy remains a documented, unresolved
  limitation. Other candidate causes (seasonal-average Kc, ECOSTRESS sampling and 70 m pixel mix, irrigated fields in
  county yields, the inferred claypan rooting limit) are listed in `docs/METHODOLOGY.md`.
- **Finding for the team:** the USDA Official Series Description describes Wymore as "very deep, moderately well drained".
  The alfalfa drainage check is triggered by slow subsoil Ksat; extension guides accept moderately well drained soils
  for alfalfa. The check is left as *conditional* (verify drainage) pending team review — not changed unilaterally.

### Item 22 · External validation
- `docs/templates/literature_comparison_table.md`: 14 agronomic claims compared with published research and
  extension guidance — 9 agree, 4 partly, 1 not tested; two of the strongest sources are long-term K-State studies
  near Manhattan, KS (rotation × tillage since 1974; cover crops and sediment loss). No source contradicted the
  direction of a rule; magnitudes and conditions to review: vetch timing in Kansas, alfalfa drainage, crop calendars.
- `docs/templates/agronomist_blind_review_form.md`: rotation feasibility, planting/termination windows, soil
  suitability, water-use assumptions, regional reasonableness, two ranking questions, nine assumption checks; tick box
  separating **independent expert validation** from **internal peer review**.
- **Status: independent expert review PENDING** (open limitation). Literature agreement checks rule directions; it does
  not validate the 0–1 expert scores or the weights.

### Item 25 · Final application and documentation
- README rewritten (v2.0.0): findings, default recommendation with near-tie, how it works, reliability table,
  quick start, limitations. METHODOLOGY sections 5–10 rewritten (feasibility, water balance with checks and runoff
  experiment, scoring with overlap and sensitivity, leakage-free yield model, validation status). DATA_DICTIONARY,
  TEAM_GUIDE and DATA_SOURCES updated; the out-of-date banners and the Part-2 guide removed.
- `tests/test_docs_consistency.py` checks that the numbers in README / METHODOLOGY equal the current reports and
  engine output (yield-model metrics, 2012 numbers, ECOSTRESS / water-balance values, sensitivity share, default scores).
- Clean rebuild from raw data + full test run → `reports/test_report.md` (sandbox: 154 passed, app tests skipped;
  Mac: to be re-run for the final 162).

---

## Final status of the 25 items (engineering vs remaining scientific limitations)

| # | Item | Status | Remaining limitation |
|---|---|---|---|
| 1 | Invalid farmer inputs | done | – |
| 2 | Units and ranges | done | only POWER declares units; others range-checked; IMERG attribution to confirm |
| 3 | Drought saturation | done | – |
| 4 | Planting / harvest feasibility | done | month granularity; some calendars "regional practice" |
| 5 | pH and drainage | done | drainage inferred from Ksat (Wymore officially moderately well drained — review) |
| 6 | No infeasible recommendations | done | herbicide carry-over, equipment not modelled |
| 7 | NASA data in scoring | done | modest influence on totals (documented, not inflated) |
| 8 | Water-balance validation | done as investigation | exploratory model; correlations are supporting evidence only |
| 9 | ECOSTRESS vs storage | done as investigation | gap 0.71 vs 0.52 unresolved; runoff a plausible partial cause |
| 10 | Soil in scoring | done | relevance anchors are assumptions |
| 11 | Spatial / temporal harmonisation | done | point sampling; no field polygon |
| 12 | Missing / stale data | done | date-based freshness only |
| 13 | ML leakage | done | – |
| 14 | Drought scenario labels | done | – |
| 15 | Crop-loss provenance | done | proxies for 3 crops |
| 16 | ML uncertainty | done | ~20 seasons; no calibrated prediction intervals |
| 17 | Traits and coefficients | done (traceable) | 70 expert estimates, 44 assumptions unvalidated |
| 18 | Market potential (not income) | done | no prices or costs |
| 19 | Farmer constraints | done (verified on Mac) | – |
| 20 | Near-ties and instability | done | 0.02 threshold is a display heuristic |
| 21 | Trade-off cards | done (verified on Mac) | – |
| 22 | External validation | partly | **independent expert review pending** |
| 23 | Tests | done | final Mac re-run for the 162-test count |
| 24 | Reproducibility | done | lock files record two environments, neither guarantees the other |
| 25 | Final app and docs | done | final Mac re-run |

### Final Mac run (folder "FINAL 5", 14 Nov 2026 23:00)
- **161 passed, 1 failed.** The failure: `test_docs_consistency::test_yield_model_numbers` — the Random Forest
  held-out MAE is **11.3** on macOS (Python 3.14, numpy 2.5.4) vs **11.24** on Linux (Python 3.13, numpy 2.5.3), with
  the same seed and scikit-learn 1.9.1. Tree building with tied split candidates and floating-point differences
  between builds can change the second decimal. This is a genuine cross-platform reproducibility limit, not a
  regression: the documentation now states both values and the test allows ±0.1 point (±0.02 for R²).
- Reproducibility statement: identical inputs, code and seeds reproduce results exactly **on the same platform**;
  across platforms the Random-Forest metrics can differ in the second decimal. The NASA water balance, feasibility and
  rankings are deterministic (no randomness) and matched on both machines (same default recommendation).
