"""
make_dashboard_mockup.py — Build a static, self-contained HTML mockup of the
5-page Power BI dashboard, using the real numbers from the cleaned dataset.

Output: powerbi/dashboard_mockup.html

Run:  python make_dashboard_mockup.py
"""
from __future__ import annotations

import json

import pandas as pd

df = pd.read_csv("data/ola_cleaned.csv")
success = df[df["Booking_Status"] == "Success"]
eda = json.load(open("eda/eda_summary.json"))

# ---- headline numbers ------------------------------------------------------
total = len(df)
succ = len(success)
rev = float(success["Booking_Value"].sum())
avg_fare = float(success["Booking_Value"].mean())
avg_dist = float(success["Ride_Distance"].mean())
status_mix = df["Booking_Status"].value_counts()
pay_mix = success["Payment_Method"].value_counts()
veh_dist = success.groupby("Vehicle_Type")["Ride_Distance"].sum().sort_values(ascending=False)
veh_avg = success.groupby("Vehicle_Type")["Ride_Distance"].mean().sort_values()
cust_reasons = (df[df["Booking_Status"] == "Canceled by Customer"]
                ["Canceled_Rides_by_Customer"].value_counts())
drv_reasons = (df[df["Booking_Status"] == "Canceled by Driver"]
               ["Canceled_Rides_by_Driver"].value_counts())
top_cust = (df.groupby("Customer_ID")
            .agg(Bookings=("Booking_ID", "count"),
                 Spend=("Booking_Value", lambda s: s[df.loc[s.index, "Booking_Status"] == "Success"].sum()))
            .sort_values("Spend", ascending=False).head(5))
daily = df.groupby("Booking_Date").size()
daily_dist = success.groupby("Booking_Date")["Ride_Distance"].sum()
drv_rating_hist = success["Driver_Ratings"].value_counts().sort_index()
cust_rating_hist = success["Customer_Rating"].value_counts().sort_index()

NAVY, GREEN, BLUE, ORANGE, TEAL, GREY = (
    "#262626", "#92D050", "#058DC7", "#ED561B", "#24CBE5", "#AEAEAE")


def hbar(rows, color, fmt="{:,.0f}", maxw=100):
    """Render a horizontal bar list as HTML."""
    mx = max(v for _, v in rows) or 1
    out = []
    for label, val in rows:
        w = max(2, val / mx * maxw)
        out.append(
            f'<div class="hb"><span class="hbl">{label}</span>'
            f'<span class="hbt"><span class="hbf" style="width:{w:.1f}%;background:{color}"></span></span>'
            f'<span class="hbv">{fmt.format(val)}</span></div>'
        )
    return "".join(out)


def sparkline(series, color, w=980, h=150):
    """Render a simple SVG line chart from a pandas Series."""
    vals = list(series.values)
    n = len(vals)
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    pts = []
    for i, v in enumerate(vals):
        x = i / (n - 1) * w
        y = h - (v - lo) / rng * (h - 20) - 10
        pts.append(f"{x:.1f},{y:.1f}")
    area = f"0,{h} " + " ".join(pts) + f" {w},{h}"
    return (f'<svg viewBox="0 0 {w} {h}" class="spark" preserveAspectRatio="none">'
            f'<polygon points="{area}" fill="{color}" opacity="0.12"/>'
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2.5"/></svg>')


def donut(rows, colors, size=190):
    """Render a donut chart as SVG with a legend."""
    total_v = sum(v for _, v in rows)
    r, cx, cy, sw = 70, size / 2, size / 2, 26
    circ = 2 * 3.14159 * r
    off = 0
    segs = []
    for (label, val), col in zip(rows, colors):
        frac = val / total_v
        segs.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{col}" '
            f'stroke-width="{sw}" stroke-dasharray="{frac*circ:.2f} {circ:.2f}" '
            f'stroke-dashoffset="{-off*circ:.2f}" transform="rotate(-90 {cx} {cy})"/>'
        )
        off += frac
    legend = "".join(
        f'<div class="lg"><span class="dot" style="background:{c}"></span>'
        f'{l} <b>{v:,}</b> <span class="pct">{v/total_v*100:.1f}%</span></div>'
        for (l, v), c in zip(rows, colors))
    return (f'<div class="donutwrap"><svg viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
            f'{"".join(segs)}</svg><div class="legend">{legend}</div></div>')


def colchart(rows, color, h=170):
    """Render a vertical column chart as HTML."""
    mx = max(v for _, v in rows) or 1
    bars = "".join(
        f'<div class="col"><div class="colb" style="height:{max(3, v/mx*(h-30)):.0f}px;background:{color}"></div>'
        f'<div class="coll">{l}</div></div>' for l, v in rows)
    return f'<div class="cols" style="height:{h}px">{bars}</div>'


def page(num, title, body):
    """Wrap page content in the dashboard chrome."""
    return f'''
<section class="page" id="p{num}">
  <header class="hdr"><div class="hdr-t">{title}</div>
    <div class="hdr-nav">{''.join(f'<a href="#p{i}" class="{"on" if i==num else ""}">{n}</a>' for i,n in [(1,"Overall"),(2,"Vehicle Type"),(3,"Revenue"),(4,"Cancellation"),(5,"Ratings")])}</div>
    <div class="hdr-logo">OLA</div>
  </header>
  <div class="body">
    <aside class="rail">
      <div class="sl"><div class="sl-h">Date Range</div><div class="sl-v">01 Jul – 31 Jul 2024</div></div>
      <div class="sl"><div class="sl-h">Vehicle Type</div><div class="sl-v">All (7)</div></div>
      <div class="sl"><div class="sl-h">Payment Method</div><div class="sl-v">All (4)</div></div>
      <div class="sl"><div class="sl-h">Booking Status</div><div class="sl-v">All (4)</div></div>
    </aside>
    <main class="main">{body}</main>
  </div>
</section>'''


# ============================ PAGE 1 =======================================
p1 = f'''
<div class="kpis">
  <div class="kpi"><div class="kv" style="color:{NAVY}">{total:,}</div><div class="kl">Total Bookings</div></div>
  <div class="kpi"><div class="kv" style="color:{GREEN}">{succ/total*100:.1f}%</div><div class="kl">Success Rate</div></div>
  <div class="kpi"><div class="kv" style="color:{NAVY}">₹{rev/1e6:.2f}M</div><div class="kl">Total Revenue</div></div>
  <div class="kpi"><div class="kv" style="color:{BLUE}">{avg_dist:.1f} km</div><div class="kl">Avg Distance</div></div>
</div>
<div class="grid2">
  <div class="card wide"><div class="ct">Ride Volume Over Time</div>{sparkline(daily, BLUE)}
    <div class="axis"><span>01 Jul</span><span>15 Jul</span><span>31 Jul</span></div></div>
  <div class="card"><div class="ct">Booking Status Breakdown</div>
    {donut([(k, int(v)) for k, v in status_mix.items()], [GREEN, ORANGE, "#EDEF00", GREY])}</div>
</div>
<div class="card"><div class="ct">Status Detail</div>
<table class="tbl"><thead><tr><th>Booking Status</th><th class="r">Bookings</th><th class="r">Share</th></tr></thead><tbody>
{''.join(f'<tr><td>{k}</td><td class="r">{v:,}</td><td class="r">{v/total*100:.1f}%</td></tr>' for k,v in status_mix.items())}
</tbody></table></div>'''

# ============================ PAGE 2 =======================================
top5 = list(veh_dist.head(5).items())
p2 = f'''
<div class="kpis">
  <div class="kpi"><div class="kv" style="color:{NAVY}">{len(veh_dist)}</div><div class="kl">Vehicle Types</div></div>
  <div class="kpi"><div class="kv" style="color:{BLUE}">{veh_dist.sum()/1e6:.2f}M km</div><div class="kl">Total Distance</div></div>
  <div class="kpi"><div class="kv" style="color:{GREEN}">{avg_dist:.1f} km</div><div class="kl">Avg per Ride</div></div>
  <div class="kpi"><div class="kv" style="color:{ORANGE}">10.0 km</div><div class="kl">Auto (short-trip)</div></div>
</div>
<div class="grid2">
  <div class="card"><div class="ct">Top 5 Vehicle Types by Ride Distance</div>
    {hbar([(k, v) for k, v in top5], BLUE, "{:,.0f} km")}</div>
  <div class="card"><div class="ct">Average Distance by Vehicle Type</div>
    {hbar([(k, v) for k, v in veh_avg.items()], GREEN, "{:.1f} km")}</div>
</div>
<div class="card"><div class="ct">Vehicle Performance Matrix</div>
<table class="tbl"><thead><tr><th>Vehicle Type</th><th class="r">Rides</th><th class="r">Avg km</th><th class="r">Avg Fare</th><th class="r">Avg Rating</th></tr></thead><tbody>
{''.join(f'<tr><td>{v}</td><td class="r">{int((success["Vehicle_Type"]==v).sum()):,}</td><td class="r">{success[success["Vehicle_Type"]==v]["Ride_Distance"].mean():.1f}</td><td class="r">₹{success[success["Vehicle_Type"]==v]["Booking_Value"].mean():,.0f}</td><td class="r">{success[success["Vehicle_Type"]==v]["Customer_Rating"].mean():.2f}</td></tr>' for v in veh_dist.index)}
</tbody></table></div>'''

# ============================ PAGE 3 =======================================
p3 = f'''
<div class="kpis">
  <div class="kpi"><div class="kv" style="color:{NAVY}">₹{rev:,.0f}</div><div class="kl">Total Revenue</div></div>
  <div class="kpi"><div class="kv" style="color:{GREEN}">₹{avg_fare:,.0f}</div><div class="kl">Avg Fare</div></div>
  <div class="kpi"><div class="kv" style="color:{BLUE}">95.2%</div><div class="kl">Cash + UPI Share</div></div>
  <div class="kpi"><div class="kv" style="color:{ORANGE}">4.8%</div><div class="kl">Card Adoption</div></div>
</div>
<div class="grid2">
  <div class="card"><div class="ct">Revenue by Payment Method</div>
    {hbar([(k, float(success[success["Payment_Method"]==k]["Booking_Value"].sum())) for k in pay_mix.index], BLUE, "₹{:,.0f}")}</div>
  <div class="card"><div class="ct">Top 5 Customers by Total Booking Value</div>
<table class="tbl"><thead><tr><th>Customer</th><th class="r">Bookings</th><th class="r">Spend</th></tr></thead><tbody>
{''.join(f'<tr><td>{c}</td><td class="r">{int(r.Bookings)}</td><td class="r">₹{r.Spend:,.0f}</td></tr>' for c, r in top_cust.iterrows())}
</tbody></table></div>
</div>
<div class="card"><div class="ct">Ride Distance Distribution Per Day</div>{sparkline(daily_dist, TEAL)}
  <div class="axis"><span>01 Jul</span><span>15 Jul</span><span>31 Jul</span></div></div>'''

# ============================ PAGE 4 =======================================
p4 = f'''
<div class="kpis">
  <div class="kpi"><div class="kv" style="color:{ORANGE}">{int(status_mix.get("Canceled by Customer",0)+status_mix.get("Canceled by Driver",0)):,}</div><div class="kl">Total Cancellations</div></div>
  <div class="kpi"><div class="kv" style="color:{ORANGE}">28.1%</div><div class="kl">Cancellation Rate</div></div>
  <div class="kpi"><div class="kv" style="color:{NAVY}">6,542</div><div class="kl">Driver: Personal &amp; Car</div></div>
  <div class="kpi"><div class="kv" style="color:{ORANGE}">₹{float(df[df["Booking_Status"].str.startswith("Canceled")]["Booking_Value"].sum())/1e6:.2f}M</div><div class="kl">Revenue Lost</div></div>
</div>
<div class="grid2">
  <div class="card"><div class="ct">Cancelled Rides Reasons (Customer)</div>
    {hbar([(k, int(v)) for k, v in cust_reasons.items()], "#EDEF00")}</div>
  <div class="card"><div class="ct">Cancelled Rides Reasons (Driver)</div>
    {hbar([(k, int(v)) for k, v in drv_reasons.items()], ORANGE)}</div>
</div>
<div class="card note"><b>Insight:</b> Driver-side cancellations (18,434) are the single largest revenue leak.
"Personal &amp; Car related issue" alone accounts for 6,542 rides — a supply-reliability problem, not a demand problem.</div>'''

# ============================ PAGE 5 =======================================
p5 = f'''
<div class="kpis">
  <div class="kpi"><div class="kv" style="color:{NAVY}">{success["Driver_Ratings"].mean():.2f}</div><div class="kl">Avg Driver Rating</div></div>
  <div class="kpi"><div class="kv" style="color:{GREEN}">{success["Customer_Rating"].mean():.2f}</div><div class="kl">Avg Customer Rating</div></div>
  <div class="kpi"><div class="kv" style="color:{GREY}">{success["Driver_Ratings"].mean()-success["Customer_Rating"].mean():+.3f}</div><div class="kl">Rating Gap</div></div>
  <div class="kpi"><div class="kv" style="color:{BLUE}">{(success["Driver_Ratings"]>=4.5).mean()*100:.1f}%</div><div class="kl">Rated 4.5+</div></div>
</div>
<div class="grid2">
  <div class="card"><div class="ct">Driver Ratings Distribution</div>
    {colchart([(f"{k:.1f}", int(v)) for k, v in drv_rating_hist.items()], BLUE)}</div>
  <div class="card"><div class="ct">Customer Ratings Distribution</div>
    {colchart([(f"{k:.1f}", int(v)) for k, v in cust_rating_hist.items()], GREEN)}</div>
</div>
<div class="card note"><b>Insight:</b> Both distributions are near-identical and centred on 4.0
(correlation r = −0.003). Satisfaction is uniformly high across all 7 vehicle types — it is <i>not</i> a differentiator.</div>'''

HTML = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OLA Rides — Power BI Dashboard Mockup</title>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Poppins',system-ui,sans-serif;background:#E9EDF0;color:#262626;padding:24px}}
.intro{{max-width:1280px;margin:0 auto 20px;background:#fff;border-radius:12px;padding:20px 24px;border-left:6px solid #92D050}}
.intro h1{{font-size:20px;margin-bottom:6px}}
.intro p{{font-size:13px;color:#595959;line-height:1.6}}
.page{{max-width:1280px;margin:0 auto 28px;background:#F7F9FA;border-radius:12px;overflow:hidden;box-shadow:0 4px 18px rgba(0,0,0,.10)}}
.hdr{{height:64px;background:#262626;display:flex;align-items:center;padding:0 24px;gap:20px}}
.hdr-t{{color:#fff;font-size:18px;font-weight:600;flex:1}}
.hdr-nav{{display:flex;gap:6px}}
.hdr-nav a{{color:#AEAEAE;text-decoration:none;font-size:11px;padding:6px 10px;border-radius:6px}}
.hdr-nav a.on{{background:#92D050;color:#262626;font-weight:600}}
.hdr-logo{{color:#92D050;font-weight:700;font-size:16px;letter-spacing:1px}}
.body{{display:flex;min-height:600px}}
.rail{{width:200px;background:#fff;border-right:1px solid #E6E6E6;padding:14px 12px;display:flex;flex-direction:column;gap:10px}}
.sl{{border:1px solid #E6E6E6;border-radius:8px;padding:8px 10px}}
.sl-h{{font-size:10px;font-weight:600;color:#262626;text-transform:uppercase;letter-spacing:.4px}}
.sl-v{{font-size:11px;color:#595959;margin-top:3px}}
.main{{flex:1;padding:16px;display:flex;flex-direction:column;gap:14px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.kpi{{background:#fff;border:1px solid #E6E6E6;border-radius:10px;padding:14px 16px}}
.kv{{font-size:26px;font-weight:700;line-height:1.1}}
.kl{{font-size:10px;color:#595959;margin-top:4px;text-transform:uppercase;letter-spacing:.4px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.card{{background:#fff;border:1px solid #E6E6E6;border-radius:10px;padding:14px 16px}}
.card.wide{{grid-column:span 1}}
.ct{{font-size:12px;font-weight:600;color:#262626;margin-bottom:12px}}
.spark{{width:100%;height:150px;display:block}}
.axis{{display:flex;justify-content:space-between;font-size:9px;color:#AEAEAE;margin-top:4px}}
.hb{{display:flex;align-items:center;gap:8px;margin-bottom:9px;font-size:11px}}
.hbl{{width:150px;color:#404040;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.hbt{{flex:1;height:16px;background:#F0F3F5;border-radius:4px;overflow:hidden}}
.hbf{{display:block;height:100%;border-radius:4px}}
.hbv{{width:88px;text-align:right;font-weight:600;color:#262626;flex-shrink:0}}
.donutwrap{{display:flex;align-items:center;gap:18px}}
.legend{{display:flex;flex-direction:column;gap:7px;font-size:11px}}
.lg{{display:flex;align-items:center;gap:7px;color:#404040}}
.dot{{width:10px;height:10px;border-radius:3px;display:inline-block}}
.pct{{color:#AEAEAE;font-size:10px}}
.tbl{{width:100%;border-collapse:collapse;font-size:11px}}
.tbl th{{background:#262626;color:#fff;text-align:left;padding:8px 10px;font-weight:600;font-size:10px;text-transform:uppercase;letter-spacing:.3px}}
.tbl td{{padding:7px 10px;border-bottom:1px solid #EEF1F3;color:#404040}}
.tbl tbody tr:nth-child(even){{background:#F7F9FA}}
.r{{text-align:right}}
.cols{{display:flex;align-items:flex-end;gap:6px;padding-top:10px}}
.col{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end}}
.colb{{width:100%;border-radius:3px 3px 0 0}}
.coll{{font-size:8px;color:#AEAEAE;margin-top:4px}}
.note{{font-size:12px;color:#404040;line-height:1.6;border-left:4px solid #92D050;background:#F4FBEC}}
@media(max-width:900px){{.kpis{{grid-template-columns:repeat(2,1fr)}}.grid2{{grid-template-columns:1fr}}.rail{{display:none}}}}
</style></head>
<body>
<div class="intro">
  <h1>OLA Rides Analytics — Power BI Dashboard Mockup</h1>
  <p>Static visual mockup of the 5-page Power BI report, rendered with the real
  numbers from the cleaned dataset (103,024 bookings, July 2024). Use this to
  review layout and content before building the .pbix — the build guide
  (<code>POWERBI_BUILD_GUIDE.md</code>) specifies every visual, measure and
  formatting choice. Palette and typography match <code>Ola-Slides.pptx</code>.</p>
</div>
{page(1, "Overall", p1)}
{page(2, "Vehicle Type", p2)}
{page(3, "Revenue", p3)}
{page(4, "Cancellation", p4)}
{page(5, "Ratings", p5)}
</body></html>'''

with open("powerbi/dashboard_mockup.html", "w") as f:
    f.write(HTML)
print("Wrote powerbi/dashboard_mockup.html", len(HTML), "bytes")
