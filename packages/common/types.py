"""Core domain types for Vietnamese Legal Contract Review system."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Vietnamese legal document types."""
    LAW = "luat"                    # Luật
    DECREE = "nghi_dinh"           # Nghị định
    CIRCULAR = "thong_tu"          # Thông tư
    DECISION = "quyet_dinh"        # Quyết định
    RESOLUTION = "nghi_quyet"      # Nghị quyết
    OTHER = "other"


class VerificationLevel(str, Enum):
    """Clause verification classification."""
    ENTAILED = "entailed"
    CONTRADICTED = "contradicted"
    PARTIALLY_SUPPORTED = "partially_supported"
    NO_REFERENCE = "no_reference"


class RiskLevel(str, Enum):
    """Risk assessment levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class QueryStrategy(str, Enum):
    """Query routing strategies."""
    CITATION = "citation"       # Exact legal reference lookup
    NEGATION = "negation"       # Negation-aware retrieval
    SEMANTIC = "semantic"       # Standard hybrid retrieval


class LegalNode(BaseModel):
    """Parsed legal document node with hierarchy and metadata."""
    id: str = Field(..., description="Unique document/node identifier")
    title: str = Field(..., description="Document or article title")
    content: str = Field(..., description="Full text content")
    doc_type: DocumentType = Field(..., description="Legal document type")
    
    # Hierarchy
    parent_id: Optional[str] = Field(None, description="Parent node ID")
    children_ids: list[str] = Field(default_factory=list, description="Child node IDs")
    level: int = Field(0, description="Hierarchy depth: 0=law, 1=chapter, 2=article, 3=clause")
    
    # Metadata
    publish_date: Optional[date] = None
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    issuing_body: Optional[str] = None
    document_number: Optional[str] = None
    
    # Relationships
    amendment_refs: list[str] = Field(default_factory=list, description="IDs of amended documents")
    citation_refs: list[str] = Field(default_factory=list, description="IDs of cited documents")
    
    # Search metadata
    embedding_id: Optional[str] = Field(None, description="Vector DB reference")
    keywords: list[str] = Field(default_factory=list)


class QueryPlan(BaseModel):
    """Structured query plan output from the Query Planner."""
    original_query: str
    normalized_query: str
    expansion_variants: list[str] = Field(default_factory=list, description="Synonym-expanded queries")
    
    has_negation: bool = False
    negation_scope: Optional[str] = None
    
    citations: list[str] = Field(default_factory=list, description="Extracted legal citation patterns")
    strategy: QueryStrategy = QueryStrategy.SEMANTIC
    
    search_filters: dict[str, Any] = Field(default_factory=dict, description="Metadata filters for retrieval")


class RetrievedDocument(BaseModel):
    """A single retrieved document with scores."""
    doc_id: str
    content: str
    title: Optional[str] = None
    score: float = 0.0
    bm25_score: Optional[float] = None
    dense_score: Optional[float] = None
    rerank_score: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    """A legal citation reference."""
    article_id: str
    law_id: str
    quote: str
    document_title: Optional[str] = None
    url: Optional[str] = None


class ContextDocument(BaseModel):
    """Context document for injection (parent/sibling/amendment)."""
    doc_id: str
    content: str
    relation_type: str  # "parent" | "sibling" | "amendment" | "related"
    title: Optional[str] = None


class EvidencePack(BaseModel):
    """Pre-assembled evidence bundle for the generator. Generator NEVER searches on its own."""
    clause: str
    retrieved_documents: list[RetrievedDocument] = Field(default_factory=list)
    context_documents: list[ContextDocument] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    verification_level: Optional[VerificationLevel] = None
    verification_confidence: float = 0.0
    verification_reasoning: Optional[str] = None


class ReviewFinding(BaseModel):
    """Single finding from contract review."""
    clause_text: str
    clause_index: int
    verification: VerificationLevel
    confidence: float
    risk_level: RiskLevel
    rationale: str
    citations: list[Citation] = Field(default_factory=list)
    revision_suggestion: Optional[str] = None
    negotiation_note: Optional[str] = None
    
    # Audit trail
    evidence_pack: Optional[EvidencePack] = None
    latency_ms: float = 0.0


class ContractReviewResult(BaseModel):
    """Complete contract review output."""
    contract_id: str
    findings: list[ReviewFinding] = Field(default_factory=list)
    summary: str = ""
    total_clauses: int = 0
    risk_summary: dict[str, int] = Field(default_factory=dict)  # risk_level -> count
    total_latency_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatAnswer(BaseModel):
    """Response from legal chat endpoint."""
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = 0.0
    evidence_pack: Optional[EvidencePack] = None
    latency_ms: float = 0.0


# Request/Response models for API
class IngestRequest(BaseModel):
    """Request to ingest legal corpus documents."""
    documents: list[dict[str, Any]] = Field(..., description="Raw legal documents to ingest")
    source: str = Field("manual", description="Source identifier")
    batch_size: int = Field(100, ge=1, le=1000)


class IngestResponse(BaseModel):
    """Response from ingestion endpoint."""
    task_id: str
    status: str = "queued"
    document_count: int
    message: str = ""


class ContractReviewRequest(BaseModel):
    """Request to review a contract."""
    contract_text: str = Field(..., min_length=10, description="Contract text to review")
    contract_id: Optional[str] = None
    filters: dict[str, Any] = Field(default_factory=dict, description="Optional metadata filters")


class ChatRequest(BaseModel):
    """Request for legal chat."""
    query: str = Field(..., min_length=1, description="Legal question")
    session_id: Optional[str] = None
    filters: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = "0.1.0"
    services: dict[str, str] = Field(default_factory=dict)
