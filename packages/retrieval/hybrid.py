"""Hybrid search combining BM25 lexical and dense semantic retrieval."""

import asyncio
import logging
from typing import Any

from prometheus_client import Histogram

from packages.common.config import Settings
from packages.common.types import DocumentRelationship, QueryPlan, RelationshipType, RetrievedDocument
from packages.common.score_normalizer import RRFNormalizer
from packages.retrieval.embedding import EmbeddingService
from packages.retrieval.rrf import reciprocal_rank_fusion

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
                    use_ssl=False,
                    verify_certs=False,
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
        bm25_candidates: int = 100,
        dense_candidates: int = 100,
        rrf_k: int = 60,
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
            bm25_candidates: Number of BM25 candidates to retrieve
            dense_candidates: Number of dense candidates to retrieve
            rrf_k: RRF constant for fusion
            filters: Optional metadata filters
            sandwich_reorder: Whether to apply sandwich reordering (default: True)

        Returns:
            List of retrieved documents with fused scores
        """
        with HYBRID_SEARCH_DURATION.time():
            try:
                # Run BM25 and dense search in parallel
                bm25_task = self._bm25_search(
                    query, size=bm25_candidates, filters=filters
                )
                dense_task = self._dense_search(
                    query, limit=dense_candidates, filters=filters
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

                # RRF fusion
                with RRF_FUSION_DURATION.time():
                    fused_results = reciprocal_rank_fusion(
                        result_lists=[bm25_results, dense_results],
                        k=rrf_k,
                        top_n=top_k * 2,  # Fetch more for reranking
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

                # Add individual scores to documents
                for doc in documents:
                    doc.bm25_score = bm25_scores.get(doc.doc_id)
                    doc.dense_score = dense_scores.get(doc.doc_id)

                # Apply sandwich reordering if enabled
                if sandwich_reorder and len(documents) > 2:
                    documents = self._apply_sandwich_reorder(documents)

                return documents[:top_k]

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

    async def _bm25_search(
        self,
        query: str,
        size: int = 100,
        filters: dict | None = None,
    ) -> list[tuple[str, float]]:
        """BM25 search via OpenSearch.

        Args:
            query: Search query
            size: Number of results to retrieve
            filters: Optional metadata filters

        Returns:
            List of (doc_id, score) tuples
        """
        with BM25_SEARCH_DURATION.time():
            try:
                client = await self._get_opensearch_client()

                # Build query
                query_body = {
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "multi_match": {
                                        "query": query,
                                        "fields": ["content^2", "title"],
                                        "type": "best_fields",
                                    }
                                }
                            ]
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

                # Search
                response = await client.search(
                    collection_name=self.settings.qdrant_collection,
                    query_vector=query_vector,
                    limit=limit,
                    query_filter=qdrant_filter,
                    with_payload=False,  # Only need IDs and scores
                )

                results = []
                for point in response:
                    doc_id = point.id
                    score = point.score
                    results.append((str(doc_id), score))

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

    async def _fetch_documents(
        self,
        doc_ids: list[str],
        scores: dict[str, float],
    ) -> list[RetrievedDocument]:
        """Fetch full document content for result IDs.

        Args:
            doc_ids: List of document IDs to fetch
            scores: Dictionary mapping doc_id to fused score

        Returns:
            List of RetrievedDocument objects
        """
        if not doc_ids:
            return []

        try:
            pool = await self._get_postgres_pool()

            async with pool.acquire() as conn:
                # Fetch documents from PostgreSQL
                rows = await conn.fetch(
                    """
                    SELECT id, content, title, doc_type, metadata
                    FROM legal_documents
                    WHERE id = ANY($1)
                    """,
                    doc_ids,
                )

                # Create lookup by ID
                row_lookup = {row["id"]: row for row in rows}

                # Build results in the same order as doc_ids
                documents = []
                for doc_id in doc_ids:
                    row = row_lookup.get(doc_id)
                    if row:
                        # Parse metadata - can be dict, JSON string, or None
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
                        
                        doc = RetrievedDocument(
                            doc_id=doc_id,
                            content=row["content"],
                            title=row["title"],
                            score=scores.get(doc_id, 0.0),
                            metadata={
                                "doc_type": row.get("doc_type", "unknown"),
                                **parsed_metadata,
                            },
                        )
                        documents.append(doc)

                return documents

        except Exception as e:
            logger.error(f"Error fetching documents: {e}")
            return []

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
        """Close all client connections."""
        if self._qdrant_client:
            await self._qdrant_client.close()
            self._qdrant_client = None

        if self._opensearch_client:
            await self._opensearch_client.close()
            self._opensearch_client = None

        if self._postgres_pool:
            await self._postgres_pool.close()
            self._postgres_pool = None

    async def search_with_relationships(
        self,
        query: str,
        query_plan: QueryPlan | None = None,
        top_k: int = 5,
        seed_doc_ids: list[str] | None = None,
        relationship_types: list[str] | None = None,
        relationship_boost: float = 1.2,
        bm25_candidates: int = 100,
        dense_candidates: int = 100,
        rrf_k: int = 60,
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
            bm25_candidates: Number of BM25 candidates to retrieve
            dense_candidates: Number of dense candidates to retrieve
            rrf_k: RRF constant for fusion
            filters: Optional metadata filters
            sandwich_reorder: Whether to apply sandwich reordering

        Returns:
            List of retrieved documents with fused scores, potentially boosted by relationships
        """
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
