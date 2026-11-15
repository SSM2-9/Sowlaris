"""
Datasets 7–10 — USDA CropScape (CDL), USDA SSURGO, FAO GAEZ v4, USDA NASS QuickStats.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config as C


# --------------------------------------------------------------------------- 7. CropScape
def build_cdl() -> pd.DataFrame:
    """Crop grown at the farm point each year (CDL web service, Albers point)."""
    cdl = pd.read_csv(C.RAW["cdl"]).sort_values("year")
    cdl["previous_crop"] = cdl.crop.shift(1)
    return cdl[["year", "lat", "lon", "cdl_code", "crop", "previous_crop"]]


# --------------------------------------------------------------------------- 8. SSURGO
def build_soil(horizons: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Horizon table (as reported) and one-row-per-map-unit summary + area-weighted field average."""
    h = pd.read_csv(C.RAW["ssurgo"]) if horizons is None else horizons.copy()
    s = h.copy()
    s["thick_in"] = s.bottom_in - s.top_in
    mid = lambda a, b: (s[a] + s[b]) / 2
    s["awc_mid"] = mid("awc_in_in_low", "awc_in_in_high")
    s["om_mid"] = mid("organic_matter_pct_low", "organic_matter_pct_high")
    s["ph_mid"] = mid("ph_low", "ph_high")
    rows = []
    for (mu, name, pct), g in s.groupby(["map_unit", "soil_name", "pct_of_field"]):
        top = g.sort_values("top_in").iloc[0]
        rows.append({
            "map_unit": mu, "soil_name": name, "pct_of_field": pct,
            "topsoil_sand_pct": top.sand_pct, "topsoil_silt_pct": top.silt_pct, "topsoil_clay_pct": top.clay_pct,
            "topsoil_organic_matter_pct": top.om_mid, "topsoil_ph": top.ph_mid,
            "topsoil_erodibility_kw": top.kw,
            "plant_available_water_in_0_79in": round(float((g.awc_mid * g.thick_in).sum()), 2),
            "min_ksat_um_s": g.ksat_um_s_low.min(), "max_clay_pct": g.clay_pct.max(),
            "t_factor": top.t_factor})
    summ = pd.DataFrame(rows)
    w = summ.pct_of_field / summ.pct_of_field.sum()
    avg = {c: round(float((summ[c] * w).sum()), 2) for c in summ.columns[3:]}
    avg.update(map_unit="FIELD_AVG", soil_name="Area-weighted field average", pct_of_field=100.0)
    summ = pd.concat([summ, pd.DataFrame([avg])], ignore_index=True)
    return h, summ


# --------------------------------------------------------------------------- 9. GAEZ
def build_gaez() -> pd.DataFrame:
    return pd.read_csv(C.RAW["gaez"]).sort_values("suitability_index_0_10000", ascending=False)


# --------------------------------------------------------------------------- 10. NASS
def build_nass() -> tuple[pd.DataFrame, pd.DataFrame]:
    q = pd.read_csv(C.RAW["nass"], dtype=str)
    q["value_num"] = pd.to_numeric(q["Value"].str.replace(",", "").str.strip(), errors="coerce")
    q["Year"] = q["Year"].astype(int)
    item = q["Data Item"]
    q["metric"] = np.select(
        [item.str.contains("ACRES HARVESTED"), item.str.contains("ACRES PLANTED"),
         item.str.contains("PRODUCTION"), item.str.contains("YIELD")],
        ["acres_harvested", "acres_planted", "production", "yield"], default="other")
    q["unit"] = item.str.extract(r"MEASURED IN (.*)$")[0].fillna("ACRES")
    q["crop_detail"] = item.str.split(" - ").str[0]
    tidy = q[q.value_num.notna()][["Year", "Commodity", "crop_detail", "metric", "unit", "value_num", "CV (%)"]]
    tidy.columns = ["year", "crop", "crop_detail", "metric", "unit", "value", "cv_pct"]
    tidy = tidy.sort_values(["year", "crop", "metric"]).reset_index(drop=True)
    # one consistent series per crop (all-practice totals; winter wheat for wheat)
    series = {"CORN": "CORN, GRAIN", "SOYBEANS": "SOYBEANS", "SORGHUM": "SORGHUM, GRAIN",
              "WHEAT": "WHEAT, WINTER", "HAY": "HAY"}
    main = tidy[(tidy.year >= C.PERIOD[0]) & tidy.crop_detail.isin(series.values())
                & tidy.metric.isin(["acres_harvested", "production", "yield"])]
    wide = main.pivot_table(index="year", columns=["crop", "metric"], values="value", aggfunc="first")
    wide.columns = [f"{c.lower()}_{m}" for c, m in wide.columns]
    wide = wide.reindex(range(C.PERIOD[0], C.PERIOD[1] + 1)).reset_index().rename(columns={"index": "year"})
    return tidy, wide


def run() -> dict:
    cdl = build_cdl()
    hz, summ = build_soil()
    gaez = build_gaez()
    tidy, wide = build_nass()
    cdl.to_csv(C.OUT["cdl"], index=False)
    hz.to_csv(C.OUT["soil_horizons"], index=False)
    summ.to_csv(C.OUT["soil_summary"], index=False)
    gaez.to_csv(C.OUT["gaez"], index=False)
    tidy.to_csv(C.OUT["nass_tidy"], index=False)
    wide.to_csv(C.OUT["nass_wide"], index=False)
    return {"cdl_years": len(cdl), "soil_map_units": len(summ) - 1, "gaez_crops": len(gaez),
            "nass_rows": len(tidy), "nass_years_wide": len(wide)}
