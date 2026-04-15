"""Tests for contract review API routes."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from apps.review_api.main import app
from packages.common.types import (
    ContractReviewRequest,
    ContractReviewResult,
    ReviewFinding,
    RiskLevel,
    VerificationLevel,
)


@pytest.fixture
async def async_client():
    """Create an async test client with mocked dependencies."""
    with patch("apps.review_api.main.QueryPlanner"), \
         patch("apps.review_api.main.HybridRetriever"), \
         patch("apps.review_api.main.LegalGenerator"), \
         patch("apps.review_api.main.LegalVerifier"), \
         patch("apps.review_api.main.ContractReviewPipeline"), \
         patch("apps.review_api.main.EmbeddingService"):
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
def sample_contract_text():
    """Sample contract text for testing."""
    return """
    HỢP ĐỒNG DỊCH VỤ
    
    Bên A: Công ty TNHH ABC
    Bên B: Công ty TNHH XYZ
    
    Điều 1: Công ty TNHH ABC có 2 thành viên góp vốn.
    Điều 2: Thợi hạn hợp đồng là 12 tháng.
    """


@pytest.fixture
def mock_review_result():
    """Create a mock contract review result."""
    return ContractReviewResult(
        contract_id="test-contract-001",
        findings=[
            ReviewFinding(
                clause_text="Công ty TNHH ABC có 2 thành viên góp vốn",
                clause_index=1,
                verification=VerificationLevel.ENTAILED,
                confidence=0.95,
                risk_level=RiskLevel.NONE,
                rationale="Phù hợp với Điều 46 Luật Doanh nghiệp 2020",
            )
        ],
        summary="Contract review summary",
        total_clauses=2,
        risk_summary={"none": 1, "low": 0, "medium": 0, "high": 0},
        total_latency_ms=1500.0,
    )


class TestReviewContract:
    """Tests for POST /api/v1/review/contracts endpoint."""
    
    @pytest.mark.asyncio
    async def test_review_contract_success(self, async_client, sample_contract_text, mock_review_result):
        """Test successful contract review."""
        # Mock the pipeline
        mock_pipeline = AsyncMock()
        mock_pipeline.review_contract = AsyncMock(return_value=mock_review_result)
        app.state.review_pipeline = mock_pipeline
        
        response = await async_client.post(
            "/api/v1/review/contracts",
            json={"contract_text": sample_contract_text, "contract_id": "contract-001"}
        )
        
        assert response.status_code == 200
        data = response.json()
        # The API overrides the contract_id with the request's contract_id
        assert data["contract_id"] == "contract-001"
        assert len(data["findings"]) == 1
        assert data["findings"][0]["verification"] == "entailed"
        mock_pipeline.review_contract.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_review_contract_with_filters(self, async_client, sample_contract_text, mock_review_result):
        """Test contract review with filters."""
        mock_pipeline = AsyncMock()
        mock_pipeline.review_contract = AsyncMock(return_value=mock_review_result)
        app.state.review_pipeline = mock_pipeline
        
        response = await async_client.post(
            "/api/v1/review/contracts",
            json={
                "contract_text": sample_contract_text,
                "contract_id": "contract-002",
                "filters": {"doc_type": "luat", "year": 2020}
            }
        )
        
        assert response.status_code == 200
        # Verify filters were passed
        call_args = mock_pipeline.review_contract.call_args
        assert call_args.kwargs["filters"] == {"doc_type": "luat", "year": 2020}
    
    @pytest.mark.asyncio
    async def test_review_contract_without_contract_id(self, async_client, sample_contract_text, mock_review_result):
        """Test contract review without providing contract_id."""
        mock_pipeline = AsyncMock()
        mock_pipeline.review_contract = AsyncMock(return_value=mock_review_result)
        app.state.review_pipeline = mock_pipeline
        
        response = await async_client.post(
            "/api/v1/review/contracts",
            json={"contract_text": sample_contract_text}
        )
        
        assert response.status_code == 200
        # Result should still have the contract_id from the mock
        data = response.json()
        assert data["contract_id"] == "test-contract-001"
    
    @pytest.mark.asyncio
    async def test_review_contract_override_contract_id(self, async_client, sample_contract_text, mock_review_result):
        """Test that provided contract_id overrides the one in result."""
        mock_pipeline = AsyncMock()
        mock_pipeline.review_contract = AsyncMock(return_value=mock_review_result)
        app.state.review_pipeline = mock_pipeline
        
        response = await async_client.post(
            "/api/v1/review/contracts",
            json={"contract_text": sample_contract_text, "contract_id": "override-id"}
        )
        
        assert response.status_code == 200
        data = response.json()
        # The contract_id from request should override the result
        assert data["contract_id"] == "override-id"
    
    @pytest.mark.asyncio
    async def test_review_contract_missing_contract_text(self, async_client):
        """Test review without contract_text field."""
        response = await async_client.post(
            "/api/v1/review/contracts",
            json={"contract_id": "contract-001"}
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_review_contract_empty_contract_text(self, async_client):
        """Test review with empty contract_text."""
        response = await async_client.post(
            "/api/v1/review/contracts",
            json={"contract_text": "", "contract_id": "contract-001"}
        )
        
        assert response.status_code == 422  # Validation error - min_length=10
    
    @pytest.mark.asyncio
    async def test_review_contract_short_contract_text(self, async_client):
        """Test review with contract_text shorter than 10 characters."""
        response = await async_client.post(
            "/api/v1/review/contracts",
            json={"contract_text": "Short", "contract_id": "contract-001"}
        )
        
        assert response.status_code == 422  # Validation error - min_length=10
    
    @pytest.mark.asyncio
    async def test_review_contract_pipeline_error(self, async_client, sample_contract_text):
        """Test review when pipeline raises an error."""
        mock_pipeline = AsyncMock()
        mock_pipeline.review_contract = AsyncMock(side_effect=Exception("Pipeline failure"))
        app.state.review_pipeline = mock_pipeline
        
        response = await async_client.post(
            "/api/v1/review/contracts",
            json={"contract_text": sample_contract_text, "contract_id": "contract-001"}
        )
        
        assert response.status_code == 500
        assert "Contract review failed" in response.json()["detail"]
        assert "Pipeline failure" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_review_contract_no_pipeline_in_state(self, async_client, sample_contract_text, mock_review_result):
        """Test review when pipeline is not in app state (creates new one)."""
        # Remove pipeline from state
        if hasattr(app.state, "review_pipeline"):
            delattr(app.state, "review_pipeline")
        
        with patch("apps.review_api.routes.review.ContractReviewPipeline") as mock_pipeline_class:
            mock_pipeline = AsyncMock()
            mock_pipeline.review_contract = AsyncMock(return_value=mock_review_result)
            mock_pipeline_class.return_value = mock_pipeline
            
            response = await async_client.post(
                "/api/v1/review/contracts",
                json={"contract_text": sample_contract_text, "contract_id": "contract-001"}
            )
            
            assert response.status_code == 200
            mock_pipeline_class.assert_called_once()
            mock_pipeline.review_contract.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_review_contract_response_model(self, async_client, sample_contract_text, mock_review_result):
        """Test response matches ContractReviewResult model."""
        mock_pipeline = AsyncMock()
        mock_pipeline.review_contract = AsyncMock(return_value=mock_review_result)
        app.state.review_pipeline = mock_pipeline
        
        response = await async_client.post(
            "/api/v1/review/contracts",
            json={"contract_text": sample_contract_text}
        )
        
        assert response.status_code == 200
        # Validate against model
        result = ContractReviewResult(**response.json())
        assert result.contract_id == "test-contract-001"
        assert len(result.findings) == 1
        assert result.total_clauses == 2
    
    @pytest.mark.asyncio
    async def test_review_contract_with_risk_findings(self, async_client):
        """Test review with various risk level findings."""
        result_with_risks = ContractReviewResult(
            contract_id="risky-contract",
            findings=[
                ReviewFinding(
                    clause_text="High risk clause",
                    clause_index=1,
                    verification=VerificationLevel.CONTRADICTED,
                    confidence=0.9,
                    risk_level=RiskLevel.HIGH,
                    rationale="Contradicts legal requirements",
                ),
                ReviewFinding(
                    clause_text="Medium risk clause",
                    clause_index=2,
                    verification=VerificationLevel.PARTIALLY_SUPPORTED,
                    confidence=0.7,
                    risk_level=RiskLevel.MEDIUM,
                    rationale="Partially supported by law",
                ),
                ReviewFinding(
                    clause_text="Low risk clause",
                    clause_index=3,
                    verification=VerificationLevel.NO_REFERENCE,
                    confidence=0.5,
                    risk_level=RiskLevel.LOW,
                    rationale="No legal reference found",
                ),
            ],
            summary="Contract with risks",
            total_clauses=3,
            risk_summary={"high": 1, "medium": 1, "low": 1, "none": 0},
        )
        
        mock_pipeline = AsyncMock()
        mock_pipeline.review_contract = AsyncMock(return_value=result_with_risks)
        app.state.review_pipeline = mock_pipeline
        
        response = await async_client.post(
            "/api/v1/review/contracts",
            json={"contract_text": "Contract with multiple clauses for risk testing." * 3}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["findings"]) == 3
        assert data["risk_summary"]["high"] == 1
        assert data["risk_summary"]["medium"] == 1
        assert data["risk_summary"]["low"] == 1


class TestContractReviewRequest:
    """Tests for ContractReviewRequest model validation."""
    
    def test_contract_review_request_valid(self):
        """Test valid ContractReviewRequest creation."""
        request = ContractReviewRequest(
            contract_text="This is a valid contract text with sufficient length.",
            contract_id="contract-001",
            filters={"doc_type": "luat"}
        )
        assert request.contract_text == "This is a valid contract text with sufficient length."
        assert request.contract_id == "contract-001"
        assert request.filters == {"doc_type": "luat"}
    
    def test_contract_review_request_min_length_validation(self):
        """Test contract_text minimum length validation."""
        with pytest.raises(Exception):  # Pydantic validation error
            ContractReviewRequest(contract_text="Short", contract_id="test")
    
    def test_contract_review_request_optional_fields(self):
        """Test ContractReviewRequest with optional fields omitted."""
        request = ContractReviewRequest(
            contract_text="This is a valid contract text with sufficient length."
        )
        assert request.contract_id is None
        assert request.filters == {}  # Default empty dict


class TestReviewEndpointEdgeCases:
    """Tests for edge cases in review endpoint."""
    
    @pytest.mark.asyncio
    async def test_review_contract_unicode_content(self, async_client, mock_review_result):
        """Test review with Vietnamese unicode content."""
        mock_pipeline = AsyncMock()
        mock_pipeline.review_contract = AsyncMock(return_value=mock_review_result)
        app.state.review_pipeline = mock_pipeline
        
        vietnamese_contract = """
        HỢP ĐỒNG DỊCH VỤ PHÁP LÝ
        
        Các bên tham gia hợp đồng này gồm có:
        - Bên A: Công ty TNHH Tư vấn Pháp lý ABC
        - Bên B: Công ty TNHH Thương mại XYZ
        
        Điều 1: Phạm vi dịch vụ
        Bên A đồng ý cung cấp dịch vụ tư vấn pháp lý cho Bên B.
        """
        
        response = await async_client.post(
            "/api/v1/review/contracts",
            json={"contract_text": vietnamese_contract}
        )
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_review_contract_large_content(self, async_client, mock_review_result):
        """Test review with large contract content."""
        mock_pipeline = AsyncMock()
        mock_pipeline.review_contract = AsyncMock(return_value=mock_review_result)
        app.state.review_pipeline = mock_pipeline
        
        large_contract = "This is a contract clause. " * 1000  # Large content
        
        response = await async_client.post(
            "/api/v1/review/contracts",
            json={"contract_text": large_contract}
        )
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_review_contract_empty_findings(self, async_client):
        """Test review returning empty findings."""
        empty_result = ContractReviewResult(
            contract_id="empty-contract",
            findings=[],
            summary="No findings",
            total_clauses=0,
            risk_summary={},
        )
        
        mock_pipeline = AsyncMock()
        mock_pipeline.review_contract = AsyncMock(return_value=empty_result)
        app.state.review_pipeline = mock_pipeline
        
        response = await async_client.post(
            "/api/v1/review/contracts",
            json={"contract_text": "This is a valid contract text with sufficient length."}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["findings"] == []
        assert data["total_clauses"] == 0
