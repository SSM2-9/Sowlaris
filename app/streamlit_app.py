"""Sowlaris entry point. Run from the project root:  streamlit run app/streamlit_app.py
Handles page config, styling, the remember-me cookie, and routing between the two pages."""
import datetime as dt
import streamlit as st
import extra_streamlit_components as stx

st.set_page_config(page_title="Sowlaris", page_icon=None, layout="wide", initial_sidebar_state="collapsed")

from core import auth, styles
from views import login, dashboard

auth.init()
styles.inject()
with st.container(key="cookie_host"):
    cookies = stx.CookieManager(key="sowlaris_cookies")
TOKEN = "sowlaris_token"

# Restore a remembered user (cookie holds a random token; only its hash is stored in the database).
if "user" not in st.session_state:
    token = cookies.get(TOKEN)
    user = auth.user_from_token(token) if token else None
    if user:
        st.session_state.user = user

if st.session_state.get("user"):
    st.session_state.user = auth.get_user(st.session_state.user["id"]) or None
if st.session_state.get("user"):
    dashboard.render(cookies, TOKEN)
else:
    login.render(cookies, TOKEN)
