"""Page 1: full-screen hero video with one button: Continue as guest."""
import urllib.parse

import streamlit as st
from core.styles import hero_svg, html, img_uri

HERO_CSS = """
/* ---- one screen, no scrolling, no Streamlit spacing ---- */
html, body, .stApp, [data-testid="stMain"], section.main { overflow: hidden !important; }
[data-testid="stAppViewContainer"] { padding-top: 0 !important; }
[data-testid="stMainBlockContainer"], .block-container { padding: 0 !important; max-width: 100% !important; }
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] { gap: 0 !important; }
.stApp h1 { font-family: 'Roboto Slab', serif !important; }

/* ---- full-screen hero ---- */
.hero-full { position: relative; width: 100%; height: 100vh; height: 100svh; min-height: 560px; overflow: hidden;
  background-image: var(--hero-bg); background-size: cover; background-position: center; color: #FBF8EE; }
.hero-video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; z-index: 0; }
.hero-full::before { content: ""; position: absolute; inset: 0; z-index: 1;
  background: linear-gradient(180deg, rgba(63,90,58,.30) 0%, rgba(63,90,58,.04) 30%, rgba(58,78,48,.62) 100%),
              linear-gradient(95deg, rgba(58,78,48,.42) 0%, rgba(58,78,48,0) 60%); }
.hero-brand { position: absolute; top: 34px; left: 96px; z-index: 2; font-family: 'Roboto Slab', serif; font-size: 1.7rem;
  font-weight: 700; color: #FBF8EE; letter-spacing: .01em; }
.hero-body { position: absolute; left: 96px; bottom: 170px; max-width: 720px; z-index: 2; }
.hero-body h1 { color: #FBF8EE !important; font-size: 3.6rem; line-height: 1.1; margin: 0; font-weight: 400 !important; }

/* ---- the Continue as guest button: a Streamlit button, floated over the video ---- */
.st-key-guest_cta { position: fixed; left: 96px; bottom: 84px; z-index: 5; width: auto !important; }
.st-key-guest_cta button { background: rgba(251,248,238,.94) !important; color: #3F5A3A !important; border: none !important;
  border-radius: 999px !important; padding: .95rem 2.1rem !important; font-family: 'Open Sans', sans-serif !important;
  font-size: 1.08rem !important; font-weight: 600 !important; letter-spacing: .01em;
  box-shadow: 0 12px 34px rgba(30,45,28,.30) !important; transition: transform .18s ease, box-shadow .18s ease, background .18s ease; }
.st-key-guest_cta button:hover { background: #FFFFFF !important; transform: translateY(-2px); box-shadow: 0 16px 40px rgba(30,45,28,.36) !important; }
.st-key-guest_cta button:active { transform: translateY(0); }
.st-key-guest_cta button:focus-visible { outline: 3px solid #D2A441 !important; outline-offset: 3px; }
.st-key-guest_cta button p, .st-key-guest_cta button span { color: #3F5A3A !important; }

@media (max-width: 800px) {
  .hero-brand, .hero-body { left: 28px; } .hero-body { bottom: 150px; max-width: calc(100vw - 56px); }
  .hero-body h1 { font-size: 2.2rem; } .st-key-guest_cta { left: 28px; bottom: 64px; }
}
"""


def _background():
    photo = img_uri("hero", 2400)
    return f"url({photo})" if photo else "url(\"data:image/svg+xml;utf8," + urllib.parse.quote(hero_svg()) + "\")"


def render():
    st.markdown(f"<style>:root{{--hero-bg:{_background()};}}{HERO_CSS}</style>", unsafe_allow_html=True)
    html(f"""<div class="hero-full">
        <video class="hero-video" autoplay muted loop playsinline preload="auto" poster="{img_uri('hero', 2400) or ''}">
          <source src="app/static/hero.mp4" type="video/mp4">
        </video>
        <div class="hero-brand">Sowlaris</div>
        <div class="hero-body"><h1>See what your land is telling you, season by season.</h1></div></div>""")
    with st.container(key="guest_cta"):
        if st.button("Continue as guest", key="guest_btn", icon=":material/arrow_forward:", icon_position="right"):
            st.session_state.guest = True
            st.session_state.user = {"id": 0, "name": "Guest", "guest": True}
            st.rerun()
