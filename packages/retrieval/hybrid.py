"""Hybrid search combining BM25 lexical and dense semantic retrieval."""

import asyncio
import logging
import time
from typing import Any

from prometheus_client import Histogram

from packages.common.config import Settings
from packages.common.types import DocumentRelationship, QueryPlan, RelationshipType, RetrievedDocument
from packages.common.score_normalizer import RRFNormalizer
from packages.retrieval.embedding import EmbeddingService
from packages.retrieval.rrf import adaptive_rrf_params, reciprocal_rank_fusion, weighted_rrf

logger = logging.getLogger(__name__)

# Prometheus histograms for instrumentation
BM25_SEARCH_DURATION = Histogram(
    "bm25_search_duration_seconds",
    "BM25 search latency",
)
DENSE_SEARCH_DURATION = Histogram(
    "dense_search_duration_seconds",
    "Dense search latency",
)
RRF_FUSION_DURATION = Histogram(
    "rrf_fusion_duration_seconds",
    "RRF fusion latency",
)
HYBRID_SEARCH_DURATION = Histogram(
    "hybrid_search_duration_seconds",
    "Total hybrid search latency",
)


class HybridSearchEngine:
    """
    Runs BM25 (OpenSearch) and dense (Qdrant) retrieval in parallel,
    then fuses results with RRF.

    Target: <150ms for parallel retrieval + 20ms for RRF fusion
    """

    def __init__(
        self,
        settings: Settings,
        normalize_scores: bool = True,
        score_scale: int = 100,
    ):
        """Initialize the hybrid search engine.

        Args:
            settings: Application settings with DB connection info
            normalize_scores: Whether to normalize RRF scores (default: True)
            score_scale: Target scale for normalized scores (100 for 0-100, 10 for 0-10)
        """
        self.settings = settings
        self._qdrant_client = None
        self._opensearch_client = None
        self._embedding_service = EmbeddingService.get_instance(
            model_name=settings.embedding_model
        )
        self._postgres_pool = None
        
        # Score normalizer for better UX
        self._normalize_scores = normalize_scores
        self._score_normalizer = RRFNormalizer(
            scale=score_scale,
            method="centered",  # Preserve distribution, avoid skew
        ) if normalize_scores else None

    async def warmup(self) -> None:
        """Warm up the hybrid search engine by pre-loading models and connections.

        This method:
        1. Warms up the embedding service (loads model, triggers JIT compilation)
        2. Establishes Qdrant and OpenSearch client connections
        3. Runs lightweight health-check queries against both backends

        All errors are caught and logged gracefully - warmup failures should not
        block application startup.
        """
        logger.info("Starting hybrid search engine warmup...")
        warmup_start = time.time()

        # 1. Warm up embedding service (runs in thread pool since it's sync)
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._embedding_service.warmup)
            logger.debug("Embedding service warmup completed")
        except Exception as e:
            logger.warning(f"Embedding service warmup failed (non-fatal): {e}")

        # 2. Warm up Qdrant connection with a lightweight query
        try:
            qdrant_client = await self._get_qdrant_client()
            # Run a minimal scroll to verify connection (limit=1)
            await qdrant_client.scroll(
                collection_name=self.settings.qdrant_collection,
                limit=1,
                with_payload=False,
                with_vectors=False,
            )
            logger.debug("Qdrant connection warmup completed")
        except Exception as e:
            logger.warning(f"Qdrant connection warmup failed (non-fatal): {e}")

        # 3. Warm up OpenSearch connection with a count query
        try:
            opensearch_client = await self._get_opensearch_client()
            # Run a count query to verify connection
            await opensearch_client.count(
                index=self.settings.opensearch_index,
                body={"query": {"match_all": {}}},
            )
            logger.debug("OpenSearch connection warmup completed")
        except Exception as e:
            logger.warning(f"OpenSearch connection warmup failed (non-fatal): {e}")

        # 4. Warm up PostgreSQL connection pool
        try:
            await self._get_postgres_pool()
            logger.debug("PostgreSQL connection pool warmup completed")
        except Exception as e:
            logger.warning(f"PostgreSQL connection warmup failed (non-fatal): {e}")

        warmup_time = time.time() - warmup_start
        logger.info(f"Hybrid search engine warmup completed in {warmup_time:.2f}s")

    async def _get_qdrant_client(self):
        """Get or create async Qdrant client."""
        if self._qdrant_client is None:
            try:
                from qdrant_client import AsyncQdrantClient

                self._qdrant_client = AsyncQdrantClient(
                    host=self.settings.qdrant_host,
                    port=self.settings.qdrant_port,
                )
                logger.info(
                    f"Connected to Qdrant at {self.settings.qdrant_host}:{self.settings.qdrant_port}"
                )
            except Exception as e:
                logger.error(f"Failed to connect to Qdrant: {e}")
                raise
        return self._qdrant_client

    async def _get_opensearch_client(self):
        """Get or create async OpenSearch client."""
        if self._opensearch_client is None:
            try:
                from opensearchpy import AsyncOpenSearch

                self._opensearch_client = AsyncOpenSearch(
                    hosts=[
                        {
                            "host": self.settings.opensearch_host,
                            "port": self.settings.opensearch_port,
                        }
                    ],
                    http_auth=(
                        self.settings.opensearch_user,
                        self.settings.opensearch_password,
                    ),
                    use_ssl=self.settings.opensearch_use_ssl,
                    verify_certs=self.settings.opensearch_verify_certs,
                )
                logger.info(
                    f"Connected to OpenSearch at {self.settings.opensearch_host}:{self.settings.opensearch_port}"
                )
            except Exception as e:
                logger.error(f"Failed to connect to OpenSearch: {e}")
                raise
        return self._opensearch_client

    async def _get_postgres_pool(self):
        """Get or create async PostgreSQL pool."""
        if self._postgres_pool is None:
            try:
                import asyncpg

                self._postgres_pool = await asyncpg.create_pool(
                    self.settings.postgres_dsn,
                    min_size=5,
                    max_size=20,
                )
                logger.info("Connected to PostgreSQL")
            except Exception as e:
                logger.error(f"Failed to connect to PostgreSQL: {e}")
                raise
        return self._postgres_pool

    async def search(
        self,
        query: str,
        query_plan: QueryPlan | None = None,
        top_k: int = 5,
        bm25_candidates: int | None = None,
        dense_candidates: int | None = None,
        rrf_k: int | None = None,
        filters: dict | None = None,
        sandwich_reorder: bool = True,
    ) -> list[RetrievedDocument]:
        """Execute hybrid search: parallel BM25 + dense -> RRF fusion.

        Uses asyncio.gather for parallel execution.
        Applies metadata filters to both searches.
        Optionally applies sandwich reordering to combat lost-in-the-middle attention decay.

        Args:
            query: Search query text
            query_plan: Optional query plan for search strategy
            top_k: Number of results to return
            bm25_candidates: Number of BM25 candidates to retrieve (defaults to config)
            dense_candidates: Number of dense candidates to retrieve (defaults to config)
            rrf_k: RRF constant for fusion (defaults to config)
            filters: Optional metadata filters
            sandwich_reorder: Whether to apply sandwich reordering (default: True)

        Returns:
            List of retrieved documents with fused scores
        """
        # Use config defaults if not provided
        if bm25_candidates is None:
            bm25_candidates = self.settings.search_bm25_candidates
        if dense_candidates is None:
            dense_candidates = self.settings.search_dense_candidates
        if rrf_k is None:
            rrf_k = self.settings.search_rrf_k

        with HYBRID_SEARCH_DURATION.time():
            try:
                # Extract expansion variants from query_plan for BM25 multi-query boosting
                expansion_queries: list[str] | None = None
                if query_plan and query_plan.expansion_variants:
                    expansion_queries = list(query_plan.expansion_variants)[:5]
                    logger.debug(
                        f"Search: using {len(expansion_queries)} expansion variants from query_plan"
                    )

                # Adaptive candidate pool scaling:
                # Scales with top_k so recall stays high as the corpus grows to 180k+ docs.
                # Formula: max(caller-specified, top_k×20), capped at 500 to keep latency bounded.
                effective_bm25 = max(bm25_candidates, min(top_k * 20, 500))
                effective_dense = max(dense_candidates, min(top_k * 20, 500))

                # Run BM25 and dense search in parallel
                bm25_task = self._bm25_search(
                    query, size=effective_bm25, filters=filters,
                    expansion_queries=expansion_queries,
                )
                dense_task = self._dense_search(
                    query, limit=effective_dense, filters=filters
                )

                bm25_results, dense_results = await asyncio.gather(
                    bm25_task, dense_task, return_exceptions=True
                )

                # Handle exceptions
                if isinstance(bm25_results, Exception):
                    logger.error(f"BM25 search failed: {bm25_results}")
                    bm25_results = []
                if isinstance(dense_results, Exception):
                    logger.error(f"Dense search failed: {dense_results}")
                    dense_results = []

                # Build score lookup dictionaries
                bm25_scores = {doc_id: score for doc_id, score in bm25_results}
                dense_scores = {doc_id: score for doc_id, score in dense_results}

                # Adaptive RRF parameters based on query characteristics
                # Falls back to defaults if no query_plan provided
                adaptive_k, adaptive_weights = adaptive_rrf_params(query_plan)

                # If rrf_k was explicitly passed, it overrides adaptive value
                effective_rrf_k = rrf_k if rrf_k is not None else adaptive_k
                effective_weights = adaptive_weights

                # RRF fusion with adaptive pool size:
                # Dense embeddings are NOT trained on Vietnamese legal domain,
                # so they may rank relevant docs poorly (#30-50). BM25 is the primary
                # signal for legal term matching.
                # Using a large pool ensures both root docs AND articles survive to reranker
                # for hierarchical aggregation
                logger.debug(
                    f"RRF fusion: k={effective_rrf_k}, weights={effective_weights}, "
                    f"top_n={self.settings.search_rrf_top_n}"
                )
                with RRF_FUSION_DURATION.time():
                    fused_results = weighted_rrf(
                        result_lists=[bm25_results, dense_results],
                        weights=effective_weights,
                        k=effective_rrf_k,
                        top_n=self.settings.search_rrf_top_n,
                    )

                # Normalize RRF scores if enabled (adaptive, no hardcoding!)
                if self._normalize_scores and self._score_normalizer and fused_results:
                    raw_scores = [score for _, score in fused_results]
                    normalized_scores = self._score_normalizer.normalize_rrf_scores(raw_scores)
                    
                    # Replace scores with normalized versions
                    fused_results = [
                        (doc_id, norm_score)
                        for (doc_id, _), norm_score in zip(fused_results, normalized_scores)
                    ]
                    
                    logger.debug(
                        f"Scores normalized: "
                        f"raw=[{min(raw_scores):.4f}-{max(raw_scores):.4f}] → "
                        f"normalized=[{min(normalized_scores):.1f}-{max(normalized_scores):.1f}]"
                    )

                # Fetch full documents
                doc_ids = [doc_id for doc_id, _ in fused_results]
                fused_scores = {doc_id: score for doc_id, score in fused_results}

                documents = await self._fetch_documents(doc_ids, fused_scores)
                
                # HIERARCHICAL AGGREGATION: Group articles by law_id and aggregate scores
                documents = self._aggregate_article_scores(documents)

                # Add individual scores to documents
                # Note: bm25_scores and dense_scores may contain chunk/article IDs
                # We need to look up by root doc ID to match the consolidated documents
                for doc in documents:
                    # Try direct lookup first, then root doc ID lookup
                    doc.bm25_score = bm25_scores.get(doc.doc_id)
                    if doc.bm25_score is None:
                        # Try to find any score from chunk/article refs that map to this root
                        for original_id, score in bm25_scores.items():
                            if self._extract_root_doc_id(str(original_id)) == doc.doc_id:
                                doc.bm25_score = score
                                break
                    
                    doc.dense_score = dense_scores.get(doc.doc_id)
                    if doc.dense_score is None:
                        # Try to find any score from chunk/article refs that map to this root
                        for original_id, score in dense_scores.items():
                            if self._extract_root_doc_id(str(original_id)) == doc.doc_id:
                                doc.dense_score = score
                                break

                # Apply top_k BEFORE sandwich reordering to ensure we don't lose
                # relevant documents that get pushed to the end of the reordered list
                documents = documents[:top_k]
                
                # Apply sandwich reordering if enabled
                if sandwich_reorder and len(documents) > 2:
                    documents = self._apply_sandwich_reorder(documents)

                return documents

            except Exception as e:
                logger.error(f"Hybrid search failed: {e}")
                raise

    def _apply_sandwich_reorder(
        self, documents: list[RetrievedDocument]
    ) -> list[RetrievedDocument]:
        """Reorder documents to combat LLM attention decay (lost-in-the-middle).

        Algorithm: Sort by score, then interleave: [1st, 3rd, 5th, ..., 6th, 4th, 2nd]
        This places most relevant docs at the start and end, with less relevant in the middle.

        Args:
            documents: List of retrieved documents (assumed to be sorted by score descending)

        Returns:
            Reordered list of documents
        """
        if len(documents) <= 2:
            return documents

        # Sort by score descending to ensure proper ordering
        sorted_docs = sorted(documents, key=lambda d: d.score, reverse=True)

        n = len(sorted_docs)

        # Split into odd and even indices (1-indexed for clarity)
        # Odd positions (1st, 3rd, 5th...) go first in order
        odd_positions = [sorted_docs[i] for i in range(0, n, 2)]
        # Even positions (2nd, 4th, 6th...) go last in reverse order
        even_positions = [sorted_docs[i] for i in range(1, n, 2)]
        even_positions.reverse()

        # Combine: high relevance at start and end
        reordered = odd_positions + even_positions

        logger.debug(
            f"Sandwich reorder: {n} documents reordered from "
            f"[{sorted_docs[0].doc_id}, ..., {sorted_docs[-1].doc_id}] to "
            f"[{reordered[0].doc_id}, ..., {reordered[-1].doc_id}]"
        )

        return reordered

    def _aggregate_article_scores(self, documents: list[RetrievedDocument]) -> list[RetrievedDocument]:
        """Hierarchical aggregation: Group articles by law_id and aggregate scores.
        
        When searching, we get a mix of:
        - Root documents (chunk_type='document')
        - Articles (chunk_type='article')
        
        Strategy:
        1. Group all articles by law_id
        2. For each law: aggregate article scores (sum or weighted avg)
        3. Compare aggregated article score vs root document score
        4. Keep whichever is higher (articles or root doc)
        5. Sort by final score
        
        This ensures:
        - If multiple articles match strongly → law ranks high
        - If only root doc matches → root doc ranks
        - Best of both worlds
        
        Args:
            documents: List of retrieved documents (mix of articles and root docs)
            
        Returns:
            Sorted list with best representations per law_id
        """
        from collections import defaultdict
        
        # Group by law_id
        law_groups = defaultdict(lambda: {'articles': [], 'root_doc': None})
        
        for doc in documents:
            law_id = doc.metadata.get('law_id')
            if not law_id:
                # No law_id, treat as unique
                law_id = doc.doc_id
            
            chunk_type = doc.metadata.get('chunk_type', 'document')
            
            if chunk_type == 'article':
                law_groups[law_id]['articles'].append(doc)
            else:
                # Root document
                law_groups[law_id]['root_doc'] = doc

        # Calculate percentile floor: top 33% threshold of all document scores
        # Articles exceeding this floor should be included regardless of root doc comparison
        all_scores = [doc.score for doc in documents]
        if all_scores:
            sorted_scores = sorted(all_scores, reverse=True)
            # Index for top 33% percentile (floor division)
            percentile_idx = max(0, len(sorted_scores) // 3 - 1)
            score_floor = sorted_scores[percentile_idx]
        else:
            score_floor = 0.0

        logger.debug(
            f"Hierarchical aggregation: {len(documents)} docs, "
            f"score_floor (top 33% percentile)={score_floor:.4f}"
        )

        # For each law, determine best representation
        final_documents = []
        
        for law_id, group in law_groups.items():
            articles = group['articles']
            root_doc = group['root_doc']
            
            if not articles and root_doc:
                # Only root doc, use it
                final_documents.append(root_doc)
            elif articles and not root_doc:
                # Only articles, use top article with aggregated score metadata
                articles.sort(key=lambda d: d.score, reverse=True)
                top_article = articles[0]
                
                # Aggregate score: sum of all article scores (indicates stronger match)
                aggregated_score = sum(a.score for a in articles)
                top_article.metadata['aggregated_score'] = aggregated_score
                top_article.metadata['matching_articles_count'] = len(articles)
                top_article.metadata['matching_article_numbers'] = [
                    a.metadata.get('article_number') for a in articles[:5]
                    if a.metadata.get('article_number')
                ]
                
                final_documents.append(top_article)
            elif articles and root_doc:
                # Both exist: compare aggregated article score vs root doc score
                aggregated_score = sum(a.score for a in articles)

                # Check if any article exceeds the percentile floor
                # This ensures high-scoring articles are not discarded due to root doc presence
                has_high_scoring_article = any(a.score >= score_floor for a in articles)

                if aggregated_score > root_doc.score * self.settings.search_aggregation_threshold:
                    # Articles collectively stronger (threshold to prefer granularity)
                    articles.sort(key=lambda d: d.score, reverse=True)
                    top_article = articles[0]
                    top_article.metadata['aggregated_score'] = aggregated_score
                    top_article.metadata['matching_articles_count'] = len(articles)
                    top_article.metadata['matching_article_numbers'] = [
                        a.metadata.get('article_number') for a in articles[:5]
                        if a.metadata.get('article_number')
                    ]
                    top_article.metadata['used_aggregation'] = True
                    final_documents.append(top_article)
                elif has_high_scoring_article:
                    # Percentile floor: include articles if any single one exceeds top 20%
                    articles.sort(key=lambda d: d.score, reverse=True)
                    top_article = articles[0]
                    top_article.metadata['aggregated_score'] = aggregated_score
                    top_article.metadata['matching_articles_count'] = len(articles)
                    top_article.metadata['matching_article_numbers'] = [
                        a.metadata.get('article_number') for a in articles[:5]
                        if a.metadata.get('article_number')
                    ]
                    top_article.metadata['percentile_floor_applied'] = True
                    logger.debug(
                        f"Article {top_article.doc_id} exceeded percentile floor "
                        f"(score={top_article.score:.4f} >= floor={score_floor:.4f})"
                    )
                    final_documents.append(top_article)
                else:
                    # Root doc stronger or comparable, use it for full context
                    # BUT: Preserve individual articles that score above median
                    # This prevents collapsing a law_id group into just one result
                    # when multiple distinct matches exist
                    sorted_all_scores = sorted(all_scores, reverse=True)
                    median_score = sorted_all_scores[len(sorted_all_scores) // 2] if sorted_all_scores else 0
                    
                    root_doc.metadata['article_scores_available'] = len(articles)
                    root_doc.metadata['aggregated_article_score'] = aggregated_score
                    final_documents.append(root_doc)
                    
                    # Preserve high-scoring articles independently
                    for article in articles:
                        if article.score >= median_score:
                            # Keep this article as a separate result
                            article.metadata['preserved_independently'] = True
                            article.metadata['median_threshold'] = median_score
                            logger.debug(
                                f"Preserving article {article.doc_id} independently "
                                f"(score={article.score:.4f} >= median={median_score:.4f})"
                            )
                            final_documents.append(article)
        
        # Sort by score (use aggregated_score if available)
        final_documents.sort(
            key=lambda d: d.metadata.get('aggregated_score', d.score),
            reverse=True
        )
        
        logger.debug(
            f"Hierarchical aggregation: {len(documents)} docs → {len(final_documents)} laws"
        )
        
        return final_documents

    async def _bm25_search(
        self,
        query: str,
        size: int = 100,
        filters: dict | None = None,
        expansion_queries: list[str] | None = None,
    ) -> list[tuple[str, float]]:
        """BM25 search via OpenSearch.

        Builds a multi-field query with title heavily weighted (title^4) for
        legal document retrieval, plus phrase-boost should-clauses for exact
        matches and optional expansion-variant should-clauses for synonym recall.

        Args:
            query: Search query
            size: Number of results to retrieve
            filters: Optional metadata filters
            expansion_queries: Optional list of synonym/expansion variant queries
                               added as should-boost clauses (never filter results)

        Returns:
            List of (doc_id, score) tuples
        """
        with BM25_SEARCH_DURATION.time():
            try:
                client = await self._get_opensearch_client()

                # Truncate query if too long to avoid clause explosion
                # OpenSearch has maxClauseCount=1024, long queries create too many terms
                # 350 chars provides good balance: covers most Vietnamese legal clauses
                # while staying well under clause limit (~420 clauses vs 1024 limit)
                MAX_QUERY_LENGTH = 350  # characters
                if len(query) > MAX_QUERY_LENGTH:
                    logger.warning(f"BM25: Query too long ({len(query)} chars), truncating to {MAX_QUERY_LENGTH}")
                    query = query[:MAX_QUERY_LENGTH].rsplit(' ', 1)[0]  # Truncate at word boundary

                # Base multi-match: title^1.5 for Vietnamese legal docs
                # Vietnamese legal titles are verbose/administrative ("Về việc ban hành...")
                # so heavy title boost (title^4) drowns out semantic content matches.
                # title^1.5 gives title a moderate advantage without dominating content.
                # tie_breaker=0.3 gives partial credit for secondary field matches
                must_clause = {
                    "multi_match": {
                        "query": query,
                        "fields": ["title^1.5", "content^1"],
                        "type": "best_fields",
                        "tie_breaker": 0.3,
                    }
                }

                # Should clauses for phrase boosting (minimum_should_match=0 → never filters)
                should_clauses: list[dict] = [
                    # Exact phrase in title: moderate boost
                    {
                        "match_phrase": {
                            "title": {
                                "query": query,
                                "boost": 2.0,
                                "slop": 1,
                            }
                        }
                    },
                    # Phrase in content with slop for Vietnamese word-order flexibility
                    {
                        "match_phrase": {
                            "content": {
                                "query": query,
                                "boost": 1.5,
                                "slop": 2,
                            }
                        }
                    },
                ]

                # Expansion variant queries as soft-boost should clauses
                # Boosts documents matching synonym/abbreviation expansions without
                # ever filtering results that only match the base query
                # Cap variants to stay well under OpenSearch maxClauseCount=1024
                # Use BM25-specific cap of 2 to avoid clause explosion with multi_match fields
                if expansion_queries:
                    # BM25 expansion cap: 2 variants max (reduced from 3) to stay safely under clause limits
                    # Each multi_match creates nested clauses per field, so we limit aggressively
                    BM25_EXPANSION_CAP = 2
                    max_variants = min(BM25_EXPANSION_CAP, self.settings.search_expansion_max_variants)
                    boost = self.settings.search_expansion_boost
                    for variant in expansion_queries[:max_variants]:
                        should_clauses.append({
                            "multi_match": {
                                "query": variant,
                                "fields": ["title^2", "content^0.5"],
                                "type": "best_fields",
                                "boost": boost,
                            }
                        })
                    logger.debug(
                        f"BM25: added {min(len(expansion_queries), max_variants)} expansion variant clauses"
                    )

                # Build final query body
                query_body = {
                    "query": {
                        "bool": {
                            "must": [must_clause],
                            "should": should_clauses,
                            "minimum_should_match": 0,  # Should clauses only boost
                        }
                    },
                    "size": size,
                    "_source": False,  # Only need IDs and scores
                }

                # Add filters if provided
                if filters:
                    filter_clauses = self._build_opensearch_filters(filters)
                    if filter_clauses:
                        query_body["query"]["bool"]["filter"] = filter_clauses

                response = await client.search(
                    index=self.settings.opensearch_index,
                    body=query_body,
                )

                results = []
                for hit in response.get("hits", {}).get("hits", []):
                    doc_id = hit.get("_id")
                    score = hit.get("_score", 0.0)
                    if doc_id:
                        results.append((doc_id, score))

                return results

            except Exception as e:
                logger.error(f"BM25 search error: {e}")
                return []

    def _aggregate_chunks(
        self,
        results: list[tuple[str, float]],
        chunk_results: dict[str, list[tuple[str, float]]],
    ) -> list[tuple[str, float]]:
        """Aggregate chunk-level results to document level using max-score pooling.

        After retrieving dense results from Qdrant, check if results contain
        chunk_type="chunk" entries. Group chunk results by parent_doc_id and
        for each parent group, take the max score among all chunks (max-pool
        aggregation — the best-matching chunk represents the document's relevance).

        Args:
            results: List of (doc_id, score) tuples from Qdrant
            chunk_results: Dict mapping chunk IDs to their parent_doc_id and score

        Returns:
            List of (doc_id, score) tuples with chunks aggregated to parent docs
        """
        from collections import defaultdict

        # Group results by whether they are chunks or full documents
        parent_scores: dict[str, float] = {}  # parent_doc_id -> max score
        non_chunk_results: list[tuple[str, float]] = []

        for doc_id, score in results:
            if doc_id in chunk_results:
                # This is a chunk result
                parent_doc_id = chunk_results[doc_id]
                # Max-pool: keep the highest score for each parent
                if parent_doc_id not in parent_scores or score > parent_scores[parent_doc_id]:
                    parent_scores[parent_doc_id] = score
            else:
                # This is a full document result (not a chunk)
                non_chunk_results.append((doc_id, score))

        # Combine: non-chunk results + aggregated parent results
        aggregated = non_chunk_results.copy()
        for parent_doc_id, score in parent_scores.items():
            aggregated.append((parent_doc_id, score))

        # Sort by score descending
        aggregated.sort(key=lambda x: x[1], reverse=True)

        logger.debug(
            f"Chunk aggregation: {len(results)} raw results -> "
            f"{len(non_chunk_results)} non-chunk + {len(parent_scores)} aggregated parents = "
            f"{len(aggregated)} final results"
        )

        return aggregated

    async def _dense_search(
        self,
        query: str,
        limit: int = 100,
        filters: dict | None = None,
    ) -> list[tuple[str, float]]:
        """Dense vector search via Qdrant.

        Args:
            query: Search query
            limit: Number of results to retrieve
            filters: Optional metadata filters

        Returns:
            List of (doc_id, score) tuples
        """
        with DENSE_SEARCH_DURATION.time():
            try:
                client = await self._get_qdrant_client()

                # Embed query
                query_vector = await self._embed_query(query)

                # Build filter
                qdrant_filter = None
                if filters:
                    qdrant_filter = self._build_qdrant_filters(filters)

                # Search with payload to identify chunks
                response = await client.search(
                    collection_name=self.settings.qdrant_collection,
                    query_vector=query_vector,
                    limit=limit,
                    query_filter=qdrant_filter,
                    with_payload=True,  # Need payload to identify chunks
                )

                results = []
                chunk_results: dict[str, str] = {}  # chunk_id -> parent_doc_id

                for point in response:
                    doc_id = str(point.id)
                    score = point.score
                    payload = point.payload or {}

                    # Check if this is a chunk
                    chunk_type = payload.get("chunk_type")
                    if chunk_type == "chunk":
                        parent_doc_id = str(payload.get("parent_doc_id", doc_id))
                        chunk_results[doc_id] = parent_doc_id

                    results.append((doc_id, score))

                # Aggregate chunk results to document level
                if chunk_results:
                    results = self._aggregate_chunks(results, chunk_results)

                return results

            except Exception as e:
                logger.error(f"Dense search error: {e}")
                return []

    async def _embed_query(self, query: str) -> list[float]:
        """Embed query text using the Vietnamese legal embedding model.

        Args:
            query: Query text

        Returns:
            Query embedding vector
        """
        # Run sync embedding in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._embedding_service.encode_query, query
        )

    def _extract_root_doc_id(self, doc_id: str) -> str:
        """Extract root document ID from chunk/article reference.
        
        Handles multiple ID formats:
        - Simple IDs: '4258' -> '4258'
        - Chunk suffixes: '4258_chunk_0' -> '4258'
        - Article suffixes: '4258_article_1' -> '4258'
        - Combined: '4258_article_1_chunk_0' -> '4258'
        - Encoded article IDs: '42580001' -> '4258' (doc_id * 10000 + article_num)
        
        Examples:
            '4258' -> '4258'
            '4258_chunk_0' -> '4258'
            '4258_article_1' -> '4258'  
            '4258_article_1_chunk_0' -> '4258'
            '42580001' -> '4258' (article 1 of doc 4258)
            '770002' -> '77' (article 2 of doc 77)
        """
        doc_id_str = str(doc_id)
        
        # First, check if this is an encoded article ID (numeric and > 10000)
        # Qdrant uses format: doc_id * 10000 + article_number for articles
        try:
            doc_id_int = int(doc_id_str)
            if doc_id_int > 10000:
                # This is an encoded article ID
                # Extract parent doc ID by integer division
                parent_id = doc_id_int // 10000
                return str(parent_id)
        except (ValueError, TypeError):
            pass
        
        # Remove _chunk_N and _article_N suffixes for string-based IDs
        root = doc_id_str.split('_chunk_')[0].split('_article_')[0]
        return root

    async def _fetch_documents(
        self,
        doc_ids: list[str],
        scores: dict[str, float],
    ) -> list[RetrievedDocument]:
        """Fetch full document content for result IDs.
        
        For articles (chunk_type='article'), fetch from Qdrant payload.
        For root documents (chunk_type='document'), fetch from PostgreSQL.

        Args:
            doc_ids: List of document IDs to fetch
            scores: Dictionary mapping doc_id to fused score

        Returns:
            List of RetrievedDocument objects
        """
        if not doc_ids:
            return []

        # Build mapping from original doc_ids to root doc_ids
        # This handles chunk/article references like "4258_chunk_0", "4258_article_1"
        root_id_map: dict[str, list[str]] = {}  # root_id -> list of original doc_ids
        original_to_root: dict[str, str] = {}  # original_doc_id -> root_id
        
        for doc_id in doc_ids:
            doc_id_str = str(doc_id)
            root_id = self._extract_root_doc_id(doc_id_str)
            original_to_root[doc_id_str] = root_id
            if root_id not in root_id_map:
                root_id_map[root_id] = []
            root_id_map[root_id].append(doc_id_str)
        
        # Consolidate scores to root level (MAX score per root doc)
        root_scores: dict[str, float] = {}
        for original_id, score in scores.items():
            root_id = original_to_root.get(str(original_id), str(original_id))
            if root_id not in root_scores or score > root_scores[root_id]:
                root_scores[root_id] = score
        
        # Only fetch unique root IDs from PostgreSQL
        unique_root_ids = list(root_id_map.keys())

        # Separate article IDs (from Qdrant) and document IDs (from PostgreSQL)
        # Article IDs are integers > 10000 (doc_id * 10000 + article_number)
        article_ids = []
        document_ids = []
        
        for root_id in unique_root_ids:
            # Check if this is an article ID (numeric and > 10000)
            try:
                root_id_int = int(root_id)
                if root_id_int > 10000:
                    article_ids.append(root_id_int)
                else:
                    document_ids.append(root_id)
            except (ValueError, TypeError):
                # Not a numeric ID, treat as document ID
                document_ids.append(root_id)
        
        documents = []
        
        # Fetch articles from Qdrant
        if article_ids:
            try:
                qdrant = await self._get_qdrant_client()
                points = await qdrant.retrieve(
                    collection_name=self.settings.qdrant_collection,
                    ids=article_ids,
                    with_payload=True,
                    with_vectors=False,
                )
                
                for point in points:
                    doc_id = str(point.id)
                    payload = point.payload or {}
                    
                    # Use consolidated root score
                    consolidated_score = root_scores.get(doc_id, 0.0)
                    
                    documents.append(RetrievedDocument(
                        doc_id=doc_id,
                        content=payload.get('content', ''),
                        title=payload.get('title', ''),
                        score=consolidated_score,
                        metadata={
                            'doc_type': payload.get('doc_type', 'other'),
                            'law_id': payload.get('law_id'),
                            'chunk_type': payload.get('chunk_type', 'article'),
                            'article_number': payload.get('article_number'),
                            'parent_doc_id': payload.get('parent_doc_id'),
                        },
                    ))
                    
                logger.info(f"Fetched {len(points)} articles from Qdrant")
            except Exception as e:
                logger.error(f"Failed to fetch articles from Qdrant: {e}")
        
        # Fetch root documents from PostgreSQL
        if document_ids:
            try:
                pool = await self._get_postgres_pool()

                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT id, content, title, doc_type, law_id, metadata
                        FROM legal_documents
                        WHERE id = ANY($1)
                        """,
                        document_ids,
                    )

                    row_lookup = {row["id"]: row for row in rows}

                    for doc_id in document_ids:
                        row = row_lookup.get(doc_id)
                        if row:
                            metadata_value = row.get("metadata")
                            if isinstance(metadata_value, str):
                                try:
                                    import json
                                    parsed_metadata = json.loads(metadata_value)
                                except (json.JSONDecodeError, TypeError):
                                    parsed_metadata = {}
                            elif isinstance(metadata_value, dict):
                                parsed_metadata = metadata_value
                            else:
                                parsed_metadata = {}
                            
                            # Use consolidated root score
                            consolidated_score = root_scores.get(doc_id, 0.0)
                            
                            documents.append(RetrievedDocument(
                                doc_id=doc_id,
                                content=row["content"],
                                title=row["title"],
                                score=consolidated_score,
                                metadata={
                                    "doc_type": row.get("doc_type") or "other",
                                    "law_id": row.get("law_id"),
                                    "chunk_type": "document",
                                    **parsed_metadata,
                                },
                            ))
                            
                    logger.info(f"Fetched {len(rows)} documents from PostgreSQL")
            except Exception as e:
                logger.error(f"Error fetching documents from PostgreSQL: {e}")
        
        # Maintain order based on original doc_ids, mapping to root docs
        # Multiple chunk/article refs may map to same root doc - deduplicate
        doc_lookup = {doc.doc_id: doc for doc in documents}
        ordered_documents = []
        seen_root_ids = set()
        
        for doc_id in doc_ids:
            doc_id_str = str(doc_id)
            root_id = original_to_root.get(doc_id_str, doc_id_str)
            
            # Skip if we've already added this root doc
            if root_id in seen_root_ids:
                continue
            
            if root_id in doc_lookup:
                ordered_documents.append(doc_lookup[root_id])
                seen_root_ids.add(root_id)

        return ordered_documents

    def _build_opensearch_filters(self, filters: dict) -> list[dict]:
        """Convert metadata filters to OpenSearch query DSL.

        Args:
            filters: Dictionary of filter key-value pairs

        Returns:
            List of OpenSearch filter clauses
        """
        filter_clauses = []

        for key, value in filters.items():
            if isinstance(value, list):
                # Terms filter for list values
                filter_clauses.append({"terms": {key: value}})
            elif isinstance(value, dict):
                # Range filters (e.g., {"gte": "2020-01-01"})
                filter_clauses.append({"range": {key: value}})
            else:
                # Term filter for single value
                filter_clauses.append({"term": {key: value}})

        return filter_clauses

    def _build_qdrant_filters(self, filters: dict) -> Any:
        """Convert metadata filters to Qdrant filter conditions.

        Args:
            filters: Dictionary of filter key-value pairs

        Returns:
            Qdrant Filter object
        """
        from qdrant_client.models import (
            FieldCondition,
            Filter,
            MatchAny,
            MatchValue,
            Range,
        )

        conditions = []

        for key, value in filters.items():
            if isinstance(value, list):
                # Match any of the values
                conditions.append(
                    FieldCondition(key=key, match=MatchAny(any=value))
                )
            elif isinstance(value, dict):
                # Range filter
                range_params = {}
                if "gte" in value:
                    range_params["gte"] = value["gte"]
                if "gt" in value:
                    range_params["gt"] = value["gt"]
                if "lte" in value:
                    range_params["lte"] = value["lte"]
                if "lt" in value:
                    range_params["lt"] = value["lt"]
                conditions.append(
                    FieldCondition(key=key, range=Range(**range_params))
                )
            else:
                # Match single value
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )

        return Filter(must=conditions) if conditions else None

    async def close(self):
        """Close all client connections with proper cleanup."""
        errors = []
        
        # Close Qdrant client
        if self._qdrant_client:
            try:
                await self._qdrant_client.close()
                logger.info("Qdrant client closed")
            except Exception as e:
                logger.error(f"Error closing Qdrant client: {e}")
                errors.append(f"Qdrant: {e}")
            finally:
                self._qdrant_client = None

        # Close OpenSearch client (this closes the aiohttp session)
        if self._opensearch_client:
            try:
                await self._opensearch_client.close()
                logger.info("OpenSearch client closed")
            except Exception as e:
                logger.error(f"Error closing OpenSearch client: {e}")
                errors.append(f"OpenSearch: {e}")
            finally:
                self._opensearch_client = None

        # Close PostgreSQL pool
        if self._postgres_pool:
            try:
                await self._postgres_pool.close()
                logger.info("PostgreSQL pool closed")
            except Exception as e:
                logger.error(f"Error closing PostgreSQL pool: {e}")
                errors.append(f"PostgreSQL: {e}")
            finally:
                self._postgres_pool = None
        
        if errors:
            logger.warning(f"Errors during cleanup: {errors}")

    async def search_with_relationships(
        self,
        query: str,
        query_plan: QueryPlan | None = None,
        top_k: int = 5,
        seed_doc_ids: list[str] | None = None,
        relationship_types: list[str] | None = None,
        relationship_boost: float = 1.2,
        bm25_candidates: int | None = None,
        dense_candidates: int | None = None,
        rrf_k: int | None = None,
        filters: dict | None = None,
        sandwich_reorder: bool = True,
    ) -> list[RetrievedDocument]:
        """Execute hybrid search with relationship-aware boosting.

        If seed_doc_ids are provided, first fetches their related documents from PostgreSQL
        and uses them as a boosting signal in the hybrid search. This enables
        "find documents related to what I already found" queries.

        Args:
            query: Search query text
            query_plan: Optional query plan for search strategy
            top_k: Number of results to return
            seed_doc_ids: Optional list of document IDs to find related documents for
            relationship_types: Optional filter by relationship types (e.g., ["Văn bản căn cứ"])
            relationship_boost: Score multiplier for documents related to seed docs (default: 1.2)
            bm25_candidates: Number of BM25 candidates to retrieve (defaults to config)
            dense_candidates: Number of dense candidates to retrieve (defaults to config)
            rrf_k: RRF constant for fusion (defaults to config)
            filters: Optional metadata filters
            sandwich_reorder: Whether to apply sandwich reordering

        Returns:
            List of retrieved documents with fused scores, potentially boosted by relationships
        """
        # Use config defaults if not provided
        if bm25_candidates is None:
            bm25_candidates = self.settings.search_bm25_candidates
        if dense_candidates is None:
            dense_candidates = self.settings.search_dense_candidates
        if rrf_k is None:
            rrf_k = self.settings.search_rrf_k

        start_time = time.perf_counter()
        related_doc_ids: set[str] = set()

        # If seed documents provided, fetch their related documents from PostgreSQL
        if seed_doc_ids:
            try:
                related_doc_ids = await self._get_related_doc_ids_from_pg(
                    seed_doc_ids, relationship_types
                )
                logger.info(
                    f"Found {len(related_doc_ids)} related documents from {len(seed_doc_ids)} seed docs"
                )
            except Exception as e:
                logger.warning(f"Failed to fetch related documents: {e}")

        # Build filters with relationship awareness if specified
        search_filters = filters.copy() if filters else {}

        # If relationship_types specified, add filter for related_doc_ids field
        if relationship_types and not seed_doc_ids:
            # Filter to only documents that have these relationship types
            search_filters["relationship_types"] = relationship_types

        # Execute standard hybrid search
        documents = await self.search(
            query=query,
            query_plan=query_plan,
            top_k=top_k * 2,  # Fetch more for potential boosting
            bm25_candidates=bm25_candidates,
            dense_candidates=dense_candidates,
            rrf_k=rrf_k,
            filters=search_filters if search_filters else None,
            sandwich_reorder=False,  # We'll do our own reordering
        )

        # Apply relationship boosting if we have related documents
        if related_doc_ids:
            documents = self._apply_relationship_boosting(
                documents, related_doc_ids, relationship_boost
            )

        # Apply sandwich reordering if enabled
        if sandwich_reorder and len(documents) > 2:
            documents = self._apply_sandwich_reorder(documents)

        total_time = (time.perf_counter() - start_time) * 1000
        logger.info(f"Relationship-aware search completed in {total_time:.2f}ms")

        return documents[:top_k]

    async def _get_related_doc_ids_from_pg(
        self,
        seed_doc_ids: list[str],
        relationship_types: list[str] | None = None,
    ) -> set[str]:
        """Fetch related document IDs from PostgreSQL.

        Args:
            seed_doc_ids: List of seed document IDs
            relationship_types: Optional filter by relationship types

        Returns:
            Set of related document IDs
        """
        if not seed_doc_ids:
            return set()

        try:
            pool = await self._get_postgres_pool()
            related_ids: set[str] = set()

            async with pool.acquire() as conn:
                # Build relationship type filter if provided
                type_filter = ""
                params = [seed_doc_ids]
                if relationship_types:
                    type_filter = " AND relationship_type = ANY($2)"
                    params.append(relationship_types)

                # Query outgoing relationships
                outgoing_query = f"""
                    SELECT DISTINCT target_doc_id as related_id
                    FROM document_relationships
                    WHERE source_doc_id = ANY($1){type_filter}
                """
                rows = await conn.fetch(outgoing_query, *params)
                for row in rows:
                    related_ids.add(row["related_id"])

                # Query incoming relationships
                incoming_query = f"""
                    SELECT DISTINCT source_doc_id as related_id
                    FROM document_relationships
                    WHERE target_doc_id = ANY($1){type_filter}
                """
                rows = await conn.fetch(incoming_query, *params)
                for row in rows:
                    related_ids.add(row["related_id"])

            return related_ids

        except Exception as e:
            logger.error(f"Error fetching related document IDs: {e}")
            return set()

    def _apply_relationship_boosting(
        self,
        documents: list[RetrievedDocument],
        related_doc_ids: set[str],
        boost_factor: float = 1.2,
    ) -> list[RetrievedDocument]:
        """Boost scores of documents that are related to seed documents.

        Args:
            documents: List of retrieved documents
            related_doc_ids: Set of document IDs to boost
            boost_factor: Multiplier for related document scores

        Returns:
            Re-sorted list with boosted scores
        """
        for doc in documents:
            if doc.doc_id in related_doc_ids:
                original_score = doc.score
                doc.score *= boost_factor
                # Mark in metadata that this was boosted
                doc.metadata["relationship_boosted"] = True
                doc.metadata["original_score"] = original_score
                logger.debug(f"Boosted {doc.doc_id}: {original_score:.4f} -> {doc.score:.4f}")

        # Re-sort by boosted scores
        documents.sort(key=lambda d: d.score, reverse=True)

        return documents

    async def fetch_related_documents_for_results(
        self,
        documents: list[RetrievedDocument],
        relationship_types: list[str] | None = None,
        max_related_per_doc: int = 3,
    ) -> list[RetrievedDocument]:
        """Enrich retrieved documents with their related documents from PostgreSQL.

        This method populates the related_documents field of each RetrievedDocument.

        Args:
            documents: List of retrieved documents to enrich
            relationship_types: Optional filter by relationship types
            max_related_per_doc: Maximum number of related documents per result

        Returns:
            The same documents with related_documents populated
        """
        try:
            pool = await self._get_postgres_pool()

            async with pool.acquire() as conn:
                for doc in documents:
                    try:
                        # Build relationship type filter if provided
                        type_filter = ""
                        params = [doc.doc_id, max_related_per_doc]
                        if relationship_types:
                            type_filter = " AND dr.relationship_type = ANY($3)"
                            params.append(relationship_types)

                        # Query related documents with limit
                        query = f"""
                            SELECT 
                                dr.target_doc_id as related_doc_id,
                                dr.relationship_type,
                                ld.title,
                                LEFT(ld.content, 300) as content_preview,
                                'outgoing' as direction
                            FROM document_relationships dr
                            LEFT JOIN legal_documents ld ON dr.target_doc_id = ld.id
                            WHERE dr.source_doc_id = $1{type_filter}
                            LIMIT $2
                        """

                        rows = await conn.fetch(query, *params)
                        related = []
                        for row in rows:
                            related.append({
                                "doc_id": row["related_doc_id"],
                                "title": row["title"] or "",
                                "content": row["content_preview"] or "",
                                "relationship_type": row["relationship_type"],
                                "direction": row["direction"],
                            })

                        doc.related_documents = related

                    except Exception as e:
                        logger.warning(f"Failed to fetch related docs for {doc.doc_id}: {e}")
                        doc.related_documents = []

            return documents

        except Exception as e:
            logger.error(f"Error enriching documents with relationships: {e}")
            return documents


# Backward compatibility alias
HybridRetriever = HybridSearchEngine
