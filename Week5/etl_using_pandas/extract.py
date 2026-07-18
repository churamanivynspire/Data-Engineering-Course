import logging
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)


def extract(conn, sql, params=None):
    try:
        df = pd.read_sql_query(sql, conn, params=params)
        logger.info(f"Extracted {len(df)} rows from the table")
        return df
    except Exception as e:
        logger.error(str(e))
        raise


def extract_driver(conn):
    sql = """
    SELECT driver_id, name, status, joined_at
    FROM drivers
    """
    return extract(conn, sql)


def extract_passenger(conn):
    sql = """
    SELECT passenger_id, name, status, created_at
    FROM passengers
    """
    return extract(conn, sql)


def extract_location(conn):
    sql = """
    SELECT location_id, city_name, state_province, country, latitude, longitude
    FROM locations
    """
    return extract(conn, sql)


def extract_payment_method(conn):
    sql = """
    SELECT payment_method_id, name, type, is_active
    FROM payment_methods
    """
    return extract(conn, sql)


def extract_promo_code(conn):
    sql = """
    SELECT promo_code_id, code, discount_type, discount_value, is_active
    FROM promo_codes
    """
    return extract(conn, sql)


def extract_trips_incremental(conn, watermark):
    sql = """
      SELECT
        t.trip_id,
        t.driver_id,
        t.passenger_id,
        t.pickup_location_id,
        t.dropoff_location_id,
        t.payment_method_id,
        t.promo_code_id,
        t.base_fare,
        t.tip_amount,
        t.discount_amount,
        t.surge_multiplier,
        t.distance_km,
        t.status,
        t.requested_at,
        t.completed_at,
        t.driver_rating,
        t.passenger_rating,
        tc.cancelled_by          -- from trip_cancellations (NULL for non-cancelled)
    FROM  trips t
    LEFT JOIN trip_cancellations tc ON t.trip_id = tc.trip_id
     WHERE t.requested_at > %(watermark)s
    ORDER BY t.requested_at
        """
    return extract(conn, sql, {"watermark": watermark})


def extract_trips_full(conn):
    sql = """
      SELECT
        t.trip_id,
        t.driver_id,
        t.passenger_id,
        t.pickup_location_id,
        t.dropoff_location_id,
        t.payment_method_id,
        t.promo_code_id,
        t.base_fare,
        t.tip_amount,
        t.discount_amount,
        t.surge_multiplier,
        t.distance_km,
        t.status,
        t.requested_at,
        t.completed_at,
        t.driver_rating,
        t.passenger_rating,
        tc.cancelled_by          -- from trip_cancellations (NULL for non-cancelled)
    FROM  trips t
    LEFT JOIN trip_cancellations tc ON t.trip_id = tc.trip_id
    ORDER BY t.requested_at
        """
    return extract(conn, sql)


def extract_lookup_dim(conn):
    logger.info("Loading lookup tables into memory")
    lookup = {
        "driver": pd.read_sql_query("SELECT driver_id, driver_key FROM dim_driver", conn),
        "passenger": pd.read_sql_query("SELECT passenger_id, passenger_key FROM dim_passenger", conn),
        "location": pd.read_sql_query("SELECT location_id, location_key FROM dim_location", conn),
        "payment_method": pd.read_sql_query(
            "SELECT payment_method_id, payment_method_key FROM dim_payment_method", conn
        ),
        "promo_code": pd.read_sql_query("SELECT promo_code_id, promo_code_key FROM dim_promo_code", conn),
        "date": pd.read_sql_query("SELECT date_key FROM dim_date", conn),
    }
    return lookup


def get_watermark(conn) -> datetime:
    """
    Return the most recent requested_at already loaded in the warehouse.
    Falls back to 2000-01-01 on an empty fact table so the first run
    behaves as a full load without special-casing.
    """
    df = pd.read_sql_query(
        """
        SELECT COALESCE(MAX(requested_at), '2000-01-01'::TIMESTAMP) AS watermark
        FROM fact_trips
        """,
        conn,
    )
    watermark = df["watermark"].iloc[0]
    logger.info(f"Watermark: {watermark}")
    return watermark
