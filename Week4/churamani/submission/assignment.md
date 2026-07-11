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

`dim_vehicle` and the two new `fact_trips` columns are in `warehouse.sql`.

- `vehicle_key` is **nullable**. In the OLTP schema `trips.vehicle_id` is a
  nullable FK, so a trip can have no vehicle (a cancelled or no-show trip
  never gets one). The warehouse keeps those rows, so the column allows NULL.
- `time_key` is **`NOT NULL`**. It comes from `requested_at`, which is always
  present, so a 15-minute bucket can always be computed.

## 2. `etl.py` — implement the remaining dimension + fact columns

- Add `extract_vehicle` / `load_dim_vehicle` following the pattern of the
  existing dimension loaders.
- Add `vehicle` and `time` to `load_lookup_dim`.
- In `transform`, resolve `vehicle_key` and `time_key` for each trip
  (remember `dim_time.time_key` is the requested time rounded **down** to
  the nearest 15-minute bucket, e.g. 14:37 → `1430`).
- Wire the new columns through `load_fact_trips`.

`vehicle` is one entry in `FK_SPECS`, marked optional, so a NULL `vehicle_id`
leaves `vehicle_key` as NULL. `time_key` is computed in `to_fact_row` as
`requested_at.hour * 100 + (requested_at.minute // 15) * 15`. Both columns go
through `queries.LOAD_FACT_TRIPS`, and `EXTRACT_VEHICLES` / `LOAD_DIM_VEHICLE`
fill `dim_vehicle`.

## 3. Revenue by city / month

Write a warehouse query that returns total revenue grouped by pickup city
and month.

Then write the equivalent query against the OLTP schema (`trips`,
`locations`, etc.) directly.

**Answer:** how many table joins does each version need? Which one needed
fewer, and why?

Warehouse (2 joins — `dim_location` + `dim_date`):

```sql
SELECT l.city_name, d.year, d.month, SUM(f.fare_amount) AS total_revenue
FROM fact_trips f
JOIN dim_location l ON f.pickup_location_key = l.location_key
JOIN dim_date d ON f.date_key = d.date_key
GROUP BY l.city_name, d.year, d.month
ORDER BY l.city_name, d.year, d.month;
```

OLTP (1 join — `locations` only):

```sql
SELECT l.city_name, DATE_TRUNC('month', t.requested_at) AS month,
       SUM((t.base_fare * t.surge_multiplier) + t.tip_amount - t.discount_amount) AS total_revenue
FROM trips t
JOIN locations l ON t.pickup_location_id = l.location_id
GROUP BY l.city_name, DATE_TRUNC('month', t.requested_at)
ORDER BY l.city_name, month;
```

**Answer:** OLTP needs fewer joins (1 vs 2). The warehouse keeps date
attributes in `dim_date`, so grouping by month costs an extra join. OLTP
reads the month straight off the `requested_at` timestamp on `trips`, and
computes the fare inline because it has no `fare_amount` column. The warehouse
gives up that one join in exchange for a ready-made `fare_amount` and clean
`year`/`month` columns, and wins once you need richer calendar attributes
(quarter, `is_weekend`, `day_name`) that OLTP would have to compute every
query.

## 4. Payment method revenue

- Write a warehouse query for total revenue per payment method.
- Extend it (or write a second query) for **average fare per trip, per
  payment method, per month**.

Total revenue per payment method:

```sql
SELECT pm.name AS payment_method, SUM(f.fare_amount) AS total_revenue
FROM fact_trips f
JOIN dim_payment_method pm ON f.payment_method_key = pm.payment_method_key
GROUP BY pm.name
ORDER BY total_revenue DESC;
```

Average fare per trip, per payment method, per month:

```sql
SELECT pm.name AS payment_method, d.year, d.month,
       ROUND(AVG(f.fare_amount), 2) AS avg_fare_per_trip
FROM fact_trips f
JOIN dim_payment_method pm ON f.payment_method_key = pm.payment_method_key
JOIN dim_date d ON f.date_key = d.date_key
GROUP BY pm.name, d.year, d.month
ORDER BY pm.name, d.year, d.month;
```

## 5. Busiest hour of day

Write a warehouse query that returns trip count per hour of day (0–23),
along with each hour's percentage of all trips — computed with a **window
function** (not a second query for the grand total).

```sql
SELECT tm.hour,
       COUNT(*) AS trip_count,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_all_trips
FROM fact_trips f
JOIN dim_time tm ON f.time_key = tm.time_key
GROUP BY tm.hour
ORDER BY trip_count DESC;
```

`SUM(COUNT(*)) OVER ()` sums the per-hour counts across all grouped rows,
giving the grand total in the same pass. So the percentage needs no second
query or subquery for the denominator.

## 7. Stretch: incremental load (watermark pattern)

Modify `etl.py` so the fact load only extracts trips newer than the
`MAX(requested_at)` already present in `fact_trips`. Where should that
watermark be read from, and what happens the very first time the ETL runs
against an empty warehouse?

`main()` reads the watermark with `queries.MAX_FACT_WATERMARK`
(`SELECT MAX(requested_at) FROM fact_trips`) and passes it into the trips
extract. `queries.EXTRACT_TRIPS` filters with
`WHERE %(watermark)s IS NULL OR t.requested_at > %(watermark)s`.

**Answer:** the watermark comes from the **target** `fact_trips` — the
warehouse already knows how current it is, so the source is never consulted.
On the first run the warehouse is empty, so `MAX(requested_at)` returns
`NULL`, and the `%(watermark)s IS NULL OR ...` guard makes it a full load of
every trip. Later runs pull only trips newer than the newest one loaded.
`ON CONFLICT (source_trip_id) DO NOTHING` stays as a safety net against
boundary duplicates.
