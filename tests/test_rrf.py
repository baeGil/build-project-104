"""Tests for RRF (Reciprocal Rank Fusion) in packages/retrieval/rrf.py."""

import pytest

from packages.retrieval.rrf import (
    ReciprocalRankFusion,
    reciprocal_rank_fusion,
    weighted_rrf,
)


class TestReciprocalRankFusion:
    """Test suite for reciprocal_rank_fusion function."""

    def test_basic_fusion_two_lists(self):
        """Test basic RRF fusion with two result lists."""
        # List 1: doc1 rank 1, doc2 rank 2, doc3 rank 3
        list1 = [("doc1", 1.0), ("doc2", 0.9), ("doc3", 0.8)]
        # List 2: doc2 rank 1, doc3 rank 2, doc4 rank 3
        list2 = [("doc2", 1.0), ("doc3", 0.9), ("doc4", 0.8)]
        
        result = reciprocal_rank_fusion([list1, list2], k=60, top_n=10)
        
        # doc2 appears in both lists at rank 2 and 1
        # doc3 appears in both lists at rank 3 and 2
        # doc1 appears only in list1 at rank 1
        # doc4 appears only in list2 at rank 3
        doc_scores = {doc_id: score for doc_id, score in result}
        
        # doc2 should have highest score (appears in both, good ranks)
        assert result[0][0] == "doc2"
        # Score for doc2: 1/(60+2) + 1/(60+1) = 1/62 + 1/61
        expected_doc2_score = 1/62 + 1/61
        assert abs(doc_scores["doc2"] - expected_doc2_score) < 1e-10

    def test_fusion_with_k_parameter(self):
        """Test RRF fusion with different k values."""
        list1 = [("doc1", 1.0), ("doc2", 0.9)]
        list2 = [("doc2", 1.0), ("doc1", 0.9)]
        
        # With k=60 (default)
        result_k60 = reciprocal_rank_fusion([list1, list2], k=60, top_n=10)
        
        # With k=10 (lower k emphasizes top ranks more)
        result_k10 = reciprocal_rank_fusion([list1, list2], k=10, top_n=10)
        
        # Both should have same ranking but different scores
        assert [doc_id for doc_id, _ in result_k60] == [doc_id for doc_id, _ in result_k10]
        
        # Scores with lower k should be higher (denominator is smaller)
        k60_scores = {doc_id: score for doc_id, score in result_k60}
        k10_scores = {doc_id: score for doc_id, score in result_k10}
        assert k10_scores["doc1"] > k60_scores["doc1"]

    def test_fusion_top_n_limit(self):
        """Test that top_n parameter limits results."""
        list1 = [(f"doc{i}", 1.0 - i * 0.1) for i in range(10)]
        list2 = [(f"doc{i}", 1.0 - i * 0.1) for i in range(10)]
        
        result_top5 = reciprocal_rank_fusion([list1, list2], k=60, top_n=5)
        result_top10 = reciprocal_rank_fusion([list1, list2], k=60, top_n=10)
        
        assert len(result_top5) == 5
        assert len(result_top10) == 10

    def test_fusion_empty_lists(self):
        """Test fusion with empty result lists."""
        result = reciprocal_rank_fusion([], k=60, top_n=10)
        assert result == []
        
        result = reciprocal_rank_fusion([[], []], k=60, top_n=10)
        assert result == []

    def test_fusion_single_list(self):
        """Test fusion with single result list."""
        list1 = [("doc1", 1.0), ("doc2", 0.9), ("doc3", 0.8)]
        
        result = reciprocal_rank_fusion([list1], k=60, top_n=10)
        
        # Should return documents in order with RRF scores
        assert len(result) == 3
        assert result[0][0] == "doc1"
        assert result[1][0] == "doc2"
        assert result[2][0] == "doc3"
        
        # Verify RRF scores
        assert abs(result[0][1] - 1/61) < 1e-10  # rank 1
        assert abs(result[1][1] - 1/62) < 1e-10  # rank 2
        assert abs(result[2][1] - 1/63) < 1e-10  # rank 3

    def test_fusion_document_not_in_all_lists(self):
        """Test fusion when documents appear in only some lists."""
        list1 = [("doc1", 1.0), ("doc2", 0.9)]
        list2 = [("doc3", 1.0), ("doc4", 0.9)]
        
        result = reciprocal_rank_fusion([list1, list2], k=60, top_n=10)
        
        # All docs should appear, each with score from only one list
        doc_ids = [doc_id for doc_id, _ in result]
        assert set(doc_ids) == {"doc1", "doc2", "doc3", "doc4"}

    def test_fusion_same_document_multiple_lists(self):
        """Test fusion when same document appears in multiple lists."""
        list1 = [("doc1", 1.0)]  # rank 1
        list2 = [("doc1", 0.5)]  # rank 1 in second list
        list3 = [("doc1", 0.3)]  # rank 1 in third list
        
        result = reciprocal_rank_fusion([list1, list2, list3], k=60, top_n=10)
        
        # doc1 should have score from all three lists
        assert len(result) == 1
        assert result[0][0] == "doc1"
        expected_score = 3 * (1/61)  # 3 lists, rank 1 in each
        assert abs(result[0][1] - expected_score) < 1e-10

    def test_fusion_score_ordering(self):
        """Test that results are properly sorted by score descending."""
        # Create lists where doc with lower individual scores should win
        list1 = [("docA", 0.5), ("docB", 0.4)]  # docA at rank 1
        list2 = [("docB", 1.0), ("docA", 0.9)]  # docB at rank 1
        list3 = [("docB", 0.8), ("docA", 0.7)]  # docB at rank 1
        
        result = reciprocal_rank_fusion([list1, list2, list3], k=60, top_n=10)
        
        # docB should win because it appears at rank 1 in 2 out of 3 lists
        assert result[0][0] == "docB"
        
        # Verify scores
        # docB: 1/62 + 1/61 + 1/61 (rank 2, 1, 1)
        # docA: 1/61 + 1/62 + 1/62 (rank 1, 2, 2)
        docB_score = 1/62 + 1/61 + 1/61
        docA_score = 1/61 + 1/62 + 1/62
        scores = {doc_id: score for doc_id, score in result}
        assert abs(scores["docB"] - docB_score) < 1e-10
        assert abs(scores["docA"] - docA_score) < 1e-10


class TestWeightedRRF:
    """Test suite for weighted_rrf function."""

    def test_basic_weighted_fusion(self):
        """Test basic weighted RRF fusion."""
        list1 = [("doc1", 1.0), ("doc2", 0.9)]
        list2 = [("doc2", 1.0), ("doc1", 0.9)]
        weights = [2.0, 1.0]  # First list has double weight
        
        result = weighted_rrf([list1, list2], weights, k=60, top_n=10)
        
        doc_scores = {doc_id: score for doc_id, score in result}
        
        # doc1: 2.0 * 1/61 + 1.0 * 1/62
        # doc2: 2.0 * 1/62 + 1.0 * 1/61
        expected_doc1 = 2.0 * (1/61) + 1.0 * (1/62)
        expected_doc2 = 2.0 * (1/62) + 1.0 * (1/61)
        
        assert abs(doc_scores["doc1"] - expected_doc1) < 1e-10
        assert abs(doc_scores["doc2"] - expected_doc2) < 1e-10
        # doc1 should win due to higher weight on list1 where it's rank 1
        assert result[0][0] == "doc1"

    def test_weighted_fusion_unequal_weights(self):
        """Test weighted fusion with significantly different weights."""
        list1 = [("docA", 1.0)]
        list2 = [("docB", 1.0)]
        weights = [10.0, 0.1]  # Heavy weight on first list
        
        result = weighted_rrf([list1, list2], weights, k=60, top_n=10)
        
        # docA should win despite both being rank 1
        assert result[0][0] == "docA"
        
        doc_scores = {doc_id: score for doc_id, score in result}
        assert abs(doc_scores["docA"] - 10.0 * (1/61)) < 1e-10
        assert abs(doc_scores["docB"] - 0.1 * (1/61)) < 1e-10

    def test_weighted_fusion_weights_length_mismatch(self):
        """Test that mismatched weights and lists raises ValueError."""
        list1 = [("doc1", 1.0)]
        list2 = [("doc2", 1.0)]
        weights = [1.0]  # Only one weight for two lists
        
        with pytest.raises(ValueError) as exc_info:
            weighted_rrf([list1, list2], weights, k=60, top_n=10)
        
        assert "Number of weights" in str(exc_info.value)
        assert "must match" in str(exc_info.value)

    def test_weighted_fusion_equal_weights(self):
        """Test weighted fusion with equal weights equals regular fusion."""
        list1 = [("doc1", 1.0), ("doc2", 0.9)]
        list2 = [("doc2", 1.0), ("doc1", 0.9)]
        
        regular_result = reciprocal_rank_fusion([list1, list2], k=60, top_n=10)
        weighted_result = weighted_rrf([list1, list2], [1.0, 1.0], k=60, top_n=10)
        
        # Results should be identical
        assert len(regular_result) == len(weighted_result)
        for (doc1, score1), (doc2, score2) in zip(regular_result, weighted_result):
            assert doc1 == doc2
            assert abs(score1 - score2) < 1e-10

    def test_weighted_fusion_zero_weights(self):
        """Test weighted fusion with zero weight for some lists."""
        list1 = [("doc1", 1.0)]
        list2 = [("doc2", 1.0)]
        weights = [1.0, 0.0]  # Second list has zero weight
        
        result = weighted_rrf([list1, list2], weights, k=60, top_n=10)
        
        # Only doc1 should have a non-zero score
        doc_scores = {doc_id: score for doc_id, score in result}
        assert doc_scores["doc1"] > 0
        assert doc_scores["doc2"] == 0


class TestReciprocalRankFusionClass:
    """Test suite for ReciprocalRankFusion class."""

    def test_default_k_value(self):
        """Test default k value in constructor."""
        rrf = ReciprocalRankFusion()
        assert rrf.k == 60

    def test_custom_k_value(self):
        """Test custom k value in constructor."""
        rrf = ReciprocalRankFusion(k=100)
        assert rrf.k == 100

    def test_fuse_method(self):
        """Test fuse method calls reciprocal_rank_fusion."""
        rrf = ReciprocalRankFusion(k=60)
        
        list1 = [("doc1", 1.0), ("doc2", 0.9)]
        list2 = [("doc2", 1.0), ("doc1", 0.9)]
        
        result = rrf.fuse([list1, list2], top_n=10)
        
        # Should produce same result as function
        expected = reciprocal_rank_fusion([list1, list2], k=60, top_n=10)
        assert result == expected

    def test_fuse_weighted_method(self):
        """Test fuse_weighted method calls weighted_rrf."""
        rrf = ReciprocalRankFusion(k=60)
        
        list1 = [("doc1", 1.0), ("doc2", 0.9)]
        list2 = [("doc2", 1.0), ("doc1", 0.9)]
        weights = [2.0, 1.0]
        
        result = rrf.fuse_weighted([list1, list2], weights, top_n=10)
        
        # Should produce same result as function
        expected = weighted_rrf([list1, list2], weights, k=60, top_n=10)
        assert result == expected

    def test_fuse_uses_instance_k(self):
        """Test that fuse method uses the instance's k value."""
        rrf = ReciprocalRankFusion(k=30)
        
        list1 = [("doc1", 1.0)]
        list2 = [("doc2", 1.0)]
        
        result = rrf.fuse([list1, list2], top_n=10)
        
        # Scores should use k=30
        doc_scores = {doc_id: score for doc_id, score in result}
        assert abs(doc_scores["doc1"] - 1/31) < 1e-10
        assert abs(doc_scores["doc2"] - 1/31) < 1e-10

    def test_fuse_weighted_uses_instance_k(self):
        """Test that fuse_weighted method uses the instance's k value."""
        rrf = ReciprocalRankFusion(k=30)
        
        list1 = [("doc1", 1.0)]
        list2 = [("doc2", 1.0)]
        weights = [1.0, 1.0]
        
        result = rrf.fuse_weighted([list1, list2], weights, top_n=10)
        
        # Scores should use k=30
        doc_scores = {doc_id: score for doc_id, score in result}
        assert abs(doc_scores["doc1"] - 1/31) < 1e-10
        assert abs(doc_scores["doc2"] - 1/31) < 1e-10
