# Dataset Ingestion System

Complete dataset ingestion system with progress tracking and monitoring UI.

## Features

✅ **Background Task Processing** - Runs asynchronously without blocking the API
✅ **Real-time Progress Tracking** - Monitor download, processing, and ingestion progress
✅ **Task Management** - Start, monitor, and cancel ingestion tasks
✅ **Beautiful UI** - Web interface with live progress bars and status updates
✅ **Error Handling** - Graceful error recovery and detailed error messages
✅ **Auto-polling** - UI automatically refreshes when tasks are active

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend UI                             │
│              (/dataset-ingest)                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  • Start ingestion form                              │   │
│  │  • Real-time progress bars                           │   │
│  │  • Task list with status                             │   │
│  │  • Auto-refresh every 2s                             │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                           ↓ HTTP
┌─────────────────────────────────────────────────────────────┐
│                     Backend API                              │
│                                                              │
│  POST /api/v1/ingest/dataset/start   → Create task          │
│  GET  /api/v1/ingest/dataset/status/:id → Get progress      │
│  GET  /api/v1/ingest/dataset/tasks   → List all tasks       │
│  POST /api/v1/ingest/dataset/cancel/:id → Cancel task       │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                  Task Manager                                │
│                                                              │
│  • Creates IngestionTask with unique ID                     │
│  • Manages background execution                             │
│  • Tracks progress state                                    │
│  • Handles cancellation                                     │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                  Dataset Downloader                          │
│                                                              │
│  Phase 1: Download from HuggingFace                         │
│    • Load metadata config (streaming)                       │
│    • Load content config (streaming)                        │
│                                                              │
│  Phase 2: Process & Merge                                   │
│    • Clean HTML to text                                     │
│    • Merge metadata with content                            │
│    • Build document objects                                 │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                  Ingestion Pipeline                          │
│                                                              │
│  • PostgreSQL (metadata storage)                            │
│  • Qdrant (vector embeddings)                               │
│  • OpenSearch (BM25 search)                                 │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Start the Backend

```bash
cd "/Users/AI/Vinuni/build project qoder"
uvicorn apps.review_api.main:app --reload --port 8000
```

### 2. Start the Frontend

```bash
cd apps/web-app
npm run dev
```

### 3. Access the UI

Open: http://localhost:3000/dataset-ingest

### 4. Start Ingestion

1. Enter number of documents (e.g., 50 for testing)
2. Click "Start Ingestion"
3. Watch real-time progress!

## API Endpoints

### Start Ingestion

```bash
POST /api/v1/ingest/dataset/start?limit=50

Response:
{
  "task_id": "abc123...",
  "status": "queued",
  "limit": 50,
  "message": "Dataset ingestion started. Use task_id to track progress."
}
```

### Get Task Status

```bash
GET /api/v1/ingest/dataset/status/{task_id}

Response:
{
  "task_id": "abc123...",
  "limit": 50,
  "status": "downloading",  // queued, downloading, processing, ingesting, completed, failed, cancelled
  "progress": {
    "status": "downloading",
    "current_step": "Loading content",
    "current_item": 25,
    "total_items": 50,
    "percentage": 50.0,
    "message": "Downloading content data...",
    "elapsed_seconds": 45.5,
    "error": null
  },
  "created_at": 1234567890,
  "started_at": 1234567891,
  "completed_at": null,
  "result": null,
  "error": null
}
```

### List Tasks

```bash
GET /api/v1/ingest/dataset/tasks?limit=20

Response: [ ...array of task objects... ]
```

### Cancel Task

```bash
POST /api/v1/ingest/dataset/cancel/{task_id}

Response:
{
  "task_id": "abc123...",
  "status": "cancelling",
  "message": "Task cancellation requested"
}
```

## Task Statuses

| Status | Description | Color |
|--------|-------------|-------|
| `queued` | Task is waiting to start | Indigo |
| `downloading` | Downloading from HuggingFace | Blue |
| `processing` | Cleaning and merging data | Yellow |
| `ingesting` | Inserting into databases | Purple |
| `completed` | Successfully finished | Green |
| `failed` | Error occurred | Red |
| `cancelled` | User cancelled | Gray |

## File Structure

```
packages/ingestion/
├── dataset_downloader.py    # Download & process HuggingFace dataset
└── task_manager.py          # Task management & state tracking

apps/review_api/routes/
└── dataset_ingestion.py     # API endpoints

apps/web-app/src/
├── app/dataset-ingest/
│   └── page.tsx             # Monitoring UI
├── components/
│   └── Sidebar.tsx          # Added dataset ingestion link
└── lib/
    └── api.ts               # Added ingestionApi client
```

## Troubleshooting

### Issue: Download is slow
**Solution**: First download caches locally. Subsequent runs will be much faster.

### Issue: Task stuck at "downloading"
**Solution**: This is normal for large datasets. HuggingFace parquet files must be fully downloaded before processing starts.

### Issue: Task failed with error
**Solution**: Check the error message in the UI. Common issues:
- Database connection failed → Check PostgreSQL is running
- Qdrant unavailable → Check Docker containers
- HuggingFace rate limit → Wait and retry, or set HF_TOKEN

### Issue: UI not updating
**Solution**: UI auto-refreshes every 2 seconds when active tasks exist. Manually refresh the page if needed.

## Performance Tips

1. **Test with small batches first**: Start with 5-10 documents
2. **Run overnight for large datasets**: 500+ documents may take hours
3. **Monitor system resources**: Check CPU, memory, disk usage
4. **Check database storage**: Ensure PostgreSQL has enough disk space

## Environment Variables

Make sure these are set in `.env`:

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=legal_review
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

# OpenSearch
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200

# HuggingFace (optional but recommended)
HF_TOKEN=your_token_here
```

## Next Steps

- [ ] Add email notifications on completion
- [ ] Implement chunked parquet downloads
- [ ] Add dataset preview before ingestion
- [ ] Support multiple dataset sources
- [ ] Add ingestion history and analytics
