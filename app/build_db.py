"""
build_db.py — Load the cleaned OLA dataset into a SQLite database.
Run:  python build_db.py
Creates: ola.db  with table `bookings` (+ a few convenience views).
"""
import os
import sqlite3
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "..", "data", "ola_cleaned.csv")
DB = os.path.join(HERE, "ola.db")

df = pd.read_csv(CSV)

# Keep a tidy, analysis-ready column set (drop the raw image URL for SQL clarity)
df = df.drop(columns=["Vehicle Images"], errors="ignore")

con = sqlite3.connect(DB)
df.to_sql("bookings", con, if_exists="replace", index=False)

# Convenience views -----------------------------------------------------------
con.executescript("""
DROP VIEW IF EXISTS successful_rides;
CREATE VIEW successful_rides AS
    SELECT * FROM bookings WHERE Booking_Status = 'Success';

DROP VIEW IF EXISTS cancellations;
CREATE VIEW cancellations AS
    SELECT * FROM bookings WHERE Booking_Status LIKE 'Canceled%';

CREATE INDEX IF NOT EXISTS idx_status  ON bookings(Booking_Status);
CREATE INDEX IF NOT EXISTS idx_vehicle ON bookings(Vehicle_Type);
CREATE INDEX IF NOT EXISTS idx_pickup  ON bookings(Pickup_Location);
CREATE INDEX IF NOT EXISTS idx_date    ON bookings(Booking_Date);
CREATE INDEX IF NOT EXISTS idx_pay     ON bookings(Payment_Method);
""")
con.commit()

n = con.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
print(f"Built {DB}  ->  table 'bookings' with {n:,} rows.")
print("Columns:", ", ".join(df.columns))
con.close()
