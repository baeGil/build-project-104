#  Expected Output & Performance Metrics - Quick Test Contract

## 🎯 Contract: HD-TEST-2024-001 (Investment & Legal Consulting)

**File:** `test contracts/quick_test_contract.txt`
**Clauses:** 5 main clauses
**Expected findings:** 4-5 findings (covering all risk levels)

---

## 📊 Expected Risk Distribution

```
🔴 High Risk:    1 finding  (20%)
🟡 Medium Risk:  2 findings (40%)
🟢 Low Risk:     1 finding  (20%)
ℹ️ No Risk:      1 finding  (20%)
```

---

## 🔍 Detailed Expected Findings

### **Finding 1: ĐIỀU 1 - Phạm vi công việc** 🟡 MEDIUM RISK

```json
{
  "clause_text": "1.1 Bên A đồng ý tư vấn cho Bên B về: a) Thủ tục đầu tư... b) Thành lập công ty con... c) Tư vấn nghĩa vụ thuế...",
  "risk_level": "medium",
  "verification": "partially_supported",
  "confidence": 75.0,
  "rationale": "Phạm vi công việc bao gồm 3 lĩnh vực khác nhau (đầu tư, doanh nghiệp, thuế) nhưng không có phụ lục chi tiết mô tả cụ thể từng công việc. Điều này có thể dẫn đến tranh chấp về sau nếu các bên không thống nhất về phạm vi thực tế.",
  "revision_suggestion": "Nên bổ sung Phụ lục 01 mô tả chi tiết từng công việc tư vấn, bao gồm: (1) Danh mục hồ sơ cần chuẩn bị, (2) Tiến độ cụ thể cho từng hạng mục, (3) Kết quả mong đợi, (4) Trách nhiệm của mỗi bên.",
  "negotiation_note": "Bên B nên yêu cầu Bên A cung cấp proposal chi tiết trước khi ký hợp đồng, hoặc thêm điều khoản: 'Phạm vi công việc chi tiết được quy định tại Phụ lục 01 kèm theo.'",
  "expected_citations": [
    {
      "law_id": "59/2020/QH14",
      "law_title": "Luật Doanh nghiệp số 59/2020/QH14",
      "article_id": "Article 4 or related",
      "topic": "Company establishment consulting"
    },
    {
      "law_id": "61/2020/QH14",
      "law_title": "Luật Đầu tư số 61/2020/QH14",
      "article_id": "Article 4 or related",
      "topic": "Investment procedures consulting"
    }
  ],
  "inline_citation_map": {
    "1": {
      "doc_id": "UUID-of-luat-doanh-nghiep",
      "title": "Luật Doanh nghiệp 59/2020/QH14",
      "content": "Trích dẫn liên quan đến thành lập doanh nghiệp",
      "metadata": {"law_id": "59/2020/QH14"}
    }
  }
}
```

**Ground Truth Check:**
- ✅ Risk level = "medium" (not high, not low)
- ✅ Citations reference Luật Doanh nghiệp 59/2020 and Luật Đầu tư 61/2020
- ✅ Rationale mentions missing detailed appendix
- ✅ Confidence around 75% (partially supported)

---

### **Finding 2: ĐIỀU 2 - Phí dịch vụ** 🟢 LOW RISK

```json
{
  "clause_text": "2.2 Thanh toán: - Đợt 1: 50% (150.000.000 VNĐ) trong 5 ngày làm việc... - Đợt 2: 50% còn lại... sau khi hoàn thành công việc",
  "risk_level": "low",
  "verification": "entailed",
  "confidence": 85.0,
  "rationale": "Phương thức thanh toán được chia thành 2 đợt hợp lý theo tiến độ công việc. Tuy nhiên, thiếu điều khoản xử lý khi Bên B thanh toán chậm (lãi suất, phạt chậm thanh toán) và không quy định rõ hậu quả nếu Bên B không thanh toán đợt 2.",
  "revision_suggestion": "Bổ sung: (1) Lãi suất chậm thanh toán: 10%/năm trên số tiền chậm trả; (2) Nếu Bên B chậm thanh toán quá 30 ngày, Bên A có quyền tạm dừng công việc; (3) Quy định rõ hóa đơn VAT sẽ được xuất khi nào.",
  "negotiation_note": "Bên B có thể đàm phán chia thành 3 đợt thanh toán (30%-40%-30%) để giảm rủi ro tài chính.",
  "expected_citations": [
    {
      "law_id": "91/2015/QH13",
      "law_title": "Bộ luật Dân sự số 91/2015/QH13",
      "article_id": "Article 357 or related",
      "topic": "Payment obligations and late payment interest"
    }
  ],
  "inline_citation_map": {}
}
```

**Ground Truth Check:**
- ✅ Risk level = "low" (payment terms are reasonable)
- ✅ Rationale mentions missing late payment penalties
- ✅ Suggests 10% annual interest rate for late payment
- ✅ Confidence around 85% (well-supported)

---

### **Finding 3: ĐIỀU 2.3 - Thuế GTGT** 🟡 MEDIUM RISK

```json
{
  "clause_text": "2.3 Phí chưa bao gồm thuế GTGT 10%",
  "risk_level": "medium",
  "verification": "contradicted",
  "confidence": 90.0,
  "rationale": "Thuế GTGT cho dịch vụ tư vấn pháp lý có thể áp dụng mức 10% hoặc 8% tùy theo thời điểm và chính sách giảm thuế của Chính phủ. Việc ghi cố định 10% có thể không chính xác nếu có thay đổi chính sách. Nên tham chiếu đến văn bản pháp luật hiện hành thay vì ghi cứng con số.",
  "revision_suggestion": "Sửa thành: 'Phí chưa bao gồm thuế GTGT theo quy định hiện hành của pháp luật về thuế giá trị gia tăng. Thuế suất áp dụng theo văn bản hướng dẫn của Bộ Tài chính tại thời điểm xuất hóa đơn.'",
  "negotiation_note": "Bên A nên chịu trách nhiệm về tính chính xác của thuế suất và cung cấp hóa đơn VAT hợp lệ theo quy định.",
  "expected_citations": [
    {
      "law_id": "various-VAT-laws",
      "law_title": "Luật Thuế giá trị gia tăng và các văn bản hướng dẫn",
      "article_id": "Relevant VAT articles",
      "topic": "VAT rate for legal consulting services"
    }
  ],
  "inline_citation_map": {}
}
```

**Ground Truth Check:**
- ✅ Risk level = "medium" (VAT rate can change)
- ✅ Rationale mentions 10% vs 8% VAT rate uncertainty
- ✅ Suggests dynamic reference to current law
- ✅ Confidence around 90% (clear contradiction to best practice)

---

### **Finding 4: ĐIỀU 3 - Trách nhiệm bồi thường** 🔴 HIGH RISK

```json
{
  "clause_text": "3.3 Mức bồi thường không vượt quá giá trị hợp đồng\n3.4 Bên B có quyền đơn phương chấm dứt hợp đồng nếu Bên A vi phạm nghiêm trọng",
  "risk_level": "high",
  "verification": "contradicted",
  "confidence": 92.0,
  "rationale": "Có 2 vấn đề nghiêm trọng: (1) Điều 3.3 giới hạn bồi thường 'không vượt quá giá trị hợp đồng' (300 triệu) - đây là mức quá cao, thông lệ thương mại thường giới hạn 20-30% giá trị hợp đồng; (2) Điều 3.4 cho phép Bên B đơn phương chấm dứt nhưng không quy định rõ 'vi phạm nghiêm trọng' là gì và không có thời hạn thông báo trước. Theo Bộ luật Dân sự, cần xác định cụ thể điều kiện chấm dứt.",
  "revision_suggestion": "Sửa 3.3: 'Mức bồi thường không vượt quá 30% giá trị hợp đồng (tối đa 90.000.000 VNĐ)'.\nSửa 3.4: 'Bên B có quyền đơn phương chấm dứt hợp đồng nếu Bên A vi phạm nghĩa vụ nghiêm trọng và không khắc phục trong 30 ngày kể từ ngày nhận được thông báo bằng văn bản.'",
  "negotiation_note": "🔴 Đây là điều khoản QUAN TRỌNG nhất cần đàm phán. Bên A sẽ phản đối việc giới hạn bồi thường thấp. Có thể thỏa hiệp ở mức 50% (150 triệu). Bên B nên yêu cầu thêm điều khoản bảo lãnh thực hiện hợp đồng.",
  "expected_citations": [
    {
      "law_id": "91/2015/QH13",
      "law_title": "Bộ luật Dân sự số 91/2015/QH13",
      "article_id": "Article 359 or related",
      "topic": "Damage compensation limits"
    },
    {
      "law_id": "91/2015/QH13",
      "law_title": "Bộ luật Dân sự số 91/2015/QH13",
      "article_id": "Article 420 or related",
      "topic": "Unilateral contract termination conditions"
    }
  ],
  "inline_citation_map": {
    "1": {
      "doc_id": "UUID-of-bo-luat-dan-su",
      "title": "Bộ luật Dân sự 91/2015/QH13",
      "content": "Trích dẫn về giới hạn bồi thường thiệt hại",
      "metadata": {"law_id": "91/2015/QH13"}
    }
  }
}
```

**Ground Truth Check:**
- ✅ Risk level = "high" (critical compensation clause)
- ✅ Identifies TWO issues: excessive limit + vague termination
- ✅ Suggests 30% limit (90 million VND)
- ✅ Cites Bộ luật Dân sự 91/2015
- ✅ Confidence >= 90% (clear legal issue)
- ⭐ This is the MOST IMPORTANT finding to detect

---

### **Finding 5: ĐIỀU 4 - Bất khả kháng & Tranh chấp** 🟢 LOW RISK or ℹ️ NO RISK

```json
{
  "clause_text": "4.1 Các sự kiện bất khả kháng: thiên tai, hỏa hoạn, chiến tranh, dịch bệnh\n4.2 Bên gặp sự kiện bất khả kháng phải thông báo trong vòng 30 ngày\n4.3 Tranh chấp được giải quyết qua thương lượng, nếu không sẽ kiện ra Tòa án",
  "risk_level": "low",
  "verification": "entailed",
  "confidence": 80.0,
  "rationale": "Điều khoản bất khả kháng và giải quyết tranh chấp khá đầy đủ. Tuy nhiên, có 2 điểm có thể cải thiện: (1) Thời hạn thông báo bất khả kháng 30 ngày là quá dài - thông lệ là 15 ngày; (2) Không quy định rõ Tòa án nào có thẩm quyền (TP.HCM hay Đà Nẵng?). Nên bổ sung cơ chế hòa giải thương mại trước khi kiện.",
  "revision_suggestion": "Sửa 4.2: '...phải thông báo bằng văn bản trong vòng 15 ngày...'\nThêm: 'Trước khi khởi kiện, các bên có nghĩa vụ tham gia hòa giải thương mại tại VCCI trong thời hạn 30 ngày. Tòa án có thẩm quyền là Tòa án nhân dân TP. Đà Nẵng.'",
  "negotiation_note": "Đây là điểm đàm phán quan trọng: Bên A có thể yêu cầu Tòa án TP.HCM, Bên B muốn Đà Nẵng. Có thể thỏa hiệp chọn Trọng tài thương mại (VIAC) thay vì Tòa án.",
  "expected_citations": [
    {
      "law_id": "91/2015/QH13",
      "law_title": "Bộ luật Dân sự số 91/2015/QH13",
      "article_id": "Article 156 or related",
      "topic": "Force majeure notification period"
    }
  ],
  "inline_citation_map": {}
}
```

**Ground Truth Check:**
- ✅ Risk level = "low" or "none" (reasonable clause)
- ✅ Mentions 30-day notice is too long (should be 15)
- ✅ Points out missing court jurisdiction
- ✅ Suggests arbitration as compromise
- ✅ Confidence around 80%

---

## ⚡ Performance Metrics to Log

### **Required Logs:**

```python
# 1. TOTAL PIPELINE TIME
total_time: float  # Target: < 15 seconds for 5 clauses

# 2. PARSING TIME
parsing_time: float  # Target: < 1 second

# 3. RETRIEVAL TIME (per clause)
retrieval_times: List[float]  # Target: < 2 seconds per clause
  - bm25_search_time: float
  - dense_search_time: float
  - neo4j_graph_time: float
  - reranking_time: float

# 4. LLM GENERATION TIME (per clause)
generation_times: List[float]  # Target: < 2 seconds per clause
  - groq_api_time: float
  - parsing_response_time: float

# 5. VERIFICATION TIME
verification_time: float  # Target: < 1 second

# 6. SUMMARY GENERATION TIME
summary_time: float  # Target: < 3 seconds

# 7. TOTAL API CALLS
total_groq_calls: int  # Expected: 5-6 (one per clause + summary)

# 8. ERROR COUNT
error_count: int  # Target: 0
```

### **Expected Performance:**

```
┌────────────────────────────────────────────────────┐
│  PERFORMANCE BENCHMARKS                            │
├────────────────────────────────────────────────────┤
│  Total Time:          < 15 seconds                 │
│  Parsing:             < 1 second                   │
│  Retrieval (avg):     < 2 seconds/clause           │
│  Generation (avg):    < 2 seconds/clause           │
│  Verification:        < 1 second                   │
│  Summary:             < 3 seconds                  │
│                                                    │
│  Total clauses:       5                            │
│  Total findings:      4-5                          │
│  Groq API calls:      5-6                          │
│  Errors:              0                            │
└────────────────────────────────────────────────────┘
```

---

## 📝 How to Test

### **Step 1: Run Contract Review**

```bash
# Option A: Via Frontend
1. Go to http://localhost:3000/review
2. Copy content from `test contracts/quick_test_contract.txt`
3. Paste into text area
4. Click "Rà soát Hợp đồng"
5. Open browser console (F12) to see logs
6. Wait for results

# Option B: Via API (with logging)
curl -X POST http://localhost:8000/api/v1/review \
  -H "Content-Type: application/json" \
  -d '{
    "contract_text": "..."
  }' \
  | tee review_output.json
```

### **Step 2: Capture Logs**

**Backend logs to check:**
```bash
# Watch backend logs in real-time
tail -f backend.log | grep -E "(retrieval|generation|verification|timing|duration)"
```

**Expected log format:**
```
[2026-04-16 10:30:01] INFO: Parsing contract: 5 clauses found
[2026-04-16 10:30:01] INFO: Parsing time: 0.5s
[2026-04-16 10:30:02] INFO: Retrieving for clause 1: BM25=0.3s, Dense=0.5s, Neo4j=0.2s, Rerank=0.4s, Total=1.4s
[2026-04-16 10:30:04] INFO: Generating finding 1: Groq=1.8s, Parse=0.1s, Total=1.9s
[2026-04-16 10:30:04] INFO: Verification: 0.3s
[2026-04-16 10:30:15] INFO: Total pipeline time: 14.2s
[2026-04-16 10:30:15] INFO: Summary generated in 2.5s
```

### **Step 3: Validate Output Against Expected**

**Create a checklist:**

```markdown
## Test Results - HD-TEST-2024-001

### Performance
- [ ] Total time < 15s (Actual: ___s)
- [ ] No connection errors
- [ ] No generation failures
- [ ] All 5 clauses processed

### Finding 1: ĐIỀU 1 (Expected: MEDIUM)
- [ ] Risk level = "medium" (Actual: ___)
- [ ] Has citations to Luật Doanh nghiệp / Luật Đầu tư (Actual: ___)
- [ ] Confidence 70-80% (Actual: ___%)
- [ ] Has revision suggestion (Actual: ___)

### Finding 2: ĐIỀU 2 (Expected: LOW)
- [ ] Risk level = "low" (Actual: ___)
- [ ] Mentions missing late payment penalties (Actual: ___)
- [ ] Confidence 80-90% (Actual: ___%)

### Finding 3: ĐIỀU 2.3 VAT (Expected: MEDIUM)
- [ ] Risk level = "medium" (Actual: ___)
- [ ] Identifies VAT rate uncertainty (Actual: ___)
- [ ] Confidence >= 85% (Actual: ___%)

### Finding 4: ĐIỀU 3 Compensation (Expected: HIGH) ⭐ CRITICAL
- [ ] Risk level = "high" (Actual: ___)
- [ ] Identifies excessive compensation limit (Actual: ___)
- [ ] Identifies vague termination clause (Actual: ___)
- [ ] Suggests 30% limit (Actual: ___)
- [ ] Cites Bộ luật Dân sự (Actual: ___)
- [ ] Confidence >= 90% (Actual: ___%)

### Finding 5: ĐIỀU 4 Force Majeure (Expected: LOW/NONE)
- [ ] Risk level = "low" or "none" (Actual: ___)
- [ ] Mentions 30-day notice too long (Actual: ___)
- [ ] Points out missing court jurisdiction (Actual: ___)

### Citations
- [ ] All findings have valid citations
- [ ] Citations reference correct laws
- [ ] Full text loads correctly in CitationPanel
- [ ] No "No Reference" badges

### Language Quality
- [ ] All output in Vietnamese
- [ ] Legal terminology accurate
- [ ] No English text in findings
- [ ] Professional tone
```

---

## 🎯 Critical Test Cases (Must Pass)

### **Test Case 1: High Risk Detection** 🔴
```
Clause: ĐIỀU 3.3 (Compensation limit = contract value)
Expected: HIGH RISK finding
Must detect:
  ✅ Excessive compensation limit (300 million)
  ✅ Should suggest 30% limit (90 million)
  ✅ Cites Bộ luật Dân sự
  ✅ Confidence >= 90%
```

### **Test Case 2: Medium Risk - Scope Ambiguity** 🟡
```
Clause: ĐIỀU 1.1 (3 consulting areas without appendix)
Expected: MEDIUM RISK finding
Must detect:
  ✅ Multiple service areas without detail
  ✅ Suggests adding appendix
  ✅ Cites Luật Doanh nghiệp or Luật Đầu tư
```

### **Test Case 3: VAT Rate Uncertainty** 🟡
```
Clause: ĐIỀU 2.3 (Fixed 10% VAT)
Expected: MEDIUM RISK finding
Must detect:
  ✅ VAT rate can change (10% vs 8%)
  ✅ Suggests dynamic reference to law
```

### **Test Case 4: Citation Quality** ✅
```
All findings
Must have:
  ✅ At least 80% findings have citations
  ✅ Citations reference laws from database
  ✅ Full text loads in < 3 seconds
  ✅ No "undefined" or "null" values
```

---

## 📊 Scoring Rubric

| Criteria | Weight | Pass Criteria | Actual | Score |
|----------|--------|---------------|--------|-------|
| **Risk Level Accuracy** | 30% | 4/5 findings correct | __/5 | __/30 |
| **Citation Quality** | 25% | 80%+ valid citations | __% | __/25 |
| **Performance** | 15% | < 15s total time | __s | __/15 |
| **Vietnamese Quality** | 15% | No English, proper terms | Yes/No | __/15 |
| **Error-Free** | 15% | 0 errors | __ errors | __/15 |
| **TOTAL** | 100% | | | **__/100** |

**Pass/Fail:**
- ✅ **PASS**: >= 80 points AND all critical test cases pass
- ⚠️ **NEEDS IMPROVEMENT**: 60-79 points OR 1 critical test case fails
- ❌ **FAIL**: < 60 points OR 2+ critical test cases fail

---

## 📤 What to Send Back

Please provide:

1. **Full JSON output** from the review API
2. **Backend logs** (timing, errors, API calls)
3. **Frontend console logs** (if any errors)
4. **Screenshot** of the review results page
5. **Completed checklist** above

I will then:
- ✅ Compare actual vs expected output
- 🐛 Identify any bugs or issues
- 📊 Calculate performance metrics
- 🎯 Suggest improvements
- 🔧 Fix any problems found

---

**Test Contract File:** `test contracts/quick_test_contract.txt`
**Expected Output File:** `EXPECTED_QUICK_TEST.md` (this file)
**Test Date:** ___________
**Tester:** ___________
**Result:** PASS / NEEDS IMPROVEMENT / FAIL

---

**Version:** 1.0
**Created:** 2026-04-16
**Purpose:** Quick validation test for contract review system
