"""Legal chat routes."""
import json
import logging
import time

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


def _build_citations_with_relationships(
    documents: list[RetrievedDocument],
    include_related: bool = True,
) -> list[Citation]:
    """Build citations including related document references.
    
    Args:
        documents: List of retrieved documents to build citations for
        include_related: Whether to include related documents in citations
    
    Returns:
        List of Citation objects, potentially including related documents
    """
    citations = []
    seen_doc_ids = set()

    for doc in documents:
        if doc.doc_id in seen_doc_ids:
            continue
        seen_doc_ids.add(doc.doc_id)

        citations.append(
            Citation(
                article_id=doc.doc_id,
                law_id=doc.metadata.get("law_id", "unknown"),
                quote=doc.content[:200],
                document_title=doc.title,
            )
        )

        # Include related documents as additional citations if available
        if include_related and doc.related_documents:
            for related in doc.related_documents[:2]:  # Max 2 related per doc
                related_id = related.get("doc_id")
                if related_id and related_id not in seen_doc_ids:
                    seen_doc_ids.add(related_id)
                    citations.append(
                        Citation(
                            article_id=related_id,
                            law_id=related.get("relationship_type", "Văn bản liên quan"),
                            quote=related.get("content", "")[:200],
                            document_title=related.get("title"),
                        )
                    )

    return citations


async def _build_context_documents(
    app_state,
    settings,
    retrieved_documents: list[RetrievedDocument],
    include_relationships: bool = True,
):
    """Build graph-augmented context for generation with relationship enrichment.
    
    Args:
        app_state: Application state with shared services
        settings: Application settings
        retrieved_documents: List of retrieved documents to enrich
        include_relationships: Whether to include document relationships (default: True)
    
    Returns:
        List of ContextDocument objects for generation
    """
    if not retrieved_documents:
        return []

    context_injector = getattr(app_state, "context_injector", None) or ContextInjector(settings)
    try:
        context_docs = await context_injector.inject_context(
            retrieved_documents,
            top_k=3,
            include_pg_relationships=include_relationships,
        )

        # Also enrich retrieved documents with their relationships for citations
        if include_relationships:
            for doc in retrieved_documents:
                if not doc.related_documents:
                    await context_injector.enrich_with_relationships(doc)


        return context_docs
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
        total_start = time.time()
        settings = get_settings()
        app_state = http_request.app.state

        # Step 1: Plan query
        t0 = time.time()
        planner = getattr(app_state, "query_planner", None) or QueryPlanner()
        query_plan = planner.plan(request.query)
        t1 = time.time()
        planner_time = (t1 - t0) * 1000
        logger.info(f"[CHAT] Step 1 - Query Planner: {planner_time:.1f}ms")

        # Step 2: Retrieve documents
        t0 = time.time()
        retriever = getattr(app_state, "hybrid_retriever", None) or HybridRetriever(settings)
        retrieved_docs = await retriever.search(
            query=query_plan.normalized_query,
            top_k=5,
            filters=request.filters or query_plan.search_filters,
        )
        t1 = time.time()
        retrieval_time = (t1 - t0) * 1000
        logger.info(f"[CHAT] Step 2 - Hybrid Retriever: {retrieval_time:.1f}ms ({len(retrieved_docs)} docs)")

        # Step 3: Convert to RetrievedDocument objects
        t0 = time.time()
        retrieved_documents = [
            _coerce_retrieved_document(doc, i)
            for i, doc in enumerate(retrieved_docs)
        ]
        t1 = time.time()
        coerce_time = (t1 - t0) * 1000
        logger.info(f"[CHAT] Step 3 - Coerce Documents: {coerce_time:.1f}ms")

        # Step 4: Build context with relationship enrichment
        t0 = time.time()
        context_documents = await _build_context_documents(
            app_state, settings, retrieved_documents, request.include_relationships
        )
        t1 = time.time()
        context_time = (t1 - t0) * 1000
        logger.info(f"[CHAT] Step 4 - Context Injector: {context_time:.1f}ms")

        # Step 5: Build citations
        t0 = time.time()
        citations = _build_citations_with_relationships(
            retrieved_documents[:3], include_related=request.include_relationships
        )
        t1 = time.time()
        citation_time = (t1 - t0) * 1000
        logger.info(f"[CHAT] Step 5 - Citations: {citation_time:.1f}ms")

        # Step 6: Assemble EvidencePack
        t0 = time.time()
        evidence_pack = EvidencePack(
            clause=request.query,
            retrieved_documents=retrieved_documents,
            context_documents=context_documents,
            citations=citations,
            verification_confidence=retrieved_documents[0].score if retrieved_documents else 0.0,
        )
        t1 = time.time()
        evidence_time = (t1 - t0) * 1000
        logger.info(f"[CHAT] Step 6 - Evidence Pack: {evidence_time:.1f}ms")

        # Step 7: Generate answer (LLM)
        t0 = time.time()
        generator = getattr(app_state, "legal_generator", None) or LegalGenerator(settings)
        answer = await generator.generate_chat_answer(
            query=request.query,
            evidence_pack=evidence_pack,
        )
        t1 = time.time()
        llm_time = (t1 - t0) * 1000
        logger.info(f"[CHAT] Step 7 - LLM Generation: {llm_time:.1f}ms")

        total_time = (time.time() - total_start) * 1000
        logger.info(
            f"[CHAT] TOTAL: {total_time:.1f}ms | "
            f"Planner: {planner_time:.1f}ms | "
            f"Retrieval: {retrieval_time:.1f}ms | "
            f"Context: {context_time:.1f}ms | "
            f"LLM: {llm_time:.1f}ms ({llm_time/total_time*100:.0f}%)"
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

        # Build context with relationship enrichment
        context_documents = await _build_context_documents(
            app_state, settings, retrieved_documents, request.include_relationships
        )

        # Build citations (including related documents if available)
        citations = _build_citations_with_relationships(
            retrieved_documents[:3], include_related=request.include_relationships
        )

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
