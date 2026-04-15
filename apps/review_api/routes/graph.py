"""Administrative routes for Neo4j graph synchronization and PostgreSQL relationships."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field

from packages.common.config import get_settings
from packages.graph.sync import GraphSyncService
from packages.retrieval.context import ContextInjector

logger = logging.getLogger(__name__)
router = APIRouter(tags=["graph"])


class RelationshipResponse(BaseModel):
    """Response model for document relationships."""
    doc_id: str = Field(..., description="Document ID")
    relationships: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of relationships"
    )


class RelationshipTypesResponse(BaseModel):
    """Response model for relationship types."""
    relationship_types: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of relationship types with counts"
    )


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


@router.get(
    "/graph/relationships/{doc_id}",
    response_model=RelationshipResponse,
    summary="Get document relationships",
    description="Returns all relationships for a document from PostgreSQL (primary) and Neo4j (secondary).",
)
async def get_document_relationships(
    request: Request,
    doc_id: str = Path(..., description="Document ID to get relationships for"),
    relationship_type: str | None = Query(None, description="Filter by relationship type"),
    depth: int = Query(1, ge=1, le=2, description="Graph traversal depth (1 or 2)"),
) -> RelationshipResponse:
    """Get all relationships for a document.
    
    Uses PostgreSQL as the primary source for relationships, with Neo4j as
    an optional secondary source for deeper graph traversal.
    
    Args:
        doc_id: Document ID to get relationships for
        relationship_type: Optional filter by relationship type
        depth: Graph traversal depth (default: 1, max: 2)
    
    Returns:
        RelationshipResponse with doc_id and list of relationships
    """
    settings = get_settings()
    context_injector = getattr(request.app.state, "context_injector", None)

    if context_injector is None:
        context_injector = ContextInjector(settings)

    try:
        # Build relationship types filter if provided
        relationship_types = [relationship_type] if relationship_type else None

        # Get relationship graph from PostgreSQL
        graph = await context_injector.get_document_relationship_graph(
            doc_id, depth=min(depth, 2)
        )

        relationships = graph.get("relationships", [])

        # Filter by relationship type if provided
        if relationship_type:
            relationships = [
                r for r in relationships
                if r.get("relationship_type") == relationship_type
            ]

        return RelationshipResponse(
            doc_id=doc_id,
            relationships=relationships,
        )

    except Exception as e:
        logger.error("Failed to get relationships for %s: %s", doc_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get relationships: {e}",
        )


@router.get(
    "/graph/relationship-types",
    response_model=RelationshipTypesResponse,
    summary="Get relationship types",
    description="Returns all unique relationship types with counts from PostgreSQL.",
)
async def get_relationship_types(request: Request) -> RelationshipTypesResponse:
    """Get all unique relationship types with counts.
    
    Queries PostgreSQL for all relationship types and their counts.
    
    Returns:
        RelationshipTypesResponse with list of relationship types and counts
    """
    settings = get_settings()
    context_injector = getattr(request.app.state, "context_injector", None)

    if context_injector is None:
        context_injector = ContextInjector(settings)

    try:
        # Get PostgreSQL pool
        pool = await context_injector._get_postgres_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT relationship_type, COUNT(*) as count
                FROM document_relationships
                GROUP BY relationship_type
                ORDER BY COUNT(*) DESC
                """
            )

            relationship_types = [
                {"relationship_type": row["relationship_type"], "count": row["count"]}
                for row in rows
            ]


        return RelationshipTypesResponse(
            relationship_types=relationship_types,
        )
    except Exception as e:
        logger.error("Failed to get relationship types: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get relationship types: {e}",
        )
