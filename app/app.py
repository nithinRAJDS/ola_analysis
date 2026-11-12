"""
app.py — OLA Rides Analytics · black & green Streamlit app
==========================================================
A presentation-grade, 11-page analytics app built on the cleaned OLA dataset.

Pages (Prev/Next wizard; state persists in session_state)
---------------------------------------------------------
 1. Overall        — Ride Volume Over Time · Booking Status Breakdown
 2. Vehicle Type   — Top 5 Vehicle Types by Ride Distance · Avg Customer Ratings
 3. Revenue        — Revenue by Payment Method · Top 5 Customers · Distance/Day
 4. Cancellation   — Cancelled Rides Reasons (Customer) · (Driver)
 5. Ratings        — Driver Ratings · Customer Ratings · Customer vs Driver
 6. SQL Questions  — the 10 required questions, one-click run
 7. Ask the Data   — free-text NL→SQL Q&A with conversation memory
 8. Data Explorer  — filters, search, table, charts
 9. Power BI       — publish-to-web iframe with graceful fallback
10. Data Quality   — scorecard, missingness, outliers, schema
11. Audience Q&A   — 20+ curated questions, one at a time, presentation-friendly

Design
------
* Black/near-black canvas (#0B0F14) with Ola green (#92D050) accents.
* All imagery comes from the Ola-Slides.pptx deck (assets/ppt/).
* Every chart is dark-themed Plotly; every page has KPI cards + insight lines.
* Primary actions sit inline with what they act on.

Run:  streamlit run app.py
"""
from __future__ import annotations

import base64
import json
import os
import sqlite3

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from nl2sql import (
    EXAMPLE_QUESTIONS,
    SCHEMA,
    _build_metric_sql,
    answer_sentence,
    run as nl_run,
    validate_sql,
)

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "ola.db")
DATA_DIR = os.path.join(HERE, "..", "data")
SQL_RESULTS = os.path.join(DATA_DIR, "sql_results.json")
ASSETS = os.path.join(HERE, "assets")
PPT = os.path.join(ASSETS, "ppt")
VEH_DIR = os.path.join(PPT, "vehicles")
ICON_DIR = os.path.join(PPT, "icons")

st.set_page_config(
    page_title="OLA Rides Analytics",
    page_icon="🚕",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------- #
# Palette
# --------------------------------------------------------------------------- #
BG = "#0B0F14"
SURF = "#161E27"
SURF2 = "#1C2632"
GREEN = "#92D050"
TEAL = "#24CBE5"
CYAN = "#058DC7"
ORANGE = "#ED561B"
YELLOW = "#EDEF00"
TEXT = "#E6EDF3"
MUTED = "#8B9AAB"
BORDER = "rgba(146,208,80,0.16)"
SERIES = [GREEN, TEAL, CYAN, "#7BE495", "#F4B942", ORANGE, "#B48EAD"]

PAGES = [
    ("Overall", "📊"),
    ("Vehicle Type", "🚗"),
    ("Revenue", "💰"),
    ("Cancellation", "🚫"),
    ("Ratings", "⭐"),
    ("SQL Questions", "🗄️"),
    ("Ask the Data", "💬"),
    ("Data Explorer", "🔎"),
    ("Power BI", "📈"),
    ("Data Quality", "✅"),
    ("Audience Q&A", "🎤"),
]

VEH_META = {
    "Auto": ("auto.png", "3-wheeler", "Short hops, lowest fares"),
    "Bike": ("bike.png", "2-wheeler", "Fastest point-to-point"),
    "E-Bike": ("ebike.png", "electric", "Short-range electric"),
    "Mini": ("mini.png", "compact", "Everyday budget cab"),
    "Prime Sedan": ("prime_sedan.png", "sedan", "Core premium tier"),
    "Prime SUV": ("prime_suv.png", "suv", "Group & luggage"),
    "Prime Plus": ("prime_plus.png", "premium", "Top-end comfort"),
}

# --------------------------------------------------------------------------- #
# Theme CSS
# --------------------------------------------------------------------------- #
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] {{ font-family:'Inter',-apple-system,sans-serif; }}
.stApp {{
  background:
    radial-gradient(1100px 520px at 12% -8%, rgba(146,208,80,.10), transparent 62%),
    radial-gradient(900px 460px at 92% 4%, rgba(36,203,229,.08), transparent 60%),
    {BG};
  color:{TEXT};
}}
.block-container {{ padding-top:1.1rem; padding-bottom:2.2rem; max-width:1520px; }}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {{
  background:linear-gradient(180deg,#0E141B 0%,#101821 100%);
  border-right:1px solid {BORDER};
}}
[data-testid="stSidebar"] * {{ color:{TEXT}; }}
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3 {{ color:{GREEN}; }}

/* ---------- hero ---------- */
.hero {{
  position:relative; overflow:hidden; border-radius:20px; padding:26px 32px;
  background:linear-gradient(110deg,#101821 0%,#16222E 46%,#123024 100%);
  border:1px solid {BORDER};
  box-shadow:0 22px 60px rgba(0,0,0,.55), inset 0 1px 0 rgba(255,255,255,.05);
  margin-bottom:18px;
}}
.hero:before {{
  content:''; position:absolute; inset:0;
  background:radial-gradient(560px 220px at 82% 18%, rgba(146,208,80,.22), transparent 62%),
             radial-gradient(420px 200px at 96% 96%, rgba(36,203,229,.16), transparent 60%);
  pointer-events:none;
}}
.hero-inner {{ position:relative; display:flex; align-items:center; gap:24px; flex-wrap:wrap; }}
.hero-logo {{
  width:118px; height:74px; object-fit:contain; border-radius:14px;
  background:rgba(11,15,20,.55); border:1px solid rgba(146,208,80,.24);
  padding:8px; box-shadow:0 0 26px rgba(146,208,80,.20);
}}
.hero h1 {{
  margin:0; font-size:2.15rem; font-weight:800; letter-spacing:-.6px;
  background:linear-gradient(92deg,#FFFFFF 8%,{GREEN} 58%,{TEAL} 100%);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
}}
.hero p {{ margin:5px 0 0; color:{MUTED}; font-size:.94rem; max-width:820px; }}
.hero .pill {{
  display:inline-block; margin-top:10px; padding:5px 13px; border-radius:999px;
  font-size:.72rem; font-weight:600; letter-spacing:.4px; text-transform:uppercase;
  color:{GREEN}; background:rgba(146,208,80,.12); border:1px solid rgba(146,208,80,.34);
}}

/* ---------- KPI cards ---------- */
.kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(172px,1fr)); gap:12px; margin:4px 0 16px; }}
.kpi {{
  position:relative; overflow:hidden; background:linear-gradient(160deg,{SURF} 0%,{SURF2} 100%);
  border:1px solid {BORDER}; border-radius:15px; padding:15px 16px 14px;
  box-shadow:0 8px 26px rgba(0,0,0,.36); transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}}
.kpi:hover {{ transform:translateY(-3px); box-shadow:0 16px 38px rgba(0,0,0,.5),0 0 0 1px rgba(146,208,80,.32);
             border-color:rgba(146,208,80,.45); }}
.kpi:before {{ content:''; position:absolute; top:0; left:0; right:0; height:2px;
  background:linear-gradient(90deg,{GREEN},{TEAL}); opacity:.85; }}
.kpi .ic {{ font-size:1.05rem; opacity:.9; }}
.kpi .v {{ font-size:1.62rem; font-weight:800; letter-spacing:-.7px; color:#FFFFFF; margin-top:4px; line-height:1.1; }}
.kpi .l {{ font-size:.71rem; text-transform:uppercase; letter-spacing:.7px; color:{MUTED}; margin-top:5px; font-weight:600; }}
.kpi .s {{ font-size:.74rem; color:{GREEN}; margin-top:5px; font-weight:600; }}

/* ---------- section headers ---------- */
.sec {{ display:flex; align-items:center; gap:11px; margin:22px 0 11px; }}
.sec .bar {{ width:4px; height:21px; border-radius:3px; background:linear-gradient(180deg,{GREEN},{TEAL}); }}
.sec h3 {{ margin:0; font-size:1.08rem; font-weight:700; color:#fff; letter-spacing:-.2px; }}
.sec .hint {{ color:{MUTED}; font-size:.8rem; margin-left:auto; }}

/* ---------- insight line ---------- */
.insight {{
  display:flex; gap:9px; align-items:flex-start;
  background:rgba(36,203,229,.07); border-left:3px solid {TEAL};
  border-radius:0 9px 9px 0; padding:9px 13px; margin:2px 0 16px;
  font-size:.85rem; color:#CFE3F0; line-height:1.5;
}}
.insight b {{ color:{GREEN}; }}

/* ---------- answer box ---------- */
.answer {{
  background:linear-gradient(120deg,rgba(146,208,80,.13),rgba(36,203,229,.09));
  border-left:4px solid {GREEN}; border-radius:13px; padding:14px 17px; margin:10px 0;
  font-size:1.02rem; font-weight:600; color:#F4F9FF;
  box-shadow:0 6px 26px rgba(0,0,0,.34);
}}
.interpreted {{ color:{MUTED}; font-size:.84rem; margin-bottom:3px; }}
.chiprow {{ display:flex; flex-wrap:wrap; gap:7px; margin:3px 0 10px; }}
.chip {{ background:rgba(36,203,229,.11); border:1px solid rgba(36,203,229,.34); color:{TEAL};
  border-radius:999px; padding:4px 11px; font-size:.74rem; font-weight:600; }}
.chip.g {{ background:rgba(146,208,80,.11); border-color:rgba(146,208,80,.34); color:{GREEN}; }}

/* ---------- vehicle cards ---------- */
.vcard {{
  background:linear-gradient(165deg,{SURF} 0%,{SURF2} 100%);
  border:1px solid {BORDER}; border-radius:16px; padding:14px; text-align:center;
  box-shadow:0 8px 24px rgba(0,0,0,.34); transition:transform .18s, box-shadow .18s, border-color .18s;
  height:100%;
}}
.vcard:hover {{ transform:translateY(-4px); border-color:rgba(146,208,80,.5);
  box-shadow:0 18px 40px rgba(0,0,0,.5); }}
.vcard img {{ width:100%; height:92px; object-fit:contain; filter:drop-shadow(0 6px 14px rgba(146,208,80,.22)); }}
.vcard .nm {{ font-weight:700; font-size:.92rem; color:#fff; margin-top:5px; }}
.vcard .tg {{ font-size:.68rem; color:{TEAL}; text-transform:uppercase; letter-spacing:.6px; font-weight:600; }}
.vcard .mt {{ font-size:.74rem; color:{MUTED}; margin-top:6px; line-height:1.45; }}
.vcard .mt b {{ color:{GREEN}; font-weight:700; }}

/* ---------- Q&A card ---------- */
.qacard {{
  background:linear-gradient(150deg,{SURF} 0%,{SURF2} 100%);
  border:1px solid rgba(146,208,80,.28); border-radius:18px;
  padding:26px 30px; margin:6px 0 16px;
  box-shadow:0 18px 50px rgba(0,0,0,.5);
}}
.qacard .qnum {{ font-size:.72rem; letter-spacing:1.4px; text-transform:uppercase;
  color:{TEAL}; font-weight:700; }}
.qacard .qtext {{ font-size:1.42rem; font-weight:700; color:#fff; margin-top:8px; line-height:1.35; }}

/* ---------- widgets ---------- */
.stButton>button {{
  background:linear-gradient(96deg,{GREEN} 0%,#A8E063 100%); color:#08130A; font-weight:700;
  border:none; border-radius:10px; padding:.42rem .92rem; transition:all .16s ease;
  box-shadow:0 5px 18px rgba(146,208,80,.24);
}}
.stButton>button:hover {{ transform:translateY(-1px); box-shadow:0 9px 26px rgba(146,208,80,.42); color:#08130A; }}
.stButton>button:active {{ transform:translateY(0); }}
.stButton>button:disabled {{ background:#222E3A; color:#5B6B7C; box-shadow:none; }}
.stDownloadButton>button {{
  background:transparent; color:{TEAL}; border:1px solid rgba(36,203,229,.5);
  border-radius:9px; font-weight:600;
}}
.stDownloadButton>button:hover {{ background:rgba(36,203,229,.12); color:{TEAL}; border-color:{TEAL}; }}

.stTextInput input, .stTextArea textarea, .stNumberInput input {{
  background:{SURF2} !important; color:{TEXT} !important;
  border:1px solid rgba(146,208,80,.22) !important; border-radius:10px !important;
}}
.stTextInput input:focus {{ border-color:{GREEN} !important; box-shadow:0 0 0 2px rgba(146,208,80,.18) !important; }}
[data-baseweb="select"]>div {{ background:{SURF2} !important; border:1px solid rgba(146,208,80,.22) !important;
  border-radius:10px !important; color:{TEXT} !important; }}
[data-baseweb="tag"] {{ background:rgba(146,208,80,.2) !important; color:{GREEN} !important; }}

.stTabs [data-baseweb="tab-list"] {{ gap:5px; background:transparent; border-bottom:1px solid rgba(146,208,80,.14); }}
.stTabs [data-baseweb="tab"] {{
  background:transparent; color:{MUTED}; border-radius:9px 9px 0 0; padding:9px 17px;
  font-weight:600; font-size:.9rem;
}}
.stTabs [aria-selected="true"] {{ background:rgba(146,208,80,.12); color:{GREEN} !important;
  box-shadow:inset 0 -2px 0 {GREEN}; }}

[data-testid="stDataFrame"] {{ border:1px solid {BORDER}; border-radius:12px; overflow:hidden; }}
[data-testid="stExpander"] {{ background:{SURF}; border:1px solid {BORDER} !important; border-radius:11px; }}
[data-testid="stMetricValue"] {{ color:{GREEN}; }}
.stAlert {{ border-radius:11px; }}
code {{ color:{TEAL} !important; background:rgba(36,203,229,.09) !important;
  padding:1px 5px; border-radius:5px; }}
hr {{ border-color:rgba(146,208,80,.12); }}

/* page indicator */
.pagebar {{ display:flex; align-items:center; justify-content:space-between;
  gap:14px; margin-top:22px; padding-top:12px; border-top:1px solid rgba(146,208,80,.14); }}
.pageind {{ color:{MUTED}; font-size:.82rem; font-weight:600; letter-spacing:.3px; }}
.pageind b {{ color:{GREEN}; }}
.dots {{ display:flex; gap:6px; }}
.dot {{ width:7px; height:7px; border-radius:50%; background:#2A3644; }}
.dot.on {{ background:{GREEN}; box-shadow:0 0 9px rgba(146,208,80,.8); }}
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def b64(path: str) -> str:
    """Base64 data-URI for any asset file (empty string if missing)."""
    try:
        with open(path, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except OSError:
        return ""


def veh_img(name: str) -> str:
    """Data-URI for a vehicle image from the PPT assets."""
    fn = VEH_META.get(name, ("fallback.png",))[0]
    p = os.path.join(VEH_DIR, fn)
    if not os.path.exists(p):
        p = os.path.join(VEH_DIR, "fallback.png")
    return b64(p)


def hero(title: str, sub: str, pill: str) -> None:
    logo = b64(os.path.join(PPT, "ola_logo.png"))
    st.markdown(f"""
    <div class="hero"><div class="hero-inner">
      {f'<img class="hero-logo" src="{logo}"/>' if logo else '<div style="font-size:2.4rem">🚕</div>'}
      <div>
        <h1>{title}</h1>
        <p>{sub}</p>
        <span class="pill">{pill}</span>
      </div>
    </div></div>""", unsafe_allow_html=True)


def section(title: str, hint: str = "") -> None:
    st.markdown(
        f'<div class="sec"><div class="bar"></div><h3>{title}</h3>'
        f'{f"<span class=hint>{hint}</span>" if hint else ""}</div>',
        unsafe_allow_html=True)


def kpis(items: list[tuple[str, str, str, str]]) -> None:
    """items = [(icon, value, label, sub), ...]"""
    html = '<div class="kpi-grid">'
    for ic, v, l, s in items:
        html += (f'<div class="kpi"><div class="ic">{ic}</div>'
                 f'<div class="v">{v}</div><div class="l">{l}</div>'
                 f'{f"<div class=s>{s}</div>" if s else ""}</div>')
    st.markdown(html + "</div>", unsafe_allow_html=True)


def insight(text: str) -> None:
    st.markdown(f'<div class="insight">💡<div>{text}</div></div>', unsafe_allow_html=True)


def dbase(fig: go.Figure, h: int = 320) -> go.Figure:
    """Apply the dark-plotly treatment."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color=TEXT, size=12),
        height=h,
        margin=dict(l=8, r=12, t=40, b=8),
        title_font=dict(size=13, color="#FFFFFF"),
        colorway=SERIES,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10.5)),
        hoverlabel=dict(bgcolor=SURF2, font_size=11.5, bordercolor=GREEN),
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,.06)", linecolor="rgba(255,255,255,.10)",
                     zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,.06)", linecolor="rgba(255,255,255,.10)",
                     zeroline=False)
    if any(getattr(tr, "orientation", None) == "h" for tr in fig.data):
        fig.update_layout(margin=dict(l=130, r=14, t=40, b=8))
    return fig


# --------------------------------------------------------------------------- #
# Data + filters
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def load_df() -> pd.DataFrame:
    con = sqlite3.connect(DB)
    df = pd.read_sql("SELECT * FROM bookings", con)
    con.close()
    return df


@st.cache_resource(show_spinner=False, max_entries=12)
def get_con(where_sql: str) -> sqlite3.Connection:
    """Connection whose `bookings` table is shadowed by a TEMP VIEW of the
    filtered rows, so every query (engine, explorer, DAO) honours the filters."""
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, check_same_thread=False)
    if where_sql:
        con.executescript(
            f"CREATE TEMP VIEW bookings AS SELECT * FROM main.bookings WHERE {where_sql};")
    return con


def build_where(f: dict) -> str:
    c: list[str] = []
    if f.get("date"):
        c.append(f"Booking_Date BETWEEN '{f['date'][0]}' AND '{f['date'][1]}'")
    for key, col in (("vehicle", "Vehicle_Type"), ("status", "Booking_Status"),
                     ("payment", "Payment_Method"), ("tod", "Time_of_Day"),
                     ("dist", "Distance_Bucket"), ("val", "Value_Bucket")):
        vals = f.get(key) or []
        if vals:
            quoted = ",".join("'" + str(v).replace("'", "''") + "'" for v in vals)
            c.append(f"{col} IN ({quoted})")
    lo, hi = f.get("rating", (3.0, 5.0))
    if (lo, hi) != (3.0, 5.0):
        c.append(f"(Driver_Ratings IS NULL OR Driver_Ratings BETWEEN {lo} AND {hi})")
    return " AND ".join(c)


def filter_chips(f: dict) -> str:
    chips = []
    if f.get("date"):
        chips.append(f"📅 {f['date'][0]} → {f['date'][1]}")
    names = {"vehicle": "🚗", "status": "📌", "payment": "💳",
             "tod": "🕒", "dist": "📏", "val": "💵"}
    for k, ic in names.items():
        for v in (f.get(k) or []):
            chips.append(f"{ic} {v}")
    lo, hi = f.get("rating", (3.0, 5.0))
    if (lo, hi) != (3.0, 5.0):
        chips.append(f"⭐ {lo}–{hi}")
    if not chips:
        return '<div class="chiprow"><span class="chip g">All data · no filters</span></div>'
    return ('<div class="chiprow">' +
            "".join(f'<span class="chip">{c}</span>' for c in chips) + "</div>")


def q(con, sql: str) -> pd.DataFrame:
    return pd.read_sql(sql, con)


# --------------------------------------------------------------------------- #
# Session state
# --------------------------------------------------------------------------- #
if "page" not in st.session_state:
    st.session_state.page = 0
if "history" not in st.session_state:
    st.session_state.history = []
if "qa_idx" not in st.session_state:
    st.session_state.qa_idx = 0
if "qa_show" not in st.session_state:
    st.session_state.qa_show = False
if "sql_open" not in st.session_state:
    st.session_state.sql_open = {}


def goto(i: int) -> None:
    st.session_state.page = max(0, min(len(PAGES) - 1, i))


# --------------------------------------------------------------------------- #
# Sidebar — navigation + filters
# --------------------------------------------------------------------------- #
df_all = load_df()

with st.sidebar:
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">'
        f'<img src="{b64(os.path.join(PPT, "ola_logo_square.png"))}" '
        f'style="width:38px;height:38px;object-fit:contain"/></div>',
        unsafe_allow_html=True)
    st.markdown("### OLA Rides Analytics")
    st.caption("July 2024 · Bengaluru · 103,024 bookings")

    st.markdown("---")
    st.markdown("**Navigate**")
    labels = [f"{i+1}. {n}" for i, (n, _) in enumerate(PAGES)]
    sel = st.radio("Page", labels, index=st.session_state.page,
                   label_visibility="collapsed", key="nav_radio")
    new_idx = labels.index(sel)
    if new_idx != st.session_state.page:
        st.session_state.page = new_idx
        st.rerun()

    st.markdown("---")
    st.markdown("**Filters**")
    dmin, dmax = df_all["Booking_Date"].min(), df_all["Booking_Date"].max()
    date_r = st.date_input("Date range", value=(pd.to_datetime(dmin).date(),
                                                pd.to_datetime(dmax).date()),
                           min_value=pd.to_datetime(dmin).date(),
                           max_value=pd.to_datetime(dmax).date())
    vehicle = st.multiselect("Vehicle type", sorted(df_all["Vehicle_Type"].unique()))
    status = st.multiselect("Booking status", sorted(df_all["Booking_Status"].unique()))
    payment = st.multiselect("Payment method",
                             sorted(df_all["Payment_Method"].dropna().unique()))
    tod = st.multiselect("Time of day", sorted(df_all["Time_of_Day"].dropna().unique()))
    dist = st.multiselect("Distance bucket",
                          ["0 km", "1-5 km", "6-10 km", "11-20 km", "21-30 km", "31-50 km"])
    val = st.multiselect("Value bucket",
                         ["<250", "250-500", "500-750", "750-1000", "1000-1500", "1500+"])
    rating = st.slider("Driver rating range", 3.0, 5.0, (3.0, 5.0), 0.1)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("↺ Reset", use_container_width=True):
            for k in ("vehicle", "status", "payment", "tod", "dist", "val"):
                st.session_state[f"f_{k}"] = []
            st.rerun()
    with c2:
        st.caption("")

FILTERS = {
    "date": (str(date_r[0]), str(date_r[1])) if isinstance(date_r, tuple) and len(date_r) == 2 else None,
    "vehicle": vehicle, "status": status, "payment": payment,
    "tod": tod, "dist": dist, "val": val, "rating": rating,
}
WHERE = build_where(FILTERS)
con = get_con(WHERE)
n_rows = int(q(con, "SELECT COUNT(*) c FROM bookings").iloc[0, 0])

with st.sidebar:
    st.markdown("---")
    st.markdown(
        f'<div style="background:rgba(146,208,80,.10);border:1px solid rgba(146,208,80,.3);'
        f'border-radius:10px;padding:10px 12px;text-align:center">'
        f'<div style="font-size:1.35rem;font-weight:800;color:{GREEN}">{n_rows:,}</div>'
        f'<div style="font-size:.7rem;letter-spacing:.7px;text-transform:uppercase;'
        f'color:{MUTED};font-weight:600">rows in view</div></div>',
        unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Page 1 — Overall
# --------------------------------------------------------------------------- #
def page_overall() -> None:
    hero("Overall Performance",
         "Ride volume and booking outcomes across the full month — the health check for the marketplace.",
         "Page 1 · Overall")

    k = q(con, """
        SELECT COUNT(*) n,
               SUM(CASE WHEN Booking_Status='Success' THEN 1 ELSE 0 END) succ,
               SUM(CASE WHEN Booking_Status='Success' THEN Booking_Value ELSE 0 END) rev,
               AVG(CASE WHEN Booking_Status='Success' THEN Booking_Value END) aov,
               AVG(CASE WHEN Booking_Status='Success' THEN Ride_Distance END) dist
        FROM bookings""").iloc[0]
    kpis([
        ("🚕", f"{int(k.n):,}", "Total bookings", "July 2024"),
        ("✅", f"{100*k.succ/k.n:.1f}%", "Success rate", f"{int(k.succ):,} completed"),
        ("💰", f"₹{k.rev/1e6:.2f}M", "Revenue", "successful rides"),
        ("🧾", f"₹{k.aov:,.0f}", "Avg booking value", "per successful ride"),
        ("📏", f"{k.dist:.1f} km", "Avg ride distance", "successful rides"),
    ])

    section("Ride Volume Over Time", "daily bookings vs successful")
    daily = q(con, """
        SELECT Booking_Date d,
               COUNT(*) total,
               SUM(CASE WHEN Booking_Status='Success' THEN 1 ELSE 0 END) success
        FROM bookings GROUP BY Booking_Date ORDER BY Booking_Date""")
    daily["d"] = pd.to_datetime(daily["d"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=daily["d"], y=daily["total"], name="All bookings",
                             line=dict(color=GREEN, width=2.4), fill="tozeroy",
                             fillcolor="rgba(146,208,80,.12)"))
    fig.add_trace(go.Scatter(x=daily["d"], y=daily["success"], name="Successful",
                             line=dict(color=TEAL, width=2.2)))
    fig.add_hline(y=daily["total"].mean(), line=dict(color=MUTED, width=1, dash="dash"),
                  annotation_text=f"avg {daily['total'].mean():.0f}/day",
                  annotation_font_color=MUTED)
    fig.update_layout(title="Daily ride volume — July 2024", hovermode="x unified")
    st.plotly_chart(dbase(fig, 340), use_container_width=True)
    insight(f"Volume is <b>flat</b> — daily bookings vary by only "
            f"{100*daily['total'].std()/daily['total'].mean():.1f}% around the mean. "
            f"Peak day <b>{daily.loc[daily['total'].idxmax(),'d']:%d %b}</b> "
            f"({daily['total'].max():,}), quietest "
            f"<b>{daily.loc[daily['total'].idxmin(),'d']:%d %b}</b> "
            f"({daily['total'].min():,}). No weekly seasonality to exploit.")

    section("Booking Status Breakdown", "where bookings end up")
    stt = q(con, "SELECT Booking_Status s, COUNT(*) n FROM bookings GROUP BY 1 ORDER BY 2 DESC")
    c1, c2 = st.columns([1, 1.25])
    with c1:
        fig = px.pie(stt, names="s", values="n", hole=0.55,
                     color="s", color_discrete_sequence=[GREEN, ORANGE, YELLOW, TEAL])
        fig.update_traces(textposition="outside", textinfo="percent+label",
                          textfont=dict(size=11))
        fig.update_layout(title="Share of bookings", showlegend=False)
        st.plotly_chart(dbase(fig, 330), use_container_width=True)
    with c2:
        fig = px.bar(stt.sort_values("n"), x="n", y="s", orientation="h",
                     color="s", color_discrete_sequence=[TEAL, YELLOW, ORANGE, GREEN],
                     text="n")
        fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig.update_layout(title="Bookings by status", showlegend=False)
        st.plotly_chart(dbase(fig, 330), use_container_width=True)

    fail = int(k.n - k.succ)
    insight(f"<b>{fail:,} bookings ({100*fail/k.n:.1f}%) never complete.</b> "
            f"Driver-side cancellations are the single largest leak — every recovered ride "
            f"is pure margin, since acquisition is already paid for.")


# --------------------------------------------------------------------------- #
# Page 2 — Vehicle Type
# --------------------------------------------------------------------------- #
def page_vehicle() -> None:
    hero("Vehicle Type Performance",
         "Which vehicle classes carry the network — and how customers rate them.",
         "Page 2 · Vehicle Type")

    v = q(con, """
        SELECT Vehicle_Type v, COUNT(*) n,
               AVG(CASE WHEN Booking_Status='Success' THEN Ride_Distance END) dist,
               AVG(Customer_Rating) cr,
               AVG(Driver_Ratings) dr,
               SUM(CASE WHEN Booking_Status='Success' THEN Booking_Value ELSE 0 END) rev
        FROM bookings GROUP BY 1 ORDER BY n DESC""")

    kpis([
        ("🚗", f"{len(v)}", "Vehicle types", "all active"),
        ("📏", f"{v['dist'].max():.1f} km", "Longest avg distance",
         v.loc[v['dist'].idxmax(), 'v']),
        ("⭐", f"{v['cr'].max():.2f}", "Best customer rating",
         v.loc[v['cr'].idxmax(), 'v']),
        ("💰", f"₹{v['rev'].sum()/1e6:.2f}M", "Total revenue", "all types"),
    ])

    section("Top 5 Vehicle Types by Ride Distance", "average km per successful ride")
    top5 = v.dropna(subset=["dist"]).nlargest(5, "dist").sort_values("dist")
    fig = px.bar(top5, x="dist", y="v", orientation="h", text="dist",
                 color="dist", color_continuous_scale=["#1C4A2A", GREEN])
    fig.update_traces(texttemplate="%{text:.1f} km", textposition="outside")
    fig.update_layout(title="Average ride distance by vehicle type (top 5)",
                      coloraxis_showscale=False, xaxis_title="km", yaxis_title="")
    st.plotly_chart(dbase(fig, 330), use_container_width=True)
    insight(f"<b>{top5.iloc[-1]['v']}</b> covers the longest average trip at "
            f"<b>{top5.iloc[-1]['dist']:.1f} km</b>, while "
            f"<b>{v.loc[v['dist'].idxmin(),'v']}</b> is the shortest at "
            f"{v['dist'].min():.1f} km — a 2.5× spread that should drive driver "
            f"allocation and surge design.")

    section("Average Customer Ratings by Vehicle Type", "1–5 scale, successful rides")
    fig = px.bar(v.sort_values("cr"), x="cr", y="v", orientation="h", text="cr",
                 color="cr", color_continuous_scale=["#123A46", TEAL])
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.update_layout(title="Average customer rating by vehicle type",
                      coloraxis_showscale=False, xaxis_title="rating", yaxis_title="",
                      xaxis_range=[3.8, 4.15])
    st.plotly_chart(dbase(fig, 330), use_container_width=True)
    insight(f"Ratings are <b>compressed into a 0.05-point band</b> "
            f"({v['cr'].min():.2f}–{v['cr'].max():.2f}). The rating system is not "
            f"discriminating between vehicle classes — treat it as a satisfaction floor, "
            f"not a quality ranking.")

    section("Vehicle Types", "imagery from the Ola deck")
    cols = st.columns(4)
    for i, (name, (fn, tag, desc)) in enumerate(VEH_META.items()):
        row = v[v["v"] == name]
        n = int(row["n"].iloc[0]) if len(row) else 0
        rev = float(row["rev"].iloc[0]) if len(row) else 0
        with cols[i % 4]:
            st.markdown(f"""
            <div class="vcard">
              <img src="{veh_img(name)}"/>
              <div class="nm">{name}</div>
              <div class="tg">{tag}</div>
              <div class="mt">{desc}<br/>
                <b>{n:,}</b> bookings · <b>₹{rev/1e6:.2f}M</b></div>
            </div>""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Page 3 — Revenue
# --------------------------------------------------------------------------- #
def page_revenue() -> None:
    hero("Revenue & Payments",
         "Where the money comes from — payment rails, top customers and trip-length mix.",
         "Page 3 · Revenue")

    k = q(con, """
        SELECT SUM(Booking_Value) rev, AVG(Booking_Value) aov, COUNT(*) n
        FROM bookings WHERE Booking_Status='Success'""").iloc[0]
    top1 = q(con, """
        SELECT Customer_ID c, SUM(Booking_Value) v FROM bookings
        WHERE Booking_Status='Success' GROUP BY 1 ORDER BY 2 DESC LIMIT 1""").iloc[0]
    kpis([
        ("💰", f"₹{k.rev/1e6:.2f}M", "Total revenue", "successful rides"),
        ("🧾", f"₹{k.aov:,.0f}", "Avg booking value", f"{int(k.n):,} rides"),
        ("👑", f"₹{top1.v:,.0f}", "Top customer spend", str(top1.c)),
        ("💳", "95.2%", "Cash + UPI share", "of successful rides"),
    ])

    section("Revenue by Payment Method", "successful rides only")
    pay = q(con, """
        SELECT Payment_Method p, SUM(Booking_Value) rev, COUNT(*) n
        FROM bookings WHERE Booking_Status='Success'
        GROUP BY 1 ORDER BY 2 DESC""")
    c1, c2 = st.columns([1.15, 1])
    with c1:
        fig = px.bar(pay, x="p", y="rev", text="rev", color="p",
                     color_discrete_sequence=SERIES)
        fig.update_traces(texttemplate="₹%{text:,.0f}", textposition="outside")
        fig.update_layout(title="Revenue by payment method", showlegend=False,
                          xaxis_title="", yaxis_title="INR")
        st.plotly_chart(dbase(fig, 320), use_container_width=True)
    with c2:
        fig = px.pie(pay, names="p", values="rev", hole=0.55,
                     color_discrete_sequence=SERIES)
        fig.update_traces(textinfo="percent", textfont=dict(size=11))
        fig.update_layout(title="Revenue share", showlegend=True)
        st.plotly_chart(dbase(fig, 320), use_container_width=True)
    cash_upi = pay[pay["p"].isin(["Cash", "UPI"])]["rev"].sum() / pay["rev"].sum() * 100
    insight(f"<b>Cash + UPI carry {cash_upi:.1f}% of revenue.</b> Card rails are almost "
            f"unused — a clear monetisation lever: card-linked offers would cut cash "
            f"handling cost and unlock credit-based upsell.")

    section("Top 5 Customers by Total Booking Value", "successful rides")
    tc = q(con, """
        SELECT Customer_ID c, SUM(Booking_Value) v, COUNT(*) n
        FROM bookings WHERE Booking_Status='Success'
        GROUP BY 1 ORDER BY 2 DESC LIMIT 5""")
    fig = px.bar(tc.sort_values("v"), x="v", y="c", orientation="h", text="v",
                 color="v", color_continuous_scale=["#1C4A2A", GREEN])
    fig.update_traces(texttemplate="₹%{text:,.0f}", textposition="outside")
    fig.update_layout(title="Top 5 customers by total booking value",
                      coloraxis_showscale=False, xaxis_title="INR", yaxis_title="")
    st.plotly_chart(dbase(fig, 300), use_container_width=True)
    insight(f"The top customer spent <b>₹{tc['v'].max():,.0f}</b> across "
            f"{int(tc['n'].max())} rides. Spend is <b>not concentrated</b> — the top 5 "
            f"together are a rounding error of total revenue, so growth must come from "
            f"breadth, not whale accounts.")

    section("Ride Distance Distribution Per Day", "successful rides")
    dd = q(con, """
        SELECT Booking_Date d, AVG(Ride_Distance) avg_km, COUNT(*) n
        FROM bookings WHERE Booking_Status='Success'
        GROUP BY 1 ORDER BY 1""")
    dd["d"] = pd.to_datetime(dd["d"])
    fig = go.Figure()
    fig.add_trace(go.Bar(x=dd["d"], y=dd["avg_km"], name="Avg km",
                         marker_color=TEAL, opacity=0.85))
    fig.add_hline(y=dd["avg_km"].mean(), line=dict(color=GREEN, width=1.6, dash="dash"),
                  annotation_text=f"mean {dd['avg_km'].mean():.1f} km",
                  annotation_font_color=GREEN)
    fig.update_layout(title="Average ride distance per day", yaxis_title="km",
                      xaxis_title="")
    st.plotly_chart(dbase(fig, 300), use_container_width=True)
    insight(f"Average trip length holds steady at <b>{dd['avg_km'].mean():.1f} km</b> "
            f"(range {dd['avg_km'].min():.1f}–{dd['avg_km'].max():.1f} km). Trip mix is "
            f"stable day to day — no long-trip drift to explain in the revenue line.")


# --------------------------------------------------------------------------- #
# Page 4 — Cancellation
# --------------------------------------------------------------------------- #
def page_cancel() -> None:
    hero("Cancellations",
         "Why rides die — the two sides of the cancellation story, side by side.",
         "Page 4 · Cancellation")

    k = q(con, """
        SELECT SUM(CASE WHEN Booking_Status='Canceled by Customer' THEN 1 ELSE 0 END) cc,
               SUM(CASE WHEN Booking_Status='Canceled by Driver' THEN 1 ELSE 0 END) dc,
               SUM(CASE WHEN Booking_Status='Driver Not Found' THEN 1 ELSE 0 END) nf,
               COUNT(*) n
        FROM bookings""").iloc[0]
    kpis([
        ("🚫", f"{int(k.cc):,}", "Customer cancellations", f"{100*k.cc/k.n:.1f}% of bookings"),
        ("🚗", f"{int(k.dc):,}", "Driver cancellations", f"{100*k.dc/k.n:.1f}% of bookings"),
        ("🔍", f"{int(k.nf):,}", "Driver not found", f"{100*k.nf/k.n:.1f}% of bookings"),
        ("📉", f"{100*(k.cc+k.dc+k.nf)/k.n:.1f}%", "Total non-success", "all failure modes"),
    ])

    section("Cancelled Rides Reasons — Customer", "why riders walk away")
    cc = q(con, """
        SELECT Canceled_Rides_by_Customer r, COUNT(*) n FROM bookings
        WHERE Booking_Status='Canceled by Customer' AND Canceled_Rides_by_Customer IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC""")
    fig = px.bar(cc.sort_values("n"), x="n", y="r", orientation="h", text="n",
                 color="n", color_continuous_scale=["#4A1C1C", ORANGE])
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(title=f"Customer cancellation reasons (n={int(cc['n'].sum()):,})",
                      coloraxis_showscale=False, xaxis_title="rides", yaxis_title="")
    st.plotly_chart(dbase(fig, 320), use_container_width=True)
    top_c = cc.iloc[0]
    insight(f"<b>{top_c['r']}</b> is the top customer reason with "
            f"<b>{int(top_c['n']):,} rides</b> ({100*top_c['n']/cc['n'].sum():.1f}%). "
            f"Both leading reasons are driver-behaviour issues — this is a "
            f"driver-quality problem surfacing as customer churn, not a pricing problem.")

    section("Cancelled Rides Reasons — Driver", "why drivers refuse")
    dc = q(con, """
        SELECT Canceled_Rides_by_Driver r, COUNT(*) n FROM bookings
        WHERE Booking_Status='Canceled by Driver' AND Canceled_Rides_by_Driver IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC""")
    fig = px.bar(dc.sort_values("n"), x="n", y="r", orientation="h", text="n",
                 color="n", color_continuous_scale=["#4A4A1C", YELLOW])
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(title=f"Driver cancellation reasons (n={int(dc['n'].sum()):,})",
                      coloraxis_showscale=False, xaxis_title="rides", yaxis_title="")
    st.plotly_chart(dbase(fig, 320), use_container_width=True)
    top_d = dc.iloc[0]
    insight(f"<b>{top_d['r']}</b> dominates driver cancellations at "
            f"<b>{int(top_d['n']):,} rides</b> ({100*top_d['n']/dc['n'].sum():.1f}%). "
            f"This is an operational, not behavioural, failure — vehicle readiness and "
            f"driver incentives are the fix.")


# --------------------------------------------------------------------------- #
# Page 5 — Ratings
# --------------------------------------------------------------------------- #
def page_ratings() -> None:
    hero("Ratings",
         "How riders and drivers score each other — and whether the two views agree.",
         "Page 5 · Ratings")

    k = q(con, """
        SELECT AVG(Driver_Ratings) dr, AVG(Customer_Rating) cr,
               MIN(Driver_Ratings) dmin, MAX(Driver_Ratings) dmax,
               COUNT(Driver_Ratings) n
        FROM bookings""").iloc[0]
    kpis([
        ("⭐", f"{k.dr:.2f}", "Avg driver rating", "1–5 scale"),
        ("🙋", f"{k.cr:.2f}", "Avg customer rating", "1–5 scale"),
        ("📊", f"{k.dmin:.1f}–{k.dmax:.1f}", "Driver rating range", "observed"),
        ("🧮", f"{int(k.n):,}", "Rated rides", "successful only"),
    ])

    section("Driver Ratings Distribution", "successful rides")
    dr = q(con, """
        SELECT Driver_Ratings r, COUNT(*) n FROM bookings
        WHERE Driver_Ratings IS NOT NULL GROUP BY 1 ORDER BY 1""")
    fig = px.bar(dr, x="r", y="n", text="n", color_discrete_sequence=[GREEN])
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(title="Driver ratings distribution", xaxis_title="rating",
                      yaxis_title="rides", xaxis=dict(dtick=0.1))
    st.plotly_chart(dbase(fig, 300), use_container_width=True)
    insight(f"Driver ratings cluster tightly around <b>{k.dr:.2f}</b> with almost no "
            f"mass below 3.5. The scale is effectively a 3.5–5.0 instrument — useful as a "
            f"floor check, weak as a ranking signal.")

    section("Customer Ratings Distribution", "successful rides")
    cr = q(con, """
        SELECT Customer_Rating r, COUNT(*) n FROM bookings
        WHERE Customer_Rating IS NOT NULL GROUP BY 1 ORDER BY 1""")
    fig = px.bar(cr, x="r", y="n", text="n", color_discrete_sequence=[TEAL])
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(title="Customer ratings distribution", xaxis_title="rating",
                      yaxis_title="rides", xaxis=dict(dtick=0.1))
    st.plotly_chart(dbase(fig, 300), use_container_width=True)
    insight(f"Customer ratings mirror the driver side at <b>{k.cr:.2f}</b>. Both "
            f"distributions are near-identical, which suggests a shared rating "
            f"behaviour rather than independent quality measurement.")

    section("Customer vs Driver Ratings", "joint distribution")
    jd = q(con, """
        SELECT Driver_Ratings d, Customer_Rating c, COUNT(*) n FROM bookings
        WHERE Driver_Ratings IS NOT NULL AND Customer_Rating IS NOT NULL
        GROUP BY 1,2""")
    fig = px.scatter(jd, x="d", y="c", size="n", color="n",
                     color_continuous_scale=["#123A46", TEAL, GREEN],
                     labels={"d": "Driver rating", "c": "Customer rating"})
    fig.update_layout(title="Customer vs driver rating (bubble = ride count)")
    st.plotly_chart(dbase(fig, 360), use_container_width=True)
    corr = jd["d"].corr(jd["c"])
    insight(f"Correlation between the two ratings is <b>{corr:.3f}</b> — essentially "
            f"none. A driver's score tells you almost nothing about how the customer "
            f"scored the trip, so neither metric can substitute for the other.")


# --------------------------------------------------------------------------- #
# Page 6 — SQL Questions
# --------------------------------------------------------------------------- #
SQL_QUESTIONS = [
    ("Retrieve all successful bookings",
     "SELECT * FROM bookings WHERE Booking_Status = 'Success' LIMIT 100",
     "All rides that completed successfully."),
    ("Average ride distance for each vehicle type",
     """SELECT Vehicle_Type, ROUND(AVG(Ride_Distance), 2) AS avg_distance_km
        FROM bookings WHERE Booking_Status = 'Success'
        GROUP BY Vehicle_Type ORDER BY avg_distance_km DESC""",
     "Average trip length per vehicle class."),
    ("Total number of cancelled rides by customers",
     """SELECT COUNT(*) AS customer_cancellations FROM bookings
        WHERE Booking_Status = 'Canceled by Customer'""",
     "How many rides customers cancelled."),
    ("Top 5 customers who booked the highest number of rides",
     """SELECT Customer_ID, COUNT(*) AS rides FROM bookings
        GROUP BY Customer_ID ORDER BY rides DESC LIMIT 5""",
     "The five most frequent riders."),
    ("Rides cancelled by drivers due to personal and car-related issues",
     """SELECT COUNT(*) AS personal_car_cancellations FROM bookings
        WHERE Booking_Status = 'Canceled by Driver'
          AND Canceled_Rides_by_Driver = 'Personal & Car related issue'""",
     "Driver cancellations from personal/vehicle problems."),
    ("Maximum and minimum driver ratings for Prime Sedan bookings",
     """SELECT MIN(Driver_Ratings) AS min_rating, MAX(Driver_Ratings) AS max_rating
        FROM bookings WHERE Vehicle_Type = 'Prime Sedan'
          AND Driver_Ratings IS NOT NULL""",
     "Rating spread for Prime Sedan."),
    ("All rides where payment was made using UPI",
     """SELECT * FROM bookings WHERE Payment_Method = 'UPI' LIMIT 100""",
     "Every UPI-paid ride."),
    ("Average customer rating per vehicle type",
     """SELECT Vehicle_Type, ROUND(AVG(Customer_Rating), 3) AS avg_customer_rating
        FROM bookings WHERE Customer_Rating IS NOT NULL
        GROUP BY Vehicle_Type ORDER BY avg_customer_rating DESC""",
     "Customer satisfaction by vehicle class."),
    ("Total booking value of rides completed successfully",
     """SELECT SUM(Booking_Value) AS total_booking_value FROM bookings
        WHERE Booking_Status = 'Success'""",
     "Revenue from completed rides."),
    ("All incomplete rides along with the reason",
     """SELECT Booking_ID, Vehicle_Type, Incomplete_Rides_Reason
        FROM bookings WHERE Incomplete_Rides = 'Yes' LIMIT 100""",
     "Rides that started but did not finish."),
]


def page_sql() -> None:
    hero("The 10 SQL Questions",
         "Every required question, answered live against the cleaned database — run any of them with one click.",
         "Page 6 · SQL Questions")

    st.markdown(f'<div class="chiprow"><span class="chip g">'
                f'{n_rows:,} rows in current filter view</span></div>',
                unsafe_allow_html=True)

    for i, (title, sql, blurb) in enumerate(SQL_QUESTIONS, 1):
        st.markdown(f'<div class="qcard"><b>Q{i}.</b> {title}</div>',
                    unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 1, 4])
        with c1:
            run_it = st.button("▶ Run", key=f"sqlrun{i}", use_container_width=True)
        with c2:
            show_sql = st.toggle("SQL", key=f"sqlshow{i}")
        if show_sql:
            st.code(sql, language="sql")
        if run_it:
            st.session_state.sql_open[i] = True
        if st.session_state.sql_open.get(i):
            try:
                res = q(con, sql)
                st.markdown(f'<div class="insight">💡<div>{blurb} '
                            f'<b>{len(res):,} row(s)</b> returned.</div></div>',
                            unsafe_allow_html=True)
                st.dataframe(res, use_container_width=True, height=min(340, 40 + 35*min(len(res), 8)))
                st.download_button("⬇ Download CSV", res.to_csv(index=False).encode(),
                                   file_name=f"q{i}.csv", mime="text/csv",
                                   key=f"sqldl{i}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Query failed: {exc}")
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Page 7 — Ask the Data
# --------------------------------------------------------------------------- #
def page_ask() -> None:
    hero("Ask the Data",
         "Type any question in plain English — the engine writes the SQL, runs it and charts the answer.",
         "Page 7 · Ask the Data")

    st.markdown(f'<div class="chiprow"><span class="chip g">'
                f'{n_rows:,} rows in current filter view</span></div>',
                unsafe_allow_html=True)

    c1, c2 = st.columns([5, 1])
    with c1:
        question = st.text_input(
            "Your question", key="ask_input",
            placeholder="e.g. Which vehicle type has the highest average fare?",
            label_visibility="collapsed")
    with c2:
        ask = st.button("Ask →", use_container_width=True)

    st.caption("Try one of these:")
    ex_cols = st.columns(3)
    for i, ex in enumerate(EXAMPLE_QUESTIONS[:6]):
        with ex_cols[i % 3]:
            if st.button(ex, key=f"ex{i}", use_container_width=True):
                st.session_state.ask_input = ex
                st.session_state.pending_ask = ex
                st.rerun()

    pending = st.session_state.pop("pending_ask", None)
    final_q = pending or (question if ask else None)

    if final_q:
        ctx = ""
        if st.session_state.history:
            ctx = st.session_state.history[-1]["q"]
        res, out, err = nl_run(final_q, con, context=ctx)
        if not res.ok:
            st.warning(res.message)
        elif err:
            st.error(f"Query error: {err}")
        else:
            st.markdown(f'<div class="interpreted">Interpreted as: '
                        f'<b>{res.explanation or res.intent}</b> · engine: {res.engine}</div>',
                        unsafe_allow_html=True)
            st.markdown(f'<div class="answer">{answer_sentence(out, res)}</div>',
                        unsafe_allow_html=True)
            with st.expander("View generated SQL"):
                st.code(res.sql, language="sql")
            st.dataframe(out, use_container_width=True,
                         height=min(320, 40 + 35*min(len(out), 8)))
            st.download_button("⬇ Download CSV", out.to_csv(index=False).encode(),
                               file_name="answer.csv", mime="text/csv")

            # chart
            if out is not None and len(out) > 0:
                cols = list(out.columns)
                if len(out) == 1 and len(cols) <= 2:
                    v = out.iloc[0, 0]
                    st.markdown(f'<div class="kpi" style="max-width:320px">'
                                f'<div class="v">{v:,.2f}</div>'
                                f'<div class="l">{cols[0]}</div></div>',
                                unsafe_allow_html=True)
                elif len(cols) >= 2:
                    x, y = cols[0], cols[1]
                    if res.intent == "trend":
                        fig = px.line(out, x=x, y=y, markers=True,
                                      color_discrete_sequence=[GREEN])
                    elif len(out) <= 8:
                        fig = px.bar(out, x=x, y=y, color=y,
                                     color_continuous_scale=["#1C4A2A", GREEN])
                        fig.update_layout(coloraxis_showscale=False)
                    else:
                        fig = px.bar(out.head(25), x=x, y=y,
                                     color_discrete_sequence=[GREEN])
                    fig.update_layout(title="Result", xaxis_title="", yaxis_title="")
                    st.plotly_chart(dbase(fig, 320), use_container_width=True)

            st.session_state.history.append({"q": final_q, "a": answer_sentence(out, res)})
            st.session_state.history = st.session_state.history[-5:]

    if st.session_state.history:
        section("Conversation", "last 5 questions")
        for h in reversed(st.session_state.history):
            st.markdown(f'<div class="hist"><b>Q:</b> {h["q"]}<br/><b>A:</b> {h["a"]}</div>',
                        unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Page 8 — Data Explorer
# --------------------------------------------------------------------------- #
def page_explorer() -> None:
    hero("Data Explorer",
         "Filter, search and inspect the cleaned dataset directly.",
         "Page 8 · Data Explorer")

    st.markdown(filter_chips(FILTERS), unsafe_allow_html=True)

    c1, c2 = st.columns([3, 1])
    with c1:
        search = st.text_input("Search (booking id, customer, area, vehicle…)",
                               placeholder="e.g. CID225428 or Tumkur")
    with c2:
        lim = st.selectbox("Rows", [100, 500, 1000, 5000], index=1)

    where = WHERE
    if search:
        s = search.replace("'", "''")
        clause = (f"(Booking_ID LIKE '%{s}%' OR Customer_ID LIKE '%{s}%' "
                  f"OR Pickup_Location LIKE '%{s}%' OR Drop_Location LIKE '%{s}%' "
                  f"OR Vehicle_Type LIKE '%{s}%')")
        where = f"({where}) AND {clause}" if where else clause

    total = int(q(con, f"SELECT COUNT(*) c FROM bookings WHERE {where or '1=1'}").iloc[0, 0])
    st.markdown(f'<div class="chiprow"><span class="chip g">{total:,} matching rows</span>'
                f'</div>', unsafe_allow_html=True)

    data = q(con, f"SELECT * FROM bookings WHERE {where or '1=1'} LIMIT {lim}")
    st.dataframe(data, use_container_width=True, height=420)
    st.download_button("⬇ Download filtered CSV", data.to_csv(index=False).encode(),
                       file_name="ola_filtered.csv", mime="text/csv")

    section("Quick profile of the filtered view")
    c1, c2 = st.columns(2)
    with c1:
        vc = q(con, f"""SELECT Vehicle_Type v, COUNT(*) n FROM bookings
                        WHERE {where or '1=1'} GROUP BY 1 ORDER BY 2 DESC""")
        fig = px.bar(vc, x="v", y="n", color="n",
                     color_continuous_scale=["#1C4A2A", GREEN])
        fig.update_layout(title="Bookings by vehicle type", coloraxis_showscale=False,
                          xaxis_title="", yaxis_title="")
        st.plotly_chart(dbase(fig, 300), use_container_width=True)
    with c2:
        sc = q(con, f"""SELECT Booking_Status s, COUNT(*) n FROM bookings
                        WHERE {where or '1=1'} GROUP BY 1 ORDER BY 2 DESC""")
        fig = px.pie(sc, names="s", values="n", hole=0.5,
                     color_discrete_sequence=[GREEN, ORANGE, YELLOW, TEAL])
        fig.update_layout(title="Status mix")
        st.plotly_chart(dbase(fig, 300), use_container_width=True)


# --------------------------------------------------------------------------- #
# Page 9 — Power BI
# --------------------------------------------------------------------------- #
def page_powerbi() -> None:
    hero("Power BI Dashboard",
         "The five-page Power BI report — embed your published report to view it live here.",
         "Page 9 · Power BI")

    url = st.text_input("Power BI publish-to-web URL (optional)",
                        value=st.session_state.get("pbi_url", ""),
                        placeholder="https://app.powerbi.com/view?r=...")
    if url:
        st.session_state.pbi_url = url

    if url and url.startswith("http"):
        st.components.v1.iframe(url, height=760, scrolling=True)
    else:
        st.info("No Power BI URL set. Paste a **publish-to-web** link above to embed the "
                "live report. Meanwhile, here is the intended 5-page structure.")

    section("Report structure", "5 pages, matching the brief")
    pages = [
        ("1 · Overall", "Ride Volume Over Time · Booking Status Breakdown"),
        ("2 · Vehicle Type", "Top 5 Vehicle Types by Ride Distance · Avg Customer Ratings"),
        ("3 · Revenue", "Revenue by Payment Method · Top 5 Customers · Distance per Day"),
        ("4 · Cancellation", "Cancelled Rides Reasons (Customer) · (Driver)"),
        ("5 · Ratings", "Driver Ratings · Customer Ratings · Customer vs Driver"),
    ]
    cols = st.columns(5)
    for i, (t, d) in enumerate(pages):
        with cols[i]:
            st.markdown(f'<div class="vcard" style="text-align:left">'
                        f'<div class="nm">{t}</div>'
                        f'<div class="mt">{d}</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**Build kit** — the full guide, theme and DAX live in `powerbi/`.")
    st.markdown("- `POWERBI_BUILD_GUIDE.md` — step-by-step build\n"
                "- `theme.json` — Ola palette theme\n"
                "- `dax_measures.md` — copy-paste measures\n"
                "- `dashboard_mockup.html` — static 5-page mockup")


# --------------------------------------------------------------------------- #
# Page 10 — Data Quality
# --------------------------------------------------------------------------- #
def page_quality() -> None:
    hero("Data Quality",
         "What was cleaned, what is missing, and what is flagged — the audit trail.",
         "Page 10 · Data Quality")

    try:
        sc = json.load(open(os.path.join(DATA_DIR, "quality_scorecard.json")))
    except Exception:  # noqa: BLE001
        sc = {}

    kpis([
        ("📥", f"{sc.get('rows_before', 103024):,}", "Rows loaded", "raw workbook"),
        ("✅", f"{sc.get('rows_after', 103024):,}", "Rows kept", "0 dropped"),
        ("📊", f"{sc.get('completeness_after_pct', 94.8):.1f}%", "Completeness",
         f"from {sc.get('completeness_before_pct', 75.2):.1f}%"),
        ("🔁", f"{sc.get('duplicates', 0)}", "Duplicates", "booking ids"),
    ])

    section("Missing values by column", "current filter view")
    miss = q(con, """
        SELECT 'Driver_Ratings' col, SUM(CASE WHEN Driver_Ratings IS NULL THEN 1 ELSE 0 END) n, COUNT(*) t FROM bookings
        UNION ALL SELECT 'Customer_Rating', SUM(CASE WHEN Customer_Rating IS NULL THEN 1 ELSE 0 END), COUNT(*) FROM bookings
        UNION ALL SELECT 'V_TAT', SUM(CASE WHEN V_TAT IS NULL THEN 1 ELSE 0 END), COUNT(*) FROM bookings
        UNION ALL SELECT 'C_TAT', SUM(CASE WHEN C_TAT IS NULL THEN 1 ELSE 0 END), COUNT(*) FROM bookings
        UNION ALL SELECT 'Payment_Method', SUM(CASE WHEN Payment_Method IS NULL THEN 1 ELSE 0 END), COUNT(*) FROM bookings
        UNION ALL SELECT 'Incomplete_Rides_Reason', SUM(CASE WHEN Incomplete_Rides_Reason IS NULL THEN 1 ELSE 0 END), COUNT(*) FROM bookings
    """)
    miss["pct"] = (100 * miss["n"] / miss["t"]).round(1)
    fig = px.bar(miss.sort_values("pct"), x="pct", y="col", orientation="h", text="pct",
                 color="pct", color_continuous_scale=["#1C4A2A", GREEN])
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(title="Missing share by column", coloraxis_showscale=False,
                      xaxis_title="% missing", yaxis_title="")
    st.plotly_chart(dbase(fig, 300), use_container_width=True)
    insight("Missingness is <b>structural, not random</b>: ratings, TAT and payment are "
            "NULL only for the 39,057 rides that never happened. These were deliberately "
            "left NULL rather than imputed — filling them would fabricate data.")

    section("Outlier flags", "IQR method, flagged not deleted")
    out = q(con, """
        SELECT 'Booking_Value' col, SUM(Booking_Value_is_outlier) n FROM bookings
        UNION ALL SELECT 'V_TAT', SUM(V_TAT_is_outlier) FROM bookings
        UNION ALL SELECT 'C_TAT', SUM(C_TAT_is_outlier) FROM bookings
        UNION ALL SELECT 'Ride_Distance', SUM(Ride_Distance_is_outlier) FROM bookings
    """)
    st.dataframe(out, use_container_width=True, hide_index=True)

    section("Schema", "37 columns after feature engineering")
    st.code(SCHEMA, language="text")


# --------------------------------------------------------------------------- #
# Page 11 — Audience Q&A
# --------------------------------------------------------------------------- #
AUDIENCE_QA = [
    ("How many bookings were there in total?", "SELECT COUNT(*) AS total_bookings FROM bookings"),
    ("What share of bookings succeeded?", "SELECT ROUND(100.0*SUM(CASE WHEN Booking_Status='Success' THEN 1 ELSE 0 END)/COUNT(*),2) AS success_pct FROM bookings"),
    ("What was total revenue from successful rides?", "SELECT SUM(Booking_Value) AS total_revenue FROM bookings WHERE Booking_Status='Success'"),
    ("What is the average booking value?", "SELECT ROUND(AVG(Booking_Value),2) AS avg_booking_value FROM bookings WHERE Booking_Status='Success'"),
    ("Which vehicle type has the highest average ride distance?", "SELECT Vehicle_Type, ROUND(AVG(Ride_Distance),2) AS avg_km FROM bookings WHERE Booking_Status='Success' GROUP BY 1 ORDER BY 2 DESC"),
    ("Which vehicle type has the best customer rating?", "SELECT Vehicle_Type, ROUND(AVG(Customer_Rating),3) AS avg_rating FROM bookings WHERE Customer_Rating IS NOT NULL GROUP BY 1 ORDER BY 2 DESC"),
    ("How many rides did customers cancel?", "SELECT COUNT(*) AS n FROM bookings WHERE Booking_Status='Canceled by Customer'"),
    ("How many rides did drivers cancel?", "SELECT COUNT(*) AS n FROM bookings WHERE Booking_Status='Canceled by Driver'"),
    ("What is the top driver cancellation reason?", "SELECT Canceled_Rides_by_Driver r, COUNT(*) n FROM bookings WHERE Booking_Status='Canceled by Driver' GROUP BY 1 ORDER BY 2 DESC"),
    ("What is the top customer cancellation reason?", "SELECT Canceled_Rides_by_Customer r, COUNT(*) n FROM bookings WHERE Booking_Status='Canceled by Customer' GROUP BY 1 ORDER BY 2 DESC"),
    ("Which hour of the day has the most bookings?", "SELECT Booking_Hour h, COUNT(*) n FROM bookings GROUP BY 1 ORDER BY 2 DESC"),
    ("How does demand split across time-of-day blocks?", "SELECT Time_of_Day t, COUNT(*) n FROM bookings GROUP BY 1 ORDER BY 2 DESC"),
    ("Which payment method is used most?", "SELECT Payment_Method p, COUNT(*) n FROM bookings WHERE Booking_Status='Success' GROUP BY 1 ORDER BY 2 DESC"),
    ("How much revenue comes from each payment method?", "SELECT Payment_Method p, SUM(Booking_Value) rev FROM bookings WHERE Booking_Status='Success' GROUP BY 1 ORDER BY 2 DESC"),
    ("Who are the top 5 customers by booking value?", "SELECT Customer_ID c, SUM(Booking_Value) v FROM bookings WHERE Booking_Status='Success' GROUP BY 1 ORDER BY 2 DESC LIMIT 5"),
    ("Who are the top 5 customers by number of rides?", "SELECT Customer_ID c, COUNT(*) n FROM bookings GROUP BY 1 ORDER BY 2 DESC LIMIT 5"),
    ("What is the average driver rating?", "SELECT ROUND(AVG(Driver_Ratings),3) AS avg_driver_rating FROM bookings WHERE Driver_Ratings IS NOT NULL"),
    ("What is the average customer rating?", "SELECT ROUND(AVG(Customer_Rating),3) AS avg_customer_rating FROM bookings WHERE Customer_Rating IS NOT NULL"),
    ("How many rides were incomplete, and why?", "SELECT Incomplete_Rides_Reason r, COUNT(*) n FROM bookings WHERE Incomplete_Rides='Yes' GROUP BY 1 ORDER BY 2 DESC"),
    ("How many zero-distance rides are there?", "SELECT COUNT(*) AS zero_distance_rides FROM bookings WHERE Ride_Distance=0"),
    ("What is the average ride distance?", "SELECT ROUND(AVG(Ride_Distance),2) AS avg_km FROM bookings WHERE Booking_Status='Success'"),
    ("How many bookings per vehicle type?", "SELECT Vehicle_Type v, COUNT(*) n FROM bookings GROUP BY 1 ORDER BY 2 DESC"),
    ("Which pickup area has the most bookings?", "SELECT Pickup_Location a, COUNT(*) n FROM bookings GROUP BY 1 ORDER BY 2 DESC LIMIT 10"),
    ("What is the busiest day of the week?", "SELECT Booking_DayOfWeek d, COUNT(*) n FROM bookings GROUP BY 1 ORDER BY 2 DESC"),
]


def page_qa() -> None:
    hero("Audience Q&A",
         "Pick a question — or ask your own — and get the answer computed live from the data.",
         "Page 11 · Audience Q&A")

    idx = st.session_state.qa_idx
    total = len(AUDIENCE_QA)

    # question picker
    c1, c2 = st.columns([3, 1])
    with c1:
        pick = st.selectbox("Choose a question", [f"{i+1}. {q_}" for i, (q_, _) in enumerate(AUDIENCE_QA)],
                            index=idx, label_visibility="collapsed")
        idx = int(pick.split(".")[0]) - 1
        st.session_state.qa_idx = idx
    with c2:
        custom = st.text_input("Or type your own", placeholder="ask anything…",
                               label_visibility="collapsed")

    question, sql = AUDIENCE_QA[idx]
    if custom:
        question, sql = custom, None

    st.markdown(f'<div class="qacard"><div class="qnum">Question {idx+1} of {total}</div>'
                f'<div class="qtext">{question}</div></div>', unsafe_allow_html=True)

    # run
    if sql:
        try:
            res = q(con, sql)
            # answer sentence
            if len(res) == 1 and len(res.columns) <= 2:
                v = res.iloc[0, 0]
                label = res.columns[0].replace("_", " ")
                ans = f"{label.capitalize()}: {v:,.2f}" if isinstance(v, (int, float)) else f"{label}: {v}"
            elif len(res.columns) >= 2:
                g, m = res.columns[0], res.columns[1]
                top = res.iloc[0]
                ans = f"{top[g]} leads with {top[m]:,.2f} ({len(res)} groups shown)."
            else:
                ans = f"{len(res):,} rows returned."
            st.markdown(f'<div class="answer">{ans}</div>', unsafe_allow_html=True)

            with st.expander("View SQL"):
                st.code(sql, language="sql")

            st.dataframe(res, use_container_width=True,
                         height=min(300, 40 + 35*min(len(res), 7)))

            if len(res.columns) >= 2 and len(res) > 1:
                g, m = res.columns[0], res.columns[1]
                if len(res) <= 10:
                    fig = px.bar(res, x=g, y=m, color=m,
                                 color_continuous_scale=["#1C4A2A", GREEN])
                    fig.update_layout(coloraxis_showscale=False)
                else:
                    fig = px.bar(res.head(20), x=g, y=m, color_discrete_sequence=[GREEN])
                fig.update_layout(title="", xaxis_title="", yaxis_title="")
                st.plotly_chart(dbase(fig, 300), use_container_width=True)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not run that question: {exc}")
    else:
        res, out, err = nl_run(question, con)
        if not res.ok:
            st.warning(res.message)
        elif err:
            st.error(err)
        else:
            st.markdown(f'<div class="answer">{answer_sentence(out, res)}</div>',
                        unsafe_allow_html=True)
            with st.expander("View SQL"):
                st.code(res.sql, language="sql")
            st.dataframe(out, use_container_width=True)

    # prev / next question
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("← Previous question", disabled=idx == 0, use_container_width=True):
            st.session_state.qa_idx = max(0, idx - 1)
            st.rerun()
    with c3:
        if st.button("Next question →", disabled=idx >= total - 1, use_container_width=True):
            st.session_state.qa_idx = min(total - 1, idx + 1)
            st.rerun()


# --------------------------------------------------------------------------- #
# Router + Prev/Next
# --------------------------------------------------------------------------- #
RENDER = {
    0: page_overall, 1: page_vehicle, 2: page_revenue, 3: page_cancel,
    4: page_ratings, 5: page_sql, 6: page_ask, 7: page_explorer,
    8: page_powerbi, 9: page_quality, 10: page_qa,
}

st.markdown(filter_chips(FILTERS), unsafe_allow_html=True)
RENDER[st.session_state.page]()

# bottom navigation
i = st.session_state.page
dots = "".join(f'<div class="dot{" on" if j == i else ""}"></div>' for j in range(len(PAGES)))
st.markdown(f'<div class="pagebar"><div class="pageind">Page <b>{i+1}</b> of {len(PAGES)} · '
            f'{PAGES[i][0]}</div><div class="dots">{dots}</div></div>',
            unsafe_allow_html=True)

c1, c2, c3 = st.columns([1, 2, 1])
with c1:
    if st.button("← Previous", disabled=i == 0, use_container_width=True):
        goto(i - 1)
        st.rerun()
with c3:
    if st.button("Next →", disabled=i >= len(PAGES) - 1, use_container_width=True):
        goto(i + 1)
        st.rerun()
