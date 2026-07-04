select * FROM trips;
--- Step 1: Check how many trips you have
SELECT
	COUNT(*)
FROM
	trips;
-- You should see: 5000

-- Step 2: Simulate a loader that inserts rows one-by-one (NO transaction)
--         We'll only insert 10 rows to keep it fast
INSERT INTO trips (driver_id, passenger_id, pickup_location_id, dropoff_location_id,
                   fare_amount, distance_km, status, requested_at)
VALUES (1, 1, 1, 2, 250.00, 8.5, 'completed', NOW());
-- (imagine repeating this 5000 times in a script)

-- Step 3: After the 3rd INSERT — STOP. Do NOT run any more.
--         Pretend your laptop just died here.

-- Step 4: Check the count again:
SELECT COUNT(*) FROM trips;
-- What do you see?  How many rows committed?


--1.  How many rows are in the DB right now?
--2.  If you re-run the full 5,000-row script tomorrow, what happens?


SELECT count(*) FROM trips;

DELETE  FROM trips WHERE trip_id > 5000;








------- consistency 
INSERT INTO trips (driver_id, passenger_id, pickup_location_id, dropoff_location_id,
                   fare_amount, distance_km, status, requested_at)
VALUES (1, 1, 1, 2, 250.00, 8.5, 'completed', NOW());

INSERT INTO trips (driver_id, passenger_id, pickup_location_id, dropoff_location_id,
                   fare_amount, distance_km, status, requested_at)
VALUES (1, 1, 1, 2, -250.00, 8.5, 'completed', NOW());

INSERT INTO trips (driver_id, passenger_id, pickup_location_id, dropoff_location_id,
                   fare_amount, distance_km, status, requested_at)
VALUES (1, 1, 1, 2, 250.00, 8.5, 'completed', NOW());


---- This is the part of transaction every thing should be rolled back 

--- isolation trun off the auto commit and open two tabs and run the query 


------- Durability 


SELECT count(*) FROM trips;
DELETE  FROM trips WHERE trip_id > 5000;

---------------------
SELECT count(*) FROM trips;

INSERT INTO trips (driver_id, passenger_id, pickup_location_id, dropoff_location_id,
                   fare_amount, distance_km, status, requested_at)
VALUES (1, 1, 1, 2, 250.00, 8.5, 'completed', NOW());

ROLLBACK ;


---- How to achive atomicity

BEGIN;

  INSERT INTO trips (driver_id, passenger_id, pickup_location_id,
                     dropoff_location_id, fare_amount, distance_km,
                     status, requested_at)
  VALUES (1, 1, 1, 2, 250.00, 8.5, 'completed', NOW());
  -- add 2 more INSERT statements here
  
  SELECT count(*) FROM trips t ;
  

COMMIT;

  SELECT count(*) FROM trips t ;

DELETE FROM trips WHERE trip_id > 5000;


BEGIN;

  INSERT INTO trips (driver_id, passenger_id, pickup_location_id,
                     dropoff_location_id, fare_amount, distance_km,
                     status, requested_at)
  VALUES (1, 1, 1, 2, 250.00, 8.5, 'completed', NOW());
  -- add 2 more INSERT statements here
  
  SELECT count(*) FROM trips t ;
  
  INSERT INTO trips (driver_id, passenger_id, pickup_location_id,
                     dropoff_location_id, fare_amount, distance_km,
                     status, requested_at)
  VALUES (1, 1, 1, 2, -250.00, 8.5, 'completed', NOW());
  
  INSERT INTO trips (driver_id, passenger_id, pickup_location_id,
                     dropoff_location_id, fare_amount, distance_km,
                     status, requested_at)
  VALUES (1, 1, 1, 2, 250.00, 8.5, 'completed', NOW());
  
COMMIT;

SELECT count(*) FROM trips;



BEGIN;
-- Step 1: insert a new driver​
INSERT INTO drivers (name)
VALUES ('Test Driver');

-- Step 2–4: insert 3 valid trips for that driver​
INSERT INTO  trips (driver_id,passenger_id,pickup_location_id,
dropoff_location_id,fare_amount,distance_km,status,requested_at)
VALUES (
(
SELECT driver_id FROM	drivers WHERE name = 'Test Driver'),
1,1,2,200.00,5.0,'completed',NOW());


-- (repeat this INSERT two more times)​
-- Step 5: insert a BROKEN trip (rating = 99 breaks the CHECK constraint)​
INSERT INTO trips (driver_id, passenger_id,pickup_location_id,dropoff_location_id,
fare_amount,distance_km, status, requested_at, rating)
VALUES (
(SELECT	driver_id FROM drivers WHERE name = 'Test Driver'),
1,1,2,500.00,10.0,'completed',NOW(),99)

COMMIT;

SELECT count(*) FROM trips;


SELECT
	driver_id
FROM
	drivers
WHERE
	name = 'Test Driver';