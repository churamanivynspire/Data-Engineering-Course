SELECT count(*) FROM trips r ;


SELECT * FROM trips;

SELECT DISTINCT payment_method FROM rides r; 


EXPLAIN ANALYZE
SELECT * FROM trips WHERE driver_id = 3;
--
--Seq Scan on trips  (cost=0.00..25375.00 rows=77833 width=67) (actual time=0.021..343.108 rows=76776 loops=1)
--  Filter: (driver_id = 3)
--  Rows Removed by Filter: 923224
--Planning Time: 0.183 ms
--Execution Time: 348.307 ms

EXPLAIN ANALYZE
SELECT * FROM trips WHERE status = 'completed';

--Seq Scan on trips  (cost=0.00..25375.00 rows=598367 width=67) (actual time=0.010..379.016 rows=600597 loops=1)
--  Filter: ((status)::text = 'completed'::text)
--  Rows Removed by Filter: 399403
--Planning Time: 0.098 ms
--Execution Time: 419.160 ms

----
  EXPLAIN ANALYZE
SELECT * FROM trips WHERE driver_id = 3 AND status = 'completed';


--Gather  (cost=1000.00..24782.30 rows=46573 width=67) (actual time=6.766..221.205 rows=45903 loops=1)
--  Workers Planned: 2
--  Workers Launched: 2
--  ->  Parallel Seq Scan on trips  (cost=0.00..19125.00 rows=19405 width=67) (actual time=0.027..174.928 rows=15301 loops=3)
--        Filter: ((driver_id = 3) AND ((status)::text = 'completed'::text))
--        Rows Removed by Filter: 318032
--Planning Time: 0.093 ms
--Execution Time: 224.718 ms

CREATE INDEX idx_trips_driver_id ON trips(driver_id);

EXPLAIN ANALYZE
SELECT * FROM trips WHERE driver_id = 3;
--
--Bitmap Heap Scan on trips  (cost=871.63..14719.54 rows=77833 width=67) (actual time=23.587..77.245 rows=76776 loops=1)
--  Recheck Cond: (driver_id = 3)
--  Heap Blocks: exact=12843
--  ->  Bitmap Index Scan on idx_trips_driver_id  (cost=0.00..852.17 rows=77833 width=0) (actual time=19.248..19.249 rows=76776 loops=1)
--        Index Cond: (driver_id = 3)
--Planning Time: 2.137 ms
--Execution Time: 84.707 ms

CREATE INDEX idx_trips_status ON trips(status);

SELECT DISTINCT status FROM trips t ;


EXPLAIN ANALYZE
SELECT * FROM trips WHERE status = 'cancelled';

--Bitmap Heap Scan on trips  (cost=2232.23..17597.22 rows=199200 width=67) (actual time=22.945..130.690 rows=199552 loops=1)
--  Recheck Cond: ((status)::text = 'cancelled'::text)
--  Heap Blocks: exact=12875
--  ->  Bitmap Index Scan on idx_trips_status  (cost=0.00..2182.43 rows=199200 width=0) (actual time=18.687..18.688 rows=199552 loops=1)
--        Index Cond: ((status)::text = 'cancelled'::text)
--Planning Time: 0.173 ms
--Execution Time: 146.515 ms


CREATE INDEX idx_trips_driver_status ON trips(driver_id, status);

EXPLAIN ANALYZE
SELECT * FROM trips WHERE driver_id = 3 AND status = 'completed';
--
--Bitmap Heap Scan on trips  (cost=641.80..14215.39 rows=46573 width=67) (actual time=12.414..60.521 rows=45903 loops=1)
--  Recheck Cond: ((driver_id = 3) AND ((status)::text = 'completed'::text))
--  Heap Blocks: exact=12555
--  ->  Bitmap Index Scan on idx_trips_driver_status  (cost=0.00..630.15 rows=46573 width=0) (actual time=5.293..5.294 rows=45903 loops=1)
--        Index Cond: ((driver_id = 3) AND ((status)::text = 'completed'::text))
--Planning Time: 0.314 ms
--Execution Time: 63.604 ms


CREATE VIEW completed_trips_detail_view AS
SELECT 
d.name driver_name,
p.name passenger_name,
pck.city_name  AS pickup_city,
dst.city_name AS dropodd_city,
t.requested_at 
FROM trips t
INNER JOIN drivers  d
ON t.driver_id = d.driver_id
INNER JOIN passengers p 
ON t.passenger_id = p.passenger_id
INNER JOIN locations pck
ON t.pickup_location_id = pck.location_id
INNER JOIN locations dst 
ON t.dropoff_location_id = dst.location_id
WHERE t.status = 'completed';


SELECT * FROM completed_trips_detail_view;

EXPLAIN ANALYZE 
SELECT * FROM drivers d 
WHERE d.driver_id NOT IN (SELECT driver_id FROM trips );


--Seq Scan on drivers d  (cost=0.00..5485134.00 rows=160 width=222) (actual time=948.653..948.655 rows=1 loops=1)
--  Filter: (NOT (SubPlan 1))
--  Rows Removed by Filter: 13
--  SubPlan 1
--    ->  Materialize  (cost=0.00..31782.00 rows=1000000 width=4) (actual time=0.003..54.528 rows=71438 loops=14)
--          ->  Seq Scan on trips  (cost=0.00..22875.00 rows=1000000 width=4) (actual time=0.028..249.968 rows=1000000 loops=1)
--Planning Time: 0.108 ms
--JIT:
--  Functions: 6
--  Options: Inlining true, Optimization true, Expressions true, Deforming true
--  Timing: Generation 0.548 ms, Inlining 7.763 ms, Optimization 24.517 ms, Emission 22.548 ms, Total 55.376 ms
--Execution Time: 955.289 ms

EXPLAIN ANALYZE 
SELECT d.* FROM drivers d 
LEFT JOIN trips t 
ON d.driver_id = t.driver_id
WHERE t.trip_id IS NULL;

--Hash Right Join  (cost=17.20..25551.97 rows=1 width=222) (actual time=596.736..596.743 rows=1 loops=1)
--  Hash Cond: (t.driver_id = d.driver_id)
--  Filter: (t.trip_id IS NULL)
--  Rows Removed by Filter: 1000000
--  ->  Seq Scan on trips t  (cost=0.00..22875.00 rows=1000000 width=8) (actual time=0.006..168.316 rows=1000000 loops=1)
--  ->  Hash  (cost=13.20..13.20 rows=320 width=222) (actual time=0.022..0.024 rows=14 loops=1)
--        Buckets: 1024  Batches: 1  Memory Usage: 9kB
--        ->  Seq Scan on drivers d  (cost=0.00..13.20 rows=320 width=222) (actual time=0.011..0.014 rows=14 loops=1)
--Planning Time: 0.205 ms
--Execution Time: 596.779 ms



---- driver name, total trip, 
--completed trip, cancellation trip,
--cancellation rate,average rating

SELECT
	d.name AS driver_name,
	count(trip_id) total_trip,
	count(CASE WHEN t.status = 'completed' THEN 1 ELSE NULL END) completed_count,
	count(trip_id) FILTER (WHERE status = 'completed') AS completed_count,
	count(trip_id) FILTER (WHERE status = 'cancelled') AS cancelled_count,
	round(count(trip_id) FILTER (WHERE status = 'cancelled')*100.00/NULLIF(count(trip_id),0),2)
	FROM
	drivers d
LEFT JOIN trips t 
ON
	t.driver_id = d.driver_id
GROUP BY
	d.name ;

SELECT 
CASE WHEN t.status = 'completed' THEN 1 ELSE NULL END AS is_completed,
t.status ,* 
FROM drivers d 
LEFT JOIN trips t 
ON t.driver_id = d.driver_id


SELECT 
	d.name driver_name,
	count(t.trip_id) total_trip,
	count(
	CASE WHEN status = 'completed' THEN 1 ELSE NULL END 
	) total_completed_count,
	count(trip_id) FILTER (WHERE status = 'cancelled') cancelled,
	Round(count(trip_id) FILTER (WHERE status = 'cancelled')*100.00
	/NULLIF(count(t.trip_id),0),2)  AS cancellation_rate
FROM drivers d
LEFT   JOIN trips t ON 
d.driver_id = t.driver_id
GROUP BY d."name";

INSERT INTO drivers (name)
VALUES ('Test 1');


