# Week 4 Assignment — Ride-Sharing Warehouse

Complete the tasks below directly in `warehouse.sql` and `etl.py`. Add any
analysis queries and your written answers to this file under the matching
section.

## 1. `warehouse.sql` — add the vehicle dimension

- Create a `dim_vehicle` table (surrogate key `vehicle_key`, natural key
  `vehicle_id`, plus the descriptive vehicle attributes from the OLTP
  `vehicles` table: plate number, make, model, year, color, category,
  is_active).
- Add `vehicle_key` and `time_key` columns to `fact_trips`, referencing
  `dim_vehicle(vehicle_key)` and `dim_time(time_key)` respectively.
  - Think about whether each new key should be `NOT NULL` — is `vehicle_id`
    always present on a trip in the OLTP schema? Is a time always known?

## 2. `etl.py` — implement the remaining dimension + fact columns

- Add `extract_vehicle` / `load_dim_vehicle` following the pattern of the
  existing dimension loaders.
- Add `vehicle` and `time` to `load_lookup_dim`.
- In `transform`, resolve `vehicle_key` and `time_key` for each trip
  (remember `dim_time.time_key` is the requested time rounded **down** to
  the nearest 15-minute bucket, e.g. 14:37 → `1430`).
- Wire the new columns through `load_fact_trips`.

## 3. Revenue by city / month

Write a warehouse query that returns total revenue grouped by pickup city
and month.

Then write the equivalent query against the OLTP schema (`trips`,
`locations`, etc.) directly.

**Answer:** how many table joins does each version need? Which one needed
fewer, and why?

## 4. Payment method revenue

- Write a warehouse query for total revenue per payment method.
- Extend it (or write a second query) for **average fare per trip, per
  payment method, per month**.

## 5. Busiest hour of day

Write a warehouse query that returns trip count per hour of day (0–23),
along with each hour's percentage of all trips — computed with a **window
function** (not a second query for the grand total).

## 7. Stretch: incremental load (watermark pattern)

Modify `etl.py` so the fact load only extracts trips newer than the
`MAX(requested_at)` already present in `fact_trips`. Where should that
watermark be read from, and what happens the very first time the ETL runs
against an empty warehouse?
