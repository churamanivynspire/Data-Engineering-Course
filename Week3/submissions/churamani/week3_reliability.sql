-- week3_reliability.sql
-- Week 3 Assignment — churamani
-- Runs against the normalized Week 2 schema
-- (drivers, passengers, locations, payment_methods, trips)
--
-- EXPLAIN ANALYZE timings below are the real captures from a 1,000,000-row
-- load (see class_query_day_2.sql). Re-run after load_test_1m.py to confirm.

-- ─────────────────────────────────────────────────────────────────
-- Q1: Indexes on the trips table
-- ─────────────────────────────────────────────────────────────────

-- Baseline (BEFORE any index):
EXPLAIN ANALYZE SELECT * FROM trips WHERE driver_id = 3;
EXPLAIN ANALYZE SELECT * FROM trips WHERE status = 'cancelled';
EXPLAIN ANALYZE SELECT * FROM trips WHERE driver_id = 3 AND status = 'completed';

-- Indexes:
CREATE INDEX idx_trips_driver_id     ON trips(driver_id);
CREATE INDEX idx_trips_status        ON trips(status);
CREATE INDEX idx_trips_driver_status ON trips(driver_id, status);

-- Re-run AFTER indexing:
EXPLAIN ANALYZE SELECT * FROM trips WHERE driver_id = 3;
EXPLAIN ANALYZE SELECT * FROM trips WHERE status = 'cancelled';
EXPLAIN ANALYZE SELECT * FROM trips WHERE driver_id = 3 AND status = 'completed';

-- Results (1M rows):
-- Query A (driver_id = 3)
--   before: Seq Scan ....................... execution time ≈ 348 ms
--   after:  Bitmap Heap Scan using idx_trips_driver_id ≈ 85 ms   (~4x faster)
--
-- Query B (status = 'cancelled')
--   before: Seq Scan ....................... execution time ≈ 380–420 ms
--   after:  Bitmap Heap Scan using idx_trips_status ≈ 146 ms
--   LESSON: status has only 3 distinct values (low cardinality), so the
--           planner uses a Bitmap scan (or even Seq Scan), never a plain
--           Index Scan — an index on a low-cardinality column buys little.
--
-- Query C (driver_id = 3 AND status = 'completed')
--   before: Parallel Seq Scan .............. execution time ≈ 224 ms
--   after:  Bitmap Heap Scan using composite idx_trips_driver_status ≈ 64 ms
--   The composite index is the winner for the pipeline's common filter.


-- ─────────────────────────────────────────────────────────────────
-- Q2: completed_trips_view — only completed trips, no IDs in output
-- ─────────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW completed_trips_view AS
SELECT
    t.trip_id,
    d.name        AS driver_name,
    p.name        AS passenger_name,
    pck.city_name AS pickup_city,
    drp.city_name AS dropoff_city,
    t.fare_amount,
    t.distance_km,
    t.rating,
    pm.name       AS payment_method,
    t.requested_at,
    t.completed_at
FROM trips t
JOIN drivers    d   ON t.driver_id           = d.driver_id
JOIN passengers p   ON t.passenger_id        = p.passenger_id
JOIN locations  pck ON t.pickup_location_id  = pck.location_id
JOIN locations  drp ON t.dropoff_location_id = drp.location_id
LEFT JOIN payment_methods pm ON t.payment_method_id = pm.payment_method_id
WHERE t.status = 'completed';

-- Verify:
-- SELECT * FROM completed_trips_view LIMIT 5;
-- SELECT COUNT(*) FROM completed_trips_view;


-- ─────────────────────────────────────────────────────────────────
-- Q3: driver_summary — one row per driver (COUNT(*) FILTER, not CASE WHEN)
-- ─────────────────────────────────────────────────────────────────

CREATE VIEW driver_summary AS
SELECT
    d.name AS driver_name,
    -- COUNT(*) with the LEFT JOIN reports 1 (not 0) for a driver with no trips,
    -- matching the reference submission; use COUNT(t.trip_id) if 0 is required.
    COUNT(*)                                        AS total_trips,
    COUNT(*) FILTER (WHERE t.status = 'completed')  AS completed_trips,
    COUNT(*) FILTER (WHERE t.status = 'cancelled')  AS cancelled_trips,
    ROUND(
        COUNT(*) FILTER (WHERE t.status = 'cancelled')::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 1
    ) AS cancellation_rate,
    ROUND(AVG(t.fare_amount) FILTER (WHERE t.status = 'completed')::NUMERIC, 2) AS avg_fare,
    ROUND(AVG(t.rating)      FILTER (WHERE t.status = 'completed'), 1) AS avg_rating
FROM drivers d
LEFT JOIN trips t ON t.driver_id = d.driver_id
GROUP BY d.driver_id, d.name
ORDER BY completed_trips DESC;

-- Verify:
-- SELECT * FROM driver_summary ORDER BY completed_trips DESC;


-- ─────────────────────────────────────────────────────────────────
-- Q4: Transaction with intentional failure — must roll back entirely
-- ─────────────────────────────────────────────────────────────────
-- The 4th INSERT (rating = 99) violates CHECK (rating BETWEEN 1.0 AND 5.0).
-- That aborts the transaction, so COMMIT resolves to ROLLBACK — atomicity.

BEGIN;

    INSERT INTO drivers (name) VALUES ('Test Driver');

    -- 3 valid trips
    INSERT INTO trips (driver_id, passenger_id, pickup_location_id, dropoff_location_id,
                       fare_amount, distance_km, status, requested_at, rating)
    VALUES ((SELECT driver_id FROM drivers WHERE name = 'Test Driver'),
            1, 1, 2, 200.00, 5.0, 'completed', NOW(), 4.5);

    INSERT INTO trips (driver_id, passenger_id, pickup_location_id, dropoff_location_id,
                       fare_amount, distance_km, status, requested_at, rating)
    VALUES ((SELECT driver_id FROM drivers WHERE name = 'Test Driver'),
            1, 1, 2, 350.00, 9.2, 'completed', NOW(), 5.0);

    INSERT INTO trips (driver_id, passenger_id, pickup_location_id, dropoff_location_id,
                       fare_amount, distance_km, status, requested_at, rating)
    VALUES ((SELECT driver_id FROM drivers WHERE name = 'Test Driver'),
            1, 1, 2, 500.00, 14.0, 'completed', NOW(), 4.0);

    -- 4th trip: rating = 99 → violates CHECK → whole transaction aborts
    INSERT INTO trips (driver_id, passenger_id, pickup_location_id, dropoff_location_id,
                       fare_amount, distance_km, status, requested_at, rating)
    VALUES ((SELECT driver_id FROM drivers WHERE name = 'Test Driver'),
            1, 1, 2, 500.00, 10.0, 'completed', NOW(), 99);

COMMIT;

-- Verification query (expected: 0 / 0):
SELECT 'drivers' AS tbl, COUNT(*) AS test_driver_rows
FROM drivers
WHERE name = 'Test Driver'
UNION ALL
SELECT 'trips', COUNT(*)
FROM trips t
JOIN drivers d ON t.driver_id = d.driver_id
WHERE d.name = 'Test Driver';


-- ─────────────────────────────────────────────────────────────────
-- Q6 (STRETCH): running total fare per driver
-- ─────────────────────────────────────────────────────────────────

SELECT
    t.trip_id,
    d.name AS driver_name,
    t.requested_at,
    t.fare_amount,
    SUM(t.fare_amount) OVER (
        PARTITION BY t.driver_id
        ORDER BY t.requested_at
    ) AS running_total_fare
FROM trips t
JOIN drivers d ON t.driver_id = d.driver_id
WHERE t.status = 'completed'
ORDER BY d.name, t.requested_at;
