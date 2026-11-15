"""'Go deeper': every chart, table and note from the old one-page dashboard, grouped into six tabs. Nothing is removed."""
import pandas as pd
import streamlit as st

from core import data, engine
from core.styles import GLOSSARY, html, icon
from views import charts
from views.parts.ui import bullets, head, jargon


def render(d, r, strategies, farm, master, alts):
    with st.expander(":material/layers: Go deeper", expanded=False):
        html('<p class="sec-sub">The evidence behind every answer above: satellites, climate risk, the rotation comparison, the climate what-if, the data and methods, and the glossary.</p>')
        t_sat, t_climate, t_rot, t_whatif, t_data, t_gloss = st.tabs(
            ["Satellite view", "Climate risk", "Rotation detail", "What-if", "Data and methods", "Glossary"])

        with t_sat:
            st.markdown("Four NASA satellites watch this field: **MODIS** (greenness), **SMAP** (soil moisture), **ECOSTRESS** (crop water use and surface temperature) and **SRTM** (elevation).")
            st.markdown("**July-August soil moisture by year (NASA SMAP)**")
            st.plotly_chart(charts.moisture_trend(data.moisture_series(master)), width="stretch")
            x, y = st.columns(2)
            with x:
                st.markdown("**Months each year with bare soil (MODIS NDVI below 0.30)**")
                st.plotly_chart(charts.bare_months(d["bare"]), width="stretch")
                st.caption(f"Winter greenness trend: {farm['trend_winter_ndvi']}.")
            with y:
                st.markdown("**Average greenness through the year (MODIS NDVI)**")
                st.plotly_chart(charts.ndvi_year(engine.csv("climatology")), width="stretch")
            x, y = st.columns(2)
            with x:
                st.markdown("**Soil moisture by month (NASA SMAP, 2015-2025)**")
                st.plotly_chart(charts.smap_by_month(master), width="stretch")
                agree = d["analysis"]["agreement"]["smap_vs_power_surface_wetness"]["pearson_r"]
                st.caption(f"Soil dries from {farm['smap_apr_may']:.2f} to {farm['smap_jul_aug']:.2f} m3/m3 just when corn silks and soybeans fill pods. Agrees with NASA POWER soil wetness (r = {agree:.2f}).")
            with y:
                st.markdown("**Crop water use vs demand (NASA ECOSTRESS, 2018-2025)**")
                st.plotly_chart(charts.eco_scatter(master), width="stretch")
                st.caption(f"Points below the line mean crops use less water than the air demands. Summer daytime surface temperature: {farm['summer_lst_day_c']:.0f} C.")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("MODIS composites used", f"{int(master.ndvi_n_obs.sum())}")
            k2.metric("SMAP days with data", f"{int(master.smap_soil_moisture_m3m3_n_obs.sum())}")
            k3.metric("ECOSTRESS clear overpasses", f"{int(master.eco_lst_day_c_n_obs.sum())} LST | {int(master.eco_et_mm_day_n_obs.sum())} ET")
            k4.metric("Elevation (SRTM)", f"{master.elevation_m.iloc[0]:.0f} m")

        with t_climate:
            l, rr = st.columns([3, 2])
            with rr:
                st.markdown("**Hot days (35 C or more) each year**")
                st.plotly_chart(charts.hot_days(d["yearly"]), width="stretch")
                st.caption(f"Trend: {farm['trend_heat_days']}. Source: NASA POWER.")
            cdl = d["cdl"]
            st.markdown("**Crop history on this field (USDA CropScape)**")
            st.markdown(" → ".join(f"**{int(y)}** {c}" for y, c in zip(cdl.year.tail(8), cdl.crop.tail(8))))
            st.caption(f"Between harvest (October) and planting (May) the soil is bare while about {farm['offseason_rain_mm']:.0f} mm of rain falls on it (NASA GPM IMERG).")
            for kind, title, text in data.trend_alerts(farm)[3:]:
                html(f'<div class="alert {kind}"><b>{title}.</b> {jargon(text)}</div>')
            reg, rm = d["regimes"], d["analysis"]["climate_regimes"]
            st.markdown(f"**Climate regimes.** K-means clustering of the 21 growing seasons finds **{rm['k_selected']} recurring kinds of season** (best silhouette score {max(rm['silhouette_by_k'].values()):.2f}).")
            prof = pd.DataFrame(rm["profiles"]).rename(columns={"regime": "Season type", "n_years": "Seasons", "years": "Years", "gs_heat_days": "Heat days",
                "gs_water_balance_mm": "Water balance (mm)", "gs_rain_mm": "Rain May-Sep (mm)", "corn_yield": "Corn bu/ac", "soybeans_yield": "Soybean bu/ac",
                "sorghum_yield": "Sorghum bu/ac", "wheat_yield": "Wheat bu/ac"})
            st.dataframe(prof[["Season type", "Seasons", "Heat days", "Water balance (mm)", "Rain May-Sep (mm)", "Corn bu/ac", "Soybean bu/ac", "Sorghum bu/ac", "Wheat bu/ac", "Years"]], hide_index=True, width="stretch")
            st.caption("Recent seasons: " + ", ".join(f"{y} {v}" for y, v in farm["recent_regimes"].items()) + ". Yields are Riley County averages (USDA NASS) in each season type.")
            st.markdown("**Month-by-month risk map, 2005-2025**")
            hm = engine.csv("heatmaps")
            choice = st.selectbox("Show", hm.label.unique().tolist(), index=0)
            fig, var = charts.risk_heatmap(hm, choice)
            st.plotly_chart(fig, width="stretch")
            if var == "water_balance_mm":
                st.caption("Ochre means water shortage (demand above rain), blue means surplus. The driest June-August periods were 2012, 2023, 2011 and 2022.")
            st.markdown("**Long-term trends (Theil-Sen slope, Mann-Kendall test)**")
            tr = d["trends"].copy()
            tr["Trend per decade"] = tr.slope_per_decade.map(lambda v: f"{v:+.3g}") + " " + tr.unit
            tr["p-value"] = tr.p_value.map(lambda p: "< 0.001" if p < 0.001 else f"{p:.2f}")
            tr["Significant (5%)"] = tr.significant_5pct.map({True: "yes", False: "no"})
            st.dataframe(tr[["indicator", "first_year", "last_year", "mean", "Trend per decade", "p-value", "Significant (5%)"]].rename(
                columns={"indicator": "Indicator", "first_year": "From", "last_year": "To", "mean": "Average"}), hide_index=True, width="stretch")
            st.caption("Twenty-one years is short for climate trends: warming and drying signals exist but are not yet statistically confirmed. The loss of winter soil cover is.")

        with t_rot:
            st.markdown("**How the options compare (0 = poor, 100 = excellent)**")
            st.plotly_chart(charts.score_compare(strategies), width="stretch")
            st.markdown("**When is the field covered? (one rotation cycle)**")
            st.plotly_chart(charts.cover_timeline(strategies, d["traits"]), width="stretch")
            st.caption("Dark green is a crop, light green a cover crop, sand is bare soil exposed to rain and wind.")
            st.markdown(f"**All {len(engine.CANDIDATES)} rotations ranked (table)**")
            rows = []
            for k in r["ranking"]:
                sc = r["all_scores"][k]
                rows.append({"Rank": r["ranking"].index(k) + 1, "Rotation": engine.CANDIDATES[k]["name"], "Feasibility": engine.FEASIBILITY[r["feasibility"][k]["status"]],
                             "Overall": round(100 * sc["total"]), **{engine.SCORE_LABELS[x]: round(100 * sc[x]) for x in engine.SCORE_LABELS},
                             "Bare months": sc["_bare_months"], "Water shortfall (mm/yr)": sc["_unmet_water_mm"], "Crop water demand (mm/yr)": sc["_water_need_mm"]})
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

        with t_whatif:
            head("sun", "Climate what-if", "What happens to yields if summers get hotter or drier? A Random Forest trained on 21 years of NASA climate data and USDA county yields.")
            ym = d["yield_model"]
            w1, w2 = st.columns(2)
            dt_ = w1.slider("Summer temperature change (C)", 0.0, 3.0, 1.0, 0.5)
            rain_ = w2.slider("Summer rain change (%)", -40, 20, 0, 5)
            res = engine.what_if(dt_, rain_)
            st.plotly_chart(charts.what_if_bar(res), width="stretch")
            wheat_hot = ym["crop_sensitivity"]["wheat"]["avg_yield_pct_in_hottest_quarter_of_years"]
            st.success(f"Winter wheat is harvested in June, before the summer heat. In the hottest summers of 2005-2025 its county yield was {wheat_hot:.0f}% of normal, so adding wheat spreads climate risk.")
            for w_ in res.get("warnings", []):
                st.warning(w_)
            y12 = ym.get("year_2012", {})
            if y12:
                st.markdown("**How reliable is this in an extreme year? The 2012 check**")
                st.dataframe(pd.DataFrame([{"Crop": c.title(), "Observed 2012 (USDA NASS)": f"{v['observed_pct_change_vs_trend']:+.0f}%",
                                            "Model, 2012 held out": f"{v['held_out_rf_prediction_pct_change']:+.0f}%",
                                            "Model, trained incl. 2012 (in-sample)": f"{v['full_sample_rf_estimate_pct_change_vs_median_summer']:+.0f}%"} for c, v in y12.items()]), hide_index=True, width="stretch")
                st.caption("When 2012 is hidden from training the model predicts about half the real loss: it under-estimates extreme years. Use it for direction and rough size only.")
            st.caption(f"Assumptions: each +1 C adds about {engine.heat_days_per_degree():.1f} hot days (observed at this farm) and about 5% more crop water demand. Trained on 42 crop-years. This is not a validated forecast.")
            st.markdown("**Model accuracy and what drives the predictions**")
            x, y = st.columns(2)
            x.dataframe(pd.DataFrame([{"Model": k, "Average error (% of normal yield)": v["MAE_pct_points"], "R2": v["R2"]} for k, v in ym["model_comparison_leave_one_year_out"].items()]), hide_index=True, width="stretch")
            y.plotly_chart(charts.importance(ym), width="stretch")
            st.plotly_chart(charts.pred_vs_actual(engine.csv("yield_predictions")), width="stretch")

        with t_data:
            st.markdown("**Which NASA and USDA data was used**")
            st.table({"Dataset": [x[0] for x in data.DATA_LINEAGE], "Measures": [x[1] for x in data.DATA_LINEAGE],
                      "What it tells us": [x[2] for x in data.DATA_LINEAGE], "Period": [x[3] for x in data.DATA_LINEAGE]})
            st.markdown("**How the suggestions are made**")
            st.markdown("""
    1. **Clean and harmonise** all datasets to one monthly table (quality filters for every satellite product).
    2. **Diagnose the farm:** water shortfall, crop water stress, soil-moisture cycle, bare months from space, climate regimes, soil limits.
    3. **Check feasibility** of 7 rotations (planting windows, soil pH, drainage, your farm situation) before ranking.
    4. **NASA daily water balance** (GPM IMERG rain, NASA POWER ET0, SSURGO soil water) gives water shortfall and drought-year yield risk per rotation.
    5. **Score each rotation (0-100)** on water, climate fit, soil health, erosion protection, pest break and market potential (not income).
    6. **Weight by your priorities;** show your current rotation and the best feasible alternatives, with near-ties, evidence, gaps and risks.
    7. **Random Forest yield model** is a secondary check for history and the what-if only; it does not change the ranking.""")
            st.markdown("**What area does each number really represent?**")
            st.dataframe(pd.DataFrame(engine.C.FOOTPRINTS, columns=["Dataset", "Footprint", "Sampling", "Can tell us", "Cannot tell us"]), hide_index=True, width="stretch")

        with t_gloss:
            st.markdown("Hover or tap any underlined word in the cards above. Here is the full list, and exactly which data sits behind every number.")
            html("".join(f'<div class="alert soil"><b>{k.capitalize() if k != "NDVI" else k}.</b> {v}</div>' for k, v in GLOSSARY.items()))
