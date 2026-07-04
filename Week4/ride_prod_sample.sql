CREATE DATABASE ride_prod;

-- =================================================================
-- NORMALIZED RIDE-SHARING SCHEMA
-- Normal Forms: 1NF, 2NF, 3NF compliant
-- =================================================================


-- -----------------------------------------------------------------
-- DROP ORDER (respects FK dependencies)
-- -----------------------------------------------------------------
DROP VIEW  IF EXISTS v_promo_usage;
DROP VIEW  IF EXISTS v_trips;

DROP TABLE IF EXISTS trip_cancellations;
DROP TABLE IF EXISTS trips;
DROP TABLE IF EXISTS vehicle_assignments;
DROP TABLE IF EXISTS vehicles;
DROP TABLE IF EXISTS driver_licenses;
DROP TABLE IF EXISTS drivers;
DROP TABLE IF EXISTS passengers;
DROP TABLE IF EXISTS locations;
DROP TABLE IF EXISTS payment_methods;
DROP TABLE IF EXISTS promo_codes;


-- =================================================================
-- DIMENSION TABLES
-- =================================================================


-- -----------------------------------------------------------------
-- locations
-- Removed: timezone (transitive dependency on lat/lng)
-- timezone is best derived in the application layer via a geo library
-- -----------------------------------------------------------------
CREATE TABLE locations (
    location_id     SERIAL          PRIMARY KEY,
    city_name       VARCHAR(100)    NOT NULL,
    state_province  VARCHAR(100),
    country         VARCHAR(100),
    latitude        NUMERIC(9,6),
    longitude       NUMERIC(9,6),
    UNIQUE (city_name, state_province, country)
);


-- -----------------------------------------------------------------
-- drivers
-- Removed: license_number, license_expiry_date (moved to driver_licenses)
-- -----------------------------------------------------------------
CREATE TABLE drivers (
    driver_id       SERIAL          PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL,
    email           VARCHAR(150)    UNIQUE,
    phone_number    VARCHAR(20)     UNIQUE,
    status          VARCHAR(20)     NOT NULL DEFAULT 'active'
                                    CHECK (status IN ('active', 'inactive', 'suspended')),
    joined_at       TIMESTAMP       NOT NULL DEFAULT NOW()
);


-- -----------------------------------------------------------------
-- driver_licenses
-- Separated from drivers to:
--   1. Eliminate transitive dependency (driver_id → license_number → expiry_date)
--   2. Support license renewal history over time
-- -----------------------------------------------------------------
CREATE TABLE driver_licenses (
    license_id      SERIAL          PRIMARY KEY,
    driver_id       INTEGER         NOT NULL REFERENCES drivers(driver_id) ON DELETE CASCADE,
    license_number  VARCHAR(50)     NOT NULL UNIQUE,
    issued_date     DATE,
    expiry_date     DATE            NOT NULL,
    is_current      BOOLEAN         NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_license_dates CHECK (
        issued_date IS NULL OR issued_date < expiry_date
    )
);

-- Only one active license per driver at a time
CREATE UNIQUE INDEX idx_driver_one_current_license
    ON driver_licenses(driver_id)
    WHERE is_current = TRUE;


-- -----------------------------------------------------------------
-- passengers
-- -----------------------------------------------------------------
CREATE TABLE passengers (
    passenger_id    SERIAL          PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL,
    email           VARCHAR(150)    UNIQUE,
    phone_number    VARCHAR(20)     UNIQUE,
    status          VARCHAR(20)     NOT NULL DEFAULT 'active'
                                    CHECK (status IN ('active', 'inactive', 'banned')),
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW()
);


-- -----------------------------------------------------------------
-- payment_methods
-- -----------------------------------------------------------------
CREATE TABLE payment_methods (
    payment_method_id   SERIAL          PRIMARY KEY,
    name                VARCHAR(30)     NOT NULL UNIQUE,
    type                VARCHAR(20)     CHECK (type IN ('card', 'cash', 'wallet', 'voucher')),
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE
);


-- -----------------------------------------------------------------
-- vehicles
-- Removed: driver_id (moved to vehicle_assignments)
-- A vehicle can be reassigned to different drivers over time;
-- a hard FK would cause update anomalies in a fleet model.
-- -----------------------------------------------------------------
CREATE TABLE vehicles (
    vehicle_id      SERIAL          PRIMARY KEY,
    plate_number    VARCHAR(20)     NOT NULL UNIQUE,
    make            VARCHAR(50),
    model           VARCHAR(50),
    year            SMALLINT        CHECK (year > 1980),
    color           VARCHAR(30),
    category        VARCHAR(20)     CHECK (category IN ('economy', 'comfort', 'xl', 'luxury')),
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE
);


-- -----------------------------------------------------------------
-- vehicle_assignments
-- Junction table tracking which driver operated which vehicle,
-- including validity periods for historical accuracy.
-- -----------------------------------------------------------------
CREATE TABLE vehicle_assignments (
    assignment_id   SERIAL          PRIMARY KEY,
    vehicle_id      INTEGER         NOT NULL REFERENCES vehicles(vehicle_id)  ON DELETE CASCADE,
    driver_id       INTEGER         NOT NULL REFERENCES drivers(driver_id)    ON DELETE CASCADE,
    assigned_at     TIMESTAMP       NOT NULL DEFAULT NOW(),
    unassigned_at   TIMESTAMP,                            -- NULL = currently active
    CONSTRAINT chk_assignment_dates CHECK (
        unassigned_at IS NULL OR unassigned_at > assigned_at
    )
);

-- Enforce only one active (unassigned_at IS NULL) assignment per vehicle
CREATE UNIQUE INDEX idx_one_active_vehicle_assignment
    ON vehicle_assignments(vehicle_id)
    WHERE unassigned_at IS NULL;


-- -----------------------------------------------------------------
-- promo_codes
-- Removed: times_used (derived value → see v_promo_usage view)
-- Storing a count that can be recomputed from trips creates
-- update anomalies and risks the count going stale.
-- -----------------------------------------------------------------
CREATE TABLE promo_codes (
    promo_code_id   SERIAL          PRIMARY KEY,
    code            VARCHAR(30)     NOT NULL UNIQUE,
    discount_type   VARCHAR(10)     NOT NULL CHECK (discount_type IN ('percent', 'flat')),
    discount_value  NUMERIC(8,2)    NOT NULL CHECK (discount_value > 0),
    valid_from      TIMESTAMP,
    valid_until     TIMESTAMP,
    max_uses        INTEGER,                              -- NULL = unlimited
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_promo_dates CHECK (
        valid_from IS NULL OR valid_until IS NULL OR valid_from < valid_until
    )
);



-- -----------------------------------------------------------------
CREATE TABLE trips (
    trip_id                 SERIAL          PRIMARY KEY,
    driver_id               INTEGER         NOT NULL REFERENCES drivers(driver_id),
    passenger_id            INTEGER         NOT NULL REFERENCES passengers(passenger_id),
    vehicle_id              INTEGER         REFERENCES vehicles(vehicle_id),
    pickup_location_id      INTEGER         NOT NULL REFERENCES locations(location_id),
    dropoff_location_id     INTEGER         NOT NULL REFERENCES locations(location_id),
    payment_method_id       INTEGER         REFERENCES payment_methods(payment_method_id) ON DELETE SET NULL,
    promo_code_id           INTEGER         REFERENCES promo_codes(promo_code_id),

    -- Fare components (fare_amount computed in view)
    base_fare               NUMERIC(10,2)   NOT NULL CHECK (base_fare >= 0),
    tip_amount              NUMERIC(8,2)    NOT NULL DEFAULT 0.00 CHECK (tip_amount >= 0),
    discount_amount         NUMERIC(8,2)    NOT NULL DEFAULT 0.00 CHECK (discount_amount >= 0),
    surge_multiplier        NUMERIC(4,2)    NOT NULL DEFAULT 1.00 CHECK (surge_multiplier >= 1.00),

    -- Trip details
    distance_km             NUMERIC(6,2)    NOT NULL CHECK (distance_km >= 0),
    status                  VARCHAR(20)     NOT NULL CHECK (status IN ('completed', 'cancelled', 'no_show')),

    -- Timestamps
    requested_at            TIMESTAMP       NOT NULL,
    completed_at            TIMESTAMP,

    -- Ratings (dual: passenger rates driver; driver rates passenger)
    driver_rating           NUMERIC(2,1)    CHECK (driver_rating   BETWEEN 1.0 AND 5.0),
    passenger_rating        NUMERIC(2,1)    CHECK (passenger_rating BETWEEN 1.0 AND 5.0),

    -- Business rules
    CONSTRAINT chk_completed_at CHECK (
        (status = 'completed' AND completed_at IS NOT NULL)
        OR (status != 'completed')
    ),
    CONSTRAINT chk_discount_not_exceed_base CHECK (
        discount_amount <= base_fare
    )
);


-- -----------------------------------------------------------------
-- trip_cancellations
-- Separated from trips to:
--   1. Eliminate nullable columns that are only meaningful for
--      a subset of rows (status = 'cancelled')
--   2. Allow richer cancellation metadata without polluting trips
-- 1:1 with trips (one cancellation record per cancelled trip)
-- -----------------------------------------------------------------
CREATE TABLE trip_cancellations (
    trip_id             INTEGER         PRIMARY KEY REFERENCES trips(trip_id) ON DELETE CASCADE,
    cancelled_at        TIMESTAMP       NOT NULL DEFAULT NOW(),
    cancelled_by        VARCHAR(10)     NOT NULL CHECK (cancelled_by IN ('driver', 'passenger', 'system')),
    cancellation_reason VARCHAR(100)
);


-- =================================================================
-- INDEXES
-- =================================================================

CREATE INDEX idx_trips_driver_id         ON trips(driver_id);
CREATE INDEX idx_trips_passenger_id      ON trips(passenger_id);
CREATE INDEX idx_trips_vehicle_id        ON trips(vehicle_id);
CREATE INDEX idx_trips_requested_at      ON trips(requested_at);
CREATE INDEX idx_trips_status            ON trips(status);
CREATE INDEX idx_trips_promo_code_id     ON trips(promo_code_id);
CREATE INDEX idx_vehicle_assignments_driver ON vehicle_assignments(driver_id);
CREATE INDEX idx_driver_licenses_driver  ON driver_licenses(driver_id);
CREATE INDEX idx_drivers_status          ON drivers(status);
CREATE INDEX idx_passengers_status       ON passengers(status);


-- =================================================================
-- VIEWS (replacing derived / computed stored columns)
-- =================================================================


-- -----------------------------------------------------------------
-- v_trips
-- Restores fare_amount and duration_minutes as computed columns
-- so consumers do not need to know the formula.
-- -----------------------------------------------------------------
CREATE OR REPLACE VIEW v_trips AS
SELECT
    t.*,
    ROUND(
        (t.base_fare * t.surge_multiplier) + t.tip_amount - t.discount_amount,
    2)                                                          AS fare_amount,
    CASE
        WHEN t.completed_at IS NOT NULL
        THEN EXTRACT(EPOCH FROM (t.completed_at - t.requested_at)) / 60
    END                                                         AS duration_minutes,
    tc.cancelled_at,
    tc.cancelled_by,
    tc.cancellation_reason
FROM trips t
LEFT JOIN trip_cancellations tc USING (trip_id);


-- -----------------------------------------------------------------
-- v_promo_usage
-- Restores times_used as an accurate, always-fresh computed count.
-- -----------------------------------------------------------------
CREATE OR REPLACE VIEW v_promo_usage AS
SELECT
    pc.*,
    COUNT(t.trip_id) AS times_used
FROM promo_codes pc
LEFT JOIN trips t USING (promo_code_id)
GROUP BY pc.promo_code_id;