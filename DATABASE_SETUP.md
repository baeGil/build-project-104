# Database Setup and Error Resolution

## Issue Resolved

**Error**: `relation "legal_documents" does not exist`

This error occurred because the PostgreSQL database table `legal_documents` had not been created.

## Solution

### 1. Database Initialization Scripts Created

Created the `/database` directory with the following files:

- **init.sql**: SQL script to create the `legal_documents` table and indexes
- **init_db.py**: Python script to initialize the database programmatically
- **verify_db.py**: Python script to verify database setup
- **add_sample_data.py**: Python script to add sample legal documents for testing
- **check_docs.py**: Quick script to check documents in the database
- **README.md**: Documentation for database setup and usage

### 2. Table Structure

The `legal_documents` table has been created with the following structure:

```sql
CREATE TABLE legal_documents (
    id VARCHAR(255) PRIMARY KEY,
    content TEXT NOT NULL,
    title TEXT,
    doc_type VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes created**:
- `idx_legal_documents_doc_type` - For filtering by document type
- `idx_legal_documents_created_at` - For time-based queries
- `idx_legal_documents_metadata` - GIN index for JSON queries

### 3. Docker Compose Integration

Updated `docker-compose.yml` to automatically initialize the database on first startup:

```yaml
volumes:
  - postgres_data:/var/lib/postgresql/data
  - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
```

### 4. Ingestion Pipeline Updated

Modified `/packages/ingestion/pipeline.py` to:
- Store documents in PostgreSQL during ingestion
- Manage PostgreSQL connection pool
- Provide cleanup method to close connections

The pipeline now stores documents in three places:
1. **PostgreSQL** - For metadata and full document storage
2. **Qdrant** - For vector search
3. **OpenSearch** - For BM25 full-text search

### 5. API Routes Updated

Updated `/apps/review_api/routes/ingest.py` to:
- Properly close pipeline connections after ingestion
- Use try/finally blocks to ensure cleanup

## Database Status

✅ Database initialized successfully
✅ Table `legal_documents` created
✅ Indexes created
✅ Sample data added (3 Vietnamese legal documents)
✅ Ingestion pipeline updated to store in PostgreSQL
✅ Docker Compose configured for automatic initialization

## How to Use

### Initialize Database (if needed)

```bash
python database/init_db.py
```

### Verify Setup

```bash
python database/verify_db.py
```

### Add Sample Data

```bash
python database/add_sample_data.py
```

### Check Documents

```bash
python database/check_docs.py
```

### Restart with Docker Compose

If using Docker, the database will be initialized automatically:

```bash
docker-compose up -d postgres
```

## Next Steps

The error should now be resolved. The system will:
1. Store all ingested documents in PostgreSQL
2. Index documents in Qdrant for vector search
3. Index documents in OpenSearch for BM25 search
4. Retrieve documents from PostgreSQL during hybrid search

## Files Modified

1. `/database/init.sql` (created)
2. `/database/init_db.py` (created)
3. `/database/verify_db.py` (created)
4. `/database/add_sample_data.py` (created)
5. `/database/check_docs.py` (created)
6. `/database/README.md` (created)
7. `/docker-compose.yml` (updated)
8. `/packages/ingestion/pipeline.py` (updated)
9. `/apps/review_api/routes/ingest.py` (updated)
