# Vietnamese Legal Contract Review AI System

AI-powered system for reviewing Vietnamese legal contracts with citation-backed analysis.

## Features

- Contract review with risk assessment
- Legal citation retrieval
- Chat-based legal consultation
- Document ingestion pipeline

## Quick Start

```bash
# Start infrastructure
docker compose up -d

# Install dependencies
pip install -e .

# Run backend
cd apps/review_api && uvicorn main:app --reload

# Run frontend (separate terminal)
cd apps/web-app && npm run dev