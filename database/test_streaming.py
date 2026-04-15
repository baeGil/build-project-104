"""Quick test: Load just 3 documents from HuggingFace without downloading entire parquet."""

import sys
sys.path.insert(0, "/Users/AI/Vinuni/build project qoder")

from datasets import load_dataset

print("Testing streaming load with take()...")

# Try using .take() to limit streaming
content_ds = load_dataset(
    "th1nhng0/vietnamese-legal-documents",
    name="content",
    split="data",
    streaming=True,
)

print("\nTaking first 3 items...")
count = 0
for item in content_ds.take(3):
    count += 1
    doc_id = item.get("id", "")
    content_length = len(item.get("content_html", ""))
    print(f"  Doc {count}: ID={doc_id}, Content length={content_length}")

print(f"\nSuccess! Loaded {count} documents without downloading entire file")
