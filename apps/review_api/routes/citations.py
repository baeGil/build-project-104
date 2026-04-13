"""Citation routes for retrieving document context."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Path, status

from packages.common.config import Settings, get_settings
from packages.common.types import ContextDocument
from packages.graph.legal_graph import LegalGraphClient

logger = logging.getLogger(__name__)
router = APIRouter(tags=["citations"])


async def get_graph_client(settings: Settings = Depends(get_settings)) -> LegalGraphClient:
    """Dependency to get graph client."""
    return LegalGraphClient(settings)


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
        }
        
    except Exception as e:
        logger.error(f"Error retrieving citation context for {node_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve citation context: {str(e)}",
        )
