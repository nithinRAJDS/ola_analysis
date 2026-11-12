# OLA Rides — EDA Findings

**Dataset:** 103,024 bookings · 31 days
(2024-07-01 → 2024-07-31) ·
94,544 customers · 50 areas ·
7 vehicle types

## 1. Booking outcomes
- **Success: 62.09%** (63,967 rides)
- **Failure: 37.91%** — Canceled by Driver 18,434,
  Canceled by Customer 10,499,
  Driver Not Found 10,124

## 2. Demand
- Peak hour **12:00** with 4,408 bookings;
  trough 18:00 with 4,176.
- Hourly spread is only **5.4%** of the mean — demand is remarkably flat.
- Largest time block: **Late Night (00-05)**.
- Daily volume averages 3323 bookings (CV 2.12%) — no strong weekly seasonality.

## 3. Pricing
- **Fare vs distance correlation r = 0.0019** — pricing is essentially
  independent of distance. This is the single most important data-quality finding: either the
  fare field is synthetic or surge/zone pricing dominates. Resolve before building surge logic.
- Cash + UPI = **95.21%** of successful rides; card adoption is minimal.
- Median fare/km 20.35 INR.

## 4. Cancellations
- Customer cancellations: **10,499**;
  driver cancellations: **18,434**.
- Driver "Personal & Car related issue" alone: **6,542** rides.

## 5. Ratings
- Driver mean 3.997, customer mean 3.998,
  correlation -0.0028 — ratings are near-uniform and carry little
  discriminating signal.

## 6. Anomalies & fraud checks
- Zero-distance rides: **39,057** (37.91%) — structural, not fraud.
- Duplicate booking IDs: **0**; same-customer/time/area duplicates: **0**.
- Extreme fares (IQR): **8,468**; fare/km > 200: **3,591**; > 500: **889**.
- Areas >2σ above mean non-success rate: **1**.

No duplicate booking IDs and no same-customer/same-time duplicates — the dataset is clean on classic fraud signals. Zero-distance rides are structural (cancelled/not-found bookings), not fraud. The real anomaly signal is fare-per-km: 889 successful rides bill above INR 500/km and warrant audit.

## Charts
All charts are in `eda/charts/` (15 files, dark Ola theme).
