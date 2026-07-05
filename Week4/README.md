# Week 4 — Normalized Ride-Sharing Schema

## Setup

**1. Create the database and load the schema (using DBeaver)**

`ride_prod_sample.sql` creates the `ride_prod` database and the normalized schema (locations, drivers, driver_licenses, vehicles, vehicle_assignments, passengers, payment_methods, promo_codes, trips, trip_cancellations).

1. Open DBeaver and connect to your local PostgreSQL server (as the `postgres` user).
2. Open a new **SQL Editor** on that connection.
3. Open `ride_prod_sample.sql` (File → Open File, or paste its contents into the editor).
4. Execute the whole script (**Execute SQL Script** — the button with the script icon, or `Alt+X`) so the `CREATE DATABASE ride_prod;` statement and the schema both run(if you run into any issue first run `CREATE DATABASE ride_prod;` then change the db selection from dbeaver and run the rest of the query)
5. Reconnect / create a new connection in DBeaver pointed at the `ride_prod` database so you can browse the tables it created.

**2. Create a virtual environment and install dependencies**

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**3. Create the warehouse database and load the schema (using DBeaver)**

`warehouse.sql` creates the star-schema tables for the `ride_dw` warehouse (`dim_date`, `dim_driver`, `dim_passenger`, `dim_location`, `dim_payment_method`, `dim_promo_code`, `fact_trips`) and pre-populates `dim_date`.

1. In DBeaver, create the `ride_dw` database (e.g. `CREATE DATABASE ride_dw;` run against your Postgres connection).
2. Open a new SQL Editor connected to the `ride_dw` database.
3. Open `warehouse.sql` and execute the whole script (**Execute SQL Script** / `Alt+X`).

**4. Configure the database connections**

Create a `.env` file in this folder with both the source (`ride_prod`) and destination (`ride_dw`) connection settings:

```bash
SRC_DB_HOST=localhost
SRC_DB_PORT=5432
SRC_DB_NAME=ride_prod
SRC_DB_USER=postgres
SRC_DB_PASSWORD=<your_password>

DEST_DB_HOST=localhost
DEST_DB_PORT=5432
DEST_DB_NAME=ride_dw
DEST_DB_USER=postgres
DEST_DB_PASSWORD=<your_password>
```

**5. Load the sample data**

```bash
python sample_data_loader.py
```

This generates and inserts sample rows (25 locations, 25 drivers, 30 vehicles, 45 passengers, 10,000 trips, etc.) into the `ride_prod` tables created in step 1. You should see progress per table and a final row-count summary when it finishes.

**6. Run the ETL into the warehouse**

```bash
python etl.py
```

This reads from `ride_prod` and loads `ride_dw` — see [ELT Flow](#elt-flow) below for what it does step by step.

**7. Query the data**

In DBeaver, open a SQL Editor on the `ride_prod` connection and run:

```sql
SELECT * FROM trips LIMIT 10;
```

Or on the `ride_dw` connection:

```sql
SELECT * FROM fact_trips LIMIT 10;
```

## ELT Flow

`etl.py` extracts from the normalized `ride_prod` OLTP schema, loads dimensions and lookups into the `ride_dw` star schema, transforms trips in Python, then loads the fact table.

```
ride_prod (OLTP)                         etl.py                          ride_dw (warehouse)
─────────────────                ───────────────────────                ───────────────────
drivers          ──extract_driver───▶ load_dim_driver         ──▶ dim_driver
passengers       ──extract_passenger▶ load_dim_passenger       ──▶ dim_passenger
locations        ──extract_location▶ load_dim_location        ──▶ dim_location
payment_methods  ──extract_payment_method▶ load_dim_payment_method ──▶ dim_payment_method
promo_codes      ──extract_promo_code▶ load_dim_promo_code     ──▶ dim_promo_code
                                                                    dim_date (pre-populated by warehouse.sql)

                                       load_lookup_dim
                                       (reads driver/passenger/location/payment_method/
                                        promo_code/date keys back from ride_dw into
                                        in-memory dicts, natural key → surrogate key)
                                              │
trips + trip_cancellations ──extract_trips──▶ │
                                              ▼
                                          transform
                                       (looks up each dimension's surrogate key,
                                        skips + logs the trip if a key is missing,
                                        computes fare_amount / duration_minutes)
                                              │
                                              ▼
                                       load_fact_trips  ──▶ fact_trips
```

1. **Load dimensions** — `extract_*` pulls each reference table from `ride_prod` (deriving a few extra columns along the way: `tenure_bucket` for drivers, `cohort_month` for passengers, `region` for locations); `load_dim_*` upserts the rows into the matching `dim_*` table in `ride_dw` (`ON CONFLICT DO NOTHING`, so re-running is safe).
2. **Build lookups** — `load_lookup_dim` reads each `dim_*` table's natural key → surrogate key mapping back out of `ride_dw` into an in-memory dict (`lookups["driver"]`, `lookups["location"]`, etc.), including `dim_date`'s `date_key` range.
3. **Extract trips** — `extract_trips` pulls every row from `trips` (left-joined to `trip_cancellations`) ordered by `requested_at`.
4. **Transform** — for each trip, `transform` resolves every dimension's surrogate key via the lookups built in step 2. `payment_method_id`/`promo_code_id` are optional — a trip is only skipped for those if it has a value that isn't found. Any other missing key skips the trip (logged as a warning). It also computes `fare_amount` (`base_fare × surge + tip − discount`) and `duration_minutes` (for completed trips).
5. **Load facts** — `load_fact_trips` bulk-inserts the transformed rows into `fact_trips`, keyed on `source_trip_id` (`ON CONFLICT DO NOTHING`, so re-running the ETL won't duplicate facts).
