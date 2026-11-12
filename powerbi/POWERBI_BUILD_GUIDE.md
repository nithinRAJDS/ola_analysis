# OLA Rides — Power BI Dashboard Build Guide

A complete, step-by-step guide to rebuilding the OLA Rides dashboard in Power BI
Desktop. Follow it top to bottom; every visual, measure, slicer and formatting
choice is specified so the result matches the design intent exactly.

**Companion files in this folder**

| File | Purpose |
|---|---|
| `theme.json` | Custom Power BI theme (Ola palette + Poppins) — import in step 2 |
| `dax_measures.md` | All DAX measures, copy-paste ready |
| `dashboard_mockup.html` | Static visual mockup of all 5 pages (open in a browser) |
| `ola_pbit_template.md` | `.pbit` template specification + acceptance test |

**Design system (from `Ola-Slides.pptx`)**

| Token | Value | Use |
|---|---|---|
| Navy | `#262626` | Titles, KPI numbers, sidebar |
| Green | `#92D050` | Primary accent, success, highlights |
| Blue | `#058DC7` | Secondary series, links |
| Orange | `#ED561B` | Alerts, cancellations, negative |
| Teal | `#24CBE5` | Tertiary series |
| Grey | `#AEAEAE` | Muted labels, "Not Applicable" |
| Page bg | `#F7F9FA` | Canvas background |
| Font | **Poppins** | All text (fallback: Segoe UI) |

---

## Step 1 — Import the data

1. Open **Power BI Desktop** → *Get Data* → **Text/CSV**.
2. Select `data/ola_cleaned.csv` (103,024 rows × 37 columns).
3. In the preview dialog set **File Origin = 65001: Unicode (UTF-8)** and
   **Delimiter = Comma**.
4. Click **Transform Data** (do *not* click Load yet — we clean in Power Query).

> **Why the CSV and not the xlsx?** The CSV is the *cleaned* output of
> `clean_data.py`: dates parsed, types coerced, derived features already built.
> Importing the raw xlsx would force you to redo all of that in M.

---

## Step 2 — Power Query cleaning steps

In the Power Query Editor, apply these steps in order. Each is a single ribbon
action, so the whole block is reproducible.

| # | Step | Ribbon action | Purpose |
|---|---|---|---|
| 1 | Promote headers | *Home → Use First Row as Headers* | Column names |
| 2 | Set data types | Select all → *Transform → Detect Data Type*, then fix below | Correct typing |
| 3 | `Booking_Datetime` | Type = **Date/Time** | Time intelligence |
| 4 | `Booking_Date` | Type = **Date** | Relate to Date table |
| 5 | `Booking_Hour`, `DayOfWeek_Num`, `Is_Weekend`, `Has_TAT`, `Zero_Distance_Flag`, `*_is_outlier` | Type = **Whole Number** | Numeric flags |
| 6 | `Ride_Distance`, `Booking_Value` | Type = **Whole Number** | Measures |
| 7 | `V_TAT`, `C_TAT`, `Driver_Ratings`, `Customer_Rating`, `Fare_per_km` | Type = **Decimal Number** | Averages |
| 8 | All text columns | Type = **Text**, *Transform → Format → Trim* | Consistency |
| 9 | `Vehicle_Type` | *Transform → Replace Values*: `eBike` → `E-Bike` (already done in CSV; keep as a guard) | Label match |
| 10 | `Payment_Method` | Replace `null` → `Not Applicable` | Structural nulls |
| 11 | `Incomplete_Rides` | Replace `null` → `No` | Structural nulls |
| 12 | `Canceled_Rides_by_Customer`, `Canceled_Rides_by_Driver`, `Incomplete_Rides_Reason` | Replace `null` → `Not Applicable` | Structural nulls |
| 13 | Remove duplicates | *Home → Remove Rows → Remove Duplicates* on `Booking_ID` | Uniqueness |
| 14 | Rename query | Right-click query → **Rename** → `bookings` | Model naming |
| 15 | Close & Apply | *Home → Close & Apply* | Load |

**Do NOT** delete rows where `Ride_Distance = 0` or ratings are null — those are
the 39,057 non-successful bookings and are required for the cancellation and
status visuals. They are flagged, not removed.

### Optional: add a Date table

*Modeling → New Table*:

```dax
Date =
ADDCOLUMNS (
    CALENDAR ( DATE ( 2024, 7, 1 ), DATE ( 2024, 7, 31 ) ),
    "Year", YEAR ( [Date] ),
    "Month", FORMAT ( [Date], "mmm" ),
    "MonthNum", MONTH ( [Date] ),
    "DayName", FORMAT ( [Date], "ddd" ),
    "WeekdayNum", WEEKDAY ( [Date], 2 )
)
```

Then *Table tools → Mark as date table* → `Date[Date]`.

---

## Step 3 — Data model & relationships

The model is intentionally a **single fact table** (`bookings`) plus an optional
`Date` dimension. There are no other tables to relate, which keeps every visual
fast and every filter unambiguous.

| From | To | Cardinality | Cross-filter |
|---|---|---|---|
| `Date[Date]` | `bookings[Booking_Date]` | 1 : * | Single |

**Model view checklist**

- [ ] `bookings` is the only fact table; `Date` is the only dimension.
- [ ] `Date[Date]` → `bookings[Booking_Date]` relationship exists, active, 1:*.
- [ ] `Date` is marked as a date table.
- [ ] No bidirectional relationships (keeps filter propagation predictable).
- [ ] Hide technical columns from Report view: `Vehicle Images`, `Has_TAT`,
      `*_is_outlier`, `DayOfWeek_Num`.

**Sort-by-column settings** (so charts order correctly):

| Column | Sort by |
|---|---|
| `Booking_DayOfWeek` | `DayOfWeek_Num` |
| `Value_Bucket` | `Booking_Value` (or a numeric helper) |
| `Distance_Bucket` | `Ride_Distance` (or a numeric helper) |
| `Time_of_Day` | a numeric helper 1–6 |

---

## Step 4 — DAX measures

Create a dedicated **`_Measures`** table (*Enter Data* → one dummy column →
hide it) and add every measure from `dax_measures.md` there. Grouping measures
in one table keeps the field list clean.

Minimum set for the 5 pages:

```
Bookings_Total, Bookings_Success, Bookings_SuccessRate,
Revenue_Total, Revenue_AvgFare, Revenue_Millions,
Distance_Total, Distance_Avg,
Cancellations_Customer, Cancellations_Driver,
Cancellations_Driver_PersonalCar, Cancellations_Total, Cancellations_Rate,
Ratings_Driver_Avg, Ratings_Customer_Avg, Rides_Rated,
Customers_Distinct, Customers_RepeatRate
```

---

## Step 5 — Report pages (visual-by-visual spec)

Canvas: **1280 × 720** (16:9). Page background `#F7F9FA`. Every page carries the
same header band and the same global slicer rail.

### Global elements (on every page)

| Element | Type | Position (x, y, w, h) | Spec |
|---|---|---|---|
| Header band | Rectangle | 0, 0, 1280, 64 | Fill `#262626`; title text white, Poppins 18 bold, left 24px |
| Page title | Text box | 24, 16, 700, 32 | White, Poppins 18 bold |
| Logo | Image | 1180, 12, 80, 40 | Ola logo (white) |
| Slicer rail | Rectangle | 0, 64, 200, 656 | Fill `#FFFFFF`, 1px border `#E6E6E6` |
| Slicer: Date | Slicer (between) | 12, 84, 176, 90 | `Date[Date]`, header "Date Range" |
| Slicer: Vehicle Type | Slicer (list) | 12, 190, 176, 200 | `bookings[Vehicle_Type]`, multi-select |
| Slicer: Payment Method | Slicer (list) | 12, 406, 176, 150 | `bookings[Payment_Method]` |
| Slicer: Booking Status | Slicer (list) | 12, 572, 176, 130 | `bookings[Booking_Status]` |

> **Sync slicers:** *View → Sync slicers* → tick all 5 pages for each slicer so a
> selection persists as the user navigates.

---

### Page 1 — Overall

**Purpose:** one-glance health of the month.

| # | Visual | Type | Position | Fields / measures | Formatting |
|---|---|---|---|---|---|
| 1 | Total Bookings | Card | 220, 84, 250, 100 | `Bookings_Total` | Callout 32 Poppins bold `#262626`; label "Total Bookings" |
| 2 | Success Rate | Card | 480, 84, 250, 100 | `Bookings_SuccessRate` (format %) | Green `#92D050` callout |
| 3 | Total Revenue | Card | 740, 84, 250, 100 | `Revenue_Total` (₹, 0 dp) | Navy callout |
| 4 | Avg Distance | Card | 1000, 84, 250, 100 | `Distance_Avg` (1 dp, " km") | Blue callout |
| 5 | **Ride Volume Over Time** | Line chart | 220, 200, 1030, 240 | Axis `Booking_Date`; Values `Bookings_Total` | Line `#058DC7` 2.5px, smooth off, markers off; data labels off; title "Ride Volume Over Time" |
| 6 | **Booking Status Breakdown** | Donut chart | 220, 456, 500, 250 | Legend `Booking_Status`; Values `Bookings_Total` | Colors: Success `#92D050`, Canceled by Driver `#ED561B`, Canceled by Customer `#EDEF00`, Driver Not Found `#AEAEAE`; detail labels = value + % |
| 7 | Status table | Table | 740, 456, 510, 250 | `Booking_Status`, `Bookings_Total`, `Bookings_SuccessRate` | Header `#262626` white text; alternating rows `#F7F9FA` |

---

### Page 2 — Vehicle Type

**Purpose:** which segments carry the most distance and how they compare.

| # | Visual | Type | Position | Fields / measures | Formatting |
|---|---|---|---|---|---|
| 1 | **Top 5 Vehicle Types by Ride Distance** | Clustered bar (horizontal) | 220, 84, 620, 300 | Axis `Vehicle_Type`; Values `Distance_Total`; **Filter: Top N = 5 by `Distance_Total`** | Bars `#058DC7`; data labels on, 0 dp; sorted descending; title as named |
| 2 | Avg Distance by Vehicle | Bar (horizontal) | 860, 84, 390, 300 | Axis `Vehicle_Type`; Values `Distance_Avg` | Bars `#92D050`; highlight Auto in `#ED561B` |
| 3 | Vehicle performance matrix | Matrix | 220, 400, 1030, 306 | Rows `Vehicle_Type`; Values `Bookings_Success`, `Distance_Avg`, `Revenue_AvgFare`, `Ratings_Customer_Avg` | Subtotals on; conditional formatting (data bars) on `Bookings_Success` |
| 4 | Distance bucket split | Stacked column | (optional, replaces 3 if space) | Axis `Distance_Bucket`; Values `Bookings_Total` | — |

**Key insight to annotate:** Auto averages ~10 km vs ~25 km for every other
type — a genuine short-trip segment, not a data error.

---

### Page 3 — Revenue

**Purpose:** where the money comes from and who spends it.

| # | Visual | Type | Position | Fields / measures | Formatting |
|---|---|---|---|---|---|
| 1 | Revenue KPI | Card | 220, 84, 320, 100 | `Revenue_Total` | ₹, 0 dp, navy |
| 2 | Avg Fare KPI | Card | 560, 84, 320, 100 | `Revenue_AvgFare` | ₹, 2 dp |
| 3 | **Revenue by Payment Method** | Clustered bar | 220, 200, 500, 250 | Axis `Payment_Method`; Values `Revenue_Total` | Bars `#058DC7`; data labels ₹; exclude "Not Applicable" via filter |
| 4 | **Top 5 Customers by Total Booking Value** | Table | 740, 200, 510, 250 | `Customer_ID`, `Revenue_Total`, `Bookings_Total`; **Top N = 5 by `Revenue_Total`** | Header navy; `Revenue_Total` right-aligned ₹ |
| 5 | **Ride Distance Distribution Per Day** | Column chart | 220, 470, 1030, 236 | Axis `Booking_Date`; Values `Distance_Total` | Columns `#24CBE5`; title as named |
| 6 | Payment mix donut | Donut | (optional) | `Payment_Method`; `Bookings_Success` | Cash `#058DC7`, UPI `#92D050`, Credit `#ED561B`, Debit `#24CBE5` |

**Key insight to annotate:** Cash + UPI = 95.2% of successful rides; card
adoption (4.8%) is the untapped monetisation lever.

---

### Page 4 — Cancellation

**Purpose:** quantify and diagnose the 37.9% of bookings that never complete.

| # | Visual | Type | Position | Fields / measures | Formatting |
|---|---|---|---|---|---|
| 1 | Total Cancellations | Card | 220, 84, 250, 100 | `Cancellations_Total` | Orange `#ED561B` |
| 2 | Cancellation Rate | Card | 480, 84, 250, 100 | `Cancellations_Rate` (%) | Orange |
| 3 | Driver Personal/Car | Card | 740, 84, 250, 100 | `Cancellations_Driver_PersonalCar` | Navy; label "Driver: Personal & Car" |
| 4 | Revenue Lost | Card | 1000, 84, 250, 100 | `Revenue_LostToCancellation` | ₹, orange |
| 5 | **Cancelled Rides Reasons (Customer)** | Clustered bar (horizontal) | 220, 200, 500, 500 | Axis `Canceled_Rides_by_Customer`; Values `Cancellations_Customer`; filter out "Not Applicable" | Bars `#EDEF00`; data labels; sorted desc |
| 6 | **Cancelled Rides Reasons (Driver)** | Clustered bar (horizontal) | 740, 200, 510, 500 | Axis `Canceled_Rides_by_Driver`; Values `Cancellations_Driver`; filter out "Not Applicable" | Bars `#ED561B`; data labels; sorted desc |

**Key insight to annotate:** Driver-side cancellations (18,434) are the single
largest revenue leak; "Personal & Car related issue" alone is 6,542 rides.

---

### Page 5 — Ratings

**Purpose:** is service quality a differentiator, or uniformly good?

| # | Visual | Type | Position | Fields / measures | Formatting |
|---|---|---|---|---|---|
| 1 | Avg Driver Rating | Card | 220, 84, 250, 100 | `Ratings_Driver_Avg` (2 dp) | Navy |
| 2 | Avg Customer Rating | Card | 480, 84, 250, 100 | `Ratings_Customer_Avg` (2 dp) | Green |
| 3 | Rating Gap | Card | 740, 84, 250, 100 | `Ratings_Gap` (3 dp) | Grey |
| 4 | High-rating share | Card | 1000, 84, 250, 100 | `Ratings_HighShare` (%) | Blue |
| 5 | **Driver Ratings Distribution** | Column chart | 220, 200, 500, 250 | Axis `Driver_Ratings`; Values `Rides_Rated` | Columns `#058DC7`; X axis 3.0–5.0 |
| 6 | **Customer Ratings Distribution** | Column chart | 740, 200, 510, 250 | Axis `Customer_Rating`; Values `Rides_Rated` | Columns `#92D050`; X axis 3.0–5.0 |
| 7 | **Customer vs Driver Ratings** | Scatter chart | 220, 470, 1030, 236 | X `Ratings_Driver_Avg`; Y `Ratings_Customer_Avg`; Details `Vehicle_Type`; Size `Bookings_Success` | Points `#058DC7`; trend line off (r ≈ 0) |

**Key insight to annotate:** both distributions are near-identical and centred on
4.0 (r = −0.003) — satisfaction is uniformly high and is *not* a differentiator.

---

## Step 6 — Slicers & interactions

1. **Sync slicers** across all 5 pages (Date, Vehicle Type, Payment Method,
   Booking Status).
2. **Edit interactions** (*Format → Edit interactions*): on Page 1, let the
   status donut filter the status table but **not** the KPI cards (cards should
   show the full filtered total).
3. Add a **Reset filters** bookmark (*View → Bookmarks → Add*) that clears all
   slicers, and a button on the header band that links to it.
4. Add **page navigation buttons** (5 buttons, one per page) in the header band,
   styled `#92D050` fill / white text, using *Action → Page navigation*.

---

## Step 7 — Formatting & theme

1. *View → Themes → Browse for themes* → select **`theme.json`**.
2. Set the report page background to `#F7F9FA` (theme handles it, verify).
3. Apply **Poppins** to all text (theme sets it; if Poppins is not installed,
   Power BI falls back to Segoe UI — install Poppins for exact fidelity).
4. Number formats:
   - Currency: `₹#,0` (or `₹#,0.00` for averages)
   - Percent: `0.0%`
   - Distance: `#,0.0 " km"`
5. Turn **off** gridlines on all charts; keep light axis lines `#E6E6E6`.
6. Add a footer text box on each page: "OLA Rides Analytics · July 2024 ·
   Source: OLA_DataSet.xlsx (103,024 bookings)".

---

## Step 8 — Publish & share

1. *File → Publish* → choose a workspace.
2. In the Power BI Service, create a **dashboard** pinning the 4 KPI cards from
   Page 1.
3. *File → Embed report → Publish to web* → copy the iframe URL and paste it
   into the Streamlit app's **Power BI** tab (see `app/README` / README).
4. Set a scheduled refresh if the CSV is replaced monthly.

---

## Acceptance test

The build is correct when all of these hold:

- [ ] `bookings` row count = **103,024**.
- [ ] Page 1 Total Bookings = **103,024**; Success Rate = **62.1%**.
- [ ] Page 1 Total Revenue = **₹35,080,467**.
- [ ] Page 2 Top-5 bar shows exactly 5 vehicle types, sorted by distance.
- [ ] Page 3 payment bar shows Cash > UPI > Credit Card > Debit Card.
- [ ] Page 4 driver reasons show "Personal & Car related issue" = **6,542**.
- [ ] Page 5 both rating distributions peak at 4.0 and span 3.0–5.0.
- [ ] All 4 slicers filter every visual on every page.
- [ ] Theme colours match `theme.json` (navy header, green accents).
