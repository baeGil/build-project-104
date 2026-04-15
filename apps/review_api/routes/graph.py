"""Administrative routes for Neo4j graph synchronization."""

import logging

from fastapi import APIRouter, HTTPException, Query, Request, status

from packages.common.config import get_settings
from packages.graph.sync import GraphSyncService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["graph"])


@router.get(
    "/graph/health",
    summary="Check Neo4j graph health",
    description="Verify Neo4j connectivity and schema availability.",
)
async def graph_health(request: Request) -> dict:
    """Return graph health information."""
    graph_client = getattr(request.app.state, "graph_client", None)
    if graph_client is None:
        return {"status": "unavailable"}

    healthy = await graph_client.ping()
    return {"status": "ok" if healthy else "unhealthy"}


@router.post(
    "/graph/sync",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Sync PostgreSQL documents into Neo4j",
    description="Backfill the legal document graph in Neo4j from already-ingested PostgreSQL documents.",
)
async def sync_graph(
    request: Request,
    limit: int | None = Query(default=None, ge=1, le=5000),
) -> dict:
    """Sync existing documents from PostgreSQL to Neo4j."""
    settings = get_settings()
    graph_sync = getattr(request.app.state, "graph_sync", None)
    owns_service = False

    if graph_sync is None:
        graph_sync = GraphSyncService(settings)
        owns_service = True

    try:
        stats = await graph_sync.sync_existing_documents(limit=limit)
        return {
            "status": "completed",
            "limit": limit,
            "stats": stats,
        }
    except Exception as e:
        logger.error("Graph sync failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph sync failed: {e}",
        )
    finally:
        if owns_service:
            await graph_sync.close()
            await graph_sync.graph_client.close()
