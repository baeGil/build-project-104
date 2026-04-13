"""Reciprocal Rank Fusion (RRF) for combining BM25 and dense retrieval results."""

from collections import defaultdict


def reciprocal_rank_fusion(
    result_lists: list[list[tuple[str, float]]],
    k: int = 60,
    top_n: int = 20,
) -> list[tuple[str, float]]:
    """Fuse multiple ranked result lists using RRF.

    Formula: score(d) = sum( 1/(k + rank_i(d)) ) for each result list i

    Args:
        result_lists: List of ranked results, each is list of (doc_id, score)
        k: RRF constant (default 60, higher = more uniform, lower = emphasizes top ranks)
        top_n: Number of results to return

    Returns:
        List of (doc_id, fused_score) sorted descending by score
    """
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
    k: int = 60,
    top_n: int = 20,
) -> list[tuple[str, float]]:
    """Weighted Reciprocal Rank Fusion for combining ranked lists.

    Formula: score(d) = sum( weight_i * 1/(k + rank_i(d)) ) for each result list i

    Args:
        result_lists: List of ranked results, each is list of (doc_id, score)
        weights: Weight multiplier for each result list (must match len(result_lists))
        k: RRF constant (default 60)
        top_n: Number of results to return

    Returns:
        List of (doc_id, fused_score) sorted descending by score

    Raises:
        ValueError: If weights length doesn't match result_lists length
    """
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

    def __init__(self, k: int = 60) -> None:
        """Initialize RRF with damping factor.

        Args:
            k: RRF damping constant (default: 60)
        """
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
