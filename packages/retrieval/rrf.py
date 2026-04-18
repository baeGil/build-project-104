"""Reciprocal Rank Fusion (RRF) for combining BM25 and dense retrieval results."""

import logging
from collections import defaultdict
from typing import TYPE_CHECKING

from packages.common.config import get_settings

if TYPE_CHECKING:
    from packages.common.types import QueryPlan

logger = logging.getLogger(__name__)


def adaptive_rrf_params(query_plan: "QueryPlan | None") -> tuple[int, list[float]]:
    """Compute adaptive RRF parameters based on query characteristics.

    Based on IR literature principles:
    - Short specific queries benefit from dense (semantic) retrieval
    - Long/broad queries benefit from BM25 (exact term matching)
    - Negation queries need BM25 for keyword-level negation detection

    Args:
        query_plan: Structured query plan with strategy and normalized_query fields

    Returns:
        Tuple of (k, weights) where:
        - k: RRF damping constant
        - weights: List of two weights [bm25_weight, dense_weight]
    """
    settings = get_settings()

    # Default: use config values with slight BM25 boost for Vietnamese legal text
    if query_plan is None:
        return settings.search_rrf_k, [1.2, 1.0]

    # Get query text for length calculation
    query_text = query_plan.normalized_query or query_plan.original_query or ""
    query_length = len(query_text.split())  # Whitespace-separated token count

    # Get strategy (handle both enum and string)
    strategy = query_plan.strategy
    strategy_name = strategy.value if hasattr(strategy, 'value') else str(strategy)

    # Rule 1: Short specific queries (CITATION) - favor dense for semantic matching
    if query_length < 15 and strategy_name == "citation":
        k = 30
        weights = [0.6, 1.0]  # Favor dense
        logger.debug(
            f"Adaptive RRF: short citation query (len={query_length}), "
            f"k={k}, weights={weights}"
        )
        return k, weights

    # Rule 2: Long broad queries or SEMANTIC - favor BM25 for term matching
    if query_length > 50 or strategy_name == "semantic":
        k = 80
        weights = [1.2, 0.8]  # Favor BM25
        logger.debug(
            f"Adaptive RRF: long/semantic query (len={query_length}), "
            f"k={k}, weights={weights}"
        )
        return k, weights

    # Rule 3: NEGATION queries - BM25 handles negation keywords better
    if strategy_name == "negation":
        k = 40
        weights = [1.0, 0.6]  # Favor BM25
        logger.debug(
            f"Adaptive RRF: negation query (len={query_length}), "
            f"k={k}, weights={weights}"
        )
        return k, weights

    # Default: use config defaults with slight BM25 boost for Vietnamese legal text
    logger.debug(
        f"Adaptive RRF: default (len={query_length}, strategy={strategy_name}), "
        f"k={settings.search_rrf_k}, weights=[1.2, 1.0]"
    )
    return settings.search_rrf_k, [1.2, 1.0]


def reciprocal_rank_fusion(
    result_lists: list[list[tuple[str, float]]],
    k: int | None = None,
    top_n: int = 20,
) -> list[tuple[str, float]]:
    """Fuse multiple ranked result lists using RRF.

    Formula: score(d) = sum( 1/(k + rank_i(d)) ) for each result list i

    Args:
        result_lists: List of ranked results, each is list of (doc_id, score)
        k: RRF constant (default from config, higher = more uniform, lower = emphasizes top ranks)
        top_n: Number of results to return

    Returns:
        List of (doc_id, fused_score) sorted descending by score
    """
    # Use config default if not provided
    if k is None:
        k = get_settings().search_rrf_k

    # Track fused scores for each document
    fused_scores: dict[str, float] = defaultdict(float)

    # Process each result list
    for result_list in result_lists:
        for rank, (doc_id, _) in enumerate(result_list, start=1):
            # RRF formula: 1 / (k + rank)
            fused_scores[doc_id] += 1.0 / (k + rank)

    # Sort by fused score descending and take top_n
    sorted_results = sorted(
        fused_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )[:top_n]

    return sorted_results


def weighted_rrf(
    result_lists: list[list[tuple[str, float]]],
    weights: list[float],
    k: int | None = None,
    top_n: int = 20,
) -> list[tuple[str, float]]:
    """Weighted Reciprocal Rank Fusion for combining ranked lists.

    Formula: score(d) = sum( weight_i * 1/(k + rank_i(d)) ) for each result list i

    Args:
        result_lists: List of ranked results, each is list of (doc_id, score)
        weights: Weight multiplier for each result list (must match len(result_lists))
        k: RRF constant (default from config)
        top_n: Number of results to return

    Returns:
        List of (doc_id, fused_score) sorted descending by score

    Raises:
        ValueError: If weights length doesn't match result_lists length
    """
    # Use config default if not provided
    if k is None:
        k = get_settings().search_rrf_k

    if len(weights) != len(result_lists):
        raise ValueError(
            f"Number of weights ({len(weights)}) must match "
            f"number of result lists ({len(result_lists)})"
        )

    # Track weighted fused scores for each document
    fused_scores: dict[str, float] = defaultdict(float)

    # Process each result list with its weight
    for result_list, weight in zip(result_lists, weights):
        for rank, (doc_id, _) in enumerate(result_list, start=1):
            # Weighted RRF formula: weight * 1 / (k + rank)
            fused_scores[doc_id] += weight * (1.0 / (k + rank))

    # Sort by fused score descending and take top_n
    sorted_results = sorted(
        fused_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )[:top_n]

    return sorted_results


class ReciprocalRankFusion:
    """Reciprocal Rank Fusion implementation (class-based wrapper).

    RRF combines multiple ranked lists using the formula:
    score = sum(1 / (k + rank)) for each list

    where k is a constant (typically 60) that dampens the impact
    of low-ranked items.
    """

    def __init__(self, k: int | None = None) -> None:
        """Initialize RRF with damping factor.

        Args:
            k: RRF damping constant (default from config)
        """
        if k is None:
            k = get_settings().search_rrf_k
        self.k = k

    def fuse(
        self,
        ranked_lists: list[list[tuple[str, float]]],
        top_n: int = 20,
    ) -> list[tuple[str, float]]:
        """Fuse multiple ranked lists into one.

        Args:
            ranked_lists: List of ranked document lists, each is list of (doc_id, score)
            top_n: Number of results to return

        Returns:
            Fused and re-ranked list of (doc_id, fused_score)
        """
        return reciprocal_rank_fusion(ranked_lists, k=self.k, top_n=top_n)

    def fuse_weighted(
        self,
        ranked_lists: list[list[tuple[str, float]]],
        weights: list[float],
        top_n: int = 20,
    ) -> list[tuple[str, float]]:
        """Fuse multiple ranked lists with weights.

        Args:
            ranked_lists: List of ranked document lists, each is list of (doc_id, score)
            weights: Weight multiplier for each result list
            top_n: Number of results to return

        Returns:
            Fused and re-ranked list of (doc_id, fused_score)
        """
        return weighted_rrf(ranked_lists, weights, k=self.k, top_n=top_n)
