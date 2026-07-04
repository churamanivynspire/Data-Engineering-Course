-- week3_reliability.sql
-- Week 3 Assignment
-- Submit TWO files:
--   1. week3_reliability.sql  (this file — SQL tasks)
--   2. transactional_loader.py (Python task — Q5)
--
-- All SQL runs against the normalized schema from Week 2
-- (drivers, riders, locations, trips)

-- ─────────────────────────────────────────────────────────────────
-- Q1: Add indexes to the trips table
--
-- Before adding ANY index, run EXPLAIN ANALYZE on each query below
-- and record the execution time in a comment.
-- Then add your indexes and run EXPLAIN ANALYZE again.
-- The comparison IS the answer — not just the CREATE INDEX statement.
-- ─────────────────────────────────────────────────────────────────

-- Baseline queries — run EXPLAIN ANALYZE on each BEFORE indexing:

-- Query A: filter by driver
EXPLAIN ANALYZE
SELECT * FROM trips WHERE driver_id = 3;

-- Query B: filter by status
EXPLAIN ANALYZE
SELECT * FROM trips WHERE status = 'cancelled';

-- Query C: filter by driver AND status (common in the pipeline)
EXPLAIN ANALYZE
SELECT * FROM trips
WHERE driver_id = 3 AND status = 'completed';

-- YOUR INDEXES HERE:
-- (add indexes, then re-run the EXPLAIN ANALYZE queries above)


-- Record results in comments, e.g.:
-- Query A before: Seq Scan, execution time = X ms
-- Query A after:  Index Scan using ..., execution time = Y ms


-- ─────────────────────────────────────────────────────────────────
-- Q2: Create completed_trips_view
--
-- Must return only completed trips with ALL of these columns:
--   trip_id, driver_name, rider_name,
--   pickup_city, dropoff_city,
--   fare_amount, distance_km, rating,
--   payment_method, requested_at, completed_at
--
-- No IDs in the output — use JOINs to resolve all foreign keys.
-- ─────────────────────────────────────────────────────────────────

-- YOUR VIEW HERE:


-- Verify:
-- SELECT * FROM completed_trips_view LIMIT 5;
-- SELECT COUNT(*) FROM completed_trips_view;
-- Expected count: ~2862 (all completed trips)


-- ─────────────────────────────────────────────────────────────────
-- Q3: Create driver_summary view
--
-- Must show one row per driver with:
--   driver_name
--   total_trips          (all statuses)
--   completed_trips
--   cancelled_trips
--   cancellation_rate    (cancelled / total * 100, rounded to 1dp)
--   avg_fare             (completed trips only, rounded to 2dp)
--   avg_rating           (completed trips only, rounded to 1dp)
--
-- Challenge: use COUNT(*) FILTER (WHERE ...) instead of CASE WHEN
-- ─────────────────────────────────────────────────────────────────

-- YOUR VIEW HERE:


-- Verify:
-- SELECT * FROM driver_summary ORDER BY completed_trips DESC;


-- ─────────────────────────────────────────────────────────────────
-- Q4: Transaction with intentional failure
--
-- Write a transaction that:
--   1. Inserts a new driver named 'Test Driver'
--   2. Inserts 3 valid trips for that driver
--   3. Inserts a 4th trip with rating = 99 (violates CHECK constraint)
--
-- The entire transaction should roll back.
-- Verify with: SELECT * FROM drivers WHERE name = 'Test Driver';
-- Expected: 0 rows (atomicity — nothing committed)
-- ─────────────────────────────────────────────────────────────────

-- YOUR TRANSACTION HERE:


-- Verification query:
SELECT
    'drivers' AS tbl,
    COUNT(*) AS test_driver_rows
FROM drivers
WHERE name = 'Test Driver'
UNION ALL
SELECT 'trips', COUNT(*)
FROM trips t
JOIN drivers d ON t.driver_id = d.driver_id
WHERE d.name = 'Test Driver';
-- Expected: 0 / 0


-- ─────────────────────────────────────────────────────────────────
-- Q6 (STRETCH): Window function — running total fare per driver
--
-- For each completed trip, show:
--   trip_id, driver_name, requested_at, fare_amount,
--   running_total_fare (driver's cumulative fare up to this trip)
--
-- Use: SUM(fare_amount) OVER (PARTITION BY driver_id ORDER BY requested_at)
-- Order the final output by driver_name, requested_at
-- ─────────────────────────────────────────────────────────────────

-- YOUR QUERY HERE: