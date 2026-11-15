"""Section 1: farm setup. Search and map, the four priority sliders and the farm-situation checkboxes (collapsed)."""
import re

import streamlit as st
from streamlit_folium import st_folium

from core import data, engine
from core.styles import html, icon
from views.parts.ui import DEFAULT, build_map, geocode, head


def render(user, cfg):
    s = st.session_state
    head("pin", "Farm setup", "Tell Sowlaris what matters to you this season and what your farm can do. Everything below updates as you change these.")
    c1, c2 = st.columns([1.25, 1], gap="large")
    with c1:
        q1, q2 = st.columns([3, 1])
        query = q1.text_input("Search by ZIP code, town, or coordinates", placeholder="e.g. 66502 or Manhattan, Kansas or 39.12, -96.63")
        q2.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if q2.button("Find", key="find_btn", width="stretch") and query:
            coords = re.match(r"^\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*$", query)
            found = (float(coords[1]), float(coords[2]), query) if coords else geocode(query)
            if found:
                cfg.update(lat=found[0], lon=found[1], place=found[2]); st.rerun()
            else:
                st.warning("We could not find that place. Try a nearby town or a ZIP code, or click the map to drop a pin.")
        st.caption("Or click anywhere on the map to drop your pin. The circles show how much ground each NASA satellite value covers; use the layer box on the map to switch them.")
        out = st_folium(build_map(cfg), height=360, use_container_width=True, key="field_map", returned_objects=["last_clicked"])
        click = out.get("last_clicked") if out else None
        if click and (click["lat"], click["lng"]) != s.get("last_click"):
            s.last_click = (click["lat"], click["lng"])
            cfg.update(lat=round(click["lat"], 4), lon=round(click["lng"], 4), place="Dropped pin"); st.rerun()
        html(f'<span class="pill">{icon("pin", 14)}{cfg["place"]}</span><span class="pill o">{cfg["lat"]:.3f}, {cfg["lon"]:.3f}</span>')
        km = data.km_from_farm(cfg["lat"], cfg["lon"])
        if km > 25:
            st.info(f"Your pin is about {km:,.0f} km from the one farm this version has NASA data for (Riley County, Kansas). "
                    "Everything below describes that demonstration farm, not your pin.")
            if st.button("Return to the demonstration farm"):
                cfg.update(lat=DEFAULT["lat"], lon=DEFAULT["lon"], place=DEFAULT["place"]); st.rerun()
    with c2:
        engine.data()
        rot = engine.recommend(3, 3, 3, 3)["farm"]
        html(f'<div class="alert note"><b>Current rotation</b> (USDA CropScape): {rot["current_rotation"]}, {rot["current_rotation_years"]}.</div>')
        html(f'<div style="margin:6px 0 2px">{icon("sliders", 18)}<b>What matters most this season</b></div>')
        st.caption("0 = not important, 5 = very important")
        cfg["w_water"] = st.slider("Avoid water shortage", 0, 5, cfg["w_water"], key="w_water")
        cfg["w_soil"] = st.slider("Rebuild soil health", 0, 5, cfg["w_soil"], key="w_soil")
        cfg["w_market"] = st.slider("Market potential", 0, 5, cfg["w_market"], key="w_market",
                                    help="How easily the crops sell locally (USDA NASS county crops). Not income: prices and costs are not modelled.")
        cfg["w_erosion"] = st.slider("Stop erosion", 0, 5, cfg["w_erosion"], key="w_erosion")
        with st.expander("Your farm's situation"):
            cfg["irrigation"] = st.checkbox("Irrigation available", cfg["irrigation"], key="c_irrigation", help="Drought yield risk is assumed covered by irrigation; water use still counts.")
            cfg["water_limit"] = st.checkbox("Do not use more water than my current rotation", cfg["water_limit"], key="c_water_limit")
            cfg["interseed"] = st.checkbox("I can seed cover crops before harvest (interseeding)", cfg["interseed"], key="c_interseed")
            cfg["forage"] = st.checkbox("I have livestock or a hay/forage buyer", cfg["forage"], key="c_forage")
    return cfg
