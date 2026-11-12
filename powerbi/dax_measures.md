# OLA Rides — DAX Measures (copy-paste ready)

All measures assume a single table named **`bookings`** (the cleaned CSV) plus a
disconnected **`Date`** table for time intelligence. Paste each block into
*Modeling → New measure*.

> **Naming convention:** `Area_Metric` (e.g. `Revenue_Total`). Every measure is
> written to be filter-context safe, so slicers on Vehicle Type / Payment Method
> / Date flow through automatically.

---

## 0. Base counts

```dax
-- Total bookings (any status)
Bookings_Total = COUNTROWS ( bookings )

-- Successful (completed) rides
Bookings_Success =
CALCULATE ( COUNTROWS ( bookings ), bookings[Booking_Status] = "Success" )

-- Non-successful rides
Bookings_NotSuccess =
CALCULATE ( COUNTROWS ( bookings ), bookings[Booking_Status] <> "Success" )

-- Success rate (%)
Bookings_SuccessRate =
DIVIDE ( [Bookings_Success], [Bookings_Total] )

-- Distinct customers
Customers_Distinct = DISTINCTCOUNT ( bookings[Customer_ID] )

-- Rated rides (proxy for completed, rated trips)
Rides_Rated = CALCULATE ( COUNTROWS ( bookings ), NOT ISBLANK ( bookings[Driver_Ratings] ) )
```

---

## 1. Revenue measures

```dax
-- Total booking value of successful rides (Q9)
Revenue_Total =
CALCULATE ( SUM ( bookings[Booking_Value] ), bookings[Booking_Status] = "Success" )

-- Average fare per successful ride
Revenue_AvgFare =
CALCULATE ( AVERAGE ( bookings[Booking_Value] ), bookings[Booking_Status] = "Success" )

-- Revenue in millions (for KPI cards)
Revenue_Millions = DIVIDE ( [Revenue_Total], 1000000 )

-- Revenue lost to cancellations (value of rides that never completed)
Revenue_LostToCancellation =
CALCULATE (
    SUM ( bookings[Booking_Value] ),
    bookings[Booking_Status] IN { "Canceled by Customer", "Canceled by Driver" }
)

-- Revenue at risk (all non-successful bookings)
Revenue_AtRisk =
CALCULATE ( SUM ( bookings[Booking_Value] ), bookings[Booking_Status] <> "Success" )

-- Revenue per customer
Revenue_PerCustomer = DIVIDE ( [Revenue_Total], [Customers_Distinct] )
```

---

## 2. Distance measures

```dax
-- Total distance travelled (successful rides)
Distance_Total =
CALCULATE ( SUM ( bookings[Ride_Distance] ), bookings[Booking_Status] = "Success" )

-- Average ride distance (Q2)
Distance_Avg =
CALCULATE ( AVERAGE ( bookings[Ride_Distance] ), bookings[Booking_Status] = "Success" )

-- Average distance per vehicle type (used in the matrix visual)
Distance_AvgByVehicle =
AVERAGEX (
    VALUES ( bookings[Vehicle_Type] ),
    CALCULATE ( AVERAGE ( bookings[Ride_Distance] ), bookings[Booking_Status] = "Success" )
)

-- Median fare per km (pricing efficiency)
FarePerKm_Median =
CALCULATE ( MEDIAN ( bookings[Fare_per_km] ), bookings[Booking_Status] = "Success" )
```

---

## 3. Cancellation measures

```dax
-- Customer cancellations (Q3)
Cancellations_Customer =
CALCULATE ( COUNTROWS ( bookings ), bookings[Booking_Status] = "Canceled by Customer" )

-- Driver cancellations
Cancellations_Driver =
CALCULATE ( COUNTROWS ( bookings ), bookings[Booking_Status] = "Canceled by Driver" )

-- Driver cancellations due to personal & car issues (Q5)
Cancellations_Driver_PersonalCar =
CALCULATE (
    COUNTROWS ( bookings ),
    bookings[Booking_Status] = "Canceled by Driver",
    bookings[Canceled_Rides_by_Driver] = "Personal & Car related issue"
)

-- Driver-not-found (supply gap)
Cancellations_DriverNotFound =
CALCULATE ( COUNTROWS ( bookings ), bookings[Booking_Status] = "Driver Not Found" )

-- Total cancellations (customer + driver)
Cancellations_Total = [Cancellations_Customer] + [Cancellations_Driver]

-- Cancellation rate (%)
Cancellations_Rate = DIVIDE ( [Cancellations_Total], [Bookings_Total] )

-- Share of driver cancels that are personal/car issues
Cancellations_Driver_PersonalCar_Share =
DIVIDE ( [Cancellations_Driver_PersonalCar], [Cancellations_Driver] )
```

---

## 4. Rating measures

```dax
-- Average driver rating
Ratings_Driver_Avg =
CALCULATE ( AVERAGE ( bookings[Driver_Ratings] ), NOT ISBLANK ( bookings[Driver_Ratings] ) )

-- Average customer rating (Q8)
Ratings_Customer_Avg =
CALCULATE ( AVERAGE ( bookings[Customer_Rating] ), NOT ISBLANK ( bookings[Customer_Rating] ) )

-- Min / max driver rating for Prime Sedan (Q6)
Ratings_Driver_Min_PrimeSedan =
CALCULATE (
    MIN ( bookings[Driver_Ratings] ),
    bookings[Vehicle_Type] = "Prime Sedan",
    NOT ISBLANK ( bookings[Driver_Ratings] )
)

Ratings_Driver_Max_PrimeSedan =
CALCULATE (
    MAX ( bookings[Driver_Ratings] ),
    bookings[Vehicle_Type] = "Prime Sedan",
    NOT ISBLANK ( bookings[Driver_Ratings] )
)

-- Rating gap (driver minus customer) — service perception delta
Ratings_Gap = [Ratings_Driver_Avg] - [Ratings_Customer_Avg]

-- % of rated rides at 4.5 or above (satisfaction proxy)
Ratings_HighShare =
DIVIDE (
    CALCULATE ( COUNTROWS ( bookings ), bookings[Driver_Ratings] >= 4.5 ),
    [Rides_Rated]
)
```

---

## 5. Customer measures (Q4)

```dax
-- Bookings per customer (average)
Customers_BookingsPerCustomer = DIVIDE ( [Bookings_Total], [Customers_Distinct] )

-- Repeat customers (>= 2 bookings)
Customers_Repeat =
COUNTROWS (
    FILTER (
        VALUES ( bookings[Customer_ID] ),
        CALCULATE ( COUNTROWS ( bookings ) ) >= 2
    )
)

-- Repeat rate (%)
Customers_RepeatRate = DIVIDE ( [Customers_Repeat], [Customers_Distinct] )
```

---

## 6. Time-intelligence measures

Requires a `Date` table marked as a date table and related 1:* to
`bookings[Booking_Date]`.

```dax
-- Bookings in the selected period
Bookings_Current = [Bookings_Total]

-- Bookings in the previous period (month-over-month)
Bookings_PrevMonth =
CALCULATE ( [Bookings_Total], DATEADD ( 'Date'[Date], -1, MONTH ) )

-- MoM growth (%)
Bookings_MoMGrowth =
DIVIDE ( [Bookings_Current] - [Bookings_PrevMonth], [Bookings_PrevMonth] )

-- Revenue MoM growth
Revenue_MoMGrowth =
DIVIDE (
    [Revenue_Total] - CALCULATE ( [Revenue_Total], DATEADD ( 'Date'[Date], -1, MONTH ) ),
    CALCULATE ( [Revenue_Total], DATEADD ( 'Date'[Date], -1, MONTH ) )
)

-- Peak-hour bookings (12:00-15:00 window)
Bookings_PeakWindow =
CALCULATE ( [Bookings_Total], bookings[Booking_Hour] >= 12, bookings[Booking_Hour] <= 15 )

-- Weekend share of bookings
Bookings_WeekendShare =
DIVIDE (
    CALCULATE ( [Bookings_Total], bookings[Is_Weekend] = 1 ),
    [Bookings_Total]
)
```

---

## 7. Anomaly / data-quality measures

```dax
-- Zero-distance rides that still carry a fare (data-quality flag)
DQ_ZeroDistanceWithFare =
CALCULATE (
    COUNTROWS ( bookings ),
    bookings[Ride_Distance] = 0,
    bookings[Booking_Value] > 0
)

-- Extreme fare-per-km rides (possible meter tampering)
DQ_ExtremeFarePerKm =
CALCULATE ( COUNTROWS ( bookings ), bookings[Fare_per_km] > 200 )

-- Completeness of the rating fields (%)
DQ_RatingCompleteness =
DIVIDE ( [Rides_Rated], [Bookings_Total] )

-- Incomplete rides (Q10)
Rides_Incomplete =
CALCULATE ( COUNTROWS ( bookings ), bookings[Incomplete_Rides] = "Yes" )

-- Incomplete rate
Rides_IncompleteRate = DIVIDE ( [Rides_Incomplete], [Bookings_Success] )
```

---

## 8. Dynamic titles (optional polish)

```dax
-- Page title that reflects the active slicer selection
Title_Overall =
"Overall Performance — " &
SELECTEDVALUE ( bookings[Vehicle_Type], "All Vehicle Types" ) &
" — " &
FORMAT ( MIN ( bookings[Booking_Date] ), "mmm yyyy" )
```

---

## Measure → visual map

| Page | Visual | Measures used |
|---|---|---|
| 1 Overall | KPI cards | `Bookings_Total`, `Bookings_SuccessRate`, `Revenue_Total`, `Distance_Avg` |
| 1 Overall | Ride Volume Over Time (line) | `Bookings_Total` by `Booking_Date` |
| 1 Overall | Booking Status Breakdown (donut) | `Bookings_Total` by `Booking_Status` |
| 2 Vehicle Type | Top 5 Vehicle Types by Ride Distance (bar) | `Distance_Total` by `Vehicle_Type`, Top N = 5 |
| 2 Vehicle Type | Vehicle matrix | `Distance_Avg`, `Revenue_AvgFare`, `Ratings_Customer_Avg` |
| 3 Revenue | Revenue by Payment Method (bar) | `Revenue_Total` by `Payment_Method` |
| 3 Revenue | Top 5 Customers by Total Booking Value (table) | `Revenue_Total` by `Customer_ID`, Top N = 5 |
| 3 Revenue | Ride Distance Distribution Per Day (column) | `Distance_Total` by `Booking_Date` |
| 4 Cancellation | Cancelled Rides Reasons — Customer (bar) | `Cancellations_Customer` by `Canceled_Rides_by_Customer` |
| 4 Cancellation | Cancelled Rides Reasons — Driver (bar) | `Cancellations_Driver` by `Canceled_Rides_by_Driver` |
| 5 Ratings | Driver Ratings Distribution (column) | `Rides_Rated` by `Driver_Ratings` |
| 5 Ratings | Customer Ratings Distribution (column) | `Rides_Rated` by `Customer_Rating` |
| 5 Ratings | Customer vs Driver Ratings (scatter) | `Ratings_Driver_Avg` vs `Ratings_Customer_Avg` by `Vehicle_Type` |
