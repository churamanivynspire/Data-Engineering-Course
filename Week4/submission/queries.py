EXTRACT_DRIVERS = """
    SELECT
        driver_id,
        name,
        status,
        joined_at,
        CASE
            WHEN joined_at >= NOW() - INTERVAL '6 months'  THEN '0-6 months'
            WHEN joined_at >= NOW() - INTERVAL '1 year'    THEN '6-12 months'
            WHEN joined_at >= NOW() - INTERVAL '2 years'   THEN '1-2 years'
            ELSE '2+ years'
        END AS tenure_bucket
    FROM drivers
"""

LOAD_DIM_DRIVER = """
    INSERT INTO dim_driver (
        driver_id,
        name,
        status,
        joined_at,
        tenure_bucket
    )
    VALUES %s
    ON CONFLICT DO NOTHING
    RETURNING driver_id, driver_key
"""

EXTRACT_PASSENGERS = """
    SELECT
        passenger_id,
        name,
        status,
        TO_CHAR(created_at, 'YYYY-MM') AS cohort_month,
        created_at
    FROM passengers
"""

LOAD_DIM_PASSENGER = """
    INSERT INTO dim_passenger (
        passenger_id,
        name,
        status,
        cohort_month,
        created_at
    )
    VALUES %s
    ON CONFLICT DO NOTHING
    RETURNING passenger_id, passenger_key
"""

EXTRACT_LOCATIONS = """
    SELECT
        location_id,
        city_name,
        state_province,
        country,
        CASE
            WHEN country <> 'USA' THEN 'International'
            WHEN state_province IN (
                'Connecticut','Maine','Massachusetts','New Hampshire','New Jersey',
                'New York','Pennsylvania','Rhode Island','Vermont'
            ) THEN 'Northeast'
            WHEN state_province IN (
                'Illinois','Indiana','Iowa','Kansas','Michigan','Minnesota',
                'Missouri','Nebraska','North Dakota','Ohio','South Dakota','Wisconsin'
            ) THEN 'Midwest'
            WHEN state_province IN (
                'Alabama','Arkansas','Delaware','Florida','Georgia','Kentucky',
                'Louisiana','Maryland','Mississippi','North Carolina','Oklahoma',
                'South Carolina','Tennessee','Texas','Virginia','West Virginia'
            ) THEN 'South'
            WHEN state_province IN (
                'Alaska','Arizona','California','Colorado','Hawaii','Idaho',
                'Montana','Nevada','New Mexico','Oregon','Utah','Washington','Wyoming'
            ) THEN 'West'
            ELSE 'International'
        END AS region,
        latitude,
        longitude
    FROM locations
"""

LOAD_DIM_LOCATION = """
    INSERT INTO dim_location (
        location_id,
        city_name,
        state_province,
        country,
        region,
        latitude,
        longitude
    )
    VALUES %s
    ON CONFLICT (location_id) DO NOTHING
    RETURNING location_id, location_key
"""

EXTRACT_PAYMENT_METHODS = "SELECT payment_method_id, name, type, is_active FROM payment_methods"

LOAD_DIM_PAYMENT_METHOD = """
    INSERT INTO dim_payment_method (
        payment_method_id,
        name,
        type,
        is_active
    )
    VALUES %s
    ON CONFLICT (payment_method_id) DO NOTHING
    RETURNING payment_method_id, payment_method_key
"""

EXTRACT_PROMO_CODES = "SELECT promo_code_id, code, discount_type, discount_value, is_active FROM promo_codes"

LOAD_DIM_PROMO_CODE = """
    INSERT INTO dim_promo_code (
        promo_code_id,
        code,
        discount_type,
        discount_value,
        is_active
    )
    VALUES %s
    ON CONFLICT (promo_code_id) DO NOTHING
    RETURNING promo_code_id, promo_code_key
"""

EXTRACT_TRIPS = """
    SELECT
        t.trip_id,
        t.driver_id,
        t.passenger_id,
        t.pickup_location_id,
        t.dropoff_location_id,
        t.payment_method_id,
        t.promo_code_id,
        t.base_fare,
        t.tip_amount,
        t.discount_amount,
        t.surge_multiplier,
        t.distance_km,
        t.status,
        t.requested_at,
        t.completed_at,
        t.driver_rating,
        t.passenger_rating,
        tc.cancelled_by          -- from trip_cancellations (NULL for non-cancelled)
    FROM trips t
    LEFT JOIN trip_cancellations tc ON t.trip_id = tc.trip_id
    ORDER BY t.requested_at
"""

LOAD_FACT_TRIPS = """
    INSERT INTO fact_trips (
        source_trip_id,
        date_key,
        driver_key,
        passenger_key,
        pickup_location_key,
        dropoff_location_key,
        payment_method_key,
        promo_code_key,
        base_fare,
        tip_amount,
        discount_amount,
        fare_amount,
        distance_km,
        duration_minutes,
        driver_rating,
        passenger_rating,
        surge_multiplier,
        requested_at
    )
    VALUES %s
    ON CONFLICT (source_trip_id) DO NOTHING
    RETURNING trip_key
"""

LOOKUP_DATE_KEYS = "SELECT date_key FROM dim_date"
