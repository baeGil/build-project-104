# Vietnamese Legal Contract Review AI System

Hệ thống AI rà soát hợp đồng pháp lý tiếng Việt với kiến trúc RAG (Retrieval-Augmented Generation), cung cấp phân tích chi tiết, đánh giá rủi ro, và gợi ý sửa đổi cho hợp đồng pháp lý.

## Tính năng chính

- **Phân tích hợp đồng tự động** - Upload hợp đồng, nhận phân tích rủi ro chi tiết theo từng điều khoản
- **Tìm kiếm pháp lý thông minh** - Hybrid search (BM25 + Dense Vector) trên corpus 1,146+ văn bản pháp luật
- **Chat pháp lý** - Hỏi đáp về pháp luật với trích dẫn cụ thể [1], [2], [3]
- **Đánh giá rủi ro** - Classification: High/Medium/Low/None với confidence score
- **Gợi ý sửa đổi** - Đề xuất cụ thể cho từng điều khoản vi phạm
- **Lời khuyên đàm phán** - Gợi ý chiến lược đàm phán hợp đồng
- **Streaming real-time** - Xem progress phân tích theo thời gian thực (SSE)
- **Dataset ingestion** - Tự động tải và xử lý dataset từ HuggingFace

## Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                       │
│  - Contract Review UI  - Chat UI  - Ingestion Dashboard     │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST API + SSE
┌──────────────────────▼──────────────────────────────────────┐
│                 Backend (FastAPI + Python)                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           Contract Review Pipeline                  │   │
│  │  Parse → Plan → Retrieve → Verify → Generate        │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Retrieval   │  │  Reasoning   │  │  Ingestion   │    │
│  │  (Hybrid)    │  │  (LLM+RAG)   │  │  (Pipeline)  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└───────┬──────────────┬──────────────┬─────────────────────┘
        │              │              │
┌───────▼──────┐ ┌─────▼──────┐ ┌─────▼──────┐
│  PostgreSQL  │ │   Qdrant   │ │ OpenSearch │
│  (Metadata)  │ │ (Vectors)  │ │  (BM25)    │
└──────────────┘ └────────────┘ └────────────┘
        │
┌───────▼──────┐
│    Neo4j     │
│  (Graph DB)  │
└──────────────┘
```

## 🚀 Quick Start

### Yêu cầu hệ thống

- **Python:** 3.11+
- **Node.js:** 18+
- **Docker & Docker Compose:** Latest
- **uv:** Package manager cho Python (https://docs.astral.sh/uv/)
- **RAM:** Tối thiểu 8GB (recommend 16GB)
- **OS:** macOS, Linux, Windows (WSL2)

### Tech Stack

**Backend:**
- **Framework:** FastAPI 0.115+ (Python 3.11+)
- **LLM Provider:** Groq API
  - Primary: `llama-3.1-8b-instant` (fast, efficient)
  - Fallback: `llama-3.3-70b-versatile` (higher quality)
- **Embedding Model:** `Quockhanh05/Vietnam_legal_embeddings` (Vietnamese legal-specific)
- **Package Manager:** uv (fast, modern)

**Databases:**
- **PostgreSQL 15+:** Document metadata và structured data
- **Qdrant:** Vector database cho dense embeddings
- **OpenSearch 3.6:** Full-text search (BM25)
- **Neo4j 5.25+:** Graph database cho quan hệ pháp lý

**Frontend:**
- **Framework:** Next.js 14+ (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS
- **Real-time:** Server-Sent Events (SSE)

### 1. Clone repository

```bash
git clone https://github.com/baeGil/build-project-104.git
cd build-project-104
```

### 2. Setup Backend (Python)

```bash
# Install Python dependencies
uv sync

# Copy environment file
cp .env.example .env

# Edit .env với cấu hình của bạn
# Ít nhất cần set:
# - GROQ_API_KEY: API key từ https://console.groq.com
# - Database URLs (nếu dùng Docker, giữ mặc định)
nano .env  # hoặc dùng editor bất kỳ
```

### 3. Start Infrastructure (Docker)

```bash
# Start all services
docker-compose up -d

# Services sẽ chạy tại:
# - PostgreSQL: localhost:5432
# - Qdrant: localhost:6333
# - OpenSearch: localhost:9200
# - Neo4j: localhost:7687
# - Neo4j Browser: http://localhost:7474

# Check health
docker-compose ps

# View logs
docker-compose logs -f postgres  # hoặc qdrant, opensearch, neo4j
```

### 4. Initialize Database

```bash
# Create database and tables
uv run python database/init_db.py

# Verify setup
uv run python database/verify_db.py
```

### 5. Ingest Legal Dataset (Optional nhưng recommended)

```bash
# Ingest Vietnamese legal documents from HuggingFace
# ~1,146 documents, takes ~10-15 minutes
uv run python scripts/ingest_dataset.py

# Hoặc dùng ultra-fast version (optimized with Polars)
uv run python scripts/ingest_ultra_fast.py

# Check ingestion status
uv run python database/check_docs.py

# Dataset được sử dụng:
# - Source: HuggingFace Vietnamese Legal Documents
# - Embeddings: Quockhanh05/Vietnam_legal_embeddings
# - Documents: Luật, Nghị định, Thông tư, Văn bản pháp lý
```

### 6. Start Backend API

```bash
# Development mode (with auto-reload)
uv run uvicorn apps.review_api.main:app --host 0.0.0.0 --port 8000 --reload

# Production mode
uv run uvicorn apps.review_api.main:app --host 0.0.0.0 --port 8000 --workers 4

# API sẽ chạy tại: http://localhost:8000
# API Docs: http://localhost:8000/docs
# Health check: http://localhost:8000/api/v1/health
```

### 7. Start Frontend (Next.js)

```bash
cd apps/web-app

# Install dependencies
npm install

# Development mode
npm run dev

# Production build
npm run build
npm start

# Frontend sẽ chạy tại: http://localhost:3000
```

## 📖 Sử dụng

### Cách 1: Qua Web UI (Recommended)

1. Mở browser: `http://localhost:3000`
2. **Review contract:** Upload hợp đồng → Xem phân tích
3. **Chat:** Hỏi câu hỏi pháp lý → Nhận câu trả lời với trích dẫn
4. **Ingest:** Theo dõi tiến trình ingestion dataset

### Cách 2: Qua API

```bash
# Review contract
curl -X POST http://localhost:8000/api/v1/review/contracts \
  -H "Content-Type: application/json" \
  -d '{
    "contract_text": "HỢP ĐỒNG MUA BÁN HÀNG HÓA\nĐIỀU 1: ..."
  }'

# Streaming review (real-time progress)
curl -X POST http://localhost:8000/api/v1/review/contracts/stream \
  -H "Content-Type: application/json" \
  -d '{
    "contract_text": "HỢP ĐỒNG MUA BÁN HÀNG HÓA\n..."
  }'

# Legal chat
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Thời hạn thử việc tối đa theo luật lao động?"
  }'

# Health check
curl http://localhost:8000/api/v1/health
```

### Cách 3: Qua Python SDK

```python
import asyncio
from packages.reasoning.review_pipeline import ContractReviewPipeline
from packages.common.config import get_settings

async def review_contract():
    settings = get_settings()
    pipeline = ContractReviewPipeline(settings)
    
    contract_text = """
    HỢP ĐỒNG MUA BÁN HÀNG HÓA
    ĐIỀU 1: Hàng hóa - Thiết bị văn phòng
    ...
    """
    
    result = await pipeline.review_contract(contract_text)
    
    for finding in result.findings:
        print(f"Risk: {finding.risk_level}")
        print(f"Confidence: {finding.confidence}%")
        print(f"Rationale: {finding.rationale}")
        print(f"Suggestion: {finding.revision_suggestion}")
        print("-" * 80)

asyncio.run(review_contract())
```

## Cấu trúc project

```
build-project-104/
├── apps/
│   ├── review_api/          # Backend FastAPI
│   │   ├── main.py         # Entry point
│   │   ├── routes/         # API endpoints
│   │   │   ├── review.py   # Contract review
│   │   │   ├── chat.py     # Legal chat
│   │   │   ├── ingest.py   # Document ingestion
│   │   │   └── dataset_ingestion.py  # HuggingFace ingestion
│   │   └── middleware/     # Request middleware
│   │
│   └── web-app/            # Frontend Next.js
│       ├── src/
│       │   ├── app/        # Pages (review, chat, ingest)
│       │   ├── components/ # UI components
│       │   └── lib/        # API client, types
│       └── package.json
│
├── packages/               # Core Python packages
│   ├── common/            # Config, types, utilities
│   ├── retrieval/         # Hybrid search, embeddings
│   ├── reasoning/         # LLM generation, verification
│   ├── ingestion/         # Document parsing, indexing
│   └── graph/             # Neo4j graph operations
│
├── database/              # Database setup scripts
│   ├── init.sql          # SQL schema
│   ├── init_db.py        # Database initialization
│   └── ingest_huggingface.py  # Dataset ingestion
│
├── scripts/               # Utility scripts
│   ├── ingest_dataset.py      # CLI ingestion
│   ├── ingest_ultra_fast.py   # Fast ingestion
│   └── test_*.py             # Testing scripts
│
├── tests/                 # Test suite
│   ├── test_api_*.py     # API endpoint tests
│   └── test_*.py         # Package tests
│
├── docker/                # Docker configurations
│   └── qdrant/Dockerfile
│
├── docker-compose.yml     # Infrastructure services
├── pyproject.toml         # Python dependencies
├── uv.lock               # Locked dependencies
└── .env.example          # Environment template
```

## Configuration

### Environment Variables (.env)

```bash
# LLM Provider (Required) - Groq API
GROQ_API_KEY=your_api_key_here
GROQ_MODEL_PRIMARY=llama-3.1-8b-instant      # Fast model (recommended)
GROQ_MODEL_FALLBACK=llama-3.3-70b-versatile  # Higher quality fallback

# Embedding Model (Vietnamese Legal)
EMBEDDING_MODEL=Quockhanh05/Vietnam_legal_embeddings

# Database URLs (Default: Docker services)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/legal_review
QDRANT_URL=http://localhost:6333
OPENSEARCH_URL=http://localhost:9200
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=admin
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password

# App Settings
APP_HOST=0.0.0.0
APP_PORT=8000
APP_ENV=development
```

### Performance Tuning

```bash
# Default configuration (balanced speed + quality)
GROQ_MODEL_PRIMARY=llama-3.1-8b-instant      # ~2-5s per clause
GROQ_MODEL_FALLBACK=llama-3.3-70b-versatile  # ~5-10s per clause

# For higher quality (slower, uses more tokens)
GROQ_MODEL_PRIMARY=llama-3.3-70b-versatile
GROQ_MODEL_FALLBACK=mixtral-8x7b-32768

# For maximum speed (lower quality)
GROQ_MODEL_PRIMARY=gemma2-9b-it
GROQ_MODEL_FALLBACK=llama-3.1-8b-instant

# Production: Upgrade Groq plan to avoid rate limiting
# https://console.groq.com/settings/billing
# Free tier: 8,000 TPM, 100,000 TPD
# Dev tier: Higher limits
```

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_api_review.py -v

# Run with coverage
uv run pytest tests/ --cov=packages --cov-report=html

# Run API tests only
uv run pytest tests/test_api_*.py -v

# Run package tests only
uv run pytest tests/test_*.py -v --ignore=tests/test_api_*.py
```

## Monitoring

```bash
# Prometheus metrics
http://localhost:8000/metrics

# Health check
http://localhost:8000/api/v1/health

# API documentation (Swagger)
http://localhost:8000/docs

# API documentation (ReDoc)
http://localhost:8000/redoc
```

## Troubleshooting

### Issue: API không start được

```bash
# Check if Docker services are running
docker-compose ps

# Check database connectivity
uv run python database/verify_db.py

# View API logs
uv run uvicorn apps.review_api.main:app --log-level debug
```

### Issue: LLM rate limiting (429 errors)

```bash
# Solution 1: Use faster model (less tokens)
# Edit .env:
GROQ_MODEL_PRIMARY=llama-3.3-70b-versatile

# Solution 2: Upgrade Groq plan
# https://console.groq.com/settings/billing

# Solution 3: Wait for rate limit to reset
# Check error message for wait time
```

### Issue: Embedding model load chậm (cold start)

**Đã fix!** Warmup query runs on startup, first request sẽ fast.

```bash
# Nếu vẫn chậm, pre-download model:
uv run python scripts/download_embedding_model.py
```

### Issue: Frontend không connect được backend

```bash
# Check CORS settings in apps/review_api/main.py
# Ensure ALLOWED_ORIGINS includes http://localhost:3000

# Restart both services
# Terminal 1: Backend
uv run uvicorn apps.review_api.main:app --reload

# Terminal 2: Frontend
cd apps/web-app && npm run dev
```

### Issue: Database connection refused

```bash
# Restart PostgreSQL
docker-compose restart postgres

# Check connection
psql -h localhost -U postgres -d legal_review

# Reinitialize if needed
uv run python database/init_db.py
```

## Tài liệu chi tiết

- [Database Setup Guide](DATABASE_SETUP.md) - Chi tiết setup PostgreSQL
- [Neo4j Setup Guide](NEO4J_SETUP.md) - Graph database configuration
- [Dataset Ingestion Guide](DATASET_INGESTION_GUIDE.md) - Ingest HuggingFace datasets
- [HuggingFace Troubleshooting](HUGGINGFACE_MODEL_TROUBLESHOOTING.md) - Model loading issues

## Contributing

1. Fork repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'feat: Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

### Development Workflow

```bash
# Create new branch
git checkout -b feature/your-feature

# Make changes and test
uv run pytest tests/ -v

# Commit with conventional commit messages
# feat: for new features
# fix: for bug fixes
# docs: for documentation
# test: for tests
# chore: for maintenance

git add .
git commit -m "feat: Your feature description"

# Push and create PR
git push origin feature/your-feature
```

## License

MIT License - xem [LICENSE](LICENSE) file

## 👥 Team

Developed with for Vietnamese legal community

## Acknowledgments

- **Groq** - Ultra-fast LLM inference (Llama 3.1 8B, Llama 3.3 70B)
- **HuggingFace** - Vietnamese legal datasets and embedding models
- **Quockhanh05** - Vietnam_legal_embeddings model
- **Qdrant** - Vector database for semantic search
- **OpenSearch** - Full-text BM25 search engine
- **Neo4j** - Graph database for legal relationships
- **FastAPI** - Modern async Python web framework
- **Next.js** - React framework with App Router
- **uv** - Extremely fast Python package manager
- **Polars** - Fast DataFrame library for data processing

---

**Support:** Open an issue on GitHub hoặc liên hệ team

**Status:** Production Ready
