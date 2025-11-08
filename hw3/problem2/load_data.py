import json, sys, os, re, time
from datetime import datetime
from collections import Counter, defaultdict

import boto3
from botocore.exceptions import ClientError

# list for keyword extraction
STOPWORDS = {
    'the','a','an','and','or','but','in','on','at','to','for','of','with','by','from','up',
    'about','into','through','during','is','are','was','were','be','been','being','have','has',
    'had','do','does','did','will','would','could','should','may','might','can','this','that',
    'these','those','we','our','use','using','based','approach','method','paper','propose',
    'proposed','show'
}

# pattern
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-']+")


def parse_args(argv):
    # parse CLI args and return (path, table, region|None)
    if len(argv) < 3:
        sys.exit(1)
    path = argv[1]
    table = argv[2]
    region = None


    # positional parser for optional region flag
    if len(argv) >= 5 and argv[3] == "--region":
        region = argv[4]

    return path, table, region


def dyn_resource(region):
    # returns DynamoDB resource bound to optional region
    if region:
        return boto3.resource("dynamodb", region_name=region)
    return boto3.resource("dynamodb")


def dyn_client(region):
    # return DynamoDB client bound to optional region
    if region:

        return boto3.client("dynamodb", region_name=region)
    
    return boto3.client("dynamodb")


def ensure_table(client, resource, table_name):
    """Ensure the target table exists with the expected schema.

    If the table is missing, create it with:
      - PK/SK primary keys for the single-table design
      - 3 GSIs to support author, paper-id, and keyword queries
    Blocks until the table is ACTIVE, then returns a Table resource.
    """
    # 1 trying to describe the table
    try:
        client.describe_table(TableName=table_name)
        print(f"Table exists: {table_name}")

        return resource.Table(table_name)
    
    except ClientError as e:
        # not-found error; re-raise anything else
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    # if table doent exist: create it on-demand billing / GSIs
    print(f"Creating DynamoDB table: {table_name}")
    resource.create_table(
        TableName=table_name,
        BillingMode='PAY_PER_REQUEST',
        KeySchema=[{"AttributeName":"PK","KeyType":"HASH"},
                   {"AttributeName":"SK","KeyType":"RANGE"}],
        AttributeDefinitions=[
            {"AttributeName":"PK","AttributeType":"S"},
            {"AttributeName":"SK","AttributeType":"S"},
            {"AttributeName":"GSI1PK","AttributeType":"S"},
            {"AttributeName":"GSI1SK","AttributeType":"S"},
            {"AttributeName":"GSI2PK","AttributeType":"S"},
            {"AttributeName":"GSI2SK","AttributeType":"S"},
            {"AttributeName":"GSI3PK","AttributeType":"S"},
            {"AttributeName":"GSI3SK","AttributeType":"S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName":"AuthorIndex",
                "KeySchema":[
                    {"AttributeName":"GSI1PK","KeyType":"HASH"},
                    {"AttributeName":"GSI1SK","KeyType":"RANGE"},
                ],
                # projecting all, item already has full paper details
                "Projection":{"ProjectionType":"ALL"}
            },
            {
                "IndexName":"PaperIdIndex",
                "KeySchema":[
                    {"AttributeName":"GSI2PK","KeyType":"HASH"},
                    {"AttributeName":"GSI2SK","KeyType":"RANGE"},
                ],
                "Projection":{"ProjectionType":"ALL"}
            },
            {
                "IndexName":"KeywordIndex",
                "KeySchema":[
                    {"AttributeName":"GSI3PK","KeyType":"HASH"},
                    {"AttributeName":"GSI3SK","KeyType":"RANGE"},
                ],
                "Projection":{"ProjectionType":"ALL"}
            },
        ]
    )

    # block til table becomes active
    waiter = client.get_waiter('table_exists')
    waiter.wait(TableName=table_name)
    print("Table is active")

    return resource.Table(table_name)

def load_papers_json(path):
    # loads papers from JSOn 
    # then return a list of dict
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # accepts {"papers":[...]} or [...]
    if isinstance(data, dict) and "papers" in data:
        return data["papers"]
    
    if isinstance(data, list):
        return data
    
    raise ValueError("Not supported papers.json format")


def iso_date_only(published_str):
    # normalize timestamp to YYYY-MM-DD string
    # If parsing fails, return top 10 characters -> best-effort date
    
    s = published_str.strip()
    if s.endswith("Z"):
        s = s[:-1]
    try:
        d = datetime.fromisoformat(s)
        return d.date().isoformat()
    
    except Exception:
        # take first 10 chars
        return s[:10]


def norm_author(name):
    # normalize author name (collapsing spaces/lowercase)
    return " ".join(str(name).split()).lower()

def extract_keywords(abstract, top_k=10):
    # get top-K keywords from abstract
    # steps: tokenize → lowercase → remove stopwords/short tokens → count → top_k
    
    if not abstract:
        return []
    tokens = [t.lower() for t in WORD_RE.findall(abstract)]
    tokens = [t for t in tokens if t not in STOPWORDS and len(t) >= 3]
    cnt = Counter(tokens)
    return [w for w,_ in cnt.most_common(top_k)]


def make_items_for_paper(p):
    # once gotten paper dict, builds the denormalized item set, returns (items, counts)
    #  items  -> dicts covering paper/category/author/keyword views
    #  counts ->  counter dict
    
    # pulls fields with defaults; tolerate to diff input shapes
    arxiv_id = str(p.get("arxiv_id") or p.get("id") or p.get("arxivId") or "").strip()
    title = p.get("title"," ").strip()
    authors = [a.strip() for a in (p.get("authors") or []) if a and str(a).strip()]
    abstract = p.get("abstract","")
    categories = [c.strip() for c in (p.get("categories") or []) if c and str(c).strip()]
    published_raw = p.get("published") or p.get("published_at") or p.get("date") or ""
    pub_date = iso_date_only(str(published_raw))

    keywords = extract_keywords(abstract, top_k=10)

    # common attributes shared
    common = {
        "arxiv_id": arxiv_id,
        "title": title,
        "authors": authors,
        "categories": categories,

        # original timestamp if present
        "published": p.get("published") or pub_date + "T00:00:00Z",
    }

    items = []
    counts = defaultdict(int)

    # paper item (addressable w GSI on paper-id)
    # PK/SK for direct GetItem (if know both), if not GSI2 
    paper_item = {
        "PK": f"PAPER#{arxiv_id}",
        "SK": "PAPER",
        "GSI2PK": f"PAPER#{arxiv_id}",
        "GSI2SK": pub_date,
        "abstract": abstract,
    }
    paper_item.update(common)
    items.append(paper_item); counts["paper_id"] += 1

    # category items (to enable browse by category and time range queries)
    for cat in categories:
        ci = {
            "PK": f"CATEGORY#{cat}",
            "SK": f"{pub_date}#{arxiv_id}",  # enable range scanz by date
        }
        ci.update(common)
        items.append(ci); counts["category"] += 1

    # author items/idx 
    for a in authors:
        na = norm_author(a)
        ai = {
            "PK": f"AUTHOR#{na}",
            "SK": f"{pub_date}#{arxiv_id}",
            "GSI1PK": f"AUTHOR#{na}",
            "GSI1SK": f"{pub_date}#{arxiv_id}",
        }
        ai.update(common)
        items.append(ai); counts["author"] += 1

    # keyword items/idx
    for kw in keywords:
        ki = {
            "PK": f"KEYWORD#{kw}",
            "SK": f"{pub_date}#{arxiv_id}",
            "GSI3PK": f"KEYWORD#{kw}",
            "GSI3SK": f"{pub_date}#{arxiv_id}",
        }

        # omitting the abstract to keep keyword items clean
        ki.update(common)
        items.append(ki); counts["keyword"] += 1

    return items, counts


def batch_put(table, items):
    # writing items in batches w automatic chunking/retries
    # makes the operation idempotent
    
    with table.batch_writer(overwrite_by_pkeys=['PK','SK']) as bw:
        for it in items:
            bw.put_item(Item=it)


def main():
    # parsing input
    papers_path, table_name, region = parse_args(sys.argv)

    # creating AWS clients/resources
    client = dyn_client(region)
    resource = dyn_resource(region)

    # ensuring table exists
    table = ensure_table(client, resource, table_name)

    print(f"loading papers from {papers_path}")
    papers = load_papers_json(papers_path)

    total_items = 0       # number of DynamoDB items written
    paper_count = 0       # number of input papers processed
    breakdown = defaultdict(int)  # count item type

    print(" xtracting key  words and denormalization ")
    start = time.time()
    buffer = []          # for batched writes

    for p in papers:

        # skipping entries that don't have any id shape
        if not (p.get("arxiv_id") or p.get("id") or p.get("arxivId")):
            continue
        items, counts = make_items_for_paper(p)
        buffer.extend(items)
        paper_count += 1
        for k, v in counts.items():
            breakdown[k] += v

        # flushing to keep memory bounded / start streaming writes
        if len(buffer) >= 1000:
            batch_put(table, buffer)
            total_items += len(buffer)
            buffer = []

    # flush
    if buffer:
        batch_put(table, buffer)
        total_items += len(buffer)

    elapsed = time.time() - start
    denom_factor = (total_items / paper_count) if paper_count else 0.0

    # statistics
    print(f"loaded {paper_count} papers")
    print(f"created denormalized {total_items} dynamoDB items")
    print(f"denormalization factor: {denom_factor:.1f}x\n")

    cat = breakdown.get("category", 0)
    auth = breakdown.get("author", 0)
    kw = breakdown.get("keyword", 0)
    pid = breakdown.get("paper_id", 0)

    print("storage breakdown:")
    print(f"  Category items: {cat} ({(cat/paper_count):.1f} per paper avg)" if paper_count else "  , Category items: 0")
    print(f"  Author items: {auth} ({(auth/paper_count):.1f} per paper avg)" if paper_count else "  , Author items: 0")
    print(f"  Keyword items: {kw} ({(kw/paper_count):.1f} per paper avg)" if paper_count else "  , Keyword items: 0")
    print(f"  Paper ID items: {pid} ({(pid/paper_count):.1f} per paper)" if paper_count else "  , Paper ID items: 0")
    print(f"\nTook: {int(elapsed*1000)} ms")


if __name__ == "__main__":
    main()