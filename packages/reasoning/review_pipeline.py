"""Contract review pipeline orchestrating all components."""
from __future__ import annotations

import re
import time
import uuid
from typing import Any

from prometheus_client import Histogram

from packages.common.config import Settings
from packages.common.types import (
    Citation,
    ContractReviewResult,
    EvidencePack,
    RetrievedDocument,
    ReviewFinding,
    VerificationLevel,
)
from packages.reasoning.generator import LegalGenerator
from packages.reasoning.planner import QueryPlanner
from packages.reasoning.verifier import LegalVerifier
from packages.retrieval.hybrid import HybridRetriever

# Prometheus metrics
review_pipeline_duration_seconds = Histogram(
    "review_pipeline_duration_seconds",
    "Time spent on full contract review pipeline",
)


class ContractReviewPipeline:
    """
    Orchestrates the full deterministic review pipeline:
    Parse -> Plan -> Retrieve -> Rerank -> Verify -> Generate
    
    No adaptive looping. Fixed pipeline stages.
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.planner = QueryPlanner()
        self.retriever = HybridRetriever()
        self.verifier = LegalVerifier(settings)
        self.generator = LegalGenerator(settings)
    
    async def review_contract(
        self, contract_text: str, filters: dict | None = None
    ) -> ContractReviewResult:
        """
        Review a full contract against the legal corpus.
        
        Steps:
        1. Parse contract into clauses (regex)
        2. For each clause:
           a. Plan query (planner)
           b. Hybrid retrieve (retrieval)
           c. Assemble EvidencePack
           d. Verify (verifier)
           e. Generate finding (generator)
        3. Summarize all findings
        """
        start_time = time.time()
        
        with review_pipeline_duration_seconds.time():
            # Step 1: Parse contract into clauses
            clauses = self._parse_contract_clauses(contract_text)
            
            # Step 2: Review each clause
            findings: list[ReviewFinding] = []
            for clause_index, clause_text in clauses:
                try:
                    finding = await self._review_single_clause(
                        clause_index, clause_text, filters
                    )
                    findings.append(finding)
                except Exception as e:
                    # Log error but continue with other clauses
                    findings.append(
                        ReviewFinding(
                            clause_text=clause_text,
                            clause_index=clause_index,
                            verification=VerificationLevel.NO_REFERENCE,
                            confidence=0.0,
                            risk_level="low",
                            rationale=f"Review failed: {str(e)}",
                        )
                    )
            
            # Step 3: Generate summary
            summary = await self.generator.generate_review_summary(findings)
            
            total_time = (time.time() - start_time) * 1000
            
            return ContractReviewResult(
                contract_id=str(uuid.uuid4()),
                findings=findings,
                summary=summary,
                total_clauses=len(clauses),
                risk_summary=self._build_risk_summary(findings),
                total_latency_ms=total_time,
            )
    
    def _parse_contract_clauses(self, contract_text: str) -> list[tuple[int, str]]:
        """
        Parse contract into individual clauses.
        Returns list of (clause_index, clause_text).
        Uses regex to split on Vietnamese article markers (Điều).
        """
        if not contract_text or not contract_text.strip():
            return []
        
        # Vietnamese article markers
        article_patterns = [
            r'(?:^|\n)\s*Điều\s+\d+',  # "Điều 1", "Điều 2", etc.
            r'(?:^|\n)\s*Điều thứ\s+\d+',  # "Điều thứ 1"
            r'(?:^|\n)\s*Điều\s+[IVX]+',  # Roman numerals
            r'(?:^|\n)\s*Chương\s+\w+',  # Chapters as fallback
            r'(?:^|\n)\s*Mục\s+\w+',  # Sections
        ]
        
        combined_pattern = '|'.join(f'({p})' for p in article_patterns)
        
        # Split by article markers
        parts = re.split(f'(?={combined_pattern})', contract_text, flags=re.IGNORECASE)
        
        clauses: list[tuple[int, str]] = []
        clause_index = 0
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Skip very short fragments (likely headers)
            if len(part) < 20:
                continue
            
            clauses.append((clause_index, part))
            clause_index += 1
        
        # If no clauses found, treat entire text as one clause
        if not clauses and contract_text.strip():
            clauses = [(0, contract_text.strip())]
        
        return clauses
    
    async def _review_single_clause(
        self,
        clause_index: int,
        clause_text: str,
        filters: dict | None = None,
    ) -> ReviewFinding:
        """Review a single clause through the full pipeline."""
        clause_start_time = time.time()
        
        # a. Plan query
        query_plan = await self.planner.plan(clause_text)
        
        # b. Hybrid retrieve
        retrieved_docs = await self.retriever.retrieve(
            query=query_plan.normalized_query,
            top_k=5,
            filters=filters or query_plan.search_filters,
        )
        
        # Convert to RetrievedDocument objects
        retrieved_documents = [
            RetrievedDocument(
                doc_id=doc.get("id", doc.get("doc_id", str(i))),
                content=doc.get("content", ""),
                title=doc.get("title"),
                score=doc.get("score", 0.0),
                bm25_score=doc.get("bm25_score"),
                dense_score=doc.get("dense_score"),
                rerank_score=doc.get("rerank_score"),
                metadata=doc.get("metadata", {}),
            )
            for i, doc in enumerate(retrieved_docs)
        ]
        
        # c. Assemble EvidencePack
        # Use top retrieved doc as primary regulation
        primary_regulation = retrieved_documents[0].content if retrieved_documents else ""
        context = "\n\n".join([d.content for d in retrieved_documents[1:3]]) if len(retrieved_documents) > 1 else ""
        
        # Build citations from retrieved docs
        citations = []
        for doc in retrieved_documents[:3]:
            citations.append(
                Citation(
                    article_id=doc.doc_id,
                    law_id=doc.metadata.get("law_id", "unknown"),
                    quote=doc.content[:200],
                    document_title=doc.title,
                )
            )
        
        # d. Verify
        verification_result = await self.verifier.verify(
            clause=clause_text,
            regulation=primary_regulation,
            context=context,
        )
        
        # Create EvidencePack
        evidence_pack = EvidencePack(
            clause=clause_text,
            retrieved_documents=retrieved_documents,
            citations=citations,
            verification_level=verification_result.get("level"),
            verification_confidence=verification_result.get("confidence", 0.0),
            verification_reasoning=verification_result.get("reasoning"),
        )
        
        # e. Generate finding
        finding = await self.generator.generate_finding(evidence_pack)
        finding.clause_index = clause_index
        finding.latency_ms = (time.time() - clause_start_time) * 1000
        
        return finding
    
    def _build_risk_summary(self, findings: list[ReviewFinding]) -> dict[str, int]:
        """Count findings by risk level."""
        from packages.common.types import RiskLevel
        
        summary: dict[str, int] = {
            RiskLevel.HIGH: 0,
            RiskLevel.MEDIUM: 0,
            RiskLevel.LOW: 0,
            RiskLevel.NONE: 0,
        }
        for finding in findings:
            summary[finding.risk_level] = summary.get(finding.risk_level, 0) + 1
        return summary
