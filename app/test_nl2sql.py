"""
test_nl2sql.py — regression test suite for the OLA natural-language → SQL engine.
================================================================================

Runs 55 varied natural-language questions through ``nl2sql.run()`` against the
real SQLite database and reports pass/fail with the generated SQL and result.

A test PASSES when:
  * the engine produced a query that executed without error,
  * the result set is non-empty,
  * the result shape matches the expected intent (scalar / group / trend / rows),
  * and, where an expected value is supplied, the answer matches it.

Run:  python test_nl2sql.py            # console report
      python test_nl2sql.py --md       # also writes TEST_REPORT.md
"""
from __future__ import annotations

import os
import sqlite3
import sys
import traceback

import pandas as pd

from nl2sql import answer_sentence, run, validate_sql

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "ola.db")

# (question, expected_intent, expected_value_or_None, tolerance)
CASES: list[tuple[str, str, float | None, float]] = [
    # ---- counts ---------------------------------------------------------
    ("How many bookings are there in total?", "scalar", 103024, 0),
    ("How many bookings were cancelled by the driver?", "scalar", 18434, 0),
    ("How many bookings were cancelled by the customer?", "scalar", 10499, 0),
    ("How many successful bookings are there?", "scalar", 63967, 0),
    ("Count of rides where the driver was not found", "scalar", 10124, 0),
    ("How many incomplete rides were there?", "scalar", 3926, 0),
    ("How many unique customers do we have?", "scalar", None, 0),
    ("Number of distinct pickup areas", "scalar", 50, 0),
    # ---- revenue / sums -------------------------------------------------
    ("What is the total revenue?", "scalar", 35080467, 5),
    ("Total booking value of successful rides", "scalar", 35080467, 5),
    ("What is the total distance travelled?", "scalar", None, 0),
    ("How much revenue did UPI rides generate?", "scalar", None, 0),
    ("Total revenue from Bike rides", "scalar", None, 0),
    # ---- averages -------------------------------------------------------
    ("What is the average fare?", "scalar", None, 0),
    ("Average ride distance for each vehicle type", "group", None, 0),
    ("What is the average fare for Bike rides?", "scalar", None, 0),
    ("Average driver rating", "scalar", 4.0, 0.05),
    ("Average customer rating per vehicle type", "group", None, 0),
    ("What is the average ride distance?", "scalar", None, 0),
    ("Average fare per km", "scalar", None, 0),
    ("What is the average vehicle turnaround time?", "scalar", None, 0),
    # ---- min / max ------------------------------------------------------
    ("Maximum and minimum driver rating for Prime Sedan bookings", "scalar", None, 0),
    ("What is the highest fare?", "scalar", 2999, 0),
    ("What is the lowest fare?", "scalar", 100, 0),
    ("Maximum ride distance", "scalar", 49, 0),
    # ---- group-bys ------------------------------------------------------
    ("Show revenue by vehicle type", "group", None, 0),
    ("Revenue by payment method", "group", None, 0),
    ("Booking status breakdown", "group", None, 0),
    ("Top 5 pickup areas by number of rides", "group", None, 0),
    ("Which city has the highest average fare?", "group", None, 0),
    ("Rides by time of day", "group", None, 0),
    ("Bookings by day of week", "group", None, 0),
    ("Show bookings by distance bucket", "group", None, 0),
    ("Revenue by value bucket", "group", None, 0),
    ("Average driver rating by vehicle type", "group", None, 0),
    ("Top 10 customers by number of bookings", "group", None, 0),
    ("Bottom 5 vehicle types by revenue", "group", None, 0),
    # ---- trends ---------------------------------------------------------
    ("Show the daily booking trend", "trend", None, 0),
    ("Hourly booking trend", "trend", None, 0),
    ("Weekly revenue trend", "trend", None, 0),
    ("Bookings over time", "trend", None, 0),
    ("Which hour has the most bookings?", "trend", None, 0),
    # ---- shares / rates -------------------------------------------------
    ("What percentage of rides are paid by UPI?", "scalar", None, 0),
    ("What is the success rate?", "scalar", 62.09, 0.5),
    ("What is the cancellation rate?", "scalar", None, 0),
    ("Share of bookings by payment method", "group", None, 0),
    ("What is the cancellation rate on weekends?", "scalar", None, 0),
    # ---- reasons --------------------------------------------------------
    ("Why do customers cancel?", "group", None, 0),
    ("Why do drivers cancel?", "group", None, 0),
    ("What are the reasons for incomplete rides?", "group", None, 0),
    # ---- row listings ---------------------------------------------------
    ("Show all successful bookings", "rows", None, 0),
    ("List all rides where payment was made using UPI", "rows", None, 0),
    ("Show rides with distance more than 30 km", "rows", None, 0),
    # ---- fuzzy / tricky phrasings ---------------------------------------
    ("how much money did ebike rides make", "scalar", None, 0),
    ("avg fare for prime sedan", "scalar", None, 0),
    ("whats the total rev", "scalar", None, 0),
    ("number of rides paid in cash", "scalar", None, 0),
    ("which vehicle type earns the most revenue", "group", None, 0),
    ("show me bookings in whitefield", "scalar", None, 0),
    ("rides cancelled by driver due to personal and car related issues", "scalar", 6542, 0),
    ("average rating of drivers for auto", "scalar", None, 0),
    ("top 3 areas by revenue", "group", None, 0),
    ("how many rides happened in the evening", "scalar", None, 0),
]

# Questions that must be gracefully rejected (out of scope)
OUT_OF_SCOPE = [
    "What is the weather in Bengaluru tomorrow?",
    "Who is the CEO of Tesla?",
    "Write me a poem about cars",
    "What is the capital of France?",
]


def _check(question: str, intent: str, expected: float | None, tol: float, con):
    res, df, err = run(question, con)
    if not res.ok:
        return False, res, df, f"engine rejected: {res.message[:80]}"
    if err:
        return False, res, df, f"SQL error: {err[:120]}"
    if df is None or len(df) == 0:
        return False, res, df, "empty result set"

    # intent shape check
    if intent == "scalar" and len(df) > 1:
        return False, res, df, f"expected scalar, got {len(df)} rows"
    if intent == "group" and len(df) < 2:
        return False, res, df, "expected multiple groups, got 1 row"
    if intent == "trend" and len(df) < 2:
        return False, res, df, "expected a series, got 1 row"
    if intent == "rows" and len(df) < 1:
        return False, res, df, "expected rows"

    if expected is not None:
        try:
            got = float(df.iloc[0, 0])
        except (TypeError, ValueError):
            return False, res, df, "first cell is not numeric"
        if abs(got - expected) > tol:
            return False, res, df, f"expected {expected}, got {got}"

    return True, res, df, ""


def main() -> int:
    if not os.path.exists(DB):
        print(f"ERROR: {DB} not found. Run `python build_db.py` first.")
        return 2

    con = sqlite3.connect(DB)
    rows = []
    passed = 0

    print("=" * 100)
    print("OLA NL→SQL ENGINE — TEST REPORT")
    print("=" * 100)

    for i, (q, intent, exp, tol) in enumerate(CASES, 1):
        try:
            ok, res, df, why = _check(q, intent, exp, tol, con)
        except Exception:  # noqa: BLE001
            ok, res, df, why = False, None, None, traceback.format_exc(limit=1)
        passed += ok
        status = "PASS" if ok else "FAIL"
        print(f"\n[{i:02d}] {status}  {q}")
        if res is not None:
            print(f"     engine={res.engine} intent={res.intent} chart={res.chart_hint}")
            print(f"     SQL: {res.sql}")
            if df is not None and len(df):
                print(f"     rows={len(df)}  answer: {answer_sentence(df, res)}")
        if not ok:
            print(f"     >>> {why}")
        rows.append({
            "n": i, "question": q, "status": status,
            "engine": getattr(res, "engine", ""),
            "intent": getattr(res, "intent", ""),
            "sql": getattr(res, "sql", ""),
            "rows": 0 if df is None else len(df),
            "answer": "" if df is None else answer_sentence(df, res),
            "note": why,
        })

    # out-of-scope handling
    print("\n" + "-" * 100)
    print("OUT-OF-SCOPE HANDLING (must be rejected gracefully, not answered wrongly)")
    oos_pass = 0
    for q in OUT_OF_SCOPE:
        res, df, err = run(q, con)
        ok = (not res.ok) and bool(res.message)
        oos_pass += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {q}  ->  "
              f"{'rejected with guidance' if ok else 'ANSWERED (bad!)'}")
        rows.append({"n": len(rows) + 1, "question": q,
                     "status": "PASS" if ok else "FAIL",
                     "engine": res.engine, "intent": "out-of-scope",
                     "sql": res.sql, "rows": 0 if df is None else len(df),
                     "answer": "", "note": "out-of-scope guard"})

    total = len(CASES) + len(OUT_OF_SCOPE)
    all_pass = passed + oos_pass
    rate = 100 * all_pass / total

    print("\n" + "=" * 100)
    print(f"RESULT: {all_pass}/{total} passed  ({rate:.1f}%)")
    print(f"  in-scope:    {passed}/{len(CASES)}")
    print(f"  out-of-scope:{oos_pass}/{len(OUT_OF_SCOPE)}")
    print("=" * 100)

    con.close()

    if "--md" in sys.argv:
        _write_md(rows, passed, oos_pass, total, rate)
    return 0 if rate >= 90 else 1


def _write_md(rows, passed, oos_pass, total, rate):
    out = os.path.join(HERE, "TEST_REPORT.md")
    lines = [
        "# NL→SQL Engine — Test Report",
        "",
        f"**Result: {passed + oos_pass}/{total} passed ({rate:.1f}%)**  ",
        f"In-scope: {passed}/{len(CASES)} · Out-of-scope guard: {oos_pass}/{len(OUT_OF_SCOPE)}",
        "",
        "Generated by `test_nl2sql.py` against the live `ola.db` (103,024 rows).",
        "",
        "| # | Question | Status | Engine | Intent | Rows | Answer |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        q = r["question"].replace("|", "\\|")
        a = (r["answer"] or "").replace("|", "\\|")
        lines.append(f"| {r['n']} | {q} | {r['status']} | {r['engine']} | "
                     f"{r['intent']} | {r['rows']} | {a} |")
    lines += ["", "## Generated SQL per question", ""]
    for r in rows:
        if r["sql"]:
            lines += [f"### {r['n']}. {r['question']}", "", "```sql", r["sql"], "```", ""]
    with open(out, "w") as f:
        f.write("\n".join(lines))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    sys.exit(main())
