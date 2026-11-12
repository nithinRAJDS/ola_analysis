-- ============================================================================
--  OLA Rides Analytics — SQL Query Library
--  File   : queries.sql
--  Engine : SQLite 3 (also ANSI-compatible; notes for PostgreSQL/MySQL inline)
--  Table  : bookings  (103,024 rows, July 2024, Bengaluru)
--  Author : Data Analytics Team
-- ----------------------------------------------------------------------------
--  HOW TO RUN
--    sqlite3 data/ola_cleaned.sqlite < queries.sql
--  or from Python:
--    import sqlite3; con = sqlite3.connect("data/ola_cleaned.sqlite")
--    con.executescript(open("queries.sql").read())
--
--  CONVENTIONS
--    * Every query is read-only (SELECT only) — safe to run on production.
--    * Comments above each query state the business question it answers.
--    * Indexes exist on Booking_Status, Booking_Date, Vehicle_Type.
--    * "Successful" = Booking_Status = 'Success' (a completed, paid trip).
--    * Non-successful rides carry Ride_Distance = 0 and NULL ratings/TAT by
--      design, so distance/rating aggregates are filtered to Success.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 0. REUSABLE VIEWS  (created once; the app and Power BI reuse them)
-- ----------------------------------------------------------------------------

-- Successful (completed) rides only — the revenue-bearing population.
DROP VIEW IF EXISTS v_successful_rides;
CREATE VIEW v_successful_rides AS
SELECT *
FROM   bookings
WHERE  Booking_Status = 'Success';

-- All cancellations (customer + driver), with a unified reason column.
DROP VIEW IF EXISTS v_cancellations;
CREATE VIEW v_cancellations AS
SELECT
    Booking_ID,
    Booking_Datetime,
    Booking_Date,
    Customer_ID,
    Vehicle_Type,
    Pickup_Location,
    Booking_Value,
    CASE
        WHEN Booking_Status = 'Canceled by Customer' THEN 'Customer'
        WHEN Booking_Status = 'Canceled by Driver'   THEN 'Driver'
    END AS Cancelled_By,
    COALESCE(
        NULLIF(Canceled_Rides_by_Customer, 'Not Applicable'),
        NULLIF(Canceled_Rides_by_Driver,   'Not Applicable')
    ) AS Cancel_Reason
FROM bookings
WHERE Booking_Status IN ('Canceled by Customer', 'Canceled by Driver');

-- Incomplete rides (started but not completed) with their reason.
DROP VIEW IF EXISTS v_incomplete_rides;
CREATE VIEW v_incomplete_rides AS
SELECT
    Booking_ID,
    Booking_Datetime,
    Customer_ID,
    Vehicle_Type,
    Pickup_Location,
    Drop_Location,
    Booking_Value,
    Incomplete_Rides_Reason,
    Incomplete_Reason_Category
FROM bookings
WHERE Incomplete_Rides = 'Yes';


-- ============================================================================
--  Q1. Retrieve all successful bookings
--      Business use: the completed-trip ledger — basis for revenue, distance
--      and rating reporting. Returns 63,967 rows.
-- ============================================================================
SELECT
    Booking_ID,
    Booking_Datetime,
    Customer_ID,
    Vehicle_Type,
    Pickup_Location,
    Drop_Location,
    Ride_Distance,
    Booking_Value,
    Payment_Method,
    Driver_Ratings,
    Customer_Rating
FROM   bookings
WHERE  Booking_Status = 'Success'
ORDER  BY Booking_Datetime
LIMIT  100;          -- preview; drop LIMIT for the full 63,967-row export


-- ============================================================================
--  Q2. Average ride distance for each vehicle type
--      Business use: which segments carry long vs short trips — informs
--      driver allocation and fare structuring. Success rides only.
-- ============================================================================
SELECT
    Vehicle_Type,
    COUNT(*)                          AS Total_Rides,
    ROUND(AVG(Ride_Distance), 2)      AS Avg_Ride_Distance_km,
    ROUND(MIN(Ride_Distance), 2)      AS Min_Distance_km,
    ROUND(MAX(Ride_Distance), 2)      AS Max_Distance_km,
    ROUND(SUM(Ride_Distance), 0)      AS Total_Distance_km
FROM   bookings
WHERE  Booking_Status = 'Success'
GROUP  BY Vehicle_Type
ORDER  BY Avg_Ride_Distance_km DESC;


-- ============================================================================
--  Q3. Total number of cancelled rides by customers
--      Business use: demand-side churn signal — how much revenue walks away
--      before a driver is even dispatched.
-- ============================================================================
SELECT
    COUNT(*) AS Customer_Cancelled_Rides
FROM   bookings
WHERE  Booking_Status = 'Canceled by Customer';


-- ============================================================================
--  Q4. Top 5 customers who booked the highest number of rides
--      Business use: identify power users for loyalty / personalised offers.
--      Counts ALL bookings (any status) — a booking is a booking.
-- ============================================================================
SELECT
    Customer_ID,
    COUNT(*)                                              AS Total_Bookings,
    SUM(CASE WHEN Booking_Status = 'Success' THEN 1 ELSE 0 END) AS Successful_Bookings,
    ROUND(SUM(CASE WHEN Booking_Status = 'Success'
                   THEN Booking_Value ELSE 0 END), 0)     AS Total_Spend_INR
FROM   bookings
GROUP  BY Customer_ID
ORDER  BY Total_Bookings DESC, Total_Spend_INR DESC
LIMIT  5;


-- ============================================================================
--  Q5. Number of rides cancelled by drivers due to personal and car-related
--      issues
--      Business use: the single largest controllable revenue leak — a
--      supply-side reliability problem, not a demand problem.
-- ============================================================================
SELECT
    COUNT(*) AS Driver_Cancelled_Personal_Car_Issue
FROM   bookings
WHERE  Booking_Status = 'Canceled by Driver'
  AND  Canceled_Rides_by_Driver = 'Personal & Car related issue';

--  Breakdown of ALL driver-cancellation reasons (context for the above):
SELECT
    Canceled_Rides_by_Driver            AS Reason,
    COUNT(*)                            AS Rides,
    ROUND(100.0 * COUNT(*) /
          (SELECT COUNT(*) FROM bookings
           WHERE Booking_Status = 'Canceled by Driver'), 2) AS Pct_of_Driver_Cancels
FROM   bookings
WHERE  Booking_Status = 'Canceled by Driver'
GROUP  BY Canceled_Rides_by_Driver
ORDER  BY Rides DESC;


-- ============================================================================
--  Q6. Maximum and minimum driver ratings for Prime Sedan bookings
--      Business use: quality spread within the flagship segment — a wide
--      range signals inconsistent driver experience.
-- ============================================================================
SELECT
    Vehicle_Type,
    COUNT(Driver_Ratings)          AS Rated_Rides,
    ROUND(MIN(Driver_Ratings), 2)  AS Min_Driver_Rating,
    ROUND(MAX(Driver_Ratings), 2)  AS Max_Driver_Rating,
    ROUND(AVG(Driver_Ratings), 2)  AS Avg_Driver_Rating
FROM   bookings
WHERE  Vehicle_Type = 'Prime Sedan'
  AND  Driver_Ratings IS NOT NULL
GROUP  BY Vehicle_Type;


-- ============================================================================
--  Q7. All rides where payment was made using UPI
--      Business use: digital-payment adoption — UPI is the growth channel for
--      cashless incentives and instant settlement.
-- ============================================================================
SELECT
    Booking_ID,
    Booking_Datetime,
    Customer_ID,
    Vehicle_Type,
    Ride_Distance,
    Booking_Value,
    Payment_Method
FROM   bookings
WHERE  Payment_Method = 'UPI'
ORDER  BY Booking_Value DESC
LIMIT  100;          -- preview; 25,881 UPI rides in total


-- ============================================================================
--  Q8. Average customer rating per vehicle type
--      Business use: customer-perceived quality by segment — pairs with Q2 to
--      show whether long-distance segments are also the best-rated.
-- ============================================================================
SELECT
    Vehicle_Type,
    COUNT(Customer_Rating)             AS Rated_Rides,
    ROUND(AVG(Customer_Rating), 3)     AS Avg_Customer_Rating,
    ROUND(MIN(Customer_Rating), 2)     AS Min_Rating,
    ROUND(MAX(Customer_Rating), 2)     AS Max_Rating
FROM   bookings
WHERE  Customer_Rating IS NOT NULL
GROUP  BY Vehicle_Type
ORDER  BY Avg_Customer_Rating DESC;


-- ============================================================================
--  Q9. Total booking value of rides completed successfully
--      Business use: the headline revenue number for the month.
-- ============================================================================
SELECT
    COUNT(*)                              AS Successful_Rides,
    ROUND(SUM(Booking_Value), 0)          AS Total_Booking_Value_INR,
    ROUND(AVG(Booking_Value), 2)          AS Avg_Booking_Value_INR,
    ROUND(SUM(Booking_Value) / 1000000.0, 2) AS Total_Value_INR_Millions
FROM   bookings
WHERE  Booking_Status = 'Success';


-- ============================================================================
--  Q10. All incomplete rides along with the reason
--       Business use: trips that started but did not finish — a direct
--       service-quality and refund/compensation exposure.
-- ============================================================================
SELECT
    Booking_ID,
    Booking_Datetime,
    Customer_ID,
    Vehicle_Type,
    Pickup_Location,
    Drop_Location,
    Booking_Value,
    Incomplete_Rides_Reason
FROM   bookings
WHERE  Incomplete_Rides = 'Yes'
ORDER  BY Booking_Datetime
LIMIT  100;          -- preview; 3,926 incomplete rides in total

--  Reason summary for the same population:
SELECT
    Incomplete_Rides_Reason,
    COUNT(*) AS Rides,
    ROUND(100.0 * COUNT(*) /
          (SELECT COUNT(*) FROM bookings WHERE Incomplete_Rides = 'Yes'), 2) AS Pct
FROM   bookings
WHERE  Incomplete_Rides = 'Yes'
GROUP  BY Incomplete_Rides_Reason
ORDER  BY Rides DESC;


-- ============================================================================
--  BONUS — supporting analytics used by the dashboard / app
-- ============================================================================

-- B1. Booking-status mix (the funnel top).
SELECT Booking_Status, COUNT(*) AS Rides,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM bookings), 2) AS Pct
FROM   bookings GROUP BY Booking_Status ORDER BY Rides DESC;

-- B2. Revenue by payment method (successful rides).
SELECT Payment_Method, COUNT(*) AS Rides,
       ROUND(SUM(Booking_Value), 0) AS Revenue_INR,
       ROUND(AVG(Booking_Value), 2) AS Avg_Fare_INR
FROM   bookings WHERE Booking_Status = 'Success'
GROUP  BY Payment_Method ORDER BY Revenue_INR DESC;

-- B3. Peak demand hours (bookings per hour of day).
SELECT Booking_Hour, COUNT(*) AS Bookings,
       SUM(CASE WHEN Booking_Status = 'Success' THEN 1 ELSE 0 END) AS Successful
FROM   bookings GROUP BY Booking_Hour ORDER BY Booking_Hour;

-- B4. Daily ride volume + success rate (trend line).
SELECT Booking_Date,
       COUNT(*) AS Bookings,
       SUM(CASE WHEN Booking_Status = 'Success' THEN 1 ELSE 0 END) AS Successful,
       ROUND(100.0 * SUM(CASE WHEN Booking_Status = 'Success' THEN 1 ELSE 0 END)
             / COUNT(*), 2) AS Success_Rate_Pct
FROM   bookings GROUP BY Booking_Date ORDER BY Booking_Date;

-- B5. Top 5 vehicle types by total ride distance.
SELECT Vehicle_Type, ROUND(SUM(Ride_Distance), 0) AS Total_Distance_km,
       COUNT(*) AS Rides
FROM   bookings WHERE Booking_Status = 'Success'
GROUP  BY Vehicle_Type ORDER BY Total_Distance_km DESC LIMIT 5;

-- B6. Customer-cancellation reasons (ranked).
SELECT Canceled_Rides_by_Customer AS Reason, COUNT(*) AS Rides
FROM   bookings WHERE Booking_Status = 'Canceled by Customer'
GROUP  BY Canceled_Rides_by_Customer ORDER BY Rides DESC;

-- B7. Anomaly check — zero-distance rides that still carry a fare.
SELECT COUNT(*) AS Zero_Distance_With_Fare
FROM   bookings WHERE Ride_Distance = 0 AND Booking_Value > 0;

-- B8. Anomaly check — extreme fare-per-km (possible meter tampering).
SELECT COUNT(*) AS Extreme_Fare_Per_Km
FROM   bookings WHERE Fare_per_km > 200;
