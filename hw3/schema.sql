DROP TABLE IF EXISTS stop_events CASCADE;
DROP TABLE IF EXISTS trips CASCADE;
DROP TABLE IF EXISTS line_stops CASCADE;
DROP TABLE IF EXISTS stops CASCADE;
DROP TABLE IF EXISTS lines CASCADE;

-- lines
CREATE TABLE lines (
    line_id SERIAL PRIMARY KEY,
    line_name VARCHAR(50) NOT NULL UNIQUE,
    vehicle_type VARCHAR(10) NOT NULL CHECK (vehicle_type IN ('rail', 'bus'))
);

-- stops
CREATE TABLE stops (
    stop_id SERIAL PRIMARY KEY,
    stop_name VARCHAR(120) NOT NULL UNIQUE,
    latitude NUMERIC(9,6) NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude NUMERIC(9,6) NOT NULL CHECK (longitude BETWEEN -180 AND 180)
);

-- line_stops
CREATE TABLE line_stops (
    line_id INTEGER NOT NULL REFERENCES lines(line_id) ON DELETE CASCADE,
    stop_id INTEGER NOT NULL REFERENCES stops(stop_id) ON DELETE CASCADE,
    sequence_number INTEGER NOT NULL CHECK (sequence_number >= 1),
    time_offset_minutes INTEGER NOT NULL CHECK (time_offset_minutes >= 0),
    PRIMARY KEY (line_id, sequence_number),
    UNIQUE (line_id, stop_id)
);

-- trips
CREATE TABLE trips (
    trip_id VARCHAR(32) PRIMARY KEY, -- viene como T0001 en CSV
    line_id INTEGER NOT NULL REFERENCES lines(line_id) ON DELETE RESTRICT,
    scheduled_departure TIMESTAMP NOT NULL,
    vehicle_id VARCHAR(64) NOT NULL,
    UNIQUE (line_id, scheduled_departure, vehicle_id)
);

-- stop_events
CREATE TABLE stop_events (
    trip_id VARCHAR(32) NOT NULL REFERENCES trips(trip_id) ON DELETE CASCADE,
    stop_id INTEGER NOT NULL REFERENCES stops(stop_id) ON DELETE RESTRICT,
    scheduled TIMESTAMP NOT NULL,
    actual TIMESTAMP NOT NULL,
    passengers_on INTEGER NOT NULL CHECK (passengers_on >= 0),
    passengers_off INTEGER NOT NULL CHECK (passengers_off >= 0),
    PRIMARY KEY (trip_id, stop_id, scheduled)
);

-- idx
CREATE INDEX idx_lines_name ON lines(line_name);
CREATE INDEX idx_stops_name ON stops(stop_name);
CREATE INDEX idx_line_stops_line_seq ON line_stops(line_id, sequence_number);
CREATE INDEX idx_trips_line_departure ON trips(line_id, scheduled_departure);
CREATE INDEX idx_stop_events_trip_sched ON stop_events(trip_id, scheduled);
