"""
load_test_1m.py
───────────────
INSTRUCTOR TOOL — Week 3, Day 2
Load 1,000,000 rows into the trips table so index performance
is clearly visible in EXPLAIN ANALYZE.

At 5,000 rows PostgreSQL often chooses Seq Scan even WITH an index
because the table fits in memory. At 1,000,000 rows:
  - Seq Scan:   300-800 ms
  - Index Scan:   1-5 ms
Students can SEE the difference with their own eyes.

Usage
─────
  pip install psycopg2-binary
  python load_test_1m.py

Options (edit the CONFIG block below):
  BATCH_SIZE   — rows per transaction (default 10,000)
  TOTAL_ROWS   — total rows to insert (default 1,000,000)
  RESET_FIRST  — delete existing trips before loading (default True)

The script logs progress every batch so students can watch it run.
Expected runtime: 60-120 seconds on a typical laptop.

After running, use the DEMO QUERIES at the bottom of this file
in DBeaver to show the before/after index effect.
"""

import psycopg2
import psycopg2.extras
import random
import logging
import time
from datetime import datetime, timedelta

# ── Configuration ─────────────────────────────────────────────────
DB_CONFIG = dict(
    host="localhost",
    port=5432,
    dbname="ride_share",
    user="postgres",
    password="hello123",
)

BATCH_SIZE  = 10_000    # rows per transaction — larger = faster load
TOTAL_ROWS  = 1_000_000 # total rows to insert
RESET_FIRST = True      # set False to ADD to existing data instead
LOG_EVERY   = 5         # log a progress line every N batches

# ── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Reference data ────────────────────────────────────────────────
# These must match what's actually in your drivers / passengers / locations tables.
# The script reads real IDs from the DB so it always stays valid.

STATUSES = ["completed", "completed", "completed", "cancelled", "no_show"]
# weighted so ~57% completed, ~29% cancelled, ~14% in_progress
# (matches the realistic distribution from the original 5k load)

BASE_DATE = datetime(2023, 1, 1)   # trips spread across ~2.7 years from here


# ── Helpers ───────────────────────────────────────────────────────

def fetch_ids(conn, table: str, id_col: str) -> list[int]:
    """Read all existing IDs from a reference table."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT {id_col} FROM {table} ORDER BY {id_col}")
        return [row[0] for row in cur.fetchall()]


def random_trip(driver_ids, passenger_ids, location_ids, payment_method_ids, row_index: int) -> dict:
    """
    Generate one realistic trip row.
    row_index is used to spread requested_at across ~2.7 years
    so window function queries (running totals) look natural.
    """
    status = random.choice(STATUSES)

    # Spread dates evenly: one trip every ~85 seconds across 2.7 years
    requested_at = BASE_DATE + timedelta(seconds=row_index * 85)
    duration_min = random.randint(8, 90)
    completed_at = (
        requested_at + timedelta(minutes=duration_min)
        if status == "completed"
        else None
    )

    fare_amount  = round(random.uniform(80, 2500), 2)
    distance_km  = round(random.uniform(0.8, 45.0), 1)

    # Rating only on completed trips, and not always (some passengers don't rate)
    rating = None
    if status == "completed" and random.random() < 0.78:
        rating = round(random.uniform(1.0, 5.0), 1)

    pickup_id   = random.choice(location_ids)
    dropoff_id  = random.choice(location_ids)
    # Avoid same pickup and dropoff
    while dropoff_id == pickup_id and len(location_ids) > 1:
        dropoff_id = random.choice(location_ids)

    return dict(
        driver_id             = random.choice(driver_ids),
        passenger_id              = random.choice(passenger_ids),
        pickup_location_id    = pickup_id,
        dropoff_location_id   = dropoff_id,
        fare_amount           = fare_amount,
        distance_km           = distance_km,
        status                = status,
        requested_at          = requested_at,
        completed_at          = completed_at,
        rating                = rating,
        payment_method_id     = random.choice(payment_method_ids),
    )


INSERT_SQL = """
    INSERT INTO trips (
        driver_id, passenger_id,
        pickup_location_id, dropoff_location_id,
        fare_amount, distance_km, status,
        requested_at, completed_at, rating, payment_method_id
    ) VALUES (
        %(driver_id)s, %(passenger_id)s,
        %(pickup_location_id)s, %(dropoff_location_id)s,
        %(fare_amount)s, %(distance_km)s, %(status)s,
        %(requested_at)s, %(completed_at)s,
        %(rating)s, %(payment_method_id)s
    )
"""


def load_batch(conn, rows: list[dict]) -> None:
    """Insert one batch inside a single transaction. Rolls back on error."""
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, INSERT_SQL, rows, page_size=1000)
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"Batch failed — rolled back. Error: {e}")
        raise


def reset_trips(conn) -> None:
    """Delete all rows from trips (keeps the table structure intact)."""
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM trips")
    log.info("Existing trips deleted — starting fresh")


# ── Main ──────────────────────────────────────────────────────────

def main():
    log.info("Connecting to database…")
    conn = psycopg2.connect(**DB_CONFIG)

    # ── 1. Optionally reset ──────────────────────────────────────
    if RESET_FIRST:
        reset_trips(conn)

    # ── 2. Read reference IDs from DB ───────────────────────────
    log.info("Reading reference IDs from drivers / passengers / locations / payment_methods…")
    driver_ids          = fetch_ids(conn, "drivers",         "driver_id")
    passenger_ids       = fetch_ids(conn, "passengers",          "passenger_id")
    location_ids        = fetch_ids(conn, "locations",       "location_id")
    payment_method_ids  = fetch_ids(conn, "payment_methods", "payment_method_id")

    if not driver_ids or not passenger_ids or not location_ids or not payment_method_ids:
        log.error(
            "One or more reference tables are empty. "
            "Make sure drivers, passengers, locations, and payment_methods are populated first."
        )
        return

    log.info(
        f"Found {len(driver_ids)} drivers, "
        f"{len(passenger_ids)} passengers, "
        f"{len(location_ids)} locations, "
        f"{len(payment_method_ids)} payment methods"
    )

    # ── 3. Generate and insert in batches ───────────────────────
    total_loaded = 0
    batch_count  = 0
    num_batches  = (TOTAL_ROWS + BATCH_SIZE - 1) // BATCH_SIZE
    start_time   = time.time()

    log.info(
        f"Starting load: {TOTAL_ROWS:,} rows "
        f"in {num_batches} batches of {BATCH_SIZE:,}"
    )
    log.info("─" * 55)

    for batch_num in range(num_batches):
        # Last batch may be smaller
        rows_this_batch = min(BATCH_SIZE, TOTAL_ROWS - total_loaded)

        rows = [
            random_trip(
                driver_ids,
                passenger_ids,
                location_ids,
                payment_method_ids,
                row_index=total_loaded + i,
            )
            for i in range(rows_this_batch)
        ]

        load_batch(conn, rows)
        total_loaded += rows_this_batch
        batch_count  += 1

        # Progress log every LOG_EVERY batches
        if batch_count % LOG_EVERY == 0 or total_loaded == TOTAL_ROWS:
            elapsed    = time.time() - start_time
            pct        = total_loaded / TOTAL_ROWS * 100
            rows_per_s = total_loaded / elapsed if elapsed > 0 else 0
            eta_s      = (TOTAL_ROWS - total_loaded) / rows_per_s if rows_per_s > 0 else 0
            log.info(
                f"  {total_loaded:>9,} / {TOTAL_ROWS:,} rows  "
                f"({pct:5.1f}%)  "
                f"{rows_per_s:,.0f} rows/s  "
                f"ETA {int(eta_s)}s"
            )

    elapsed = time.time() - start_time
    log.info("─" * 55)
    log.info(f"Done.  {total_loaded:,} rows loaded in {elapsed:.1f}s")
    log.info(f"Average speed: {total_loaded / elapsed:,.0f} rows/second")

    # ── 4. Final count verification ──────────────────────────────
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM trips")
        final_count = cur.fetchone()[0]
    log.info(f"Trips table now has {final_count:,} rows total")

    conn.close()


if __name__ == "__main__":
    main()


# ════════════════════════════════════════════════════════════════════
# DEMO QUERIES — run these in DBeaver after loading
# Copy into a new SQL tab and run step by step with students
# ════════════════════════════════════════════════════════════════════
#
# ── STEP 1: Drop any existing indexes (clean baseline) ───────────
#
#   DROP INDEX IF EXISTS idx_trips_driver_id;
#   DROP INDEX IF EXISTS idx_trips_status;
#   DROP INDEX IF EXISTS idx_trips_driver_status;
#
# ── STEP 2: Run WITHOUT indexes — record execution times ─────────
#
#   -- Query A: filter by driver_id
#   EXPLAIN ANALYZE
#   SELECT * FROM trips WHERE driver_id = 3;
#   -- Expected: Seq Scan, ~300–800 ms
#   -- Record: Seq Scan · execution time = _____ ms
#
#   -- Query B: filter by status
#   EXPLAIN ANALYZE
#   SELECT * FROM trips WHERE status = 'cancelled';
#   -- Expected: Seq Scan, ~300–800 ms
#
#   -- Query C: filter by driver_id AND status
#   EXPLAIN ANALYZE
#   SELECT * FROM trips WHERE driver_id = 3 AND status = 'completed';
#   -- Expected: Seq Scan, ~300–800 ms
#
# ── STEP 3: Add indexes one at a time ────────────────────────────
#
#   CREATE INDEX idx_trips_driver_id ON trips(driver_id);
#
#   -- Re-run Query A immediately:
#   EXPLAIN ANALYZE
#   SELECT * FROM trips WHERE driver_id = 3;
#   -- Expected: Index Scan, 1–5 ms  ← students will gasp
#   -- Record: Index Scan · execution time = _____ ms
#
#   CREATE INDEX idx_trips_status ON trips(status);
#
#   -- Re-run Query B:
#   EXPLAIN ANALYZE
#   SELECT * FROM trips WHERE status = 'cancelled';
#   -- Expected: STILL Seq Scan or Bitmap Scan — low cardinality (3 values)
#   -- This is the key lesson: indexes on low-cardinality columns are ignored
#
#   CREATE INDEX idx_trips_driver_status ON trips(driver_id, status);
#
#   -- Re-run Query C:
#   EXPLAIN ANALYZE
#   SELECT * FROM trips WHERE driver_id = 3 AND status = 'completed';
#   -- Expected: Index Scan using composite index, 1–5 ms
#
# ── STEP 4: The covering index bonus (advanced) ──────────────────
#
#   CREATE INDEX idx_trips_driver_fare
#   ON trips(driver_id)
#   INCLUDE (fare_amount);
#
#   EXPLAIN ANALYZE
#   SELECT driver_id, SUM(fare_amount)
#   FROM trips
#   WHERE driver_id = 3
#   GROUP BY driver_id;
#   -- Expected: Index Only Scan — never touches the main table
#
# ── CLEANUP (run after demo if students want to reset) ────────────
#
#   DROP INDEX IF EXISTS idx_trips_driver_id;
#   DROP INDEX IF EXISTS idx_trips_status;
#   DROP INDEX IF EXISTS idx_trips_driver_status;
#   DROP INDEX IF EXISTS idx_trips_driver_fare;
#
# ════════════════════════════════════════════════════════════════════
