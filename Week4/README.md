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

**3. Configure the database connection**

Create a `.env` file in this folder:

```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ride_prod
DB_USER=postgres
DB_PASSWORD=<your_password>
```

**4. Load the sample data**

```bash
python sample_data_loader.py
```

This generates and inserts sample rows (25 locations, 25 drivers, 30 vehicles, 45 passengers, 10,000 trips, etc.) into the tables created in step 1. You should see progress per table and a final row-count summary when it finishes.

**5. Query the data**

In DBeaver, open a SQL Editor on the `ride_prod` connection and run:

```sql
SELECT * FROM trips LIMIT 10;
```
