import sys
import os
import json
import time
import datetime
import re
import urllib.request
import urllib.error
from collections import defaultdict

# --- functions ---

def current_datestamp():
    # returns current UTC time with Z suffix
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def word_count(text):
    # counts words in a text
    return len(re.findall(r"\w+", text))

# --- logic ---

def main():
    if len(sys.argv) != 3:
        sys.stderr.write("Usage: python fetch_and_process.py <input_file> <output_dir>\n")
        sys.exit(1)

    input_file = sys.argv[1]
    output_dir = sys.argv[2]

    if not os.path.exists(input_file):
        sys.stderr.write(f"Input file not found: {input_file}\n")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    responses = []
    status_distribution = defaultdict(int)
    total_bytes = 0
    total_time = 0.0
    success_count = 0
    fail_count = 0

    errors_path = os.path.join(output_dir, "errors.log")
    responses_path = os.path.join(output_dir, "responses.json")
    summary_path = os.path.join(output_dir, "summary.json")

    start_time = current_datestamp()

    with open(input_file, "r") as f, open(errors_path, "w") as err_log:
        urls = [line.strip() for line in f if line.strip()]

        for url in urls:
            entry = {
                "url": url,
                "status_code": None,
                "response_time_ms": None,
                "content_length": None,
                "word_count": None,
                "timestamp": current_datestamp(),
                "error": None,
            }

            try:
                req = urllib.request.Request(url, method="GET")
                start = time.time()
                with urllib.request.urlopen(req, timeout=10) as resp:
                    end = time.time()

                    entry["status_code"] = resp.getcode()
                    elapsed_ms = (end - start) * 1000
                    entry["response_time_ms"] = round(elapsed_ms, 2)

                    body = resp.read()
                    entry["content_length"] = len(body)

                    # content type
                    content_type = resp.headers.get("Content-Type", "")
                    if "text" in content_type.lower():
                        try:
                            decoded = body.decode("utf-8", errors="ignore")
                            entry["word_count"] = word_count(decoded)
                        except Exception as e:
                            entry["word_count"] = None

                    # aggregate stats
                    success_count += 1
                    total_bytes += entry["content_length"]
                    total_time += entry["response_time_ms"]
                    status_distribution[str(entry["status_code"])] += 1

            except Exception as e:
                entry["error"] = str(e)
                fail_count += 1
                err_log.write(f"{url} - {str(e)}\n")

            responses.append(entry)

    end_time = current_datestamp()

    # write responses.json
    with open(responses_path, "w") as f:
        json.dump(responses, f, indent=2)

    # write summary.json
    summary = {
        "total_urls": len(urls),
        "successful_requests": success_count,
        "failed_requests": fail_count,
        "average_response_time_ms": round(total_time / success_count, 2) if success_count > 0 else None,
        "total_bytes_downloaded": total_bytes,
        "status_code_distribution": dict(status_distribution),
        "processing_start": start_time,
        "processing_end": end_time,
    }

    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()