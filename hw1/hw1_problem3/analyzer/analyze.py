import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations

def jaccard_similarity(doc1_words, doc2_words):
    set1 = set(doc1_words)
    set2 = set(doc2_words)
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    return len(intersection) / len(union) if union else 0.0

def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Analyzer starting", flush=True)
    
    while not os.path.exists("/shared/status/process_complete.json"):
        print("Waiting for processor to finish...", flush=True)
        time.sleep(2)
    
    os.makedirs("/shared/analysis", exist_ok=True)
    os.makedirs("/shared/status", exist_ok=True)

    docs = {}
    all_words = []
    for filename in os.listdir("/shared/processed"):
        if filename.endswith(".json"):
            with open(os.path.join("/shared/processed", filename)) as f:
                data = json.load(f)
                words = data["text"].split()
                docs[filename] = words
                all_words.extend(words)
    
    counter = Counter(all_words)
    top_100 = [{"word": w, "count": c, "frequency": c/len(all_words)} for w, c in counter.most_common(100)]
    
    sims = []
    for (f1, w1), (f2, w2) in combinations(docs.items(), 2):
        sims.append({"doc1": f1, "doc2": f2, "similarity": jaccard_similarity(w1, w2)})
    
    bigrams = Counter(zip(all_words, all_words[1:]))
    trigrams = Counter(zip(all_words, all_words[1:], all_words[2:]))
    
    sentences = sum(len(re.split(r'[.!?]+', " ".join(w))) for w in docs.values())
    avg_sentence_length = len(all_words)/sentences if sentences else 0
    
    report = {
        "processing_timestamp": datetime.now(timezone.utc).isoformat(),
        "documents_processed": len(docs),
        "total_words": len(all_words),
        "unique_words": len(set(all_words)),
        "top_100_words": top_100,
        "document_similarity": sims,
        "top_bigrams": [{"bigram": " ".join(bg), "count": c} for bg, c in bigrams.most_common(20)],
        "readability": {
            "avg_sentence_length": avg_sentence_length,
            "avg_word_length": sum(len(w) for w in all_words)/len(all_words) if all_words else 0,
            "complexity_score": avg_sentence_length * (sum(len(w) for w in all_words)/len(all_words) if all_words else 0)
        }
    }
    
    with open("/shared/analysis/final_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"[{datetime.now(timezone.utc).isoformat()}] Analyzer complete", flush=True)

if __name__ == "__main__":
    main()