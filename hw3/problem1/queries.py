#!/usr/bin/env python3
import argparse
import json
import sys

import psycopg2 # PostgreSQL adapter for Python


# query results into list of dicts, column_name:value
def rows_to_dicts(cur):
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


#                  *** queries  ***

# Q1: List all stops on Route 20 in order
def q1(cur, route):

    cur.execute(
        """

        SELECT s.stop_name,
               ls.sequence_number AS sequence,
               ls.time_offset_minutes AS time_offset
        FROM line_stops ls

        JOIN lines l ON ls.line_id = l.line_id
        JOIN stops s ON ls.stop_id = s.stop_id
        WHERE l.line_name = %s
        ORDER BY ls.sequence_number

        """,

        (route,),
    )
    return " stops on x route in order", rows_to_dicts(cur)


# Q2: Trips during morning rush (7-9 AM)
def q2(cur):
    cur.execute(
        """

        SELECT t.trip_id, l.line_name, t.scheduled_departure
        FROM trips t
        JOIN lines l ON t.line_id = l.line_id

        WHERE (t.scheduled_departure::time >= TIME '07:00:00'
           AND t.scheduled_departure::time <  TIME '09:00:00')

        ORDER BY t.scheduled_departure

        """
    )
    return "Trips during morning rush (7-9 AM)", rows_to_dicts(cur)


# Q3: Transfer stops (stops on 2+ routes)
def q3(cur):
    cur.execute(
        """

        SELECT s.stop_name, COUNT(DISTINCT ls.line_id) AS line_count
        FROM line_stops ls
        JOIN stops s ON s.stop_id = ls.stop_id
        GROUP BY s.stop_id, s.stop_name

        HAVING COUNT(DISTINCT ls.line_id) >= 2
        ORDER BY line_count DESC, s.stop_name

        """
    )
    return "Transfer stops (on 2+ routes)", rows_to_dicts(cur)


# Q4: Complete route for trip T0001
def q4(cur, trip_id):
    cur.execute(
        """
        SELECT
          s.stop_name,
          se.scheduled,

          se.actual,
          ls.sequence_number AS sequence,
          ls.time_offset_minutes AS time_offset,
          se.passengers_on,
          se.passengers_off

        FROM stop_events se

        JOIN stops s ON s.stop_id = se.stop_id
        JOIN trips t ON t.trip_id = se.trip_id

        LEFT JOIN line_stops ls
          ON ls.line_id = t.line_id AND ls.stop_id = se.stop_id
        WHERE se.trip_id = %s
        ORDER BY se.scheduled

        """,
        (trip_id,),
    )
    return "Complete route for trip T0001", rows_to_dicts(cur)


# Q5: Find which routes serve both specified stops
def q5(cur, stop_a, stop_b):
    cur.execute(
        """
        SELECT l.line_name
        FROM lines l

        JOIN line_stops ls1 ON ls1.line_id = l.line_id

        JOIN stops s1 ON s1.stop_id = ls1.stop_id AND s1.stop_name = %s

        JOIN line_stops ls2 ON ls2.line_id = l.line_id

        JOIN stops s2 ON s2.stop_id = ls2.stop_id AND s2.stop_name = %s

        GROUP BY l.line_id, l.line_name
        ORDER BY l.line_name
        """,
        (stop_a, stop_b),
    )
    return " Routes serving both Wilshire / Veteran and Le Conte / Broxton", rows_to_dicts(cur)


# Q6: Average ridership by line
def q6(cur):
    cur.execute(
        """
        SELECT l.line_name,

               ROUND(AVG((se.passengers_on + se.passengers_off))::numeric, 2) AS avg_passengers

        FROM stop_events se
        JOIN trips t ON t.trip_id = se.trip_id
        JOIN lines l ON l.line_id = t.line_id

        GROUP BY l.line_name
        ORDER BY avg_passengers DESC
        """
    )
    return "Average ridership by line", rows_to_dicts(cur)


# Q7: 10 busiest stops
def q7(cur):
    cur.execute(
        """
        SELECT s.stop_name,
               SUM(se.passengers_on + se.passengers_off) AS total_activity

        FROM stop_events se
        JOIN stops s ON s.stop_id = se.stop_id
        GROUP BY s.stop_name

        ORDER BY total_activity DESC, s.stop_name
        LIMIT 10
        """
    )
    return "Top 10 busiest stops (boardings+alightings)", rows_to_dicts(cur)


# Q8: delayed stop events (>2 min late) each line has
def q8(cur):
    cur.execute(
        """
        SELECT l.line_name, COUNT(*) AS delay_count

        FROM stop_events se
        JOIN trips t ON t.trip_id = se.trip_id
        JOIN lines l ON l.line_id = t.line_id
        WHERE se.actual > se.scheduled + INTERVAL '2 minutes'

        GROUP BY l.line_name
        ORDER BY delay_count DESC
        """
    )
    return "Count of delayed stop events by line (>2 min late)", rows_to_dicts(cur)


# Q9: Trips with 3+ delayed stops
def q9(cur):
    cur.execute(
        """

        SELECT se.trip_id, COUNT(*) AS delayed_stop_count
        FROM stop_events se
        WHERE se.actual > se.scheduled + INTERVAL '2 minutes'
        GROUP BY se.trip_id
        HAVING COUNT(*) >= 3

        ORDER BY delayed_stop_count DESC, se.trip_id

        """
    )
    return "Trips with 3+ delayed stops", rows_to_dicts(cur)


# Q10:  Stops with above-average ridership

def q10(cur):
    cur.execute(
        """

        WITH totals AS (

          SELECT stop_id, SUM(passengers_on) AS total_boardings
          FROM stop_events
          GROUP BY stop_id
        ),

        avg_total AS (
          SELECT AVG(total_boardings) AS avg_boardings FROM totals
        )

        SELECT s.stop_name, t.total_boardings
        FROM totals t
        JOIN stops s ON s.stop_id = t.stop_id
        CROSS JOIN avg_total a
        WHERE t.total_boardings > a.avg_boardings
        ORDER BY t.total_boardings DESC, s.stop_name

        """
    )
    return "Stops with above-average total boardings", rows_to_dicts(cur)


# query exec

# runs one of above queries (Q1–Q10)

def run_query(conn_args, which, params):
    conn = psycopg2.connect(**conn_args)

    try:
        with conn.cursor() as cur:

            if which == "Q1":
                desc, rows = q1(cur, params.get("route", "Route 20"))

            elif which == "Q2":
                desc, rows = q2(cur)

            elif which == "Q3":
                desc, rows = q3(cur)

            elif which == "Q4":
                desc, rows = q4(cur, params.get("trip", "T0001"))
                
            elif which == "Q5":
                a = params.get("stop_a", "Wilshire / Veteran")
                b = params.get("stop_b", "Le Conte / Broxton")
                desc, rows = q5(cur, a, b)

            elif which == "Q6":
                desc, rows = q6(cur)

            elif which == "Q7":
                desc, rows = q7(cur)

            elif which == "Q8":
                desc, rows = q8(cur)

            elif which == "Q9":
                desc, rows = q9(cur)

            elif which == "Q10":
                desc, rows = q10(cur)
            else:
                raise ValueError(f"Unknown query: {which}")

            # dictionary with results
            return {
                "query": which,
                "description": desc,
                "results": rows,
                "count": len(rows),
            }
        
    finally:
        conn.close()



def main():
    
    # Parsing args
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", default="5432")
    ap.add_argument("--dbname", required=True)
    ap.add_argument("--user", default="transit")
    ap.add_argument("--password", default="transit123")
    ap.add_argument("--query", help="Q1..Q10")
    ap.add_argument("--all", action="store_true", help="Run all queries Q1–Q10")

    ap.add_argument("--format", choices=["json"], default="json")


    ap.add_argument("--route", default="Route 20")
    ap.add_argument("--trip", default="T0001")
    ap.add_argument("--stop_a", default="Wilshire / Veteran")
    ap.add_argument("--stop_b", default="Le Conte / Broxton")
    args = ap.parse_args()



    # config for psycopg2
    conn_args = dict(
        host=args.host,
        port=args.port,
        dbname=args.dbname,
        user=args.user,
        password=args.password,
    )


    # options 


    # O1: run all queries, print JSON array
    if args.all:
        out = []
        for i in range(1, 11):
            out.append(run_query(conn_args, f"Q{i}", vars(args)))
        print(json.dumps(out, default=str, indent=2))
        return


    # O2: run a single query
    if not args.query:
        sys.exit(2)

    res = run_query(conn_args, args.query, vars(args))
    print(json.dumps(res, default=str, indent=2))

if __name__ == "__main__":
    main()