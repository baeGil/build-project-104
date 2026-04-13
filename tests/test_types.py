"""Tests for shared domain types."""
from datetime import date, datetime

import pytest
from pydantic import ValidationError

from packages.common.types import (
    ChatAnswer,
    ChatRequest,
    Citation,
    ContextDocument,
    ContractReviewRequest,
    ContractReviewResult,
    DocumentType,
    EvidencePack,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    LegalNode,
    QueryPlan,
    QueryStrategy,
    RetrievedDocument,
    ReviewFinding,
    RiskLevel,
    VerificationLevel,
)


class TestEnums:
    """Tests for enumeration types."""
    
    def test_document_type_values(self) -> None:
        """Test DocumentType enum values."""
        assert DocumentType.LAW == "luat"
        assert DocumentType.DECREE == "nghi_dinh"
        assert DocumentType.CIRCULAR == "thong_tu"
        assert DocumentType.DECISION == "quyet_dinh"
        assert DocumentType.RESOLUTION == "nghi_quyet"
        assert DocumentType.OTHER == "other"
    
    def test_verification_level_values(self) -> None:
        """Test VerificationLevel enum values."""
        assert VerificationLevel.ENTAILED == "entailed"
        assert VerificationLevel.CONTRADICTED == "contradicted"
        assert VerificationLevel.PARTIALLY_SUPPORTED == "partially_supported"
        assert VerificationLevel.NO_REFERENCE == "no_reference"
    
    def test_risk_level_values(self) -> None:
        """Test RiskLevel enum values."""
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.LOW == "low"
        assert RiskLevel.NONE == "none"
    
    def test_query_strategy_values(self) -> None:
        """Test QueryStrategy enum values."""
        assert QueryStrategy.CITATION == "citation"
        assert QueryStrategy.NEGATION == "negation"
        assert QueryStrategy.SEMANTIC == "semantic"


class TestLegalNode:
    """Tests for LegalNode model."""
    
    def test_create_legal_node(self) -> None:
        """Test creating a LegalNode instance."""
        node = LegalNode(
            id="law-2020-01-01",
            title="Luật Doanh nghiệp 2020",
            content="Nội dung luật...",
            doc_type=DocumentType.LAW,
        )
        assert node.id == "law-2020-01-01"
        assert node.title == "Luật Doanh nghiệp 2020"
        assert node.doc_type == DocumentType.LAW
        assert node.level == 0  # default value
        assert node.children_ids == []  # default value
    
    def test_legal_node_with_dates(self) -> None:
        """Test LegalNode with date fields."""
        node = LegalNode(
            id="law-2020-01-01",
            title="Luật Doanh nghiệp 2020",
            content="Nội dung luật...",
            doc_type=DocumentType.LAW,
            publish_date=date(2020, 1, 1),
            effective_date=date(2020, 7, 1),
            issuing_body="Quốc hội",
            document_number="59/2020/QH14",
        )
        assert node.publish_date == date(2020, 1, 1)
        assert node.effective_date == date(2020, 7, 1)
        assert node.issuing_body == "Quốc hội"


class TestQueryPlan:
    """Tests for QueryPlan model."""
    
    def test_create_query_plan(self) -> None:
        """Test creating a QueryPlan instance."""
        plan = QueryPlan(
            original_query="Test query",
            normalized_query="test query",
        )
        assert plan.original_query == "Test query"
        assert plan.normalized_query == "test query"
        assert plan.strategy == QueryStrategy.SEMANTIC  # default
        assert plan.has_negation is False  # default
        assert plan.expansion_variants == []  # default
    
    def test_query_plan_with_citations(self) -> None:
        """Test QueryPlan with citations."""
        plan = QueryPlan(
            original_query="Theo Luật Doanh nghiệp 2020",
            normalized_query="theo luat doanh nghiep 2020",
            citations=["Luật Doanh nghiệp 2020"],
            strategy=QueryStrategy.CITATION,
        )
        assert plan.citations == ["Luật Doanh nghiệp 2020"]
        assert plan.strategy == QueryStrategy.CITATION


class TestRetrievedDocument:
    """Tests for RetrievedDocument model."""
    
    def test_create_retrieved_document(self) -> None:
        """Test creating a RetrievedDocument instance."""
        doc = RetrievedDocument(
            doc_id="doc-001",
            content="Test content",
            score=0.95,
        )
        assert doc.doc_id == "doc-001"
        assert doc.content == "Test content"
        assert doc.score == 0.95
        assert doc.title is None
    
    def test_retrieved_document_with_scores(self) -> None:
        """Test RetrievedDocument with all score types."""
        doc = RetrievedDocument(
            doc_id="doc-001",
            content="Test content",
            title="Test Title",
            score=0.95,
            bm25_score=0.85,
            dense_score=0.92,
            rerank_score=0.97,
        )
        assert doc.bm25_score == 0.85
        assert doc.dense_score == 0.92
        assert doc.rerank_score == 0.97


class TestCitation:
    """Tests for Citation model."""
    
    def test_create_citation(self) -> None:
        """Test creating a Citation instance."""
        citation = Citation(
            article_id="art-46",
            law_id="law-2020-01-01",
            quote="Test quote",
        )
        assert citation.article_id == "art-46"
        assert citation.law_id == "law-2020-01-01"
        assert citation.quote == "Test quote"


class TestEvidencePack:
    """Tests for EvidencePack model."""
    
    def test_create_evidence_pack(self) -> None:
        """Test creating an EvidencePack instance."""
        pack = EvidencePack(
            clause="Test clause",
            verification_level=VerificationLevel.ENTAILED,
            verification_confidence=0.95,
        )
        assert pack.clause == "Test clause"
        assert pack.verification_level == VerificationLevel.ENTAILED
        assert pack.verification_confidence == 0.95
        assert pack.retrieved_documents == []  # default


class TestReviewFinding:
    """Tests for ReviewFinding model."""
    
    def test_create_review_finding(self) -> None:
        """Test creating a ReviewFinding instance."""
        finding = ReviewFinding(
            clause_text="Test clause",
            clause_index=1,
            verification=VerificationLevel.ENTAILED,
            confidence=0.95,
            risk_level=RiskLevel.NONE,
            rationale="Test rationale",
        )
        assert finding.clause_text == "Test clause"
        assert finding.clause_index == 1
        assert finding.verification == VerificationLevel.ENTAILED
        assert finding.risk_level == RiskLevel.NONE


class TestContractReviewResult:
    """Tests for ContractReviewResult model."""
    
    def test_create_contract_review_result(self) -> None:
        """Test creating a ContractReviewResult instance."""
        result = ContractReviewResult(
            contract_id="contract-001",
            summary="Test summary",
            total_clauses=5,
        )
        assert result.contract_id == "contract-001"
        assert result.summary == "Test summary"
        assert result.total_clauses == 5
        assert result.findings == []  # default
        assert isinstance(result.timestamp, datetime)


class TestChatAnswer:
    """Tests for ChatAnswer model."""
    
    def test_create_chat_answer(self) -> None:
        """Test creating a ChatAnswer instance."""
        answer = ChatAnswer(
            answer="Test answer",
            confidence=0.9,
        )
        assert answer.answer == "Test answer"
        assert answer.confidence == 0.9
        assert answer.citations == []  # default


class TestIngestRequest:
    """Tests for IngestRequest model."""
    
    def test_create_ingest_request(self) -> None:
        """Test creating an IngestRequest instance."""
        request = IngestRequest(
            documents=[{"id": "doc-001", "content": "Test"}],
        )
        assert len(request.documents) == 1
        assert request.source == "manual"  # default
        assert request.batch_size == 100  # default
    
    def test_ingest_request_batch_size_validation(self) -> None:
        """Test batch_size validation."""
        # Valid batch sizes
        IngestRequest(documents=[], batch_size=1)
        IngestRequest(documents=[], batch_size=1000)
        
        # Invalid batch sizes
        with pytest.raises(ValidationError):
            IngestRequest(documents=[], batch_size=0)
        with pytest.raises(ValidationError):
            IngestRequest(documents=[], batch_size=1001)


class TestIngestResponse:
    """Tests for IngestResponse model."""
    
    def test_create_ingest_response(self) -> None:
        """Test creating an IngestResponse instance."""
        response = IngestResponse(
            task_id="task-001",
            document_count=10,
        )
        assert response.task_id == "task-001"
        assert response.status == "queued"  # default
        assert response.document_count == 10


class TestContractReviewRequest:
    """Tests for ContractReviewRequest model."""
    
    def test_create_contract_review_request(self) -> None:
        """Test creating a ContractReviewRequest instance."""
        request = ContractReviewRequest(
            contract_text="Test contract text",
        )
        assert request.contract_text == "Test contract text"
        assert request.contract_id is None
        assert request.filters == {}  # default
    
    def test_contract_review_request_min_length(self) -> None:
        """Test contract_text minimum length validation."""
        with pytest.raises(ValidationError):
            ContractReviewRequest(contract_text="Short")  # Less than 10 chars


class TestChatRequest:
    """Tests for ChatRequest model."""
    
    def test_create_chat_request(self) -> None:
        """Test creating a ChatRequest instance."""
        request = ChatRequest(
            query="Test question?",
        )
        assert request.query == "Test question?"
        assert request.session_id is None
    
    def test_chat_request_min_length(self) -> None:
        """Test query minimum length validation."""
        with pytest.raises(ValidationError):
            ChatRequest(query="")  # Empty query


class TestHealthResponse:
    """Tests for HealthResponse model."""
    
    def test_create_health_response(self) -> None:
        """Test creating a HealthResponse instance."""
        response = HealthResponse()
        assert response.status == "ok"  # default
        assert response.version == "0.1.0"  # default
        assert response.services == {}  # default
    
    def test_health_response_with_services(self) -> None:
        """Test HealthResponse with service statuses."""
        response = HealthResponse(
            status="ok",
            services={"api": "ok", "db": "error"},
        )
        assert response.services["api"] == "ok"
        assert response.services["db"] == "error"


class TestContextDocument:
    """Tests for ContextDocument model."""
    
    def test_create_context_document(self) -> None:
        """Test creating a ContextDocument instance."""
        doc = ContextDocument(
            doc_id="doc-001",
            content="Context content",
            relation_type="parent",
        )
        assert doc.doc_id == "doc-001"
        assert doc.content == "Context content"
        assert doc.relation_type == "parent"
