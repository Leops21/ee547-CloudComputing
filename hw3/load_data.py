#!/usr/bin/env python3
import argparse
import csv

import json
import os
import sys
from datetime import datetime
import psycopg2  # PostgreSQL adapter for Python

# Print to stderr (for error messages)
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

# reads the .sql file and returns its contents as a string
def read_sql(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# converts CSV timestamp string into Python datetime
def to_timestamp(s):

    return datetime.fromisoformat(s)

def main():
    # parsing
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--dbname", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--port", default="5432")
    parser.add_argument("--datadir", required=True)  # folder wth CSV files
    parser.add_argument("--schema", default="schema.sql")  # SQL schema
    args = parser.parse_args()

    # connecting to PostgreSQL
    conn = psycopg2.connect(
        host=args.host,
        dbname=args.dbname,
        user=args.user,
        password=args.password,
        port=args.port
    )
    conn.autocommit = False  # manual commit
    print(f"Connected to {args.dbname}@{args.host}")

    try:
        with conn.cursor() as cur:
            # creates database schema
            cur.execute(read_sql(args.schema))  # run CREATE TABLE
            conn.commit()

            print("Tables created: lines, stops, line_stops, trips, stop_events")



            # loads any CSV into list of dicts
            def load_csv(relpath):
                full = os.path.join(args.datadir, relpath)
                with open(full, "r", encoding="utf-8") as f:
                    return list(csv.DictReader(f))
            # loads lines.csv
            lines_rows = load_csv("lines.csv")
            cur.executemany(
                "INSERT INTO lines(line_name, vehicle_type) VALUES (%s, %s)",
                [(r["line_name"].strip(), r["vehicle_type"].strip()) for r in lines_rows],
            )
            conn.commit()



            # loads stops.csv
            stops_rows = load_csv("stops.csv")
            cur.executemany(
                "INSERT INTO stops(stop_name, latitude, longitude) VALUES (%s, %s, %s)",
                [
                    (
                        r["stop_name"].strip(),
                        float(r["latitude"]),
                        float(r["longitude"]),
                    )
                    for r in stops_rows
                ],
            )
            conn.commit()
            # mapping dicts, name:ID
            cur.execute("SELECT line_id, line_name FROM lines")

            line_map = {name: lid for (lid, name) in [(row[0], row[1]) for row in cur.fetchall()]}
            cur.execute("SELECT stop_id, stop_name FROM stops")

            stop_map = {name: sid for (sid, name) in [(row[0], row[1]) for row in cur.fetchall()]}



            # loads line_stops.csv
            ls_rows = load_csv("line_stops.csv")
            payload = []
            for r in ls_rows:
                ln = r["line_name"].strip()

                sn = r["stop_name"].strip()
                if ln not in line_map:

                    raise ValueError(f"Unknown line_name '{ln}' in line_stops.csv")
                if sn not in stop_map:
                    raise ValueError(f"Unknown stop_name '{sn}' in line_stops.csv")
                payload.append(
                    (
                        line_map[ln],

                        stop_map[sn],
                        int(r["sequence"]),

                        int(r["time_offset"]),
                    )
                )
            cur.executemany(
                """
                INSERT INTO line_stops(line_id, stop_id, sequence_number, time_offset_minutes)
                VALUES (%s, %s, %s, %s)
                """,
                payload,
            )
            conn.commit()



            # loads trips.csv
            trips_rows = load_csv("trips.csv")
            payload = []
            for r in trips_rows:
                ln = r["line_name"].strip()
                if ln not in line_map:
                    raise ValueError(f"Unknown line_name '{ln}' in trips.csv")
                payload.append(
                    (
                        r["trip_id"].strip(),
                        line_map[ln],
                        to_timestamp(r["scheduled_departure"].strip()),
                        r["vehicle_id"].strip(),
                    )
                )
            cur.executemany(
                """
                INSERT INTO trips(trip_id, line_id, scheduled_departure, vehicle_id)
                VALUES (%s, %s, %s, %s)
                """,
                payload,
            )
            conn.commit()



            # loads stop_events.csv
            se_rows = load_csv("stop_events.csv")
            payload = []
            for r in se_rows:
                trip_id = r["trip_id"].strip()
                stop_name = r["stop_name"].strip()
                if stop_name not in stop_map:
                    raise ValueError(f"Unknown stop_name '{stop_name}' in stop_events.csv")
                payload.append(
                    (
                        trip_id,
                        stop_map[stop_name],
                        to_timestamp(r["scheduled"].strip()),
                        to_timestamp(r["actual"].strip()),
                        int(r["passengers_on"]),
                        int(r["passengers_off"]),
                    )
                )

            cur.executemany(
                """
                INSERT INTO stop_events(trip_id, stop_id, scheduled, actual, passengers_on, passengers_off)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                payload,
            )
            conn.commit()

            # total rows loaded
            total = (
                len(lines_rows)
                + len(stops_rows)
                + len(ls_rows)
                + len(trips_rows)
                + len(se_rows)
            )
            print(f"\nTotal: {total} rows loaded successfully!")

    except Exception as ex:
        # roll back uncommitted changes
        conn.rollback()
        eprint("ERROR:", ex)
        sys.exit(1)

    finally:
        # closing connection
        conn.close()


if __name__ == "__main__":
    main()