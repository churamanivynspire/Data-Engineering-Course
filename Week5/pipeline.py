import psycopg2
import logging
import os
from dotenv import load_dotenv
from datetime import datetime

import time

import argparse

from extract import (
    extract_driver,
    extract_passenger,
    extract_location,
    extract_payment_method,
    extract_promo_code,
    extract_trips_incremental,
    extract_trips_full,
    extract_lookup_dim,
    get_watermark
)
from load import (
    load_dim_driver,
    load_dim_passenger,
    load_dim_location,
    load_dim_payment_method,
    load_dim_promo_code,
    load_fact_trips,
)
from transform import transform

from quality  import run_quality_checks

def parse_args():
    parser = argparse.ArgumentParser(description="Rides ETL pipeline")
    parser.add_argument(
        "--full-reload",
        action="store_true",
        help="Truncate warehouse and reload all data (default: incremental)"
    )
    return parser.parse_args()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s [%(filename)s:%(lineno)d] %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

SOURCE_DB_CONFIG = dict(
    host=    os.getenv("SRC_DB_HOST"),
    port =   os.getenv("SRC_DB_PORT"),
    dbname = os.getenv("SRC_DB_NAME"),
    user=    os.getenv("SRC_DB_USER"),
    password=os.getenv("SRC_DB_PASSWORD")
)
DEST_DB_CONFIG = dict(
    host=    os.getenv("DEST_DB_HOST"),
    port =   os.getenv("DEST_DB_PORT"),
    dbname = os.getenv("DEST_DB_NAME"),
    user=    os.getenv("DEST_DB_USER"),
    password=os.getenv("DEST_DB_PASSWORD")
)



def main():
    args = parse_args()
    mode = 'FULL' if args.full_reload else 'INCREMENTAL'
    """
    Extract all dimension data from the source DB and load them into the target DB.
    """
    src_conn = psycopg2.connect(**SOURCE_DB_CONFIG)
    dst_conn = psycopg2.connect(**DEST_DB_CONFIG)
    try:
        time0 = time.time()
        driver_data = extract_driver(src_conn)
        load_dim_driver(dst_conn, driver_data)

        passenger_data = extract_passenger(src_conn)
        load_dim_passenger(dst_conn, passenger_data)

        location_data = extract_location(src_conn)
        load_dim_location(dst_conn, location_data)

        payment_method_data = extract_payment_method(src_conn)
        load_dim_payment_method(dst_conn, payment_method_data)

        promo_code_data = extract_promo_code(src_conn)
        load_dim_promo_code(dst_conn, promo_code_data)
        logger.info(f"Dimention table load completed on {time.time() - time0:.2f}s")

        time0 = time.time()
        lookups = extract_lookup_dim(dst_conn)
        logger.info(f"Lookup table extraction completed on {time.time() - time0:.2f}s")

        time0 = time.time()
        if mode == 'INCREMENTAL':
            watermark = get_watermark(dst_conn)
            rows = extract_trips_incremental(src_conn,{"watermark":watermark})
        else:
            rows = extract_trips_full(src_conn)
        logger.info(f"Trip extraction  completed on {time.time() - time0:.2f}s")

        time0 = time.time()
        fact_rows = transform(rows, lookups)
        logger.info(f"Transformation completed on {time.time() - time0:.2f}s")

        time0 = time.time()
        run_quality_checks(fact_rows)
        logger.info(f"Quality Check completed on {time.time() - time0:.2f}s")
        time0 = time.time()
        load_fact_trips(dst_conn, fact_rows)
        logger.info(f"Trip table load completed on {time.time() - time0:.2f}s")
    finally:
        src_conn.close()
        dst_conn.close()


if __name__ == "__main__":
    main()

