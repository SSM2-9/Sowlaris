"""Page 1: full-screen photo hero, then a full-height split: photo panel + sign-in form."""
import datetime as dt
import time
import urllib.parse
import streamlit as st
from core import auth
from core.styles import hero_svg, html, img_uri

LOGIN_CSS = """
html, body, .stApp, [data-testid="stMain"], section.main { scroll-behavior: smooth; }

/* ---- one type system everywhere: Roboto Slab headings, Open Sans for all interface text ---- */
.stApp label, .stApp input, .stApp textarea, .stApp button, .stApp p, .stApp li,
.stApp [data-baseweb="tab"], .stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stCaptionContainer"],
.stApp [data-testid="stAlert"], .stApp [data-baseweb="input"] { font-family: 'Open Sans', sans-serif !important; }
.stApp h1, .stApp h2, .stApp h3, .form-title { font-family: 'Roboto Slab', serif !important; }

/* ---- remove top space and the invisible cookie component ---- */
[data-testid="stAppViewContainer"] { padding-top: 0 !important; }
[data-testid="stMainBlockContainer"], .block-container { padding: 0 !important; max-width: 100% !important; }
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] { gap: 0 !important; }
.stElementContainer:has(iframe), .element-container:has(iframe) { position: absolute !important; height: 0 !important; margin: 0 !important; overflow: hidden; }

/* ---- screen 1: full-screen hero ---- */
.hero-full { position: relative; width: 100%; height: 100vh; height: 100svh; min-height: 560px; overflow: hidden;
  background-image: var(--hero-bg); background-size: cover; background-position: center; color: #FBF8EE; }
.hero-full::before { content: ""; position: absolute; inset: 0;
  background: linear-gradient(180deg, rgba(63,90,58,.30) 0%, rgba(63,90,58,.04) 30%, rgba(58,78,48,.62) 100%),
              linear-gradient(95deg, rgba(58,78,48,.42) 0%, rgba(58,78,48,0) 60%); }
.hero-brand { position: absolute; top: 34px; left: 96px; font-family: 'Roboto Slab', serif; font-size: 1.7rem; font-weight: 700; color: #FBF8EE; letter-spacing: .01em; z-index: 2; }
.hero-body { position: absolute; left: 96px; bottom: 150px; max-width: 720px; }
.hero-body { z-index: 2; }
.hero-body h1 { color: #FBF8EE !important; font-size: 3.6rem; line-height: 1.1; margin: 0; font-weight: 400 !important; }
.hero-video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; z-index: 0; }
.hero-full::before { z-index: 1; }
a.cue { z-index: 2; }
a.cue { position: absolute; left: 50%; bottom: 30px; transform: translateX(-50%); display: flex; flex-direction: column; align-items: center;
  gap: 8px; color: #FBF8EE; text-decoration: none; font-size: .9rem; letter-spacing: .02em; }
a.cue svg { animation: bob 1.9s ease-in-out infinite; }
@keyframes bob { 0%,100% { transform: translateY(0); opacity: .75; } 50% { transform: translateY(7px); opacity: 1; } }
@media (prefers-reduced-motion: reduce) { a.cue svg { animation: none; } }

/* ---- screen 2: full-height split, no card ---- */
#signin-section { height: 12px; }
div[data-testid="stHorizontalBlock"] { gap: 0 !important; }
div[data-testid="stColumn"], div[data-testid="column"] { padding: 0 !important; }
.split-photo { position: relative; height: 100vh; height: 100svh; min-height: 620px; background-image: var(--hero2-bg);
  background-size: cover; background-position: 72% center; }
.split-photo::after { content: ""; position: absolute; inset: 0;
  background: linear-gradient(0deg, rgba(58,78,48,.55) 0%, rgba(63,90,58,.14) 55%, rgba(63,90,58,.22) 100%); }
div[data-testid="stColumn"]:has(.form-anchor), div[data-testid="column"]:has(.form-anchor) { background: var(--bg-grad); }
div[data-testid="stColumn"]:has(.form-anchor) > div[data-testid="stVerticalBlock"],
div[data-testid="column"]:has(.form-anchor) > div[data-testid="stVerticalBlock"] {
  min-height: 100vh; justify-content: center; padding: 96px 112px; max-width: 680px; gap: 1rem; }
.form-title { font-size: 2.2rem; color: var(--deep); margin: 0 0 4px; font-weight: 500; line-height: 1.2; }
.form-sub { font-size: 1.05rem; color: var(--muted); margin: 0 0 18px; line-height: 1.6; }

/* ---- larger, balanced form controls ---- */
div[data-testid="stTabs"] button[data-baseweb="tab"] { font-size: 1.05rem; padding: 10px 22px; }
div[data-testid="stForm"] { border: none !important; padding: 10px 0 0 !important; background: transparent !important; }
.stTextInput label, .stCheckbox label, .stTextInput label p, .stCheckbox label p { font-size: 1rem !important; color: var(--text); }
.stTextInput input { font-size: 1.05rem; padding: 14px 16px; }
.stFormSubmitButton > button, .stButton > button { width: 100%; font-size: 1.05rem; padding: .8rem 1.3rem; }
.stFormSubmitButton > button, .stButton > button:not([kind="secondary"]) { background: var(--deep); }
.stFormSubmitButton > button:hover { background: #324A2F; }
/* the split stays side by side at every zoom level: columns never wrap, and the layout never switches */
div[data-testid="stHorizontalBlock"]:has(.form-anchor), div[data-testid="stHorizontalBlock"]:has(.split-photo) { flex-wrap: nowrap !important; }
div[data-testid="stHorizontalBlock"]:has(.form-anchor) > div[data-testid="column"], div[data-testid="stHorizontalBlock"]:has(.split-photo) > div[data-testid="column"] { min-width: 0 !important; flex: 1 1 0 !important; width: auto !important; }"""


def _background(name="hero"):
    photo = img_uri(name, 2400)
    return f"url({photo})" if photo else "url(\"data:image/svg+xml;utf8," + urllib.parse.quote(hero_svg()) + "\")"

def _poster():
    return img_uri("hero", 2400) or ""


def _start_session(cookies, token_name, user, remember):
    st.session_state.user = user
    st.session_state.just_logged_in = True
    if remember:
        token, days = auth.create_session(user["id"])
        cookies.set(token_name, token, expires_at=dt.datetime.now() + dt.timedelta(days=days), key="set_token")
    time.sleep(0.5)  # lets the browser store the cookie before the page reruns
    st.rerun()


def render(cookies, token_name):
    st.markdown(f"<style>:root{{--hero-bg:{_background('hero')};--hero2-bg:{_background('hero2')};}}{LOGIN_CSS}</style>", unsafe_allow_html=True)

    # ---------- screen 1: full-screen hero (wordmark + headline only) ----------
    chevron = ('<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#FBF8EE" stroke-width="1.8" '
               'stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>')
    html(f"""<div class="hero-full">
        <video class="hero-video" autoplay muted loop playsinline preload="auto" poster="{_poster()}">
          <source src="app/static/hero.mp4" type="video/mp4">
        </video>
        <div class="hero-brand">Sowlaris</div>
        <div class="hero-body"><h1>See what your land is telling you, season by season.</h1></div>
        <a class="cue" href="#signin-section"><span>Sign in or create an account</span>{chevron}</a></div>
        <div id="signin-section"></div>""")

    # ---------- screen 2: photo panel (left) + form (right), edge to edge ----------
    photo_col, form_col = st.columns(2, gap="small")
    with photo_col:
        html('<div class="split-photo"></div>')

    with form_col:
        html('<span class="form-anchor"></span><div class="form-title">Welcome to Sowlaris</div>'
             '<div class="form-sub">Sign in to continue with your fields, or create an account to get started.</div>')
        tab_in, tab_up, tab_forgot = st.tabs(["Sign in", "Create account", "Forgot password"])

        with tab_in:
            with st.form("signin"):
                email = st.text_input("Email", key="si_email")
                pw = st.text_input("Password", type="password", key="si_pw")
                remember = st.checkbox("Keep me signed in on this device", value=True)
                go = st.form_submit_button("Sign in")
            if go:
                u = auth.login(email, pw)
                if u:
                    _start_session(cookies, token_name, u, remember)
                else:
                    st.error("Email or password is not correct. Check both, or use Forgot password.")

        with tab_up:
            with st.form("signup"):
                name = st.text_input("Your name")
                farm = st.text_input("Farm name (optional)")
                region = st.text_input("Region or nearest town (optional)")
                email = st.text_input("Email", key="su_email")
                pw = st.text_input("Password (8 characters or more)", type="password", key="su_pw")
                go = st.form_submit_button("Create account")
            if go:
                uid, err = auth.signup(name, email, pw, farm, region)
                if err:
                    st.error(err)
                else:
                    _start_session(cookies, token_name, auth.get_user(uid), True)

        with tab_forgot:
            step = st.session_state.get("reset_step", 1)
            if step == 1:
                st.caption("Enter your email and we will send a 6-digit code.")
                with st.form("reset1"):
                    email = st.text_input("Email", key="rs_email")
                    go = st.form_submit_button("Send reset code")
                if go:
                    emailed, demo = auth.request_reset(email)
                    st.session_state.update(reset_step=2, reset_email=email, reset_demo=demo)
                    st.rerun()
            else:
                st.success("If that email has an account, a code is on its way. It stays valid for 15 minutes.")
                if st.session_state.get("reset_demo"):  # only when SMTP is not configured
                    st.info(f"Demo mode (no email server set up). Your code is {st.session_state.reset_demo}.")
                with st.form("reset2"):
                    code = st.text_input("6-digit code")
                    new = st.text_input("New password", type="password")
                    go = st.form_submit_button("Set new password")
                if go:
                    err = auth.confirm_reset(st.session_state.reset_email, code, new)
                    if err:
                        st.error(err)
                    else:
                        for k in ("reset_step", "reset_email", "reset_demo"):
                            st.session_state.pop(k, None)
                        st.success("Password updated. Go to the Sign in tab.")
                if st.button("Start over", type="secondary"):
                    st.session_state.reset_step = 1
                    st.rerun()