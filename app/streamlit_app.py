"""Sowlaris entry point. Run from the project root:  streamlit run app/streamlit_app.py
No accounts: the first screen is the hero video, and "Continue as guest" opens the dashboard."""
import streamlit as st

st.set_page_config(page_title="Sowlaris", page_icon=None, layout="wide", initial_sidebar_state="collapsed")

from core import styles
from views import dashboard, login

styles.inject()
if st.session_state.get("guest"):
    dashboard.render()
else:
    login.render()
