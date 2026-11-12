"""
run_queries.py — Execute the 10 required SQL questions against the cleaned DB
and capture real results into data/sql_results.json (used by SQL_RESULTS.md,
the Streamlit app and the slide deck).

Run:  python run_queries.py
"""
from __future__ import annotations

import json
import sqlite3

import pandas as pd

DB = "data/ola_cleaned.sqlite"
OUT = "data/sql_results.json"

# The 10 required questions, each with a short title and the exact SQL used.
QUESTIONS = [
    {
        "id": 1,
        "title": "Retrieve all successful bookings",
        "sql": """SELECT Booking_ID, Booking_Datetime, Customer_ID, Vehicle_Type,
       Pickup_Location, Drop_Location, Ride_Distance, Booking_Value,
       Payment_Method, Driver_Ratings, Customer_Rating
FROM   bookings
WHERE  Booking_Status = 'Success'
ORDER  BY Booking_Datetime
LIMIT  10""",
        "count_sql": "SELECT COUNT(*) AS n FROM bookings WHERE Booking_Status='Success'",
    },
    {
        "id": 2,
        "title": "Average ride distance for each vehicle type",
        "sql": """SELECT Vehicle_Type,
       COUNT(*)                     AS Total_Rides,
       ROUND(AVG(Ride_Distance), 2) AS Avg_Ride_Distance_km,
       ROUND(MIN(Ride_Distance), 2) AS Min_Distance_km,
       ROUND(MAX(Ride_Distance), 2) AS Max_Distance_km,
       ROUND(SUM(Ride_Distance), 0) AS Total_Distance_km
FROM   bookings
WHERE  Booking_Status = 'Success'
GROUP  BY Vehicle_Type
ORDER  BY Avg_Ride_Distance_km DESC""",
    },
    {
        "id": 3,
        "title": "Total number of cancelled rides by customers",
        "sql": """SELECT COUNT(*) AS Customer_Cancelled_Rides
FROM   bookings
WHERE  Booking_Status = 'Canceled by Customer'""",
    },
    {
        "id": 4,
        "title": "Top 5 customers who booked the highest number of rides",
        "sql": """SELECT Customer_ID,
       COUNT(*) AS Total_Bookings,
       SUM(CASE WHEN Booking_Status='Success' THEN 1 ELSE 0 END) AS Successful_Bookings,
       ROUND(SUM(CASE WHEN Booking_Status='Success' THEN Booking_Value ELSE 0 END),0) AS Total_Spend_INR
FROM   bookings
GROUP  BY Customer_ID
ORDER  BY Total_Bookings DESC, Total_Spend_INR DESC
LIMIT  5""",
    },
    {
        "id": 5,
        "title": "Rides cancelled by drivers due to personal and car-related issues",
        "sql": """SELECT COUNT(*) AS Driver_Cancelled_Personal_Car_Issue
FROM   bookings
WHERE  Booking_Status = 'Canceled by Driver'
  AND  Canceled_Rides_by_Driver = 'Personal & Car related issue'""",
    },
    {
        "id": 6,
        "title": "Maximum and minimum driver ratings for Prime Sedan bookings",
        "sql": """SELECT Vehicle_Type,
       COUNT(Driver_Ratings)         AS Rated_Rides,
       ROUND(MIN(Driver_Ratings),2)  AS Min_Driver_Rating,
       ROUND(MAX(Driver_Ratings),2)  AS Max_Driver_Rating,
       ROUND(AVG(Driver_Ratings),2)  AS Avg_Driver_Rating
FROM   bookings
WHERE  Vehicle_Type = 'Prime Sedan' AND Driver_Ratings IS NOT NULL
GROUP  BY Vehicle_Type""",
    },
    {
        "id": 7,
        "title": "All rides where payment was made using UPI",
        "sql": """SELECT Booking_ID, Booking_Datetime, Customer_ID, Vehicle_Type,
       Ride_Distance, Booking_Value, Payment_Method
FROM   bookings
WHERE  Payment_Method = 'UPI'
ORDER  BY Booking_Value DESC
LIMIT  10""",
        "count_sql": "SELECT COUNT(*) AS n FROM bookings WHERE Payment_Method='UPI'",
    },
    {
        "id": 8,
        "title": "Average customer rating per vehicle type",
        "sql": """SELECT Vehicle_Type,
       COUNT(Customer_Rating)         AS Rated_Rides,
       ROUND(AVG(Customer_Rating),3)  AS Avg_Customer_Rating,
       ROUND(MIN(Customer_Rating),2)  AS Min_Rating,
       ROUND(MAX(Customer_Rating),2)  AS Max_Rating
FROM   bookings
WHERE  Customer_Rating IS NOT NULL
GROUP  BY Vehicle_Type
ORDER  BY Avg_Customer_Rating DESC""",
    },
    {
        "id": 9,
        "title": "Total booking value of rides completed successfully",
        "sql": """SELECT COUNT(*)                             AS Successful_Rides,
       ROUND(SUM(Booking_Value),0)            AS Total_Booking_Value_INR,
       ROUND(AVG(Booking_Value),2)            AS Avg_Booking_Value_INR,
       ROUND(SUM(Booking_Value)/1000000.0,2)  AS Total_Value_INR_Millions
FROM   bookings
WHERE  Booking_Status = 'Success'""",
    },
    {
        "id": 10,
        "title": "All incomplete rides along with the reason",
        "sql": """SELECT Booking_ID, Booking_Datetime, Customer_ID, Vehicle_Type,
       Pickup_Location, Drop_Location, Booking_Value, Incomplete_Rides_Reason
FROM   bookings
WHERE  Incomplete_Rides = 'Yes'
ORDER  BY Booking_Datetime
LIMIT  10""",
        "count_sql": "SELECT COUNT(*) AS n FROM bookings WHERE Incomplete_Rides='Yes'",
    },
]


def main() -> None:
    """Run every question, capture the result table and a total-row count."""
    con = sqlite3.connect(DB)
    results = []
    for q in QUESTIONS:
        df = pd.read_sql_query(q["sql"], con)
        total = None
        if q.get("count_sql"):
            total = int(pd.read_sql_query(q["count_sql"], con).iloc[0, 0])
        results.append({
            "id": q["id"],
            "title": q["title"],
            "sql": q["sql"],
            "columns": list(df.columns),
            "rows": df.astype(object).where(df.notna(), None).values.tolist(),
            "row_count": int(len(df)),
            "total_matching_rows": total,
        })
        print(f"Q{q['id']}: {q['title']} -> {len(df)} rows"
              + (f" (of {total:,} total)" if total else ""))
    con.close()
    with open(OUT, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved {len(results)} results -> {OUT}")


if __name__ == "__main__":
    main()
