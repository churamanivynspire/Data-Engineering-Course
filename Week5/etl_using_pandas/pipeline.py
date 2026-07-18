import argparse
import logging
import os
import time

import psycopg2
from dotenv import load_dotenv

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
from transform import (
    derive_driver_dim,
    derive_passenger_dim,
    derive_location_dim,
    transform_trips,
)
from load import (
    load_dim_driver,
    load_dim_passenger,
    load_dim_location,
    load_dim_payment_method,
    load_dim_promo_code,
    load_fact_trips,
)

from quality import run_quality_checks


def parse_args():
    parser = argparse.ArgumentParser(description="Rides ETL pipeline (pandas)")
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
        load_dim_driver(dst_conn, derive_driver_dim(extract_driver(src_conn)))
        load_dim_passenger(dst_conn, derive_passenger_dim(extract_passenger(src_conn)))
        load_dim_location(dst_conn, derive_location_dim(extract_location(src_conn)))
        load_dim_payment_method(dst_conn, extract_payment_method(src_conn))
        load_dim_promo_code(dst_conn, extract_promo_code(src_conn))
        logger.info(f"Dimention table load completed on {time.time() - time0:.2f}s")

        time0 = time.time()
        lookups = extract_lookup_dim(dst_conn)
        logger.info(f"Lookup table extraction completed on {time.time() - time0:.2f}s")

        time0 = time.time()
        if mode == 'INCREMENTAL':
            watermark = get_watermark(dst_conn)
            trips_df = extract_trips_incremental(src_conn, watermark)
        else:
            trips_df = extract_trips_full(src_conn)
        logger.info(f"Trip extraction  completed on {time.time() - time0:.2f}s")

        time0 = time.time()
        fact_df = transform_trips(trips_df, lookups)
        logger.info(f"Transformation completed on {time.time() - time0:.2f}s")

        time0 = time.time()
        run_quality_checks(fact_df)
        logger.info(f"Quality Check completed on {time.time() - time0:.2f}s")
        time0 = time.time()
        load_fact_trips(dst_conn, fact_df)
        logger.info(f"Trip table load completed on {time.time() - time0:.2f}s")
    finally:
        src_conn.close()
        dst_conn.close()


if __name__ == "__main__":
    main()
