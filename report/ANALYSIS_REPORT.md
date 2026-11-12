# OLA Rides Analytics — Analysis Report
### July 2024 · Bengaluru · 103,024 bookings

**Prepared by:** Data Analysis Agent
**Dataset:** `OLA_DataSet.xlsx` (sheet `July`) — one row per Ola booking
**Deliverables in this package:** cleaned dataset (CSV + SQLite), Streamlit NL-Q&A app, Power BI build kit, slide deck, this report

---

## 1. Executive Summary

Ola's July-2024 Bengaluru operation processed **103,024 bookings** across **50 pickup areas** and **7 vehicle types**, generating **₹35.08 million** in revenue from **63,967 successful rides**. The headline issue is **service reliability**: only **62.1%** of bookings completed successfully — **37.9%** failed through customer cancellations (10,499), driver cancellations (18,434) or "driver not found" (10,124).

Demand is **remarkably uniform**: bookings are evenly spread across the month (~3,300/day), across all 50 areas (top-10 within ₹722k–₹777k), and across all 7 vehicle types (₹7.93M–₹8.30M). This is a mature, balanced marketplace — the growth levers are therefore **quality and monetisation**, not geographic expansion.

Three findings drive the recommendations:
1. **Driver-side cancellations are the single largest revenue leak** — 18,434 bookings (17.9% of all bookings) canceled by drivers.
2. **Digital payment adoption is low** — Cash + UPI account for **95.2%** of successful rides; cards are just 4.8%.
3. **Repeat rate is only 8.41%** — 94,544 unique customers but only 7,954 repeat riders, leaving retention largely untapped.

**Estimated opportunity:** recovering even half of driver-cancelled rides at the average fare of ₹548 would add **~₹5.0M/month** in revenue; a 5-point lift in repeat rate compounds this further.

---

## 2. Data Cleaning & Quality

### 2.1 What we found (raw profile)
| Issue | Detail |
|---|---|
| Shape | 103,024 rows × 20 columns |
| Missing values | 5 columns with **39,057** blanks each (V_TAT, C_TAT, Payment_Method, Driver_Ratings, Customer_Rating); cancellation-reason columns up to 99,098 blanks |
| Duplicates | 0 full-row duplicates; 0 duplicate Booking_IDs |
| Date/time | `Date` and `Time` stored separately — needed combining |
| Outliers | Booking_Value: 8,468 IQR outliers; 39,057 zero-distance records |
| Label inconsistency | `eBike` vs template's `E-Bike` |

### 2.2 Cleaning steps applied
1. Parsed `Date` + `Time` → **`Booking_Datetime`**; derived `Booking_Hour`, `Booking_DayOfWeek`, `Booking_Date`, `Is_Weekend`.
2. Trimmed whitespace on all categorical text columns.
3. Normalised **`eBike` → `E-Bike`**.
4. Filled `Incomplete_Rides` blanks → `"No"` (blank = completed ride).
5. Filled `Payment_Method` and cancellation/incomplete reasons → `"Not Applicable"` where structurally absent.
6. **Kept TAT / ratings as NULL** for non-successful rides — no fake imputation; added `Has_TAT` flag.
7. Computed **IQR outlier flags** on V_TAT, C_TAT, Booking_Value, Ride_Distance; added `Zero_Distance_Flag`.
8. De-duplicated on `Booking_ID` (0 removed).
9. Reordered to 29 analysis-ready columns.

### 2.3 Before / after scorecard
| Metric | Before | After |
|---|---|---|
| Rows | 103,024 | 103,024 (100% retained) |
| Columns | 20 | 29 |
| **Completeness** | **75.22%** | **94.77%** |
| Duplicate rows | 0 | 0 |
| Unparseable datetimes | — | 0 |
| Outlier flags added | — | 8,468 (Booking_Value) |
| Zero-distance flags | — | 39,057 |

> **Note on structural missingness:** the remaining 5.2% "missing" is *by design* — TAT, ratings and payment method only exist for successful rides. These are retained as NULL so downstream analysis can filter cleanly rather than being polluted by imputed values.

---

## 3. Key Findings

### 3.1 Overall KPIs
| KPI | Value |
|---|---|
| Total bookings | 103,024 |
| Successful bookings | 63,967 |
| **Success rate** | **62.09%** |
| Canceled by driver | 18,434 (17.9%) |
| Canceled by customer | 10,499 (10.2%) |
| Driver not found | 10,124 (9.8%) |
| **Total revenue** | **₹35,080,467** |
| Avg booking value | ₹548.42 |
| Avg ride distance | 22.85 km |
| Total distance | 1,461,903 km |
| Avg driver / customer rating | 4.00 / 4.00 |
| Avg V_TAT / C_TAT | 170.9 / 84.9 min |
| Unique customers | 94,544 |
| Repeat customers | 7,954 (**8.41%**) |
| Incomplete rides | 3,926 |

### 3.2 By vehicle type
| Vehicle | Bookings | Revenue | Success rate | Avg fare | Avg distance |
|---|---|---|---|---|---|
| Prime Sedan | 14,877 | ₹8,298,612 | 63.04% | ₹556.99 | 25.01 km |
| E-Bike | 14,816 | ₹8,181,523 | 61.96% | ₹550.62 | 25.15 km |
| Auto | 14,755 | ₹8,092,210 | 62.13% | ₹551.09 | 10.04 km |
| Prime Plus | 14,707 | ₹8,050,889 | 61.71% | ₹552.64 | 25.03 km |
| Mini | 14,552 | ₹7,990,996 | 62.09% | ₹540.72 | 24.98 km |
| Bike | 14,662 | ₹7,987,054 | 62.30% | ₹544.34 | 24.93 km |
| Prime SUV | 14,655 | ₹7,933,330 | 61.39% | ₹542.11 | 24.88 km |

**Insight:** revenue is almost perfectly balanced across the fleet (spread of just ₹365k between best and worst). **Prime Sedan** leads; **Prime SUV** trails on both revenue and success rate. Auto has a much shorter average distance (10 km) yet a comparable fare — a distinct short-hop use case.

### 3.3 By payment method (successful rides)
| Method | Rides | Revenue | Share |
|---|---|---|---|
| Cash | 35,022 | ₹19,260,316 | 54.75% |
| UPI | 25,881 | ₹14,168,436 | 40.46% |
| Credit Card | 2,435 | ₹1,312,793 | 3.81% |
| Debit Card | 629 | ₹338,922 | 0.98% |

**Insight:** **95.2% of rides are Cash + UPI.** Card payments are a clear, under-exploited channel.

### 3.4 By city (top 10 pickup areas)
| Area | Bookings | Revenue | Success rate | Avg fare |
|---|---|---|---|---|
| RT Nagar | 2,135 | ₹777,106 | 61.87% | ₹588.27 |
| Nagarbhavi | 2,083 | ₹773,073 | 62.46% | ₹594.21 |
| Banashankari | 2,201 | ₹771,628 | 62.02% | ₹565.30 |
| Yeshwanthpur | 2,139 | ₹748,319 | 63.25% | ₹553.08 |
| Frazer Town | 2,048 | ₹738,003 | 62.35% | ₹577.92 |
| Magadi Road | 2,099 | ₹734,480 | 62.98% | ₹555.58 |
| Ramamurthy Nagar | 2,116 | ₹731,591 | 63.23% | ₹546.78 |
| MG Road | 2,048 | ₹729,119 | 63.43% | ₹561.29 |
| Basavanagudi | 2,120 | ₹728,652 | 62.36% | ₹551.17 |
| BTM Layout | 2,091 | ₹721,656 | 61.74% | ₹558.99 |

**Insight:** demand is evenly distributed — no dominant hotspot. Success rates are uniform (~62%) city-wide, so the reliability problem is **systemic, not localised**.

### 3.5 Cancellation reasons
**By customer (10,499):** Driver not moving toward pickup (3,175) · Driver asked to cancel (2,670) · Change of plans (2,081) · AC not working (1,568) · Wrong address (1,005)

**By driver (18,434):** Personal & car-related issue (6,542) · Customer-related issue (5,413) · Customer coughing/sick (3,654) · More than permitted people (2,825)

**Incomplete rides (3,926):** Customer demand (1,601) · Vehicle breakdown (1,591) · Other (734)

**Insight:** the top customer reason ("driver not moving toward pickup") and the top driver reason ("personal & car-related issue") are both **operational** — addressable with better dispatch and driver accountability.

### 3.6 Time patterns
- **Peak hour: 12:00** (4,408 bookings) — midday is the busiest window.
- Daily volume is stable at ~3,300 bookings/day with no material spikes or dips across July.
- **Top route:** Majestic → Hennur (67 rides).

---

## 4. Recommendations

| # | Recommendation | Rationale | Expected impact |
|---|---|---|---|
| 1 | **Cut driver-side cancellations** — reliability incentives, penalties, and better dispatch for "driver not moving" cases | 18,434 driver cancellations + 3,175 "not moving" customer cancels | Recovering half ≈ **+₹5.0M/month** |
| 2 | **Grow digital payments** — card/wallet offers, cashback | Cash+UPI = 95.2% of rides | Lower cash-handling cost; enables loyalty |
| 3 | **Launch a retention programme** — loyalty tiers, ride credits | Repeat rate only 8.41% | Repeat riders are the cheapest growth |
| 4 | **Optimise supply by hour** — position drivers ahead of the noon peak | 12:00 is the busiest hour | Higher fulfilment, fewer "driver not found" |
| 5 | **Fix data capture** — record distance for failed rides | 39,057 zero-distance records | Sharper demand & pricing models |
| 6 | **A/B test pricing on Prime SUV** | Lowest revenue (₹7.93M) & success (61.4%) | Close the gap with Prime Sedan |

### Follow-up measurement plan
- Track **success rate**, **driver-cancellation rate**, **card share** and **repeat rate** weekly.
- Run the Prime SUV pricing test as a proper A/B experiment (power analysis, ≥2 weeks, guard against novelty effects).
- Re-run this pipeline monthly to monitor trend and validate the interventions.

---

## 5. Deliverables Index

| Deliverable | Location |
|---|---|
| Cleaned dataset (CSV) | `data/ola_cleaned.csv` |
| SQLite database | `app/ola.db` |
| Cleaning log & scorecard | `data/cleaning_log.md`, `data/quality_scorecard.json` |
| Streamlit app | `app/app.py`, `app/nl2sql.py`, `app/build_db.py`, `app/requirements.txt` |
| Power BI kit | `powerbi/POWERBI_BUILD_GUIDE.md`, `powerbi/ola_theme.json`, `powerbi/dax_measures.md`, `powerbi/ola_pbit_template.md` |
| Slide deck | `presentations/ola_rides_analytics/` |
| This report | `report/ANALYSIS_REPORT.md` |

---

*Analysis performed on the full July-2024 dataset (103,024 bookings, 100% of rows retained). All revenue figures are computed over successful rides only. Confidence: high for descriptive KPIs (full population, no sampling); the revenue-recovery estimate is an illustrative scenario, not a forecast.*
