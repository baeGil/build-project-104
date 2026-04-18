#!/usr/bin/env python3
"""Test API and show detailed timing from server logs."""

import requests
import time
import subprocess
import re

API_URL = "http://localhost:8000/api/v1/chat/legal"

query = "Điều kiện chấm dứt hợp đồng thuê văn phòng"

print("\n" + "="*70)
print("🔍 TESTING API WITH DETAILED TIMING")
print("="*70 + "\n")

print(f"Query: {query}\n")

# Make request
start = time.time()
response = requests.post(
    API_URL,
    json={"query": query},
    timeout=30
)
client_latency = (time.time() - start) * 1000

print(f"Client-side latency: {client_latency:.0f}ms")
print(f"Response status: {response.status_code}\n")

if response.status_code == 200:
    data = response.json()
    print(f"Answer length: {len(data.get('answer', ''))} characters")
    print(f"Confidence: {data.get('confidence', 0):.1f}%")
    print(f"Citations: {len(data.get('citations', []))}\n")

# Get server logs
print("="*70)
print("📊 SERVER-SIDE TIMING (from logs)")
print("="*70 + "\n")

try:
    # Read the last 50 lines of server output
    result = subprocess.run(
        ['tail', '-50', '/tmp/uvicorn_server.log'],
        capture_output=True,
        text=True
    )
    
    # Find timing logs
    for line in result.stdout.split('\n'):
        if '[CHAT]' in line:
            # Parse and display
            if 'TOTAL:' in line:
                print(f"\n{line.split('[CHAT] ')[-1]}")
            elif 'Step' in line:
                print(f"  {line.split('[CHAT] ')[-1]}")
except Exception as e:
    print(f"Could not read logs: {e}")
    print("Check server terminal for timing details\n")

print("\n" + "="*70)
