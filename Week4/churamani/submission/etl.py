from typing import Any, Sequence

from psycopg2.extras import RealDictRow

from db import Database
from logging_config import get_logger

logger = get_logger(__name__)


class ETL:
    def __init__(self, source_db: Database, target_db: Database):
        self.source_db = source_db
        self.target_db = target_db

    def extract(self, sql: str, params: Any = None, as_dict: bool = False) -> list:
        rows = (
            self.source_db.fetch_dicts(sql, params)
            if as_dict
            else self.source_db.fetch_all(sql, params)
        )
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


FK_SPECS = [
    ("driver",         "driver_id",            "driver_key",           True),
    ("passenger",      "passenger_id",         "passenger_key",        True),
    ("location",       "pickup_location_id",   "pickup_location_key",  True),
    ("location",       "dropoff_location_id",  "dropoff_location_key", True),
    ("payment_method", "payment_method_id",    "payment_method_key",   False),
    ("promo_code",     "promo_code_id",        "promo_code_key",       False),
    ("vehicle",        "vehicle_id",           "vehicle_key",          False),
]


def to_fact_row(
    row: RealDictRow,
    date_key: int,
    keys: dict[str, Any],
) -> tuple:
    base_fare = row["base_fare"] or 0
    tip_amount = row["tip_amount"] or 0
    surge_multiplier = row["surge_multiplier"] or 0
    discount_amount = row["discount_amount"] or 0
    fare_amount = round(
        base_fare * surge_multiplier + tip_amount - discount_amount, 2
    )

    requested_at = row["requested_at"]
    time_key = requested_at.hour * 100 + (requested_at.minute // 15) * 15

    duration_minutes = None
    if row["status"] == "completed" and row["completed_at"]:
        delta = row["completed_at"] - requested_at
        duration_minutes = round(delta.total_seconds() / 60, 1)

    return (
        row["trip_id"],
        date_key,
        keys["driver_key"],
        keys["passenger_key"],
        keys["pickup_location_key"],
        keys["dropoff_location_key"],
        keys["payment_method_key"],
        keys["promo_code_key"],
        keys["vehicle_key"],
        time_key,
        base_fare,
        tip_amount,
        discount_amount,
        fare_amount,
        row["distance_km"],
        duration_minutes,
        row["driver_rating"],
        row["passenger_rating"],
        surge_multiplier,
        requested_at,
    )


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

        keys: dict[str, Any] = {}
        skip = False
        for lookup_name, id_field, key_name, required in FK_SPECS:
            id_value = row[id_field]
            if id_value is None and not required:
                keys[key_name] = None
                continue
            key = lookups[lookup_name].get(id_value)
            if key is None:
                logger.warning(
                    f"trip {trip_id}: {id_field} {id_value} not in dim_{lookup_name} — skipped"
                )
                skipped += 1
                skip = True
                break
            keys[key_name] = key
        if skip:
            continue

        fact_rows.append(to_fact_row(row, date_key, keys))

    logger.info(f"Transformed {len(fact_rows)} rows, skipped {skipped}")
    return fact_rows
