"""Legal chat routes."""
import json
import logging

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

from packages.common.config import get_settings
from packages.common.types import (
    ChatAnswer,
    ChatRequest,
    Citation,
    EvidencePack,
    RetrievedDocument,
)
from packages.reasoning.generator import LegalGenerator
from packages.reasoning.planner import QueryPlanner
from packages.retrieval.context import ContextInjector
from packages.retrieval.hybrid import HybridRetriever

router = APIRouter(tags=["chat"])


def _coerce_retrieved_document(doc: RetrievedDocument | dict, index: int) -> RetrievedDocument:
    """Normalize retriever outputs into RetrievedDocument models."""
    if isinstance(doc, RetrievedDocument):
        return doc

    return RetrievedDocument(
        doc_id=doc.get("id", doc.get("doc_id", str(index))),
        content=doc.get("content", ""),
        title=doc.get("title"),
        score=doc.get("score", 0.0),
        metadata=doc.get("metadata", {}),
    )


async def _build_context_documents(app_state, settings, retrieved_documents: list[RetrievedDocument]):
    """Build graph-augmented context for generation."""
    if not retrieved_documents:
        return []

    context_injector = getattr(app_state, "context_injector", None) or ContextInjector(settings)
    try:
        return await context_injector.inject_context(retrieved_documents, top_k=3)
    except Exception as e:
        logger.debug("Context injection failed for chat request: %s", e)
        return []


@router.post(
    "/chat/legal",
    response_model=ChatAnswer,
    status_code=status.HTTP_200_OK,
    summary="Legal chat",
    description="Ask a legal question and get an answer based on Vietnamese legal corpus.",
)
async def legal_chat(request: ChatRequest, http_request: Request) -> ChatAnswer:
    """Handle legal chat queries.
    
    Args:
        request: Chat request with legal question
        http_request: HTTP request object to check for SSE support
        
    Returns:
        Chat answer with citations and confidence
        
    Raises:
        HTTPException: If query processing fails
    """
    try:
        settings = get_settings()
        app_state = http_request.app.state
        
        # Plan query
        planner = getattr(app_state, "query_planner", None) or QueryPlanner()
        query_plan = planner.plan(request.query)
        
        # Retrieve documents
        retriever = getattr(app_state, "hybrid_retriever", None) or HybridRetriever(settings)
        retrieved_docs = await retriever.search(
            query=query_plan.normalized_query,
            top_k=5,
            filters=request.filters or query_plan.search_filters,
        )
        
        # Convert to RetrievedDocument objects
        retrieved_documents = [
            _coerce_retrieved_document(doc, i)
            for i, doc in enumerate(retrieved_docs)
        ]
        
        # Build citations
        citations = [
            Citation(
                article_id=doc.doc_id,
                law_id=doc.metadata.get("law_id", "unknown"),
                quote=doc.content[:200],
                document_title=doc.title,
            )
            for doc in retrieved_documents[:3]
        ]
        context_documents = await _build_context_documents(app_state, settings, retrieved_documents)
        
        # Assemble EvidencePack
        evidence_pack = EvidencePack(
            clause=request.query,
            retrieved_documents=retrieved_documents,
            context_documents=context_documents,
            citations=citations,
            verification_confidence=retrieved_documents[0].score if retrieved_documents else 0.0,
        )
        
        # Generate answer
        generator = getattr(app_state, "legal_generator", None) or LegalGenerator(settings)
        answer = await generator.generate_chat_answer(
            query=request.query,
            evidence_pack=evidence_pack,
        )
        
        return answer
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing failed: {str(e)}",
        )


@router.post(
    "/chat/legal/stream",
    status_code=status.HTTP_200_OK,
    summary="Legal chat (streaming)",
    description="Ask a legal question and get a streaming answer via SSE.",
)
async def legal_chat_stream(request: ChatRequest, http_request: Request) -> StreamingResponse:
    """Handle legal chat queries with streaming response.
    
    Args:
        request: Chat request with legal question
        
    Returns:
        StreamingResponse with SSE event stream
        
    Raises:
        HTTPException: If query processing fails
    """
    try:
        settings = get_settings()
        app_state = http_request.app.state
        
        # Plan query
        logger.info(f"Chat stream: planning query '{request.query[:50]}...'" )
        planner = getattr(app_state, "query_planner", None) or QueryPlanner()
        query_plan = planner.plan(request.query)
        
        # Retrieve documents
        logger.info(f"Chat stream: retrieving documents for '{query_plan.normalized_query[:50]}...'")
        retriever = getattr(app_state, "hybrid_retriever", None) or HybridRetriever(settings)
        retrieved_docs = await retriever.search(
            query=query_plan.normalized_query,
            top_k=5,
            filters=request.filters or query_plan.search_filters,
        )
        
        # Convert to RetrievedDocument objects
        retrieved_documents = [
            _coerce_retrieved_document(doc, i)
            for i, doc in enumerate(retrieved_docs)
        ]
        
        logger.info(f"Chat stream: retrieved {len(retrieved_docs)} documents, starting stream")
        
        # Build citations
        citations = [
            Citation(
                article_id=doc.doc_id,
                law_id=doc.metadata.get("law_id", "unknown"),
                quote=doc.content[:200],
                document_title=doc.title,
            )
            for doc in retrieved_documents[:3]
        ]
        context_documents = await _build_context_documents(app_state, settings, retrieved_documents)
        
        # Assemble EvidencePack
        evidence_pack = EvidencePack(
            clause=request.query,
            retrieved_documents=retrieved_documents,
            context_documents=context_documents,
            citations=citations,
            verification_confidence=retrieved_documents[0].score if retrieved_documents else 0.0,
        )
        
        # Stream answer
        generator = getattr(app_state, "legal_generator", None) or LegalGenerator(settings)
        
        async def event_generator():
            """Generate SSE events."""
            try:
                async for token in generator.stream_chat_answer(
                    query=request.query,
                    evidence_pack=evidence_pack,
                ):
                    # SSE format: data: <content>\n\n
                    yield f"data: {token}\n\n"
                
                # Send citations as final event
                citation_data = "[CITATIONS] " + json.dumps(
                    [
                        {
                            "article_id": c.article_id,
                            "law_id": c.law_id,
                            "quote": c.quote[:100],
                            "document_title": c.document_title,
                        }
                        for c in citations
                    ],
                    ensure_ascii=False,
                )
                yield f"data: {citation_data}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Chat streaming error: {e}")
                yield f"data: [ERROR] {str(e)}\n\n"
                yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat streaming failed: {str(e)}",
        )
