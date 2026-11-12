# OLA DataSet — Cleaning Log

**Source:** `OLA_DataSet.xlsx` (sheet `July`)  
**Raw shape:** 103,024 rows x 20 columns  
**Clean shape:** 103,024 rows x 37 columns

## Steps

1. Loaded sheet 'July': 103,024 rows x 20 columns.
2. Parsed Date+Time -> Booking_Datetime (unparseable: 0).
3. Derived Booking_Hour, Booking_DayOfWeek, DayOfWeek_Num, Booking_Date, Is_Weekend.
4. Derived Time_of_Day demand bucket (5 windows).
5. Stripped whitespace on all categorical text columns.
6. Normalised vehicle label 'eBike' -> 'E-Bike' (matches slide template).
7. Booking_Status split: 63,967 Success / 39,057 non-success.
8. Filled Incomplete_Rides blanks with 'No' (blank = completed ride).
9. Filled Payment_Method blanks with 'Not Applicable' (non-successful rides).
10. Filled cancellation / incomplete reason blanks with 'Not Applicable'.
11. Kept V_TAT/C_TAT/ratings as NULL for non-successful rides (no fake imputation); added Has_TAT flag.
12. Derived normalised cancellation-reason categories (Customer_Cancel_Category, Driver_Cancel_Category, Incomplete_Reason_Category).
13. IQR outlier flags computed: V_TAT=0, C_TAT=0, Booking_Value=8468, Ride_Distance=0
14. Flagged 39,057 zero-distance rides (Zero_Distance_Flag).
15. Derived Distance_Bucket (0 / 1-5 / 6-10 / 11-20 / 21-30 / 31-50 km).
16. Derived Value_Bucket (<250 / 250-500 / 500-750 / 750-1000 / 1000-1500 / 1500+ INR).
17. Derived Fare_per_km (INR/km) for successful, non-zero-distance rides.
18. De-duplicated on Booking_ID: removed 0 rows.
19. Saved cleaned dataset -> data/ola_cleaned.csv (103,024 rows x 37 cols).
20. Wrote SQLite database -> data/ola_cleaned.sqlite (table 'bookings', 3 indexes).

## Data-Quality Scorecard

| Metric | Before | After |
|---|---|---|
| Rows | 103,024 | 103,024 |
| Columns | 20 | 37 |
| Completeness | 75.22% | 94.88% |
| Duplicate rows | 0 | 0 |
| Unparseable datetimes | 0 | 0 |
| Zero-distance rides | 39,057 | 39,057 (flagged) |

## Derived features added

- `Booking_Hour`
- `Booking_DayOfWeek`
- `DayOfWeek_Num`
- `Is_Weekend`
- `Time_of_Day`
- `Distance_Bucket`
- `Value_Bucket`
- `Fare_per_km`
- `Customer_Cancel_Category`
- `Driver_Cancel_Category`
- `Incomplete_Reason_Category`

## Outlier flags (IQR 1.5x)

| Column | Lower fence | Upper fence | Flagged |
|---|---|---|---|
| V_TAT | -112.0 | 448.0 | 0 |
| C_TAT | -35.0 | 205.0 | 0 |
| Booking_Value | -326.5 | 1189.5 | 8,468 |
| Ride_Distance | -39.0 | 65.0 | 0 |
