"""Shared helpers for the dashboard parts: headings, jargon tooltips, score bars, strategy cards and the map.
Presentation only. Every number comes from core.engine / core.data."""
import re

import folium
import streamlit as st
from geopy.geocoders import Nominatim

from core import data, engine
from core.styles import GLOSSARY, html, icon, img_uri, term
from views import charts

DEFAULT = dict(lat=data.FARM["lat"], lon=data.FARM["lon"], place="Demonstration farm, Riley County, Kansas",
               w_water=3, w_market=3, w_soil=3, w_erosion=3,
               irrigation=False, water_limit=False, interseed=False, forage=False)


def head(ic, title, sub):
    html(f'<div class="sec-head">{icon(ic, 26)}<h2>{title}</h2></div><p class="sec-sub">{sub}</p>')


def jargon(text):
    return re.sub(r"\{([^}]+)\}", lambda m: term(m.group(1)) if m.group(1) in GLOSSARY else m.group(1), text)


def geocode(q):
    try:
        loc = Nominatim(user_agent="sowlaris-hackathon").geocode(q, timeout=8)
        return (loc.latitude, loc.longitude, loc.address.split(",")[0]) if loc else None
    except Exception:
        return None


def build_map(cfg):
    """Pin plus one toggleable circle per satellite product, drawn at its real footprint around the farm that has data."""
    f = data.FARM
    m = folium.Map(location=[cfg["lat"], cfg["lon"]], zoom_start=10, tiles="OpenStreetMap", control_scale=True)
    for name, radius, colour, show in data.SATELLITE_LAYERS:
        g = folium.FeatureGroup(name=name, show=show)
        folium.Circle([f["lat"], f["lon"]], radius=radius, color=colour, weight=2, fill=True, fill_opacity=.18, tooltip=name).add_to(g)
        g.add_to(m)
    folium.Marker([f["lat"], f["lon"]], tooltip="Demonstration farm (NASA data)", icon=folium.Icon(color="green", icon="leaf")).add_to(m)
    if data.km_from_farm(cfg["lat"], cfg["lon"]) > 1:
        folium.Marker([cfg["lat"], cfg["lon"]], tooltip="Your pin", icon=folium.Icon(color="orange", icon="map-marker")).add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    return m


def bar(label, val):
    """val is 0-100 (0 = poor, 100 = excellent)."""
    return (f'<div class="score"><div class="lbl"><span>{label}</span><span>{val}/100</span></div>'
            f'<div class="bar"><i style="width:{val}%"></i></div></div>')


def bullets(items):
    st.markdown("\n".join(f"- {x}" for x in items) if items else "- None recorded")


def strategy_card(s, r):
    cur = s["id"] == "current_corn_soy"
    tag = "Your current rotation (baseline)" if cur else f"Suggestion {s['rank_among_eligible']}"
    feas = s["feasibility"]["status"]
    pills = (f'<span class="pill {"" if feas == "feasible" else "o"}">{engine.FEASIBILITY[feas]}</span>'
             + ('<span class="pill o">Close call</span>' if s.get("near_tie") else ""))
    bars = "".join(bar(lab, round(100 * s["scores"][k])) for k, lab in engine.SCORE_LABELS.items())
    years = "".join(f"<div>Year {i}: <b>{m}</b>" + (f" then <i>{a}</i>" if a else "") + "</div>" for i, (m, a) in enumerate(s["rotation"], 1))
    delta = "" if cur else f" ({100 * s['change_vs_current']['total']:+.0f} vs current)"
    short = r["all_scores"][s["id"]]["_unmet_water_mm"]
    photo = img_uri("crops/" + s["rotation"][0][0].lower().split()[0], 700)
    top = f'<div class="crop-photo" style="background-image:url({photo})"></div>' if photo else ""
    colour = charts.ROT_COLOR[s["id"]]
    html(f"""<div class="card" style="border-top:5px solid {colour}">{top}
        <div style="color:var(--muted);font-size:.85rem">{tag}</div>
        <div class="strat-title">{s['name'].replace('Current: ', '')}</div>{pills}
        <div class="strat-crop" style="margin-top:10px">{years}</div>{bars}
        <div style="margin-top:12px;font-size:.92rem">Overall fit for you: <b>{100 * s['scores']['total']:.0f} / 100</b>{delta}</div>
        <div style="color:var(--muted);font-size:.85rem;margin-top:4px">Bare soil {s['bare_months_per_year']:.1f} months a year | Water shortfall {short:.0f} mm a year</div>
        <div style="color:var(--muted);font-size:.85rem">Strongest: {engine.SCORE_LABELS[s['strongest']]} | Weakest: {engine.SCORE_LABELS[s['weakest']]}</div></div>""")
