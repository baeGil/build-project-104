/*
 * TypeScript types mirroring the backend API types
 * Based on packages/common/types.py
 */

// Enums
export type DocumentType = "luat" | "nghi_dinh" | "thong_tu" | "quyet_dinh" | "nghi_quyet" | "other";

export type VerificationLevel = "entailed" | "contradicted" | "partially_supported" | "no_reference";

export type RiskLevel = "high" | "medium" | "low" | "none";

export type QueryStrategy = "citation" | "negation" | "semantic";

// Core Models
export interface LegalNode {
  id: string;
  title: string;
  content: string;
  doc_type: DocumentType;
  parent_id?: string;
  children_ids: string[];
  level: number;
  publish_date?: string;
  effective_date?: string;
  expiry_date?: string;
  issuing_body?: string;
  document_number?: string;
  amendment_refs: string[];
  citation_refs: string[];
  embedding_id?: string;
  keywords: string[];
}

export interface QueryPlan {
  original_query: string;
  normalized_query: string;
  expansion_variants: string[];
  has_negation: boolean;
  negation_scope?: string;
  citations: string[];
  strategy: QueryStrategy;
  search_filters: Record<string, unknown>;
}

export interface RetrievedDocument {
  doc_id: string;
  content: string;
  title?: string;
  score: number;
  bm25_score?: number;
  dense_score?: number;
  rerank_score?: number;
  metadata: Record<string, unknown>;
}

export interface Citation {
  article_id: string;
  law_id: string;
  quote: string;
  document_title?: string;
  url?: string;
}

export interface ContextDocument {
  doc_id: string;
  content: string;
  relation_type: string;
  title?: string;
}

export interface EvidencePack {
  clause: string;
  retrieved_documents: RetrievedDocument[];
  context_documents: ContextDocument[];
  citations: Citation[];
  verification_level?: VerificationLevel;
  verification_confidence: number;
  verification_reasoning?: string;
}

export interface ReviewFinding {
  clause_text: string;
  clause_index: number;
  verification: VerificationLevel;
  confidence: number;
  risk_level: RiskLevel;
  rationale: string;
  citations: Citation[];
  revision_suggestion?: string;
  negotiation_note?: string;
  evidence_pack?: EvidencePack;
  latency_ms: number;
}

export interface ContractReviewResult {
  contract_id: string;
  findings: ReviewFinding[];
  summary: string;
  total_clauses: number;
  risk_summary: Record<RiskLevel, number>;
  total_latency_ms: number;
  timestamp: string;
}

export interface ChatAnswer {
  answer: string;
  citations: Citation[];
  confidence: number;
  evidence_pack?: EvidencePack;
  latency_ms: number;
}

// Request/Response Models
export interface IngestRequest {
  documents: Record<string, unknown>[];
  source: string;
  batch_size: number;
}

export interface IngestResponse {
  task_id: string;
  status: string;
  document_count: number;
  message: string;
}

export interface ContractReviewRequest {
  contract_text: string;
  contract_id?: string;
  filters?: Record<string, unknown>;
}

export interface ChatRequest {
  query: string;
  session_id?: string;
  filters?: Record<string, unknown>;
}

export interface HealthResponse {
  status: string;
  version: string;
  services: Record<string, string>;
}

// UI-specific types
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  confidence?: number;
  isStreaming?: boolean;
}

export interface CitationDetail extends Citation {
  full_text?: string;
  parent_document?: string;
  related_amendments?: string[];
  original_source_url?: string;
}
