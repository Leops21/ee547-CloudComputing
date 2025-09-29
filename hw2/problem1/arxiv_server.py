#!/usr/bin/env python3
import sys
import os
import json
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "sample_data")

# load data
try:
    with open(os.path.join(DATA_DIR, "papers.json"), "r", encoding="utf-8") as f:
        PAPERS = json.load(f)
except FileNotFoundError:
    PAPERS = []

try:
    with open(os.path.join(DATA_DIR, "corpus_analysis.json"), "r", encoding="utf-8") as f:
        CORPUS_STATS = json.load(f)
except FileNotFoundError:
    CORPUS_STATS = {}

# index papers by id
PAPER_INDEX = {p["arxiv_id"]: p for p in PAPERS}


def log_request(method, path, code, extra=""):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{ts}] {method} {path} - {code} {extra}"
    print(msg)


class ArxivHandler(BaseHTTPRequestHandler):
    def _set_headers(self, code=200, content_type="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.end_headers()

    def _send_json(self, obj, code=200):
        self._set_headers(code)
        self.wfile.write(json.dumps(obj, indent=2).encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        try:
            #  get /papers
            if path == "/papers":
                papers_summary = [
                    {
                        "arxiv_id": p["arxiv_id"],
                        "title": p["title"],
                        "authors": p["authors"],
                        "categories": p.get("categories", []),
                    }
                    for p in PAPERS
                ]
                self._send_json(papers_summary, 200)
                log_request("GET", path, 200, f"({len(papers_summary)} results)")
                return

            # get /papers/{id}
            if path.startswith("/papers/"):
                paper_id = path.split("/")[-1]
                if paper_id in PAPER_INDEX:
                    self._send_json(PAPER_INDEX[paper_id], 200)
                    log_request("GET", path, 200)
                else:
                    self._send_json({"error": "Paper not found"}, 404)
                    log_request("GET", path, 404)
                return

            # get /search?q
            if path == "/search":
                if "q" not in query or not query["q"][0].strip():
                    self._send_json({"error": "Missing or empty query"}, 400)
                    log_request("GET", path, 400)
                    return

                terms = [t.lower() for t in re.findall(r"\w+", query["q"][0])]
                results = []
                for p in PAPERS:
                    score = 0
                    matches_in = []
                    title = p["title"].lower()
                    abstract = p["abstract"].lower()

                    for t in terms:
                        if t in title:
                            score += title.count(t)
                            if "title" not in matches_in:
                                matches_in.append("title")
                        if t in abstract:
                            score += abstract.count(t)
                            if "abstract" not in matches_in:
                                matches_in.append("abstract")

                    if score > 0:
                        results.append({
                            "arxiv_id": p["arxiv_id"],
                            "title": p["title"],
                            "match_score": score,
                            "matches_in": matches_in,
                        })

                resp = {"query": " ".join(terms), "results": results}
                self._send_json(resp, 200)
                log_request("GET", f"{path}?q={query['q'][0]}", 200, f"({len(results)} matches)")
                return

            # get /stats
            if path == "/stats":
                if not CORPUS_STATS:
                    self._send_json({"error": "Corpus stats are not available"}, 500)
                    log_request("GET", path, 500)
                    return
                self._send_json(CORPUS_STATS, 200)
                log_request("GET", path, 200)
                return

            # unknown endpoint
            self._send_json({"error": "Endpoint not found"}, 404)
            log_request("GET", path, 404)

        except Exception as e:
            self._send_json({"error": str(e)}, 500)
            log_request("GET", path, 500, f"({e})")


def main():
    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Error: port must be an integer")
            sys.exit(1)

    server = HTTPServer(("0.0.0.0", port), ArxivHandler)
    print(f"Starting ArXiv API server on port {port}")
    print("Endpoints:")
    print("  get /papers")
    print("  get /papers/{arxiv_id}")
    print("  get /search?q={query}")
    print("  get /stats")
    server.serve_forever()


if __name__ == "__main__":
    main()