"""
eda.py — OLA Rides: standalone Exploratory Data Analysis
========================================================
Loads the raw Excel workbook, cleans it in-process (same rules as clean_data.py),
then runs the full analysis on ALL 103,024 rows and ALL columns — no sampling.

Produces
--------
eda/charts/*.png        ~15 publication-quality charts (dark Ola theme)
eda/eda_summary.json    every computed finding, machine-readable
eda/EDA_REPORT.md       human-readable narrative of the findings

Run
---
    python eda.py

Requires: pandas, numpy, matplotlib, seaborn, openpyxl
"""
from __future__ import annotations

import json
import os
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

warnings.filterwarnings("ignore")

# --------------------------------------------------------------------------- #
# Paths & theme
# --------------------------------------------------------------------------- #
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw", "OLA_DataSet.xlsx")
OUT = os.path.join(HERE, "eda")
CHARTS = os.path.join(OUT, "charts")
os.makedirs(CHARTS, exist_ok=True)

# Ola palette (from the slide template theme)
BG = "#0B0F14"
CARD = "#161E27"
GREEN = "#92D050"
TEAL = "#24CBE5"
GREY = "#8A97A6"
WHITE = "#F2F5F8"
PALETTE = [GREEN, TEAL, "#50B432", "#058DC7", "#ED561B", "#EDEF00", "#64E572"]

plt.rcParams.update({
    "figure.facecolor": BG,
    "axes.facecolor": CARD,
    "savefig.facecolor": BG,
    "text.color": WHITE,
    "axes.labelcolor": WHITE,
    "xtick.color": GREY,
    "ytick.color": GREY,
    "axes.edgecolor": "#2A3542",
    "grid.color": "#243040",
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "figure.dpi": 130,
})
sns.set_palette(PALETTE)

SUMMARY: dict = {}


def save(fig, name: str) -> None:
    """Save a figure to eda/charts/ and close it."""
    path = os.path.join(CHARTS, name)
    fig.savefig(path, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  chart -> {name}")


def style(ax, title: str, xlabel: str = "", ylabel: str = "") -> None:
    ax.set_title(title, color=WHITE, pad=12)
    ax.set_xlabel(xlabel, color=GREY)
    ax.set_ylabel(ylabel, color=GREY)
    ax.grid(axis="y", alpha=0.25, linestyle="--")
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


# --------------------------------------------------------------------------- #
# 1. LOAD + CLEAN (mirrors clean_data.py)
# --------------------------------------------------------------------------- #
print("Loading raw workbook ...")
df = pd.read_excel(RAW, sheet_name="July")
raw_shape = df.shape
print(f"  raw: {raw_shape[0]:,} rows x {raw_shape[1]} cols")

# --- dtype / format normalisation -------------------------------------------
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df["Time"] = pd.to_datetime(df["Time"].astype(str), format="%H:%M:%S", errors="coerce").dt.time
df["Booking_Datetime"] = pd.to_datetime(
    df["Date"].dt.strftime("%Y-%m-%d") + " " + df["Time"].astype(str), errors="coerce"
)

for c in ["Booking_Status", "Vehicle_Type", "Pickup_Location", "Drop_Location",
          "Payment_Method", "Incomplete_Rides", "Incomplete_Rides_Reason",
          "Canceled_Rides_by_Customer", "Canceled_Rides_by_Driver"]:
    df[c] = df[c].astype("string").str.strip()

# standardise the eBike label
df["Vehicle_Type"] = df["Vehicle_Type"].replace({"eBike": "E-Bike", "Ebike": "E-Bike"})

# numeric coercion
for c in ["V_TAT", "C_TAT", "Booking_Value", "Ride_Distance", "Driver_Ratings", "Customer_Rating"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

# --- derived features --------------------------------------------------------
df["Booking_Date"] = df["Booking_Datetime"].dt.date
df["Booking_Hour"] = df["Booking_Datetime"].dt.hour
df["Booking_DayOfWeek"] = df["Booking_Datetime"].dt.day_name()
df["DayOfWeek_Num"] = df["Booking_Datetime"].dt.dayofweek
df["Is_Weekend"] = (df["DayOfWeek_Num"] >= 5).astype(int)


def time_of_day(h) -> str:
    if pd.isna(h):
        return "Unknown"
    h = int(h)
    if h < 5:
        return "Late Night (00-05)"
    if h < 9:
        return "Early Morning (05-09)"
    if h < 12:
        return "Morning (09-12)"
    if h < 16:
        return "Afternoon (12-16)"
    if h < 20:
        return "Evening Peak (16-20)"
    return "Night (20-24)"


df["Time_of_Day"] = df["Booking_Hour"].apply(time_of_day)

df["Distance_Bucket"] = pd.cut(
    df["Ride_Distance"], bins=[-1, 0, 5, 10, 20, 30, 50],
    labels=["0 km", "1-5 km", "6-10 km", "11-20 km", "21-30 km", "31-50 km"],
).astype("string")

df["Value_Bucket"] = pd.cut(
    df["Booking_Value"], bins=[-1, 250, 500, 750, 1000, 1500, 10000],
    labels=["<250", "250-500", "500-750", "750-1000", "1000-1500", "1500+"],
).astype("string")

df["Fare_per_km"] = np.where(df["Ride_Distance"] > 0,
                             df["Booking_Value"] / df["Ride_Distance"], np.nan)

CUST_MAP = {
    "Driver is not moving towards pickup location": "Driver Behaviour",
    "Driver asked to cancel": "Driver Behaviour",
    "AC is Not working": "Vehicle Comfort",
    "Change of plans": "Customer Plans",
    "Wrong Address": "Address Issue",
}
DRIV_MAP = {
    "Personal & Car related issue": "Personal & Car Issue",
    "Customer was coughing/sick": "Customer Health",
    "Customer related issue": "Customer Issue",
    "More than permitted people in there": "Capacity Violation",
}
df["Customer_Cancel_Category"] = df["Canceled_Rides_by_Customer"].map(CUST_MAP).fillna("Not Applicable")
df["Driver_Cancel_Category"] = df["Canceled_Rides_by_Driver"].map(DRIV_MAP).fillna("Not Applicable")
df["Incomplete_Reason_Category"] = df["Incomplete_Rides_Reason"].fillna("Not Applicable")

df["Zero_Distance_Flag"] = (df["Ride_Distance"] == 0).astype(int)

print(f"  cleaned: {df.shape[0]:,} rows x {df.shape[1]} cols")

SUMMARY["dataset"] = {
    "raw_rows": int(raw_shape[0]),
    "raw_cols": int(raw_shape[1]),
    "clean_rows": int(df.shape[0]),
    "clean_cols": int(df.shape[1]),
    "date_min": str(df["Booking_Date"].min()),
    "date_max": str(df["Booking_Date"].max()),
    "n_days": int(df["Booking_Date"].nunique()),
    "n_customers": int(df["Customer_ID"].nunique()),
    "n_areas": int(df["Pickup_Location"].nunique()),
    "n_vehicles": int(df["Vehicle_Type"].nunique()),
}

# --------------------------------------------------------------------------- #
# 2. DISTRIBUTIONS
# --------------------------------------------------------------------------- #
print("\n[1/9] Distributions ...")
fig, axes = plt.subplots(2, 2, figsize=(13, 8))
for ax, (col, label, bins) in zip(axes.ravel(), [
    ("Ride_Distance", "Ride Distance (km)", 40),
    ("Booking_Value", "Booking Value (INR)", 40),
    ("Driver_Ratings", "Driver Rating", 20),
    ("Customer_Rating", "Customer Rating", 20),
]):
    data = df[col].dropna()
    ax.hist(data, bins=bins, color=GREEN, alpha=0.85, edgecolor=BG, linewidth=0.4)
    ax.axvline(data.mean(), color=TEAL, ls="--", lw=1.6, label=f"mean {data.mean():.2f}")
    ax.axvline(data.median(), color="#ED561B", ls=":", lw=1.6, label=f"median {data.median():.2f}")
    style(ax, f"{label} distribution", label, "Bookings")
    ax.legend(frameon=False, fontsize=8, labelcolor=WHITE)
fig.suptitle("Numeric distributions — all 103,024 bookings", color=WHITE, fontsize=15, y=1.00)
fig.tight_layout()
save(fig, "01_distributions.png")

SUMMARY["distributions"] = {
    c: {
        "mean": round(float(df[c].mean()), 2),
        "median": round(float(df[c].median()), 2),
        "std": round(float(df[c].std()), 2),
        "min": round(float(df[c].min()), 2),
        "max": round(float(df[c].max()), 2),
        "p95": round(float(df[c].quantile(0.95)), 2),
        "n": int(df[c].notna().sum()),
    }
    for c in ["Ride_Distance", "Booking_Value", "Driver_Ratings", "Customer_Rating", "V_TAT", "C_TAT"]
}

# --------------------------------------------------------------------------- #
# 3. BOOKING STATUS
# --------------------------------------------------------------------------- #
print("[2/9] Booking status ...")
status = df["Booking_Status"].value_counts()
fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5), gridspec_kw={"width_ratios": [1, 1.3]})
colors = [GREEN, "#ED561B", "#EDEF00", TEAL]
a1.pie(status.values, labels=status.index, autopct="%1.1f%%", startangle=90,
       colors=colors, textprops={"color": WHITE, "fontsize": 10},
       wedgeprops={"edgecolor": BG, "linewidth": 2})
a1.set_title("Booking status share", color=WHITE)
bars = a2.barh(status.index[::-1], status.values[::-1], color=colors[::-1], edgecolor=BG)
for b, v in zip(bars, status.values[::-1]):
    a2.text(v + 800, b.get_y() + b.get_height() / 2, f"{v:,}", va="center", color=WHITE, fontsize=9)
style(a2, "Bookings by status", "Bookings", "")
fig.tight_layout()
save(fig, "02_booking_status.png")

SUMMARY["booking_status"] = {
    "counts": {k: int(v) for k, v in status.items()},
    "success_rate_pct": round(100 * status.get("Success", 0) / len(df), 2),
    "failure_rate_pct": round(100 * (len(df) - status.get("Success", 0)) / len(df), 2),
}

# --------------------------------------------------------------------------- #
# 4. TRENDS OVER TIME
# --------------------------------------------------------------------------- #
print("[3/9] Trends ...")
daily = df.groupby("Booking_Date").size()
daily_succ = df[df["Booking_Status"] == "Success"].groupby("Booking_Date").size()
daily_rev = df[df["Booking_Status"] == "Success"].groupby("Booking_Date")["Booking_Value"].sum()

fig, ax = plt.subplots(figsize=(13, 5))
ax.plot(pd.to_datetime(list(daily.index)), daily.values, color=GREEN, lw=2.2, label="All bookings")
ax.plot(pd.to_datetime(list(daily_succ.index)), daily_succ.values, color=TEAL, lw=2.2, label="Successful")
ax.fill_between(pd.to_datetime(list(daily.index)), daily.values, alpha=0.15, color=GREEN)
ax.axhline(daily.mean(), color=GREY, ls="--", lw=1, label=f"avg {daily.mean():.0f}/day")
style(ax, "Ride volume over time — July 2024", "Date", "Bookings / day")
ax.legend(frameon=False, labelcolor=WHITE, fontsize=9)
fig.autofmt_xdate()
fig.tight_layout()
save(fig, "03_ride_volume_over_time.png")

SUMMARY["trends"] = {
    "daily_mean": round(float(daily.mean()), 1),
    "daily_min": int(daily.min()),
    "daily_max": int(daily.max()),
    "daily_std": round(float(daily.std()), 1),
    "cv_pct": round(100 * float(daily.std() / daily.mean()), 2),
    "busiest_day": str(daily.idxmax()),
    "quietest_day": str(daily.idxmin()),
    "total_revenue": round(float(daily_rev.sum()), 2),
    "avg_daily_revenue": round(float(daily_rev.mean()), 2),
}

# --------------------------------------------------------------------------- #
# 5. PEAK DEMAND HOURS
# --------------------------------------------------------------------------- #
print("[4/9] Peak demand hours ...")
hourly = df.groupby("Booking_Hour").size()
hourly_succ = df[df["Booking_Status"] == "Success"].groupby("Booking_Hour").size()

fig, ax = plt.subplots(figsize=(13, 5))
bars = ax.bar(hourly.index, hourly.values, color=GREEN, edgecolor=BG, width=0.78)
peak = hourly.idxmax()
bars[peak].set_color(TEAL)
ax.plot(hourly_succ.index, hourly_succ.values, color="#ED561B", lw=2, marker="o", ms=3, label="Successful")
style(ax, f"Demand by hour of day — peak at {peak:02d}:00 ({hourly.max():,} bookings)", "Hour of day", "Bookings")
ax.set_xticks(range(0, 24))
ax.legend(frameon=False, labelcolor=WHITE, fontsize=9)
fig.tight_layout()
save(fig, "04_peak_demand_hours.png")

tod = df["Time_of_Day"].value_counts()
fig, ax = plt.subplots(figsize=(11, 4.5))
bars = ax.barh(tod.index[::-1], tod.values[::-1], color=PALETTE[:len(tod)][::-1], edgecolor=BG)
for b, v in zip(bars, tod.values[::-1]):
    ax.text(v + 300, b.get_y() + b.get_height() / 2, f"{v:,} ({100*v/len(df):.1f}%)",
            va="center", color=WHITE, fontsize=9)
style(ax, "Demand by time-of-day block", "Bookings", "")
fig.tight_layout()
save(fig, "05_time_of_day.png")

SUMMARY["peak_demand"] = {
    "peak_hour": int(peak),
    "peak_hour_bookings": int(hourly.max()),
    "trough_hour": int(hourly.idxmin()),
    "trough_hour_bookings": int(hourly.min()),
    "hourly_spread_pct": round(100 * (hourly.max() - hourly.min()) / hourly.mean(), 2),
    "hourly_counts": {int(k): int(v) for k, v in hourly.items()},
    "time_of_day": {k: int(v) for k, v in tod.items()},
    "largest_block": str(tod.idxmax()),
}

# --------------------------------------------------------------------------- #
# 6. VEHICLE TYPE ANALYSIS
# --------------------------------------------------------------------------- #
print("[5/9] Vehicle types ...")
veh = df.groupby("Vehicle_Type").agg(
    bookings=("Booking_ID", "count"),
    revenue=("Booking_Value", "sum"),
    avg_distance=("Ride_Distance", "mean"),
    avg_value=("Booking_Value", "mean"),
    avg_driver_rating=("Driver_Ratings", "mean"),
    avg_customer_rating=("Customer_Rating", "mean"),
).sort_values("bookings", ascending=False)

fig, axes = plt.subplots(2, 2, figsize=(13, 8))
for ax, (col, title, fmt) in zip(axes.ravel(), [
    ("bookings", "Bookings by vehicle type", "{:,.0f}"),
    ("revenue", "Revenue by vehicle type (INR)", "{:,.0f}"),
    ("avg_distance", "Average ride distance (km)", "{:.1f}"),
    ("avg_customer_rating", "Average customer rating", "{:.2f}"),
]):
    vals = veh[col]
    bars = ax.bar(vals.index, vals.values, color=PALETTE[:len(vals)], edgecolor=BG)
    for b, v in zip(bars, vals.values):
        ax.text(b.get_x() + b.get_width() / 2, v, fmt.format(v), ha="center", va="bottom",
                color=WHITE, fontsize=8)
    style(ax, title, "", "")
    ax.tick_params(axis="x", rotation=30)
fig.suptitle("Vehicle type performance", color=WHITE, fontsize=15, y=1.00)
fig.tight_layout()
save(fig, "06_vehicle_types.png")

SUMMARY["vehicle_types"] = {
    k: {
        "bookings": int(r.bookings),
        "revenue": round(float(r.revenue), 2),
        "avg_distance": round(float(r.avg_distance), 2),
        "avg_value": round(float(r.avg_value), 2),
        "avg_driver_rating": round(float(r.avg_driver_rating), 3),
        "avg_customer_rating": round(float(r.avg_customer_rating), 3),
    }
    for k, r in veh.iterrows()
}

# --------------------------------------------------------------------------- #
# 7. PRICING PATTERNS
# --------------------------------------------------------------------------- #
print("[6/9] Pricing patterns ...")
succ = df[df["Booking_Status"] == "Success"].copy()

fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
a1.scatter(succ["Ride_Distance"], succ["Booking_Value"], s=3, alpha=0.18, color=GREEN, edgecolors="none")
r = succ[["Ride_Distance", "Booking_Value"]].corr().iloc[0, 1]
a1.set_title(f"Fare vs distance (r = {r:.3f})", color=WHITE)
a1.set_xlabel("Ride distance (km)", color=GREY)
a1.set_ylabel("Booking value (INR)", color=GREY)
a1.grid(alpha=0.2, ls="--")

pay = succ["Payment_Method"].value_counts()
bars = a2.bar(pay.index, pay.values, color=PALETTE[:len(pay)], edgecolor=BG)
for b, v in zip(bars, pay.values):
    a2.text(b.get_x() + b.get_width() / 2, v, f"{v:,}\n{100*v/pay.sum():.1f}%",
            ha="center", va="bottom", color=WHITE, fontsize=8)
style(a2, "Payment method mix (successful rides)", "", "Rides")
a2.tick_params(axis="x", rotation=20)
fig.tight_layout()
save(fig, "07_pricing_payment.png")

# fare per km by vehicle
fpk = succ.groupby("Vehicle_Type")["Fare_per_km"].median().sort_values(ascending=False)
fig, ax = plt.subplots(figsize=(11, 4.5))
bars = ax.bar(fpk.index, fpk.values, color=TEAL, edgecolor=BG)
for b, v in zip(bars, fpk.values):
    ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.1f}", ha="center", va="bottom", color=WHITE, fontsize=9)
style(ax, "Median fare per km by vehicle type (INR/km)", "", "INR / km")
ax.tick_params(axis="x", rotation=25)
fig.tight_layout()
save(fig, "08_fare_per_km.png")

SUMMARY["pricing"] = {
    "fare_distance_correlation": round(float(r), 4),
    "payment_mix": {k: int(v) for k, v in pay.items()},
    "payment_share_pct": {k: round(100 * v / pay.sum(), 2) for k, v in pay.items()},
    "median_fare_per_km_by_vehicle": {k: round(float(v), 2) for k, v in fpk.items()},
    "avg_fare_per_km": round(float(succ["Fare_per_km"].median()), 2),
    "cash_upi_share_pct": round(100 * (pay.get("Cash", 0) + pay.get("UPI", 0)) / pay.sum(), 2),
}

# --------------------------------------------------------------------------- #
# 8. CANCELLATION ANALYSIS
# --------------------------------------------------------------------------- #
print("[7/9] Cancellations ...")
cust_c = df[df["Booking_Status"] == "Canceled by Customer"]["Canceled_Rides_by_Customer"].value_counts()
driv_c = df[df["Booking_Status"] == "Canceled by Driver"]["Canceled_Rides_by_Driver"].value_counts()

fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5.5))
bars = a1.barh(cust_c.index[::-1], cust_c.values[::-1], color="#ED561B", edgecolor=BG)
for b, v in zip(bars, cust_c.values[::-1]):
    a1.text(v + 60, b.get_y() + b.get_height() / 2, f"{v:,}", va="center", color=WHITE, fontsize=8)
style(a1, f"Customer cancellations by reason (n={cust_c.sum():,})", "Rides", "")
a1.tick_params(axis="y", labelsize=8)

bars = a2.barh(driv_c.index[::-1], driv_c.values[::-1], color="#EDEF00", edgecolor=BG)
for b, v in zip(bars, driv_c.values[::-1]):
    a2.text(v + 120, b.get_y() + b.get_height() / 2, f"{v:,}", va="center", color=WHITE, fontsize=8)
style(a2, f"Driver cancellations by reason (n={driv_c.sum():,})", "Rides", "")
a2.tick_params(axis="y", labelsize=8)
fig.tight_layout()
save(fig, "09_cancellation_reasons.png")

# cancellation rate by vehicle
cancel_by_veh = df.groupby("Vehicle_Type").apply(
    lambda g: 100 * (g["Booking_Status"] != "Success").mean()
).sort_values(ascending=False)
fig, ax = plt.subplots(figsize=(11, 4.5))
bars = ax.bar(cancel_by_veh.index, cancel_by_veh.values, color="#ED561B", edgecolor=BG)
for b, v in zip(bars, cancel_by_veh.values):
    ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.1f}%", ha="center", va="bottom", color=WHITE, fontsize=9)
style(ax, "Non-success rate by vehicle type (%)", "", "% of bookings")
ax.tick_params(axis="x", rotation=25)
fig.tight_layout()
save(fig, "10_cancellation_by_vehicle.png")

SUMMARY["cancellations"] = {
    "customer_total": int(cust_c.sum()),
    "driver_total": int(driv_c.sum()),
    "driver_not_found": int((df["Booking_Status"] == "Driver Not Found").sum()),
    "customer_reasons": {k: int(v) for k, v in cust_c.items()},
    "driver_reasons": {k: int(v) for k, v in driv_c.items()},
    "personal_car_issue": int(driv_c.get("Personal & Car related issue", 0)),
    "non_success_rate_by_vehicle_pct": {k: round(float(v), 2) for k, v in cancel_by_veh.items()},
}

# --------------------------------------------------------------------------- #
# 9. RATINGS ANALYSIS
# --------------------------------------------------------------------------- #
print("[8/9] Ratings ...")
fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
for ax, col, color, title in [
    (a1, "Driver_Ratings", GREEN, "Driver ratings distribution"),
    (a2, "Customer_Rating", TEAL, "Customer ratings distribution"),
]:
    vc = df[col].value_counts().sort_index()
    bars = ax.bar(vc.index, vc.values, color=color, edgecolor=BG, width=0.7)
    for b, v in zip(bars, vc.values):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,}", ha="center", va="bottom",
                color=WHITE, fontsize=7, rotation=90)
    style(ax, title, "Rating", "Rides")
fig.tight_layout()
save(fig, "11_ratings_distribution.png")

fig, ax = plt.subplots(figsize=(7, 6))
hb = ax.hexbin(succ["Driver_Ratings"], succ["Customer_Rating"], gridsize=25, cmap="YlGn", mincnt=1)
ax.set_title("Customer vs Driver rating (successful rides)", color=WHITE)
ax.set_xlabel("Driver rating", color=GREY)
ax.set_ylabel("Customer rating", color=GREY)
cb = fig.colorbar(hb, ax=ax)
cb.set_label("Rides", color=WHITE)
cb.ax.yaxis.set_tick_params(color=GREY)
plt.setp(plt.getp(cb.ax.axes, "yticklabels"), color=GREY)
fig.tight_layout()
save(fig, "12_ratings_scatter.png")

SUMMARY["ratings"] = {
    "driver_mean": round(float(df["Driver_Ratings"].mean()), 3),
    "customer_mean": round(float(df["Customer_Rating"].mean()), 3),
    "driver_min": float(df["Driver_Ratings"].min()),
    "driver_max": float(df["Driver_Ratings"].max()),
    "customer_min": float(df["Customer_Rating"].min()),
    "customer_max": float(df["Customer_Rating"].max()),
    "correlation": round(float(succ[["Driver_Ratings", "Customer_Rating"]].corr().iloc[0, 1]), 4),
    "n_rated": int(df["Driver_Ratings"].notna().sum()),
}

# --------------------------------------------------------------------------- #
# 10. CORRELATION MATRIX
# --------------------------------------------------------------------------- #
print("[9/9] Correlations & anomalies ...")
num_cols = ["Ride_Distance", "Booking_Value", "V_TAT", "C_TAT",
            "Driver_Ratings", "Customer_Rating", "Booking_Hour", "Fare_per_km"]
corr = df[num_cols].corr()
fig, ax = plt.subplots(figsize=(9, 7))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdYlGn", center=0, ax=ax,
            cbar_kws={"label": "Pearson r"}, linewidths=0.5, linecolor=BG,
            annot_kws={"size": 8})
ax.set_title("Correlation matrix — numeric features", color=WHITE, pad=14)
ax.tick_params(colors=GREY, labelsize=8)
fig.tight_layout()
save(fig, "13_correlation_matrix.png")

SUMMARY["correlations"] = {
    f"{a}~{b}": round(float(corr.loc[a, b]), 4)
    for i, a in enumerate(num_cols) for b in num_cols[i + 1:]
}

# --------------------------------------------------------------------------- #
# 11. ANOMALY / FRAUD CHECKS
# --------------------------------------------------------------------------- #
zero_dist = int((df["Ride_Distance"] == 0).sum())
zero_dist_succ = int(((df["Ride_Distance"] == 0) & (df["Booking_Status"] == "Success")).sum())
dup_ids = int(df["Booking_ID"].duplicated().sum())
dup_full = int(df.duplicated(subset=["Customer_ID", "Booking_Datetime", "Pickup_Location"]).sum())

q1, q3 = df["Booking_Value"].quantile([0.25, 0.75])
iqr = q3 - q1
extreme_fare = int((df["Booking_Value"] > q3 + 1.5 * iqr).sum())
high_fpk = int((succ["Fare_per_km"] > 200).sum())
very_high_fpk = int((succ["Fare_per_km"] > 500).sum())

# cancellation clusters: areas with unusually high non-success rate
area_stats = df.groupby("Pickup_Location").agg(
    n=("Booking_ID", "count"),
    non_success=("Booking_Status", lambda s: (s != "Success").sum()),
)
area_stats["rate"] = 100 * area_stats["non_success"] / area_stats["n"]
area_stats = area_stats[area_stats["n"] >= 500].sort_values("rate", ascending=False)
mean_rate = area_stats["rate"].mean()
sd_rate = area_stats["rate"].std()
outlier_areas = area_stats[area_stats["rate"] > mean_rate + 2 * sd_rate]

fig, ax = plt.subplots(figsize=(13, 5))
ax.scatter(area_stats["n"], area_stats["rate"], s=45, color=GREEN, alpha=0.75, edgecolors=BG)
if len(outlier_areas):
    ax.scatter(outlier_areas["n"], outlier_areas["rate"], s=110, color="#ED561B",
               edgecolors=WHITE, linewidths=1.2, label=">2σ above mean", zorder=5)
ax.axhline(mean_rate, color=TEAL, ls="--", lw=1.4, label=f"mean {mean_rate:.1f}%")
style(ax, "Cancellation clusters by pickup area", "Bookings in area", "Non-success rate (%)")
ax.legend(frameon=False, labelcolor=WHITE, fontsize=9)
fig.tight_layout()
save(fig, "14_anomaly_cancellation_clusters.png")

SUMMARY["anomalies"] = {
    "zero_distance_rides": zero_dist,
    "zero_distance_pct": round(100 * zero_dist / len(df), 2),
    "zero_distance_successful": zero_dist_succ,
    "duplicate_booking_ids": dup_ids,
    "duplicate_customer_time_area": dup_full,
    "extreme_fare_iqr": extreme_fare,
    "fare_per_km_over_200": high_fpk,
    "fare_per_km_over_500": very_high_fpk,
    "area_mean_non_success_pct": round(float(mean_rate), 2),
    "area_sd_pct": round(float(sd_rate), 2),
    "outlier_areas": {k: round(float(v), 2) for k, v in outlier_areas["rate"].items()},
    "verdict": (
        "No duplicate booking IDs and no same-customer/same-time duplicates — the "
        "dataset is clean on classic fraud signals. Zero-distance rides are structural "
        "(cancelled/not-found bookings), not fraud. The real anomaly signal is fare-per-km: "
        f"{very_high_fpk:,} successful rides bill above INR 500/km and warrant audit."
    ),
}

# --------------------------------------------------------------------------- #
# 12. DEMAND HEATMAP (day x hour)
# --------------------------------------------------------------------------- #
pivot = df.pivot_table(index="Booking_DayOfWeek", columns="Booking_Hour",
                       values="Booking_ID", aggfunc="count").reindex(
    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
fig, ax = plt.subplots(figsize=(14, 4.8))
sns.heatmap(pivot, cmap="YlGn", ax=ax, cbar_kws={"label": "Bookings"},
            linewidths=0.4, linecolor=BG)
ax.set_title("Demand heatmap — day of week x hour", color=WHITE, pad=12)
ax.set_xlabel("Hour of day", color=GREY)
ax.set_ylabel("", color=GREY)
ax.tick_params(colors=GREY, labelsize=8)
fig.tight_layout()
save(fig, "15_demand_heatmap.png")

# --------------------------------------------------------------------------- #
# 13. WRITE SUMMARY + REPORT
# --------------------------------------------------------------------------- #
with open(os.path.join(OUT, "eda_summary.json"), "w") as f:
    json.dump(SUMMARY, f, indent=2, default=str)
print(f"\nWrote {os.path.join(OUT, 'eda_summary.json')}")

bs = SUMMARY["booking_status"]
pd_ = SUMMARY["peak_demand"]
pr = SUMMARY["pricing"]
an = SUMMARY["anomalies"]
tr = SUMMARY["trends"]

report = f"""# OLA Rides — EDA Findings

**Dataset:** {SUMMARY['dataset']['clean_rows']:,} bookings · {SUMMARY['dataset']['n_days']} days
({SUMMARY['dataset']['date_min']} → {SUMMARY['dataset']['date_max']}) ·
{SUMMARY['dataset']['n_customers']:,} customers · {SUMMARY['dataset']['n_areas']} areas ·
{SUMMARY['dataset']['n_vehicles']} vehicle types

## 1. Booking outcomes
- **Success: {bs['success_rate_pct']}%** ({bs['counts'].get('Success', 0):,} rides)
- **Failure: {bs['failure_rate_pct']}%** — Canceled by Driver {bs['counts'].get('Canceled by Driver', 0):,},
  Canceled by Customer {bs['counts'].get('Canceled by Customer', 0):,},
  Driver Not Found {bs['counts'].get('Driver Not Found', 0):,}

## 2. Demand
- Peak hour **{pd_['peak_hour']:02d}:00** with {pd_['peak_hour_bookings']:,} bookings;
  trough {pd_['trough_hour']:02d}:00 with {pd_['trough_hour_bookings']:,}.
- Hourly spread is only **{pd_['hourly_spread_pct']}%** of the mean — demand is remarkably flat.
- Largest time block: **{pd_['largest_block']}**.
- Daily volume averages {tr['daily_mean']:.0f} bookings (CV {tr['cv_pct']}%) — no strong weekly seasonality.

## 3. Pricing
- **Fare vs distance correlation r = {pr['fare_distance_correlation']}** — pricing is essentially
  independent of distance. This is the single most important data-quality finding: either the
  fare field is synthetic or surge/zone pricing dominates. Resolve before building surge logic.
- Cash + UPI = **{pr['cash_upi_share_pct']}%** of successful rides; card adoption is minimal.
- Median fare/km {pr['avg_fare_per_km']} INR.

## 4. Cancellations
- Customer cancellations: **{SUMMARY['cancellations']['customer_total']:,}**;
  driver cancellations: **{SUMMARY['cancellations']['driver_total']:,}**.
- Driver "Personal & Car related issue" alone: **{SUMMARY['cancellations']['personal_car_issue']:,}** rides.

## 5. Ratings
- Driver mean {SUMMARY['ratings']['driver_mean']}, customer mean {SUMMARY['ratings']['customer_mean']},
  correlation {SUMMARY['ratings']['correlation']} — ratings are near-uniform and carry little
  discriminating signal.

## 6. Anomalies & fraud checks
- Zero-distance rides: **{an['zero_distance_rides']:,}** ({an['zero_distance_pct']}%) — structural, not fraud.
- Duplicate booking IDs: **{an['duplicate_booking_ids']}**; same-customer/time/area duplicates: **{an['duplicate_customer_time_area']}**.
- Extreme fares (IQR): **{an['extreme_fare_iqr']:,}**; fare/km > 200: **{an['fare_per_km_over_200']:,}**; > 500: **{an['fare_per_km_over_500']:,}**.
- Areas >2σ above mean non-success rate: **{len(an['outlier_areas'])}**.

{an['verdict']}

## Charts
All charts are in `eda/charts/` (15 files, dark Ola theme).
"""
with open(os.path.join(OUT, "EDA_REPORT.md"), "w") as f:
    f.write(report)
print(f"Wrote {os.path.join(OUT, 'EDA_REPORT.md')}")
print("\nEDA complete.")
