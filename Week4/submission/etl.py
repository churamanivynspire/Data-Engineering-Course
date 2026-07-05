import os
from typing import Any, Sequence

from dotenv import load_dotenv
from psycopg2.extras import RealDictRow

import queries
from db import Database
from logging_config import get_logger

logger = get_logger(__name__)

load_dotenv()


class ETL:
    def __init__(self, source_db: Database, target_db: Database):
        self.source_db = source_db
        self.target_db = target_db

    def extract(self, sql: str, as_dict: bool = False) -> list:
        rows = self.source_db.fetch_dicts(sql) if as_dict else self.source_db.fetch_all(sql)
        logger.info(f"Extracted {len(rows)} rows")
        return rows

    def load_dim(
        self,
        sql: str,
        data: Sequence[Sequence[Any]],
        label: str,
    ) -> dict[int, int]:
        result = self.target_db.insert_returning(sql, data)
        self.target_db.commit()
        logger.info(f"{len(result)} inserted to {label}")
        return dict(result)

    def load_fact(
        self,
        sql: str,
        data: Sequence[Sequence[Any]],
        label: str,
    ) -> None:
        if not data:
            logger.info(f"No rows to load — skipping {label}")
            return
        result = self.target_db.insert_returning(sql, data)
        self.target_db.commit()
        logger.info(f"{len(result)} inserted to {label}")


def transform(
    oltp_rows: Sequence[RealDictRow],
    lookups: dict[str, dict[int, Any]],
) -> list[tuple]:
    fact_rows = []
    skipped = 0
    for row in oltp_rows:
        trip_id = row["trip_id"]

        date_key = int(row["requested_at"].strftime("%Y%m%d"))
        if date_key not in lookups["date"]:
            logger.warning(
                f"trip {trip_id}: date_key {date_key} outside of dim_date range — skipped"
            )
            skipped += 1
            continue

        driver_key = lookups["driver"].get(row["driver_id"])
        if driver_key is None:
            logger.warning(
                f"trip {trip_id}: driver_id {row['driver_id']} not in dim_driver — skipped"
            )
            skipped += 1
            continue

        passenger_key = lookups["passenger"].get(row["passenger_id"])
        if passenger_key is None:
            logger.warning(
                f"trip {trip_id}: passenger_id {row['passenger_id']} not in dim_passenger — skipped"
            )
            skipped += 1
            continue

        pickup_location_key = lookups["location"].get(row["pickup_location_id"])
        if pickup_location_key is None:
            logger.warning(
                f"trip {trip_id}: pickup_location_id {row['pickup_location_id']} not in dim_location — skipped"
            )
            skipped += 1
            continue

        dropoff_location_key = lookups["location"].get(row["dropoff_location_id"])
        if dropoff_location_key is None:
            logger.warning(
                f"trip {trip_id}: dropoff_location_id {row['dropoff_location_id']} not in dim_location — skipped"
            )
            skipped += 1
            continue

        # payment_method_id / promo_code_id are nullable in trips (e.g. no_show trips
        # have no payment method) and fact_trips allows NULL for both — only look
        # up and skip when the OLTP row actually has a value.
        payment_method_key = None
        if row["payment_method_id"] is not None:
            payment_method_key = lookups["payment_method"].get(row["payment_method_id"])
            if payment_method_key is None:
                logger.warning(
                    f"trip {trip_id}: payment_method_id {row['payment_method_id']} not in dim_payment_method — skipped"
                )
                skipped += 1
                continue

        promo_code_key = None
        if row["promo_code_id"] is not None:
            promo_code_key = lookups["promo_code"].get(row["promo_code_id"])
            if promo_code_key is None:
                logger.warning(
                    f"trip {trip_id}: promo_code_id {row['promo_code_id']} not in dim_promo_code — skipped"
                )
                skipped += 1
                continue

        base_fare = row["base_fare"] or 0
        tip_amount = row["tip_amount"] or 0
        surge_multiplier = row["surge_multiplier"] or 0
        discount_amount = row["discount_amount"] or 0
        fare_amount = round(
            base_fare * surge_multiplier + tip_amount - discount_amount, 2
        )

        duration_minutes = None
        if row["status"] == "completed" and row["completed_at"]:
            delta = row["completed_at"] - row["requested_at"]
            duration_minutes = round(delta.total_seconds() / 60, 1)

        fact_rows.append(
            (
                trip_id,
                date_key,
                driver_key,
                passenger_key,
                pickup_location_key,
                dropoff_location_key,
                payment_method_key,
                promo_code_key,
                base_fare,
                tip_amount,
                discount_amount,
                fare_amount,
                row["distance_km"],
                duration_minutes,
                row["driver_rating"],
                row["passenger_rating"],
                surge_multiplier,
                row["requested_at"],
            )
        )

    logger.info(f"Transformed {len(fact_rows)} rows, skipped {skipped}")
    return fact_rows


def main() -> None:
    """
    Extract all dimension data from the source DB and load them into the target DB.
    """
    source_db = Database().connect()
    target_db = Database(
        {
            "host": os.getenv("DEST_DB_HOST"),
            "port": os.getenv("DEST_DB_PORT"),
            "user": os.getenv("DEST_DB_USER"),
            "password": os.getenv("DEST_DB_PASSWORD"),
            "dbname": os.getenv("DEST_DB_NAME"),
        }
    ).connect()
    etl = ETL(source_db, target_db)

    try:
        lookups: dict[str, dict[int, Any]] = {}

        lookups["driver"] = etl.load_dim(
            queries.LOAD_DIM_DRIVER, etl.extract(queries.EXTRACT_DRIVERS), "dim_driver"
        )
        lookups["passenger"] = etl.load_dim(
            queries.LOAD_DIM_PASSENGER, etl.extract(queries.EXTRACT_PASSENGERS), "dim_passenger"
        )
        lookups["location"] = etl.load_dim(
            queries.LOAD_DIM_LOCATION, etl.extract(queries.EXTRACT_LOCATIONS), "dim_location"
        )
        lookups["payment_method"] = etl.load_dim(
            queries.LOAD_DIM_PAYMENT_METHOD,
            etl.extract(queries.EXTRACT_PAYMENT_METHODS),
            "dim_payment_method",
        )
        lookups["promo_code"] = etl.load_dim(
            queries.LOAD_DIM_PROMO_CODE, etl.extract(queries.EXTRACT_PROMO_CODES), "dim_promo_code"
        )

        logger.info("Loading static lookup tables into memory")
        lookups["date"] = {r[0]: True for r in etl.extract(queries.LOOKUP_DATE_KEYS)}

        oltp_rows = etl.extract(queries.EXTRACT_TRIPS, as_dict=True)
        fact_rows = transform(oltp_rows, lookups)
        etl.load_fact(queries.LOAD_FACT_TRIPS, fact_rows, "fact_trips")

    except Exception:
        target_db.rollback()
        logger.exception("ETL failed, rolled back")
        raise
    finally:
        source_db.close()
        target_db.close()


if __name__ == "__main__":
    main()
