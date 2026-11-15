# Team Guide — who owns what, and how to explain it

Each section lists the files a team member should study, what they do, and the key numbers to
present. Run `python3 scripts/run_pipeline.py` once; every number below is reproduced by it.

---

## Ekram — Lead ML Engineer & Product Architect

**Files:** `fieldshift/models/` (yield model, water balance), `fieldshift/engine/` (recommender, feasibility),
`fieldshift/validation.py`, `fieldshift/manifest.py`, `scripts/`, overall structure of `app/streamlit_app.py`.

**NASA water balance (the main climate signal in scoring)** — daily rain (GPM IMERG) and ET0 (NASA POWER) fill and
empty a soil reservoir sized from SSURGO (limited by the claypan); crops lose yield by FAO-33 Ky when they run short.
Checked against ECOSTRESS, SMAP and county yields (r 0.69–0.78); still over-estimates ECOSTRESS water use (0.71 vs 0.52).

**Random Forest (secondary)** — leakage-free leave-one-year-out: MAE 11.2 vs 15.4 baseline, R² 0.44. With 2012 held
out it predicts about half the observed loss, so it is used only for history and the what-if tab, never for ranking.

**Recommendation engine** — `recommend(priorities, constraints)`: validate inputs → feasibility checks → six scores →
farmer-weighted total → current rotation + best feasible alternatives, with near-ties, evidence, gaps and risks.

**Architecture** — raw → validation → processing → analysis → models → engine → app; one command rebuilds everything;
162 tests; every run writes a manifest with input checksums. The full audit is in `docs/AUDIT_LOG.md`.

## Aisanat — Data Engineering & Time Series

**Files:** `fieldshift/processing/*.py`, `fieldshift/analysis/timeseries.py`.

- `power.py`: reads NASA POWER, computes FAO-56 Hargreaves ET0, water balance, GDD and heat/frost/heavy-rain days.
- `satellite.py`: quality rules — SMAP flags {0,1} (flag 0 never occurs here; explain why — METHODOLOGY §2.2), MODIS reliability {0,1}, ECOSTRESS cloud/QC/range filters and tile de-duplication.
- `harmonize.py`: joins everything into the 252-month master table.
- `timeseries.py`: climatology, Theil–Sen + Mann–Kendall trends, NDVI bare months, cross-sensor agreement.

**Key numbers:** 7 670 days with 0 missing; SMAP 2 613 days; MODIS 563/595 composites kept; ECOSTRESS 589 LST and 279 ET overpasses.
Agreement: SMAP vs POWER r = 0.64, ECOSTRESS ET vs ET0 r = 0.80, NDVI vs ET r = 0.78.
Only NDVI trends are statistically significant (winter NDVI −0.048/decade, p < 0.001).

---

## Aarya — Agronomy, Clustering & Heat Maps, Science Check

**Files:** `fieldshift/engine/crop_traits.csv`, `fieldshift/analysis/clustering.py`, METHODOLOGY §5.

- `crop_traits.csv`: 10 crops (+ `crop_requirements.csv` calendars, pH, drainage; `parameter_registry.csv` types every value) with water need, drought/heat/wet-soil tolerance, N fixing, rooting depth, months in field, pest family and risk notes — every row has a **source**.
- Rotation sequencing rules: rye after corn before soybean; vetch after soybean before a grass crop; nothing fall-sown right after sorghum.
- `clustering.py`: K-means on 21 growing seasons, k chosen by silhouette (k = 2, 0.50): **Hot & dry** (12 seasons, incl. all of 2021–2025) vs **Wet & mild** (9). Corn 130 vs 146 bu/ac; wheat does better in hot years (45 vs 40).
- Heat maps: month × year matrices for water balance, heat, frost, heavy rain, NDVI and SMAP.

**Science check list:** wheat's worst year was 2007 (April freeze); county corn includes irrigated fields; warming is a signal, not yet significant.

---

## Sakina — UI/UX & Pitch

**Files:** `app/streamlit_app.py`, `.streamlit/config.toml`.

- Six tabs: Farm today · Satellite view · Climate risk · Rotation strategies · Climate what-if · Data & methods.
- Design rules: each rotation keeps one colour everywhere; one axis per chart; hover tooltips on every chart; plain-language captions under each chart; a glossary.
- **Pitch story (3 beats):**
  1. *Problem* — NASA satellites show the field is now bare ~7 months a year, and crops get only 52 % of the water they need in July–August.
  2. *Tool* — the farmer sets priorities; Field Shift compares the current rotation with the two best alternatives, with evidence, gaps and risks.
  3. *Impact* — feasible alternatives cut bare soil from 7 to 1–1.4 months a year; water-first priorities point to sorghum–soybean–wheat, which loses the least water in the NASA water balance. Be honest about limits: near-ties, unstable market-first results, exploratory water model.
