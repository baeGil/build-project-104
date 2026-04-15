Tôi sẽ giải thích chi tiết quá trình searching trong hệ thống của bạn. Đây là một **Hybrid RAG (Retrieval-Augmented Generation)** pipeline rất tinh vi!


Perfect! Bây giờ tôi sẽ giải thích chi tiết toàn bộ quá trình searching:

---

## 🔍 **Complete Search Process - Step by Step**

### **Overview: Hybrid RAG Pipeline**

```
User Query
    ↓
Step 1: Query Planning (Strategy Selection)
    ↓
Step 2: Parallel Retrieval (BM25 + Dense)
    ↓
Step 3: Score Normalization & RRF Fusion
    ↓
Step 4: Sandwich Reordering
    ↓
Step 5: Context Enrichment (Neo4j Graph)
    ↓
Step 6: Reranking (Optional)
    ↓
Step 7: LLM Generation with Citations
```

---

## **Step 1: Query Planning** 📋

**Mục đích:** Phân tích query để chọn chiến lược search phù hợp

```python
# Query Planner determines strategy:
query_plan = QueryPlanner.plan(user_query)

# Examples:
"Điều 5 luật này nói gì?" → CITATION strategy (exact article lookup)
"Văn bản này đã bị sửa đổi chưa?" → NEGATION strategy
"Tìm quy định về bảo vệ dữ liệu" → SEMANTIC strategy (hybrid search)
```

**Các strategies:**
- `CITATION` - Tìm chính xác điều khoản được trích dẫn
- `NEGATION` - Tìm phủ định, ngoại lệ
- `SEMANTIC` - Standard hybrid retrieval (phổ biến nhất)

---

## **Step 2: Parallel Retrieval** ⚡

**Đây là phần quan trọng nhất!** Hệ thống chạy **2 searches song song** bằng `asyncio.gather`:

### **2a. BM25 Search (OpenSearch)** 🔎

```python
# What it does:
- Full-text search với BM25 algorithm
- Tìm keyword matching exact
- Ví dụ: "bảo vệ dữ liệu cá nhân" → tìm documents chứa exact phrases này

# OpenSearch Query:
{
  "query": {
    "multi_match": {
      "query": "bảo vệ dữ liệu cá nhân",
      "fields": ["title^3", "content"],  # title được weight gấp 3
      "type": "best_fields"
    }
  },
  "size": 100  # Lấy top 100 candidates
}

# Returns:
[("doc-77", 15.234), ("doc-45", 12.456), ("doc-23", 10.123), ...]
 # (doc_id, BM25_score)
```

**Ưu điểm:**
- ✅ Tìm exact keyword matches
- ✅ Tốt cho legal citations ("Điều 15", "Khoản 2")
- ✅ Fast (~50ms)

### **2b. Dense Semantic Search (Qdrant)** 🧠

```python
# What it does:
1. Convert query to vector embedding (768 dimensions)
   "bảo vệ dữ liệu cá nhân" → [0.123, -0.456, 0.789, ...]

2. Search Qdrant for similar vectors using cosine similarity

# Qdrant Search:
search_result = qdrant.search(
    collection_name="legal_docs",
    query_vector=[0.123, -0.456, ...],  # Query embedding
    limit=100  # Top 100 candidates
)

# Returns:
[("doc-77", 0.92), ("doc-89", 0.87), ("doc-12", 0.83), ...]
 # (doc_id, cosine_similarity_score)
```

**Ưu điểm:**
- ✅ Hiểu semantic meaning (không cần exact match)
- ✅ Tìm documents liên quan về mặt ngữ nghĩa
- ✅ Xử lý synonyms ("dữ liệu" = "thông tin")

### **Parallel Execution** 🚀

```python
# Chạy song song - không chờ nhau!
bm25_task = self._bm25_search(query, size=100)
dense_task = self._dense_search(query, limit=100)

# Wait for BOTH to complete
bm25_results, dense_results = await asyncio.gather(
    bm25_task, 
    dense_task,
    return_exceptions=True  # Nếu 1 cái fail, cái kia vẫn chạy
)

# Total time = max(BM25_time, Dense_time) ≈ 100ms
# Thay vì: BM25_time + Dense_time ≈ 150ms
```

---

## **Step 3: RRF Fusion** 🔀

**Problem:** Làm sao kết hợp BM25 scores (0-20) với Dense scores (0-1)?

**Solution: Reciprocal Rank Fusion (RRF)**

```python
# BM25 results (score range: 0-20)
bm25 = [("doc-77", 15.2), ("doc-45", 12.4), ("doc-23", 10.1)]
# Rank:        1st         2nd          3rd

# Dense results (score range: 0-1)
dense = [("doc-89", 0.92), ("doc-77", 0.87), ("doc-12", 0.83)]
# Rank:         1st          2nd           3rd

# RRF Formula: score(d) = Σ 1/(k + rank_i(d))
# k = 60 (constant)

# Calculate:
doc-77: 1/(60+1) + 1/(60+2) = 0.0164 + 0.0161 = 0.0325  ← Highest!
doc-45: 1/(60+2) = 0.0161
doc-89: 1/(60+1) = 0.0164
doc-23: 1/(60+3) = 0.0159
doc-12: 1/(60+3) = 0.0159

# Final ranking after RRF:
[("doc-77", 0.0325), ("doc-89", 0.0164), ("doc-45", 0.0161), ...]
```

**Why RRF is brilliant:**
- ✅ Không cần normalize scores trước
- ✅ Documents xuất hiện trong BOTH lists được rank cao
- ✅ Robust với score scales khác nhau

### **Score Normalization (Optional)** 📊

```python
# Raw RRF scores: [0.0325, 0.0164, 0.0161, ...]
# Normalize to 0-100 scale for better UX:
normalized = normalizer.normalize_rrf_scores(raw_scores)
# [85.2, 62.1, 58.7, ...]  ← Dễ hiểu hơn!
```

---

## **Step 4: Sandwich Reordering** 🥪

**Problem:** LLMs suffer from "lost-in-the-middle" - quên documents ở giữa context

**Solution:** Reorder documents để important ones ở đầu và cuối

```python
# Before (sorted by score):
[Doc1(95), Doc2(88), Doc3(82), Doc4(75), Doc5(70), Doc6(65)]

# Sandwich algorithm:
# 1. Split: Odd positions [1,3,5] + Even positions [2,4,6]
# 2. Reverse even positions
# 3. Concatenate

# After reordering:
[Doc1(95), Doc3(82), Doc5(70), Doc6(65), Doc4(75), Doc2(88)]
 ↑ High relevance      ↑ Low relevance       ↑ High relevance
 (LLM reads first)     (LLM may forget)      (LLM sees last)
```

**Why this works:**
- ✅ LLM attention mạnh nhất ở đầu và cuối
- ✅ Documents quan trọng nhất không bị "lost in the middle"
- ✅ Improves answer quality by 10-15%

---

## **Step 5: Context Enrichment (Neo4j)** 🔗

**Problem:** Retrieved documents có relationships mà chúng ta chưa khai thác!

```python
# For each retrieved document, query Neo4j:
for doc in retrieved_docs:
    # Find related documents
    related = neo4j.query("""
        MATCH (d:Document {id: $doc_id})-[:RELATES_TO*1..2]-(related)
        RETURN related.title, related.doc_type, count(*) as rel_count
    """, doc_id=doc.doc_id)
    
    # Add to document context
    doc.related_documents = related

# Example:
# User searches: "Luật doanh nghiệp 2020"
# Retrieved: Document A
# Neo4j finds: A → [B (amended by), C (references), D (based on)]
# Now LLM has A + B + C + D for complete context!
```

**Benefits:**
- ✅ Multi-hop reasoning (2 degrees of separation)
- ✅ Legal context expansion
- ✅ Citation chain discovery

---

## **Step 6: Reranking (Optional)** 🎯

**Khi nào dùng:** Khi cần độ chính xác cao hơn (ví dụ: citation queries)

```python
# Initial retrieval: 10 documents from hybrid search
# Reranker re-scores them with cross-encoder model

reranker = LegalReranker(model="cross-encoder-vietnamese")
reranked = await reranker.rerank(
    query="Quy định về thành lập công ty TNHH?",
    documents=retrieved_docs[:10]
)

# Reranker hiểu query-document relationship sâu hơn
# Có thể thay đổi ranking hoàn toàn!
```

---

## **Step 7: LLM Generation** 💬

**Final step:** Đưa retrieved documents vào prompt cho LLM

```python
# Build prompt with retrieved context
prompt = f"""
Dựa trên các văn bản pháp lý sau, hãy trả lời câu hỏi:

Câu hỏi: {user_query}

=== Document 1 (Score: 85.2) ===
Title: Luật Doanh nghiệp 2020
Content: {doc1.content[:2000]}
Metadata: {doc1.metadata}
Related: {doc1.related_documents}

=== Document 2 (Score: 78.5) ===
Title: Nghị định 01/2021/NĐ-CP
Content: {doc2.content[:2000]}
...

Hãy trả lời bằng tiếng Việt, trích dẫn cụ thể các điều khoản.
"""

# Call LLM (Groq, OpenAI, etc.)
response = await llm.generate(prompt)

# Parse citations from response
citations = extract_citations(response)
# ["Luật Doanh nghiệp 2020, Điều 12", "Nghị định 01/2021, Khoản 3"]
```

---

## 📊 **Complete Example: User Query Flow**

**User asks:** *"Quy định về vốn điều lệ khi thành lập công ty TNHH?"*

```
1. Query Planning
   → Strategy: SEMANTIC (hybrid search)

2. Parallel Retrieval
   → BM25 (OpenSearch, 80ms):
     [("doc-123", 14.2), ("doc-456", 11.8), ...]  # Exact: "vốn điều lệ"
   
   → Dense (Qdrant, 95ms):
     [("doc-789", 0.89), ("doc-123", 0.85), ...]  # Semantic: capital requirements

3. RRF Fusion (15ms)
   → doc-123: 1/(60+1) + 1/(60+2) = 0.0325  ← #1 (appears in both!)
   → doc-789: 1/(60+1) = 0.0164
   → doc-456: 1/(60+2) = 0.0161

4. Score Normalization (5ms)
   → [85.2, 62.1, 58.7, ...]

5. Fetch Full Documents (30ms)
   → Load content, metadata from PostgreSQL

6. Sandwich Reorder (2ms)
   → [85.2, 58.7, 45.3, 52.1, 62.1]  # Important at start/end

7. Neo4j Context Enrichment (50ms)
   → doc-123 relates to: [doc-100 (amended by), doc-200 (based on)]
   → Add 2 more documents to context

8. LLM Generation (3-5s)
   → Generate answer with citations

Total Retrieval Time: ~280ms (excluding LLM)
✅ Under 1s p95 target!
```

---

## 🎯 **Key Optimizations**

1. **Parallel BM25 + Dense** - Tiết kiệm 50% time
2. **RRF Fusion** - Không cần score normalization phức tạp
3. **Sandwich Reorder** - Combat LLM attention decay
4. **Neo4j Graph** - Multi-hop context expansion
5. **Score Normalization** - Better UX (0-100 scale)
6. **Adaptive Candidates** - Dynamically adjust based on query type

Đây là một trong những RAG systems tiên tiến nhất cho legal domain! 🚀