# 📋 Scripts Guide - Vietnamese Legal Contract Review System

## 🎯 Quick Reference

### **Production Scripts (Use These)**

| Script | Purpose | When to Use |
|--------|---------|-------------|
| **`ingest_dataset.py`** | ⭐ **MAIN INGESTION** - Production-ready | **USE THIS** for ingesting dataset |
| **`final_comprehensive_test.py`** | ⭐ **FULL PIPELINE TEST** - End-to-end testing | Test entire system with real LLM |

---

### **Legacy/Experimental Scripts (Don't Use)**

| Script | Status | Why Not Use |
|--------|--------|-------------|
| `ingest_complete.py` | ❌ Deprecated | Old version, slower |
| `ingest_ultra_fast.py` | ❌ Experimental | Unstable, not tested |

---

## 🚀 Main Scripts Usage

### 1️⃣ **Dataset Ingestion** (Most Important)

```bash
# Ingest 50 documents (for testing)
uv run python scripts/ingest_dataset.py --limit 50

# Ingest 500 documents (medium dataset)
uv run python scripts/ingest_dataset.py --limit 500 --batch-size 50

# Ingest with custom batch size
uv run python scripts/ingest_dataset.py --limit 1000 --batch-size 100
```

**What it does:**
- ✅ Downloads from HuggingFace (`th1nhng0/vietnamese-legal-documents`)
- ✅ Parses and cleans HTML content
- ✅ Stores in PostgreSQL (`legal_documents` table)
- ✅ Creates vector embeddings in Qdrant
- ✅ Indexes for BM25 search in OpenSearch
- ✅ Syncs relationships to Neo4j
- ✅ Shows real-time progress with Rich UI

**Output:**
```
┌─────────────────────────────────────┐
│  Dataset Ingestion Progress         │
├─────────────────────────────────────┤
│  Documents: ████████████░░░░ 65%    │
│  Processed: 325/500                 │
│  Time: 5m 23s                       │
│  ETA: 2m 45s                        │
└─────────────────────────────────────┘
```

---

### 2️⃣ **Comprehensive Test** (QA)

```bash
# Run full pipeline test with real LLM
uv run python scripts/final_comprehensive_test.py
```

**What it tests:**
1. ✅ Hybrid retrieval (BM25 + Dense)
2. ✅ Contract review pipeline
3. ✅ LLM generation (Vietnamese)
4. ✅ Citation accuracy
5. ✅ Performance metrics (<2s per clause)
6. ✅ Output completeness

**Output:**
```
┌────────────────────────────────────────┐
│  Test Results                          │
├────────────────────────────────────────┤
│  ✅ Retrieval: 95% accuracy            │
│  ✅ Review: 13 clauses processed       │
│  ✅ LLM: Vietnamese output correct     │
│  ✅ Citations: All valid               │
│  ⚡ Performance: 1.2s avg/clause       │
└────────────────────────────────────────┘
```

---

### 3️⃣ **Quick Start Test** (Frontend + Backend)

```bash
# Start both frontend and backend
bash scripts/quick_start_test.sh
```

**What it does:**
- ✅ Checks Docker services (PostgreSQL, Qdrant, Neo4j)
- ✅ Starts backend on port 8000
- ✅ Starts frontend on port 3000
- ✅ Opens browser automatically

---

## 📊 Other Scripts

### Test Scripts (Development)

| Script | Purpose |
|--------|---------|
| `test_contract_review.py` | Test contract review endpoint |
| `test_performance.py` | Benchmark retrieval speed |
| `test_retrieval.py` | Test hybrid search |
| `test_score_normalization.py` | Test RRF scoring |

### Utility Scripts

| Script | Purpose |
|--------|---------|
| `download_embedding_model.py` | Download Vietnam legal embeddings |

---

## 🎯 Recommended Workflow

### For New Setup:

```bash
# 1. Ingest small dataset for testing
uv run python scripts/ingest_dataset.py --limit 50

# 2. Test the system
uv run python scripts/final_comprehensive_test.py

# 3. Start frontend + backend
bash scripts/quick_start_test.sh

# 4. Open browser and test UI
# http://localhost:3000/review
```

### For Production:

```bash
# Ingest full dataset (180K+ documents)
uv run python scripts/ingest_dataset.py --limit 180000 --batch-size 100

# This will take ~2-3 hours depending on your machine
```

---

## 🗑️ Scripts to Delete (Optional)

These are old/experimental and can be safely removed:

```bash
# Old ingest scripts (replaced by ingest_dataset.py)
rm scripts/ingest_complete.py
rm scripts/ingest_ultra_fast.py
```

**Note:** Keep them if you want to compare performance or revert.

---

## 📝 Script Comparison

| Feature | ingest_dataset.py | ingest_complete.py | ingest_ultra_fast.py |
|---------|-------------------|-------------------|---------------------|
| **Status** | ✅ Production | ❌ Deprecated | ️ Experimental |
| **Speed** | Fast | Slow | Fastest (unstable) |
| **UI** | Rich progress bar | Basic | Compact UI |
| **Resume** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Parallel** | ✅ Optimized | ❌ Sequential | ✅ Aggressive |
| **Tested** | ✅ Fully | ❌ Partially | ❌ Not tested |
| **Use This?** | ⭐ **YES** | No | No |

---

## 🎓 Tips

1. **Start small**: Use `--limit 50` for testing
2. **Batch size**: Use 50-100 for best performance
3. **Resume**: If interrupted, script auto-resumes
4. **Monitor**: Watch Rich UI for progress
5. **Test**: Always run `final_comprehensive_test.py` after ingestion

---

## ❓ FAQ

**Q: Which script should I use?**
A: **`ingest_dataset.py`** - It's the production-ready one.

**Q: Can I delete the other ingest scripts?**
A: Yes, but keep them as backup until you're confident.

**Q: How long does ingestion take?**
A: 
- 50 docs: ~2 minutes
- 500 docs: ~15 minutes
- 180K docs: ~2-3 hours

**Q: What if ingestion fails?**
A: Script has resume capability - just run it again, it continues from where it stopped.

---

**Last Updated:** 2026-04-15
**Author:** AI Assistant
**Status:** ✅ Verified & Tested
