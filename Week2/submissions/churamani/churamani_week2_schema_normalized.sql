-- churamani_week2_schema_normalized.sql
-- Week 2 Assignment — Normalized Schema Migration
-- Normalizes the flat `rides` table into a star schema 


-- ── Dimension tables ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS locations (
    location_id  SERIAL        PRIMARY KEY,
    city_name    VARCHAR(100)  NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS drivers (
    driver_id    SERIAL        PRIMARY KEY,
    name         VARCHAR(100)  NOT NULL
);

CREATE TABLE IF NOT EXISTS passengers (
    passenger_id  SERIAL        PRIMARY KEY,
    name          VARCHAR(100)  NOT NULL
);

CREATE TABLE IF NOT EXISTS payment_methods (
    payment_method_id  SERIAL       PRIMARY KEY,
    name               VARCHAR(30)  NOT NULL UNIQUE
);


-- ── Fact table ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS trips (
    trip_id              SERIAL        PRIMARY KEY,
    driver_id            INTEGER       NOT NULL REFERENCES drivers(driver_id),
    passenger_id         INTEGER       NOT NULL REFERENCES passengers(passenger_id),
    pickup_location_id   INTEGER       NOT NULL REFERENCES locations(location_id),
    dropoff_location_id  INTEGER       NOT NULL REFERENCES locations(location_id),
    fare_amount          NUMERIC(10,2) NOT NULL CHECK (fare_amount > 0),
    distance_km          NUMERIC(6,2)  NOT NULL,
    status               VARCHAR(50)   NOT NULL CHECK (status IN ('completed', 'cancelled', 'no_show')),
    requested_at         TIMESTAMP     NOT NULL,
    completed_at         TIMESTAMP,
    rating               NUMERIC(2,1)  CHECK (rating BETWEEN 1.0 AND 5.0),
    payment_method_id    INTEGER       REFERENCES payment_methods(payment_method_id)
);


-- ── Populate dimension tables ─────────────────────────────────────────────────

INSERT INTO drivers (name)
SELECT DISTINCT INITCAP(TRIM(REGEXP_REPLACE(driver_name, '\s+', ' ', 'g')))
FROM rides
ON CONFLICT DO NOTHING;

INSERT INTO passengers (name)
SELECT DISTINCT INITCAP(TRIM(REGEXP_REPLACE(passenger_name, '\s+', ' ', 'g')))
FROM rides
ON CONFLICT DO NOTHING;

INSERT INTO locations (city_name)
SELECT DISTINCT pickup_city  FROM rides
UNION
SELECT DISTINCT dropoff_city FROM rides
ON CONFLICT DO NOTHING;

INSERT INTO payment_methods (name)
SELECT DISTINCT payment_method
FROM rides
WHERE payment_method IS NOT NULL
ON CONFLICT DO NOTHING;


-- ── Populate fact table ───────────────────

INSERT INTO trips (
    driver_id,
    passenger_id,
    pickup_location_id,
    dropoff_location_id,
    fare_amount,
    distance_km,
    status,
    requested_at,
    completed_at,
    rating,
    payment_method_id
)
SELECT
    (SELECT driver_id    FROM drivers         WHERE name      = INITCAP(TRIM(REGEXP_REPLACE(r.driver_name,    '\s+', ' ', 'g')))),
    (SELECT passenger_id FROM passengers      WHERE name      = INITCAP(TRIM(REGEXP_REPLACE(r.passenger_name, '\s+', ' ', 'g')))),
    (SELECT location_id  FROM locations       WHERE city_name = r.pickup_city),
    (SELECT location_id  FROM locations       WHERE city_name = r.dropoff_city),
    r.fare_amount,
    r.ride_distance_km,
    r.ride_status,
    r.requested_at,
    r.completed_at,
    r.rating,
    (SELECT payment_method_id FROM payment_methods WHERE name = r.payment_method)
FROM rides r;
