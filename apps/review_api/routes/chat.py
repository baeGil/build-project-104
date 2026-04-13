"""Legal chat routes."""
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

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
from packages.retrieval.hybrid import HybridRetriever

router = APIRouter(tags=["chat"])


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
        
        # Plan query
        planner = QueryPlanner()
        query_plan = await planner.plan(request.query)
        
        # Retrieve documents
        retriever = HybridRetriever()
        retrieved_docs = await retriever.retrieve(
            query=query_plan.normalized_query,
            top_k=5,
            filters=request.filters or query_plan.search_filters,
        )
        
        # Convert to RetrievedDocument objects
        retrieved_documents = [
            RetrievedDocument(
                doc_id=doc.get("id", doc.get("doc_id", str(i))),
                content=doc.get("content", ""),
                title=doc.get("title"),
                score=doc.get("score", 0.0),
                metadata=doc.get("metadata", {}),
            )
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
        
        # Assemble EvidencePack
        evidence_pack = EvidencePack(
            clause=request.query,
            retrieved_documents=retrieved_documents,
            citations=citations,
            verification_confidence=retrieved_documents[0].score if retrieved_documents else 0.0,
        )
        
        # Generate answer
        generator = LegalGenerator(settings)
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
async def legal_chat_stream(request: ChatRequest) -> StreamingResponse:
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
        
        # Plan query
        planner = QueryPlanner()
        query_plan = await planner.plan(request.query)
        
        # Retrieve documents
        retriever = HybridRetriever()
        retrieved_docs = await retriever.retrieve(
            query=query_plan.normalized_query,
            top_k=5,
            filters=request.filters or query_plan.search_filters,
        )
        
        # Convert to RetrievedDocument objects
        retrieved_documents = [
            RetrievedDocument(
                doc_id=doc.get("id", doc.get("doc_id", str(i))),
                content=doc.get("content", ""),
                title=doc.get("title"),
                score=doc.get("score", 0.0),
                metadata=doc.get("metadata", {}),
            )
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
        
        # Assemble EvidencePack
        evidence_pack = EvidencePack(
            clause=request.query,
            retrieved_documents=retrieved_documents,
            citations=citations,
            verification_confidence=retrieved_documents[0].score if retrieved_documents else 0.0,
        )
        
        # Stream answer
        generator = LegalGenerator(settings)
        
        async def event_generator():
            """Generate SSE events."""
            async for token in generator.stream_chat_answer(
                query=request.query,
                evidence_pack=evidence_pack,
            ):
                # SSE format: data: <content>\n\n
                yield f"data: {token}\n\n"
            
            # Send citations as final event
            citation_data = "[CITATIONS] " + str([
                {"article_id": c.article_id, "law_id": c.law_id, "quote": c.quote[:100]}
                for c in citations
            ])
            yield f"data: {citation_data}\n\n"
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
