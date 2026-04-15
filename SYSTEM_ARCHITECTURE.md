# Tài liệu Kiến trúc Hệ thống - Vietnamese Legal Contract Review AI

**Tài liệu này mô tả chi tiết kiến trúc hệ thống RAG (Retrieval-Augmented Generation) để rà soát hợp đồng pháp luật Việt Nam.**

---

## 1. Tổng quan hệ thống (System Overview)

### 1.1 Mục đích

Hệ thống cung cấp khả năng **rà soát hợp đồng tự động** dựa trên kho văn bản pháp luật Việt Nam, sử dụng kiến trúc RAG (Retrieval-Augmented Generation) kết hợp với đồ thị tri thức pháp lý (Legal Knowledge Graph).

### 1.2 Sơ đồ kiến trúc tổng quan

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           CLIENT LAYER (Frontend)                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Web App   │  │   Chat UI   │  │ Ingest UI   │  │    Progress Tracking    │ │
│  │  (Next.js)  │  │   (SSE)     │  │   (React)   │  │       (WebSocket)       │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────────────────────────┘ │
└─────────┼────────────────┼────────────────┼─────────────────────────────────────┘
          │                │                │
          └────────────────┴────────────────┘
                           │
                           ▼ HTTP/REST + SSE
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        API LAYER (FastAPI + Uvicorn)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Review    │  │    Chat     │  │   Ingest    │  │    Graph/Citations      │ │
│  │  Endpoints  │  │  Endpoints  │  │  Endpoints  │  │      Endpoints          │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────────────────────────┘ │
│         │                │                │                                      │
│  ┌──────┴────────────────┴────────────────┴──────────────────────────────────┐  │
│  │                         Middleware Layer                                    │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐  │  │
│  │  │    CORS     │  │   Timing    │  │ Prometheus  │  │  Error Handling   │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      REASONING LAYER (Core Business Logic)                      │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                      ContractReviewPipeline                              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │   │
│  │  │   Clause    │  │    Query    │  │   Hybrid    │  │   Two-Stage     │ │   │
│  │  │  Extraction │──│   Planner   │──│  Retriever  │──│   Verifier      │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘ │   │
│  │         │                                                      │         │   │
│  │         └──────────────────────────────────────────────────────┘         │   │
│  │                              │                                           │   │
│  │                              ▼                                           │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │                    EvidencePack Pattern                          │    │   │
│  │  │  (Generator NEVER searches - only consumes pre-assembled evidence)│    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  │                              │                                           │   │
│  │                              ▼                                           │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │                    LegalGenerator (Groq LLM)                     │    │   │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │    │   │
│  │  │  │   Finding   │  │    Chat     │  │       Summary           │  │    │   │
│  │  │  │  Generation │  │   Answer    │  │      Generation         │  │    │   │
│  │  │  └─────────────┘  └─────────────┘  └─────────────────────────┘  │    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                      QueryPlanner (LegalQueryPlanner)                    │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │   │
│  │  │  Normalize  │  │   Expand    │  │   Detect    │  │   Extract       │ │   │
│  │  │   (NFC)     │──│Abbreviations│──│  Negation   │──│  Citations      │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      RETRIEVAL LAYER (Hybrid Search)                            │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    HybridSearchEngine                                    │   │
│  │                                                                          │   │
│  │   ┌─────────────────┐         ┌─────────────────┐                       │   │
│  │   │   BM25 Search   │         │   Dense Search  │                       │   │
│  │   │  (OpenSearch)   │◄───────►│    (Qdrant)     │                       │   │
│  │   │                 │  async  │                 │                       │   │
│  │   │  - Full-text    │ parallel│  - Vector       │                       │   │
│  │   │  - BM25 ranking │         │  - Cosine sim   │                       │   │
│  │   └────────┬────────┘         └────────┬────────┘                       │   │
│  │            │                           │                                 │   │
│  │            └─────────────┬─────────────┘                                 │   │
│  │                          ▼                                               │   │
│  │            ┌─────────────────────────┐                                   │   │
│  │            │    RRF Fusion (k=60)    │                                   │   │
│  │            │  score = Σ 1/(k+rank)   │                                   │   │
│  │            └────────────┬────────────┘                                   │   │
│  │                         ▼                                                │   │
│  │            ┌─────────────────────────┐                                   │   │
│  │            │   Score Normalization   │                                   │   │
│  │            │   (Adaptive Centering)  │                                   │   │
│  │            └────────────┬────────────┘                                   │   │
│  │                         ▼                                                │   │
│  │            ┌─────────────────────────┐                                   │   │
│  │            │   Sandwich Reordering   │                                   │   │
│  │            │ (Lost-in-the-middle fix)│                                   │   │
│  │            └────────────┬────────────┘                                   │   │
│  │                         ▼                                                │   │
│  │            ┌─────────────────────────┐                                   │   │
│  │            │   ContextInjector       │                                   │   │
│  │            │  - PostgreSQL (primary) │                                   │   │
│  │            │  - Neo4j (secondary)    │                                   │   │
│  │            └─────────────────────────┘                                   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                      Reranker (Two-Stage)                                │   │
│  │  ┌─────────────────────────┐  ┌─────────────────────────────────────────┐ │   │
│  │  │   Stage 1: Position-    │  │  Stage 2: ColBERT/Cross-Encoder         │ │   │
│  │  │        Decay            │  │        (Optional)                       │ │   │
│  │  └─────────────────────────┘  └─────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      DATA LAYER (Multi-Backend Storage)                         │
│                                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌───────────┐  │
│  │    Qdrant       │  │   OpenSearch    │  │   PostgreSQL    │  │   Neo4j   │  │
│  │  (Vector DB)    │  │  (Full-text)    │  │   (Metadata)    │  │  (Graph)  │  │
│  │                 │  │                 │  │                 │  │           │  │
│  │  - 768-dim      │  │  - BM25 index   │  │  - legal_docs   │  │  - Nodes: │  │
│  │  - Cosine       │  │  - Multi-match  │  │  - relationships│  │    Doc    │  │
│  │  - Payloads     │  │  - Filters      │  │  - JSONB meta   │  │    Article│  │
│  │                 │  │                 │  │                 │  │  - Edges: │  │
│  │                 │  │                 │  │                 │  │  CONTAINS │  │
│  │                 │  │                 │  │                 │  │  CITES    │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └───────────┘  │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                      Redis (Configured but NOT Integrated)               │   │
│  │     Container running but no code uses it - in-memory caches used instead│   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      INGESTION PIPELINE (4 Phases)                              │
│                                                                                 │
│  Phase 1: Download          Phase 2: Process           Phase 3: Document        │
│  ┌─────────────┐            ┌─────────────┐            ┌─────────────┐          │
│  │ HuggingFace │───────────►│   Polars    │───────────►│  PostgreSQL │          │
│  │   Dataset   │            │    Merge    │            │   (Store)   │          │
│  │   (Cache)   │            │ HTML Clean  │            └──────┬──────┘          │
│  └─────────────┘            │ ID Cast     │                   │                 │
│                             └─────────────┘                   ▼                 │
│                                                    ┌─────────────────────┐      │
│                                                    │  Qdrant + OpenSearch │      │
│                                                    │     (Index)          │      │
│                                                    └──────────┬──────────┘      │
│                                                               │                 │
│                                                               ▼                 │
│                                                    ┌─────────────────────┐      │
│                                                    │       Neo4j         │      │
│                                                    │   (Graph Nodes)     │      │
│                                                    └─────────────────────┘      │
│                                                                                 │
│  Phase 4: Relationship Ingestion                                                │
│  ┌─────────────┐            ┌─────────────┐            ┌─────────────┐          │
│  │ PostgreSQL  │───────────►│    Neo4j    │───────────►│  Metadata   │          │
│  │relationships│            │   (Edges)   │            │ Enrichment  │          │
│  └─────────────┘            └─────────────┘            └─────────────┘          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      EXTERNAL SERVICES                                          │
│                                                                                 │
│  ┌─────────────────────────┐  ┌─────────────────────────────────────────────┐  │
│  │    Groq API (LLM)       │  │  HuggingFace (Dataset & Embeddings)         │  │
│  │  - llama-3.1-8b-instant │  │  - th1nhng0/vietnamese-legal-documents      │  │
│  │  - llama-3.3-70b-versatile│  - Quockhanh05/Vietnam_legal_embeddings     │  │
│  │  - Temperature=0        │  │                                             │  │
│  └─────────────────────────┘  └─────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  Web Search (DISABLED - Code exists but never called)                    │   │
│  │  WebSearchResult type defined but no DuckDuckGo/Google integration       │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Tech Stack Summary

| Layer | Technology | Purpose |
|-------|------------|---------|
| **API Layer** | FastAPI + Uvicorn | REST API endpoints, SSE streaming |
| **Frontend** | Next.js + React | Web UI (separate app in `apps/web-app/`) |
| **Vector DB** | Qdrant | Dense vector search (768-dim, cosine) |
| **Full-text** | OpenSearch | BM25 lexical search |
| **Metadata** | PostgreSQL 15+ | Relational storage, JSONB metadata |
| **Graph** | Neo4j 5+ | Document relationships (optional) |
| **Cache** | Redis 7+ | Configured but NOT integrated |
| **LLM** | Groq API | llama-3.1-8b-instant / llama-3.3-70b-versatile |
| **Embeddings** | SentenceTransformers | Quockhanh05/Vietnam_legal_embeddings |
| **Dataset** | HuggingFace | th1nhng0/vietnamese-legal-documents |
| **Metrics** | Prometheus | Infrastructure ready, Grafana optional |

---

## 2. Mô hình dữ liệu (Data Model)

### 2.1 Dữ liệu nguồn (Source Data)

Dataset HuggingFace: `th1nhng0/vietnamese-legal-documents`

#### 2.1.1 metadata.parquet (16 cột)

| Column | Type | Description |
|--------|------|-------------|
| `id` | Int64 | Document ID (numeric) |
| `title` | String | Tiêu đề văn bản |
| `so_ky_hieu` | String | Số ký hiệu |
| `ngay_ban_hanh` | String | Ngày ban hành |
| `loai_van_ban` | String | Loại văn bản (Luật, Nghị định, Thông tư...) |
| `ngay_co_hieu_luc` | String | Ngày có hiệu lực |
| `ngay_het_hieu_luc` | String | Ngày hết hiệu lực |
| `nguon_thu_thap` | String | Nguồn thu thập |
| `ngay_dang_cong_bao` | String | Ngày đăng công báo |
| `nganh` | String | Ngành |
| `linh_vuc` | String | Lĩnh vực |
| `co_quan_ban_hanh` | String | Cơ quan ban hành |
| `chuc_danh` | String | Chức danh |
| `nguoi_ky` | String | NgườI ký |
| `pham_vi` | String | Phạm vi |
| `thong_tin_ap_dung` | String | Thông tin áp dụng |
| `tinh_trang_hieu_luc` | String | Tình trạng hiệu lực |

#### 2.1.2 content.parquet (2 cột)

| Column | Type | Description |
|--------|------|-------------|
| `id` | String | Document ID (string - **type mismatch với metadata!**) |
| `content_html` | String | Nội dung HTML đầy đủ |

**Lưu ý quan trọng:** ID trong metadata là Int64, trong content là String. Pipeline phải cast cả hai về String để join.

#### 2.1.3 relationships.parquet (3 cột)

| Column | Type | Description |
|--------|------|-------------|
| `doc_id` | Int64 | ID văn bản gốc |
| `other_doc_id` | Int64 | ID văn bản liên quan |
| `relationship` | String | Loại quan hệ (Văn bản căn cứ, Văn bản sửa đổi...) |

### 2.2 PostgreSQL Schema

#### 2.2.1 legal_documents table

```sql
CREATE TABLE IF NOT EXISTS legal_documents (
    id VARCHAR(255) PRIMARY KEY,
    content TEXT NOT NULL,
    title TEXT,
    doc_type VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_legal_documents_doc_type ON legal_documents(doc_type);
CREATE INDEX idx_legal_documents_created_at ON legal_documents(created_at);
CREATE INDEX idx_legal_documents_metadata ON legal_documents USING gin(metadata);
```

**JSONB metadata structure:**
```json
{
  "doc_type": "luat",
  "source": "ingestion_pipeline",
  "parent_id": null,
  "children_ids": [],
  "publish_date": "2020-01-01",
  "effective_date": "2020-07-01",
  "expiry_date": null,
  "issuing_body": "Quốc Hội",
  "document_number": "45/2019/QH14",
  "amendment_refs": [],
  "citation_refs": [],
  "keywords": [],
  "level": 0,
  "related_doc_count": 5,
  "relationship_types": ["Văn bản căn cứ", "Văn bản hướng dẫn"]
}
```

#### 2.2.2 document_relationships table

```sql
CREATE TABLE IF NOT EXISTS document_relationships (
    id SERIAL PRIMARY KEY,
    source_doc_id VARCHAR(255) NOT NULL,
    target_doc_id VARCHAR(255) NOT NULL,
    relationship_type VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_doc_id, target_doc_id, relationship_type)
);

-- Indexes
CREATE INDEX idx_rel_source ON document_relationships(source_doc_id);
CREATE INDEX idx_rel_target ON document_relationships(target_doc_id);
CREATE INDEX idx_rel_type ON document_relationships(relationship_type);
```

### 2.3 Qdrant Schema

**Collection:** `legal_docs`

| Field | Type | Description |
|-------|------|-------------|
| `id` | String | Document ID (primary key) |
| `vector` | Float[768] | Embedding vector (cosine similarity) |
| `title` | String | Document title |
| `doc_type` | String | Loại văn bản |
| `issuing_body` | String | Cơ quan ban hành |
| `dates` | Object | publish_date, effective_date, expiry_date |
| `keywords` | String[] | Từ khóa |
| `related_doc_ids` | String[] | IDs của văn bản liên quan |
| `relationship_types` | String[] | Các loại quan hệ |
| `related_doc_count` | Integer | Số lượng văn bản liên quan |

**Embedding Model:** `Quockhanh05/Vietnam_legal_embeddings` (768-dim)

### 2.4 OpenSearch Schema

**Index:** `legal_docs`

| Field | Type | Analyzer | Description |
|-------|------|----------|-------------|
| `id` | keyword | - | Document ID |
| `title` | text | standard | Tiêu đề (boost 2x) |
| `content` | text | standard | Nội dung đầy đủ |
| `doc_type` | keyword | - | Loại văn bản |
| `issuing_body` | keyword | - | Cơ quan ban hành |
| `dates` | object | - | Các ngày quan trọng |
| `keywords` | keyword | - | Từ khóa |
| `related_doc_ids` | keyword | - | IDs liên quan |
| `relationship_types` | keyword | - | Loại quan hệ |
| `related_doc_count` | integer | - | Số lượng liên quan |

**BM25 Ranking:** Default OpenSearch BM25 with field boost: `content^2, title`

### 2.5 Neo4j Graph Schema

#### Nodes

| Label | Properties | Description |
|-------|------------|-------------|
| `:Document` | id, title, content, doc_type, year, publish_date, effective_date, expiry_date, issuing_body, document_number, level, keywords | Văn bản pháp luật |
| `:Article` | id, number, title, content | Điều luật |
| `:Subsection` | id, number, content | Khoản |

#### Relationships (Edges)

| Type | From | To | Properties | Description |
|------|------|-----|------------|-------------|
| `CONTAINS` | Document | Article | - | Văn bản chứa điều |
| `HAS_SUBSECTION` | Article | Subsection | - | Điều có khoản |
| `AMENDED_BY` | Document | Document | effective_date | Văn bản được sửa đổi bởi |
| `REFERENCES` | Document | Document | - | Văn bản tham chiếu |
| `CITES` | Article | Article | - | Điều trích dẫn |
| `RELATES_TO` | Document | Document | type | Quan hệ chung |

**Lưu ý:** Neo4j là OPTIONAL - hệ thống hoạt động bình thường nếu Neo4j không khả dụng.

---

## 3. Luồng dữ liệu (Data Flow)

### 3.1 Pipeline nạp dữ liệu (Ingestion Pipeline)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 1: DOWNLOAD                                        │
│                                                                                  │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                        │
│  │ HuggingFace │────►│   Cache     │────►│   Resume    │                        │
│  │   Dataset   │     │  (Parquet)  │     │   Support   │                        │
│  └─────────────┘     └─────────────┘     └─────────────┘                        │
│                                                                                  │
│  Files: content.parquet, metadata.parquet, relationships.parquet                 │
│  Location: data/cache/datasets/                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 2: PROCESS                                         │
│                                                                                  │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐   │
│  │    Load     │────►│  ID Cast    │────►│ Inner Join  │────►│ HTML Clean  │   │
│  │   Polars    │     │ (Int→Str)   │     │  (on id)    │     │ (ThreadPool)│   │
│  └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘   │
│                                                                                  │
│  - streaming=False cho Parquet (large_string support)                            │
│  - Parallel HTML cleaning với ThreadPoolExecutor                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 3: DOCUMENT INGESTION                              │
│                                                                                  │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐   │
│  │   Parse     │────►│  Normalize  │────►│ PostgreSQL  │────►│   Qdrant    │   │
│  │   (Regex)   │     │    (NFC)    │     │   (Store)   │     │  (Vectors)  │   │
│  └─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘   │
│                                                                     │          │
│                                                                     ▼          │
│                                                            ┌─────────────┐     │
│                                                            │ OpenSearch  │     │
│                                                            │   (BM25)    │     │
│                                                            └──────┬──────┘     │
│                                                                   │            │
│                                                                   ▼            │
│                                                            ┌─────────────┐     │
│                                                            │    Neo4j    │     │
│                                                            │   (Nodes)   │     │
│                                                            └─────────────┘     │
│                                                                                  │
│  Batching: 50-100 docs/batch cho throughput tối ưu                              │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 4: RELATIONSHIP INGESTION                          │
│                                                                                  │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐   │
│  │  Load rels  │────►│ PostgreSQL  │────►│    Neo4j    │────►│   Update    │   │
│  │  (parquet)  │     │ (INSERT...) │     │   (Edges)   │     │   Metadata  │   │
│  └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘   │
│                                                                                  │
│  - UPSERT với ON CONFLICT DO NOTHING                                            │
│  - Batch size: 500 relationships                                                │
│  - Metadata enrichment: related_doc_count, relationship_types                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Luồng truy vấn (Query/Retrieval Flow)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         QUERY FLOW                                               │
│                                                                                  │
│  User Query                                                                      │
│      │                                                                           │
│      ▼                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    QueryPlanner.plan() (SYNC - never await)              │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │    │
│  │  │  Normalize  │  │   Expand    │  │   Detect    │  │   Extract       │ │    │
│  │  │    NFC      │  │     Abbr    │  │  Negation   │  │  Citations      │ │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘ │    │
│  │                                                                           │    │
│  │  Output: QueryPlan {normalized_query, has_negation, citations, strategy} │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│      │                                                                           │
│      ▼                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    HybridRetriever.search() (ASYNC)                      │    │
│  │                                                                           │    │
│  │   ┌─────────────────┐         ┌─────────────────┐                       │    │
│  │   │   BM25 Search   │         │   Dense Search  │                       │    │
│  │   │  (OpenSearch)   │◄───────►│    (Qdrant)     │                       │    │
│  │   │                 │  async  │                 │                       │    │
│  │   │  - 100 cands    │ parallel│  - 100 cands    │                       │    │
│  │   │  - Multi-match  │         │  - Cosine sim   │                       │    │
│  │   │  - Filters      │         │  - Filters      │                       │    │
│  │   └────────┬────────┘         └────────┬────────┘                       │    │
│  │            │                           │                                 │    │
│  │            └─────────────┬─────────────┘                                 │    │
│  │                          ▼                                               │    │
│  │            ┌─────────────────────────┐                                   │    │
│  │            │    RRF Fusion (k=60)    │                                   │    │
│  │            │  score = 1/(60+bm25_rank) + 1/(60+dense_rank)               │    │
│  │            └────────────┬────────────┘                                   │    │
│  │                         ▼                                                │    │
│  │            ┌─────────────────────────┐                                   │    │
│  │            │   Score Normalization   │                                   │    │
│  │            │   (Adaptive Centering)  │                                   │    │
│  │            └────────────┬────────────┘                                   │    │
│  │                         ▼                                                │    │
│  │            ┌─────────────────────────┐                                   │    │
│  │            │   Sandwich Reordering   │                                   │    │
│  │            │ [1st,3rd,5th...6th,4th,2nd]                                 │    │
│  │            │  (Lost-in-the-middle fix)                                   │    │
│  │            └────────────┬────────────┘                                   │    │
│  │                         ▼                                                │    │
│  │            ┌─────────────────────────┐                                   │    │
│  │            │   Fetch Full Documents  │                                   │    │
│  │            │    (from PostgreSQL)    │                                   │    │
│  │            └─────────────────────────┘                                   │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│      │                                                                           │
│      ▼                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    ContextInjector.inject_context()                      │    │
│  │                                                                           │    │
│  │  PRIMARY: PostgreSQL relationships (bidirectional query)                │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │    │
│  │  │   Parent    │  │  Siblings   │  │ Amendments  │  │  PG Relations   │ │    │
│  │  │   (Neo4j)   │  │   (Neo4j)   │  │  (Neo4j)    │  │   (PRIMARY)     │ │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘ │    │
│  │                                                                           │    │
│  │  SECONDARY: Neo4j graph traversal (multi-hop) - optional                │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│      │                                                                           │
│      ▼                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    Reranker (Two-Stage)                                  │    │
│  │                                                                           │    │
│  │  Stage 1: Position-Decay (always applied)                               │    │
│  │  Stage 2: ColBERT/Cross-Encoder (optional - not implemented)            │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│      │                                                                           │
│      ▼                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    Result with Related Documents                         │    │
│  │  - RetrievedDocument[] với related_documents populated                   │    │
│  │  - ContextDocument[] cho EvidencePack                                    │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Luồng đánh giá hợp đồng (Contract Review Flow)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CONTRACT REVIEW FLOW                                     │
│                                                                                  │
│  Contract Text                                                                   │
│      │                                                                           │
│      ▼                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    Clause Extraction (Regex)                             │    │
│  │                                                                           │    │
│  │  Patterns:                                                                │    │
│  │  - "Điều \d+" (Article markers)                                          │    │
│  │  - "Chương \w+" (Chapter markers)                                        │    │
│  │  - "Mục \w+" (Section markers)                                           │    │
│  │                                                                           │    │
│  │  Output: List[(clause_index, clause_text)]                               │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│      │                                                                           │
│      ▼                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    Parallel Clause Processing (Semaphore)                │    │
│  │                                                                           │    │
│  │  max_concurrent = 5 (configurable)                                       │    │
│  │                                                                           │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │    │
│  │  │   Clause 1  │  │   Clause 2  │  │   Clause 3  │  │   ...       │     │    │
│  │  │  (async)    │  │  (async)    │  │  (async)    │  │  (async)    │     │    │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │    │
│  │         │                │                │                │            │    │
│  │         └────────────────┴────────────────┴────────────────┘            │    │
│  │                              │                                          │    │
│  │                              ▼                                          │    │
│  │         PER-CLAUSE PIPELINE (mỗi clause chạy riêng):                    │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│      │                                                                           │
│      ▼                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    Per-Clause Pipeline                                   │    │
│  │                                                                           │    │
│  │  1. Query Planning                                                        │    │
│  │     └── QueryPlanner.plan(clause_text) → QueryPlan                       │    │
│  │                                                                           │    │
│  │  2. Hybrid Retrieval                                                      │    │
│  │     └── HybridRetriever.search(top_k=5) → RetrievedDocument[]            │    │
│  │                                                                           │    │
│  │  3. Context Enrichment                                                    │    │
│  │     └── ContextInjector.inject_context() → ContextDocument[]             │    │
│  │                                                                           │    │
│  │  4. Two-Stage Verification                                                │    │
│  │     ┌─────────────────────────────────────────────────────────────┐      │    │
│  │     │ Stage 1: Rule-Based (<10ms)                                 │      │    │
│  │     │ - Exact phrase containment → ENTAILED                     │      │    │
│  │     │ - Negation mismatch → CONTRADICTED                        │      │    │
│  │     │ - Number mismatch → CONTRADICTED                          │      │    │
│  │     │ - Inconclusive → Stage 2                                  │      │    │
│  │     └─────────────────────────────────────────────────────────────┘      │    │
│  │                              │                                           │    │
│  │                              ▼ (nếu Stage 1 inconclusive)                │    │
│  │     ┌─────────────────────────────────────────────────────────────┐      │    │
│  │     │ Stage 2: LLM (Groq API, temperature=0)                      │      │    │
│  │     │ - Prompt with clause + regulation + context                 │      │    │
│  │     │ - Output: ENTAILED/CONTRADICTED/PARTIALLY_SUPPORTED/NO_REF  │      │    │
│  │     │ - Fallback model nếu rate limit                             │      │    │
│  │     └─────────────────────────────────────────────────────────────┘      │    │
│  │                                                                           │    │
│  │  5. EvidencePack Assembly                                                 │    │
│  │     ┌─────────────────────────────────────────────────────────────┐      │    │
│  │     │  EvidencePack {                                             │      │    │
│  │     │    clause: str,                                             │      │    │
│  │     │    retrieved_documents: RetrievedDocument[],                │      │    │
│  │     │    context_documents: ContextDocument[],                    │      │    │
│  │     │    citations: Citation[],                                   │      │    │
│  │     │    verification_level: VerificationLevel,                   │      │    │
│  │     │    verification_confidence: float                           │      │    │
│  │     │  }                                                          │      │    │
│  │     └─────────────────────────────────────────────────────────────┘      │    │
│  │                                                                           │    │
│  │  6. Finding Generation (Generator NEVER searches - consumes EvidencePack)│    │
│  │     └── LegalGenerator.generate_finding(EvidencePack) → ReviewFinding    │    │
│  │                                                                           │    │
│  │  Output: ReviewFinding {                                                 │    │
│  │    clause_text, clause_index, verification, confidence,                  │    │
│  │    risk_level, rationale, citations,                                     │    │
│  │    revision_suggestion, negotiation_note, latency_ms                     │    │
│  │  }                                                                       │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│      │                                                                           │
│      ▼                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    Summary Aggregation                                   │    │
│  │                                                                           │    │
│  │  - Collect all ReviewFinding[]                                           │    │
│  │  - Sort by clause_index                                                  │    │
│  │  - Generate risk_summary: {high: N, medium: N, low: N, none: N}          │    │
│  │  - LegalGenerator.generate_review_summary()                              │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│      │                                                                           │
│      ▼                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    SSE Streaming to Client                               │    │
│  │                                                                           │    │
│  │  Events:                                                                  │    │
│  │  {"type": "progress", "data": {"phase": "analyzing", "total_clauses": N}}  │    │
│  │  {"type": "progress", "data": {"phase": "reviewing", "current": X, "total": N}}│  │
│  │  {"type": "finding", "data": {<ReviewFinding>}}                          │    │
│  │  {"type": "progress", "data": {"phase": "summarizing"}}                   │    │
│  │  {"type": "summary", "data": {"summary": "...", "risk_summary": {...}}}   │    │
│  │  {"type": "done", "data": {}}                                            │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Kiến trúc truy xuất (Retrieval Architecture)

### 4.1 Hybrid Search

Hệ thống sử dụng **song song BM25 + Dense Vector** với RRF fusion:

```python
# Parallel execution
bm25_task = self._bm25_search(query, size=bm25_candidates, filters=filters)
dense_task = self._dense_search(query, limit=dense_candidates, filters=filters)

bm25_results, dense_results = await asyncio.gather(
    bm25_task, dense_task, return_exceptions=True
)
```

### 4.2 RRF Fusion Formula

```
score = 1/(k + bm25_rank) + 1/(k + dense_rank)

Where:
- k = 60 (constant)
- bm25_rank = rank trong BM25 results (1-indexed)
- dense_rank = rank trong dense results (1-indexed)

Example:
- Doc A: BM25 rank=1, Dense rank=3 → score = 1/61 + 1/63 = 0.0323
- Doc B: BM25 rank=2, Dense rank=1 → score = 1/62 + 1/61 = 0.0326
→ Doc B wins
```

### 4.3 Score Normalization

Sử dụng **adaptive centering** để normalize scores về range 0-1:

```python
class RRFNormalizer:
    def normalize_rrf_scores(self, scores: list[float]) -> list[float]:
        if not scores:
            return []
        
        min_score = min(scores)
        max_score = max(scores)
        score_range = max_score - min_score
        
        if score_range < 1e-6:
            return [0.5] * len(scores)
        
        # Center to 0-1 range
        return [(s - min_score) / score_range for s in scores]
```

### 4.4 Sandwich Reordering

Giải pháp cho **lost-in-the-middle** problem (LLM attention decay):

```
Input (sorted by score):  [A, B, C, D, E, F]  (A=best, F=worst)
Output (sandwich):        [A, C, E, F, D, B]
                              ↑     ↑
                           High relevance at START and END
                           Low relevance in MIDDLE
```

Algorithm:
```python
def _apply_sandwich_reorder(docs):
    sorted_docs = sorted(docs, key=lambda d: d.score, reverse=True)
    n = len(sorted_docs)
    
    # Odd positions first (1st, 3rd, 5th...)
    odd_positions = [sorted_docs[i] for i in range(0, n, 2)]
    
    # Even positions reversed (..., 6th, 4th, 2nd)
    even_positions = [sorted_docs[i] for i in range(1, n, 2)]
    even_positions.reverse()
    
    return odd_positions + even_positions
```

### 4.5 Relationship-Boosted Search

Khi có `seed_doc_ids`, hệ thống fetch related documents từ PostgreSQL và boost scores:

```python
async def search_with_relationships(
    self,
    query: str,
    seed_doc_ids: list[str] | None = None,
    relationship_boost: float = 1.2,
    ...
):
    # 1. Fetch related doc IDs from PostgreSQL
    related_doc_ids = await self._get_related_doc_ids_from_pg(seed_doc_ids)
    
    # 2. Execute standard hybrid search
    documents = await self.search(query, ...)
    
    # 3. Apply relationship boosting
    for doc in documents:
        if doc.doc_id in related_doc_ids:
            doc.score *= relationship_boost
            doc.metadata["relationship_boosted"] = True
    
    # 4. Re-sort by boosted scores
    documents.sort(key=lambda d: d.score, reverse=True)
    
    return documents
```

### 4.6 Context Injection

**PostgreSQL là PRIMARY source** cho relationships:

```python
async def _fetch_pg_relationships(self, doc: RetrievedDocument) -> list[ContextDocument]:
    # Query outgoing relationships
    outgoing = """
        SELECT dr.target_doc_id, dr.relationship_type, ld.title, LEFT(ld.content, 500)
        FROM document_relationships dr
        LEFT JOIN legal_documents ld ON dr.target_doc_id = ld.id
        WHERE dr.source_doc_id = $1
    """
    
    # Query incoming relationships
    incoming = """
        SELECT dr.source_doc_id, dr.relationship_type, ld.title, LEFT(ld.content, 500)
        FROM document_relationships dr
        LEFT JOIN legal_documents ld ON dr.source_doc_id = ld.id
        WHERE dr.target_doc_id = $1
    """
```

**Neo4j là SECONDARY source** cho multi-hop traversal (depth >= 2):

```python
if depth >= 2 and self._graph_client:
    neo4j_rels = await self._graph_client.get_related_by_topic(
        doc_id, max_hops=min(depth, 3)
    )
```

---

## 5. Pipeline đánh giá (Review Pipeline)

### 5.1 Clause Extraction

```python
def _parse_contract_clauses(self, contract_text: str) -> list[tuple[int, str]]:
    article_patterns = [
        r'(?:^|\n)\s*Điều\s+\d+',      # "Điều 1", "Điều 2"
        r'(?:^|\n)\s*Điều thứ\s+\d+',  # "Điều thứ 1"
        r'(?:^|\n)\s*Điều\s+[IVX]+',   # Roman numerals
        r'(?:^|\n)\s*Chương\s+\w+',    # Chapters
        r'(?:^|\n)\s*Mục\s+\w+',       # Sections
    ]
    
    combined_pattern = '|'.join(f'({p})' for p in article_patterns)
    parts = re.split(f'(?={combined_pattern})', contract_text, flags=re.IGNORECASE)
    
    # Filter: skip fragments < 20 chars
    return [(i, part.strip()) for i, part in enumerate(parts) if len(part.strip()) >= 20]
```

### 5.2 Two-Stage Verification

#### Stage 1: Rule-Based (<10ms)

```python
def _rule_based_score(self, clause: str, regulation: str) -> VerificationLevel | None:
    # Rule 1: Exact phrase containment
    key_phrases = self._extract_key_phrases(clause.lower())
    for phrase in key_phrases:
        if len(phrase) > 20 and phrase in regulation.lower():
            return VerificationLevel.ENTAILED
    
    # Rule 2: Negation mismatch
    clause_has_negation = self._has_negation(clause)
    regulation_has_negation = self._has_negation(regulation)
    if clause_has_negation != regulation_has_negation:
        similarity = self._calculate_similarity(clause, regulation)
        if similarity > 0.6:
            return VerificationLevel.CONTRADICTED
    
    # Rule 3: Number mismatch
    clause_numbers = self._extract_numbers(clause)
    regulation_numbers = self._extract_numbers(regulation)
    if clause_numbers and regulation_numbers:
        common = set(clause_numbers) & set(regulation_numbers)
        if not common:
            similarity = self._calculate_similarity(clause, regulation)
            if similarity > 0.5:
                return VerificationLevel.CONTRADICTED
    
    # Inconclusive - need LLM
    return None
```

#### Stage 2: LLM (Groq API)

```python
async def _llm_score(self, clause, regulation, context) -> dict:
    prompt = f"""
You are a legal verification system for Vietnamese law.

Contract Clause:
{clause}

Regulation:
{regulation}

Analyze and respond in this exact format:
LEVEL: [entailed|contradicted|partially_supported|no_reference]
CONFIDENCE: [0.0-1.0]
REASONING: [Brief explanation]
"""
    
    response = await self._call_groq_with_fallback(prompt, temperature=0)
    return self._parse_llm_response(response)
```

### 5.3 Verification Levels

| Level | Description | Risk Mapping |
|-------|-------------|--------------|
| `ENTAILED` | Điều khoản tuân thủ đầy đủ quy định | `NONE` |
| `CONTRADICTED` | Điều khoản vi phạm quy định | `HIGH` |
| `PARTIALLY_SUPPORTED` | Điều khoản tuân thủ một phần | `MEDIUM` |
| `NO_REFERENCE` | Không tìm thấy căn cứ pháp lý | `LOW` |

### 5.4 EvidencePack Pattern

**Nguyên tắc quan trọng:** Generator **KHÔNG BAO GIỜ** tự tìm kiếm. Chỉ sử dụng evidence đã được chuẩn bị sẵn.

```python
class EvidencePack(BaseModel):
    """Pre-assembled evidence bundle for the generator.
    
    Generator NEVER initiates searches, only consumes pre-assembled evidence.
    This ensures deterministic, auditable reasoning.
    """
    clause: str
    retrieved_documents: list[RetrievedDocument] = []
    context_documents: list[ContextDocument] = []
    citations: list[Citation] = []
    web_sources: list[WebSearchResult] = []  # Currently always empty
    verification_level: VerificationLevel | None = None
    verification_confidence: float = 0.0
    verification_reasoning: str | None = None
```

### 5.5 Streaming SSE Events

```
Client ──POST /review/contracts/stream──► Server
         
Server ──SSE: {"type": "progress", "data": {"phase": "analyzing", "total_clauses": 5}}──► Client
Server ──SSE: {"type": "progress", "data": {"phase": "reviewing", "current": 1, "total": 5}}──► Client
Server ──SSE: {"type": "finding", "data": {<ReviewFinding 1>}}──► Client
Server ──SSE: {"type": "progress", "data": {"phase": "reviewing", "current": 2, "total": 5}}──► Client
Server ──SSE: {"type": "finding", "data": {<ReviewFinding 2>}}──► Client
...
Server ──SSE: {"type": "progress", "data": {"phase": "summarizing"}}──► Client
Server ──SSE: {"type": "summary", "data": {"summary": "...", "risk_summary": {...}}}──► Client
Server ──SSE: {"type": "done", "data": {}}──► Client
```

---

## 6. API Reference

### 6.1 Health Check

```
GET /api/v1/health

Response (HealthResponse):
{
  "status": "ok" | "degraded",
  "version": "0.1.0",
  "services": {
    "api": "ok",
    "qdrant": "ok" | "unhealthy",
    "opensearch": "green" | "yellow" | "red" | "unhealthy",
    "postgres": "ok" | "unhealthy",
    "redis": "ok" | "unhealthy",
    "neo4j": "ok" | "unhealthy"
  }
}
```

### 6.2 Contract Review

#### Synchronous Review

```
POST /api/v1/review/contracts

Request (ContractReviewRequest):
{
  "contract_text": "string (min_length=10)",
  "contract_id": "string (optional)",
  "filters": {"doc_type": ["luat", "nghi_dinh"]} (optional),
  "include_relationships": true (default)
}

Response (ContractReviewResult):
{
  "contract_id": "uuid",
  "findings": [ReviewFinding],
  "summary": "string",
  "total_clauses": 5,
  "risk_summary": {"high": 1, "medium": 2, "low": 1, "none": 1},
  "total_latency_ms": 1234.5,
  "timestamp": "2024-01-01T00:00:00Z",
  "references": [{"article_id": "...", "law_id": "...", "document_title": "..."}]
}
```

#### Streaming Review (SSE)

```
POST /api/v1/review/contracts/stream

Request: Same as synchronous

Response: text/event-stream

data: {"type": "progress", "data": {"phase": "analyzing", "total_clauses": 5}}

data: {"type": "finding", "data": {"clause_text": "...", "verification": "entailed", ...}}

data: {"type": "summary", "data": {"summary": "...", "risk_summary": {...}}}

data: {"type": "done", "data": {}}
```

### 6.3 Legal Chat

#### Synchronous Chat

```
POST /api/v1/chat/legal

Request (ChatRequest):
{
  "query": "string (min_length=1)",
  "session_id": "string (optional)",
  "filters": {"doc_type": ["luat"]} (optional),
  "include_relationships": true (default)
}

Response (ChatAnswer):
{
  "answer": "string",
  "citations": [Citation],
  "confidence": 0.85,
  "evidence_pack": EvidencePack,
  "latency_ms": 567.8
}
```

#### Streaming Chat (SSE)

```
POST /api/v1/chat/legal/stream

Request: Same as synchronous

Response: text/event-stream

data: Phần 1 của câu trả lời...

data: Phần 2 của câu trả lời...

data: [CITATIONS] [{"article_id": "...", "law_id": "..."}]

data: [DONE]
```

### 6.4 Ingestion

#### Batch Ingest

```
POST /api/v1/ingest/legal-corpus

Request (IngestRequest):
{
  "documents": [{"title": "...", "content": "..."}],
  "source": "manual",
  "batch_size": 100
}

Response (IngestResponse):
{
  "task_id": "uuid",
  "status": "queued",
  "document_count": 10,
  "message": "..."
}
```

#### Single Document Ingest

```
POST /api/v1/ingest/single?title=...&content=...

Response: IngestResponse
```

#### HuggingFace Dataset Ingest

```
POST /api/v1/ingest/huggingface

Query Params:
- dataset_name: "th1nhng0/vietnamese-legal-documents" (default)
- split: "train" (default)
- limit: int (optional)

Response: IngestResponse
```

#### Check Task Status

```
GET /api/v1/ingest/status/{task_id}

Response:
{
  "task_id": "uuid",
  "status": "queued" | "processing" | "completed" | "failed",
  "progress": 50,
  "message": "...",
  "stats": {...}
}
```

### 6.5 Citations

```
GET /api/v1/citations/{node_id}

Response:
{
  "node_id": "...",
  "hierarchy": {...},
  "parent": {...} | null,
  "amendments": [...],
  "citing_articles": [...],
  "related_documents": [...],
  "context_documents": [ContextDocument],
  "graph_available": true | false,
  "warning": "string" | null
}
```

### 6.6 Graph API

#### Get Document Relationships

```
GET /api/v1/graph/relationships/{doc_id}

Query Params:
- relationship_type: "Văn bản căn cứ" (optional filter)
- depth: 1 | 2 (default: 1)

Response (RelationshipResponse):
{
  "doc_id": "...",
  "relationships": [
    {
      "doc_id": "...",
      "title": "...",
      "relationship_type": "Văn bản căn cứ",
      "direction": "outgoing" | "incoming",
      "depth": 1
    }
  ]
}
```

#### Get Relationship Types

```
GET /api/v1/graph/relationship-types

Response (RelationshipTypesResponse):
{
  "relationship_types": [
    {"relationship_type": "Văn bản căn cứ", "count": 150},
    {"relationship_type": "Văn bản sửa đổi", "count": 80}
  ]
}
```

#### Sync PostgreSQL to Neo4j

```
POST /api/v1/graph/sync?limit=1000

Response:
{
  "status": "completed",
  "limit": 1000,
  "stats": {"synced": 950, "errors": 50}
}
```

### 6.7 Dataset Ingestion (Task Manager)

```
POST /api/v1/dataset-ingestion/start?limit=50

Response:
{
  "task_id": "uuid",
  "status": "queued",
  "limit": 50,
  "message": "..."
}

GET /api/v1/dataset-ingestion/status/{task_id}

Response: Task status with detailed progress

GET /api/v1/dataset-ingestion/tasks?limit=20

Response: List of recent tasks

POST /api/v1/dataset-ingestion/cancel/{task_id}

Response: Cancellation status
```

---

## 7. Hạ tầng (Infrastructure)

### 7.1 Docker Compose Services

```yaml
services:
  # Qdrant - Vector Database
  qdrant:
    ports: ["6333:6333", "6334:6334"]
    volumes: [qdrant_storage:/qdrant/storage]
    healthcheck: curl -f http://localhost:6333/healthz

  # OpenSearch - Full-text search
  opensearch:
    ports: ["9200:9200", "9600:9600"]
    environment:
      - discovery.type=single-node
      - plugins.security.disabled=true
      - OPENSEARCH_INITIAL_ADMIN_PASSWORD=SecureP@ssw0rd!2024
    volumes: [opensearch_data:/usr/share/opensearch/data]
    healthcheck: curl -f http://localhost:9200/_cluster/health

  # PostgreSQL - Metadata storage
  postgres:
    image: postgres:15-alpine
    ports: ["5432:5432"]
    environment:
      - POSTGRES_DB=legal_review
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck: pg_isready -U postgres -d legal_review

  # Redis - Caching (configured but NOT integrated)
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: [redis_data:/data]
    command: redis-server --appendonly yes
    healthcheck: redis-cli ping

  # Neo4j - Graph database (optional)
  neo4j:
    image: neo4j:5-community
    ports: ["7474:7474", "7687:7687"]
    environment:
      - NEO4J_AUTH=neo4j/password
      - NEO4J_PLUGINS=["apoc", "graph-data-science"]
    volumes: [neo4j_data:/data, neo4j_logs:/logs]
    healthcheck: cypher-shell -u neo4j -p password 'RETURN 1'

volumes:
  qdrant_storage:
  opensearch_data:
  postgres_data:
  redis_data:
  neo4j_data:
  neo4j_logs:

networks:
  legal-ai-network:
    driver: bridge
```

### 7.2 Port Mapping

| Service | Port | Purpose |
|---------|------|---------|
| FastAPI | 8000 | API server |
| Qdrant HTTP | 6333 | Vector search |
| Qdrant gRPC | 6334 | Vector search (gRPC) |
| OpenSearch | 9200 | Full-text search |
| OpenSearch Perf | 9600 | Performance metrics |
| PostgreSQL | 5432 | Relational database |
| Redis | 6379 | Cache (not used) |
| Neo4j HTTP | 7474 | Graph browser |
| Neo4j Bolt | 7687 | Graph queries |

### 7.3 Health Checks

Tất cả services đều có health checks và graceful degradation:

```python
# Trong lifespan() của FastAPI
warmup_tasks = (
    app.state.hybrid_retriever._get_qdrant_client(),
    app.state.hybrid_retriever._get_opensearch_client(),
    app.state.hybrid_retriever._get_postgres_pool(),
    app.state.graph_client.ping(),
)
results = await asyncio.gather(*warmup_tasks, return_exceptions=True)

# Mỗi service có thể fail independently
for service_name, result in zip(("qdrant", "opensearch", "postgres", "neo4j"), results):
    if isinstance(result, Exception):
        logger.warning(f"Startup warmup skipped for {service_name}: {result}")
```

---

## 8. Đã triển khai (Implemented Features)

**Danh sách CHỈ bao gồm các tính năng có code hoạt động thực sự:**

### 8.1 Ingestion Pipeline

- Full 4-phase ingestion pipeline với cache, resume capability, progress bars
- Text normalization (Unicode NFC, abbreviation expansion, date standardization)
- Hierarchical document parsing (articles, subsections, clauses) qua regex
- Multi-backend indexing: Qdrant vectors, OpenSearch BM25, PostgreSQL relational
- Document relationship ingestion (PostgreSQL + Neo4j)
- Batch processing với Polars cho performance
- Parallel HTML cleaning với ThreadPoolExecutor
- Retry logic với exponential backoff

### 8.2 Query Planning

- Text normalization (Unicode NFC)
- Abbreviation expansion (100+ Vietnamese legal abbreviations)
- Synonym expansion (LEGAL_SYNONYMS dictionary)
- Negation detection (NEGATION_PATTERNS)
- Citation extraction (Điều, Luật, Nghị định, Thông tư, Khoản, Điểm)
- Query strategy classification (CITATION, NEGATION, SEMANTIC)

### 8.3 Retrieval

- Hybrid search: parallel BM25 + dense vector
- RRF fusion với k=60
- Score normalization: adaptive centering to 0-1 range
- Sandwich reordering (lost-in-the-middle mitigation)
- Relationship-boosted search (seed_doc_ids → fetch related → boost scores 1.2x)
- Context injection: PostgreSQL primary (bidirectional relationship queries), Neo4j secondary
- Two-stage reranking: position-decay (Stage 1), ColBERT/cross-encoder placeholder (Stage 2)

### 8.4 Review Pipeline

- Clause extraction từ contract text (regex-based)
- Per-clause parallel processing với semaphore (max_concurrent=5)
- Two-stage verification: rule-based (<10ms) then LLM (Groq API, temperature=0)
- Verification levels: ENTAILED, CONTRADICTED, PARTIALLY_SUPPORTED, NO_REFERENCE
- EvidencePack pattern: generator NEVER initiates searches
- Finding generation từ EvidencePack
- Streaming contract review (SSE) với progress events
- Summary aggregation với risk levels

### 8.5 Chat System

- Legal Q&A chat với citations
- Streaming chat (SSE)
- Context enrichment với relationships
- Citation building từ retrieved documents

### 8.6 API Endpoints

- Health check với service status
- Contract review (sync + stream)
- Legal chat (sync + stream)
- Batch ingest + single ingest + HuggingFace ingest
- Citation context retrieval
- Graph relationship API (GET /graph/relationships/{doc_id}, GET /graph/relationship-types)
- Dataset ingestion task management

### 8.7 Resilience & Observability

- Graceful degradation: mỗi optional service có thể down independently
- Prometheus metrics collection (infrastructure ready)
- Request timing middleware
- Error handling với fallback responses
- Connection pooling cho PostgreSQL
- Lazy initialization cho external clients

---

## 9. Chưa triển khai (Not Yet Implemented)

**Danh sách này được viết một cách TRUNG THỰC về những gì chưa có:**

### 9.1 Redis Caching

- **Status:** Redis container chạy nhưng **KHÔNG CÓ CODE NÀO sử dụng**
- **Evidence:** In-memory caches (`self._cache: dict`) được sử dụng trong `LegalVerifier` và `LegalGenerator`
- **Impact:** Single-instance limitation, no distributed caching

### 9.2 Web Search Integration

- **Status:** `WebSearchResult` type được định nghĩa nhưng **KHÔNG BAO GIỜ được populate**
- **Evidence:** Trong `review_pipeline.py`, web search bị comment out:
  ```python
  # DISABLED: Web search not useful for Vietnamese legal domain
  # Saves ~30s per contract (5s timeout × 6 clauses)
  ```
- **Impact:** Không có khả năng tìm kiếm thông tin bổ sung từ internet

### 9.3 PDF/DOCX Parsing

- **Status:** Chỉ hỗ trợ text input
- **Evidence:** Comment trong code: "would need additional libraries"
- **Impact:** NgườI dùng phải tự extract text từ PDF/DOCX

### 9.4 Authentication & Authorization

- **Status:** **KHÔNG CÓ** - Tất cả endpoints đều public
- **Evidence:**
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],  # Configure appropriately for production
      ...
  )
  ```
- **Impact:** Không an toàn cho production deployment

### 9.5 Rate Limiting

- **Status:** **KHÔNG CÓ** rate limiter nào trên endpoints
- **Impact:** Dễ bị abuse, không có protection chống lại request flooding

### 9.6 Amendment Chain Resolution

- **Status:** Parser extract amendment references qua regex nhưng **KHÔNG resolve** chúng thành actual document IDs
- **Evidence:** `amendment_refs` được extract nhưng không có code để resolve
- **Impact:** Không có temporal legal analysis (không biết văn bản nào đã bị sửa đổi)

### 9.7 Advanced Neo4j Traversal

- **Status:** Basic document/relationship creation hoạt động, nhưng deeper graph analytics **KHÔNG được implement**
- **Missing:**
  - Amendment chain resolution
  - Transitive closure queries
  - Graph algorithms (shortest path, centrality)
- **Impact:** Chỉ có simple 1-2 hop queries

### 9.8 Fine-Tuned Reranker

- **Status:** Đang sử dụng generic ms-marco model, **KHÔNG có** Vietnamese-legal-tuned model
- **Evidence:** Stage 2 reranker là placeholder, không được gọi
- **Impact:** Reranking quality có thể không tối ưu cho Vietnamese legal domain

### 9.9 Multi-Model LLM Routing

- **Status:** Chỉ có simple sequential fallback (primary → fallback)
- **Missing:** Quality-based routing, cost-based routing, latency-based routing
- **Evidence:**
  ```python
  models = [
      self.settings.groq_model_primary,
      self.settings.groq_model_fallback,
  ]
  ```

### 9.10 Citation Validation

- **Status:** Citations được extract nhưng **KHÔNG được verify** chống lại actual corpus documents
- **Impact:** Có thể có citations trỏ đến documents không tồn tại

### 9.11 Prometheus/Grafana Dashboards

- **Status:** Prometheus metrics được collect nhưng **KHÔNG CÓ** Grafana dashboards được triển khai
- **Evidence:** Grafana service bị comment out trong docker-compose.yml

---

## 10. Gợi ý tối ưu (Optimization Recommendations)

### 10.1 High Priority

1. **Integrate Redis for retrieval caching**
   - Cache Qdrant/OpenSearch results cho repeated queries
   - Reduce latency cho common queries
   - Enable horizontal scaling

2. **Add authentication (JWT or API key)**
   - Bắt buộc trước khi deploy production
   - Bảo vệ endpoints khỏi unauthorized access

3. **Add rate limiting**
   - Sử dụng SlowAPI hoặc custom middleware
   - Protect against abuse và ensure fair usage

### 10.2 Medium Priority

4. **Fine-tune reranker on Vietnamese legal data**
   - Train ColBERT hoặc cross-encoder trên Vietnamese legal corpus
   - Cải thiện retrieval quality

5. **Implement amendment chain resolution**
   - Resolve amendment references thành actual document IDs
   - Enable temporal legal analysis (biết văn bản nào còn hiệu lực)

6. **Add PDF/DOCX parsing**
   - Sử dụng PyMuPDF (fitz) cho PDF
   - Sử dụng python-docx cho DOCX
   - Enable direct document upload

### 10.3 Low Priority

7. **Validate citations against corpus**
   - Dead-link detection
   - Ensure citations trỏ đến documents tồn tại

8. **Add Grafana dashboards**
   - Visualize Prometheus metrics
   - Monitor system health và performance

9. **Implement web search for supplementary info**
   - DuckDuckGo hoặc Google Custom Search
   - Fallback khi corpus không có thông tin

10. **Consider horizontal scaling**
    - Load balancer cho multiple API instances
    - Distributed caching với Redis Cluster

---

## Tài liệu tham khảo (References)

- Dataset: [th1nhng0/vietnamese-legal-documents](https://huggingface.co/datasets/th1nhng0/vietnamese-legal-documents)
- Embedding Model: [Quockhanh05/Vietnam_legal_embeddings](https://huggingface.co/Quockhanh05/Vietnam_legal_embeddings)
- Groq API: https://groq.com/
- Qdrant: https://qdrant.tech/
- OpenSearch: https://opensearch.org/
- Neo4j: https://neo4j.com/

---

**Document Version:** 1.0  
**Last Updated:** April 2026  
**Author:** AI Assistant  
**Language:** Vietnamese with English technical terms
