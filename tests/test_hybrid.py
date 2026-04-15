"""Tests for hybrid search in packages/retrieval/hybrid.py."""

from datetime import date
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from packages.common.config import Settings
from packages.common.types import QueryPlan, QueryStrategy, RetrievedDocument
from packages.retrieval.hybrid import HybridSearchEngine, HybridRetriever


class TestHybridSearchEngine:
    """Test suite for HybridSearchEngine class."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            qdrant_host="localhost",
            qdrant_port=6333,
            qdrant_collection="test_collection",
            opensearch_host="localhost",
            opensearch_port=9200,
            opensearch_index="test_index",
            opensearch_user="admin",
            opensearch_password="admin",
            postgres_host="localhost",
            postgres_port=5432,
            postgres_db="test_db",
            postgres_user="postgres",
            postgres_password="postgres",
            embedding_model="test-model",
            embedding_dim=768,
        )

    @pytest.fixture
    def sample_retrieved_docs(self):
        """Create sample retrieved documents."""
        return [
            RetrievedDocument(
                doc_id="doc-1",
                content="Content 1",
                title="Document 1",
                score=0.95,
                metadata={"doc_type": "luat"},
            ),
            RetrievedDocument(
                doc_id="doc-2",
                content="Content 2",
                title="Document 2",
                score=0.85,
                metadata={"doc_type": "nghi_dinh"},
            ),
        ]

    @pytest.mark.asyncio
    async def test_get_qdrant_client_creates_new(self, settings):
        """Test that _get_qdrant_client creates a new client when none exists."""
        engine = HybridSearchEngine(settings)
        mock_client = AsyncMock()

        with patch("qdrant_client.AsyncQdrantClient", return_value=mock_client):
            client = await engine._get_qdrant_client()

        assert client is mock_client
        assert engine._qdrant_client is mock_client

    @pytest.mark.asyncio
    async def test_get_qdrant_client_returns_cached(self, settings):
        """Test that _get_qdrant_client returns cached client if already created."""
        engine = HybridSearchEngine(settings)
        mock_client = AsyncMock()
        engine._qdrant_client = mock_client

        with patch("qdrant_client.AsyncQdrantClient") as mock_constructor:
            client = await engine._get_qdrant_client()
            mock_constructor.assert_not_called()

        assert client is mock_client

    @pytest.mark.asyncio
    async def test_get_opensearch_client_creates_new(self, settings):
        """Test that _get_opensearch_client creates a new client when none exists."""
        engine = HybridSearchEngine(settings)
        mock_client = AsyncMock()

        with patch("opensearchpy.AsyncOpenSearch", return_value=mock_client):
            client = await engine._get_opensearch_client()

        assert client is mock_client
        assert engine._opensearch_client is mock_client

    @pytest.mark.asyncio
    async def test_get_opensearch_client_returns_cached(self, settings):
        """Test that _get_opensearch_client returns cached client if already created."""
        engine = HybridSearchEngine(settings)
        mock_client = AsyncMock()
        engine._opensearch_client = mock_client

        with patch("opensearchpy.AsyncOpenSearch") as mock_constructor:
            client = await engine._get_opensearch_client()
            mock_constructor.assert_not_called()

        assert client is mock_client

    @pytest.mark.asyncio
    async def test_bm25_search_success(self, settings):
        """Test successful BM25 search."""
        engine = HybridSearchEngine(settings)
        mock_client = AsyncMock()

        mock_response = {
            "hits": {
                "hits": [
                    {"_id": "doc-1", "_score": 1.5},
                    {"_id": "doc-2", "_score": 1.2},
                ]
            }
        }
        mock_client.search.return_value = mock_response
        engine._opensearch_client = mock_client

        results = await engine._bm25_search("test query", size=10)

        assert len(results) == 2
        assert results[0] == ("doc-1", 1.5)
        assert results[1] == ("doc-2", 1.2)

    @pytest.mark.asyncio
    async def test_bm25_search_empty_results(self, settings):
        """Test BM25 search with empty results."""
        engine = HybridSearchEngine(settings)
        mock_client = AsyncMock()

        mock_response = {"hits": {"hits": []}}
        mock_client.search.return_value = mock_response
        engine._opensearch_client = mock_client

        results = await engine._bm25_search("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_bm25_search_with_filters(self, settings):
        """Test BM25 search with filters."""
        engine = HybridSearchEngine(settings)
        mock_client = AsyncMock()

        mock_response = {"hits": {"hits": [{"_id": "doc-1", "_score": 1.0}]}}
        mock_client.search.return_value = mock_response
        engine._opensearch_client = mock_client

        filters = {"doc_type": "luat", "level": 1}
        await engine._bm25_search("test query", filters=filters)

        # Verify search was called with filter clauses
        call_args = mock_client.search.call_args
        assert "body" in call_args[1] or call_args[1].get("body")

    @pytest.mark.asyncio
    async def test_bm25_search_error(self, settings):
        """Test BM25 search handles errors gracefully."""
        engine = HybridSearchEngine(settings)
        mock_client = AsyncMock()
        mock_client.search.side_effect = Exception("Search error")
        engine._opensearch_client = mock_client

        results = await engine._bm25_search("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_dense_search_success(self, settings):
        """Test successful dense search."""
        engine = HybridSearchEngine(settings)
        mock_client = AsyncMock()

        mock_results = [
            MagicMock(id="doc-1", score=0.95),
            MagicMock(id="doc-2", score=0.85),
        ]
        mock_client.search.return_value = mock_results
        engine._qdrant_client = mock_client

        # Mock embedding service
        engine._embedding_service = MagicMock()
        engine._embedding_service.encode_query = AsyncMock(return_value=[0.1] * 768)

        with patch.object(engine, "_embed_query", return_value=[0.1] * 768):
            results = await engine._dense_search("test query", limit=10)

        assert len(results) == 2
        assert results[0] == ("doc-1", 0.95)
        assert results[1] == ("doc-2", 0.85)

    @pytest.mark.asyncio
    async def test_dense_search_empty_results(self, settings):
        """Test dense search with empty results."""
        engine = HybridSearchEngine(settings)
        mock_client = AsyncMock()

        mock_client.search.return_value = []
        engine._qdrant_client = mock_client

        with patch.object(engine, "_embed_query", return_value=[0.1] * 768):
            results = await engine._dense_search("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_dense_search_error(self, settings):
        """Test dense search handles errors gracefully."""
        engine = HybridSearchEngine(settings)
        mock_client = AsyncMock()
        mock_client.search.side_effect = Exception("Search error")
        engine._qdrant_client = mock_client

        with patch.object(engine, "_embed_query", return_value=[0.1] * 768):
            results = await engine._dense_search("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_success(self, settings, sample_retrieved_docs):
        """Test successful hybrid search."""
        engine = HybridSearchEngine(settings)

        bm25_results = [("doc-1", 1.5), ("doc-2", 1.2)]
        dense_results = [("doc-1", 0.95), ("doc-2", 0.85)]

        with patch.object(engine, "_bm25_search", return_value=bm25_results), \
             patch.object(engine, "_dense_search", return_value=dense_results), \
             patch.object(engine, "_fetch_documents", return_value=sample_retrieved_docs):
            results = await engine.search("test query", top_k=2)

        assert len(results) == 2
        assert results[0].doc_id == "doc-1"
        assert results[1].doc_id == "doc-2"

    @pytest.mark.asyncio
    async def test_search_with_bm25_failure(self, settings, sample_retrieved_docs):
        """Test search continues when BM25 fails."""
        engine = HybridSearchEngine(settings)

        dense_results = [("doc-1", 0.95), ("doc-2", 0.85)]

        with patch.object(engine, "_bm25_search", return_value=[]), \
             patch.object(engine, "_dense_search", return_value=dense_results), \
             patch.object(engine, "_fetch_documents", return_value=sample_retrieved_docs):
            results = await engine.search("test query", top_k=2)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_with_dense_failure(self, settings, sample_retrieved_docs):
        """Test search continues when dense search fails."""
        engine = HybridSearchEngine(settings)

        bm25_results = [("doc-1", 1.5), ("doc-2", 1.2)]

        with patch.object(engine, "_bm25_search", return_value=bm25_results), \
             patch.object(engine, "_dense_search", return_value=[]), \
             patch.object(engine, "_fetch_documents", return_value=sample_retrieved_docs):
            results = await engine.search("test query", top_k=2)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_both_failures(self, settings):
        """Test search handles both BM25 and dense failures."""
        engine = HybridSearchEngine(settings)

        with patch.object(engine, "_bm25_search", return_value=[]), \
             patch.object(engine, "_dense_search", return_value=[]), \
             patch.object(engine, "_fetch_documents", return_value=[]):
            results = await engine.search("test query", top_k=2)

        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_query_plan(self, settings, sample_retrieved_docs):
        """Test search with query plan."""
        engine = HybridSearchEngine(settings)

        query_plan = QueryPlan(
            original_query="test query",
            normalized_query="test query",
            expansion_variants=[],
            has_negation=False,
            citations=[],
            strategy=QueryStrategy.SEMANTIC,
        )

        bm25_results = [("doc-1", 1.5)]
        dense_results = [("doc-1", 0.95)]

        with patch.object(engine, "_bm25_search", return_value=bm25_results), \
             patch.object(engine, "_dense_search", return_value=dense_results), \
             patch.object(engine, "_fetch_documents", return_value=sample_retrieved_docs[:1]):
            results = await engine.search("test query", query_plan=query_plan, top_k=1)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_with_custom_parameters(self, settings, sample_retrieved_docs):
        """Test search with custom parameters."""
        engine = HybridSearchEngine(settings)

        bm25_results = [("doc-1", 1.5), ("doc-2", 1.2)]
        dense_results = [("doc-1", 0.95), ("doc-2", 0.85)]

        with patch.object(engine, "_bm25_search", return_value=bm25_results) as mock_bm25, \
             patch.object(engine, "_dense_search", return_value=dense_results) as mock_dense, \
             patch.object(engine, "_fetch_documents", return_value=sample_retrieved_docs):
            await engine.search(
                "test query",
                top_k=5,
                bm25_candidates=50,
                dense_candidates=50,
                rrf_k=30,
            )

        mock_bm25.assert_called_once()
        mock_dense.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_documents_success(self, settings):
        """Test successful document fetching."""
        engine = HybridSearchEngine(settings)

        mock_conn = AsyncMock()
        mock_rows = [
            {"id": "doc-1", "content": "Content 1", "title": "Title 1", "doc_type": "luat", "metadata": {"key": "value"}},
            {"id": "doc-2", "content": "Content 2", "title": "Title 2", "doc_type": "nghi_dinh", "metadata": None},
        ]
        mock_conn.fetch.return_value = mock_rows

        # Create async context manager mock
        class AsyncContextManagerMock:
            async def __aenter__(self):
                return mock_conn
            async def __aexit__(self, *args):
                return False

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = AsyncContextManagerMock()
        engine._postgres_pool = mock_pool

        scores = {"doc-1": 0.95, "doc-2": 0.85}
        results = await engine._fetch_documents(["doc-1", "doc-2"], scores)

        assert len(results) == 2
        assert results[0].doc_id == "doc-1"
        assert results[0].score == 0.95
        assert results[1].doc_id == "doc-2"

    @pytest.mark.asyncio
    async def test_fetch_documents_empty_ids(self, settings):
        """Test fetching with empty document IDs."""
        engine = HybridSearchEngine(settings)
        results = await engine._fetch_documents([], {})
        assert results == []

    @pytest.mark.asyncio
    async def test_fetch_documents_error(self, settings):
        """Test document fetching handles errors gracefully."""
        engine = HybridSearchEngine(settings)

        mock_pool = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(side_effect=Exception("DB error"))
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        engine._postgres_pool = mock_pool

        results = await engine._fetch_documents(["doc-1"], {"doc-1": 0.95})
        assert results == []

    @pytest.mark.asyncio
    async def test_embed_query(self, settings):
        """Test query embedding."""
        engine = HybridSearchEngine(settings)
        engine._embedding_service = MagicMock()
        engine._embedding_service.encode_query.return_value = [0.1] * 768

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = MagicMock()
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=[0.1] * 768)
            result = await engine._embed_query("test query")

        assert result == [0.1] * 768

    def test_build_opensearch_filters(self, settings):
        """Test building OpenSearch filter clauses."""
        engine = HybridSearchEngine(settings)

        filters = {
            "doc_type": "luat",
            "level": [1, 2],
            "date": {"gte": "2020-01-01"},
        }
        clauses = engine._build_opensearch_filters(filters)

        assert len(clauses) == 3
        assert clauses[0] == {"term": {"doc_type": "luat"}}
        assert clauses[1] == {"terms": {"level": [1, 2]}}
        assert clauses[2] == {"range": {"date": {"gte": "2020-01-01"}}}

    def test_build_qdrant_filters(self, settings):
        """Test building Qdrant filter conditions."""
        engine = HybridSearchEngine(settings)

        filters = {
            "doc_type": "luat",
            "level": [1, 2],
            "date": {"gte": "2020-01-01", "lte": "2021-12-31"},
        }

        with patch("qdrant_client.models.FieldCondition"), \
             patch("qdrant_client.models.Filter"), \
             patch("qdrant_client.models.MatchAny"), \
             patch("qdrant_client.models.MatchValue"), \
             patch("qdrant_client.models.Range"):
            result = engine._build_qdrant_filters(filters)
            assert result is not None

    @pytest.mark.asyncio
    async def test_close(self, settings):
        """Test closing all client connections."""
        engine = HybridSearchEngine(settings)

        mock_qdrant = AsyncMock()
        mock_opensearch = AsyncMock()
        mock_pool = AsyncMock()

        engine._qdrant_client = mock_qdrant
        engine._opensearch_client = mock_opensearch
        engine._postgres_pool = mock_pool

        await engine.close()

        mock_qdrant.close.assert_called_once()
        mock_opensearch.close.assert_called_once()
        mock_pool.close.assert_called_once()
        assert engine._qdrant_client is None
        assert engine._opensearch_client is None
        assert engine._postgres_pool is None


class TestHybridRetriever:
    """Test suite for HybridRetriever alias class."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            qdrant_host="localhost",
            qdrant_port=6333,
            qdrant_collection="test_collection",
            opensearch_host="localhost",
            opensearch_port=9200,
            opensearch_index="test_index",
            opensearch_user="admin",
            opensearch_password="admin",
            postgres_host="localhost",
            postgres_port=5432,
            postgres_db="test_db",
            postgres_user="postgres",
            postgres_password="postgres",
            embedding_model="test-model",
            embedding_dim=768,
        )

    def test_hybrid_retriever_is_alias(self, settings):
        """Test that HybridRetriever is an alias for HybridSearchEngine."""
        retriever = HybridRetriever(settings)
        assert isinstance(retriever, HybridSearchEngine)

    @pytest.mark.asyncio
    async def test_retrieve_method(self, settings):
        """Test that retrieve method works (alias for search)."""
        retriever = HybridRetriever(settings)

        sample_docs = [
            RetrievedDocument(
                doc_id="doc-1",
                content="Content 1",
                title="Title 1",
                score=0.95,
            )
        ]

        with patch.object(retriever, "_bm25_search", return_value=[("doc-1", 1.5)]), \
             patch.object(retriever, "_dense_search", return_value=[("doc-1", 0.95)]), \
             patch.object(retriever, "_fetch_documents", return_value=sample_docs):
            results = await retriever.search("test query", top_k=1)

        assert len(results) == 1
        assert results[0].doc_id == "doc-1"

    @pytest.mark.asyncio
    async def test_retriever_close(self, settings):
        """Test HybridRetriever close method."""
        retriever = HybridRetriever(settings)

        mock_qdrant = AsyncMock()
        mock_opensearch = AsyncMock()

        retriever._qdrant_client = mock_qdrant
        retriever._opensearch_client = mock_opensearch

        await retriever.close()

        mock_qdrant.close.assert_called_once()
        mock_opensearch.close.assert_called_once()
