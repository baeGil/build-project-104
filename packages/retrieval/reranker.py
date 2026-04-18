"""Two-stage reranker with ColBERTv2 and latency budget enforcement.

This module implements a two-stage reranking pipeline:
- Stage 1: Fast position-decay scoring (5ms) - eliminates obvious non-matches
- Stage 2: ColBERTv2 late-interaction on top candidates (50-100ms)

Includes latency budget enforcement: skips Stage 2 if budget is exceeded.
Target: <100ms total for reranking top-20 candidates.
"""

from __future__ import annotations

import os
import logging
import time
from typing import Any, TYPE_CHECKING

from prometheus_client import Histogram

from packages.common.config import get_settings
from packages.common.types import RetrievedDocument

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

# Prevent transformers from probing TensorFlow at import time.
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")
os.environ.setdefault("USE_TF", "0")

# Module-level model cache for singleton pattern
_colbert_model_cache: Any = None
_cross_encoder_cache: Any = None
_model_type_cache: str | None = None

RERANK_DURATION = Histogram(
    "reranker_duration_seconds",
    "Reranking latency",
    labelnames=["stage"],
)


class LegalReranker:
    """Two-stage reranking pipeline with latency budget enforcement.

    Stage 1: Fast position-decay scoring (5ms) - eliminates obvious non-matches
    Stage 2: ColBERTv2 late-interaction on top candidates (50-100ms)

    Includes latency budget enforcement: skips Stage 2 if budget is exceeded.
    Target: <100ms total for reranking top-20 candidates.
    """

    def __init__(self, budget_ms: float | None = None) -> None:
        """Initialize the LegalReranker.

        Args:
            budget_ms: Maximum time allowed for reranking in milliseconds (defaults to config).
        """
        self._colbert_model = None  # Lazy load
        self._cross_encoder = None  # Fallback model
        self.budget_ms = budget_ms if budget_ms is not None else get_settings().search_reranker_budget_ms
        self._model_type: str | None = None

    def _load_colbert(self) -> bool:
        """Lazy-load ColBERTv2 model with singleton caching.

        Uses fastembed.LateInteractionTextEmbedding if available,
        otherwise falls back to sentence-transformers cross-encoder.
        Models are cached at module level to avoid re-creation per request.

        Models tried in order:
        1. fastembed with colbert-ir/colbertv2.0
        2. sentence-transformers cross-encoder/ms-marco-MiniLM-L-6-v2

        Returns:
            True if a model was successfully loaded, False otherwise.
        """
        global _colbert_model_cache, _cross_encoder_cache, _model_type_cache

        # Check instance-level cache first
        if self._colbert_model is not None or self._cross_encoder is not None:
            return True

        # Check module-level cache
        if _colbert_model_cache is not None or _cross_encoder_cache is not None:
            self._colbert_model = _colbert_model_cache
            self._cross_encoder = _cross_encoder_cache
            self._model_type = _model_type_cache
            logger.debug("Using cached model from module-level cache")
            return True

        # Try fastembed with ColBERT first
        try:
            from fastembed import LateInteractionTextEmbedding

            _colbert_model_cache = LateInteractionTextEmbedding(
                "colbert-ir/colbertv2.0"
            )
            self._colbert_model = _colbert_model_cache
            self._model_type = "colbert"
            _model_type_cache = "colbert"
            logger.info("Loaded ColBERTv2 model via fastembed")
            return True
        except ImportError:
            logger.debug("fastembed not installed, trying cross-encoder fallback")
        except Exception as e:
            logger.warning(f"Failed to load ColBERTv2 model: {e}")

        # Fall back to sentence-transformers cross-encoder
        try:
            from sentence_transformers import CrossEncoder

            _cross_encoder_cache = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            self._cross_encoder = _cross_encoder_cache
            self._model_type = "cross_encoder"
            _model_type_cache = "cross_encoder"
            logger.info("Loaded cross-encoder model (ms-marco-MiniLM-L-6-v2)")
            return True
        except Exception as e:
            logger.error(f"Failed to load cross-encoder model: {e}")
            return False

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievedDocument],
        top_k: int = 5,
    ) -> list[RetrievedDocument]:
        """Execute two-stage reranking with latency budget.

        Stage 1: Position-decay scoring on all candidates
        Stage 2: ColBERT/cross-encoder on top-N (if budget permits)

        Args:
            query: Original search query.
            candidates: List of retrieved documents to rerank.
            top_k: Number of top documents to return.

        Returns:
            Top_k reranked documents with updated rerank_score.
        """
        if not candidates:
            return []

        start_time = time.perf_counter()

        # Stage 1: Position-decay scoring
        with RERANK_DURATION.labels(stage="stage1_position_decay").time():
            stage1_candidates = self._stage1_position_decay(candidates)

        stage1_elapsed_ms = (time.perf_counter() - start_time) * 1000
        remaining_budget = self.budget_ms - stage1_elapsed_ms

        logger.debug(
            f"Stage 1 completed in {stage1_elapsed_ms:.2f}ms, "
            f"remaining budget: {remaining_budget:.2f}ms"
        )

        # Check if we have budget for Stage 2
        if remaining_budget <= 0:
            logger.warning(
                f"Latency budget exceeded after Stage 1 ({stage1_elapsed_ms:.2f}ms > "
                f"{self.budget_ms:.2f}ms), skipping Stage 2"
            )
            # Return top_k from Stage 1 results
            for doc in stage1_candidates:
                doc.rerank_score = doc.score
            return stage1_candidates[:top_k]

        # Stage 2: Model-based reranking (if budget permits)
        try:
            with RERANK_DURATION.labels(stage="stage2_model_rerank").time():
                final_results = await self._stage2_model_rerank(
                    query, stage1_candidates, top_k
                )

            total_elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(f"Total reranking completed in {total_elapsed_ms:.2f}ms")

            return final_results

        except Exception as e:
            logger.error(f"Stage 2 reranking failed: {e}, returning Stage 1 results")
            for doc in stage1_candidates:
                doc.rerank_score = doc.score
            return stage1_candidates[:top_k]

    def _stage1_position_decay(
        self,
        candidates: list[RetrievedDocument],
    ) -> list[RetrievedDocument]:
        """Apply fast position-decay scoring (< 5ms).

        Score = alpha * original_score + (1 - alpha) * (1 - position/total)
        where alpha = 0.5 (balanced weight between original score and position)

        Eliminates bottom half of candidates.

        Args:
            candidates: List of retrieved documents.

        Returns:
            Top half of candidates after position-decay scoring.
        """
        total = len(candidates)
        alpha = 0.5  # Hardcoded: balanced weight for fairer "second opinion"

        scored_candidates = []
        for position, doc in enumerate(candidates):
            decay_score = self._compute_position_decay_score(
                original_score=doc.score,
                position=position,
                total=total,
                alpha=alpha,
            )
            doc.rerank_score = decay_score
            scored_candidates.append((decay_score, doc))

        # Sort by decay score descending
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        # Keep top half for Stage 2
        keep_count = max(1, total // 2)
        return [doc for _, doc in scored_candidates[:keep_count]]

    async def _stage2_model_rerank(
        self,
        query: str,
        candidates: list[RetrievedDocument],
        top_k: int = 5,
    ) -> list[RetrievedDocument]:
        """Apply model-based reranking using ColBERTv2 or cross-encoder.

        For ColBERT: encode query + docs separately, compute max-sim scores
        For cross-encoder: encode (query, doc) pairs, get relevance scores

        Args:
            query: Original search query.
            candidates: List of candidates from Stage 1.
            top_k: Number of top documents to return.

        Returns:
            Top_k reranked documents with updated rerank_score.
        """
        # Try to load model if not already loaded
        if not self._load_colbert():
            logger.warning("No model available for Stage 2, using Stage 1 scores")
            # Sort by Stage 1 scores and return
            candidates.sort(key=lambda x: x.rerank_score or 0, reverse=True)
            for doc in candidates:
                if doc.rerank_score is None:
                    doc.rerank_score = doc.score
            return candidates[:top_k]

        if self._model_type == "colbert":
            return await self._rerank_with_colbert(query, candidates, top_k)
        else:
            return await self._rerank_with_cross_encoder(query, candidates, top_k)

    async def _rerank_with_colbert(
        self,
        query: str,
        candidates: list[RetrievedDocument],
        top_k: int = 5,
    ) -> list[RetrievedDocument]:
        """Rerank using ColBERT late interaction.

        Args:
            query: Original search query.
            candidates: List of candidates to rerank.
            top_k: Number of top documents to return.

        Returns:
            Top_k reranked documents.
        """
        import asyncio

        loop = asyncio.get_event_loop()

        # Encode query and documents in parallel
        query_embedding = await loop.run_in_executor(
            None, lambda: list(self._colbert_model.embed([query]))[0]
        )

        doc_texts = [doc.content for doc in candidates]
        doc_embeddings = await loop.run_in_executor(
            None, lambda: list(self._colbert_model.embed(doc_texts))
        )

        # Compute max-sim scores
        scored_docs = []
        for doc, doc_emb in zip(candidates, doc_embeddings):
            score = self._compute_max_similarity(query_embedding, doc_emb)
            doc.rerank_score = float(score)
            scored_docs.append((score, doc))

        # Sort by score descending
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored_docs[:top_k]]

    async def _rerank_with_cross_encoder(
        self,
        query: str,
        candidates: list[RetrievedDocument],
        top_k: int = 5,
    ) -> list[RetrievedDocument]:
        """Rerank using cross-encoder.

        Args:
            query: Original search query.
            candidates: List of candidates to rerank.
            top_k: Number of top documents to return.

        Returns:
            Top_k reranked documents.
        """
        import asyncio

        loop = asyncio.get_event_loop()

        # Prepare query-document pairs
        pairs = [(query, doc.content) for doc in candidates]

        # Get predictions from cross-encoder
        scores = await loop.run_in_executor(
            None, lambda: self._cross_encoder.predict(pairs)
        )

        # Update scores and sort
        scored_docs = []
        for doc, score in zip(candidates, scores):
            doc.rerank_score = float(score)
            scored_docs.append((score, doc))

        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored_docs[:top_k]]

    @staticmethod
    def _compute_max_similarity(query_emb, doc_emb) -> float:
        """Compute max-sim score between query and document embeddings.

        This is the standard ColBERT late interaction scoring:
        For each query token, find max similarity to any document token,
        then sum these max similarities.

        Args:
            query_emb: Query token embeddings (num_query_tokens, dim)
            doc_emb: Document token embeddings (num_doc_tokens, dim)

        Returns:
            Max-sim similarity score.
        """
        import numpy as np

        # Compute cosine similarity matrix
        query_norm = query_emb / (np.linalg.norm(query_emb, axis=1, keepdims=True) + 1e-8)
        doc_norm = doc_emb / (np.linalg.norm(doc_emb, axis=1, keepdims=True) + 1e-8)

        # Similarity matrix: (num_query_tokens, num_doc_tokens)
        similarity_matrix = np.dot(query_norm, doc_norm.T)

        # Max-sim: for each query token, take max similarity to any doc token
        max_sims = np.max(similarity_matrix, axis=1)

        # Sum of max similarities
        return float(np.sum(max_sims))

    @staticmethod
    def _compute_position_decay_score(
        original_score: float,
        position: int,
        total: int,
        alpha: float = 0.7,
    ) -> float:
        """Compute position-decay score.

        Formula: alpha * original_score + (1 - alpha) * (1 - position/total)

        Args:
            original_score: Original retrieval score.
            position: Position in the original ranking (0-indexed).
            total: Total number of candidates.
            alpha: Weight towards original score (0-1).

        Returns:
            Position-decay score.
        """
        if total <= 1:
            position_factor = 1.0
        else:
            position_factor = 1.0 - (position / (total - 1)) if total > 1 else 1.0

        return alpha * original_score + (1 - alpha) * position_factor


class SimpleReranker:
    """Lightweight fallback reranker using only position decay.

    Used when ColBERTv2 model is not available or budget is too tight.
    """

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievedDocument],
        top_k: int = 5,
    ) -> list[RetrievedDocument]:
        """Apply simple position-decay reranking only.

        Args:
            query: Original search query (unused in simple reranker).
            candidates: List of retrieved documents to rerank.
            top_k: Number of top documents to return.

        Returns:
            Top_k reranked documents with updated rerank_score.
        """
        if not candidates:
            return []

        with RERANK_DURATION.labels(stage="simple_rerank").time():
            total = len(candidates)
            alpha = 0.5  # Hardcoded: balanced weight for fairer "second opinion"

            scored_candidates = []
            for position, doc in enumerate(candidates):
                decay_score = LegalReranker._compute_position_decay_score(
                    original_score=doc.score,
                    position=position,
                    total=total,
                    alpha=alpha,
                )
                doc.rerank_score = decay_score
                scored_candidates.append((decay_score, doc))

            # Sort by decay score descending
            scored_candidates.sort(key=lambda x: x[0], reverse=True)

            return [doc for _, doc in scored_candidates[:top_k]]


def create_reranker(
    use_model: bool = True, budget_ms: float | None = None
) -> LegalReranker | SimpleReranker:
    """Create appropriate reranker based on configuration.

    Args:
        use_model: Whether to use model-based reranking (ColBERT/cross-encoder).
            If False, returns SimpleReranker.
        budget_ms: Maximum time allowed for reranking in milliseconds (defaults to config).

    Returns:
        LegalReranker if use_model is True and models are available,
        otherwise SimpleReranker.
    """
    if budget_ms is None:
        budget_ms = get_settings().search_reranker_budget_ms

    if not use_model:
        logger.info("Creating SimpleReranker (model-based reranking disabled)")
        return SimpleReranker()

    # Try to create LegalReranker and load a model
    reranker = LegalReranker(budget_ms=budget_ms)

    if reranker._load_colbert():
        logger.info(f"Created LegalReranker with model type: {reranker._model_type}")
        return reranker
    else:
        logger.warning(
            "No model available for LegalReranker, falling back to SimpleReranker"
        )
        return SimpleReranker()


# Backward compatibility alias
Reranker = LegalReranker
