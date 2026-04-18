"""Contract review pipeline orchestrating all components."""
from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from prometheus_client import Histogram

from packages.common.config import Settings
from packages.common.types import (
    Citation,
    ContractReviewResult,
    EvidencePack,
    ReviewFinding,
    RiskLevel,
    VerificationLevel,
    WebSearchResult,
)
from packages.reasoning.generator import LegalGenerator
from packages.reasoning.planner import QueryPlanner
from packages.reasoning.verifier import LegalVerifier
from packages.reasoning.web_search import WebSearchTool
from packages.retrieval.context import ContextInjector
from packages.retrieval.hybrid import HybridRetriever
from packages.retrieval.reranker import LegalReranker

logger = logging.getLogger(__name__)

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
    Supports parallel clause processing and adaptive web search.
    """

    def __init__(self, settings: Settings, max_concurrent: int = 5):
        self.settings = settings
        self.planner = QueryPlanner()
        self.retriever = HybridRetriever(settings)
        self.context_injector = ContextInjector(settings)
        self.verifier = LegalVerifier(settings)
        self.generator = LegalGenerator(settings)
        self.web_search = WebSearchTool()
        self.reranker = LegalReranker(budget_ms=settings.search_reranker_budget_ms)
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def warmup(self) -> None:
        """Warm up the pipeline by pre-loading models and connections.

        This method calls the retriever's warmup to:
        - Load the embedding model and trigger JIT compilation
        - Establish Qdrant and OpenSearch connections
        - Run health-check queries against both backends

        Should be called before processing clauses to eliminate cold-start latency.
        """
        logger.info("Warming up review pipeline...")
        warmup_start = time.time()

        await self.retriever.warmup()

        warmup_time = time.time() - warmup_start
        logger.info(f"Review pipeline warmup completed in {warmup_time:.2f}s")

    async def review_contract(
        self,
        contract_text: str,
        filters: dict | None = None,
        include_relationships: bool = True,
    ) -> ContractReviewResult:
        """
        Review a full contract against the legal corpus.
        
        Steps:
        1. Parse contract into clauses (regex)
        2. For each clause (in parallel with semaphore):
           a. Plan query (planner)
           b. Hybrid retrieve (retrieval)
           c. Assemble EvidencePack (with relationship context)
           d. Verify (verifier)
           e. Generate finding (generator)
        3. Summarize all findings
        
        Args:
            contract_text: The contract text to review
            filters: Optional metadata filters for retrieval
            include_relationships: Whether to include document relationships (default: True)
        """
        start_time = time.time()

        with review_pipeline_duration_seconds.time():
            # Step 1: Parse contract into clauses
            clauses = self._parse_contract_clauses(contract_text)

            # Step 2: Review each clause in parallel
            clause_tasks = []
            clause_times: list[tuple[int, float]] = []  # Track individual clause times

            for clause_index, clause_text in clauses:
                task = self._review_single_clause_with_semaphore(
                    clause_index, clause_text, filters, clause_times, include_relationships
                )
                clause_tasks.append(task)

            # Execute all clause reviews in parallel
            results = await asyncio.gather(*clause_tasks, return_exceptions=True)

            # Process results, maintaining clause order
            findings: list[ReviewFinding] = []
            for i, result in enumerate(results):
                clause_index, clause_text = clauses[i]

                if isinstance(result, Exception):
                    # Log error but continue with other clauses
                    logger.warning(f"Clause {clause_index} review failed: {result}")
                    findings.append(
                        ReviewFinding(
                            clause_text=clause_text,
                            clause_index=clause_index,
                            verification=VerificationLevel.NO_REFERENCE,
                            confidence=0.0,
                            risk_level="low",
                            rationale=f"Review failed: {str(result)}",
                        )
                    )
                else:
                    findings.append(result)

            # Sort findings by clause_index to maintain order
            findings.sort(key=lambda f: f.clause_index)

            # Step 3: Generate summary
            summary = await self.generator.generate_review_summary(findings)

            total_time = (time.time() - start_time) * 1000

            # Log timing stats
            if clause_times:
                sum_individual_times = sum(t for _, t in clause_times)
                logger.info(
                    f"Contract review timing: total_wall_clock={total_time:.2f}ms, "
                    f"sum_individual={sum_individual_times:.2f}ms, "
                    f"speedup={sum_individual_times/total_time:.2f}x, "
                    f"clauses={len(clauses)}"
                )

            return ContractReviewResult(
                contract_id=str(uuid.uuid4()),
                findings=findings,
                summary=summary,
                total_clauses=len(clauses),
                risk_summary=self._build_risk_summary(findings),
                total_latency_ms=total_time,
            )

    async def _review_single_clause_with_semaphore(
        self,
        clause_index: int,
        clause_text: str,
        filters: dict | None,
        timing_list: list[tuple[int, float]],
        include_relationships: bool = True,
    ) -> ReviewFinding:
        """Review a single clause with semaphore-controlled concurrency."""
        async with self._semaphore:
            clause_start = time.time()
            try:
                result = await self._review_single_clause(
                    clause_index, clause_text, filters, include_relationships
                )
                clause_time = (time.time() - clause_start) * 1000
                timing_list.append((clause_index, clause_time))
                return result
            except Exception:
                clause_time = (time.time() - clause_start) * 1000
                timing_list.append((clause_index, clause_time))
                raise

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
            # Skip None values that can result from regex split with capturing groups
            if part is None:
                continue
            part = part.strip()
            if not part:
                continue

            # Skip very short fragments (likely headers)
            if len(part) < 20:
                continue
            
            # Skip content before first "Điều" marker (header/preamble)
            if not re.match(r'.*Điều\s+\d+', part, re.IGNORECASE):
                # Check if this is just preamble without actual clause content
                if 'Điều' not in part or part.count('Điều') == 0:
                    # This is likely header/preamble, skip it
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
        include_relationships: bool = True,
    ) -> ReviewFinding:
        """Review a single clause through the full pipeline with adaptive web search.
        
        Args:
            clause_index: Index of the clause in the contract
            clause_text: Text of the clause
            filters: Optional metadata filters for retrieval
            include_relationships: Whether to include document relationships (default: True)
        """
        clause_start_time = time.time()
        web_sources: list[WebSearchResult] = []

        # a. Plan query
        query_plan = self.planner.plan(clause_text)

        # b. Hybrid retrieve with reranker optimization
        # Fetch more candidates than needed to feed the reranker a richer pool
        reranker_input_k = self.settings.search_reranker_input_k  # default 15
        final_top_k = 10  # Final number of documents after reranking
        
        retrieved_documents = await self.retriever.search(
            query=query_plan.normalized_query,
            query_plan=query_plan,              # Pass full plan for expansion_variants in BM25
            top_k=reranker_input_k,             # Get more candidates for reranker
            bm25_candidates=100,                # Large BM25 pool for better recall
            dense_candidates=100,               # Large Dense pool
            sandwich_reorder=True,              # Better diversity
            filters=filters or query_plan.search_filters,
        )
        
        # c. Rerank the retrieved documents
        reranked_documents = await self.reranker.rerank(
            query=query_plan.normalized_query,
            candidates=retrieved_documents,
            top_k=final_top_k,                  # Trim to final top_k after reranking
        )
        retrieved_documents = reranked_documents

        # d. Assemble EvidencePack with relationship enrichment
        # Build context from articles, grouping by law for coherence
        from collections import defaultdict
        
        law_articles = defaultdict(list)
        for doc in retrieved_documents:
            law_id = doc.metadata.get('law_id', doc.doc_id)
            law_articles[law_id].append(doc)
        
        # Primary regulation: top article
        primary_regulation = retrieved_documents[0].content if retrieved_documents else ""
        
        # Context: Increase coverage - top 5 laws, 3 articles each for better LLM context
        context_parts = []
        for law_id, articles in list(law_articles.items())[:5]:  # Top 5 laws (increased from 3)
            for article in articles[:3]:  # Top 3 articles per law (increased from 2)
                article_title = article.title or ""
                context_parts.append(f"[{article_title}]\n{article.content}")
        
        context = "\n\n".join(context_parts) if context_parts else ""
        
        logger.debug(
            f"Context assembled: {len(law_articles)} unique laws, "
            f"{len(context_parts)} article contexts"
        )
        
        context_documents = []

        # Enrich with relationships from PostgreSQL (primary source)
        if include_relationships:
            try:
                context_documents = await self.context_injector.inject_context(
                    retrieved_documents,
                    top_k=3,
                    include_pg_relationships=True,
                )
                # Also enrich each retrieved document with its related documents
                for doc in retrieved_documents:
                    if not doc.related_documents:
                        await self.context_injector.enrich_with_relationships(doc)
                logger.debug(
                    f"Enriched clause {clause_index} with {len(context_documents)} context docs "
                    f"(relationships enabled)"
                )
            except Exception as e:
                logger.debug(f"Context injection failed for clause {clause_index}: {e}")
        else:
            # Fallback: basic context injection without relationships
            try:
                context_documents = await self.context_injector.inject_context(
                    retrieved_documents,
                    top_k=3,
                    include_pg_relationships=False,
                )
            except Exception as e:
                logger.debug(f"Context injection failed for clause {clause_index}: {e}")

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

        # e. Adaptive web search for low-confidence results
        # DISABLED: Web search not useful for Vietnamese legal domain
        # The ingested corpus (1,146 documents) is more relevant than DuckDuckGo
        # Saves ~30s per contract (5s timeout × 6 clauses)
        confidence = verification_result.get("confidence", 0.0)
        level = verification_result.get("level")

        if confidence < 0.5 or level == VerificationLevel.NO_REFERENCE:
            logger.debug(f"Skipping web search for clause (confidence={confidence:.2f}, level={level})")
        # Old web search code (disabled):
        # web_results = await self.web_search.search_vietnamese_law(clause_text)
        # if web_results:
        #     web_sources = [...]
        #     verification_result = await self.verifier.verify(...)  # re-verify with web context

        # Create EvidencePack
        evidence_pack = EvidencePack(
            clause=clause_text,
            retrieved_documents=retrieved_documents,
            context_documents=context_documents,
            citations=citations,
            web_sources=web_sources,
            verification_level=verification_result.get("level"),
            verification_confidence=verification_result.get("confidence", 0.0),
            verification_reasoning=verification_result.get("reasoning"),
        )

        # f. Generate finding
        finding = await self.generator.generate_finding(evidence_pack)
        finding.clause_index = clause_index
        finding.latency_ms = (time.time() - clause_start_time) * 1000

        return finding

    def _build_risk_summary(self, findings: list[ReviewFinding]) -> dict[str, int]:
        """Count findings by risk level."""
        summary: dict[str, int] = {
            RiskLevel.HIGH: 0,
            RiskLevel.MEDIUM: 0,
            RiskLevel.LOW: 0,
            RiskLevel.NONE: 0,
        }
        for finding in findings:
            summary[finding.risk_level] = summary.get(finding.risk_level, 0) + 1
        return summary

    async def review_contract_stream(
        self,
        contract_text: str,
        filters: dict | None = None,
        include_relationships: bool = True,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Streaming contract review with progress events.
        
        Yields events:
        - {"type": "progress", "data": {"phase": "analyzing", "message": "...", "total_clauses": N}}
        - {"type": "progress", "data": {"phase": "reviewing", "message": "...", "current": X, "total": N}}
        - {"type": "finding", "data": {<ReviewFinding JSON>}}
        - {"type": "progress", "data": {"phase": "summarizing", "message": "..."}}
        - {"type": "summary", "data": {"summary": "...", "risk_summary": {...}, "references": [...]}}
        - {"type": "done", "data": {}}
        
        Args:
            contract_text: The contract text to review
            filters: Optional metadata filters for retrieval
            include_relationships: Whether to include document relationships (default: True)
        """
        start_time = time.time()

        # Step 1: Parse contract into clauses
        clauses = self._parse_contract_clauses(contract_text)
        total_clauses = len(clauses)

        yield {
            "type": "progress",
            "data": {
                "phase": "analyzing",
                "message": "Đang phân tích hợp đồng...",
                "total_clauses": total_clauses,
            }
        }

        # Step 2: Process clauses with progress updates
        findings: list[ReviewFinding] = []

        # Process clauses and yield findings as they complete
        tasks: list[asyncio.Task[tuple[int, ReviewFinding | Exception]]] = []
        for clause_index, clause_text in clauses:
            task = asyncio.create_task(
                self._review_single_clause_result(clause_index, clause_text, filters, include_relationships)
            )
            tasks.append(task)

        # Collect results as they complete
        completed_count = 0
        for task in asyncio.as_completed(tasks):
            clause_index, result = await task
            if not isinstance(result, Exception):
                finding = result
                findings.append(finding)
                completed_count += 1

                yield {
                    "type": "progress",
                    "data": {
                        "phase": "reviewing",
                        "message": f"Đã kiểm tra {completed_count}/{total_clauses} điều khoản...",
                        "current": completed_count,
                        "total": total_clauses,
                    }
                }

                # Yield the finding
                yield {
                    "type": "finding",
                    "data": finding.model_dump(),
                }
            else:
                logger.warning(f"Clause {clause_index} review failed: {result}")
                error_finding = ReviewFinding(
                    clause_text=clauses[clause_index][1] if clause_index < len(clauses) else "",
                    clause_index=clause_index,
                    verification=VerificationLevel.NO_REFERENCE,
                    confidence=0.0,
                    risk_level=RiskLevel.LOW,
                    rationale=f"Review failed: {str(result)}",
                    citations=[],
                )
                findings.append(error_finding)
                completed_count += 1
                yield {
                    "type": "progress",
                    "data": {
                        "phase": "reviewing",
                        "message": f"Đã kiểm tra {completed_count}/{total_clauses} điều khoản...",
                        "current": completed_count,
                        "total": total_clauses,
                    }
                }
                yield {
                    "type": "finding",
                    "data": error_finding.model_dump(),
                }

        # Step 3: Generate summary
        yield {
            "type": "progress",
            "data": {
                "phase": "summarizing",
                "message": "Đang tổng hợp kết quả...",
            }
        }

        # Sort findings by clause_index
        findings.sort(key=lambda f: f.clause_index)

        # Generate summary
        summary = await self.generator.generate_review_summary(findings)

        # Collect unique references
        seen_article_ids: set[str] = set()
        references: list[dict[str, Any]] = []
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

        total_time = (time.time() - start_time) * 1000

        # Yield summary
        yield {
            "type": "summary",
            "data": {
                "summary": summary,
                "risk_summary": self._build_risk_summary(findings),
                "references": references,
                "total_clauses": total_clauses,
                "total_latency_ms": total_time,
            }
        }

        # Yield done
        yield {"type": "done", "data": {}}

    async def _review_single_clause_result(
        self,
        clause_index: int,
        clause_text: str,
        filters: dict | None = None,
        include_relationships: bool = True,
    ) -> tuple[int, ReviewFinding | Exception]:
        """Review a single clause and preserve its index for streaming.
        
        Args:
            clause_index: Index of the clause in the contract
            clause_text: Text of the clause
            filters: Optional metadata filters for retrieval
            include_relationships: Whether to include document relationships (default: True)
        """
        try:
            finding = await self._review_single_clause(
                clause_index, clause_text, filters, include_relationships
            )
            finding.clause_index = clause_index
            return clause_index, finding
        except Exception as exc:
            return clause_index, exc
