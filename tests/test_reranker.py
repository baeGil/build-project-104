"""Tests for reranker module in packages/retrieval/reranker.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from packages.common.types import RetrievedDocument
from packages.retrieval.reranker import (
    LegalReranker,
    SimpleReranker,
    create_reranker,
)


class TestLegalReranker:
    """Test suite for LegalReranker class."""

    def test_init_default_budget(self):
        """Test initialization with default budget."""
        reranker = LegalReranker()
        assert reranker.budget_ms == 150.0
        assert reranker._colbert_model is None
        assert reranker._cross_encoder is None

    def test_init_custom_budget(self):
        """Test initialization with custom budget."""
        reranker = LegalReranker(budget_ms=100.0)
        assert reranker.budget_ms == 100.0

    def test_compute_position_decay_score(self):
        """Test position decay score computation."""
        # Test basic case
        score = LegalReranker._compute_position_decay_score(
            original_score=0.9, position=0, total=10, alpha=0.7
        )
        # score = 0.7 * 0.9 + 0.3 * (1 - 0/9) = 0.63 + 0.3 = 0.93
        expected = 0.7 * 0.9 + 0.3 * 1.0
        assert abs(score - expected) < 1e-10

    def test_compute_position_decay_score_last_position(self):
        """Test position decay at last position."""
        score = LegalReranker._compute_position_decay_score(
            original_score=0.9, position=9, total=10, alpha=0.7
        )
        # score = 0.7 * 0.9 + 0.3 * (1 - 9/9) = 0.63 + 0 = 0.63
        expected = 0.7 * 0.9 + 0.3 * 0.0
        assert abs(score - expected) < 1e-10

    def test_compute_position_decay_score_single_item(self):
        """Test position decay with single item."""
        score = LegalReranker._compute_position_decay_score(
            original_score=0.9, position=0, total=1, alpha=0.7
        )
        # With total <= 1, position_factor should be 1.0
        expected = 0.7 * 0.9 + 0.3 * 1.0
        assert abs(score - expected) < 1e-10

    def test_compute_position_decay_score_different_alpha(self):
        """Test position decay with different alpha values."""
        # Alpha = 1.0 (only original score matters)
        score = LegalReranker._compute_position_decay_score(
            original_score=0.8, position=5, total=10, alpha=1.0
        )
        assert abs(score - 0.8) < 1e-10

        # Alpha = 0.0 (only position matters)
        score = LegalReranker._compute_position_decay_score(
            original_score=0.8, position=0, total=10, alpha=0.0
        )
        assert abs(score - 1.0) < 1e-10

    def test_stage1_position_decay(self):
        """Test Stage 1 position decay scoring."""
        reranker = LegalReranker()
        
        candidates = [
            RetrievedDocument(doc_id="doc1", content="content1", score=0.9),
            RetrievedDocument(doc_id="doc2", content="content2", score=0.8),
            RetrievedDocument(doc_id="doc3", content="content3", score=0.7),
            RetrievedDocument(doc_id="doc4", content="content4", score=0.6),
        ]
        
        result = reranker._stage1_position_decay(candidates)
        
        # Should return top half (2 documents)
        assert len(result) == 2
        
        # All returned docs should have rerank_score set
        for doc in result:
            assert doc.rerank_score is not None

    def test_stage1_position_decay_single_candidate(self):
        """Test Stage 1 with single candidate."""
        reranker = LegalReranker()
        
        candidates = [
            RetrievedDocument(doc_id="doc1", content="content1", score=0.9),
        ]
        
        result = reranker._stage1_position_decay(candidates)
        
        # Should return at least 1 document
        assert len(result) == 1
        assert result[0].doc_id == "doc1"

    def test_stage1_position_decay_empty(self):
        """Test Stage 1 with empty candidates."""
        reranker = LegalReranker()
        result = reranker._stage1_position_decay([])
        assert result == []

    @pytest.mark.skip(reason="fastembed not installed")
    def test_load_colbert_fastembed_success(self):
        """Test loading ColBERT model via fastembed."""
        reranker = LegalReranker()
        
        mock_model = MagicMock()
        with patch("fastembed.LateInteractionTextEmbedding", return_value=mock_model):
            success = reranker._load_colbert()
        
        assert success is True
        assert reranker._colbert_model is mock_model
        assert reranker._model_type == "colbert"

    @pytest.mark.skip(reason="fastembed not installed")
    def test_load_colbert_cross_encoder_fallback(self):
        """Test fallback to cross-encoder when fastembed not available."""
        reranker = LegalReranker()
        
        mock_model = MagicMock()
        with patch("fastembed.LateInteractionTextEmbedding", side_effect=ImportError()):
            with patch("sentence_transformers.CrossEncoder", return_value=mock_model):
                success = reranker._load_colbert()
        
        assert success is True
        assert reranker._cross_encoder is mock_model
        assert reranker._model_type == "cross_encoder"

    @pytest.mark.skip(reason="fastembed not installed")
    def test_load_colbert_both_fail(self):
        """Test when both model loading attempts fail."""
        reranker = LegalReranker()
        
        with patch("fastembed.LateInteractionTextEmbedding", side_effect=ImportError()):
            with patch("sentence_transformers.CrossEncoder", side_effect=RuntimeError("Load failed")):
                success = reranker._load_colbert()
        
        assert success is False
        assert reranker._colbert_model is None
        assert reranker._cross_encoder is None

    def test_load_colbert_already_loaded(self):
        """Test load when model already loaded."""
        reranker = LegalReranker()
        reranker._colbert_model = MagicMock()
        reranker._model_type = "colbert"
        
        success = reranker._load_colbert()
        
        assert success is True
        # Should not try to load again

    @pytest.mark.asyncio
    async def test_rerank_empty_candidates(self):
        """Test rerank with empty candidates."""
        reranker = LegalReranker()
        result = await reranker.rerank("query", [], top_k=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_budget_exceeded(self):
        """Test rerank when latency budget is exceeded after Stage 1."""
        reranker = LegalReranker(budget_ms=0.001)  # Very tight budget
        
        candidates = [
            RetrievedDocument(doc_id="doc1", content="content1", score=0.9),
            RetrievedDocument(doc_id="doc2", content="content2", score=0.8),
        ]
        
        result = await reranker.rerank("query", candidates, top_k=5)
        
        # Should return Stage 1 results
        assert len(result) == 1  # Top half of 2 = 1
        assert result[0].rerank_score is not None

    @pytest.mark.asyncio
    async def test_rerank_stage2_fallback_on_error(self):
        """Test fallback to Stage 1 when Stage 2 fails."""
        reranker = LegalReranker(budget_ms=1000.0)
        
        candidates = [
            RetrievedDocument(doc_id="doc1", content="content1", score=0.9),
        ]
        
        # Mock _stage2_model_rerank to raise exception
        reranker._stage2_model_rerank = AsyncMock(side_effect=RuntimeError("Stage 2 failed"))
        
        result = await reranker.rerank("query", candidates, top_k=5)
        
        # Should return Stage 1 results
        assert len(result) == 1
        assert result[0].rerank_score == 0.9  # Original score used as fallback

    @pytest.mark.asyncio
    async def test_stage2_model_rerank_no_model(self):
        """Test Stage 2 when no model is available."""
        reranker = LegalReranker()
        
        candidates = [
            RetrievedDocument(doc_id="doc1", content="content1", score=0.9),
            RetrievedDocument(doc_id="doc2", content="content2", score=0.8),
        ]
        
        with patch.object(reranker, "_load_colbert", return_value=False):
            result = await reranker._stage2_model_rerank("query", candidates, top_k=2)
        
        # Should return candidates sorted by Stage 1 scores
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_rerank_with_colbert(self):
        """Test reranking with ColBERT model."""
        reranker = LegalReranker(budget_ms=1000.0)
        
        # Mock ColBERT model
        mock_model = MagicMock()
        mock_embeddings = [np.array([[0.1, 0.2], [0.3, 0.4]])]
        mock_model.embed.return_value = mock_embeddings
        reranker._colbert_model = mock_model
        reranker._model_type = "colbert"
        
        candidates = [
            RetrievedDocument(doc_id="doc1", content="content1", score=0.9),
        ]
        
        with patch.object(reranker, "_load_colbert", return_value=True):
            with patch.object(reranker, "_rerank_with_colbert", new_callable=AsyncMock) as mock_colbert:
                mock_colbert.return_value = candidates
                result = await reranker._stage2_model_rerank("query", candidates, top_k=1)
        
        assert result == candidates

    @pytest.mark.asyncio
    async def test_rerank_with_cross_encoder(self):
        """Test reranking with cross-encoder model."""
        reranker = LegalReranker(budget_ms=1000.0)
        
        reranker._cross_encoder = MagicMock()
        reranker._model_type = "cross_encoder"
        
        candidates = [
            RetrievedDocument(doc_id="doc1", content="content1", score=0.9),
        ]
        
        with patch.object(reranker, "_load_colbert", return_value=True):
            with patch.object(reranker, "_rerank_with_cross_encoder", new_callable=AsyncMock) as mock_ce:
                mock_ce.return_value = candidates
                result = await reranker._stage2_model_rerank("query", candidates, top_k=1)
        
        assert result == candidates

    def test_compute_max_similarity(self):
        """Test max-similarity computation for ColBERT."""
        # Create simple embeddings
        query_emb = np.array([[1.0, 0.0], [0.0, 1.0]])  # 2 query tokens
        doc_emb = np.array([[1.0, 0.0], [0.0, 1.0]])    # 2 doc tokens
        
        score = LegalReranker._compute_max_similarity(query_emb, doc_emb)
        
        # Should return a positive score
        assert score > 0
        assert isinstance(score, float)

    def test_compute_max_similarity_different_shapes(self):
        """Test max-similarity with different embedding shapes."""
        query_emb = np.array([[1.0, 0.0, 0.0]])  # 1 query token, 3 dims
        doc_emb = np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0]])  # 2 doc tokens
        
        score = LegalReranker._compute_max_similarity(query_emb, doc_emb)
        
        assert score > 0
        assert isinstance(score, float)


class TestSimpleReranker:
    """Test suite for SimpleReranker class."""

    @pytest.mark.asyncio
    async def test_simple_rerank_basic(self):
        """Test basic simple reranking."""
        reranker = SimpleReranker()
        
        candidates = [
            RetrievedDocument(doc_id="doc1", content="content1", score=0.9),
            RetrievedDocument(doc_id="doc2", content="content2", score=0.8),
            RetrievedDocument(doc_id="doc3", content="content3", score=0.7),
        ]
        
        result = await reranker.rerank("query", candidates, top_k=2)
        
        assert len(result) == 2
        # Should be sorted by decay score
        assert result[0].rerank_score >= result[1].rerank_score

    @pytest.mark.asyncio
    async def test_simple_rerank_empty(self):
        """Test simple rerank with empty candidates."""
        reranker = SimpleReranker()
        result = await reranker.rerank("query", [], top_k=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_simple_rerank_single_candidate(self):
        """Test simple rerank with single candidate."""
        reranker = SimpleReranker()
        
        candidates = [
            RetrievedDocument(doc_id="doc1", content="content1", score=0.9),
        ]
        
        result = await reranker.rerank("query", candidates, top_k=5)
        
        assert len(result) == 1
        assert result[0].doc_id == "doc1"
        assert result[0].rerank_score is not None

    @pytest.mark.asyncio
    async def test_simple_rerank_top_k_limit(self):
        """Test that top_k limits results."""
        reranker = SimpleReranker()
        
        candidates = [
            RetrievedDocument(doc_id=f"doc{i}", content=f"content{i}", score=1.0 - i * 0.1)
            for i in range(10)
        ]
        
        result = await reranker.rerank("query", candidates, top_k=3)
        
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_simple_rerank_preserves_order_by_score(self):
        """Test that reranking preserves order by decay score."""
        reranker = SimpleReranker()
        
        # Create candidates with decreasing scores
        candidates = [
            RetrievedDocument(doc_id="doc1", content="content1", score=1.0),
            RetrievedDocument(doc_id="doc2", content="content2", score=0.9),
            RetrievedDocument(doc_id="doc3", content="content3", score=0.8),
        ]
        
        result = await reranker.rerank("query", candidates, top_k=3)
        
        # First doc should have highest decay score
        assert result[0].doc_id == "doc1"
        # Decay scores should be set
        for doc in result:
            assert doc.rerank_score is not None


class TestCreateReranker:
    """Test suite for create_reranker factory function."""

    def test_create_simple_reranker(self):
        """Test creating SimpleReranker when use_model=False."""
        reranker = create_reranker(use_model=False, budget_ms=150.0)
        
        assert isinstance(reranker, SimpleReranker)
        assert not isinstance(reranker, LegalReranker)

    @pytest.mark.skip(reason="fastembed not installed")
    def test_create_legal_reranker_with_model(self):
        """Test creating LegalReranker when model loads successfully."""
        with patch("fastembed.LateInteractionTextEmbedding") as mock_fastembed:
            mock_fastembed.return_value = MagicMock()
            reranker = create_reranker(use_model=True, budget_ms=150.0)
        
        assert isinstance(reranker, LegalReranker)
        assert reranker._model_type == "colbert"

    @pytest.mark.skip(reason="fastembed not installed")
    def test_create_fallback_to_simple_when_model_fails(self):
        """Test fallback to SimpleReranker when model loading fails."""
        with patch("fastembed.LateInteractionTextEmbedding", side_effect=ImportError()):
            with patch("sentence_transformers.CrossEncoder", side_effect=RuntimeError("Failed")):
                reranker = create_reranker(use_model=True, budget_ms=150.0)
        
        assert isinstance(reranker, SimpleReranker)
        assert not isinstance(reranker, LegalReranker)

    @pytest.mark.skip(reason="fastembed not installed")
    def test_create_legal_reranker_custom_budget(self):
        """Test creating LegalReranker with custom budget."""
        with patch("fastembed.LateInteractionTextEmbedding") as mock_fastembed:
            mock_fastembed.return_value = MagicMock()
            reranker = create_reranker(use_model=True, budget_ms=200.0)
        
        assert isinstance(reranker, LegalReranker)
        assert reranker.budget_ms == 200.0

    def test_create_simple_reranker_ignores_budget(self):
        """Test that SimpleReranker doesn't use budget parameter."""
        reranker = create_reranker(use_model=False, budget_ms=100.0)
        
        assert isinstance(reranker, SimpleReranker)
        # SimpleReranker doesn't have budget_ms attribute
        assert not hasattr(reranker, "budget_ms")
