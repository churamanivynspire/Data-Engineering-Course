import logging
import os
from datetime import datetime

from db import Database

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SOURCE_DB_NAME = os.getenv("SOURCE_DB_NAME", "rides_2")
TARGET_DB_NAME = os.getenv("TARGET_DB_NAME", "rides_dw")

# US census-style regions, keyed by state_province. Any country other than
# "USA" is bucketed as "International".
STATE_TO_REGION = {
    "New York": "Northeast", "Pennsylvania": "Northeast",
    "Illinois": "Midwest", "Ohio": "Midwest",
    "Texas": "South", "Florida": "South", "Tennessee": "South",
    "Arizona": "West", "California": "West", "Washington": "West",
    "Colorado": "West", "Nevada": "West", "Oregon": "West",
}


def region_for(state_province: str, country: str) -> str:
    if country != "USA":
        return "International"
    return STATE_TO_REGION.get(state_province, "Other")


def tenure_bucket_for(joined_at: datetime) -> str:
    months = (datetime.now() - joined_at).days / 30
    if months < 6:
        return "0-6 months"
    if months < 12:
        return "6-12 months"
    if months < 24:
        return "1-2 years"
    return "2+ years"


class WarehouseMigrator:
    def __init__(self, source_db: Database, target_db: Database):
        self.source_db = source_db
        self.target_db = target_db
        self.driver_key = {}          # driver_id -> driver_key
        self.passenger_key = {}       # passenger_id -> passenger_key
        self.location_key = {}        # location_id -> location_key
        self.payment_method_key = {}  # payment_method_id (incl. None) -> key
        self.promo_code_key = {}      # promo_code_id (incl. None) -> key

    def truncate_target(self) -> None:
        self.target_db.execute(
            "TRUNCATE fact_trips, dim_driver, dim_passenger, "
            "dim_location, dim_payment_method, dim_promo_code "
            "RESTART IDENTITY CASCADE"
        )

    def migrate_dim_driver(self) -> None:
        drivers = self.source_db.fetch_all(
            "SELECT driver_id, name, status, joined_at FROM drivers"
        )

        rows = [
            (driver_id, name, status, joined_at, tenure_bucket_for(joined_at))
            for driver_id, name, status, joined_at in drivers
        ]
        result = self.target_db.insert_returning(
            """INSERT INTO dim_driver (driver_id, name, status, joined_at, tenure_bucket)
               VALUES %s RETURNING driver_id, driver_key""",
            rows,
        )
        self.driver_key = dict(result)

    def migrate_dim_passenger(self) -> None:
        passengers = self.source_db.fetch_all(
            "SELECT passenger_id, name, status, created_at FROM passengers"
        )

        rows = [
            (passenger_id, name, status, created_at.strftime("%Y-%m"), created_at)
            for passenger_id, name, status, created_at in passengers
        ]
        result = self.target_db.insert_returning(
            """INSERT INTO dim_passenger (passenger_id, name, status, cohort_month, created_at)
               VALUES %s RETURNING passenger_id, passenger_key""",
            rows,
        )
        self.passenger_key = dict(result)

    def migrate_dim_location(self) -> None:
        locations = self.source_db.fetch_all(
            "SELECT location_id, city_name, state_province, country, latitude, longitude "
            "FROM locations"
        )

        rows = [
            (loc_id, city, state, country, region_for(state, country), lat, lon)
            for loc_id, city, state, country, lat, lon in locations
        ]
        result = self.target_db.insert_returning(
            """INSERT INTO dim_location
                   (location_id, city_name, state_province, country, region, latitude, longitude)
               VALUES %s RETURNING location_id, location_key""",
            rows,
        )
        self.location_key = dict(result)

    def migrate_dim_payment_method(self) -> None:
        rows = self.source_db.fetch_all(
            "SELECT payment_method_id, name, type, is_active FROM payment_methods"
        )
        rows.append((None, "Unknown", None, False))

        result = self.target_db.insert_returning(
            """INSERT INTO dim_payment_method (payment_method_id, name, type, is_active)
               VALUES %s RETURNING payment_method_id, payment_method_key""",
            rows,
        )
        self.payment_method_key = dict(result)

    def migrate_dim_promo_code(self) -> None:
        rows = self.source_db.fetch_all(
            "SELECT promo_code_id, code, discount_type, discount_value, is_active "
            "FROM promo_codes"
        )
        rows.append((None, "No Promo", None, None, None))

        result = self.target_db.insert_returning(
            """INSERT INTO dim_promo_code (promo_code_id, code, discount_type, discount_value, is_active)
               VALUES %s RETURNING promo_code_id, promo_code_key""",
            rows,
        )
        self.promo_code_key = dict(result)

    def migrate_fact_trips(self) -> None:
        trips = self.source_db.fetch_all("""
            SELECT trip_id, driver_id, passenger_id, pickup_location_id, dropoff_location_id,
                   payment_method_id, promo_code_id, base_fare, tip_amount, discount_amount,
                   fare_amount, distance_km, duration_minutes, driver_rating, passenger_rating,
                   surge_multiplier, requested_at
            FROM v_trips
        """)

        rows = [
            (
                trip_id,
                int(requested_at.strftime("%Y%m%d")),
                self.driver_key[driver_id],
                self.passenger_key[passenger_id],
                self.location_key[pickup_id],
                self.location_key[dropoff_id],
                self.payment_method_key.get(payment_method_id),
                self.promo_code_key.get(promo_code_id),
                base_fare, tip_amount, discount_amount, fare_amount,
                distance_km, duration_minutes, driver_rating, passenger_rating,
                surge_multiplier, requested_at,
            )
            for trip_id, driver_id, passenger_id, pickup_id, dropoff_id,
                payment_method_id, promo_code_id, base_fare, tip_amount, discount_amount,
                fare_amount, distance_km, duration_minutes, driver_rating, passenger_rating,
                surge_multiplier, requested_at in trips
        ]

        self.target_db.execute_values(
            """INSERT INTO fact_trips (
                   source_trip_id, date_key, driver_key, passenger_key,
                   pickup_location_key, dropoff_location_key,
                   payment_method_key, promo_code_key,
                   base_fare, tip_amount, discount_amount, fare_amount,
                   distance_km, duration_minutes, driver_rating, passenger_rating,
                   surge_multiplier, requested_at
               ) VALUES %s""",
            rows, page_size=1000,
        )

    def run(self) -> None:
        self.truncate_target()
        self.migrate_dim_driver()
        self.migrate_dim_passenger()
        self.migrate_dim_location()
        self.migrate_dim_payment_method()
        self.migrate_dim_promo_code()
        self.migrate_fact_trips()


def main() -> None:
    logger.info("Connecting to source and target databases…")
    source_db = Database({"dbname": SOURCE_DB_NAME}).connect()
    target_db = Database({"dbname": TARGET_DB_NAME}).connect()

    migrator = WarehouseMigrator(source_db, target_db)

    try:
        migrator.run()
        target_db.commit()
        logger.info("Warehouse load committed successfully.")

        tables = [
            "dim_driver", "dim_passenger", "dim_location",
            "dim_payment_method", "dim_promo_code", "fact_trips",
        ]
        logger.info("─── Final row counts ─────────────────────────")
        for table in tables:
            count = target_db.fetch_all(f"SELECT COUNT(*) FROM {table}")[0][0]
            logger.info(f"    {table:<25}  {count:>7,}")
        logger.info("──────────────────────────────────────────────")

    except Exception:
        target_db.rollback()
        logger.exception("Transaction rolled back")
        raise
    finally:
        source_db.close()
        target_db.close()


if __name__ == "__main__":
    main()
