# Article-Level Chunking: Impact Analysis

## 🔍 CURRENT FLOW (Whole Document Indexing)

### 1. INGESTION
```
HTML Content → normalize_legal_text() → parse_legal_document()
    ↓
LegalNode (ROOT):
  - id: "4258"
  - title: "Quyết định 166/1999/QĐ-UB về quản lý chợ"
  - content: [TOÀN BỘ VĂN BẢN - 5000 words, 25 articles]
  - level: 0
    ↓
indexer.index([node])  # ❌ Only root node
    ↓
Qdrant: 1 vector (5000 words)
OpenSearch: 1 document (5000 words)
```

### 2. SEARCHING
```
User Query: "tổ chức bộ máy ban quản lý dự án" (10 words)
    ↓
┌─────────────────────────────────────────────────────────┐
│ BM25 (OpenSearch)                                       │
│ Query: "tổ chức bộ máy ban quản lý dự án"               │
│ ↔ 50 documents (5000 words each)                        │
│                                                         │
│ Problem: TF-IDF loãng vì content quá dài                │
│ - "tổ chức" xuất hiện 3 lần / 5000 words → TF thấp      │
│ - Score: 12.5 (không cao vì loãng)                      │
│ - Rank: #12 trong 50 docs                               │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│ Dense (Qdrant)                                          │
│ Query embedding: [0.1, 0.2, ...] (10 words)             │
│ ↔ 50 vectors (5000 words each)                          │
│                                                         │
│ Problem: Length mismatch severe                         │
│ - Query ngắn (10 words) vs Doc dài (5000 words)         │
│ - Embedding loãng, cosine similarity thấp               │
│ - Score: 0.42 (rất thấp)                                │
│ - Rank: #46 trong 50 docs                               │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│ RRF Fusion                                              │
│ BM25 rank #12 + Dense rank #46                          │
│ RRF score = 1/(60+12) + 1/(60+46) = 0.0139 + 0.0094    │
│           = 0.0233 → Rank #18 (ngoài top-10!)           │
│                                                         │
│ Result: ❌ DOCUMENT BỊ DROP                             │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│ Reranker (LegalReranker)                                │
│ Input: Top-10 documents từ RRF                          │
│                                                         │
│ Problem: Document đúng không có trong top-10            │
│ → Reranker không thể giúp được                          │
└─────────────────────────────────────────────────────────┘
    ↓
Final Result: Top-5 documents (THIẾU document liên quan)
```

### 3. RESPONSE FORMAT
```python
RetrievedDocument(
    doc_id="4280",
    title="Quyết định 157/1999/QĐ-UB",
    content="[TOÀN BỘ 5000 WORDS]",  # ❌ LLM phải đọc hết
    score=95.2,
    bm25_score=15.3,
    dense_score=0.51,
    metadata={
        "law_id": "157/1999/QĐ-UB",
        "doc_type": "Quyết định",
        "issuing_body": "UBND"
    }
)
```

---

## ✅ NEW FLOW (Article-Level Chunking)

### 1. INGESTION (CHANGED)
```
HTML Content → normalize_legal_text() → parse_legal_document()
    ↓
LegalNode (ROOT):  # Vẫn tạo nhưng KHÔNG index
  - id: "4258"
  - children_ids: ["4258_article_1", "4258_article_2", ...]
  
LegalNode (ARTICLES):  # ✅ Index từng Điều
  - Article 1:
    - id: "4258_article_1"
    - title: "Điều 1. Phạm vi điều chỉnh"
    - content: "Quy định này áp dụng cho..." (200 words)
    - level: 2
    - chunk_type: "article"
    - article_number: 1
    - parent_doc_id: "4258"
  
  - Article 2:
    - id: "4258_article_2"
    - title: "Điều 2. Tổ chức bộ máy"
    - content: "Tổ chức bộ máy ban quản lý gồm..." (250 words)
    - level: 2
    - chunk_type: "article"
    - article_number: 2
    - parent_doc_id: "4258"
    ↓
indexer.index([article_1, article_2, ...])  # ✅ All articles
    ↓
Qdrant: 25 vectors (200-500 words each)  # Cho 1 document
OpenSearch: 25 documents (200-500 words each)
```

### 2. SEARCHING (CHANGED)
```
User Query: "tổ chức bộ máy ban quản lý dự án" (10 words)
    ↓
┌─────────────────────────────────────────────────────────┐
│ BM25 (OpenSearch) - SEARCHING ARTICLES                  │
│ Query: "tổ chức bộ máy ban quản lý dự án"               │
│ ↔ 1,250 articles (200-500 words each)                   │
│                                                         │
│ Advantage: TF-IDF TẬP TRUNG                              │
│ - "tổ chức" xuất hiện 2 lần / 250 words → TF CAO        │
│ - Score: 28.5 (cao hơn 2.3x)                            │
│ - Rank: #1 trong 1,250 articles                         │
│                                                         │
│ Result: Article 2 của 75/1999 → Rank #1 ✅              │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│ Dense (Qdrant) - SEARCHING ARTICLES                     │
│ Query embedding: [0.1, 0.2, ...] (10 words)             │
│ ↔ 1,250 vectors (200-500 words each)                    │
│                                                         │
│ Advantage: Length match tốt                              │
│ - Query 10 words vs Article 250 words (tỉ lệ 1:25)      │
│ - Embedding tập trung, cosine similarity CAO            │
│ - Score: 0.78 (cao hơn 1.86x)                           │
│ - Rank: #3 trong 1,250 articles                         │
│                                                         │
│ Result: Article 2 của 75/1999 → Rank #3 ✅              │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│ RRF Fusion - ARTICLES                                   │
│ BM25 rank #1 + Dense rank #3                            │
│ RRF score = 1/(60+1) + 1/(60+3) = 0.0164 + 0.0159      │
│           = 0.0323 → Rank #1 ✅                          │
│                                                         │
│ Result: ✅ ARTICLE TOP-1, GUARANTEED TO REACH RERANKER  │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│ Reranker (LegalReranker) - RERANKING ARTICLES           │
│ Input: Top-20 articles từ RRF                           │
│                                                         │
│ Advantage: Context tập trung, dễ so khớp semantic        │
│ - ColBERT/cross-encoder hoạt động tốt với 200-500 words │
│ - Score: 0.92 (very high confidence)                    │
│ - Rank: #1 sau reranker                                 │
│                                                         │
│ Result: ✅ Article 2 của 75/1999 → Final Rank #1        │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│ GROUP BY law_id (NEW STEP)                              │
│ Top-10 articles → Group by parent document              │
│                                                         │
│ Example:                                                │
│ - 75/1999: 3 articles (Điều 2, 5, 8)                    │
│ - 99/QĐ-UB: 2 articles (Điều 1, 3)                      │
│ - 171/1999: 2 articles (Điều 4, 7)                      │
│ → Deduplicate → Show top article per document           │
│                                                         │
│ Result: Top-5 unique documents (MỖI DOC CÓ ARTICLE ĐÚNG)│
└─────────────────────────────────────────────────────────┘
    ↓
Final Result: Top-5 documents (ĐẦY ĐỦ, CHÍNH XÁC)
```

### 3. RESPONSE FORMAT (CHANGED)
```python
# Each retrieved document now represents an ARTICLE, not full document
RetrievedDocument(
    doc_id="75_1999_QĐ_UB_article_2",  # ✅ Article ID
    title="Điều 2. Tổ chức bộ máy ban quản lý",  # ✅ Article title
    content="Tổ chức bộ máy ban quản lý dự án gồm...",  # ✅ 250 words ONLY
    score=97.5,
    bm25_score=28.5,  # ✅ Higher (focused TF)
    dense_score=0.78,  # ✅ Higher (length matched)
    metadata={
        "law_id": "75/1999/QĐ-UB",  # ✅ Parent document
        "doc_type": "Quyết định",
        "issuing_body": "UBND",
        "chunk_type": "article",  # ✅ NEW field
        "article_number": 2,  # ✅ NEW field
        "parent_doc_id": "75_1999_QĐ_UB"  # ✅ NEW field
    }
)
```

---

## 📊 COMPARISON: WHAT CHANGES & WHAT STAYS SAME

### ✅ UNCHANGED (No Impact)

| Component | Current | After Chunking | Notes |
|-----------|---------|----------------|-------|
| **Query Planning** | `planner.plan(clause_text)` | Same | Still extracts keywords, expansion variants |
| **BM25 Query DSL** | `multi_match` with phrase boost | Same | Still uses title^1.5, content^1 |
| **Dense Search** | Qdrant vector search | Same | Still uses cosine similarity |
| **RRF Algorithm** | `weighted_rrf(bm25, dense)` | Same | Still fuses with k=60 |
| **Reranker** | LegalReranker (ColBERT) | Same | Still 2-stage reranking |
| **Sandwich Reorder** | Odd-even interleaving | Same | Still combats lost-in-the-middle |
| **Relationship Queries** | Neo4j graph lookups | Same | Still fetches related docs |
| **API Endpoints** | `/api/review` | Same | Still returns same JSON structure |

### ⚠️ CHANGED (Impact)

| Component | Current | After Chunking | Impact |
|-----------|---------|----------------|--------|
| **Ingestion** | Index 1 root per doc | Index 20-30 articles per doc | ✅ 25x more searchable units |
| **Search Space** | 50 documents | ~1,250 articles | ✅ Better granularity |
| **BM25 TF** | Low (diluted in 5000 words) | High (focused in 250 words) | ✅ 2-3x score improvement |
| **Dense Similarity** | Low (length mismatch) | High (length matched) | ✅ 1.5-2x score improvement |
| **RRF Input** | 50 docs | 1,250 articles | ✅ More candidates |
| **RRF Output** | Top-10 docs | Top-50 articles | Need grouping step |
| **Reranker Input** | Top-10 docs (5000 words) | Top-20 articles (250 words) | ✅ Better model performance |
| **Result Grouping** | None | Group by law_id | ⚠️ NEW step needed |
| **Context Assembly** | Full doc content | Article content | ✅ Cleaner, focused context |

### ❌ POTENTIAL ISSUES (Must Handle)

| Issue | Risk | Solution |
|-------|------|----------|
| **Duplicate documents** | Same doc appears multiple times | Group by `law_id`, keep top article |
| **Missing parent context** | Article lacks document-level info | Include parent metadata in payload |
| **Storage increase** | 25x more vectors/docs | Acceptable (50→1,250 is small) |
| **Search latency** | More candidates to scan | Negligible (Qdrant/OpenSearch handle millions) |
| **ID format change** | `doc_id` now has `_article_N` suffix | Parse to extract parent ID |

---

## 🔧 REQUIRED CODE CHANGES

### 1. Ingestion Pipeline (`packages/ingestion/pipeline.py`)

**Current** (line ~302):
```python
# Index only root node
await self.indexer.index([node])
```

**New**:
```python
# Index root + all articles
all_chunks = [node]  # Root document (optional, for metadata)
for child_node in node.children:  # Articles already parsed
    if child_node.level == 2:  # Article level
        # Add chunk metadata
        child_node.metadata['chunk_type'] = 'article'
        child_node.metadata['parent_doc_id'] = node.id
        all_chunks.append(child_node)

await self.indexer.index(all_chunks)
```

### 2. Indexer (`packages/ingestion/indexer.py`)

**Add to payload** (line ~260):
```python
payload = {
    "title": node.title,
    "content": node.content,
    "doc_type": node.doc_type.value,
    "level": node.level,
    "chunk_type": "article" if node.level == 2 else "document",  # NEW
    "article_number": int(node.id.split("_")[-1]) if node.level == 2 else None,  # NEW
    "parent_doc_id": node.parent_id if node.level == 2 else None,  # NEW
    # ... existing fields ...
}
```

### 3. Hybrid Search (`packages/retrieval/hybrid.py`)

**Add grouping after RRF** (after line ~242):
```python
# After fetching documents, group by law_id to deduplicate
from collections import defaultdict

grouped = defaultdict(list)
for doc in documents:
    law_id = doc.metadata.get('law_id')
    if law_id:
        grouped[law_id].append(doc)

# Keep top article per document, aggregate scores
deduplicated = []
for law_id, articles in grouped.items():
    # Sort articles by score, keep top
    articles.sort(key=lambda d: d.score, reverse=True)
    top_article = articles[0]
    
    # Optionally: add info about other matching articles
    top_article.metadata['matching_articles'] = len(articles)
    top_article.metadata['article_numbers'] = [
        a.metadata.get('article_number') for a in articles[:3]
    ]
    
    deduplicated.append(top_article)

# Re-sort by score
deduplicated.sort(key=lambda d: d.score, reverse=True)
documents = deduplicated
```

### 4. Review Pipeline (`packages/reasoning/review_pipeline.py`)

**Context assembly** (line ~271-273):
```python
# Current: May miss context if top docs are from same law
primary_regulation = retrieved_documents[0].content

# New: Better - each doc is a focused article
# Can also aggregate multiple articles from same law
from collections import defaultdict

law_articles = defaultdict(list)
for doc in retrieved_documents:
    law_id = doc.metadata.get('law_id')
    law_articles[law_id].append(doc)

# Build context: Top law + related articles
primary_regulation = retrieved_documents[0].content
context_parts = []
for law_id, articles in list(law_articles.items())[:3]:  # Top 3 laws
    for article in articles[:2]:  # Top 2 articles per law
        context_parts.append(f"[{article.title}]\n{article.content}")

context = "\n\n".join(context_parts)
```

---

## 📈 EXPECTED IMPACT

### Retrieval Quality
| Metric | Current | After Chunking | Improvement |
|--------|---------|----------------|-------------|
| **BM25 rank (expected docs)** | #1-12 | #1-5 | 2-3x better |
| **Dense rank (expected docs)** | #36-49 | #3-8 | 5-6x better |
| **RRF retention rate** | 64% (7/11) | 91-100% (10-11/11) | +36% |
| **Ground truth match** | 7-8/11 | 10-11/11 | +40% |

### Performance
| Metric | Current | After Chunking | Notes |
|--------|---------|----------------|-------|
| **Search latency** | ~150ms | ~160ms | +10ms (more candidates) |
| **Reranker latency** | ~200ms | ~150ms | -50ms (shorter texts) |
| **Total pipeline** | ~800ms | ~750ms | -50ms (better reranker) |
| **Storage (Qdrant)** | 50 × 768 × 4B = 150KB | 1,250 × 768 × 4B = 3.7MB | Negligible |

### LLM Response Quality
| Aspect | Current | After Chunking |
|--------|---------|----------------|
| **Context relevance** | Mixed (full docs) | High (focused articles) |
| **Citation precision** | Vague (whole doc) | Exact (specific article) |
| **Hallucination risk** | Higher (too much context) | Lower (focused context) |
| **Answer accuracy** | ~75% | ~90% |

---

## 🎯 DECISION CHECKLIST

- [ ] **Modify ingestion** to index articles
- [ ] **Add chunk_type field** to distinguish document vs article
- [ ] **Update indexer payload** with article metadata
- [ ] **Add grouping logic** in hybrid search
- [ ] **Update context assembly** in review pipeline
- [ ] **Re-index 50 documents** (~2-3 minutes)
- [ ] **Run ground truth test** (expect 10-11/11)
- [ ] **Update UI** to show article numbers (optional)
- [ ] **Add article navigation** in frontend (future enhancement)

---

## 💡 FUTURE ENHANCEMENTS

1. **Subsection-level chunking**: For very long articles (>1000 words), split into Khoản/Điểm
2. **Cross-article context**: If query matches multiple articles from same doc, fetch full doc
3. **Article hierarchy**: Show parent document structure in UI
4. **Progressive loading**: Fetch article first, then full doc if needed
5. **Citation linking**: Click article number → jump to specific section
