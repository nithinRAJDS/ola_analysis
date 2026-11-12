# OLA Rides — Power BI Template (`.pbit`) Specification

A `.pbit` (Power BI Template) is a `.pbix` with the data stripped out: it keeps
the **data-source definition, Power Query, data model, measures, theme and
report pages**, and prompts the user for the source path on open. This file is
the human-readable spec of that template — follow it to produce the `.pbit`.

## 1. Template metadata

| Field | Value |
|---|---|
| Name | `OLA Rides Analytics` |
| Version | 1.0 |
| Author | Data Analytics |
| Description | July-2024 Ola booking analytics — KPIs, vehicle, payment, city, cancellations, time patterns, data quality |
| Theme | `ola_theme.json` |
| Canvas | 16:9, 1280 × 720 |

## 2. Parameters (prompted on open)

| Parameter | Type | Default | Purpose |
|---|---|---|---|
| `pSourcePath` | Text | `C:\OLA\ola_cleaned.csv` | Path to the cleaned CSV |
| `pSourceFolder` | Text | `C:\OLA` | Folder containing the CSV |

Wire the query's `File.Contents` to `pSourcePath`:

```m
Source = Csv.Document(File.Contents(pSourcePath), [Delimiter=",", Encoding=65001])
```

## 3. Data sources

| Source | Type | Object |
|---|---|---|
| `ola_cleaned.csv` | Text/CSV (file) | query `bookings` |

## 4. Model objects

- **Tables:** `bookings` (fact), `Date` (calculated), `_Measures` (measure holder).
- **Relationships:** `Date[Date]` → `bookings[Booking_Date]` (1:many, single).
- **Date table:** `Date` marked as date table.
- **Measures:** all measures in `dax_measures.md` (≈40 measures).
- **Calculated columns:** `Revenue Band`, `Time of Day`, `Is Successful`.

## 5. Report pages (7)

1. Executive Overview
2. Vehicle Type Analysis
3. Revenue & Payment
4. Cancellations & Service Quality
5. Geography (City)
6. Time Patterns
7. Data Quality

(Visual-by-visual specs in `POWERBI_BUILD_GUIDE.md` §5.)

## 6. How to generate the `.pbit` from this spec

1. Open Power BI Desktop → **Get data → Text/CSV** → `ola_cleaned.csv`.
2. Apply the Power Query steps in `POWERBI_BUILD_GUIDE.md` §2.
3. Add the `Date` table and relationships (§3).
4. Paste every measure from `dax_measures.md`.
5. Apply `ola_theme.json` (**View → Themes → Browse**).
6. Build the 7 pages per §5.
7. **File → Export → Power BI template** → save as `OLA_Rides_Analytics.pbit`.
8. On open, the template prompts for `pSourcePath` — point it at the CSV.

## 7. Acceptance test

After opening the generated `.pbit` and pointing it at `ola_cleaned.csv`, the
Executive Overview cards must read:

- Total Bookings = **103,024**
- Total Revenue = **₹35,080,467**
- Success Rate = **62.1 %**
- Avg Booking Value = **₹548**
- Avg Driver Rating = **4.00**
