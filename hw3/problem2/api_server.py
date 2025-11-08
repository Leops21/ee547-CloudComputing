import json, os, sys, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


import boto3,os
from boto3.dynamodb.conditions import Key

# config
# read table/region from environment

TABLE_NAME = os.environ.get("TABLE_NAME", "arxiv-papers")
AWS_REGION = os.environ.get("AWS_REGION")

def dynamo():
    # Read region from environment, default to us-west-2
    region = os.environ.get("AWS_REGION", "us-west-2")
    print(f"Using DynamoDB region: {region}")
    return boto3.resource("dynamodb", region_name=region)


# create shared dynamoDB
DB = dynamo()
TABLE = DB.Table(TABLE_NAME)


def trim(item):
    # project item to public

    
    if not item:
        return None
    
    return {
        "arxiv_id": item.get("arxiv_id"),
        "title": item.get("title"),
        "authors": item.get("authors", []),
        "published": item.get("published"),
        "categories": item.get("categories", []),
    }

# dynamoDB query

def q_recent(category, limit=20):
    # newest papers within category partition

    
    resp = TABLE.query(
        KeyConditionExpression=Key('PK').eq(f'CATEGORY#{category}'),
        ScanIndexForward=False,
        Limit=int(limit),
    )
    return [trim(i) for i in resp["Items"] if i]


def q_author(author_name):
    # all papers by author
    key = " ".join(author_name.split()).lower()
    resp = TABLE.query(
        IndexName='AuthorIndex',
        KeyConditionExpression=Key('GSI1PK').eq(f'AUTHOR#{key}'),
    )
    return [trim(i) for i in resp["Items"] if i]


def q_get(arxiv_id):
    # single paper by id wth PaperIdIndex to return the raw item

    
    resp = TABLE.query(
        IndexName='PaperIdIndex',
        KeyConditionExpression=Key('GSI2PK').eq(f'PAPER#{arxiv_id}'),
    )
    return resp["Items"][0] if resp["Items"] else None


def q_daterange(category, start_date, end_date):
    # date range within a category

    
    resp = TABLE.query(
        KeyConditionExpression=Key('PK').eq(f'CATEGORY#{category}')
        & Key('SK').between(f'{start_date}#', f'{end_date}#zzzzzzzz'),
    )
    return [trim(i) for i in resp["Items"] if i]


def q_keyword(keyword, limit=20):
    # Newest papers for keyword with KeywordIndex
    resp = TABLE.query(
        IndexName='KeywordIndex',
        KeyConditionExpression=Key('GSI3PK').eq(f'KEYWORD#{keyword.lower()}'),
        ScanIndexForward=False,
        Limit=int(limit),
    )
    return [trim(i) for i in resp["Items"] if i]


# HTTP handler

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        # serializes payload to JSON and sends HTTP response wth headers
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # override: log to stdout instead of stderr with a simple format
        print("%s - - [%s] %s" % (
            self.address_string(),
            self.log_date_time_string(),
            fmt % args,
        ))

    def do_GET(self):
        #  GET requests to the appropriate query helper.
        # matches fixed prefixes and reads query-string params via urllib.parse
      
        
        t0 = time.perf_counter()
        try:
            url = urlparse(self.path)
            path = url.path
            qs = parse_qs(url.query)

            # /papers/recent?category=cs.LG&limit=20
            if path == "/papers/recent":
                category = (qs.get("category") or [""])[0]
                limit = int((qs.get("limit") or ["20"])[0])
                if not category:
                    return self._send(400, {"error": "missing category"})
                
                res = q_recent(category, limit)
                return self._send(200, {"category": category, "papers": res, "count": len(res)})

            # /papers/author/{author_name}
            if path.startswith("/papers/author/"):
                author_name = path.split("/papers/author/", 1)[1]
                res = q_author(author_name)
                return self._send(200, {"author": author_name, "papers": res, "count": len(res)})

            # /papers/keyword/{kw}?limit=20
            if path.startswith("/papers/keyword/"):
                keyword = path.split("/papers/keyword/", 1)[1]
                limit = int((qs.get("limit") or ["20"])[0])
                res = q_keyword(keyword, limit)
                return self._send(200, {"keyword": keyword, "papers": res, "count": len(res)})

            # /papers/{arxiv_id}
            if path.startswith("/papers/"):
                arxiv_id = path.split("/papers/", 1)[1]
                item = q_get(arxiv_id)
                if not item:
                    return self._send(404, {"error": "not found"})
                
                return self._send(200, item)

            # /papers/search?category=...&start=...&end=...
            if path == "/papers/search":
                category = (qs.get("category") or [""])[0]
                start = (qs.get("start") or [""])[0]
                end = (qs.get("end") or [""])[0]
                if not (category and start and end):
                    return self._send(400, {"error": "missing category/start/end"})
                
                res = q_daterange(category, start, end)

                return self._send(200, {
                    "category": category,
                    "start": start,
                    "end": end,
                    "papers": res,
                    "count": len(res),
                })

            # No route matched
            self._send(404, {"error": "endpoint not found"})

        except Exception as e:
            # catch-all
            self._send(500, {"error": "server error", "detail": str(e)})
        finally:
            # basic request timing to stdout
            ms = int((time.perf_counter() - t0) * 1000)
            print(f"{self.command} {self.path} -> {self.protocol_version} {ms}ms")


# Server bootstrap

def main():
    # determine TCP port from argv, default 8080
    port = 8080
    if len(sys.argv) >= 2 and sys.argv[1].isdigit():
        port = int(sys.argv[1])

    # bind to all interfaces for container/VM use. For local 127.0.0.1.
    srv = HTTPServer(("0.0.0.0", port), Handler)
    print(
        f"API server listening on :{port} using table '{TABLE_NAME}' "
        f"region='{AWS_REGION or 'default'}'"
    )
    srv.serve_forever()


if __name__ == "__main__":
    main()