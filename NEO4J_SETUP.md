# Neo4j Setup

## 1. Start Neo4j

```bash
docker compose up -d neo4j
docker compose ps
```

Neo4j services:

- Browser UI: `http://localhost:7474`
- Bolt: `bolt://localhost:7687`
- Default user: `neo4j`
- Default password: `password`

## 2. Start the backend

```bash
uv run uvicorn apps.review_api.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/graph/health
```

## 3. Backfill existing documents into Neo4j

If PostgreSQL already contains legal documents, sync them into the graph:

```bash
python database/sync_neo4j.py
```

To limit the sync size while testing:

```bash
python database/sync_neo4j.py --limit 20
```

You can also trigger sync through the API:

```bash
curl -X POST "http://localhost:8000/api/v1/graph/sync?limit=20"
```

## 4. New ingestion flow

New documents ingested through the project pipeline are now written to:

- PostgreSQL
- Qdrant
- OpenSearch
- Neo4j

This means Neo4j no longer needs manual sync for newly ingested documents.

## 5. What Neo4j contains

The graph sync creates:

- `Document` nodes
- `Article` nodes
- `Subsection` nodes
- `CONTAINS` edges
- `HAS_SUBSECTION` edges
- best-effort `REFERENCES`, `CITES`, and `AMENDED_BY` edges

## 6. Common checks

Open Neo4j Browser and run:

```cypher
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS total ORDER BY total DESC;
```

```cypher
MATCH (d:Document)-[:CONTAINS]->(a:Article)
RETURN d.title, count(a) AS article_count
ORDER BY article_count DESC
LIMIT 10;
```

```cypher
MATCH ()-[r]->()
RETURN type(r) AS relation, count(*) AS total
ORDER BY total DESC;
```

## 7. Environment variables

Defaults already work with Docker Compose:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```
