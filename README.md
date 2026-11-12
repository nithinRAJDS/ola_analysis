# 🚕 OLA Rides Analytics — Complete Data Analysis Deliverable

End-to-end analytics on **103,024 Ola bookings** (Bengaluru, July 2024): cleaning, EDA,
SQL, a black-and-green Streamlit app, a Power BI kit, a slide deck and a written report.

---

## 1. What's inside

```
ola_deliverable_v5/
├── raw/
│   └── OLA_DataSet.xlsx            # source workbook (sheet 'July')
├── data/
│   ├── ola_cleaned.csv             # cleaned dataset (103,024 × 37)
│   ├── ola_cleaned.sqlite          # same data as SQLite
│   ├── cleaning_log.md             # every cleaning step, auditable
│   ├── quality_scorecard.json      # before/after data-quality metrics
│   ├── profile_before.json         # raw column profile
│   ├── profile_after.json          # cleaned column profile
│   └── sql_results.json            # captured outputs of the 10 SQL questions
├── clean_data.py                   # profiling → cleaning → feature engineering
├── eda.py                          # standalone EDA (all 103k rows, 15 charts)
├── eda/
│   ├── charts/                     # 15 dark-themed PNG charts
│   ├── eda_summary.json            # every computed finding
│   └── EDA_REPORT.md               # narrative of the findings
├── sql/
│   ├── queries.sql                 # 10 required + bonus queries, commented
│   └── SQL_RESULTS.md              # query → answer → validation table
├── app/                            # Streamlit app
│   ├── app.py                      # 11-page black/green app
│   ├── nl2sql.py                   # NL→SQL engine (LLM + rule-based)
│   ├── build_db.py                 # CSV → ola.db
│   ├── test_nl2sql.py              # 67-question test suite
│   ├── TEST_REPORT.md              # test results
│   ├── requirements.txt
│   ├── .streamlit/config.toml      # dark native theme
│   └── assets/ppt/                 # images extracted from Ola-Slides.pptx
│       ├── ola_logo.png            # wide logo (hero)
│       ├── ola_logo_square.png     # square logo (sidebar)
│       ├── vehicles/               # 7 vehicle icons + fallback
│       └── icons/                  # chart, rupee, cancellation, rating, vehicle
├── powerbi/
│   ├── POWERBI_BUILD_GUIDE.md      # step-by-step 5-page build
│   ├── theme.json                  # Ola palette theme
│   ├── dax_measures.md             # copy-paste DAX
│   ├── dashboard_mockup.html       # static 5-page mockup
│   └── ola_pbit_template.md        # .pbit template spec
├── report/
│   ├── ANALYSIS_REPORT.md
│   └── BUSINESS_INSIGHTS.md
└── README.md
```

---

## 2. Quick start

### 2.1 Rebuild the data (optional — outputs are committed)

```bash
pip install pandas numpy openpyxl matplotlib seaborn
python clean_data.py          # raw/ → data/ola_cleaned.csv + scorecard + log
```

### 2.2 Run the EDA

```bash
python eda.py                 # → eda/charts/*.png, eda/eda_summary.json, eda/EDA_REPORT.md
```

### 2.3 Run the Streamlit app

```bash
cd app
pip install -r requirements.txt
python build_db.py            # data/ola_cleaned.csv → app/ola.db
streamlit run app.py
```

Open <http://localhost:8501>.

### 2.4 Run the NL engine tests

```bash
cd app
python test_nl2sql.py         # 67 questions → pass/fail + generated SQL
```

---

## 3. The Streamlit app

### 3.1 Page structure (11 pages, Prev/Next wizard)

| # | Page | Contents |
|---|------|----------|
| 1 | **Overall** | Ride Volume Over Time · Booking Status Breakdown |
| 2 | **Vehicle Type** | Top 5 Vehicle Types by Ride Distance · Avg Customer Ratings · vehicle cards |
| 3 | **Revenue** | Revenue by Payment Method · Top 5 Customers by Booking Value · Distance per Day |
| 4 | **Cancellation** | Cancelled Rides Reasons (Customer) · (Driver) |
| 5 | **Ratings** | Driver Ratings · Customer Ratings · Customer vs Driver |
| 6 | **SQL Questions** | the 10 required questions, one-click ▶ Run, SQL toggle, CSV download |
| 7 | **Ask the Data** | free-text NL→SQL with conversation memory |
| 8 | **Data Explorer** | filters, free-text search, table, quick charts |
| 9 | **Power BI** | publish-to-web iframe with graceful fallback |
| 10 | **Data Quality** | scorecard, missingness, outlier flags, schema |
| 11 | **Audience Q&A** | 24 curated questions, one at a time, Prev/Next question |

Navigation: sidebar radio **or** the ← Previous / Next → buttons at the bottom of every
page, with a `Page N of 11` indicator and dot strip. Page, filters and the last question
all persist in `session_state`.

### 3.2 Theme

Black/near-black canvas (`#0B0F14`) with Ola green (`#92D050`) accents and a teal
(`#24CBE5`) secondary. Custom CSS in `app.py` plus a matching
`.streamlit/config.toml` so native widgets match. Gradient hero, glowing KPI cards,
rounded cards, hover lift, styled buttons/inputs/dataframes/sidebar.

### 3.3 Images from the PPT

All imagery is extracted from **`Ola-Slides.pptx`** into `app/assets/ppt/` — the Ola
logo (wide + square), the 7 vehicle icons and 5 UI icons. The deck's icons are black
line-art, so they are recoloured to the Ola palette (green vehicles, teal icons, white
logos) while keeping the exact original shapes. No generated art is substituted.

### 3.4 Filters

Persistent sidebar panel: **date range, vehicle type, booking status, payment method,
time of day, distance bucket, value bucket, driver-rating slider**. Implemented by
shadowing `bookings` with a filtered `TEMP VIEW`, so the question engine, the explorer
and every chart honour them. Active-filter chips + one-click **Reset** + live row count.

### 3.5 The question engine (`nl2sql.py`)

Two engines, chosen automatically:

* **LLM engine** — used when `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` or `GEMINI_API_KEY`
  is set. Schema-aware prompt (full schema, column descriptions, value samples,
  few-shot examples) → SELECT-only validation → execute → **one self-repair retry**
  on error.
* **Rule engine** — no key needed. Detects metric, group-by dimension, time grain,
  filters, ordering and limit independently, then assembles SQL. Covers counts, sums,
  averages, min/max, distinct counts, group-bys on any categorical column, filters on
  any column, top-N/bottom-N, trends (daily/weekly/hourly), shares and rates.

Fuzzy matching handles `bike`/`ebike`/`e-bike`, `prime sedan`/`sedan`, `cash`/`upi`,
`cancelled by driver`/`successful`/`completed`. Unmappable questions get a clear
message with rephrasing suggestions — never a silent wrong answer.

**Test result: 67/67 (100%)** — 63 in-scope + 4 out-of-scope guards. See
`app/TEST_REPORT.md`.

### 3.6 Optional API key

```bash
export OPENAI_API_KEY="sk-..."      # or ANTHROPIC_API_KEY / GEMINI_API_KEY
streamlit run app.py
```

Without a key the app runs fully on the rule engine.

---

## 4. Data cleaning

`clean_data.py` profiles the raw workbook, cleans it and engineers features.

| Metric | Before | After |
|---|---|---|
| Rows | 103,024 | 103,024 (0 dropped) |
| Columns | 20 | 37 |
| Completeness | 75.22% | 94.77% |
| Duplicate booking IDs | 0 | 0 |
| Unparseable dates | 0 | 0 |

**11 derived features:** `Booking_Hour`, `Booking_DayOfWeek`, `DayOfWeek_Num`,
`Is_Weekend`, `Time_of_Day`, `Distance_Bucket`, `Value_Bucket`, `Fare_per_km`,
`Customer_Cancel_Category`, `Driver_Cancel_Category`, `Incomplete_Reason_Category`
(+ `Zero_Distance_Flag` and IQR outlier flags).

**Design principle:** structural NULLs (ratings/TAT/payment on the 39,057 rides that
never happened) are **preserved, not imputed** — filling them would fabricate data.
Outliers are **flagged, not deleted**. Every step is logged in `data/cleaning_log.md`.

---

## 5. EDA highlights

`eda.py` runs on all 103,024 rows and all columns — no sampling. 15 charts in
`eda/charts/`, findings in `eda/eda_summary.json`.

* **Success rate 62.09%** — 37.9% of bookings never complete.
* **Demand is flat:** hourly spread only 5.6% of the mean; peak 12:00 (4,408 bookings).
  Late-night 00–05 is the *largest* time block (20.8%).
* **Fare vs distance r = 0.0019** — pricing is essentially independent of distance.
  The single most important data-quality finding; resolve before building surge logic.
* **Cash + UPI = 95.2%** of successful rides.
* **Ratings compressed** into 3.0–5.0 with means of 4.00; customer↔driver correlation
  ≈ 0.
* **Anomalies:** 0 duplicate booking IDs, 0 same-customer/time duplicates. Zero-distance
  rides (39,057) are structural, not fraud. 889 successful rides bill above ₹500/km —
  the real audit target.

---

## 6. Power BI

`powerbi/POWERBI_BUILD_GUIDE.md` covers the exact 5-page structure:

1. **Overall** — Ride Volume Over Time · Booking Status Breakdown
2. **Vehicle Type** — Top 5 Vehicle Types by Ride Distance
3. **Revenue** — Revenue by Payment Method · Top 5 Customers · Distance per Day
4. **Cancellation** — Cancelled Rides Reasons (Customer) · (Driver)
5. **Ratings** — Driver Ratings · Customer Ratings · Customer vs Driver

Includes Power Query steps, data model, visual-by-visual specs with pixel positions,
synced slicers, KPI cards, formatting and an acceptance test. Plus `theme.json`
(Ola palette), `dax_measures.md` (~40 measures) and `dashboard_mockup.html`
(a static 5-page mockup rendered with the real numbers).

---

## 7. Business insights

`report/BUSINESS_INSIGHTS.md` addresses the four use cases:

1. **Peak demand & driver allocation** — demand is flat, so reallocate rather than add
   headcount; late-night is the largest block and the least staffed.
2. **Customer behaviour for personalised marketing** — 8.41% repeat rate, max 5 bookings
   per customer; loyalty is an opportunity, not a moat.
3. **Pricing patterns & surge effectiveness** — r = 0.0019 means fare is not
   distance-driven; fix data governance before building surge.
4. **Anomaly / fraud detection** — clean on classic signals; 889 high fare-per-km rides
   to audit; stop flagging zero-distance rides.

**Biggest lever:** 18,434 driver cancellations (6,542 personal/car). Recovering half
≈ **+₹5.0M/month**.

---

## 8. Deployment (Streamlit Community Cloud)

1. Push this folder to a GitHub repo.
2. On <https://share.streamlit.io> → **New app** → pick the repo.
3. **Main file path:** `app/app.py`
4. **Requirements:** `app/requirements.txt`
5. (Optional) Add `OPENAI_API_KEY` under *Secrets*.
6. Deploy.

> `app/ola.db` is committed so the app works without a build step. To regenerate it,
> run `python app/build_db.py`.

---

## 9. Coding standards

* Type hints on public functions; docstrings on every module and non-trivial function.
* No fabricated data — structural NULLs preserved, outliers flagged not dropped.
* SQL is always SELECT-only and validated before execution.
* All chart styling centralised in `dbase()`; all colours in one palette block.
* `.gitignore` excludes caches, virtualenvs and the large raw workbook.

---

## 10. Data dictionary (key columns)

| Column | Type | Description |
|---|---|---|
| `Booking_ID` | TEXT | unique booking id |
| `Booking_Datetime` | TEXT | ISO timestamp |
| `Booking_Date` | TEXT | YYYY-MM-DD |
| `Booking_Hour` | INT | 0–23 |
| `Booking_DayOfWeek` | TEXT | Monday..Sunday |
| `Is_Weekend` | INT | 1 if Sat/Sun |
| `Time_of_Day` | TEXT | 6 blocks |
| `Booking_Status` | TEXT | Success / Canceled by Customer / Canceled by Driver / Driver Not Found |
| `Vehicle_Type` | TEXT | 7 classes |
| `Pickup_Location` / `Drop_Location` | TEXT | 50 Bengaluru areas |
| `Ride_Distance` | INT | km (0 for non-successful) |
| `Booking_Value` | INT | fare in INR |
| `Fare_per_km` | REAL | fare ÷ distance |
| `Payment_Method` | TEXT | Cash / UPI / Credit Card / Debit Card / Not Applicable |
| `Driver_Ratings` / `Customer_Rating` | REAL | 3.0–5.0 (NULL for non-success) |
| `V_TAT` / `C_TAT` | REAL | turnaround minutes (NULL for non-success) |
| `Incomplete_Rides` | TEXT | Yes / No |
| `*_Cancel_Category` | TEXT | normalised reason buckets |
