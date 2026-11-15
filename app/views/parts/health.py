"""Section 2: field health. Four headline numbers, the first three alerts, and the rain-versus-demand chart."""
import streamlit as st

from core import data
from core.styles import html, img_uri
from views import charts
from views.parts.ui import head, jargon


def render(d, farm, master):
    head("thermo", "Field health and vulnerability", f"What NASA satellites and USDA records show for the demonstration farm: {farm['location']}.")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Summer water shortfall", f"{-farm['gs_water_balance_mm']:.0f} mm", help="May-Sep crop water demand (ET0, NASA POWER) minus rain (NASA GPM IMERG), 2005-2025 mean")
    m2.metric("Crop water use vs demand", f"{100 * farm['eco_et_to_et0_jul_aug']:.0f}%", help="Jul-Aug actual evapotranspiration (NASA ECOSTRESS) divided by reference demand ET0. Below about 80% means water-limited.")
    m3.metric("Bare months a year", f"{farm['observed_bare_months_since_2015']:.1f}", f"from {farm['observed_bare_months_2005_2007']:.1f} in 2005-07", delta_color="inverse", help="Months with NASA MODIS NDVI below 0.30")
    m4.metric("Subsoil clay", f"{farm['subsoil_max_clay_pct']:.0f}%", help="Dense clay layer means slow drainage (USDA SSURGO)")
    a, b = st.columns([1, 1.4], gap="large")
    with a:
        for kind, title, text in data.trend_alerts(farm)[:3]:
            html(f'<div class="alert {kind}"><b>{title}.</b> {jargon(text)}</div>')
        sat = img_uri("satellite", 900)
        if sat:
            html(f'<div class="side-photo" style="background-image:url({sat})"></div><div class="photo-cap">Farmland as seen from space</div>')
    with b:
        st.markdown("**Rain vs crop water demand, by month (2005-2025 average)**")
        st.plotly_chart(charts.rain_vs_demand(master), width="stretch")
        st.caption("Demand taller than rain means crops need more water than falls as rain.")
