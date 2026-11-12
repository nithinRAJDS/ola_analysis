"""
nl2sql.py — Natural-language → SQLite SQL engine for the OLA rides dataset.
===========================================================================

Two engines, tried in order:

1. **LLM engine** — used automatically when ``OPENAI_API_KEY``,
   ``ANTHROPIC_API_KEY`` or ``GEMINI_API_KEY`` is present.  A schema-aware
   prompt (full schema, column descriptions, value samples, few-shot examples)
   asks for a single read-only SQLite ``SELECT``.  The SQL is validated
   (SELECT-only, no DDL/DML, whitelisted tables) and, if execution fails, the
   error is fed back for **one** self-repair retry.

2. **Rule engine** — a structured parser (not a keyword chain) that handles
   counts, sums, averages, min/max, distinct counts, group-bys on any
   categorical column, filters on any column, top-N / bottom-N, ordering,
   time trends (daily / weekly / hourly), segment comparisons, percentage
   shares, and "which / why" questions.  Fuzzy matching covers vehicle types,
   payment methods, statuses and column names.

Public API
----------
``translate(question, context=None) -> Result``
``run(question, con, context=None) -> (Result, DataFrame|None, error|None)``
``answer_sentence(df, result) -> str``
``validate_sql(sql) -> (ok, message)``
``EXAMPLE_QUESTIONS -> list[str]``
"""
from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# 1. SCHEMA
# ---------------------------------------------------------------------------
COLUMNS: dict[str, tuple[str, str]] = {
    "Booking_ID": ("TEXT", "unique booking id"),
    "Booking_Datetime": ("TEXT", "ISO timestamp of the booking"),
    "Booking_Date": ("TEXT", "booking date, YYYY-MM-DD (July 2024)"),
    "Booking_Hour": ("INT", "hour of day 0-23"),
    "Booking_DayOfWeek": ("TEXT", "Monday..Sunday"),
    "DayOfWeek_Num": ("INT", "1=Monday .. 7=Sunday"),
    "Is_Weekend": ("INT", "1 if Saturday/Sunday else 0"),
    "Time_of_Day": ("TEXT", "Late Night (00-05) | Early Morning (05-09) | Morning (09-12) | Afternoon (12-16) | Evening Peak (16-20) | Night (20-24)"),
    "Booking_Status": ("TEXT", "Success | Canceled by Customer | Canceled by Driver | Driver Not Found"),
    "Customer_ID": ("TEXT", "customer identifier"),
    "Vehicle_Type": ("TEXT", "Prime Sedan | Prime SUV | Prime Plus | Mini | Auto | Bike | E-Bike"),
    "Pickup_Location": ("TEXT", "one of 50 Bengaluru areas"),
    "Drop_Location": ("TEXT", "one of 50 Bengaluru areas"),
    "Ride_Distance": ("INT", "ride distance in km (0 for non-successful rides)"),
    "Distance_Bucket": ("TEXT", "0 km | 1-5 km | 6-10 km | 11-20 km | 21-30 km | 31-50 km"),
    "Booking_Value": ("INT", "fare in INR"),
    "Value_Bucket": ("TEXT", "<250 | 250-500 | 500-750 | 750-1000 | 1000-1500 | 1500+"),
    "Fare_per_km": ("REAL", "fare divided by distance (INR/km)"),
    "Payment_Method": ("TEXT", "Cash | UPI | Credit Card | Debit Card | Not Applicable"),
    "V_TAT": ("REAL", "vehicle turnaround time in minutes (NULL for non-success)"),
    "C_TAT": ("REAL", "customer turnaround time in minutes (NULL for non-success)"),
    "Driver_Ratings": ("REAL", "driver rating 3.0-5.0 (NULL for non-success)"),
    "Customer_Rating": ("REAL", "customer rating 3.0-5.0 (NULL for non-success)"),
    "Incomplete_Rides": ("TEXT", "Yes | No"),
    "Incomplete_Rides_Reason": ("TEXT", "raw incomplete reason"),
    "Incomplete_Reason_Category": ("TEXT", "Customer Demand | Vehicle Breakdown | Other Issue | Not Applicable"),
    "Canceled_Rides_by_Customer": ("TEXT", "raw customer cancellation reason"),
    "Customer_Cancel_Category": ("TEXT", "Driver Behaviour | Vehicle Comfort | Customer Plans | Address Issue | Not Applicable"),
    "Canceled_Rides_by_Driver": ("TEXT", "raw driver cancellation reason"),
    "Driver_Cancel_Category": ("TEXT", "Personal & Car Issue | Customer Health | Customer Issue | Capacity Violation | Not Applicable"),
    "Has_TAT": ("INT", "1 if turnaround time recorded"),
    "Zero_Distance_Flag": ("INT", "1 if Ride_Distance = 0"),
    "V_TAT_is_outlier": ("INT", "IQR outlier flag"),
    "C_TAT_is_outlier": ("INT", "IQR outlier flag"),
    "Booking_Value_is_outlier": ("INT", "IQR outlier flag"),
    "Ride_Distance_is_outlier": ("INT", "IQR outlier flag"),
}

SCHEMA = (
    "Table: bookings  (one row per Ola booking, July 2024, Bengaluru, 103,024 rows)\n"
    + "\n".join(f"  {c:<28} {t:<5} -- {d}" for c, (t, d) in COLUMNS.items())
    + "\nViews: successful_rides (Booking_Status='Success'), "
      "cancellations (Booking_Status LIKE 'Canceled%')\n"
)

ALLOWED_TABLES = {"bookings", "successful_rides", "cancellations"}

# ---------------------------------------------------------------------------
# 2. Value vocabularies + fuzzy aliases
# ---------------------------------------------------------------------------
VEHICLES = ["Prime Sedan", "Prime SUV", "Prime Plus", "Mini", "Auto", "Bike", "E-Bike"]
PAYMENTS = ["Cash", "UPI", "Credit Card", "Debit Card"]
STATUSES = ["Success", "Canceled by Customer", "Canceled by Driver", "Driver Not Found"]

VEH_PATTERNS: list[tuple[list[str], str]] = [
    (["e-bike", "ebike", "e bike", "electric bike", "electric scooter", "ev bike"], "E-Bike"),
    (["prime sedan", "prime-sedan", "premium sedan"], "Prime Sedan"),
    (["prime suv", "prime-suv", "premium suv"], "Prime SUV"),
    (["prime plus", "prime-plus"], "Prime Plus"),
    (["sedan"], "Prime Sedan"),
    (["suv"], "Prime SUV"),
    (["auto", "rickshaw", "tuk tuk", "tuk-tuk", "three wheeler", "3 wheeler"], "Auto"),
    (["mini", "hatchback"], "Mini"),
    (["bike", "motorcycle", "motorbike", "two wheeler", "2 wheeler"], "Bike"),
]

PAY_PATTERNS: list[tuple[list[str], str]] = [
    (["credit card", "credit"], "Credit Card"),
    (["debit card", "debit"], "Debit Card"),
    (["upi", "gpay", "google pay", "phonepe", "phone pe", "paytm", "vpa"], "UPI"),
    (["cash", "cod", "cash on delivery"], "Cash"),
]

STATUS_PATTERNS: list[tuple[list[str], str]] = [
    (["driver not found", "driver was not found", "driver wasn't found", "no driver",
      "driver unavailable", "couldn't find a driver", "could not find a driver",
      "no driver found", "driver not available"], "Driver Not Found"),
    (["canceled by driver", "cancelled by driver", "cancel by driver", "driver cancel",
      "driver cancelled", "driver canceled", "cancelled by the driver", "canceled by the driver"], "Canceled by Driver"),
    (["canceled by customer", "cancelled by customer", "cancel by customer", "customer cancel",
      "customer cancelled", "customer canceled", "cancelled by the customer", "canceled by the customer"], "Canceled by Customer"),
    (["success", "successful", "completed", "complete", "finished", "fulfilled", "went through"], "Success"),
]

GROUP_TARGETS: list[tuple[list[str], str]] = [
    (["customer id", "by customer", "per customer", "each customer", "top customers",
      "top customer", "customers by", "customer ranking", "riders by", "users by"], "Customer_ID"),
    (["vehicle type", "vehicle", "car type", "cab type", "ride type", "vehicle category"], "Vehicle_Type"),
    (["payment method", "payment", "pay mode", "paid by", "payment type"], "Payment_Method"),
    (["booking status", "status", "outcome"], "Booking_Status"),
    (["pickup location", "pickup", "city", "cities", "area", "areas", "location", "locations",
      "zone", "region", "neighbourhood", "neighborhood", "locality"], "Pickup_Location"),
    (["time of day", "time slot", "part of day", "daypart", "time band"], "Time_of_Day"),
    (["day of week", "weekday", "day name", "which day", "day of the week"], "Booking_DayOfWeek"),
    (["distance bucket", "distance range", "distance band"], "Distance_Bucket"),
    (["value bucket", "fare bucket", "price range", "price band", "fare band", "value range"], "Value_Bucket"),
    (["customer cancel category", "customer cancellation reason", "customer cancel reason"], "Customer_Cancel_Category"),
    (["driver cancel category", "driver cancellation reason", "driver cancel reason"], "Driver_Cancel_Category"),
    (["incomplete reason", "incomplete category", "reason for incomplete"], "Incomplete_Reason_Category"),
    (["weekend", "weekends"], "Is_Weekend"),
]

NUMERIC_TARGETS: list[tuple[list[str], str]] = [
    (["fare per km", "per km", "rate per km", "price per km"], "Fare_per_km"),
    (["driver rating", "driver ratings", "driver score", "rating of driver"], "Driver_Ratings"),
    (["customer rating", "customer ratings", "rider rating", "user rating"], "Customer_Rating"),
    (["v tat", "vehicle tat", "turnaround", "wait time", "pickup time", "vehicle turnaround"], "V_TAT"),
    (["c tat", "customer tat", "customer turnaround"], "C_TAT"),
    (["distance", "km", "kilometre", "kilometer", "mileage"], "Ride_Distance"),
    (["revenue", "fare", "value", "price", "cost", "amount", "money", "earnings",
      "sales", "income", "gmv", "ticket", "spend", "spent", "billing"], "Booking_Value"),
]

METRIC_LABEL = {
    "count": "bookings",
    "revenue": "revenue",
    "sum_distance": "total distance",
    "avg_value": "average fare",
    "avg_distance": "average ride distance",
    "avg_driver_rating": "average driver rating",
    "avg_customer_rating": "average customer rating",
    "avg_v_tat": "average vehicle turnaround time",
    "avg_c_tat": "average customer turnaround time",
    "avg_fare_per_km": "average fare per km",
    "min_value": "minimum fare",
    "max_value": "maximum fare",
    "min_distance": "minimum ride distance",
    "max_distance": "maximum ride distance",
    "min_driver_rating": "minimum driver rating",
    "max_driver_rating": "maximum driver rating",
    "min_customer_rating": "minimum customer rating",
    "max_customer_rating": "maximum customer rating",
    "distinct_customers": "distinct customers",
    "success_rate": "success rate",
    "cancel_rate": "cancellation rate",
}

FMT = {
    "count": "int", "distinct_customers": "int",
    "revenue": "money", "avg_value": "money", "min_value": "money", "max_value": "money",
    "avg_distance": "km", "sum_distance": "km", "min_distance": "km", "max_distance": "km",
    "avg_driver_rating": "rating", "avg_customer_rating": "rating",
    "min_driver_rating": "rating", "max_driver_rating": "rating",
    "min_customer_rating": "rating", "max_customer_rating": "rating",
    "avg_v_tat": "min", "avg_c_tat": "min", "avg_fare_per_km": "money",
    "success_rate": "pct", "cancel_rate": "pct",
}

EXAMPLE_QUESTIONS = [
    "What is the total revenue?",
    "How many bookings were cancelled by the driver?",
    "Show revenue by vehicle type",
    "Top 5 pickup areas by number of rides",
    "What is the average fare for Bike rides?",
    "Show the daily booking trend",
    "Which payment method is most used?",
    "Average driver rating by vehicle type",
    "Why do customers cancel?",
    "What is the success rate?",
    "Which hour has the most bookings?",
    "Compare revenue for UPI and Cash",
    "What percentage of rides are paid by UPI?",
    "Show all successful bookings",
    "Maximum and minimum driver rating for Prime Sedan",
    "How many unique customers are there?",
    "Average ride distance for each vehicle type",
    "Which city has the highest average fare?",
    "Show rides with distance more than 30 km",
    "What is the cancellation rate on weekends?",
]


# ---------------------------------------------------------------------------
# 3. Result object
# ---------------------------------------------------------------------------
@dataclass
class Result:
    sql: str = ""
    engine: str = "Rule-based"
    intent: str = "aggregate"
    explanation: str = ""
    chart_hint: str = "bar"
    metric: str = "count"
    metric_label: str = "bookings"
    fmt: str = "int"
    group_col: str | None = None
    order: str = "desc"
    ok: bool = True
    message: str = ""
    parsed: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 4. Helpers
# ---------------------------------------------------------------------------
def _norm(q: str) -> str:
    q = q.lower().strip()
    q = q.replace("\u2019", "'").replace("\u2013", "-").replace("\u2014", "-")
    q = re.sub(r"\s+", " ", q)
    return q


def _match_patterns(q: str, patterns: list[tuple[list[str], str]]) -> str | None:
    for phrases, value in patterns:
        for p in phrases:
            if re.search(r"\b" + re.escape(p) + r"\b", q):
                return value
    return None


def _fuzzy_value(q: str, candidates: list[str], cutoff: float = 0.82) -> str | None:
    words = re.findall(r"[a-z0-9\- ]+", q)
    for w in words:
        w = w.strip()
        if not w:
            continue
        m = difflib.get_close_matches(w, [c.lower() for c in candidates], n=1, cutoff=cutoff)
        if m:
            for c in candidates:
                if c.lower() == m[0]:
                    return c
    return None


def _find_city(q: str, cities: list[str]) -> str | None:
    for c in sorted(cities, key=len, reverse=True):
        if re.search(r"\b" + re.escape(c.lower()) + r"\b", q):
            return c
    return _fuzzy_value(q, cities, cutoff=0.88)


# ---------------------------------------------------------------------------
# 5. SQL validation
# ---------------------------------------------------------------------------
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|"
    r"reindex|grant|revoke|truncate|begin|commit|rollback)\b", re.I)


def validate_sql(sql: str) -> tuple[bool, str]:
    """Reject anything that is not a single read-only SELECT over allowed tables."""
    s = (sql or "").strip().rstrip(";").strip()
    if not s:
        return False, "Empty query."
    if not re.match(r"^(select|with)\b", s, re.I):
        return False, "Only SELECT queries are allowed."
    if _FORBIDDEN.search(s):
        return False, "Query contains a forbidden keyword (DDL/DML)."
    if ";" in s:
        return False, "Multiple statements are not allowed."
    for t in re.findall(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_]*)", s, re.I):
        if t.lower() not in ALLOWED_TABLES:
            return False, f"Table '{t}' is not allowed."
    return True, ""


# ---------------------------------------------------------------------------
# 6. LLM engine
# ---------------------------------------------------------------------------
_FEWSHOT = """
Q: What is the total revenue?
SQL: SELECT ROUND(SUM(Booking_Value),2) AS total_revenue FROM bookings WHERE Booking_Status='Success'

Q: How many bookings were cancelled by the driver?
SQL: SELECT COUNT(*) AS bookings FROM bookings WHERE Booking_Status='Canceled by Driver'

Q: Show revenue by vehicle type
SQL: SELECT Vehicle_Type, ROUND(SUM(Booking_Value),2) AS revenue FROM bookings WHERE Booking_Status='Success' GROUP BY Vehicle_Type ORDER BY revenue DESC

Q: Top 5 pickup areas by number of rides
SQL: SELECT Pickup_Location, COUNT(*) AS rides FROM bookings GROUP BY Pickup_Location ORDER BY rides DESC LIMIT 5

Q: Show the daily booking trend
SQL: SELECT Booking_Date, COUNT(*) AS bookings FROM bookings GROUP BY Booking_Date ORDER BY Booking_Date

Q: Average ride distance for each vehicle type
SQL: SELECT Vehicle_Type, ROUND(AVG(Ride_Distance),2) AS avg_distance_km FROM bookings GROUP BY Vehicle_Type ORDER BY avg_distance_km DESC

Q: What percentage of rides are paid by UPI?
SQL: SELECT ROUND(100.0*SUM(CASE WHEN Payment_Method='UPI' THEN 1 ELSE 0 END)/COUNT(*),2) AS pct FROM bookings
"""


def _llm_prompt(question: str, context: str = "") -> str:
    return (
        "You are an expert SQLite analyst. Write ONE read-only SQLite SELECT query "
        "that answers the user's question about the OLA rides dataset.\n\n"
        "RULES:\n"
        "- Return ONLY the SQL. No markdown fences, no explanation, no trailing semicolon.\n"
        "- Use only the table `bookings` (or the views successful_rides / cancellations).\n"
        "- Never use INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/PRAGMA.\n"
        "- Revenue = SUM(Booking_Value) restricted to Booking_Status='Success'.\n"
        "- Ratings and TAT are NULL for non-successful rides; AVG ignores NULLs automatically.\n"
        "- Add LIMIT 100 for row-listing queries; aggregates need no LIMIT.\n"
        "- Use ROUND(x,2) for averages and money.\n"
        "- Alias every computed column with a readable snake_case name.\n\n"
        f"SCHEMA:\n{SCHEMA}\n"
        "VALUE SAMPLES:\n"
        "  Vehicle_Type: Prime Sedan, Prime SUV, Prime Plus, Mini, Auto, Bike, E-Bike\n"
        "  Payment_Method: Cash, UPI, Credit Card, Debit Card, Not Applicable\n"
        "  Booking_Status: Success, Canceled by Customer, Canceled by Driver, Driver Not Found\n"
        "  Time_of_Day: Late Night (00-05), Early Morning (05-09), Morning (09-12), "
        "Afternoon (12-16), Evening Peak (16-20), Night (20-24)\n"
        "  Distance_Bucket: 0 km, 1-5 km, 6-10 km, 11-20 km, 21-30 km, 31-50 km\n"
        "  Value_Bucket: <250, 250-500, 500-750, 750-1000, 1000-1500, 1500+\n"
        "  Customer_Cancel_Category: Driver Behaviour, Vehicle Comfort, Customer Plans, Address Issue\n"
        "  Driver_Cancel_Category: Personal & Car Issue, Customer Health, Customer Issue, Capacity Violation\n"
        "  Incomplete_Reason_Category: Customer Demand, Vehicle Breakdown, Other Issue\n"
        "  Booking_Date range: 2024-07-01 .. 2024-07-31\n\n"
        f"EXAMPLES:\n{_FEWSHOT}\n"
        + (f"CONVERSATION CONTEXT (previous question): {context}\n" if context else "")
        + f"QUESTION: {question}\nSQL:"
    )


def _clean_sql(raw: str) -> str:
    s = (raw or "").strip()
    s = re.sub(r"^```(?:sql)?\s*", "", s, flags=re.I)
    s = re.sub(r"\s*```$", "", s)
    return s.strip().rstrip(";").strip()


def _llm_call(prompt: str) -> str | None:
    okey = os.getenv("OPENAI_API_KEY")
    akey = os.getenv("ANTHROPIC_API_KEY")
    gkey = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    try:
        if okey:
            from openai import OpenAI
            client = OpenAI(api_key=okey)
            r = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            return r.choices[0].message.content
        if akey:
            import anthropic
            client = anthropic.Anthropic(api_key=akey)
            r = client.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            return r.content[0].text
        if gkey:
            import requests
            model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{model}:generateContent?key={gkey}")
            r = requests.post(url, json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0},
            }, timeout=45)
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None
    return None


def _llm_translate(question: str, context: str = "") -> str | None:
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        return None
    raw = _llm_call(_llm_prompt(question, context))
    if not raw:
        return None
    sql = _clean_sql(raw)
    ok, _ = validate_sql(sql)
    return sql if ok else None


# ---------------------------------------------------------------------------
# 7. Rule engine
# ---------------------------------------------------------------------------
def _detect_filters(q: str, cities: list[str]) -> tuple[list[str], list[str]]:
    conds: list[str] = []
    labels: list[str] = []

    st = _match_patterns(q, STATUS_PATTERNS)
    if st:
        conds.append(f"Booking_Status = '{st}'")
        labels.append(st)
    elif re.search(r"\bcancel", q):
        conds.append("Booking_Status LIKE 'Canceled%'")
        labels.append("any cancellation")

    veh = _match_patterns(q, VEH_PATTERNS)
    if veh:
        conds.append(f"Vehicle_Type = '{veh}'")
        labels.append(veh)

    pay = _match_patterns(q, PAY_PATTERNS)
    if pay:
        conds.append(f"Payment_Method = '{pay}'")
        labels.append(pay)

    city = _find_city(q, cities)
    if city:
        conds.append(f"Pickup_Location = '{city}'")
        labels.append(city)

    m = re.search(r"between\s+(20\d{2}-\d{2}-\d{2})\s+and\s+(20\d{2}-\d{2}-\d{2})", q)
    if m:
        conds.append(f"Booking_Date BETWEEN '{m.group(1)}' AND '{m.group(2)}'")
        labels.append(f"{m.group(1)}..{m.group(2)}")
    else:
        m = re.search(r"(20\d{2}-\d{2}-\d{2})", q)
        if m:
            conds.append(f"Booking_Date = '{m.group(1)}'")
            labels.append(f"date {m.group(1)}")
        else:
            m = re.search(r"july\s+(\d{1,2})(?:st|nd|rd|th)?\b", q)
            if m:
                d = int(m.group(1))
                if 1 <= d <= 31:
                    conds.append(f"Booking_Date = '2024-07-{d:02d}'")
                    labels.append(f"2024-07-{d:02d}")

    m = re.search(r"between\s+(\d{1,2})\s*(?:am|pm|:00)?\s*(?:and|to|-)\s*(\d{1,2})\s*(am|pm)?", q)
    if m and ("hour" in q or "am" in q or "pm" in q or "time" in q):
        a, b = int(m.group(1)), int(m.group(2))
        if m.group(3) == "pm" and b < 12:
            b += 12
        if 0 <= a <= 23 and 0 <= b <= 23:
            conds.append(f"Booking_Hour BETWEEN {a} AND {b}")
            labels.append(f"hours {a}-{b}")
    else:
        m = re.search(r"after\s+(\d{1,2})\s*(am|pm)", q)
        if m:
            h = int(m.group(1)) % 12 + (12 if m.group(2) == "pm" else 0)
            conds.append(f"Booking_Hour >= {h}")
            labels.append(f"after {h}:00")
        m = re.search(r"before\s+(\d{1,2})\s*(am|pm)", q)
        if m:
            h = int(m.group(1)) % 12 + (12 if m.group(2) == "pm" else 0)
            conds.append(f"Booking_Hour < {h}")
            labels.append(f"before {h}:00")

    if not any("Booking_Hour" in c for c in conds):
        tod = None
        if re.search(r"\blate night\b", q):
            tod = "Late Night (00-05)"
        elif re.search(r"\bearly morning\b", q):
            tod = "Early Morning (05-09)"
        elif re.search(r"\bmorning\b", q):
            tod = "Morning (09-12)"
        elif re.search(r"\bafternoon\b", q):
            tod = "Afternoon (12-16)"
        elif re.search(r"\bevening\b", q):
            tod = "Evening Peak (16-20)"
        elif re.search(r"\bnight\b", q):
            tod = "Night (20-24)"
        if tod:
            conds.append(f"Time_of_Day = '{tod}'")
            labels.append(tod)

    if re.search(r"\bweekend", q):
        conds.append("Is_Weekend = 1")
        labels.append("weekend")
    elif re.search(r"\bweekday", q):
        conds.append("Is_Weekend = 0")
        labels.append("weekday")

    m = re.search(r"rating[s]?\s*(?:of\s*)?(?:above|over|greater than|more than|>=|>)\s*(\d(?:\.\d)?)", q)
    if m:
        conds.append(f"Driver_Ratings > {m.group(1)}")
        labels.append(f"driver rating > {m.group(1)}")
    m = re.search(r"rating[s]?\s*(?:of\s*)?(?:below|under|less than|<=|<)\s*(\d(?:\.\d)?)", q)
    if m:
        conds.append(f"Driver_Ratings < {m.group(1)}")
        labels.append(f"driver rating < {m.group(1)}")

    m = re.search(r"distance\s*(?:of\s*)?(?:more than|greater than|above|over|>=|>)\s*(\d+(?:\.\d+)?)\s*(?:km)?", q)
    if m:
        conds.append(f"Ride_Distance > {m.group(1)}")
        labels.append(f"distance > {m.group(1)} km")
    m = re.search(r"distance\s*(?:of\s*)?(?:less than|under|below|<=|<)\s*(\d+(?:\.\d+)?)\s*(?:km)?", q)
    if m:
        conds.append(f"Ride_Distance < {m.group(1)}")
        labels.append(f"distance < {m.group(1)} km")
    m = re.search(r"(?:fare|value|price|revenue)\s*(?:of\s*)?(?:more than|greater than|above|over|>=|>)\s*(?:rs\.?|inr|\u20b9)?\s*(\d+(?:\.\d+)?)", q)
    if m:
        conds.append(f"Booking_Value > {m.group(1)}")
        labels.append(f"fare > \u20b9{m.group(1)}")
    m = re.search(r"(?:fare|value|price)\s*(?:of\s*)?(?:less than|under|below|<=|<)\s*(?:rs\.?|inr|\u20b9)?\s*(\d+(?:\.\d+)?)", q)
    if m:
        conds.append(f"Booking_Value < {m.group(1)}")
        labels.append(f"fare < \u20b9{m.group(1)}")

    if re.search(r"\bincomplete\b", q) and not re.search(r"reason|why", q):
        conds.append("Incomplete_Rides = 'Yes'")
        labels.append("incomplete rides")

    # --- cancellation sub-category (e.g. "personal and car related issues") --
    if re.search(r"personal\s*(?:&|and)?\s*car|car related|personal issue", q):
        conds.append("Driver_Cancel_Category = 'Personal & Car Issue'")
        labels.append("driver: personal & car issue")
    elif re.search(r"capacity violation|too many people|more than permitted", q):
        conds.append("Driver_Cancel_Category = 'Capacity Violation'")
        labels.append("driver: capacity violation")
    elif re.search(r"customer (?:was )?(?:coughing|sick)|health", q):
        conds.append("Driver_Cancel_Category = 'Customer Health'")
        labels.append("driver: customer health")
    elif re.search(r"driver (?:behaviour|behavior)|not moving towards|asked to cancel", q):
        conds.append("Customer_Cancel_Category = 'Driver Behaviour'")
        labels.append("customer: driver behaviour")
    elif re.search(r"ac is not working|vehicle comfort|ac not working", q):
        conds.append("Customer_Cancel_Category = 'Vehicle Comfort'")
        labels.append("customer: vehicle comfort")
    elif re.search(r"change of plans|plans changed", q):
        conds.append("Customer_Cancel_Category = 'Customer Plans'")
        labels.append("customer: change of plans")
    elif re.search(r"wrong address|address issue", q):
        conds.append("Customer_Cancel_Category = 'Address Issue'")
        labels.append("customer: address issue")

    return conds, labels


def _detect_group(q: str) -> str | None:
    # "vehicle turnaround time" / "customer tat" are metrics, not group-bys
    if re.search(r"turnaround|\btat\b|wait time|pickup time", q) and " by " not in q:
        return None
    for phrases, col in GROUP_TARGETS:
        for p in phrases:
            if re.search(r"\b" + re.escape(p) + r"\b", q):
                return col
    return None


def _detect_time_grain(q: str) -> str | None:
    if re.search(r"day of week|weekday|day name|which day|day of the week", q):
        return "Booking_DayOfWeek"
    if re.search(r"\b(hourly|by hour|per hour|each hour|peak hour|busiest hour|what time|which hour|hour of)\b", q):
        return "Booking_Hour"
    if re.search(r"\b(weekly|by week|per week|each week)\b", q):
        return "week"
    if re.search(r"\b(monthly|by month|per month)\b", q):
        return "month"
    if re.search(r"\b(daily|by day|per day|each day|by date|over time|trend|time series|day by day|across days)\b", q):
        return "Booking_Date"
    return None


def _detect_metric(q: str) -> tuple[str, str | None]:
    if re.search(r"success rate|rate of success|percentage of (?:successful|success)|% success", q):
        return "success_rate", None
    if re.search(r"cancel(?:lation)? rate|rate of cancel|percentage of cancel", q):
        return "cancel_rate", None
    if re.search(r"\b(percentage|percent|share|proportion|%)\b", q):
        return "share", None

    if re.search(r"\b(distinct|unique)\b", q):
        if re.search(r"customer|rider|user", q):
            return "distinct_customers", "Customer_ID"
        if re.search(r"vehicle", q):
            return "distinct_vehicles", "Vehicle_Type"
        if re.search(r"city|area|location", q):
            return "distinct_cities", "Pickup_Location"
        return "distinct_customers", "Customer_ID"

    is_min = bool(re.search(r"\b(min|minimum|lowest|smallest|cheapest|least)\b", q))
    is_max = bool(re.search(r"\b(max|maximum|highest|largest|biggest|most expensive|priciest)\b", q))
    if is_min or is_max:
        col = None
        for phrases, c in NUMERIC_TARGETS:
            if any(p in q for p in phrases):
                col = c
                break
        if col is None:
            col = "Booking_Value"
        base = {"Booking_Value": "value", "Ride_Distance": "distance",
                "Driver_Ratings": "driver_rating", "Customer_Rating": "customer_rating",
                "Fare_per_km": "fare_per_km", "V_TAT": "v_tat", "C_TAT": "c_tat"}.get(col, "value")
        if is_min and is_max:
            return "minmax", col
        return ("min_" if is_min else "max_") + base, col

    if re.search(r"\b(average|avg|mean|typical)\b", q):
        for phrases, c in NUMERIC_TARGETS:
            if any(p in q for p in phrases):
                key = {"Booking_Value": "avg_value", "Ride_Distance": "avg_distance",
                       "Driver_Ratings": "avg_driver_rating", "Customer_Rating": "avg_customer_rating",
                       "Fare_per_km": "avg_fare_per_km", "V_TAT": "avg_v_tat",
                       "C_TAT": "avg_c_tat"}.get(c, "avg_value")
                return key, c
        return "avg_value", "Booking_Value"

    if re.search(r"\b(revenue|rev|earnings|sales|income|gmv|turnover|total value|total fare|"
                 r"booking value|total booking value|total amount|total money|how much money|"
                 r"how much revenue|billing|made|earn|earned)\b", q):
        return "revenue", "Booking_Value"
    if re.search(r"total distance|distance travelled|distance traveled|total km", q):
        return "sum_distance", "Ride_Distance"

    if re.search(r"\b(how many|count|number of|total number|how often|how much)\b", q):
        return "count", None

    return "count", None


# Cities present in the dataset (used when the caller does not supply them)
CITIES = [
    "BTM Layout", "Banashankari", "Bannerghatta Road", "Basavanagudi", "Bellandur",
    "Chamarajpet", "Chickpet", "Cox Town", "Devanahalli", "Electronic City",
    "Frazer Town", "HSR Layout", "Hebbal", "Hennur", "Hosur Road", "Hulimavu",
    "Indiranagar", "JP Nagar", "Jayanagar", "KR Puram", "Kadugodi", "Kammanahalli",
    "Kengeri", "Koramangala", "Langford Town", "MG Road", "Magadi Road", "Majestic",
    "Malleshwaram", "Marathahalli", "Mysore Road", "Nagarbhavi", "Padmanabhanagar",
    "Peenya", "RT Nagar", "Rajajinagar", "Rajarajeshwari Nagar", "Ramamurthy Nagar",
    "Richmond Town", "Sahakar Nagar", "Sarjapur Road", "Shantinagar", "Shivajinagar",
    "Tumkur Road", "Ulsoor", "Varthur", "Vijayanagar", "Whitefield", "Yelahanka",
    "Yeshwanthpur",
]


def _detect_order_limit(q: str) -> tuple[str, int | None]:
    order = "desc"
    if re.search(r"\b(bottom|lowest|least|fewest|smallest|worst|minimum)\b", q):
        order = "asc"
    limit = None
    m = re.search(r"\b(?:top|bottom|first|last|highest|lowest)\s+(\d{1,3})\b", q)
    if m:
        limit = int(m.group(1))
    else:
        m = re.search(r"\b(\d{1,3})\s+(?:top|highest|best|worst|lowest)\b", q)
        if m:
            limit = int(m.group(1))
    if limit is None and re.search(r"\b(top|bottom|highest|lowest|best|worst|most|least)\b", q):
        limit = 10
    return order, limit


def _is_row_listing(q: str) -> bool:
    return bool(re.search(
        r"\b(show all|list all|retrieve all|display all|all (?:the )?(?:successful|rides|bookings)|"
        r"show me all|give me all|all rides where|all bookings where|rows where|"
        r"which rides|which bookings|show rides|show bookings|list rides|list bookings)\b", q))


def _build_metric_sql(metric: str, col: str | None) -> tuple[str, str]:
    if metric == "count":
        return "COUNT(*)", "bookings"
    if metric == "revenue":
        return "ROUND(SUM(Booking_Value),2)", "revenue"
    if metric == "sum_distance":
        return "ROUND(SUM(Ride_Distance),2)", "total_distance_km"
    if metric == "avg_value":
        return "ROUND(AVG(Booking_Value),2)", "avg_fare"
    if metric == "avg_distance":
        return "ROUND(AVG(Ride_Distance),2)", "avg_distance_km"
    if metric == "avg_driver_rating":
        return "ROUND(AVG(Driver_Ratings),2)", "avg_driver_rating"
    if metric == "avg_customer_rating":
        return "ROUND(AVG(Customer_Rating),2)", "avg_customer_rating"
    if metric == "avg_v_tat":
        return "ROUND(AVG(V_TAT),2)", "avg_v_tat_min"
    if metric == "avg_c_tat":
        return "ROUND(AVG(C_TAT),2)", "avg_c_tat_min"
    if metric == "avg_fare_per_km":
        return "ROUND(AVG(Fare_per_km),2)", "avg_fare_per_km"
    if metric.startswith("min_"):
        c = {"min_value": "Booking_Value", "min_distance": "Ride_Distance",
             "min_driver_rating": "Driver_Ratings", "min_customer_rating": "Customer_Rating",
             "min_fare_per_km": "Fare_per_km", "min_v_tat": "V_TAT",
             "min_c_tat": "C_TAT"}.get(metric, "Booking_Value")
        return f"MIN({c})", metric
    if metric.startswith("max_"):
        c = {"max_value": "Booking_Value", "max_distance": "Ride_Distance",
             "max_driver_rating": "Driver_Ratings", "max_customer_rating": "Customer_Rating",
             "max_fare_per_km": "Fare_per_km", "max_v_tat": "V_TAT",
             "max_c_tat": "C_TAT"}.get(metric, "Booking_Value")
        return f"MAX({c})", metric
    if metric == "minmax":
        c = col or "Booking_Value"
        return f"MIN({c}) AS min_value, MAX({c}) AS max_value", "minmax"
    if metric == "distinct_customers":
        return "COUNT(DISTINCT Customer_ID)", "distinct_customers"
    if metric == "distinct_vehicles":
        return "COUNT(DISTINCT Vehicle_Type)", "distinct_vehicles"
    if metric == "distinct_cities":
        return "COUNT(DISTINCT Pickup_Location)", "distinct_cities"
    if metric == "success_rate":
        return ("ROUND(100.0*SUM(CASE WHEN Booking_Status='Success' THEN 1 ELSE 0 END)"
                "/COUNT(*),2)"), "success_rate_pct"
    if metric == "cancel_rate":
        return ("ROUND(100.0*SUM(CASE WHEN Booking_Status LIKE 'Canceled%' THEN 1 ELSE 0 END)"
                "/COUNT(*),2)"), "cancel_rate_pct"
    return "COUNT(*)", "bookings"


def _rev_sel(metric: str) -> str:
    if metric in ("revenue", "avg_value"):
        return ", ROUND(SUM(CASE WHEN Booking_Status='Success' THEN Booking_Value ELSE 0 END),2) AS revenue"
    return ""


def _rule_translate(question: str, context: str = "", cities: list[str] | None = None) -> Result:
    q = _norm(question)
    cities = cities or CITIES

    if re.search(r"\b(why|reason|reasons)\b", q) and re.search(r"cancel", q):
        if re.search(r"driver", q):
            col, status = "Driver_Cancel_Category", "Canceled by Driver"
        else:
            col, status = "Customer_Cancel_Category", "Canceled by Customer"
        sql = (f"SELECT {col} AS reason, COUNT(*) AS bookings "
               f"FROM bookings WHERE Booking_Status = '{status}' "
               f"AND {col} <> 'Not Applicable' "
               f"GROUP BY {col} ORDER BY bookings DESC")
        return Result(sql=sql, intent="group", chart_hint="bar", metric="count",
                      metric_label="bookings", fmt="int", group_col=col,
                      explanation=f"cancellation reasons ({status})",
                      parsed={"group_col": col, "metric": "count"})

    if re.search(r"\b(why|reason|reasons)\b", q) and re.search(r"incomplete", q):
        col = "Incomplete_Reason_Category"
        sql = (f"SELECT {col} AS reason, COUNT(*) AS bookings FROM bookings "
               f"WHERE Incomplete_Rides = 'Yes' AND {col} <> 'Not Applicable' "
               f"GROUP BY {col} ORDER BY bookings DESC")
        return Result(sql=sql, intent="group", chart_hint="bar", metric="count",
                      metric_label="bookings", fmt="int", group_col=col,
                      explanation="incomplete-ride reasons",
                      parsed={"group_col": col, "metric": "count"})

    conds, labels = _detect_filters(q, cities)

    if _is_row_listing(q):
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        sql = f"SELECT * FROM bookings{where} LIMIT 100"
        return Result(sql=sql, intent="rows", chart_hint="bar", metric="count",
                      metric_label="rows", fmt="int",
                      explanation="row listing" + (f" \u00b7 {', '.join(labels)}" if labels else ""),
                      parsed={"filters": labels})

    metric, mcol = _detect_metric(q)
    group_col = _detect_group(q)
    grain = _detect_time_grain(q)
    order, limit = _detect_order_limit(q)

    # distinct counts are always scalars, never group-bys
    if metric.startswith("distinct_"):
        group_col = None
        grain = None

    # rate metrics must not carry a status filter (it would force 0% or 100%)
    if metric in ("success_rate", "cancel_rate"):
        conds = [c for c in conds if "Booking_Status" not in c]
        labels = [l for l in labels if l not in STATUSES and l != "any cancellation"]

    # revenue / average fare are only meaningful on completed rides
    if metric in ("revenue", "avg_value") and not any("Booking_Status" in c for c in conds):
        conds.append("Booking_Status = 'Success'")
        labels.append("successful rides")

    where = (" WHERE " + " AND ".join(conds)) if conds else ""

    if re.search(r"\bwhich\b", q) and group_col and limit is None:
        limit = 1

    if metric == "share":
        if group_col:
            sql = (f"SELECT {group_col}, COUNT(*) AS bookings, "
                   f"ROUND(100.0*COUNT(*)/(SELECT COUNT(*) FROM bookings{where}),2) AS pct "
                   f"FROM bookings{where} GROUP BY {group_col} ORDER BY bookings DESC")
            return Result(sql=sql, intent="group", chart_hint="pie", metric="count",
                          metric_label="bookings", fmt="int", group_col=group_col,
                          explanation=f"share by {group_col}",
                          parsed={"group_col": group_col, "metric": "count", "share": True})
        if conds:
            sql = (f"SELECT ROUND(100.0*SUM(CASE WHEN {' AND '.join(conds)} THEN 1 ELSE 0 END)"
                   f"/COUNT(*),2) AS pct FROM bookings")
            return Result(sql=sql, intent="scalar", chart_hint="kpi", metric="share",
                          metric_label="share", fmt="pct",
                          explanation="share of matching rides",
                          parsed={"filters": labels})
        sql = ("SELECT Booking_Status, COUNT(*) AS bookings, "
               "ROUND(100.0*COUNT(*)/(SELECT COUNT(*) FROM bookings),2) AS pct "
               "FROM bookings GROUP BY Booking_Status ORDER BY bookings DESC")
        return Result(sql=sql, intent="group", chart_hint="pie", metric="count",
                      metric_label="bookings", fmt="int", group_col="Booking_Status",
                      explanation="share by status", parsed={"group_col": "Booking_Status"})

    if grain and not group_col:
        if grain == "Booking_Hour":
            sql = (f"SELECT Booking_Hour AS hour, COUNT(*) AS bookings{_rev_sel(metric)} "
                   f"FROM bookings{where} GROUP BY Booking_Hour ORDER BY Booking_Hour")
            return Result(sql=sql, intent="trend", chart_hint="line", metric=metric,
                          metric_label=METRIC_LABEL.get(metric, "bookings"),
                          fmt=FMT.get(metric, "int"), group_col="hour",
                          explanation="hourly trend", parsed={"grain": "hour", "metric": metric})
        if grain == "Booking_DayOfWeek":
            sql = (f"SELECT Booking_DayOfWeek AS day_of_week, COUNT(*) AS bookings{_rev_sel(metric)} "
                   f"FROM bookings{where} GROUP BY Booking_DayOfWeek "
                   f"ORDER BY MIN(DayOfWeek_Num)")
            return Result(sql=sql, intent="group", chart_hint="bar", metric=metric,
                          metric_label=METRIC_LABEL.get(metric, "bookings"),
                          fmt=FMT.get(metric, "int"), group_col="day_of_week",
                          explanation="by day of week", parsed={"grain": "dow", "metric": metric})
        if grain == "week":
            sql = (f"SELECT strftime('%Y-W%W', Booking_Date) AS week, COUNT(*) AS bookings{_rev_sel(metric)} "
                   f"FROM bookings{where} GROUP BY week ORDER BY week")
            return Result(sql=sql, intent="trend", chart_hint="line", metric=metric,
                          metric_label=METRIC_LABEL.get(metric, "bookings"),
                          fmt=FMT.get(metric, "int"), group_col="week",
                          explanation="weekly trend", parsed={"grain": "week", "metric": metric})
        if grain == "month":
            sql = (f"SELECT substr(Booking_Date,1,7) AS month, COUNT(*) AS bookings{_rev_sel(metric)} "
                   f"FROM bookings{where} GROUP BY month ORDER BY month")
            return Result(sql=sql, intent="trend", chart_hint="line", metric=metric,
                          metric_label=METRIC_LABEL.get(metric, "bookings"),
                          fmt=FMT.get(metric, "int"), group_col="month",
                          explanation="monthly trend", parsed={"grain": "month", "metric": metric})
        sql = (f"SELECT Booking_Date AS date, COUNT(*) AS bookings{_rev_sel(metric)} "
               f"FROM bookings{where} GROUP BY Booking_Date ORDER BY Booking_Date")
        return Result(sql=sql, intent="trend", chart_hint="line", metric=metric,
                      metric_label=METRIC_LABEL.get(metric, "bookings"),
                      fmt=FMT.get(metric, "int"), group_col="date",
                      explanation="daily trend", parsed={"grain": "day", "metric": metric})

    if group_col:
        expr, alias = _build_metric_sql(metric, mcol)
        if metric == "minmax":
            sql = (f"SELECT {group_col}, {expr} FROM bookings{where} "
                   f"GROUP BY {group_col} ORDER BY {group_col}")
            return Result(sql=sql, intent="group", chart_hint="bar", metric=metric,
                          metric_label="min / max", fmt="money", group_col=group_col,
                          explanation=f"min/max by {group_col}",
                          parsed={"group_col": group_col, "metric": metric})
        direction = "DESC" if order == "desc" else "ASC"
        lim = f" LIMIT {limit}" if limit else ""
        sql = (f"SELECT {group_col}, {expr} AS {alias} FROM bookings{where} "
               f"GROUP BY {group_col} ORDER BY {alias} {direction}{lim}")
        return Result(sql=sql, intent="group", chart_hint="bar", metric=metric,
                      metric_label=METRIC_LABEL.get(metric, "bookings"),
                      fmt=FMT.get(metric, "int"), group_col=group_col, order=order,
                      explanation=f"{METRIC_LABEL.get(metric, 'bookings')} by {group_col}",
                      parsed={"group_col": group_col, "metric": metric, "limit": limit})

    expr, alias = _build_metric_sql(metric, mcol)
    if metric == "minmax":
        sql = f"SELECT {expr} FROM bookings{where}"
        return Result(sql=sql, intent="scalar", chart_hint="kpi", metric=metric,
                      metric_label="min / max", fmt="money",
                      explanation="min and max", parsed={"metric": metric})
    sql = f"SELECT {expr} AS {alias} FROM bookings{where}"
    return Result(sql=sql, intent="scalar", chart_hint="kpi", metric=metric,
                  metric_label=METRIC_LABEL.get(metric, "bookings"),
                  fmt=FMT.get(metric, "int"),
                  explanation=METRIC_LABEL.get(metric, "bookings")
                  + (f" \u00b7 {', '.join(labels)}" if labels else ""),
                  parsed={"metric": metric, "filters": labels})


# ---------------------------------------------------------------------------
# 8. Public API
# ---------------------------------------------------------------------------
def translate(question: str, context: str = "", cities: list[str] | None = None) -> Result:
    """Translate a natural-language question into a validated SQLite SELECT."""
    if not question or not question.strip():
        return Result(ok=False, message="Please type a question about the OLA data.")

    sql = _llm_translate(question, context)
    if sql:
        return Result(sql=sql, engine="LLM", intent="aggregate", chart_hint="bar",
                      explanation="Generated by the LLM engine (schema-aware prompt).",
                      parsed={"llm": True})

    res = _rule_translate(question, context, cities)

    q = _norm(question)
    recognised = (
        res.parsed.get("group_col") or res.parsed.get("grain")
        or res.parsed.get("filters") or res.parsed.get("metric") not in (None, "count")
        or re.search(r"\b(how many|count|number of|total|revenue|average|avg|rating|distance|"
                     r"fare|booking|ride|cancel|payment|vehicle|city|area|hour|day|week|"
                     r"status|success|incomplete|driver|customer|price|value)\b", q)
    )
    if not recognised:
        res.ok = False
        res.message = (
            "I couldn't map that question to the OLA dataset. I can answer questions about "
            "**bookings, revenue, fares, ride distance, ratings, cancellations, payment methods, "
            "vehicle types, pickup areas, hours, days and trends**.\n\n"
            "Try rephrasing, for example:\n"
            "- *How many bookings were cancelled by the driver?*\n"
            "- *Show revenue by vehicle type*\n"
            "- *What is the average fare for Bike rides?*\n"
            "- *Which hour has the most bookings?*"
        )
    return res


def run(question: str, con, context: str = "", cities: list[str] | None = None):
    """Translate, validate, execute (with one LLM self-repair retry).

    Returns ``(Result, DataFrame | None, error | None)``.
    """
    import pandas as pd

    res = translate(question, context, cities)
    if not res.ok:
        return res, None, None

    ok, msg = validate_sql(res.sql)
    if not ok:
        res.ok = False
        res.message = f"The generated query was rejected by the safety validator: {msg}"
        return res, None, None

    try:
        return res, pd.read_sql(res.sql, con), None
    except Exception as exc:  # noqa: BLE001
        if res.engine == "LLM":
            repair_prompt = (
                _llm_prompt(question, context)
                + f"\n\n-- The previous query failed with this SQLite error:\n-- {exc}\n"
                  f"-- Previous query:\n-- {res.sql}\n-- Write a corrected query.\nSQL:"
            )
            raw = _llm_call(repair_prompt)
            if raw:
                fixed = _clean_sql(raw)
                ok2, _ = validate_sql(fixed)
                if ok2:
                    try:
                        df = pd.read_sql(fixed, con)
                        res.sql = fixed
                        res.explanation += " (self-repaired after an execution error)"
                        return res, df, None
                    except Exception as exc2:  # noqa: BLE001
                        return res, None, str(exc2)
        return res, None, str(exc)


# ---------------------------------------------------------------------------
# 9. Natural-language answer sentence
# ---------------------------------------------------------------------------
def _fmt_num(v: Any, fmt: str) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if fmt == "money":
        return f"\u20b9{f:,.0f}" if abs(f) >= 100 else f"\u20b9{f:,.2f}"
    if fmt == "km":
        return f"{f:,.2f} km"
    if fmt == "rating":
        return f"{f:.2f}"
    if fmt == "pct":
        return f"{f:.2f}%"
    if fmt == "min":
        return f"{f:,.1f} min"
    if fmt == "int":
        return f"{f:,.0f}"
    return f"{f:,.2f}"


def answer_sentence(df, res: Result) -> str:
    """One-line natural-language answer derived from the result set."""
    if df is None or len(df) == 0:
        return "No rows matched that question \u2014 try relaxing the filters."

    cols = list(df.columns)

    if res.intent == "scalar" or (len(df) == 1 and len(cols) <= 2):
        if res.metric == "minmax" and len(cols) >= 2:
            return (f"The minimum is {_fmt_num(df.iloc[0, 0], res.fmt)} and the maximum is "
                    f"{_fmt_num(df.iloc[0, 1], res.fmt)}.")
        val = df.iloc[0, 0]
        if res.metric == "share":
            return f"That is {_fmt_num(val, 'pct')} of all bookings."
        return f"The {res.metric_label} is {_fmt_num(val, res.fmt)}."

    if res.intent == "rows":
        return f"Returned {len(df):,} matching row(s) \u2014 showing the first {min(len(df), 100)}."

    if len(cols) < 2:
        return f"Returned {len(df):,} row(s)."

    gcol, vcol = cols[0], cols[1]
    try:
        vals = df[vcol].astype(float)
    except (TypeError, ValueError):
        return f"Returned {len(df):,} row(s) grouped by {gcol}."

    if vals.isna().all():
        return f"Returned {len(df):,} row(s) grouped by {gcol}."

    if res.order == "asc":
        idx = vals.idxmin()
        extreme = "lowest"
    else:
        idx = vals.idxmax()
        extreme = "highest"

    top_label = df.loc[idx, gcol]
    top_val = _fmt_num(df.loc[idx, vcol], res.fmt)
    label = res.metric_label

    if res.intent == "trend":
        first, last = vals.iloc[0], vals.iloc[-1]
        if first:
            chg = 100 * (last - first) / first
            direction = "up" if chg >= 0 else "down"
            return (f"{label.capitalize()} moved {direction} {abs(chg):.1f}% from "
                    f"{_fmt_num(first, res.fmt)} to {_fmt_num(last, res.fmt)} over the period; "
                    f"the peak was {top_label} at {top_val}.")

    if len(df) == 1:
        return f"{top_label} has {label} of {top_val}."

    return f"{top_label} has the {extreme} {label} at {top_val} (out of {len(df)} {gcol} values)."


if __name__ == "__main__":
    for t in EXAMPLE_QUESTIONS:
        r = translate(t)
        print(f"\nQ: {t}\n[{r.engine} | {r.intent} | {r.chart_hint}] {r.explanation}\n{r.sql}")
