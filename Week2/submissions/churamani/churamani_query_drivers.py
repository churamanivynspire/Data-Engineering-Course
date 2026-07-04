"""
churamani_query_drivers.py
--------------------------
Week 2 Assignment — Python + PostgreSQL

Counts completed rides per driver and prints a formatted table.
Run:  python churamani_query_drivers.py   (with a .env file present)
"""

import os
import psycopg2
from dotenv import load_dotenv


# The SQL query is provided — do not change it.
SQL = """
    SELECT
        d.name              AS driver_name,
        COUNT(t.trip_id)    AS completed_rides
    FROM drivers d
    LEFT JOIN trips t
        ON t.driver_id = d.driver_id
        AND t.status = 'completed'
    GROUP BY d.driver_id, d.name
    ORDER BY completed_rides DESC;
"""


# ─── TASK 1 ───────────────────────────────────────────────────────────────────
def load_config() -> dict:
    """Load database credentials from a .env file."""
    load_dotenv()
    return {
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT"),
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
    }


# ─── TASK 2 ───────────────────────────────────────────────────────────────────
def get_connection(config: dict):
    """Open and return a psycopg2 database connection."""
    return psycopg2.connect(**config)


# ─── TASK 3 ───────────────────────────────────────────────────────────────────
def fetch_drivers(conn) -> list:
    """Execute the SQL query and return all rows as (driver_name, completed_rides)."""
    cur = conn.cursor()
    cur.execute(SQL)
    rows = cur.fetchall()
    cur.close()
    return rows


# ─── TASK 4 ───────────────────────────────────────────────────────────────────
def print_results(rows: list) -> None:
    """Print the query results as a formatted table."""
    print(f"{'Driver':<25}{'Completed Rides':>15}")
    print("-" * 42)
    for driver_name, completed_rides in rows:
        print(f"{driver_name:<25}{completed_rides:>15}")
    print("-" * 42)
    print(f"{'Total drivers:':<25}{len(rows):>15}")


# ─────────────────────────────────────────────────────────────────────────────
def main():
    config = load_config()

    try:
        conn = get_connection(config)
    except psycopg2.OperationalError as e:
        print(f"Connection failed: {e}")
        return

    rows = fetch_drivers(conn)
    print_results(rows)

    conn.close()


if __name__ == "__main__":
    main()
