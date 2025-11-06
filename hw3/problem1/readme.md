1 Schema Decisions: Natural vs surrogate keys? Why?
I used both serial integers for most tables (lines, stops, line_stops) and natutal keys for line_name, stop_name
because surrogate keys make joins faster and stable, ensuring referential integrity

2 Constraints: What CHECK/UNIQUE constraints did you add?
I used the check and unique constraint:
CHECK (vehicle_type IN ('rail', 'bus'))       TAble: lines
CHECK (latitude BETWEEN -90 AND 90)        TAble: stops
CHECK (longitude BETWEEN -180 AND 180)        TAble: stops
CHECK (sequence_number >= 1)        TAble: line_stops
CHECK (time_offset_minutes >= 0)        TAble: line_stops
CHECK (passengers_on >= 0 AND passengers_off >= 0)        TAble: stop_events
UNIQUE (line_name) and UNIQUE (stop_name)        TAble: lines, stops
UNIQUE (line_id, stop_id)          TAble: line_stops

3 Complex Query: Which query was hardest? Why?
query 4, it was required to join 4 tables, the tough part was to ensure the correct order of stops by scheduled time/sequence_number.
left join was really tricky to apply

4 Foreign Keys: Give example of invalid data they prevent
stop_events(stop_id , stops.stop_id) prevent recording a stop event at an undefined stop.
For example 
INSERT INTO stop_events VALUES ('T9999', 9999, '2025-10-01 06:00:00', '2025-10-01 06:05:00', 10, 5); 
would fail because stop_id 1M or trip T0000 are out of range / do not exists

5 When Relational: Why is SQL good for this domain?
because the data is relational, it fits the ACID properties, and also we can normalize the data, perform queries on joins and aggregation to retrieve data
