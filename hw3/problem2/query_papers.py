import json, sys, time
import boto3
from boto3.dynamodb.conditions import Key

# dynamoDB table name
DEFAULT_TABLE = "arxiv-papers"


def parse_kv(argv):
    # parsing
    out = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--"):
            key = argv[i][2:]
            val = argv[i + 1] if (i + 1) < len(argv) else None
            out[key] = val
            i += 2
        else:
            i += 1
    return out


def dynamo(region):
    # returns DynamoDB resource bound to optional region
    if region:
        return boto3.resource("dynamodb", region_name=region)
    return boto3.resource("dynamodb")


def trim(item):

    return {
        "arxiv_id": item.get("arxiv_id"),
        "title": item.get("title"),
        "authors": item.get("authors", []),
        "published": item.get("published"),
        "categories": item.get("categories", []),
    }


def out_json(obj):
    #  JSON to stdout
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")


# Query

def query_recent_in_category(table, category, limit=20):
    # newest papers for category from table partition

    # partition on PK = CATEGORY#{category}
    # sorting by SK descending 
    # limit N items 

    return table.query(
        KeyConditionExpression=Key('PK').eq(f'CATEGORY#{category}'),
        ScanIndexForward=False,
        Limit=int(limit),
    )["Items"]


def query_papers_by_author(table, author_name):
    # all papers by author

    return table.query(
        IndexName='AuthorIndex',
        KeyConditionExpression=Key('GSI1PK').eq(
            f'AUTHOR#{" ".join(author_name.split()).lower()}'
        ),
    )["Items"]


def get_paper_by_id(table, arxiv_id):
    # returns the first match or None by fetching paper arXiv id wth PaperIdIndex (GSI2) 
    resp = table.query(
        IndexName='PaperIdIndex',
        KeyConditionExpression=Key('GSI2PK').eq(f'PAPER#{arxiv_id}'),
    )["Items"]
    return resp[0] if resp else None


def query_papers_in_date_range(table, category, start_date, end_date):
    #  date‑range scan
    
    return table.query(
        KeyConditionExpression=Key('PK').eq(f'CATEGORY#{category}')
        & Key('SK').between(f'{start_date}#', f'{end_date}#zzzzzzzz'),
    )["Items"]


def query_papers_by_keyword(table, keyword, limit=20):
    # most recent papers
    return table.query(
        IndexName='KeywordIndex',
        KeyConditionExpression=Key('GSI3PK').eq(f'KEYWORD#{keyword.lower()}'),
        ScanIndexForward=False,
        Limit=int(limit),
    )["Items"]


# CLI

def main():
    # command name
    if len(sys.argv) < 2:
        sys.stderr.write("Missing command\n")
        sys.exit(1)

    cmd = sys.argv[1]  # recent | author | get | daterange | keyword
    kv = parse_kv(sys.argv[2:])

    # confg: table name, region ---> build a table
    table_name = kv.get("table", DEFAULT_TABLE)
    region = kv.get("region")
    db = dynamo(region)
    table = db.Table(table_name)

    # ,etrics
    t0 = time.perf_counter()
    res = []
    qtype = cmd
    params = {}

    try:
        if cmd == "recent":
            if len(sys.argv) < 3:
                raise SystemExit("recent <category> [--limit 20] ...")
            category = sys.argv[2]
            limit = kv.get("limit", "20")
            params = {"category": category, "limit": int(limit)}
            res = query_recent_in_category(table, category, limit)

        elif cmd == "author":

            if len(sys.argv) < 3:
                raise SystemExit("author <author_name> ...")
            author_name = sys.argv[2]
            params = {"author": author_name}
            res = query_papers_by_author(table, author_name)

        elif cmd == "get":
            if len(sys.argv) < 3:
                raise SystemExit("get <arxiv_id> ...")
            arxiv_id = sys.argv[2]
            params = {"arxiv_id": arxiv_id}
            item = get_paper_by_id(table, arxiv_id)
            res = [item] if item else []

        elif cmd == "daterange":
            if len(sys.argv) < 5:
                raise SystemExit("daterange <category> <start_date> <end_date> ...")
            category, start_date, end_date = sys.argv[2], sys.argv[3], sys.argv[4]
            params = {"category": category, "start_date": start_date, "end_date": end_date}
            res = query_papers_in_date_range(table, category, start_date, end_date)

        elif cmd == "keyword":
            if len(sys.argv) < 3:
                raise SystemExit("keyword <keyword> [--limit 20] ...")
            kw = sys.argv[2]
            limit = kv.get("limit", "20")
            params = {"keyword": kw, "limit": int(limit)}
            res = query_papers_by_keyword(table, kw, limit)

        else:
            raise SystemExit(f"Unknown command: {cmd}")

        # JSON response
        ms = int((time.perf_counter() - t0) * 1000)
        out_json({
            "query_type": qtype,
            "parameters": params,
            "results": [trim(x) for x in res if x],
            "count": len([x for x in res if x]),
            "execution_time_ms": ms,
        })

    except SystemExit as e:
        # usage error messages to stderr / exit 
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()