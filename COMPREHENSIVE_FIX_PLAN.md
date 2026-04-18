# 🔧 Comprehensive Fix Implementation Plan

**Date:** 2026-04-16
**Status:** Partially Complete

---

## ✅ COMPLETED FIXES

### **Fix 1: Add law_id Field & Extraction** ✅

**Files Modified:**
1. `/packages/common/types.py` - Added `law_id` field to LegalNode
2. `/packages/ingestion/parser.py` - Added law_id extraction logic
3. `/packages/ingestion/indexer.py` - Added law_id to Qdrant payload

**Implementation:**
```python
# In parser.py - extract law_id from document_number
law_id_pattern = re.compile(r'(\d{2}/\d{4}/[A-Z]{2}\d{1,2})')
law_id_match = law_id_pattern.search(metadata["document_number"])
if law_id_match:
    metadata["law_id"] = law_id_match.group(1)
```

**What it does:**
- Extracts pattern like "61/2020/QH14" from "SỐ 61/2020/QH14"
- Adds law_id to all LegalNode instances
- Stores law_id in Qdrant vector database

**Remaining Work:**
- ❌ Update OpenSearch indexer (indexer.py line ~520)
- ❌ Update PostgreSQL storage (pipeline.py)
- ❌ Update citation API to use law_id instead of "unknown"
- ❌ Re-ingest existing documents to populate law_id

---

## 🔄 IN PROGRESS

### **Fix 2: Parallel Clause Processing** 🔄

**Problem:** Sequential processing causes 36s latency per clause
**Solution:** Process clauses concurrently with asyncio.gather()

**File to Modify:** `/packages/reasoning/review_pipeline.py`

**Current Implementation (Sequential):**
```python
findings = []
for clause_index, clause_text in clauses:
    finding = await self._review_single_clause(clause_index, clause_text)
    findings.append(finding)
```

**New Implementation (Parallel):**
```python
# Process all clauses concurrently
tasks = [
    self._review_single_clause(clause_index, clause_text)
    for clause_index, clause_text in clauses
]
findings = await asyncio.gather(*tasks, return_exceptions=True)

# Handle any exceptions
for i, finding in enumerate(findings):
    if isinstance(finding, Exception):
        logger.error(f"Clause {i} failed: {finding}")
        findings[i] = self._create_error_finding(clauses[i][1], finding)
```

**Expected Impact:**
- Latency: 36s → 3-5s per clause (10x improvement)
- Total time: 147s → 15-20s for 5 clauses

---

## 📋 PENDING FIXES

### **Fix 3: Improve Retrieval Relevance** 📋

**Problems:**
1. Citations from 1989 for Luật Đầu tư 2020
2. Irrelevant documents (vận chuyển hàng siêu trường for payment terms)
3. law_id = "unknown" in all citations

**Solutions:**

**A. Add Recency Filter:**
```python
# In hybrid.py - filter old documents
def _filter_by_recency(documents: list, min_year: int = 2015) -> list:
    filtered = []
    for doc in documents:
        publish_date = doc.metadata.get("publish_date")
        if publish_date:
            year = publish_date.year if hasattr(publish_date, 'year') else int(str(publish_date)[:4])
            if year >= min_year:
                filtered.append(doc)
        else:
            filtered.append(doc)  # Keep if no date
    return filtered
```

**B. Add Legal Domain Matching:**
```python
# Boost documents from same legal domain
def _boost_by_domain(query: str, documents: list) -> list:
    # Extract legal domains from query
    domains = extract_legal_domains(query)
    
    for doc in documents:
        law_id = doc.metadata.get("law_id", "")
        if any(domain in law_id for domain in domains):
            doc.score *= 1.5  # Boost score
    
    return sorted(documents, key=lambda x: x.score, reverse=True)
```

**C. Fix Citation law_id:**
```python
# In citations API or citation building logic
def build_citation(node: LegalNode) -> Citation:
    return Citation(
        article_id=node.id,
        law_id=node.law_id or "unknown",  # Use law_id from node
        quote=node.content[:500],
        document_title=node.title,
    )
```

---

### **Fix 4: Risk Level Validation** 📋

**Problem:** Wrong risk levels (Payment=Medium should be Low, Compensation=Medium should be High)

**Solution: Add Post-Processing Validation**

```python
# In generator.py or review_pipeline.py
def validate_risk_level(finding: ReviewFinding) -> ReviewFinding:
    """Apply business rules to validate/correct risk levels."""
    
    clause_text = finding.clause_text.lower()
    
    # Rule 1: Compensation limit = full contract value → HIGH
    if "bồi thường" in clause_text and "không vượt quá giá trị hợp đồng" in clause_text:
        if finding.risk_level != RiskLevel.HIGH:
            logger.warning(f"Correcting risk level to HIGH for compensation clause")
            finding.risk_level = RiskLevel.HIGH
            finding.confidence = max(finding.confidence, 90.0)
    
    # Rule 2: Standard payment terms → LOW
    elif "thanh toán" in clause_text and "đợt" in clause_text:
        if "chậm thanh toán" not in clause_text:  # No late payment penalty mentioned
            if finding.risk_level == RiskLevel.MEDIUM:
                finding.risk_level = RiskLevel.LOW
    
    # Rule 3: VAT rate mentioned without legal basis → MEDIUM
    elif "thuế GTGT" in clause_text or "VAT" in clause_text:
        if finding.risk_level == RiskLevel.LOW:
            finding.risk_level = RiskLevel.MEDIUM
    
    return finding
```

---

### **Fix 5: Improve Metadata Extraction** 📋

**Problem:** 8+ null fields (issuing_body, publish_date, effective_date, document_number)

**Solution: Enhanced Parser with Better Regex**

```python
# In parser.py - Better issuing body extraction
ISSUING_BODY_PATTERNS = [
    re.compile(r"(?:Bộ|Uỷ ban|Cơ quan)\s+([^,\n]+)", re.IGNORECASE),
    re.compile(r"(Căn cứ\s+)?(Luật|Nghị định|Thông tư).*?của\s+([^,\n]+)", re.IGNORECASE),
]

# Better date extraction
DATE_PATTERNS = [
    re.compile(r"ban\s+hành\s+ngày\s+(\d{1,2})[/-](\d{1,2})[/-](\d{4})"),
    re.compile(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})"),
    re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})"),
]
```

---

## 🎯 IMPLEMENTATION PRIORITY

### **Phase 1: Critical (Do Now)**
1. ✅ Add law_id field - DONE
2. 🔄 Implement parallel processing - IN PROGRESS
3. ⏳ Update OpenSearch & PostgreSQL storage
4. ⏳ Re-ingest documents with law_id

### **Phase 2: High Impact (This Week)**
5. ⏳ Add recency filter to retrieval
6. ⏳ Fix citation law_id population
7. ⏳ Add risk level validation rules

### **Phase 3: Quality Improvements (Next Week)**
8. ⏳ Improve metadata extraction
9. ⏳ Add domain-specific boosting
10. ⏳ Fine-tune LLM prompts

---

## 📊 Expected Results After All Fixes

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **law_id populated** | 0% | 95%+ | +95% |
| **Avg latency** | 36.8s | 3-5s | -87% |
| **Total pipeline time** | 147s | 15-20s | -87% |
| **Risk level accuracy** | 50% | 90%+ | +40% |
| **Citation relevance** | 30% | 85%+ | +55% |
| **Metadata completeness** | 60% | 95%+ | +35% |

---

##  NEXT STEPS

1. **Complete parallel processing implementation** (30 min)
2. **Update remaining storage backends** (20 min)
3. **Create re-ingestion script** (15 min)
4. **Test with quick_test.py** (10 min)
5. **Validate all fixes** (15 min)

**Total Time:** ~90 minutes

---

**Created:** 2026-04-16
**Status:** 20% Complete (1/5 critical fixes done)
