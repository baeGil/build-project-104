"""Contract review routes."""
from fastapi import APIRouter, HTTPException, status

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
async def review_contract(request: ContractReviewRequest) -> ContractReviewResult:
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
        pipeline = ContractReviewPipeline(settings)
        
        result = await pipeline.review_contract(
            contract_text=request.contract_text,
            filters=request.filters or None,
        )
        
        # Override with provided contract_id if any
        if request.contract_id:
            result.contract_id = request.contract_id
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Contract review failed: {str(e)}",
        )
