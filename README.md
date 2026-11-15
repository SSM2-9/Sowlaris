# Field Shift — Adapting Farms with NASA Data

**NASA Space Apps Challenge 2026 · Challenge: *Field Shift: Adapting Farms with NASA Data***
Version 2.0 (post-audit) · Team: Ekram (lead ML & product architect), Aisanat (data & time series),
Aarya (agronomy & clustering), Sakina (UI/UX & pitch)

https://sowlaris.streamlit.app/

Field Shift is a **decision-support prototype** that compares crop-rotation strategies for a farm. It shows the farmer's
current rotation next to the best **feasible** alternatives for their own priorities and farm situation. Each option
comes with why it was suggested, the evidence from NASA and USDA data, the benefits, the information gaps, the
feasibility checks and the risks to review with a local agronomist. It is **not** a validated farm advisory system.

> Demonstration farm: dryland cropland, Riley County, Kansas, USA (39.12 °N, 96.63 °W), 2005–2025.

---

## 1. What the data say about the farm

| Finding | Value | Source |
|---|---|---|
| May–Sep crop water demand vs rain | ET0 769 mm vs rain 562 mm → **207 mm shortfall** | NASA POWER, GPM IMERG |
| Crop water use as a share of demand, Jul–Aug (matched days) | **0.50** → water-limited | NASA ECOSTRESS |
| Soil moisture, Apr–May → Jul–Aug | 0.256 → 0.204 m³/m³ | NASA SMAP |
| Bare-soil months per year (NDVI < 0.30) | **0.7** (2005–07, pasture) → **6.4** (since 2015, corn–soybean) | NASA MODIS, USDA CropScape |
| Winter greenness trend | −0.048 NDVI/decade, p < 0.001 (**significant**) | NASA MODIS |
| Warming | +0.86 °C/decade, p = 0.09 (**signal, not statistically significant**) | NASA POWER |
| Climate regimes (K-means, k = 2) | 12 of 21 seasons *Hot & dry*, including all of 2021–2025 | NASA POWER, GPM IMERG |
| Soil | Wymore claypan at 6–11 in (45 % clay), pH 6.1, 3 % organic matter | USDA SSURGO |
| 2012 drought, observed county yields vs trend | corn −34 %, soybean −27 %, sorghum −30 % | USDA NASS |

## 2. What the tool recommends (default: all priorities = 3, no special farm situation)

| Option | Overall fit | Status | Strongest / weakest | Notes |
|---|---|---|---|---|
| **Current:** Corn → Soybean | 70 / 100 | ✅ feasible | market potential / erosion protection | baseline, 7 bare months a year |
| Corn → Soybean → Winter wheat + hairy vetch | 78 / 100 | ✅ feasible | pest break / climate fit | **close call** with the next option |
| Alfalfa (3 yrs) → Corn → Soybean | 77 / 100 | ⚠️ conditional | erosion protection / climate fit | pH, drainage and forage-outlet checks; close call |

- The two alternatives differ by 0.007 → shown as a **near-tie**: choose on the trade-offs, not the order.
- **Excluded by feasibility:** the two rotations that put hairy vetch after soybean (vetch must be sown by
  mid-September; soybean is harvested in September–October) — unless the farmer can interseed.
- **Water first** → *Sorghum → Soybean → Winter wheat + double-crop soybean* leads in 99.7 % of 300 sensitivity runs.
- **Market first** → the result is **unstable** (same pair in only 42 % of runs); the app says so.

## 3. How it works

```
data/raw (10 NASA / USDA / FAO downloads)
 → fieldshift/validation.py      units, location, ranges, required vs optional datasets, freshness
 → fieldshift/processing/        cleaning, quality filters, monthly harmonisation (252 months × 49 columns)
 → fieldshift/analysis/          climatology, Theil–Sen / Mann–Kendall trends, NDVI bare months, K-means regimes
 → fieldshift/models/
      water_balance.py           NASA daily soil-water balance (GPM IMERG rain, POWER ET0, SSURGO storage,
                                 FAO-56 stress, FAO-33 yield response) — drives the water & drought-risk scores
      yield_model.py             Random Forest (secondary diagnostic: history and what-if only)
 → fieldshift/engine/
      feasibility.py             planting / termination windows, pH, drainage, farmer constraints
      recommender.py             6 scores → weighted by farmer priorities → current + best feasible alternatives
 → app/streamlit_app.py          6-tab app with priorities, 4 farm-situation controls, cards, warnings
```

**Scores (0–1):** water (NASA water-balance shortfall + drought tolerance) · climate fit (FAO GAEZ, heat and
wet-soil tolerance, drought-year relative yield) · soil health · erosion protection · pest break · **market potential**
(county market presence — not income; no prices or costs). Farmers weight four of them 0–5; climate fit (2) and pest
break (1) are fixed. Soil characteristics set how much drainage, erosion and organic-matter differences matter.

Seven candidate rotations: current corn–soybean; corn–soybean with rye and vetch covers; corn–soybean + rye;
sorghum–soybean + vetch; sorghum–soybean–wheat + double-crop soybean; corn–soybean–wheat + vetch; alfalfa (3 yrs)–corn–soybean.

## 4. How reliable is it?

| Component | Evidence | Limitation |
|---|---|---|
| NASA water balance | Water conserved exactly; reproduces county yield swings (r 0.78 corn, 0.76 soybean, 0.69 sorghum) and SMAP timing (r 0.60); storage limited by the claypan agrees better than the full profile | **Exploratory calibrated model.** Over-estimates ECOSTRESS crop water use (0.71 vs 0.52). Experimental runoff (TR-55 curve numbers) closes part of the gap (0.59–0.62) — a plausible partial explanation, not a validated cause |
| Random Forest yield model | Leave-one-year-out with fold-wise detrending: MAE **11.2** % points vs 15.4 baseline, R² 0.44 (11.3 on macOS — Random-Forest results differ slightly across platforms); forward-in-time 13.6 vs 16.5 | ~20 seasons; under-predicts extremes (2012 held out: corn −16 % predicted vs −34 % observed). Not used in scoring |
| Feasibility rules | 9 of 14 agronomic claims agree with published research (2 from fields near Manhattan, KS), 4 partly, 1 untested | Calendars partly "regional practice"; herbicide carry-over and equipment not modelled |
| Scores and weights | Every parameter traceable in `fieldshift/engine/parameter_registry.csv` | 70 expert estimates and 44 assumptions are **unvalidated**; independent expert review **pending** |
| Software | 162 automated tests incl. 8 Streamlit app tests (run on macOS, Python 3.14); manifest with input checksums | Single demonstration farm |

## 5. Quick start

Requires Python ≥ 3.10.

```bash
pip3 install -r requirements.txt
python3 scripts/run_pipeline.py      # validate + rebuild everything from data/raw (~30 s)
python3 -m pytest -q                 # 162 tests (app tests need Streamlit)
streamlit run app/streamlit_app.py   # http://localhost:8501
```

Optional analyses: `python3 scripts/sensitivity.py` (ranking stability, ~3 min) ·
`python3 scripts/runoff_sensitivity.py` (experimental runoff) · `python3 scripts/validate_water_balance.py`.
Exact tested environments: `requirements-lock-mac.txt` (macOS, Python 3.14) and `requirements-lock-sandbox.txt` (Linux, 3.13).

## 6. Documentation

| File | Content |
|---|---|
| `docs/METHODOLOGY.md` | Every method, threshold, assumption and limitation |
| `docs/AUDIT_LOG.md` | The 25-item audit: each change, the test that failed before, the result after, remaining limits |
| `docs/DATA_SOURCES.md` | The 10 datasets, download settings, spatial / temporal footprint |
| `docs/DATA_DICTIONARY.md` | Every output file and column |
| `docs/templates/literature_comparison_table.md` | Agronomic claims vs published research |
| `docs/templates/agronomist_blind_review_form.md` | Form for independent expert review (pending) |
| `docs/TEAM_GUIDE.md` | Which part of the code belongs to whom, and how to present it |

## 7. Limitations (read before using with a farmer)

1. One demonstration farm; datasets are point samples at very different scales (see the footprint table).
2. The water balance is exploratory: runoff and irrigation are not modelled in production; the claypan rooting limit is inferred.
3. Expert scores, weights and some crop calendars are unvalidated assumptions; the top-two pair changes in up to 58 % of sensitivity runs for some farmer profiles.
4. "Market potential" is not income: no prices, costs, contracts or yields.
5. The Random Forest under-estimates extreme years and is a secondary diagnostic.
6. Independent agronomist review is pending; herbicide carry-over, equipment and labour are not checked.
7. **Field Shift supports decisions — it does not make them. Review every suggestion with the farmer and a local agronomist.**

## 8. Data acknowledgement
NASA POWER (NASA LaRC), SMAP (NASA/NSIDC DAAC), GPM IMERG (NASA GSFC), MODIS, ECOSTRESS and SRTM (NASA LP DAAC via
AppEEARS), USDA NASS CropScape and QuickStats, USDA NRCS Web Soil Survey, FAO/IIASA GAEZ v4. See `docs/DATA_SOURCES.md`.
# Sowlaris
