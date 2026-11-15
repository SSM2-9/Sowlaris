# Sowlaris

**NASA Space Apps Challenge 2026 Challenge: *Field Shift: Adapting Farms with NASA Data***
Team: Aarya, Aisanat, Ekram, Sakina

https://sowlaris.streamlit.app/
---
**What it does**
Sowlaris turns NASA satellite and climate data into a crop-rotation plan a farmer can understand. The farmer sets what matters most to them this season. They also answer four practical questions:
  Do I have irrigation?
  Should crop water use stay at today’s level?
  Can I plant a cover crop before harvest?
  Do I have livestock or a forage market?

Sowlaris then compares the current rotation with the best feasible alternatives. Each option shows its strongest and weakest point, what changes compared with today, and a clear status: feasible, conditional or infeasible. 
> Demonstration farm: dryland cropland, Riley County, Kansas, USA (39.12 °N, 96.63 °W), 2005–2025.


**How it works**

_Water_
A daily FAO-56 soil-water model is driven by NASA POWER weather and GPM IMERG precipitation from 2001 to the present. Rooting depth comes from USDA SSURGO soil layers. The model detects a dense clay layer that limits corn roots to 109 mm of available water.

_Yield risk_
Water stress is converted into yield loss using FAO-33 yield response factors. In the 2012 drought, the model shows corn suffering the most, which is what really happened.

_Scoring_
Each rotation is scored on four things:
Water risk (NASA water deficit plus the crop’s drought tolerance)
Climate fit (FAO GAEZ v4 and heat and wet-soil tolerance)
Soil health and erosion protection
Market presence
Rotations the farm can’t carry out, for example a cover crop with no time to plant it, are removed before ranking.

_Honesty checks_
We compare the water model with ECOSTRESS evapotranspiration and report the result openly. The model estimates 0.71 of the reference value, and ECOSTRESS observes 0.53.
A sensitivity test shows the same top two rotations in 79% of priority weightings.
A Random Forest yield model (error of 11.2 vs 15.4 for a simple baseline, tested leave-one-year-out with no data leakage) is used only as a diagnostic. It never changes the ranking.
Known limitations are listed inside the app.

**NASA Data Used**

SMAP soil moisture
MODIS NDVI/EVI
ECOSTRESS land surface temperature and evapotranspiration
SRTM elevation
NASA POWER and GPM IMERG

These were retrieved through NASA AppEEARS and the POWER API. They are combined with USDA CropScape, SSURGO and NASS county yields, and FAO GAEZ.

**Tools**

Python (pandas, NumPy, scikit-learn) and Streamlit. 162 automated tests check units, missing data, drought behaviour, feasibility rules, reproducibility and the app itself.

**What makes it creative**

Most farm tools give one confident answer. Sowlaris shows its uncertainty. It flags close calls instead of hiding them. It shows the farmer why each rotation wins or loses, in plain language, on a calm, farmer-first interface.

**Intended impact**

Farmers facing more frequent droughts get a rotation plan that is clear about its water risk and built on NASA data they can check themselves. This helps them adapt their fields to a changing climate with confidence.

**Use of AI**

AI assistants (Claude by Anthropic) helped write and test parts of the code and documentation. The team made the scientific decisions, reviewed every result, and owns the final work.

