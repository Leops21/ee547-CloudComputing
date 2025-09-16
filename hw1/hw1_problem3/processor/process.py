import json
import os
import re
import time
from datetime import datetime, timezone

def strip_html(html_content):
    """Remove HTML tags and extract text."""
    html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    
    links = re.findall(r'href=[\'"]?([^\'" >]+)', html_content, flags=re.IGNORECASE)
    images = re.findall(r'src=[\'"]?([^\'" >]+)', html_content, flags=re.IGNORECASE)
    
    text = re.sub(r'<[^>]+>', ' ', html_content)
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text, links, images

def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Processor starting", flush=True)
    
    while not os.path.exists("/shared/status/fetch_complete.json"):
        print("Waiting for fetcher to finish...", flush=True)
        time.sleep(2)

    os.makedirs("/shared/processed", exist_ok=True)
    os.makedirs("/shared/status", exist_ok=True)
    
    results = []
    for filename in os.listdir("/shared/raw"):
        if filename.endswith(".html"):
            path = os.path.join("/shared/raw", filename)
            with open(path, 'r', encoding="utf-8", errors="ignore") as f:
                html = f.read()
            text, links, images = strip_html(html)
            
            words = text.split()
            sentences = re.split(r'[.!?]+', text)
            paragraphs = text.split("\n\n")
            
            data = {
                "source_file": filename,
                "text": text,
                "statistics": {
                    "word_count": len(words),
                    "sentence_count": len([s for s in sentences if s.strip()]),
                    "paragraph_count": len([p for p in paragraphs if p.strip()]),
                    "avg_word_length": sum(len(w) for w in words)/len(words) if words else 0
                },
                "links": links,
                "images": images,
                "processed_at": datetime.now(timezone.utc).isoformat()
            }
            
            out_path = os.path.join("/shared/processed", filename.replace(".html", ".json"))
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            results.append(out_path)

    status = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "files_processed": len(results),
        "results": results
    }
    with open("/shared/status/process_complete.json", "w") as f:
        json.dump(status, f, indent=2)
    
    print(f"[{datetime.now(timezone.utc).isoformat()}] Processor complete", flush=True)

if __name__ == "__main__":
    main()