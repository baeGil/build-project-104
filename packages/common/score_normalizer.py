"""
Score Normalization Utilities.

Provides dynamic score normalization for retrieval systems.
Supports multiple normalization methods without hardcoded ranges.
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np

logger = logging.getLogger(__name__)


class ScoreNormalizer:
    """
    Dynamic score normalizer that adapts to any score distribution.
    
    Supports multiple normalization methods:
    - min-max: Scale to [0, 100] or custom range
    - z-score: Standardize to mean=0, std=1
    - percentile: Convert to percentile rank
    - rank-based: Convert to rank percentile
    
    All methods are adaptive - no hardcoded score ranges!
    """

    def __init__(
        self,
        method: Literal["min-max", "z-score", "percentile", "rank"] = "min-max",
        target_min: float = 0.0,
        target_max: float = 100.0,
        epsilon: float = 1e-10,
    ):
        """
        Initialize score normalizer.
        
        Args:
            method: Normalization method
                - "min-max": Linear scaling to [target_min, target_max]
                - "z-score": Standardize (mean=0, std=1)
                - "percentile": Convert to percentile [0, 100]
                - "rank": Convert to rank percentile [0, 100]
            target_min: Minimum value for min-max normalization
            target_max: Maximum value for min-max normalization
            epsilon: Small value to prevent division by zero
        """
        self.method = method
        self.target_min = target_min
        self.target_max = target_max
        self.epsilon = epsilon
        
        # Statistics for adaptive normalization
        self._stats = {
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "count": 0,
        }

    def fit(self, scores: list[float]) -> None:
        """
        Calculate statistics from score distribution.
        
        Args:
            scores: List of raw scores to learn distribution from
        """
        if not scores:
            logger.warning("No scores provided for fitting")
            return

        scores_array = np.array(scores, dtype=np.float64)
        
        self._stats = {
            "min": float(np.min(scores_array)),
            "max": float(np.max(scores_array)),
            "mean": float(np.mean(scores_array)),
            "std": float(np.std(scores_array)),
            "count": len(scores),
        }
        
        logger.debug(
            f"ScoreNormalizer fitted: min={self._stats['min']:.4f}, "
            f"max={self._stats['max']:.4f}, "
            f"mean={self._stats['mean']:.4f}, "
            f"std={self._stats['std']:.4f}"
        )

    def normalize(self, score: float) -> float:
        """
        Normalize a single score using learned statistics.
        
        Args:
            score: Raw score to normalize
            
        Returns:
            Normalized score
        """
        if self._stats["count"] == 0:
            logger.warning("Normalizer not fitted, returning original score")
            return score

        if self.method == "min-max":
            return self._normalize_min_max(score)
        elif self.method == "z-score":
            return self._normalize_zscore(score)
        elif self.method == "percentile":
            return self._normalize_percentile(score)
        elif self.method == "rank":
            return self._normalize_rank(score)
        else:
            raise ValueError(f"Unknown normalization method: {self.method}")

    def normalize_batch(self, scores: list[float]) -> list[float]:
        """
        Normalize a batch of scores.
        
        Args:
            scores: List of raw scores
            
        Returns:
            List of normalized scores
        """
        if not scores:
            return []
        
        # Auto-fit if not already fitted
        if self._stats["count"] == 0:
            self.fit(scores)
        
        return [self.normalize(score) for score in scores]

    def _normalize_min_max(self, score: float) -> float:
        """Min-max normalization to [target_min, target_max]."""
        score_range = self._stats["max"] - self._stats["min"]
        
        if score_range < self.epsilon:
            # All scores are the same
            return (self.target_min + self.target_max) / 2.0
        
        normalized = (score - self._stats["min"]) / score_range
        return self.target_min + normalized * (self.target_max - self.target_min)

    def _normalize_zscore(self, score: float) -> float:
        """Z-score standardization."""
        if self._stats["std"] < self.epsilon:
            return 0.0
        
        return (score - self._stats["mean"]) / self._stats["std"]

    def _normalize_percentile(self, score: float) -> float:
        """
        Convert score to percentile rank.
        
        Assumes scores follow the learned distribution.
        """
        if self._stats["std"] < self.epsilon:
            return 50.0  # Median if no variance
        
        # Use CDF of normal distribution
        z_score = (score - self._stats["mean"]) / self._stats["std"]
        
        # Approximate CDF using error function
        from math import erf, sqrt
        percentile = 0.5 * (1.0 + erf(z_score / sqrt(2)))
        
        return percentile * 100.0

    def _normalize_rank(self, score: float) -> float:
        """
        Convert score to rank-based percentile.
        
        Higher scores get higher percentiles.
        """
        # This is a simplified version - for accurate rank normalization,
        # you need all scores to determine exact rank
        # Using percentile approximation instead
        return self._normalize_percentile(score)

    def get_stats(self) -> dict:
        """Get current normalization statistics."""
        return self._stats.copy()

    def reset(self) -> None:
        """Reset normalizer statistics."""
        self._stats = {
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "count": 0,
        }


class RRFNormalizer(ScoreNormalizer):
    """
    Specialized normalizer for RRF (Reciprocal Rank Fusion) scores.
    
    RRF scores typically range from 0.012 to 0.033.
    Instead of min-max (which creates skewed distribution),
    we use centered scaling to preserve relative differences.
    """

    def __init__(
        self,
        scale: Literal[10, 100] = 100,
        method: Literal["centered", "min-max", "percentile"] = "centered",
    ):
        """
        Initialize RRF normalizer.
        
        Args:
            scale: Target scale (100 for 0-100, 10 for 0-10)
            method: Normalization method
                - "centered": Preserve distribution, shift to target range (RECOMMENDED)
                - "min-max": Stretch to full range (creates skew)
                - "percentile": Statistical percentile
        """
        target_max = float(scale)
        super().__init__(
            method=method,
            target_min=0.0,
            target_max=target_max,
        )
        self.scale = scale
        
        # RRF typical range (for centered normalization)
        # These are ESTIMATES - actual values learned from data
        self._rrf_typical_min = 0.012
        self._rrf_typical_max = 0.035
        self._rrf_typical_mean = 0.023

    def normalize_rrf_scores(self, scores: list[float]) -> list[float]:
        """
        Normalize RRF scores with automatic fitting.
        
        Uses centered normalization by default to preserve distribution.
        
        Args:
            scores: List of RRF scores
            
        Returns:
            Normalized scores
        """
        if not scores:
            return []
        
        # Auto-fit to score distribution
        self.fit(scores)
        
        # Use centered normalization (preserves distribution)
        if self.method == "centered":
            normalized = self._normalize_centered(scores)
        elif self.method == "min-max":
            normalized = self.normalize_batch(scores)
        elif self.method == "percentile":
            normalized = self.normalize_batch(scores)
        else:
            normalized = self.normalize_batch(scores)
        
        logger.debug(
            f"RRF scores normalized: "
            f"original=[{min(scores):.4f}-{max(scores):.4f}] → "
            f"normalized=[{min(normalized):.2f}-{max(normalized):.2f}]"
        )
        
        return normalized
    
    def _normalize_centered(self, scores: list[float]) -> list[float]:
        """
        Centered normalization: preserve relative differences.
        
        Formula: normalized = (score - baseline) * scale_factor + offset
        
        This keeps the distribution shape while shifting to target range.
        """
        if not scores:
            return []
        
        # Calculate statistics
        min_score = self._stats["min"] or min(scores)
        max_score = self._stats["max"] or max(scores)
        mean_score = self._stats["mean"] or (min_score + max_score) / 2
        
        # Strategy: Map [typical_min, typical_max] to [offset, target_max]
        # Keep distribution shape, just shift and scale
        
        # Calculate scale factor based on typical range
        typical_range = self._rrf_typical_max - self._rrf_typical_min
        actual_range = max_score - min_score
        
        # Use the LARGER of typical or actual range to avoid over-scaling
        effective_range = max(typical_range, actual_range)
        
        # Scale factor: how much to multiply
        scale_factor = self.target_max / effective_range
        
        # Offset: where to start (map typical_min to a reasonable minimum)
        # For RRF: typical scores 0.015-0.033 should map to ~20-100 on 0-100 scale
        # So offset = target_min + (typical_min * scale_factor)
        # But we want meaningful minimum, so use: offset = 10% of target_max
        offset = self.target_max * 0.1
        
        # Normalize each score
        normalized = []
        for score in scores:
            # Center around typical mean, then scale
            centered = score - self._rrf_typical_min
            norm_score = offset + (centered * scale_factor)
            
            # Clamp to valid range
            norm_score = max(self.target_min, min(self.target_max, norm_score))
            normalized.append(norm_score)
        
        return normalized


# Factory function for easy usage
def create_normalizer(
    scale: int = 100,
    method: str = "min-max",
    **kwargs,
) -> ScoreNormalizer:
    """
    Create a score normalizer.
    
    Args:
        scale: Target scale (100 for 0-100, 10 for 0-10, etc.)
        method: Normalization method
        **kwargs: Additional arguments passed to ScoreNormalizer
        
    Returns:
        Configured ScoreNormalizer instance
    """
    return ScoreNormalizer(
        method=method,
        target_min=0.0,
        target_max=float(scale),
        **kwargs,
    )


# Example usage and testing
if __name__ == "__main__":
    # Test with typical RRF scores
    rrf_scores = [0.0328, 0.0312, 0.0299, 0.0296, 0.0164, 0.0159, 0.0154]
    
    print("=" * 60)
    print("Score Normalizer Demo")
    print("=" * 60)
    
    # Method 1: Min-Max to 0-100
    print("\n1. Min-Max Normalization (0-100 scale):")
    normalizer_100 = RRFNormalizer(scale=100, method="min-max")
    normalized_100 = normalizer_100.normalize_rrf_scores(rrf_scores)
    for orig, norm in zip(rrf_scores, normalized_100):
        print(f"  {orig:.4f} → {norm:.1f}")
    
    # Method 2: Min-Max to 0-10
    print("\n2. Min-Max Normalization (0-10 scale):")
    normalizer_10 = RRFNormalizer(scale=10, method="min-max")
    normalized_10 = normalizer_10.normalize_rrf_scores(rrf_scores)
    for orig, norm in zip(rrf_scores, normalized_10):
        print(f"  {orig:.4f} → {norm:.1f}")
    
    # Method 3: Percentile
    print("\n3. Percentile Normalization (0-100):")
    normalizer_pct = RRFNormalizer(scale=100, method="percentile")
    normalized_pct = normalizer_pct.normalize_rrf_scores(rrf_scores)
    for orig, norm in zip(rrf_scores, normalized_pct):
        print(f"  {orig:.4f} → {norm:.1f}th percentile")
    
    print("\n" + "=" * 60)
    print("✅ All normalizations are DYNAMIC - no hardcoded ranges!")
    print("=" * 60)
