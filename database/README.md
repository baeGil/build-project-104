# Database Initialization

This directory contains scripts for initializing and managing the PostgreSQL database.

## Files

- `init.sql` - SQL script to create the necessary tables and indexes
- `init_db.py` - Python script to initialize the database
- `verify_db.py` - Python script to verify the database setup
- `add_sample_data.py` - Python script to add sample legal documents for testing
- `check_docs.py` - Quick script to check documents in the database

## Tables

### legal_documents

Stores legal documents with the following structure:

| Column     | Type                      | Description                    |
|------------|---------------------------|--------------------------------|
| id         | VARCHAR(255)              | Primary key, document ID       |
| content    | TEXT                      | Document content               |
| title      | TEXT                      | Document title                 |
| doc_type   | VARCHAR(100)              | Type of legal document         |
| metadata   | JSONB                     | Additional metadata            |
| created_at | TIMESTAMP WITH TIME ZONE  | Creation timestamp             |
| updated_at | TIMESTAMP WITH TIME ZONE  | Last update timestamp          |

## Indexes

- `idx_legal_documents_doc_type` - Index on doc_type for faster filtering
- `idx_legal_documents_created_at` - Index on created_at for time-based queries
- `idx_legal_documents_metadata` - GIN index on metadata for JSON queries

## Usage

### Option 1: Docker Compose (Recommended)

The database will be automatically initialized when you start the services with Docker Compose:

```bash
docker-compose up -d postgres
```

The init.sql script is mounted to `/docker-entrypoint-initdb.d/init.sql`, which PostgreSQL executes on first startup.

### Option 2: Manual Initialization

If you're running PostgreSQL locally or need to reinitialize:

```bash
python database/init_db.py
```

### Verify Setup

To verify the database setup:

```bash
python database/verify_db.py
```

### Add Sample Data

To add sample legal documents for testing:

```bash
python database/add_sample_data.py
```

### Check Documents

To quickly check what documents are in the database:

```bash
python database/check_docs.py
```

## Environment Variables

The database connection is configured via environment variables in `.env`:

- `POSTGRES_HOST` - Database host (default: localhost)
- `POSTGRES_PORT` - Database port (default: 5432)
- `POSTGRES_DB` - Database name (default: legal_review)
- `POSTGRES_USER` - Database user (default: postgres)
- `POSTGRES_PASSWORD` - Database password (default: postgres)
