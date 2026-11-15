"""Page 2: the Sowlaris dashboard. Four sections on one screen, then 'Go deeper' tabs for the full evidence.
The page only lays things out: every number comes from core.engine and core.data."""
import streamlit as st
import streamlit.components.v1 as components

from core import engine
from core.styles import credits, html, icon, img_uri
from views.parts import deeper, health, rotations, setup
from views.parts.ui import DEFAULT, head


def _banner(user):
    """Welcome banner: deep green panel with the photo faintly behind it, so the white welcome text reads clearly."""
    photo = img_uri("banner", 2400)   # placeholder: put your image at app/assets/banner.jpg
    img = f"url({photo})" if photo else "linear-gradient(120deg,#3F5A3A,#5F7F4F)"
    html(f"""<style>
        .stApp:has(.top-full) .top-full {{
            position:relative; overflow:hidden; height:270px; margin:0 0 2.2rem; border-radius:26px;
            display:flex; align-items:flex-end;
            background:rgba(63,90,58,.90);
            -webkit-backdrop-filter:blur(16px) saturate(120%); backdrop-filter:blur(16px) saturate(120%);
            border:1px solid rgba(255,255,255,.35);
            box-shadow:0 14px 40px rgba(63,90,58,.22), inset 0 1px 0 rgba(255,255,255,.25); }}
        .stApp:has(.top-full) .top-full::before {{
            content:""; position:absolute; inset:0; z-index:0; pointer-events:none;
            background-image:{img}; background-size:cover; background-position:center 40%; opacity:.30; filter:blur(3px); }}
        .stApp:has(.top-full) .top-copy {{ position:relative; z-index:1; padding:0 3.2rem 2.2rem; color:#FFFFFF; }}
        .stApp:has(.top-full) .top-copy .brand {{ color:#FFFFFF; font-size:1.25rem; font-weight:700; opacity:1; }}
        .stApp:has(.top-full) .top-copy h2 {{ color:#FFFFFF !important; margin:6px 0 4px; font-size:2.6rem; font-weight:400 !important; }}
        .stApp:has(.top-full) .top-copy p {{ margin:0; color:#FFFFFF; }}
        </style>
        <div class="top-full"><div class="top-copy">
            <div class="brand">Sowlaris</div>
            <h2>Welcome to your farm dashboard</h2>
        </div></div>""")


def _dashboard(user):
    s = st.session_state
    if "setup" not in s:
        s.setup = dict(DEFAULT)      # guests: settings live only in this browser session
    cfg = s.setup

    _banner(user)
    with st.container(key="sec_setup", border=True):
        setup.render(user, cfg)                   # 1. farm setup (writes the sliders into cfg)

    r = engine.recommend(cfg["w_water"], cfg["w_market"], cfg["w_soil"], cfg["w_erosion"], cfg["irrigation"], cfg["water_limit"], cfg["interseed"], cfg["forage"])
    d = engine.data()
    farm, master, strategies = r["farm"], d["master"], r["strategies"]
    current, alts = strategies[0], strategies[1:]
    best = alts[0] if alts else None

    # each section sits in its own frosted box: heading, text, charts and tables together
    with st.container(key="sec_health", border=True):
        health.render(d, farm, master)            # 2. field health
    with st.container(key="sec_rotations", border=True):
        rotations.render(r, strategies, current, alts, best)   # 3. rotation options
    with st.container(key="sec_deeper", border=True):
        deeper.render(d, r, strategies, farm, master, alts)    # Go deeper: one collapsible section with six tabs


def _menu():
    with st.container(key="menu_corner"):
        with st.popover(":material/menu:"):
            if st.button("Back to start", key="menu_out", type="tertiary", width="stretch"):
                st.session_state.clear(); st.rerun()


def _scroll_to_top():
    """Login leaves the page scrolled down; reset to the banner after signing in."""
    components.html("""<script>
        const doc = window.parent.document;
        ['[data-testid="stMain"]', 'section.main', '[data-testid="stAppViewContainer"]'].forEach(sel => {
            const el = doc.querySelector(sel); if (el) el.scrollTop = 0; });
        window.parent.scrollTo(0, 0);
    </script>""", height=0)


def _scroll_to_top_once():
    """After login the page keeps the login screen's scroll position; jump to the top once."""
    if st.session_state.get("scrolled_top"):
        return
    st.session_state.scrolled_top = True
    components.html("""<script>
        const doc = window.parent.document;
        const main = doc.querySelector('[data-testid="stMain"]') || doc.querySelector('section.main');
        if (main) main.scrollTo(0, 0);
        window.parent.scrollTo(0, 0);
    </script>""", height=0)


def render():
    user = st.session_state.user
    _scroll_to_top_once()
    _menu()
    _dashboard(user)