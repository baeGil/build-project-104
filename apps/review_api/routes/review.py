"""Contract review routes."""
import json
import logging

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

from packages.common.config import get_settings
from packages.common.types import ContractReviewRequest, ContractReviewResult
from packages.reasoning.review_pipeline import ContractReviewPipeline

router = APIRouter(tags=["review"])


@router.post(
    "/review/contracts",
    response_model=ContractReviewResult,
    status_code=status.HTTP_200_OK,
    summary="Review a contract",
    description="Analyze a contract against Vietnamese legal corpus and return findings.",
)
async def review_contract(
    request: ContractReviewRequest,
    http_request: Request,
) -> ContractReviewResult:
    """Review a contract for legal compliance.
    
    Args:
        request: Contract review request with contract text
        
    Returns:
        Contract review result with findings and analysis
        
    Raises:
        HTTPException: If review fails
    """
    try:
        settings = get_settings()
        pipeline = getattr(http_request.app.state, "review_pipeline", None) or ContractReviewPipeline(settings)

        result = await pipeline.review_contract(
            contract_text=request.contract_text,
            filters=request.filters or None,
            include_relationships=request.include_relationships,
        )

        # Override with provided contract_id if any
        if request.contract_id:
            result.contract_id = request.contract_id

        # Collect unique references across all findings
        result.references = _collect_unique_references(result.findings)

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Contract review failed: {str(e)}",
        )


def _collect_unique_references(findings: list) -> list[dict]:
    """Collect unique references from all findings."""
    seen_article_ids: set[str] = set()
    references: list[dict] = []

    for finding in findings:
        for citation in finding.citations:
            if citation.article_id not in seen_article_ids:
                seen_article_ids.add(citation.article_id)
                references.append({
                    "article_id": citation.article_id,
                    "law_id": citation.law_id,
                    "document_title": citation.document_title,
                    "quote": citation.quote,
                })

    return references


@router.post(
    "/review/contracts/stream",
    status_code=status.HTTP_200_OK,
    summary="Review a contract (streaming)",
    description="Analyze a contract against Vietnamese legal corpus with streaming progress updates.",
)
async def review_contract_stream(
    request: ContractReviewRequest,
    http_request: Request,
):
    """Streaming contract review with progress events.
    
    SSE format events:
    - {"type": "progress", "data": {"phase": "analyzing", "message": "...", "total_clauses": N}}
    - {"type": "progress", "data": {"phase": "reviewing", "message": "...", "current": X, "total": N}}
    - {"type": "finding", "data": {<ReviewFinding JSON>}}
    - {"type": "progress", "data": {"phase": "summarizing", "message": "..."}}
    - {"type": "summary", "data": {"summary": "...", "risk_summary": {...}, "references": [...]}}
    - {"type": "done", "data": {}}
    
    Args:
        request: Contract review request with contract text
        http_request: HTTP request object
        
    Returns:
        StreamingResponse with SSE event stream
        
    Raises:
        HTTPException: If review fails
    """
    try:
        settings = get_settings()
        pipeline = getattr(http_request.app.state, "review_pipeline", None) or ContractReviewPipeline(settings)

        async def event_generator():
            """Generate SSE events from streaming review."""
            try:
                async for event in pipeline.review_contract_stream(
                    contract_text=request.contract_text,
                    filters=request.filters or None,
                    include_relationships=request.include_relationships,
                ):
                    # SSE format: data: <json>\n\n
                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as e:
                logger.error(f"Streaming review error: {e}")
                error_event = {"type": "error", "data": {"message": str(e)}}
                yield f"data: {json.dumps(error_event)}\n\n"

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
            detail=f"Contract review streaming failed: {str(e)}",
        )
