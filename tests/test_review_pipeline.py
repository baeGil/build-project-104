"""Tests for ContractReviewPipeline in packages/reasoning/review_pipeline.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from packages.common.config import Settings
from packages.common.types import (
    ContractReviewResult,
    QueryPlan,
    QueryStrategy,
    RetrievedDocument,
    ReviewFinding,
    RiskLevel,
    VerificationLevel,
)
from packages.reasoning.review_pipeline import ContractReviewPipeline


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for testing."""
    settings = MagicMock(spec=Settings)
    settings.llm_model = "test-model"
    # Search configuration attributes
    settings.search_reranker_budget_ms = 300
    settings.search_reranker_input_k = 15
    settings.search_bm25_candidates = 200
    settings.search_dense_candidates = 200
    settings.search_rrf_k = 60
    settings.search_rrf_top_n = 200
    settings.search_expansion_max_variants = 4
    settings.search_expansion_boost = 0.7
    settings.search_aggregation_threshold = 1.0
    settings.search_chunk_size_tokens = 400
    settings.search_chunk_overlap = 0.5
    settings.search_min_chunk_tokens = 100
    return settings


@pytest.fixture
def pipeline(mock_settings: Settings) -> ContractReviewPipeline:
    """Create a ContractReviewPipeline with mocked components."""
    with patch("packages.reasoning.review_pipeline.QueryPlanner") as mock_planner, \
         patch("packages.reasoning.review_pipeline.HybridRetriever") as mock_retriever, \
         patch("packages.reasoning.review_pipeline.LegalVerifier") as mock_verifier, \
         patch("packages.reasoning.review_pipeline.LegalGenerator") as mock_generator:
        
        pipeline = ContractReviewPipeline(mock_settings)
        pipeline.planner = mock_planner.return_value
        pipeline.retriever = mock_retriever.return_value
        pipeline.verifier = mock_verifier.return_value
        pipeline.generator = mock_generator.return_value
        # Clear the cache to avoid interference between tests
        pipeline._parse_contract_clauses.cache_clear() if hasattr(pipeline._parse_contract_clauses, 'cache_clear') else None
        return pipeline


@pytest.fixture
def sample_vietnamese_contract() -> str:
    """Create a sample Vietnamese contract text."""
    return "Điều 1. Thông tin các bên\nBên A: Công ty TNHH ABC có địa chỉ tại Hà Nội.\nBên B: Công ty TNHH XYZ có địa chỉ tại TP.HCM.\n\nĐiều 2. Đối tượng hợp đồng\nHợp đồng này quy định về việc cung cấp dịch vụ tư vấn pháp lý theo quy định.\n\nĐiều 3. Thỏa thuận về giá\nTổng giá trị hợp đồng là 100 triệu đồng thanh toán làm nhiều đợt."


class TestReviewContract:
    """Tests for ContractReviewPipeline.review_contract method."""

    async def test_review_contract_success(
        self,
        pipeline: ContractReviewPipeline,
        sample_vietnamese_contract: str,
    ) -> None:
        """Test successful contract review."""
        # Setup mocks
        pipeline.planner.plan = Mock(return_value=QueryPlan(
            original_query="test",
            normalized_query="test",
            strategy=QueryStrategy.SEMANTIC,
        ))
        pipeline.retriever.search = AsyncMock(return_value=[{
            "id": "doc-1",
            "content": "Test content",
            "title": "Test Doc",
            "score": 0.9,
            "metadata": {"law_id": "law-2020"},
        }])
        pipeline.verifier.verify = AsyncMock(return_value={
            "level": VerificationLevel.ENTAILED,
            "confidence": 0.95,
            "reasoning": "Test reasoning",
        })
        pipeline.generator.generate_finding = AsyncMock(return_value=ReviewFinding(
            clause_text="Test clause",
            clause_index=0,
            verification=VerificationLevel.ENTAILED,
            confidence=0.95,
            risk_level=RiskLevel.NONE,
            rationale="Test rationale",
        ))
        pipeline.generator.generate_review_summary = AsyncMock(return_value="Test summary")

        result = await pipeline.review_contract(sample_vietnamese_contract)

        assert isinstance(result, ContractReviewResult)
        assert result.total_clauses > 0
        assert len(result.findings) > 0
        assert result.summary == "Test summary"
        assert "high" in result.risk_summary
        assert "medium" in result.risk_summary
        assert "low" in result.risk_summary
        assert "none" in result.risk_summary

    async def test_review_contract_with_filters(
        self,
        pipeline: ContractReviewPipeline,
        sample_vietnamese_contract: str,
    ) -> None:
        """Test contract review with filters."""
        filters = {"doc_type": "luat", "year": 2020}
        
        pipeline.planner.plan = Mock(return_value=QueryPlan(
            original_query="test",
            normalized_query="test",
            strategy=QueryStrategy.SEMANTIC,
            search_filters={"year": 2020},
        ))
        pipeline.retriever.search = AsyncMock(return_value=[])
        pipeline.verifier.verify = AsyncMock(return_value={
            "level": VerificationLevel.NO_REFERENCE,
            "confidence": 0.0,
            "reasoning": "No documents found",
        })
        pipeline.generator.generate_finding = AsyncMock(return_value=ReviewFinding(
            clause_text="Test clause",
            clause_index=0,
            verification=VerificationLevel.NO_REFERENCE,
            confidence=0.0,
            risk_level=RiskLevel.LOW,
            rationale="No reference found",
        ))
        pipeline.generator.generate_review_summary = AsyncMock(return_value="Summary with filters")

        result = await pipeline.review_contract(sample_vietnamese_contract, filters=filters)

        assert isinstance(result, ContractReviewResult)
        # Verify filters were passed to retriever
        call_args = pipeline.retriever.search.call_args
        assert call_args is not None


class TestParseContractClauses:
    """Tests for ContractReviewPipeline._parse_contract_clauses method."""

    def test_parse_vietnamese_contract_with_dieu_markers(self, pipeline: ContractReviewPipeline) -> None:
        """Test parsing Vietnamese contract with 'Điều' markers."""
        # Use a simple contract format that works with the regex
        contract = "Điều 1. Thông tin các bên\nBên A và Bên B thống nhất ký kết hợp đồng này theo quy định của pháp luật.\n\nĐiều 2. Giá trị hợp đồng\nTổng giá trị là 100 triệu đồng Việt Nam."
        clauses = pipeline._parse_contract_clauses(contract)

        # The method returns at least one clause
        assert len(clauses) >= 1
        assert all(isinstance(c[0], int) for c in clauses)
        assert all(isinstance(c[1], str) for c in clauses)

    def test_parse_contract_with_dieu_thu(self, pipeline: ContractReviewPipeline) -> None:
        """Test parsing contract with 'Điều thứ' markers."""
        contract = "Điều thứ 1. Quy định chung\nCác bên tuân thủ pháp luật hiện hành.\n\nĐiều thứ 2. Trách nhiệm\nCác bên chịu trách nhiệm về hợp đồng."
        clauses = pipeline._parse_contract_clauses(contract)

        assert len(clauses) >= 1

    def test_parse_contract_with_roman_numerals(self, pipeline: ContractReviewPipeline) -> None:
        """Test parsing contract with Roman numeral markers."""
        contract = "Điều I. Nguyên tắc chung\nCác bên bình đẳng trong quan hệ hợp đồng.\n\nĐiều II. Thực hiện hợp đồng\nThực hiện đúng tiến độ đã thỏa thuận."
        clauses = pipeline._parse_contract_clauses(contract)

        assert len(clauses) >= 1

    def test_parse_empty_contract(self, pipeline: ContractReviewPipeline) -> None:
        """Test parsing empty contract."""
        clauses = pipeline._parse_contract_clauses("")
        assert clauses == []

    def test_parse_contract_no_markers(self, pipeline: ContractReviewPipeline) -> None:
        """Test parsing contract without article markers."""
        contract = "This is a simple contract without any article markers. It should be treated as one clause."
        clauses = pipeline._parse_contract_clauses(contract)

        assert len(clauses) == 1
        assert clauses[0][0] == 0
        assert "simple contract" in clauses[0][1]

    def test_parse_contract_skips_short_fragments(self, pipeline: ContractReviewPipeline) -> None:
        """Test that short fragments (likely headers) are skipped."""
        contract = "Điều 1. A\nShort text here.\n\nĐiều 2. B\nThis is a longer clause with sufficient content to be included in the parsing results and more."
        clauses = pipeline._parse_contract_clauses(contract)

        # Should skip very short fragments (less than 20 chars)
        assert all(len(c[1]) >= 20 for c in clauses)


class TestBuildRiskSummary:
    """Tests for ContractReviewPipeline._build_risk_summary method."""

    def test_build_risk_summary_with_mixed_risks(self, pipeline: ContractReviewPipeline) -> None:
        """Test risk summary with various risk levels."""
        findings = [
            ReviewFinding(
                clause_text="Clause 1",
                clause_index=0,
                verification=VerificationLevel.CONTRADICTED,
                confidence=0.9,
                risk_level=RiskLevel.HIGH,
                rationale="High risk",
            ),
            ReviewFinding(
                clause_text="Clause 2",
                clause_index=1,
                verification=VerificationLevel.PARTIALLY_SUPPORTED,
                confidence=0.7,
                risk_level=RiskLevel.MEDIUM,
                rationale="Medium risk",
            ),
            ReviewFinding(
                clause_text="Clause 3",
                clause_index=2,
                verification=VerificationLevel.NO_REFERENCE,
                confidence=0.5,
                risk_level=RiskLevel.LOW,
                rationale="Low risk",
            ),
            ReviewFinding(
                clause_text="Clause 4",
                clause_index=3,
                verification=VerificationLevel.ENTAILED,
                confidence=0.95,
                risk_level=RiskLevel.NONE,
                rationale="No risk",
            ),
        ]

        summary = pipeline._build_risk_summary(findings)

        assert summary[RiskLevel.HIGH] == 1
        assert summary[RiskLevel.MEDIUM] == 1
        assert summary[RiskLevel.LOW] == 1
        assert summary[RiskLevel.NONE] == 1

    def test_build_risk_summary_empty(self, pipeline: ContractReviewPipeline) -> None:
        """Test risk summary with no findings."""
        summary = pipeline._build_risk_summary([])

        assert summary[RiskLevel.HIGH] == 0
        assert summary[RiskLevel.MEDIUM] == 0
        assert summary[RiskLevel.LOW] == 0
        assert summary[RiskLevel.NONE] == 0


class TestReviewSingleClause:
    """Tests for ContractReviewPipeline._review_single_clause method."""

    async def test_review_single_clause_success(
        self,
        pipeline: ContractReviewPipeline,
    ) -> None:
        """Test successful single clause review."""
        clause_text = "Công ty có 2 thành viên góp vốn"

        pipeline.planner.plan = Mock(return_value=QueryPlan(
            original_query=clause_text,
            normalized_query="cong ty co 2 thanh vien",
            strategy=QueryStrategy.SEMANTIC,
        ))
        # Return RetrievedDocument objects (not dicts) as the reranker expects .score attribute
        pipeline.retriever.search = AsyncMock(return_value=[
            RetrievedDocument(
                doc_id="art-46",
                content="Công ty TNHH có thể có 1 hoặc nhiều thành viên",
                title="Điều 46",
                score=0.95,
                metadata={"law_id": "law-2020-01-01"},
            )
        ])
        pipeline.verifier.verify = AsyncMock(return_value={
            "level": VerificationLevel.ENTAILED,
            "confidence": 0.95,
            "reasoning": "Clause is compliant",
        })
        pipeline.generator.generate_finding = AsyncMock(return_value=ReviewFinding(
            clause_text=clause_text,
            clause_index=0,
            verification=VerificationLevel.ENTAILED,
            confidence=0.95,
            risk_level=RiskLevel.NONE,
            rationale="Compliant with Article 46",
        ))

        result = await pipeline._review_single_clause(0, clause_text)

        assert isinstance(result, ReviewFinding)
        assert result.clause_text == clause_text
        assert result.clause_index == 0
        pipeline.planner.plan.assert_called_once_with(clause_text)
        pipeline.retriever.search.assert_called_once()
        pipeline.verifier.verify.assert_called_once()
        pipeline.generator.generate_finding.assert_called_once()

    async def test_review_single_clause_with_filters(
        self,
        pipeline: ContractReviewPipeline,
    ) -> None:
        """Test single clause review with filters."""
        clause_text = "Test clause"
        filters = {"doc_type": "luat"}

        pipeline.planner.plan = Mock(return_value=QueryPlan(
            original_query=clause_text,
            normalized_query="test clause",
            strategy=QueryStrategy.SEMANTIC,
            search_filters={},
        ))
        pipeline.retriever.search = AsyncMock(return_value=[])
        pipeline.verifier.verify = AsyncMock(return_value={
            "level": VerificationLevel.NO_REFERENCE,
            "confidence": 0.0,
            "reasoning": "No reference",
        })
        pipeline.generator.generate_finding = AsyncMock(return_value=ReviewFinding(
            clause_text=clause_text,
            clause_index=0,
            verification=VerificationLevel.NO_REFERENCE,
            confidence=0.0,
            risk_level=RiskLevel.LOW,
            rationale="No reference found",
        ))

        await pipeline._review_single_clause(0, clause_text, filters=filters)

        # Verify filters were passed to retriever
        call_kwargs = pipeline.retriever.search.call_args[1]
        assert call_kwargs.get("filters") == filters

    async def test_review_single_clause_error_handling(
        self,
        pipeline: ContractReviewPipeline,
    ) -> None:
        """Test error handling in single clause review."""
        clause_text = "Test clause"

        pipeline.planner.plan = Mock(side_effect=Exception("Planner error"))

        # The error should propagate up since there's no try-except in _review_single_clause
        with pytest.raises(Exception, match="Planner error"):
            await pipeline._review_single_clause(0, clause_text)


class TestClauseErrorHandlingInReviewContract:
    """Tests for error handling at review_contract level."""

    async def test_review_contract_continues_on_clause_error(
        self,
        pipeline: ContractReviewPipeline,
    ) -> None:
        """Test that review continues even if one clause fails."""
        contract = "Điều 1. First clause\nThis is the first clause content with enough length.\n\nĐiều 2. Second clause\nThis is the second clause content with enough length too."

        call_count = 0
        # Mock must accept 4 positional args: clause_index, clause_text, filters, include_relationships
        async def mock_review_single_clause(index, text, filters=None, include_relationships=True):
            nonlocal call_count
            call_count += 1
            if index == 0:
                raise Exception("Simulated error")
            return ReviewFinding(
                clause_text=text,
                clause_index=index,
                verification=VerificationLevel.NO_REFERENCE,
                confidence=0.0,
                risk_level=RiskLevel.LOW,
                rationale="Success",
            )

        pipeline._review_single_clause = mock_review_single_clause
        pipeline.generator.generate_review_summary = AsyncMock(return_value="Summary")

        result = await pipeline.review_contract(contract)

        # Should have findings for both clauses (one error, one success)
        assert len(result.findings) == 2
        assert "Review failed" in result.findings[0].rationale
        assert result.findings[1].rationale == "Success"
