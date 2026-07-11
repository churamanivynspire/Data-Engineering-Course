import os

from dotenv import load_dotenv

import queries
from db import Database
from etl import ETL, transform
from logging_config import get_logger

logger = get_logger(__name__)

load_dotenv()


def main() -> None:
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
        lookups: dict[str, dict] = {}

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
        lookups["vehicle"] = etl.load_dim(
            queries.LOAD_DIM_VEHICLE, etl.extract(queries.EXTRACT_VEHICLES), "dim_vehicle"
        )

        logger.info("Loading static lookup tables into memory")
        lookups["date"] = {r[0]: True for r in etl.extract(queries.LOOKUP_DATE_KEYS)}

        watermark = etl.target_db.fetch_all(queries.MAX_FACT_WATERMARK)[0][0]
        oltp_rows = etl.extract(
            queries.EXTRACT_TRIPS, params={"watermark": watermark}, as_dict=True
        )
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
