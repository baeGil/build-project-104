#!/usr/bin/env python3
"""Test API latency via HTTP requests."""

import requests
import time
import json

API_URL = "http://localhost:8000/api/v1/chat/legal"

queries = [
    "Điều kiện chấm dứt hợp đồng thuê văn phòng",
    "Quy định về bồi thường thiệt hại",
    "Thủ tục đăng ký kinh doanh",
]

print("\n" + "="*70)
print("🔍 TESTING API LATENCY (via HTTP)")
print("="*70 + "\n")

for i, query in enumerate(queries, 1):
    print(f"[{i}/3] Query: {query}")
    
    start = time.time()
    response = requests.post(
        API_URL,
        json={"query": query},
        timeout=30
    )
    latency = (time.time() - start) * 1000
    
    if response.status_code == 200:
        data = response.json()
        answer_len = len(data.get("answer", ""))
        confidence = data.get("confidence", 0)
        
        print(f"     ✓ {latency:.0f}ms | Answer: {answer_len} chars | Confidence: {confidence:.1f}%\n")
    else:
        print(f"     ❌ {latency:.0f}ms | Error: {response.status_code}\n")

print("="*70)
print("✅ Test complete")
print("="*70 + "\n")
