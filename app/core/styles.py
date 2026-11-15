"""Design system: palette (60/30/10), fonts, CSS, line icons, hero artwork, jargon tooltips."""
import base64, io, os
import streamlit as st

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")


@st.cache_data(show_spinner=False)
def img_uri(name, max_w=1600):
    """Return a data-URI for assets/<name> (jpg/jpeg/png/webp), resized for fast loading; None if the file is missing.
    Pass the name without extension, e.g. img_uri("hero")."""
    for ext in ("jpg", "jpeg", "png", "webp"):
        path = os.path.join(ASSETS, f"{name}.{ext}")
        if os.path.exists(path):
            try:
                from PIL import Image
                im = Image.open(path).convert("RGB")
                if im.width > max_w:
                    im = im.resize((max_w, int(im.height * max_w / im.width)))
                buf = io.BytesIO(); im.save(buf, "JPEG", quality=82)
                return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
            except Exception:
                return f"data:image/{ext};base64," + base64.b64encode(open(path, "rb").read()).decode()
    return None


def credits():
    path = os.path.join(ASSETS, "credits.txt")
    return open(path).read().strip() if os.path.exists(path) else ""

# 60% neutrals (wheat/beige)  |  30% greens  |  10% accents (ochre + soil brown)
PALETTE = dict(
    bg="#F4EFE0", panel="#FBF8EE", sand="#EBE4CF", line="#E3DAC0",
    green="#5F7F4F", green_deep="#3F5A3A", green_soft="#DCE6CF", sage="#8FA97C",
    ochre="#D2A441", ochre_soft="#F3E4BC", soil="#8A6A4A", soil_soft="#E9DCCB",
    text="#43402F", muted="#7A7561",
)

ICONS = {
    "sprout": "M7 20h10M10 20c5.5-2.5.8-6.4 3-10M9.5 9.4c1.1.8 1.8 2.2 2.3 3.7-2 .4-3.5.4-4.8-.3-1.2-.6-2.3-1.9-3-4.2 2.8-.5 4.4 0 5.5.8zM14.1 6a7 7 0 0 0-1.1 4c1.9-.1 3.3-.6 4.3-1.4 1-1 1.6-2.3 1.7-4.6-2.7.1-4 1-4.9 2z",
    "droplet": "M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z",
    "pin": "M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0zM12 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    "thermo": "M14 4v10.5a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0z",
    "layers": "M12 2 2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5",
    "shield": "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
    "user": "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
    "logout": "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
    "sun": "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4",
    "info": "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 16v-4M12 8h.01",
    "globe": "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM2 12h20M12 2a15 15 0 0 1 0 20 15 15 0 0 1 0-20z",
    "sliders": "M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6",
    "repeat": "M17 2l4 4-4 4M3 11v-1a4 4 0 0 1 4-4h14M7 22l-4-4 4-4M21 13v1a4 4 0 0 1-4 4H3",
    "alert": "M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01",
    "check": "M20 6 9 17l-5-5",
}


def icon(name, size=20, color=None):
    c = color or PALETTE["green"]
    return (f'<svg class="ic" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{c}" '
            f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="{ICONS[name]}"/></svg>')


def html(s):
    """Render HTML safely through Streamlit markdown (collapses whitespace so markdown never breaks it)."""
    st.markdown(" ".join(s.split()), unsafe_allow_html=True)


GLOSSARY = {
    "NDVI": "A satellite 'greenness' score. Higher means healthier, leafier plants.",
    "evapotranspiration": "Water leaving your field as vapour, from the soil and from plant leaves.",
    "soil moisture anomaly": "How much wetter or drier your soil is than usual for this time of year.",
    "frost risk": "The chance of freezing nights while crops are still tender.",
    "water balance": "Rain minus the water the air demands. Negative means crops lean on water stored in the soil.",
    "heat-stress day": "A day above 35 C. Corn pollination and soybean pod-fill are harmed by these.",
    "satellite vs ground data": "Satellites cover every field every few days; ground stations are precise but few. Using both gives the best picture.",
    "bare-field period": "Weeks when no crop covers the soil, so rain and wind can wash or blow it away.",
}


def term(word):
    """Underlined word with a plain-language hover tooltip."""
    return f'<span class="term" tabindex="0">{word}<span class="tip">{GLOSSARY[word]}</span></span>'


def hero_svg():
    """Original layered-field artwork for the login page."""
    furrows = "".join(
        f'<path d="M-20 {330 + i*18} Q 150 {300 + i*16} 320 {325 + i*18} T 640 {315 + i*18}" '
        f'stroke="#DCE6CF" stroke-opacity="{0.55 - i*0.07:.2f}" stroke-width="2" fill="none"/>' for i in range(6))
    return f"""<svg viewBox="0 0 600 460" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg" class="hero-art">
    <defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F3E4BC"/><stop offset="1" stop-color="#F4EFE0"/></linearGradient></defs>
    <rect width="600" height="460" fill="url(#sky)"/>
    <circle cx="440" cy="130" r="62" fill="#D2A441" fill-opacity=".35"/><circle cx="440" cy="130" r="38" fill="#D2A441" fill-opacity=".75"/>
    <path d="M0 260 Q 120 190 250 245 T 480 230 T 600 250 V460 H0Z" fill="#BFD0AE"/>
    <path d="M0 300 Q 150 235 300 285 T 600 270 V460 H0Z" fill="#8FA97C"/>
    <path d="M0 340 Q 180 290 340 330 T 600 320 V460 H0Z" fill="#5F7F4F"/>
    <path d="M0 400 Q 200 360 400 395 T 600 385 V460 H0Z" fill="#8A6A4A"/>{furrows}
    <g stroke="#3F5A3A" stroke-width="3" stroke-linecap="round" fill="none"><path d="M118 395 v-40"/><path d="M118 372 q-16 -4 -18 -20"/><path d="M118 362 q16 -4 18 -20"/>
    <path d="M168 400 v-32"/><path d="M168 382 q-13 -3 -15 -16"/><path d="M168 374 q13 -3 15 -16"/></g></svg>"""


CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;500;600&family=Roboto+Slab:wght@400;500;600&display=swap');
:root {{ --bg:{PALETTE['bg']}; --bg-grad: linear-gradient(165deg, #F7F1DF 0%, #F3EDD9 42%, #EAEDDC 74%, #DFE8D2 100%); --panel:{PALETTE['panel']}; --sand:{PALETTE['sand']}; --line:{PALETTE['line']};
 --green:{PALETTE['green']}; --deep:{PALETTE['green_deep']}; --gsoft:{PALETTE['green_soft']}; --ochre:{PALETTE['ochre']};
 --osoft:{PALETTE['ochre_soft']}; --soil:{PALETTE['soil']}; --ssoft:{PALETTE['soil_soft']}; --text:{PALETTE['text']}; --muted:{PALETTE['muted']}; }}
html, body, .stApp {{ background: var(--bg-grad) fixed no-repeat; color: var(--text); font-family: 'Open Sans', sans-serif; }}
h1, h2, h3, h4 {{ font-family: 'Roboto Slab', serif !important; color: var(--deep) !important; font-weight: 500 !important; letter-spacing: -.01em; }}
#MainMenu, footer {{ visibility: hidden; }}
.block-container {{ padding-top: 2.2rem; max-width: 1440px; }}
[data-testid="stVerticalBlock"] {{ gap: 1.5rem; }}
section.main, [data-testid="stMain"] {{ background: transparent; }}
section[data-testid="stSidebar"] {{ background: var(--sand); }}
.ic {{ vertical-align: -4px; margin-right: 8px; }}
.brand {{ font-family: 'Roboto Slab', serif; font-size: 1.5rem; color: var(--deep); font-weight: 600; }}
.card {{ background: var(--panel); border-radius: 22px; padding: 34px 38px; box-shadow: 0 10px 34px rgba(63,90,58,.08); margin-bottom: 24px; }}
[data-testid="stVerticalBlockBorderWrapper"] > div {{ padding: 6px 4px; }}
.sec-head {{ display:flex; align-items:center; gap:14px; margin: 110px 0 12px; }}
.sec-head h2 {{ margin:0; font-size:1.55rem; }}
.sec-sub {{ color: var(--muted); margin: 0 0 28px 0; max-width: none; line-height: 1.7; font-size: 1.02rem; }}
.alert {{ border-radius: 16px; padding: 16px 18px; margin-bottom: 12px; line-height: 1.6; font-size: .95rem; }}
.alert.warn {{ background: var(--osoft); }} .alert.note {{ background: var(--gsoft); }} .alert.soil {{ background: var(--ssoft); }}
.alert b {{ color: var(--deep); }}
.pill {{ display:inline-block; padding:3px 12px; border-radius:99px; font-size:.78rem; background:var(--gsoft); color:var(--deep); margin-right:6px; }}
.pill.o {{ background: var(--osoft); color: #6B5420; }}
.score {{ margin: 10px 0; }} .score .lbl {{ display:flex; justify-content:space-between; font-size:.85rem; color:var(--muted); margin-bottom:4px; }}
.bar {{ height: 9px; background: var(--sand); border-radius: 9px; overflow: hidden; }} .bar > i {{ display:block; height:100%; border-radius:9px; background: var(--sage); }}
.bar.risk > i {{ background: var(--ochre); }}
.strat-title {{ font-family:'Roboto Slab',serif; font-size:1.25rem; color:var(--deep); margin:2px 0; }}
.strat-crop {{ font-size:1.02rem; margin-bottom:10px; }}
.term {{ border-bottom: 1.5px dotted var(--soil); cursor: help; position: relative; }}
.term .tip {{ visibility:hidden; opacity:0; position:absolute; left:0; bottom:140%; width:240px; background:var(--deep); color:#F4EFE0;
  padding:10px 12px; border-radius:12px; font-size:.8rem; line-height:1.45; transition:opacity .15s; z-index:50; }}
.term:hover .tip, .term:focus .tip {{ visibility:visible; opacity:1; }}
.hero {{ position:relative; border-radius:26px; overflow:hidden; min-height:560px; background:var(--osoft); box-shadow:0 10px 34px rgba(94,86,52,.12); }}
.hero-photo {{ position:absolute; inset:0; background-size:cover; background-position:center; }}
.hero-veil {{ position:absolute; inset:0; background:linear-gradient(95deg, rgba(244,239,224,.93) 0%, rgba(244,239,224,.78) 38%, rgba(244,239,224,.12) 78%); }}
.banner {{ height:190px; border-radius:20px; background-size:cover; background-position:center 60%; margin:6px 0 4px; position:relative; overflow:hidden; box-shadow:0 6px 22px rgba(94,86,52,.10); }}
.banner::after {{ content:""; position:absolute; inset:0; background:linear-gradient(90deg, rgba(63,90,58,.35), rgba(63,90,58,0) 60%); }}
.crop-photo {{ height:130px; margin:-22px -24px 16px; border-radius:18px 18px 0 0; background-size:cover; background-position:center; }}
.side-photo {{ height:170px; border-radius:16px; background-size:cover; background-position:center; margin-top:4px; }}
.photo-cap {{ color:var(--muted); font-size:.78rem; margin:6px 2px 0; }}
.hero-art {{ position:absolute; inset:0; width:100%; height:100%; }}
.hero-copy {{ position:relative; padding:42px 40px; max-width:430px; }}
.hero-copy h1 {{ font-size:2.35rem; line-height:1.18; margin:18px 0 14px; }}
.hero-copy p {{ line-height:1.7; color:var(--text); }}
.hero-copy .chip {{ display:inline-flex; align-items:center; background:rgba(251,248,238,.85); border-radius:99px; padding:7px 14px; margin:4px 6px 0 0; font-size:.85rem; }}
.stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] > div, .stMultiSelect div[data-baseweb="select"] > div, .stTextArea textarea
 {{ background: var(--panel) !important; border: 1px solid var(--line) !important; border-radius: 12px !important; color: var(--text) !important; }}
.stButton > button, .stFormSubmitButton > button {{ background: var(--green); color:#FBF8EE; border:none; border-radius:12px; padding:.55rem 1.3rem; font-weight:600; font-family:'Open Sans',sans-serif; }}
.stButton > button:hover, .stFormSubmitButton > button:hover {{ background: var(--deep); color:#FBF8EE; }}
button[kind="secondary"] {{ background: var(--sand) !important; color: var(--deep) !important; }}
div[data-baseweb="tab-list"] {{ gap: 6px; }} button[data-baseweb="tab"] {{ border-radius: 99px; padding: 6px 16px; }}
div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {{ display:none; }}
button[data-baseweb="tab"][aria-selected="true"] {{ background: var(--gsoft); color: var(--deep); }}
.stSlider [data-baseweb="slider"] div[role="slider"] {{ background: var(--green); box-shadow:none; }}
.stSlider label {{ font-weight: 600; color: var(--deep); }}
details {{ background: var(--panel); border-radius: 14px; border: none !important; }}
.foot {{ color: var(--muted); font-size: .82rem; line-height: 1.7; margin-top: 30px; }}
@media (max-width: 800px) {{ .hero {{ min-height: 420px; }} .hero-copy {{ padding: 26px 22px; }} .hero-copy h1 {{ font-size: 1.8rem; }} }}
:root {{ --pad-x: 4rem; }}
[data-testid="stMainBlockContainer"], .block-container {{
  padding-left: var(--pad-x) !important; padding-right: var(--pad-x) !important; max-width: 100% !important; }}
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] {{ display: none !important; }}
/* ---- no Streamlit top bar: remove it and every gap above the page content ---- */
header, [data-testid="stHeader"], [data-testid="stDecoration"], [data-testid="stToolbar"], [data-testid="stAppHeader"] {{
  display: none !important; height: 0 !important; min-height: 0 !important; }}
[data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stMainBlockContainer"], .block-container {{
  padding-top: 0 !important; margin-top: 0 !important; }}
[data-testid="stAppViewContainer"] > section, [data-testid="stMain"] > div {{ padding-top: 0 !important; }}
/* ---- three-bar menu: pinned top-right, floats over the banner ---- */
.st-key-menu_corner {{ position: fixed; top: 18px; right: 28px; z-index: 1000; width: auto !important; }}
.st-key-menu_corner [data-testid="stPopover"] button {{ background: rgba(251,248,238,.92) !important; color: var(--deep) !important;
  border: none !important; border-radius: 12px !important; box-shadow: 0 2px 10px rgba(0,0,0,.12) !important; min-width: 44px; min-height: 44px; }}
/* ---- menu panel: two equal halves split by a centred divider; hover fills each half ---- */
[data-testid="stPopoverBody"] {{ background: var(--panel) !important; border-radius: 14px !important; padding: 0 !important;
  width: 200px !important; min-width: 200px !important; overflow: hidden !important; }}
[data-testid="stPopoverBody"] [data-testid="stVerticalBlock"] {{ gap: 0 !important; height: 112px; }}
[data-testid="stPopoverBody"] [data-testid="stElementContainer"]:has(button) {{ flex: 1 1 0 !important; display: flex !important; margin: 0 !important; }}
[data-testid="stPopoverBody"] [data-testid="stElementContainer"]:has(hr),
[data-testid="stPopoverBody"] [data-testid="stDivider"] {{ flex: 0 0 1px !important; height: 1px !important; margin: 0 !important; padding: 0 !important; }}
[data-testid="stPopoverBody"] hr {{ margin: 0 !important; border: none !important; border-top: 1px solid var(--line) !important; }}
[data-testid="stPopoverBody"] button {{ width: 100% !important; height: 100% !important; min-height: 0 !important; margin: 0 !important;
  background: transparent !important; color: var(--deep) !important; border: none !important; border-radius: 0 !important;
  box-shadow: none !important; padding: 0 16px !important; display: flex !important; align-items: center !important;
  justify-content: center !important; font-family: 'Open Sans', sans-serif !important; font-size: 1rem !important; }}
[data-testid="stPopoverBody"] button p {{ margin: 0 !important; line-height: 1 !important; }}
[data-testid="stPopoverBody"] button:hover {{ background: var(--sand) !important; box-shadow: 0 8px 20px rgba(0,0,0,.14) !important; }}
/* dashboard text sizes: larger and easier to read (root size is unchanged, so the login page is not affected) */
.stApp [data-testid="stMarkdownContainer"] p, .stApp [data-testid="stMarkdownContainer"] li {{ font-size: 1.12rem; line-height: 1.65; }}
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stCaptionContainer"] p {{ font-size: 1.02rem !important; }}
.stApp [data-testid="stWidgetLabel"] p, .stApp label p {{ font-size: 1.08rem !important; }}
.stApp [data-baseweb="tab"] {{ font-size: 1.18rem !important; }}
.stApp [data-testid="stExpander"] summary p {{ font-size: 1.12rem !important; }}
.stApp [data-testid="stMetricLabel"] p {{ font-size: 1.08rem !important; }}
.stApp [data-testid="stMetricValue"] {{ font-size: 2.3rem !important; }}
.stApp [data-testid="stDataFrame"], .stApp table {{ font-size: 1.02rem; }}
.stApp .stButton button p {{ font-size: 1.08rem !important; }}
.alert {{ font-size: 1.08rem !important; }}
.score .lbl {{ font-size: 1.02rem !important; }}
.pill {{ font-size: .92rem !important; }}
.strat-crop {{ font-size: 1.12rem; }}
.sec-sub {{ font-size: 1.18rem !important; }}
.sec-head h2 {{ font-size: 1.85rem !important; }}
.foot, .photo-cap {{ font-size: .98rem !important; }}
[data-testid="stPopoverBody"] button, [data-testid="stPopoverBody"] button p {{ font-size: 1.3rem !important; }}
/* ---- light glass (dashboard only; scoped with :has(.top-full), so the login page is unchanged) ----
   Design rules: text stays dark on the frosted panels (WCAG AA, 4.5:1 or better); glass sits on a calm,
   softly blurred photo; only cards, alerts, expanders and menus are glass, never the charts or the page itself;
   one blur layer per panel and a single blurred backdrop keeps scrolling smooth. */
html, body {{ background: var(--bg-grad) fixed no-repeat; }}
.stApp:has(.top-full, .app-glass) {{ background: transparent !important; }}
.stApp:has(.top-full, .app-glass)::before {{ content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
  /* soft colour light behind the glass (works with no photo); the photo is an optional extra on top */
  background:
    radial-gradient(60% 50% at 12% 18%, rgba(126,160,110,.55) 0%, rgba(126,160,110,0) 70%),
    radial-gradient(50% 45% at 88% 12%, rgba(224,165,38,.38) 0%, rgba(224,165,38,0) 70%),
    radial-gradient(70% 55% at 70% 92%, rgba(95,127,79,.42) 0%, rgba(95,127,79,0) 70%),
    radial-gradient(55% 40% at 25% 85%, rgba(232,220,170,.60) 0%, rgba(232,220,170,0) 70%),
    linear-gradient(165deg, rgba(247,241,223,.50) 0%, rgba(241,235,213,.56) 45%, rgba(230,236,216,.62) 100%),
    url('app/static/backdrop.jpg') center / cover no-repeat;
  filter: blur(9px) saturate(118%); transform: scale(1.06); }}
.stApp:has(.top-full, .app-glass) [data-testid="stMain"], .stApp:has(.top-full, .app-glass) [data-testid="stAppViewContainer"] {{ position: relative; z-index: 1; background: transparent !important; }}
.stApp:has(.top-full, .app-glass) .card,
.stApp:has(.top-full, .app-glass) .alert,
.stApp:has(.top-full, .app-glass) [data-testid="stVerticalBlockBorderWrapper"],
.stApp:has(.top-full, .app-glass) [data-testid="stExpander"],
.stApp:has(.top-full, .app-glass) [data-testid="stAlert"],
.stApp:has(.top-full, .app-glass) [data-testid="stPopoverBody"] {{
  background: linear-gradient(135deg, rgba(246,240,222,.72) 0%, rgba(236,228,204,.52) 100%) !important;
  -webkit-backdrop-filter: blur(16px) saturate(160%); backdrop-filter: blur(16px) saturate(160%);
  border: 1px solid rgba(255, 255, 255, .85) !important;
  box-shadow: 0 12px 36px rgba(63, 90, 58, .12), inset 0 1px 0 rgba(255, 255, 255, .85) !important; }}
.stApp:has(.top-full, .app-glass) [data-testid="stExpander"] {{ border-radius: 18px; }}
.stApp:has(.top-full, .app-glass) .card {{ box-shadow: 0 12px 36px rgba(63, 90, 58, .12), inset 0 1px 0 rgba(255,255,255,.85); }}
.stApp:has(.top-full, .app-glass) .alert {{ box-shadow: 0 6px 20px rgba(63, 90, 58, .08), inset 0 1px 0 rgba(255,255,255,.85); }}
.stApp:has(.top-full, .app-glass) .bar {{ background: rgba(255,255,255,.55); }}
.stApp:has(.top-full, .app-glass) .pill {{ background: rgba(255,255,255,.7); border: 1px solid rgba(255,255,255,.9); }}
/* ---- glass behind the charts, metrics, tables and text on the dashboard ----
   Charts and small text sat directly on the blurred photo and lost contrast. Each one now gets its own
   light frosted panel. Charts and metrics get a light blur; plain captions get tint only (cheaper to draw). */
.stApp:has(.top-full, .app-glass) [data-testid="stPlotlyChart"],
.stApp:has(.top-full, .app-glass) [data-testid="stDataFrame"],
.stApp:has(.top-full, .app-glass) [data-testid="stTable"],
.stApp:has(.top-full, .app-glass) [data-testid="stMetric"] {{
  background: rgba(255, 252, 244, .68);
  -webkit-backdrop-filter: blur(10px) saturate(130%); backdrop-filter: blur(10px) saturate(130%);
  border: 1px solid rgba(255, 255, 255, .80); border-radius: 18px; padding: 14px 16px; margin-bottom: 14px;
  box-shadow: 0 8px 26px rgba(63, 90, 58, .10), inset 0 1px 0 rgba(255,255,255,.85); }}
.stApp:has(.top-full, .app-glass) [data-testid="stCaptionContainer"],
.stApp:has(.top-full, .app-glass) .sec-sub {{
  background: rgba(255, 252, 244, .56); border-radius: 14px; padding: 10px 16px; margin-top: 6px; margin-bottom: 12px;
  border: 1px solid rgba(255, 255, 255, .65); display: inline-block; max-width: 100%; }}
.stApp:has(.top-full, .app-glass) .sec-sub {{ display: block; padding: 12px 18px; margin-bottom: 22px; }}
/* one frosted box per dashboard section (heading, text, charts and tables together) */
.stApp:has(.top-full, .app-glass) [class*="st-key-sec_"] {{
  background: rgba(230, 221, 196, .90) !important;
  -webkit-backdrop-filter: blur(16px) saturate(140%); backdrop-filter: blur(16px) saturate(140%);
  border: 1px solid rgba(255, 255, 255, .85) !important; border-radius: 26px !important;
  box-shadow: 0 14px 40px rgba(63, 90, 58, .12), inset 0 1px 0 rgba(255, 255, 255, .9) !important;
  padding: 30px 34px !important; margin-bottom: 2.6rem !important; }}
/* headings inside a section box sit at the top of the box, not 110px down */
.stApp:has(.top-full, .app-glass) [class*="st-key-sec_"] .sec-head {{ margin-top: 0 !important; }}
.stApp:has(.top-full, .app-glass) [class*="st-key-sec_"] > div {{ gap: 1.1rem; }}
/* one colour rule everywhere: 60% cream, 30% green, 10% ochre (sliders, buttons, charts, text) */
.stSlider [data-baseweb="slider"] div[role="slider"] {{ background: var(--deep) !important; border: 2px solid #FBF8EE !important; }}
.stSlider [data-baseweb="slider"] > div > div:first-child {{ background: var(--green) !important; }}
.stSlider [data-testid="stSliderThumbValue"] {{ color: var(--deep) !important; }}
.stSlider [data-baseweb="slider"] div[role="slider"]:focus {{ box-shadow: 0 0 0 6px rgba(210,164,65,.30) !important; }}
.stApp:has(.top-full, .app-glass) .stButton > button[kind="primary"], .stFormSubmitButton > button {{ background: var(--deep) !important; color: #FBF8EE !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background: var(--ochre) !important; }}
/* ---- 60 / 30 / 10 colour rule (dashboard and profile) ----
   60%  beige ground and panels (--bg, --panel, --sand)
   30%  sage and deep green for headings, sliders, charts and buttons (--green, --deep)
   10%  ochre for highlights and alerts (--ochre)
   Off-palette defaults (blue info boxes, red metric changes) are replaced here. Login errors stay red on purpose. */
.stApp:has(.top-full, .app-glass) [data-testid="stAlert"] {{ background: var(--sand) !important; color: var(--text) !important;
  border-left: 4px solid var(--ochre) !important; border-radius: 14px !important; }}
.stApp:has(.top-full, .app-glass) [data-testid="stAlert"] * {{ color: var(--text) !important; }}
.stApp:has(.top-full, .app-glass) [data-testid="stMetricDelta"] {{ color: var(--soil) !important; }}
.stApp:has(.top-full, .app-glass) [data-testid="stMetricDelta"] svg {{ fill: var(--soil) !important; }}
.stApp:has(.top-full, .app-glass) a {{ color: var(--green) !important; }}

/* collapsible sections: the heading row is the clickable title, styled like the section headings */
.st-key-sec_trust [data-testid="stExpander"], .st-key-sec_deeper [data-testid="stExpander"] {{
  background: transparent !important; border: none !important; box-shadow: none !important; }}
.st-key-sec_trust [data-testid="stExpander"] summary, .st-key-sec_deeper [data-testid="stExpander"] summary {{
  padding: 0 !important; cursor: pointer; }}
.st-key-sec_trust [data-testid="stExpander"] summary p, .st-key-sec_deeper [data-testid="stExpander"] summary p {{
  font-family: 'Roboto Slab', serif !important; font-size: 1.85rem !important; font-weight: 500 !important;
  color: var(--deep) !important; margin: 0; }}
.st-key-sec_trust [data-testid="stExpander"] summary svg, .st-key-sec_deeper [data-testid="stExpander"] summary svg {{
  color: var(--green) !important; fill: var(--green) !important; }}
/* Go deeper sits inside its section box with no second box: the title row and the content are transparent */
.st-key-sec_deeper [data-testid="stExpander"], .st-key-sec_deeper [data-testid="stExpander"] details,
.st-key-sec_deeper [data-testid="stExpander"] summary, .st-key-sec_deeper [data-testid="stExpanderDetails"] {{
  background: transparent !important; border: none !important; box-shadow: none !important; }}
/* no glow behind button text */
.stButton button, .stButton button p, .stFormSubmitButton button, .stFormSubmitButton button p {{
  text-shadow: none !important; box-shadow: none !important; -webkit-backdrop-filter: none !important; backdrop-filter: none !important; }}
/* the invisible cookie widget stays out of the page layout */
.st-key-cookie_host {{ position: absolute !important; height: 0 !important; width: 0 !important; overflow: hidden !important; margin: 0 !important; padding: 0 !important; }}
.st-key-find_btn button {{
  background: #FFFFFF !important; color: var(--deep) !important;
  border: 1px solid rgba(255,255,255,.95) !important; }}
.st-key-find_btn button:hover {{ background: #FBF8EE !important; }}
.st-key-find_btn button p {{ color: var(--deep) !important; }}
"""


def inject():
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
