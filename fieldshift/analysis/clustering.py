"""
Climate-vulnerability clustering and risk heat-maps.

Because the study is a single farm, spatial K-means on one point is not
meaningful. We therefore cluster *growing seasons* (2005–2025) on their
climate signature — heat, water balance, rain, soil wetness and heavy-rain
frequency — to find the farm's recurring climate regimes ("hot-dry",
"normal", "wet", …). Each regime is linked to county yields so the app can
say how the farm fares in each kind of year.

The month × year matrices of water stress, heat, frost, heavy rain and NDVI
are exported for heat-map display.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from .. import config as C

FEATURES = ["gs_heat_days", "gs_water_balance_mm", "gs_rain_mm", "ja_root_wetness", "gs_heavy_rain_days"]


def season_features(master: pd.DataFrame) -> pd.DataFrame:
    gs = master[master.month.isin(C.GROWING_SEASON)].groupby("year")
    ja = master[master.month.isin([7, 8])].groupby("year")
    f = pd.DataFrame({
        "gs_heat_days": gs.heat_stress_days.sum(),
        "gs_water_balance_mm": gs.water_balance_mm.sum(),
        "gs_rain_mm": gs.rain_gpm_imerg_mm.sum(),
        "ja_root_wetness": ja.soil_wetness_root_0_1.mean(),
        "gs_heavy_rain_days": gs.heavy_rain_days.sum(),
        "gs_temp_c": gs.temp_mean_c.mean(),
    })
    return f.reset_index()


def name_regime(c: pd.Series, overall: pd.Series) -> str:
    hot = c.gs_heat_days > overall.gs_heat_days.mean() + 0.5 * overall.gs_heat_days.std()
    dry = c.gs_water_balance_mm < overall.gs_water_balance_mm.mean() - 0.5 * overall.gs_water_balance_mm.std()
    wet = c.gs_water_balance_mm > overall.gs_water_balance_mm.mean() + 0.5 * overall.gs_water_balance_mm.std()
    if hot and dry:
        return "Hot & dry"
    if dry:
        return "Dry"
    if wet:
        return "Wet & mild"
    if hot:
        return "Hot"
    return "Near normal"


def climate_regimes(master: pd.DataFrame, k_range=range(2, 6), seed: int = 0) -> tuple[pd.DataFrame, dict]:
    f = season_features(master)
    X = StandardScaler().fit_transform(f[FEATURES])
    scores = {}
    for k in k_range:
        lab = KMeans(n_clusters=k, n_init=50, random_state=seed).fit_predict(X)
        scores[k] = float(silhouette_score(X, lab))
    k_best = max(scores, key=scores.get)
    km = KMeans(n_clusters=k_best, n_init=50, random_state=seed).fit(X)
    f["cluster"] = km.labels_
    centers = f.groupby("cluster")[FEATURES].mean()
    names = {cl: name_regime(row, f) for cl, row in centers.iterrows()}
    # make names unique if two clusters share one
    seen = {}
    for cl in sorted(names, key=lambda c: centers.loc[c, "gs_water_balance_mm"]):
        n = names[cl]
        seen[n] = seen.get(n, 0) + 1
        if seen[n] > 1:
            names[cl] = f"{n} ({seen[n]})"
    f["regime"] = f.cluster.map(names)

    nass = pd.read_csv(C.OUT["nass_wide"])
    f = f.merge(nass[["year", "corn_yield", "soybeans_yield", "sorghum_yield", "wheat_yield"]], on="year", how="left")
    profile = (f.groupby("regime")
               .agg(years=("year", lambda s: ", ".join(map(str, s))), n_years=("year", "count"),
                    **{k: (k, "mean") for k in FEATURES + ["corn_yield", "soybeans_yield", "sorghum_yield", "wheat_yield"]})
               .round(1).reset_index())
    meta = {"k_selected": int(k_best), "silhouette_by_k": {int(k): round(v, 3) for k, v in scores.items()},
            "features": FEATURES, "profiles": profile.to_dict(orient="records")}
    return f.round(3), meta


def risk_matrices(master: pd.DataFrame) -> pd.DataFrame:
    """Long table (variable, year, month, value) for heat-maps."""
    cols = {"water_balance_mm": "Water balance (rain − ET0), mm",
            "heat_stress_days": "Heat-stress days (≥35 °C)",
            "frost_days": "Frost days (≤0 °C)",
            "heavy_rain_days": "Heavy-rain days (≥25 mm)",
            "ndvi": "Vegetation greenness (MODIS NDVI)",
            "smap_soil_moisture_m3m3": "Soil moisture (SMAP), m³/m³"}
    long = master.melt(id_vars=["year", "month"], value_vars=list(cols), var_name="variable", value_name="value")
    long["label"] = long.variable.map(cols)
    return long.dropna(subset=["value"]).reset_index(drop=True)
