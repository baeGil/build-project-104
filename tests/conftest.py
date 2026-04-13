"""Pytest configuration and fixtures."""
from datetime import date, datetime
from typing import Any

import pytest

from packages.common.types import (
    Citation,
    ContextDocument,
    ContractReviewRequest,
    DocumentType,
    EvidencePack,
    HealthResponse,
    IngestRequest,
    LegalNode,
    QueryPlan,
    QueryStrategy,
    RetrievedDocument,
    ReviewFinding,
    RiskLevel,
    VerificationLevel,
)


@pytest.fixture
def sample_legal_node() -> LegalNode:
    """Create a sample legal node for testing."""
    return LegalNode(
        id="law-2020-01-01",
        title="Luật Doanh nghiệp 2020",
        content="Nội dung luật doanh nghiệp...",
        doc_type=DocumentType.LAW,
        level=0,
        publish_date=date(2020, 1, 1),
        issuing_body="Quốc hội",
        document_number="59/2020/QH14",
    )


@pytest.fixture
def sample_query_plan() -> QueryPlan:
    """Create a sample query plan for testing."""
    return QueryPlan(
        original_query="Công ty TNHH có bao nhiêu thành viên?",
        normalized_query="cong ty tnhh co bao nhieu thanh vien",
        expansion_variants=["cong ty trach nhiem huu han thanh vien"],
        has_negation=False,
        citations=["Luật Doanh nghiệp 2020"],
        strategy=QueryStrategy.SEMANTIC,
    )


@pytest.fixture
def sample_retrieved_document() -> RetrievedDocument:
    """Create a sample retrieved document for testing."""
    return RetrievedDocument(
        doc_id="law-2020-01-01-art-46",
        content="Công ty trách nhiệm hữu hạn có thể có 1 hoặc nhiều thành viên...",
        title="Điều 46. Công ty trách nhiệm hữu hạn",
        score=0.95,
        bm25_score=0.85,
        dense_score=0.92,
    )


@pytest.fixture
def sample_citation() -> Citation:
    """Create a sample citation for testing."""
    return Citation(
        article_id="art-46",
        law_id="law-2020-01-01",
        quote="Công ty trách nhiệm hữu hạn có thể có một hoặc nhiều thành viên",
        document_title="Luật Doanh nghiệp 2020",
    )


@pytest.fixture
def sample_context_document() -> ContextDocument:
    """Create a sample context document for testing."""
    return ContextDocument(
        doc_id="law-2020-01-01-art-45",
        content="Quy định chung về công ty trách nhiệm hữu hạn...",
        relation_type="parent",
        title="Điều 45. Quy định chung",
    )


@pytest.fixture
def sample_evidence_pack(sample_retrieved_document: RetrievedDocument) -> EvidencePack:
    """Create a sample evidence pack for testing."""
    return EvidencePack(
        clause="Công ty có 2 thành viên góp vốn",
        retrieved_documents=[sample_retrieved_document],
        verification_level=VerificationLevel.ENTAILED,
        verification_confidence=0.95,
        verification_reasoning="Phù hợp với Điều 46 Luật Doanh nghiệp 2020",
    )


@pytest.fixture
def sample_review_finding(sample_citation: Citation) -> ReviewFinding:
    """Create a sample review finding for testing."""
    return ReviewFinding(
        clause_text="Công ty có 2 thành viên góp vốn",
        clause_index=1,
        verification=VerificationLevel.ENTAILED,
        confidence=0.95,
        risk_level=RiskLevel.NONE,
        rationale="Điều khoản phù hợp với quy định tại Điều 46 Luật Doanh nghiệp 2020",
        citations=[sample_citation],
    )


@pytest.fixture
def sample_ingest_request() -> IngestRequest:
    """Create a sample ingest request for testing."""
    return IngestRequest(
        documents=[
            {
                "id": "law-2020-01-01",
                "title": "Luật Doanh nghiệp 2020",
                "content": "Nội dung luật...",
                "type": "luat",
            }
        ],
        source="test",
        batch_size=10,
    )


@pytest.fixture
def sample_contract_review_request() -> ContractReviewRequest:
    """Create a sample contract review request for testing."""
    return ContractReviewRequest(
        contract_text="HỢP ĐỒNG DỊCH VỤ...",
        contract_id="contract-001",
        filters={"doc_type": "luat"},
    )


@pytest.fixture
def sample_health_response() -> HealthResponse:
    """Create a sample health response for testing."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        services={"api": "ok", "qdrant": "ok"},
    )
