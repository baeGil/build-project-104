"""Citation routes for retrieving document context."""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status

from packages.common.config import Settings, get_settings
from packages.common.types import ContextDocument
from packages.graph.legal_graph import LegalGraphClient

logger = logging.getLogger(__name__)
router = APIRouter(tags=["citations"])


async def get_graph_client(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> LegalGraphClient:
    """Dependency to get graph client."""
    graph_client = getattr(request.app.state, "graph_client", None)
    if graph_client is not None:
        return graph_client
    return LegalGraphClient(settings)


def _empty_citation_response(node_id: str, warning: str | None = None) -> dict[str, Any]:
    """Return a minimal citation payload when graph context is unavailable."""
    return {
        "node_id": node_id,
        "hierarchy": {},
        "parent": None,
        "amendments": [],
        "citing_articles": [],
        "related_documents": [],
        "context_documents": [],
        "graph_available": False,
        "warning": warning,
    }


@router.get(
    "/citations/{node_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get citation context",
    description="Retrieve context documents (parent, siblings, amendments) for a legal node.",
)
async def get_citation_context(
    node_id: str = Path(..., description="Legal node ID to get context for"),
    graph_client: LegalGraphClient = Depends(get_graph_client),
) -> dict:
    """Get context documents for a legal citation.
    
    Args:
        node_id: ID of the legal node
        
    Returns:
        Structured response with document hierarchy, parent context, 
        amendments, and citing articles
        
    Raises:
        HTTPException: If node not found or query fails
    """
    try:
        # Fetch document hierarchy
        hierarchy = await graph_client.get_document_hierarchy(node_id)

        # Fetch parent context (if node is an article)
        parent = await graph_client.get_parent_document(node_id)

        # Fetch amendments
        amendments = await graph_client.get_amendments(node_id, max_depth=2)

        # Fetch citing articles
        citing = await graph_client.get_citing_articles(node_id)

        # Fetch related documents
        related = await graph_client.get_related_by_topic(node_id, max_hops=2)

    except Exception as e:
        error_message = str(e)
        logger.warning("Citation context unavailable for %s: %s", node_id, error_message)

        unavailable_markers = (
            "Couldn't connect to localhost:7687",
            "Connection refused",
            "Connect call failed",
            "ServiceUnavailable",
            "Failed to establish connection",
        )
        if any(marker in error_message for marker in unavailable_markers):
            return _empty_citation_response(
                node_id,
                warning="Citation graph is unavailable; returning basic citation data only.",
            )

        logger.error(f"Error retrieving citation context for {node_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve citation context: {str(e)}",
        )

    # Convert to ContextDocument format
    context_documents: list[ContextDocument] = []

    if parent:
        context_documents.append(ContextDocument(
            doc_id=parent["id"],
            content=parent.get("content", ""),
            relation_type="parent",
            title=parent.get("title"),
        ))

    for amd in amendments:
        context_documents.append(ContextDocument(
            doc_id=amd["id"],
            content=amd.get("content", ""),
            relation_type="amendment",
            title=amd.get("title"),
        ))

    for cite in citing:
        context_documents.append(ContextDocument(
            doc_id=cite["id"],
            content=cite.get("content", ""),
            relation_type="citing",
            title=cite.get("title"),
        ))

    for rel in related:
        if rel["id"] != node_id:
            context_documents.append(ContextDocument(
                doc_id=rel["id"],
                content=rel.get("content", ""),
                relation_type="related",
                title=rel.get("title"),
            ))

    logger.info(f"Retrieved citation context for {node_id}: {len(context_documents)} context documents")

    return {
        "node_id": node_id,
        "hierarchy": hierarchy,
        "parent": parent,
        "amendments": amendments,
        "citing_articles": citing,
        "related_documents": related,
        "context_documents": context_documents,
        "graph_available": True,
        "warning": None,
    }


@router.get(
    "/citations/{doc_id}/full-text",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get full document text",
    description="Retrieve full content of a cited document.",
)
async def get_citation_full_text(
    doc_id: str = Path(..., description="Document ID to get full text for"),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Get full document content for citation display.
    
    This endpoint returns the complete document text when users click
    "Xem thêm" on citations, solving the UX issue of truncated content.
    
    Args:
        doc_id: ID of the document
        
    Returns:
        Dict with full_text, title, metadata
    """
    try:
        import asyncpg
        
        pool = await asyncpg.create_pool(settings.postgres_dsn)
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, title, content, doc_type, metadata
                FROM legal_documents
                WHERE id = $1
                """,
                doc_id
            )
        
        await pool.close()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {doc_id} not found"
            )
        
        # Parse metadata if it's a string
        import json
        metadata = row["metadata"]
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        
        return {
            "doc_id": row["id"],
            "title": row["title"],
            "full_text": row["content"],  # Full content, not truncated!
            "doc_type": row["doc_type"],
            "metadata": metadata,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching full text for {doc_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve full text: {str(e)}"
        )
