# 🧪 Quick Test Guide - Contract Review System

## 📦 Files Created

| File | Purpose |
|------|---------|
| `test contracts/quick_test_contract.txt` | Test contract (5 clauses, 63 lines) |
| `EXPECTED_QUICK_TEST.md` | Expected output with ground truth |
| `scripts/quick_test.py` | Automated test script with logging |
| `QUICK_TEST_GUIDE.md` | This guide |

---

## 🎯 Test Contract Overview

**Contract:** HD-TEST-2024-001 (Investment & Legal Consulting)
**Clauses:** 5 main clauses
**Expected findings:** 4-5

### **Risk Distribution:**
```
🔴 High Risk:    1 finding  (Điều 3 - Compensation limit)
🟡 Medium Risk:  2 findings (Điều 1 - Scope, Điều 2.3 - VAT)
🟢 Low Risk:     1 finding  (Điều 2 - Payment terms)
ℹ️ No Risk:      1 finding  (Điều 4 - Force majeure)
```

---

## 🚀 How to Run

### **Option 1: Automated Script (Recommended)**

```bash
# Navigate to project root
cd "/Users/AI/Vinuni/build project qoder"

# Run the test script
uv run python scripts/quick_test.py
```

**What it does:**
- ✅ Loads test contract
- ✅ Runs full pipeline (parse → retrieve → generate → verify)
- ✅ Logs all timing metrics
- ✅ Prints risk distribution
- ✅ Saves full JSON output to `test_output.json`
- ✅ Shows performance summary table

**Expected output:**
```
🚀 Quick Test - Contract Review Pipeline
📄 Loading contract: /path/to/quick_test_contract.txt
✅ Contract loaded: 2045 characters

🔧 Initializing pipeline...
✅ Pipeline initialized

🔍 Running contract review...

⏱️  parsing: 0.45s
⏱️  retrieval: 1.23s
⏱️  generation: 1.87s
⏱️  retrieval: 1.15s
⏱️  generation: 1.92s
...

================================================================================
📊 REVIEW RESULTS
================================================================================

📈 Risk Distribution
┌──────────────┬───────┬────────────┐
│ Risk Level   │ Count │ Percentage │
├──────────────┼───────┼────────────┤
│ HIGH         │   1   │   20.0%    │
│ MEDIUM       │   2   │   40.0%    │
│ LOW          │   1   │   20.0%    │
│ NONE         │   1   │   20.0%    │
└──────────────┴───────┴────────────┘

📝 Detailed Findings:

Finding 1: MEDIUM
  Clause: 1.1 Bên A đồng ý tư vấn cho Bên B về: a) Thủ tục đầu tư...
  Confidence: 75.0%
  Citations: 2
  Rationale: Phạm vi công việc bao gồm 3 lĩnh vực khác nhau...

...

💾 Full output saved to: test_output.json

================================================================================
⚡ Performance Metrics
┌────────────────────────┬──────────┬──────────┬────────┐
│ Metric                 │    Value │   Target │ Status │
├────────────────────────┼──────────┼──────────┼────────┤
│ Total Pipeline Time    │  12.34s  │   < 15s  │   ✅   │
│ Contract Parsing       │   0.45s  │    < 1s  │   ✅   │
│ Retrieval (avg/max)    │ 1.23s /  │ < 2s avg │   ✅   │
│ Generation (avg/max)   │ 1.87s /  │ < 2s avg │   ✅   │
│ Clauses Processed      │     5    │     5    │   ✅   │
│ Findings Generated     │     5    │   4-5    │   ✅   │
│ Errors                 │     0    │     0    │   ✅   │
└────────────────────────┴──────────┴──────────┴────────┘
================================================================================

📤 Next Steps:
1. Review the output in: test_output.json
2. Compare with expected output in: EXPECTED_QUICK_TEST.md
3. Send results back to AI assistant for analysis

✅ Test complete!
```

---

### **Option 2: Via Frontend (Manual)**

```bash
# 1. Start backend
uv run uvicorn apps.review_api.main:app --reload --host 0.0.0.0 --port 8000

# 2. Start frontend (in another terminal)
cd apps/web-app
npm run dev

# 3. Open browser
http://localhost:3000/review

# 4. Copy content from `test contracts/quick_test_contract.txt`
# 5. Paste into text area
# 6. Click "Rà soát Hợp đồng"
# 7. Wait for results
# 8. Open browser console (F12) to see logs
# 9. Take screenshot of results
```

---

### **Option 3: Via API (cURL)**

```bash
# Read contract
CONTRACT=$(cat "test contracts/quick_test_contract.txt")

# Send to API
curl -X POST http://localhost:8000/api/v1/review \
  -H "Content-Type: application/json" \
  -d "{
    \"contract_text\": $(echo "$CONTRACT" | jq -Rs .)
  }" \
  | tee test_output_api.json \
  | jq .
```

---

## 📊 What to Monitor

### **1. Performance Metrics**

| Metric | Target | Why It Matters |
|--------|--------|----------------|
| **Total Time** | < 15s | User experience |
| **Parsing** | < 1s | Contract complexity |
| **Retrieval (avg)** | < 2s/clause | Database performance |
| **Generation (avg)** | < 2s/clause | LLM latency |
| **Errors** | 0 | System reliability |

### **2. Quality Metrics**

| Metric | Target | How to Check |
|--------|--------|--------------|
| **Risk Level Accuracy** | 4/5 correct | Compare with EXPECTED_QUICK_TEST.md |
| **Citation Validity** | 80%+ valid | Click citations, check full text loads |
| **Vietnamese Quality** | 100% Vietnamese | No English text in findings |
| **Confidence Scores** | 70-95% range | Not all same, realistic values |

### **3. Critical Test Cases**

#### **Test Case 1: High Risk Detection** 🔴
```
Clause: ĐIỀU 3.3 (Compensation = contract value)
Expected: 
  ✅ Risk level = "high"
  ✅ Mentions excessive limit (300 million)
  ✅ Suggests 30% limit (90 million)
  ✅ Cites Bộ luật Dân sự 91/2015
  ✅ Confidence >= 90%
```

#### **Test Case 2: VAT Rate Issue** 🟡
```
Clause: ĐIỀU 2.3 (Fixed 10% VAT)
Expected:
  ✅ Risk level = "medium"
  ✅ Mentions VAT rate uncertainty (10% vs 8%)
  ✅ Suggests dynamic reference
```

#### **Test Case 3: Scope Ambiguity** 🟡
```
Clause: ĐIỀU 1.1 (3 services without appendix)
Expected:
  ✅ Risk level = "medium"
  ✅ Suggests adding detailed appendix
  ✅ Cites Luật Doanh nghiệp or Luật Đầu tư
```

---

## 📤 What to Send Back

After running the test, please provide:

### **1. Full JSON Output**
```bash
# File generated by quick_test.py
cat test_output.json
```

### **2. Performance Logs**
```bash
# Copy the performance table from console output
```

### **3. Screenshot**
```
Screenshot of frontend review results page
(If testing via frontend)
```

### **4. Completed Checklist**

```markdown
## Test Results

### Performance
- [ ] Total time < 15s (Actual: ___s)
- [ ] No connection errors
- [ ] All 5 clauses processed

### Finding 1: ĐIỀU 1 (Expected: MEDIUM)
- [ ] Risk level = "medium" (Actual: ___)
- [ ] Has citations (Actual: ___)
- [ ] Confidence 70-80% (Actual: ___%)

### Finding 2: ĐIỀU 2 (Expected: LOW)
- [ ] Risk level = "low" (Actual: ___)
- [ ] Mentions late payment penalties (Actual: ___)

### Finding 3: ĐIỀU 2.3 (Expected: MEDIUM)
- [ ] Risk level = "medium" (Actual: ___)
- [ ] Identifies VAT uncertainty (Actual: ___)

### Finding 4: ĐIỀU 3 (Expected: HIGH) ⭐
- [ ] Risk level = "high" (Actual: ___)
- [ ] Identifies excessive compensation (Actual: ___)
- [ ] Suggests 30% limit (Actual: ___)
- [ ] Cites Bộ luật Dân sự (Actual: ___)

### Finding 5: ĐIỀU 4 (Expected: LOW/NONE)
- [ ] Risk level = "low" or "none" (Actual: ___)
- [ ] Mentions court jurisdiction (Actual: ___)

### Overall
- [ ] Citations load correctly
- [ ] All Vietnamese text
- [ ] No generation errors
```

---

## 🎯 Success Criteria

**PASS (>= 80 points):**
- ✅ 4/5 risk levels correct
- ✅ 80%+ citations valid
- ✅ Total time < 15s
- ✅ 0 errors
- ✅ All critical test cases pass

**NEEDS IMPROVEMENT (60-79 points):**
- ⚠️ 3/5 risk levels correct
- ⚠️ 60-80% citations valid
- ⚠️ Total time 15-20s
- ⚠️ 1 error
- ⚠️ 1 critical test case fails

**FAIL (< 60 points):**
- ❌ < 3/5 risk levels correct
- ❌ < 60% citations valid
- ❌ Total time > 20s
- ❌ 2+ errors
- ❌ 2+ critical test cases fail

---

## 🔧 Troubleshooting

### **Problem: Connection Error**
```
Solution:
1. Check if Groq API is accessible:
   curl https://api.groq.com/openai/v1/chat/completions \
     -H "Authorization: Bearer YOUR_API_KEY"

2. Check backend logs:
   tail -f backend.log

3. Verify .env file has correct GROQ_API_KEY
```

### **Problem: No Citations Found**
```
Solution:
1. Check if database has data:
   uv run python scripts/check_db.py

2. Verify ingestion completed:
   SELECT COUNT(*) FROM legal_documents;

3. Check Neo4j:
   http://localhost:7474 → MATCH (n) RETURN COUNT(n)
```

### **Problem: Low Confidence Scores**
```
Solution:
1. Check if retrieval is finding relevant documents
2. Verify embeddings are correct
3. Check if prompt template is clear
```

---

## 📈 Expected Performance (Reference)

Based on similar systems:

```
┌────────────────────────────────────────────────────┐
│  BENCHMARK (5 clauses)                             │
├────────────────────────────────────────────────────┤
│  Total Time:          10-15 seconds                │
│  Parsing:             0.3-0.8 seconds              │
│  Retrieval (avg):     1.0-1.5 seconds/clause       │
│  Generation (avg):    1.5-2.0 seconds/clause       │
│  Total API calls:     5-6 (Groq)                   │
│  Memory usage:        ~500MB                       │
│  Database queries:    ~25-30                       │
└────────────────────────────────────────────────────┘
```

---

## 🚀 Ready to Test?

```bash
# 1. Make sure services are running
docker ps | grep -E "(postgres|qdrant|neo4j)"

# 2. Run the test
uv run python scripts/quick_test.py

# 3. Review results
cat test_output.json | jq .

# 4. Send results back to AI assistant
```

---

**Good luck! 🎯**

**Version:** 1.0
**Created:** 2026-04-16
**Author:** AI Assistant
