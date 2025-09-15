import sys
import os
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import time
import re
import json
from collections import Counter, defaultdict
import urllib.parse


"""
ArXiv Paper Metadata Processor
Fetches paper metadata from the ArXiv API
"""

ARXIV_API_URL = "http://export.arxiv.org/api/query"

STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
    'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
    'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it',
    'we', 'they', 'what', 'which', 'who', 'when', 'where', 'why', 'how',
    'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some',
    'such', 'as', 'also', 'very', 'too', 'only', 'so', 'than', 'not'
}


def log(message, output_dir):
    # log message with timestamp
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{ts}] {message}\n"
    log_path = os.path.join(output_dir, "processing.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def fetch_arxiv_data(query, max_results, output_dir):
    # fetches XML from ArXiv API with retry on 429
    query_encoded = urllib.parse.quote(query)  # pase query
    url = f"{ARXIV_API_URL}?search_query={query_encoded}&start=0&max_results={max_results}"

    attempts = 0
    while attempts < 3:
        try:
            with urllib.request.urlopen(url) as response:
                if response.status == 429:
                    log("rate limit hit, waiting 3 seconds ...", output_dir)
                    time.sleep(3)
                    attempts += 1
                    continue
                return response.read()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                log("HTTP 429 received, retrying ...", output_dir)
                time.sleep(3)
                attempts += 1
                continue
            log(f"HTTP error: {e}", output_dir)
            sys.exit(1)
        except urllib.error.URLError as e:
            log(f"Network error: {e}", output_dir)
            sys.exit(1)

    log("Failed after 3 attempts dueto rate limit", output_dir)
    sys.exit(1)


def parse_arxiv_xml(xml_data, output_dir):
    # parses XML and extracts metadata for each paper
    papers = []
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as e:
        log(f"Invalid XML from API: {e}", output_dir)
        return papers

    ns = {"atom": "http://www.w3.org/2005/Atom"}

    for entry in root.findall("atom:entry", ns):
        try:
            arxiv_id = entry.find("atom:id", ns).text.split("/")[-1]
            title = entry.find("atom:title", ns).text.strip()
            authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
            abstract = entry.find("atom:summary", ns).text.strip()
            categories = [c.attrib["term"] for c in entry.findall("atom:category", ns)]
            published = entry.find("atom:published", ns).text
            updated = entry.find("atom:updated", ns).text

            if not (arxiv_id and title and authors and abstract):
                raise ValueError("Missing required field")

            abstract_stats = analyze_abstract(abstract)

            paper = {
                "arxiv_id": arxiv_id,
                "title": title,
                "authors": authors,
                "abstract": abstract,
                "categories": categories,
                "published": published,
                "updated": updated,
                "abstract_stats": {
                    "total_words": abstract_stats["total_words"],
                    "unique_words": abstract_stats["unique_words"],
                    "total_sentences": abstract_stats["total_sentences"],
                    "avg_words_per_sentence": abstract_stats["avg_words_per_sentence"],
                    "avg_word_length": abstract_stats["avg_word_length"],
                },
            }
            papers.append((paper, abstract_stats))
            log(f"Processing paper: {arxiv_id}", output_dir)

        except Exception as e:
            log(f"Skipping paper due to missing/invalid field: {e}", output_dir)
            continue

    return papers


def analyze_abstract(text):
    # word/sentence statistics from abstract
    words = re.findall(r"\b[\w\-]+\b", text)
    words_lower = [w.lower() for w in words]

    words_no_stop = [w for w in words_lower if w not in STOPWORDS]

    total_words = len(words)
    unique_words = len(set(words_lower))

    freq = Counter(words_no_stop)
    top_20 = freq.most_common(20)

    avg_word_length = sum(len(w) for w in words) / total_words if total_words else 0

    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    total_sentences = len(sentences)

    if total_sentences > 0:
        words_per_sentence = [len(re.findall(r"\b[\w\-]+\b", s)) for s in sentences]
        avg_words_per_sentence = sum(words_per_sentence) / total_sentences
        longest_sentence = max(words_per_sentence)
        shortest_sentence = min(words_per_sentence)
    else:
        avg_words_per_sentence = 0
        longest_sentence = 0
        shortest_sentence = 0

    uppercase_terms = [w for w in words if any(c.isupper() for c in w)]
    numeric_terms = [w for w in words if any(c.isdigit() for c in w)]
    hyphenated_terms = [w for w in words if "-" in w]

    return {
        "total_words": total_words,
        "unique_words": unique_words,
        "top_20_words": top_20,
        "avg_word_length": avg_word_length,
        "total_sentences": total_sentences,
        "avg_words_per_sentence": avg_words_per_sentence,
        "longest_sentence_words": longest_sentence,
        "shortest_sentence_words": shortest_sentence,
        "technical_terms": {
            "uppercase_terms": uppercase_terms,
            "numeric_terms": numeric_terms,
            "hyphenated_terms": hyphenated_terms,
        },
    }


def aggregate_analysis(query, papers, output_dir):
    # creates analysis across all papers
    total_abstracts = len(papers)
    total_words = sum(p[1]["total_words"] for p in papers)
    all_words = []
    category_distribution = defaultdict(int)
    uppercase_terms, numeric_terms, hyphenated_terms = set(), set(), set()

    longest_abs = 0
    shortest_abs = float("inf")

    for p, stats in papers:
        all_words.extend([w.lower() for w in re.findall(r"\b[\w\-]+\b", p["abstract"])])
        for cat in p["categories"]:
            category_distribution[cat] += 1

        longest_abs = max(longest_abs, stats["total_words"])
        shortest_abs = min(shortest_abs, stats["total_words"])

        uppercase_terms.update(stats["technical_terms"]["uppercase_terms"])
        numeric_terms.update(stats["technical_terms"]["numeric_terms"])
        hyphenated_terms.update(stats["technical_terms"]["hyphenated_terms"])

    unique_words_global = len(set(all_words))
    avg_abstract_length = total_words / total_abstracts if total_abstracts else 0

    freq_global = Counter([w for w in all_words if w not in STOPWORDS])
    top_50 = [
        {
            "word": w,
            "frequency": c,
            "documents": sum(
                1 for _, s in papers
                if w in [x.lower() for x in re.findall(r"\b[\w\-]+\b", _["abstract"])]
            )
        }
        for w, c in freq_global.most_common(50)
    ]

    stats = {
        "query": query,
        "papers_processed": total_abstracts,
        "processing_timestamp": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total_abstracts": total_abstracts,
            "total_words": total_words,
            "unique_words_global": unique_words_global,
            "avg_abstract_length": avg_abstract_length,
            "longest_abstract_words": longest_abs,
            "shortest_abstract_words": (shortest_abs if shortest_abs != float("inf") else 0),
        },
        "top_50_words": top_50,
        "technical_terms": {
            "uppercase_terms": sorted(list(uppercase_terms)),
            "numeric_terms": sorted(list(numeric_terms)),
            "hyphenated_terms": sorted(list(hyphenated_terms)),
        },
        "category_distribution": dict(category_distribution),
    }

    out_path = os.path.join(output_dir, "analysis.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


def write_papers_output(papers, output_dir):
    # writes papers.json with metadata and abstract stats
    papers_only = [p for p, _ in papers]
    out_path = os.path.join(output_dir, "papers.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(papers_only, f, indent=2, ensure_ascii=False)


def main():
    if len(sys.argv) != 4:
        sys.exit(1)

    query = sys.argv[1]
    try:
        max_results = int(sys.argv[2])
        if not (1 <= max_results <= 100):
            raise ValueError
    except ValueError:
        print("Error: max_results must be an integer between 1 and 100")
        sys.exit(1)

    output_dir = sys.argv[3]
    os.makedirs(output_dir, exist_ok=True)

    log(f"Starting ArXiv query: {query}", output_dir)

    start_time = time.time()
    xml_data = fetch_arxiv_data(query, max_results, output_dir)
    papers = parse_arxiv_xml(xml_data, output_dir)

    elapsed = time.time() - start_time
    log(f"Completed processing: {len(papers)} papers in {elapsed:.2f} seconds", output_dir)

    if not papers:
        log("No valid papers processed. Exiting.", output_dir)
        sys.exit(0)

    # outputs
    write_papers_output(papers, output_dir)
    aggregate_analysis(query, papers, output_dir)

    print(f"Generated papers.json and analysis.json in {output_dir}")


if __name__ == "__main__":
    main()
