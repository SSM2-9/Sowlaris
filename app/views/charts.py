"""Ekram's charts (same data, same logic) restyled to the Sowlaris palette. Pure functions: data in, Plotly figure out."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from core.data import MONTHS
from core.engine import C, CANDIDATES, SCORE_LABELS, timeline

# Colour rule 60/30/10: cream ground (60%), greens (30%), ochre accent (10%). A rotation keeps its colour whatever its rank.
CAT = ["#3F5A3A", "#D2A441", "#8FA97C", "#5F7F4F", "#E6CF8F", "#6E8B62", "#B9C99A", "#8A6A4A"]
BARE, COVER, CROP = "#EFE6CC", "#B9C99A", "#3F5A3A"
ROT_COLOR = {k: CAT[i] for i, k in enumerate(CANDIDATES)}
TEXT = "#43402F"


def style(fig, height=340):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=36, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Open Sans, sans-serif", color=TEXT, size=13),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None), hoverlabel=dict(font_size=13))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(120,110,80,0.15)", zeroline=False)
    return fig


def moisture_trend(series: pd.DataFrame):
    fig = go.Figure(go.Scatter(x=series.index, y=series.iloc[:, 0], mode="lines+markers", line=dict(color=CAT[0], width=3),
                               marker=dict(size=8), hovertemplate="%{x}: %{y:.3f} m3/m3<extra></extra>"))
    fig.update_layout(yaxis_title="m3 water per m3 soil", showlegend=False)
    return style(fig, 260)


def rain_vs_demand(master):
    m = master.groupby("month")[["rain_gpm_imerg_mm", "et0_hargreaves_mm"]].mean().reset_index()
    m["Month"] = [MONTHS[i - 1] for i in m.month]
    fig = go.Figure()
    fig.add_bar(x=m.Month, y=m.rain_gpm_imerg_mm, name="Rain (NASA GPM IMERG)", marker_color=CAT[3], hovertemplate="%{x}: %{y:.0f} mm rain<extra></extra>")
    fig.add_bar(x=m.Month, y=m.et0_hargreaves_mm, name="Crop water demand ET0 (NASA POWER)", marker_color=CAT[1], hovertemplate="%{x}: %{y:.0f} mm demand<extra></extra>")
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.08, yaxis_title="mm per month")
    fig.update_traces(marker_line_width=0)
    return style(fig)


def hot_days(yearly):
    fig = go.Figure(go.Bar(x=yearly.year, y=yearly.heat_stress_day, marker_color=CAT[4], showlegend=False, hovertemplate="%{x}: %{y} hot days<extra></extra>"))
    for yr in (2012, 2023):
        fig.add_annotation(x=yr, y=int(yearly.loc[yearly.year == yr, "heat_stress_day"].iloc[0]), text=f"{yr}<br>drought", showarrow=False, yshift=22, font_size=11)
    fig.update_layout(yaxis_title="days")
    return style(fig)


def bare_months(bare):
    fig = go.Figure(go.Bar(x=bare.year, y=bare.bare_months_scaled_to_12, marker_color=CAT[2], showlegend=False, customdata=bare.crop_grown.fillna("none"),
                           hovertemplate="%{x}: %{y:.1f} bare months | %{customdata}<extra></extra>"))
    fig.add_vrect(x0=2004.5, x1=2007.5, fillcolor=BARE, opacity=0.5, line_width=0, annotation_text="pasture", annotation_position="top left")
    fig.update_layout(yaxis_title="months / year", yaxis_range=[0, 12])
    return style(fig)


def ndvi_year(clim):
    fig = go.Figure()
    fig.add_scatter(x=[MONTHS[i - 1] for i in clim.month], y=clim.ndvi_mean, mode="lines+markers", line=dict(color=CAT[0], width=3),
                    marker=dict(size=8), hovertemplate="%{x}: NDVI %{y:.2f}<extra></extra>")
    fig.add_hline(y=C.NDVI_BARE, line_dash="dot", line_color="#7A7561", annotation_text="bare-soil threshold 0.30", annotation_position="bottom right")
    fig.update_layout(yaxis_title="NDVI", yaxis_range=[0, 1], showlegend=False)
    return style(fig)


def smap_by_month(master):
    sm = master.dropna(subset=["smap_soil_moisture_m3m3"])
    fig = go.Figure()
    for i, yr in enumerate([2018, 2021, 2023, 2024]):
        s = sm[sm.year == yr]
        fig.add_scatter(x=[MONTHS[m - 1] for m in s.month], y=s.smap_soil_moisture_m3m3, mode="lines", name=str(yr), line=dict(color=CAT[i], width=2),
                        hovertemplate=f"{yr} %{{x}}: %{{y:.3f}} m3/m3<extra></extra>")
    avg = sm.groupby("month").smap_soil_moisture_m3m3.mean()
    fig.add_scatter(x=[MONTHS[m - 1] for m in avg.index], y=avg.values, mode="lines", name="2015-2025 average", line=dict(color="#7A7561", width=3, dash="dot"))
    fig.update_layout(yaxis_title="m3/m3")
    return style(fig)


def eco_scatter(master):
    e = master.dropna(subset=["eco_et_mm_day"])
    mx = float(max(e.et0_mm_day.max(), e.eco_et_mm_day.max())) + 0.5
    fig = go.Figure()
    fig.add_scatter(x=e.et0_mm_day, y=e.eco_et_mm_day, mode="markers", name="Monthly median", marker=dict(color=CAT[0], size=9, line=dict(color="white", width=1)),
                    customdata=e[["year", "month"]], hovertemplate="%{customdata[0]}-%{customdata[1]:02d}: ET %{y:.1f} vs ET0 %{x:.1f} mm/day<extra></extra>")
    fig.add_scatter(x=[0, mx], y=[0, mx], mode="lines", name="Use = demand (no stress)", line=dict(color="#7A7561", dash="dot"), hoverinfo="skip")
    fig.update_layout(xaxis_title="Demand ET0 (mm/day)", yaxis_title="Actual crop water use ET (mm/day)")
    return style(fig)


def risk_heatmap(hm, choice):
    sub = hm[hm.label == choice].pivot(index="year", columns="month", values="value").reindex(columns=range(1, 13))
    var = hm[hm.label == choice].variable.iloc[0]
    if var == "water_balance_mm":
        lim = float(sub.abs().max().max())
        scale, zmin, zmax, zmid = [[0, CAT[1]], [0.5, "#F7F1DF"], [1, CAT[3]]], -lim, lim, 0
    else:
        hue = {"heat_stress_days": CAT[4], "frost_days": CAT[3], "heavy_rain_days": CAT[6], "ndvi": CAT[0], "smap_soil_moisture_m3m3": CAT[5]}[var]
        scale, zmin, zmax, zmid = [[0, "#F7F3E6"], [1, hue]], float(sub.min().min()), float(sub.max().max()), None
    fig = go.Figure(go.Heatmap(z=sub.values, x=MONTHS, y=sub.index, colorscale=scale, zmin=zmin, zmax=zmax, zmid=zmid, xgap=2, ygap=2,
                               colorbar=dict(title="", thickness=12), hovertemplate="%{y} %{x}: %{z:.2f}<extra></extra>"))
    fig.update_yaxes(autorange="reversed", dtick=2)
    return style(fig, 520), var


def score_compare(strategies):
    rows = [{"Score": lab, "Option": s["name"], "Value": round(100 * s["scores"][k])} for s in strategies for k, lab in SCORE_LABELS.items()]
    fig = px.bar(pd.DataFrame(rows), x="Value", y="Score", color="Option", orientation="h", barmode="group", text="Value",
                 color_discrete_map={s["name"]: ROT_COLOR[s["id"]] for s in strategies}, category_orders={"Score": list(SCORE_LABELS.values())})
    fig.update_traces(textposition="outside", marker_line_width=0, cliponaxis=False, hovertemplate="%{y}: %{x}<extra>%{fullData.name}</extra>")
    fig.update_layout(xaxis_range=[0, 110], xaxis_title=None, yaxis_title=None, bargap=0.3)
    return style(fig, 470)


def cover_timeline(strategies, traits):
    z, text, ylab = [], [], []
    for s in strategies:
        for i, row in enumerate(timeline(CANDIDATES[s["id"]], traits), 1):
            z.append([0 if c is None else (1 if traits.loc[c, "role"] == "cover" else 2) for c in row])
            text.append(["Bare soil" if c is None else traits.loc[c, "label"] for c in row])
            ylab.append(f"{s['name'][:36]} - yr {i}")
    fig = go.Figure(go.Heatmap(z=z, x=MONTHS, y=ylab, text=text, xgap=2, ygap=2, showscale=False, zmin=0, zmax=2,
                               colorscale=[[0, BARE], [0.33, BARE], [0.34, COVER], [0.66, COVER], [0.67, CROP], [1, CROP]],
                               hovertemplate="%{y} | %{x}: %{text}<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    return style(fig, 60 + 28 * len(ylab))


def what_if_bar(res):
    wdf = pd.DataFrame({"Crop": ["Corn", "Soybean", "Grain sorghum"], "Change": [res["corn"], res["soybean"], res["sorghum"]]})
    fig = go.Figure(go.Bar(x=wdf.Change, y=wdf.Crop, orientation="h", marker_color=CAT[0], text=[f"{v:+.0f}%" for v in wdf.Change],
                           textposition="outside", cliponaxis=False, hovertemplate="%{y}: %{x:+.1f}% vs a normal summer<extra></extra>"))
    fig.update_layout(xaxis_range=[min(-40, wdf.Change.min() - 8), 15], showlegend=False, xaxis_title="Predicted yield change vs a normal summer (%)")
    fig.add_vline(x=0, line_width=1, line_color="#7A7561")
    return style(fig, 260)


def importance(ym):
    imp = pd.Series(ym["feature_importance"]).sort_values()
    fig = go.Figure(go.Bar(x=imp.values, y=imp.index, orientation="h", marker_color=CAT[0], text=[f"{v:.0%}" for v in imp.values],
                           textposition="outside", cliponaxis=False, hovertemplate="%{y}: %{x:.0%}<extra></extra>"))
    fig.update_layout(xaxis_range=[0, float(imp.max()) * 1.3], xaxis_tickformat=".0%", showlegend=False)
    return style(fig, 240)


def pred_vs_actual(pr):
    fig = px.scatter(pr, x="yield_pct_of_normal", y="predicted_pct_of_normal", color="crop", color_discrete_sequence=CAT, hover_data=["year"],
                     labels={"yield_pct_of_normal": "Actual (% of normal)", "predicted_pct_of_normal": "Predicted (% of normal)"})
    fig.add_shape(type="line", x0=60, y0=60, x1=130, y1=130, line=dict(color="#7A7561", dash="dot"))
    return style(fig, 380)
