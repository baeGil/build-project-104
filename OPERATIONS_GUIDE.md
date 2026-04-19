# 📋 Vietnamese Legal AI - Operations Guide

Chi tiết tất cả commands và scripts để vận hành hệ thống.

---

## 🚀 QUICK START

### 1. Setup Environment
```bash
cd "/Users/AI/Vinuni/build project qoder"
source .venv/bin/activate
```

### 2. Start Services (Docker)
```bash
# Start all databases
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 3. Ingest Data
```bash
# Ingest with limit
uv run python scripts/ingest_dataset.py --limit 115

# Ingest all available
uv run python scripts/ingest_dataset.py

# Monitor progress
tail -f ingest.log
```

---

## 🗄️ DATABASE MANAGEMENT

### Cleanup All Databases
```bash
# Complete cleanup (WARNING: Deletes ALL data)
uv run python scripts/cleanup_all_databases.py
# Type 'YES' to confirm

# This cleans:
# - PostgreSQL (legal_documents, document_relationships)
# - Neo4j (all nodes and relationships)
# - Qdrant (entire collection)
# - OpenSearch (entire index)
```

### Cleanup Test Documents Only
```bash
# Remove test/sample documents, keep real legal docs
uv run python scripts/cleanup_all_test_docs.py

# This removes:
# - Documents with UUID-style IDs
# - Documents with titles like "Test Document", "Document 1", etc.
# - Keeps documents with numeric IDs (real legal documents)
```

### Force Cleanup Specific Databases
```bash
# Neo4j only - Remove non-numeric ID documents
uv run python scripts/force_cleanup_neo4j.py

# Qdrant only - Remove UUID-style law_id points
uv run python scripts/force_cleanup_qdrant.py
```

---

## 📊 HEALTH CHECKS & VERIFICATION

### Comprehensive Database Health Check
```bash
# Quick health check (recommended)
uv run python scripts/comprehensive_db_check.py

# Output shows:
# - PostgreSQL: documents, relationships, coverage
# - Neo4j: documents, articles, subsections, relationships
# - Qdrant: total points, vector dimension
# - OpenSearch: indexed documents
# - Issues and warnings
```

### Data Quality Test
```bash
# Detailed data quality analysis
uv run python scripts/test_data_quality.py

# Tests:
# ✅ PostgreSQL: ID consistency, content quality, relationships
# ✅ Neo4j: Node counts, relationship integrity, duplicates
# ✅ Qdrant: Payload validation, chunk distribution, duplicates
# ✅ OpenSearch: Index count, consistency
# ✅ Cross-DB consistency checks
```

### Analyze Data Quality
```bash
# Deep dive into data quality metrics
uv run python scripts/analyze_data_quality.py

# Analyzes:
# - Content length distribution
# - Document type distribution
# - Relationship patterns
# - Indexing ratios
# - Cross-database consistency
```

---

## 🔍 DIAGNOSTICS & TROUBLESHOOTING

### Check Neo4j Relationships
```bash
# Check for duplicate relationships
uv run python scripts/check_neo4j_relationships.py

# Output:
# - Total relationships
# - Duplicate groups (if any)
# - Relationship type distribution
# - RELATES_TO property analysis
```

### Fix Neo4j Duplicates
```bash
# Remove duplicate relationships (keep oldest by created_at)
uv run python scripts/fix_neo4j_duplicates.py

# This:
# - Finds true duplicates (same source, target, AND type property)
# - Deletes duplicates, keeps first created
# - Verifies no duplicates remain
# - Shows final relationship distribution
```

### Check Existing Documents
```bash
# Check which documents exist in database
uv run python scripts/check_existing_docs.py

# Shows:
# - Documents in PostgreSQL
# - Documents in Neo4j
# - Missing documents
# - Duplicate documents
```

### Check Index Counts
```bash
# Verify index counts across all databases
uv run python scripts/check_index_counts.py

# Compares:
# - PostgreSQL document count
# - Neo4j node count
# - Qdrant point count
# - OpenSearch document count
```

### Diagnose Missing Documents
```bash
# Debug why documents are missing from search results
uv run python scripts/diagnose_missing_docs.py

# Checks:
# - Documents in DB but not in index
# - Indexing failures
# - Parsing errors
# - Relationship issues
```

### Comprehensive Verification
```bash
# Full system verification
uv run python scripts/comprehensive_verification.py

# Verifies:
# - All databases operational
# - Data consistency
# - Search functionality
# - API endpoints
```

---

## 🧪 TESTING

### Quick Test
```bash
# Fast basic functionality test
uv run python scripts/quick_test.py

# Tests:
# - Database connectivity
# - Basic search
# - Simple ingestion
```

### Retrieval Quality Test
```bash
# Test retrieval system with Vietnamese legal queries
uv run python scripts/test_retrieval.py

# Tests:
# - Semantic search (Qdrant)
# - Full-text search (OpenSearch BM25)
# - Hybrid search (RRF)
# - Ranking quality
# - Latency
```

### Comprehensive Test
```bash
# Full system test with multiple scenarios
uv run python scripts/test_comprehensive.py

# Tests:
# - Multiple contract types
# - Various query difficulties
# - Edge cases
# - Performance metrics
```

### Ground Truth Test
```bash
# Validate against expected outputs
uv run python scripts/test_groundtruth.py

# Validates:
# - Retrieval accuracy
# - Citation correctness
# - Response quality
# - Compliance with expected results
```

### Extremely Difficult Test
```bash
# Test with very difficult queries
uv run python scripts/test_extremely_difficult.py

# Tests:
# - Complex multi-part questions
# - Ambiguous queries
# - Cross-document reasoning
# - Edge cases
```

### API Latency Test
```bash
# Test API response times
uv run python scripts/test_api_latency.py

# Measures:
# - Endpoint response times
# - P50, P95, P99 latencies
# - Throughput
# - Error rates
```

### Profile Chat Latency
```bash
# Detailed latency profiling for chat endpoint
uv run python scripts/profile_chat_latency.py

# Profiles:
# - Retrieval time
# - LLM generation time
# - Total response time
# - Bottleneck identification
```

### Test with Detailed Timing
```bash
# Detailed timing for each pipeline stage
uv run python scripts/test_with_detailed_timing.py

# Times:
# - Query parsing
# - Retrieval
# - Reranking
# - RRF fusion
# - Response generation
```

---

## 📈 ANALYSIS & REPORTING

### Analyze Ground Truth
```bash
# Analyze ground truth test results
uv run python scripts/analyze_groundtruth.py

# Analyzes:
# - Precision/Recall
# - F1 scores
# - Per-category performance
# - Error patterns
```

### Analyze Search Performance
```bash
# Deep dive into search performance
uv run python scripts/analyze_search_performance.py

# Metrics:
# - Search accuracy
# - Ranking quality
# - Relevance scores
# - Performance bottlenecks
```

### Trace RRF Scoring
```bash
# Debug Reciprocal Rank Fusion scoring
uv run python scripts/trace_rrf.py

# Shows:
# - BM25 scores
# - Vector scores
# - RRF calculation
# - Final ranking
```

---

## 🔄 REINDEXING

### Reindex with Articles
```bash
# Reindex with article-level granularity
uv run python scripts/reindex_with_articles.py

# This:
# - Drops existing indexes
# - Reindexes at article level
# - Updates Qdrant and OpenSearch
# - Preserves hierarchical structure
```

### Simulate Pipeline
```bash
# Simulate full pipeline without executing
uv run python scripts/simulate_pipeline.py

# Simulates:
# - Ingestion flow
# - Indexing process
# - Search workflow
# - Expected outputs
```

---

## 🌐 API USAGE

### Start API Server
```bash
# Start FastAPI server
uvicorn apps.review_api.main:app --reload --host 0.0.0.0 --port 8000

# Or using the script
./apps/web-app/start-dev.sh
```

### Test API Endpoints
```bash
# Health check
curl http://localhost:8000/health

# Contract review
curl -X POST http://localhost:8000/api/v1/review \
  -H "Content-Type: application/json" \
  -d '{
    "contract_text": "Your contract text here...",
    "max_issues": 5
  }'

# Chat endpoint
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Câu hỏi về pháp luật Việt Nam",
    "session_id": "test-session"
  }'
```

---

## 📊 COMMON WORKFLOWS

### Workflow 1: Fresh Start
```bash
# 1. Clean everything
uv run python scripts/cleanup_all_databases.py

# 2. Ingest data
uv run python scripts/ingest_dataset.py --limit 115

# 3. Verify
uv run python scripts/comprehensive_db_check.py

# 4. Test quality
uv run python scripts/test_data_quality.py
```

### Workflow 2: Debug Search Issues
```bash
# 1. Check indexes
uv run python scripts/check_index_counts.py

# 2. Diagnose missing docs
uv run python scripts/diagnose_missing_docs.py

# 3. Test retrieval
uv run python scripts/test_retrieval.py

# 4. Trace RRF
uv run python scripts/trace_rrf.py
```

### Workflow 3: Fix Neo4j Duplicates
```bash
# 1. Check for duplicates
uv run python scripts/check_neo4j_relationships.py

# 2. Fix if found
uv run python scripts/fix_neo4j_duplicates.py

# 3. Verify
uv run python scripts/check_neo4j_relationships.py
```

### Workflow 4: Performance Testing
```bash
# 1. API latency
uv run python scripts/test_api_latency.py

# 2. Profile chat
uv run python scripts/profile_chat_latency.py

# 3. Detailed timing
uv run python scripts/test_with_detailed_timing.py

# 4. Analyze results
uv run python scripts/analyze_search_performance.py
```

### Workflow 5: Quality Assurance
```bash
# 1. Health check
uv run python scripts/comprehensive_db_check.py

# 2. Data quality
uv run python scripts/test_data_quality.py

# 3. Ground truth test
uv run python scripts/test_groundtruth.py

# 4. Analyze results
uv run python scripts/analyze_groundtruth.py
```

---

## 🎯 KEY METRICS TO MONITOR

### Database Consistency
```
PostgreSQL docs = Neo4j Document nodes
Qdrant points = OpenSearch indexed docs
Indexing ratio: 10-20x (Qdrant points / PostgreSQL docs)
Articles/doc ratio: 5-15x (Neo4j articles / PostgreSQL docs)
```

### Data Quality
```
- No test data contamination (0 UUID-style IDs)
- No duplicate relationships
- Cross-DB consistency: 100%
- Content completeness: 100%
```

### Performance
```
- API response time: < 2s (P95)
- Search latency: < 500ms (P95)
- Retrieval accuracy: > 80%
- Ground truth match: > 90%
```

---

## ⚠️ IMPORTANT NOTES

### Before Running Cleanup
```bash
# ALWAYS verify before cleanup
uv run python scripts/comprehensive_db_check.py

# Backup if needed
pg_dump -U postgres legal_ai_db > backup.sql
```

### Understanding Warnings
```
⚠️  Orphaned nodes in Neo4j (< 5%)
→ NORMAL, no action needed

⚠️  Low relationship coverage (< 10%)
→ NORMAL for Vietnamese legal documents

⚠️  High indexing ratio (> 20x)
→ Check for duplicate chunks
```

### Common Issues
```bash
# Issue: OpenSearch count mismatch
# Fix: Reindex OpenSearch
uv run python scripts/reindex_with_articles.py

# Issue: Neo4j duplicates
# Fix: Run deduplication
uv run python scripts/fix_neo4j_duplicates.py

# Issue: Missing documents
# Fix: Diagnose and reindex
uv run python scripts/diagnose_missing_docs.py
```

---

## 📚 ADDITIONAL RESOURCES

### Documentation Files
- `SCRIPTS_GUIDE.md` - Detailed script documentation
- `QUICK_TEST_GUIDE.md` - Quick testing guide
- `TEST_ANALYSIS_SUMMARY.md` - Test analysis results
- `CHUNKING_IMPACT_ANALYSIS.md` - Chunking strategy analysis

### Test Outputs
- `test_*.json` - Test result files
- `output_test_contract_*.json` - Contract review outputs
- `EXPECTED_*.json` - Expected validation outputs

---

## 🆘 TROUBLESHOOTING

### Database Connection Issues
```bash
# Check Docker
docker-compose ps

# Restart services
docker-compose restart

# Check logs
docker-compose logs postgresql
docker-compose logs neo4j
docker-compose logs qdrant
docker-compose logs opensearch
```

### Ingestion Failures
```bash
# Check logs
tail -f ingest.log

# Verify source data
ls -lh data/cache/datasets/

# Test with small batch
uv run python scripts/ingest_dataset.py --limit 10
```

### Search Issues
```bash
# Verify indexes
uv run python scripts/check_index_counts.py

# Test search directly
uv run python scripts/test_retrieval.py

# Check RRF scoring
uv run python scripts/trace_rrf.py
```

---

## ✅ VERIFICATION CHECKLIST

After any major operation:

```bash
# 1. Health check
uv run python scripts/comprehensive_db_check.py
# Expected: 0 issues, 0-1 warnings

# 2. Data quality
uv run python scripts/test_data_quality.py
# Expected: ALL TESTS PASSED

# 3. Search test
uv run python scripts/test_retrieval.py
# Expected: Good results for all queries

# 4. API test
curl http://localhost:8000/health
# Expected: {"status": "ok"}
```

---

**Last Updated:** 2026-04-18
**Version:** 1.0
**Status:** Production Ready ✅
