"""Tests for document indexers in packages/ingestion/indexer.py."""

from datetime import date
from unittest.mock import MagicMock, patch, AsyncMock

import numpy as np
import pytest

from packages.common.config import Settings
from packages.common.types import LegalNode, DocumentType
from packages.ingestion.indexer import QdrantIndexer, OpenSearchIndexer, DocumentIndexer


class TestQdrantIndexer:
    """Test suite for QdrantIndexer class."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            qdrant_host="localhost",
            qdrant_port=6333,
            qdrant_collection="test_collection",
            embedding_model="test-model",
            embedding_dim=768,
        )

    @pytest.fixture
    def sample_nodes(self):
        """Create sample legal nodes for testing."""
        return [
            LegalNode(
                id="doc-1",
                title="Test Document 1",
                content="Content of document 1",
                doc_type=DocumentType.LAW,
                level=0,
                publish_date=date(2020, 1, 1),
                issuing_body="Test Body",
                document_number="01/2020",
                keywords=["test", "law"],
            ),
            LegalNode(
                id="doc-2",
                title="Test Document 2",
                content="Content of document 2",
                doc_type=DocumentType.DECREE,
                level=1,
                publish_date=date(2021, 6, 15),
                issuing_body="Test Body 2",
                document_number="02/2021",
                keywords=["test", "decree"],
            ),
        ]

    @pytest.mark.asyncio
    async def test_get_client_creates_new_client(self, settings):
        """Test that _get_client creates a new QdrantClient when none exists."""
        indexer = QdrantIndexer(settings)
        mock_client = MagicMock()

        with patch("qdrant_client.QdrantClient", return_value=mock_client):
            client = await indexer._get_client()

        assert client is mock_client
        assert indexer._client is mock_client

    @pytest.mark.asyncio
    async def test_get_client_returns_cached_client(self, settings):
        """Test that _get_client returns cached client if already created."""
        indexer = QdrantIndexer(settings)
        mock_client = MagicMock()
        indexer._client = mock_client

        with patch("qdrant_client.QdrantClient") as mock_constructor:
            client = await indexer._get_client()
            mock_constructor.assert_not_called()

        assert client is mock_client

    @pytest.mark.asyncio
    async def test_get_client_import_error(self, settings):
        """Test handling of ImportError when qdrant-client not installed."""
        indexer = QdrantIndexer(settings)

        with patch("qdrant_client.QdrantClient", side_effect=ImportError("No module named 'qdrant_client'")):
            with pytest.raises(ImportError):
                await indexer._get_client()

    @pytest.mark.asyncio
    async def test_get_embedding_model_creates_new_model(self, settings):
        """Test that _get_embedding_model creates a new model when none exists."""
        indexer = QdrantIndexer(settings)
        mock_model = MagicMock()

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
            model = await indexer._get_embedding_model()

        assert model is mock_model
        assert indexer._embedding_model is mock_model

    @pytest.mark.asyncio
    async def test_get_embedding_model_returns_cached_model(self, settings):
        """Test that _get_embedding_model returns cached model if already loaded."""
        indexer = QdrantIndexer(settings)
        mock_model = MagicMock()
        indexer._embedding_model = mock_model

        with patch("sentence_transformers.SentenceTransformer") as mock_constructor:
            model = await indexer._get_embedding_model()
            mock_constructor.assert_not_called()

        assert model is mock_model

    @pytest.mark.asyncio
    async def test_ensure_collection_creates_new_collection(self, settings):
        """Test that ensure_collection creates collection if it doesn't exist."""
        indexer = QdrantIndexer(settings)
        mock_client = MagicMock()
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_client.get_collections.return_value = mock_collections

        indexer._client = mock_client

        with patch("qdrant_client.models.Distance") as mock_distance, \
             patch("qdrant_client.models.HnswConfigDiff") as mock_hnsw, \
             patch("qdrant_client.models.VectorParams") as mock_vector_params:
            await indexer.ensure_collection()

        mock_client.create_collection.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_collection_skips_existing(self, settings):
        """Test that ensure_collection skips if collection already exists."""
        indexer = QdrantIndexer(settings)
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.name = "test_collection"
        mock_collections = MagicMock()
        mock_collections.collections = [mock_collection]
        mock_client.get_collections.return_value = mock_collections

        indexer._client = mock_client

        await indexer.ensure_collection()

        mock_client.create_collection.assert_not_called()

    @pytest.mark.asyncio
    async def test_index_documents_empty_list(self, settings):
        """Test that index_documents returns 0 for empty list."""
        indexer = QdrantIndexer(settings)
        result = await indexer.index_documents([])
        assert result == 0

    @pytest.mark.asyncio
    async def test_index_documents_success(self, settings, sample_nodes):
        """Test successful indexing of documents."""
        indexer = QdrantIndexer(settings)
        mock_client = MagicMock()
        mock_model = MagicMock()

        # Mock embeddings
        mock_embeddings = np.array([[0.1] * 768, [0.2] * 768])
        mock_model.encode.return_value = mock_embeddings

        indexer._client = mock_client
        indexer._embedding_model = mock_model

        with patch.object(indexer, "ensure_collection") as mock_ensure:
            result = await indexer.index_documents(sample_nodes, batch_size=64)

        assert result == 2
        mock_ensure.assert_called_once()
        mock_client.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_documents_with_batching(self, settings):
        """Test indexing with batching."""
        indexer = QdrantIndexer(settings)
        mock_client = MagicMock()
        mock_model = MagicMock()

        # Create 5 nodes
        nodes = [
            LegalNode(
                id=f"doc-{i}",
                title=f"Document {i}",
                content=f"Content {i}",
                doc_type=DocumentType.LAW,
                level=0,
            )
            for i in range(5)
        ]

        mock_embeddings = np.array([[0.1] * 768] * 5)
        mock_model.encode.return_value = mock_embeddings

        indexer._client = mock_client
        indexer._embedding_model = mock_model

        with patch.object(indexer, "ensure_collection"):
            result = await indexer.index_documents(nodes, batch_size=2)

        assert result == 5
        # Should call upsert 3 times (batches of 2, 2, 1)
        assert mock_client.upsert.call_count == 3

    @pytest.mark.asyncio
    async def test_delete_collection_success(self, settings):
        """Test successful deletion of collection."""
        indexer = QdrantIndexer(settings)
        mock_client = MagicMock()
        indexer._client = mock_client

        await indexer.delete_collection()

        mock_client.delete_collection.assert_called_once_with(
            collection_name="test_collection"
        )


class TestOpenSearchIndexer:
    """Test suite for OpenSearchIndexer class."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            opensearch_host="localhost",
            opensearch_port=9200,
            opensearch_index="test_index",
            opensearch_user="admin",
            opensearch_password="admin",
        )

    @pytest.fixture
    def sample_nodes(self):
        """Create sample legal nodes for testing."""
        return [
            LegalNode(
                id="doc-1",
                title="Test Document 1",
                content="Content of document 1",
                doc_type=DocumentType.LAW,
                level=0,
                publish_date=date(2020, 1, 1),
                effective_date=date(2020, 7, 1),
                issuing_body="Test Body",
                document_number="01/2020",
                keywords=["test", "law"],
                parent_id="parent-1",
                children_ids=["child-1", "child-2"],
                amendment_refs=["amd-1"],
                citation_refs=["cite-1"],
            ),
        ]

    @pytest.mark.asyncio
    async def test_get_client_creates_new_client(self, settings):
        """Test that _get_client creates a new OpenSearch client when none exists."""
        indexer = OpenSearchIndexer(settings)
        mock_client = MagicMock()

        with patch("opensearchpy.OpenSearch", return_value=mock_client):
            client = await indexer._get_client()

        assert client is mock_client
        assert indexer._client is mock_client

    @pytest.mark.asyncio
    async def test_get_client_returns_cached_client(self, settings):
        """Test that _get_client returns cached client if already created."""
        indexer = OpenSearchIndexer(settings)
        mock_client = MagicMock()
        indexer._client = mock_client

        with patch("opensearchpy.OpenSearch") as mock_constructor:
            client = await indexer._get_client()
            mock_constructor.assert_not_called()

        assert client is mock_client

    @pytest.mark.asyncio
    async def test_get_client_import_error(self, settings):
        """Test handling of ImportError when opensearch-py not installed."""
        indexer = OpenSearchIndexer(settings)

        with patch("opensearchpy.OpenSearch", side_effect=ImportError("No module named 'opensearchpy'")):
            with pytest.raises(ImportError):
                await indexer._get_client()

    @pytest.mark.asyncio
    async def test_ensure_index_creates_new_index(self, settings):
        """Test that ensure_index creates index if it doesn't exist."""
        indexer = OpenSearchIndexer(settings)
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = False

        indexer._client = mock_client

        await indexer.ensure_index()

        mock_client.indices.create.assert_called_once()
        call_args = mock_client.indices.create.call_args
        assert call_args[1]["index"] == "test_index"

    @pytest.mark.asyncio
    async def test_ensure_index_skips_existing(self, settings):
        """Test that ensure_index skips if index already exists."""
        indexer = OpenSearchIndexer(settings)
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = True

        indexer._client = mock_client

        await indexer.ensure_index()

        mock_client.indices.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_index_documents_empty_list(self, settings):
        """Test that index_documents returns 0 for empty list."""
        indexer = OpenSearchIndexer(settings)
        result = await indexer.index_documents([])
        assert result == 0

    @pytest.mark.asyncio
    async def test_index_documents_success(self, settings, sample_nodes):
        """Test successful indexing of documents."""
        indexer = OpenSearchIndexer(settings)
        mock_client = MagicMock()
        indexer._client = mock_client

        # Mock bulk helper
        mock_bulk_result = (1, [])  # 1 success, 0 errors

        with patch.object(indexer, "ensure_index") as mock_ensure, \
             patch("opensearchpy.helpers.bulk", return_value=mock_bulk_result):
            result = await indexer.index_documents(sample_nodes)

        assert result == 1
        mock_ensure.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_documents_with_errors(self, settings, sample_nodes):
        """Test indexing with some document errors."""
        indexer = OpenSearchIndexer(settings)
        mock_client = MagicMock()
        indexer._client = mock_client

        # Mock bulk helper with errors
        mock_bulk_result = (0, [{"error": "test error"}])

        with patch.object(indexer, "ensure_index"), \
             patch("opensearchpy.helpers.bulk", return_value=mock_bulk_result):
            result = await indexer.index_documents(sample_nodes)

        assert result == 0

    @pytest.mark.asyncio
    async def test_delete_index_success(self, settings):
        """Test successful deletion of index."""
        indexer = OpenSearchIndexer(settings)
        mock_client = MagicMock()
        indexer._client = mock_client

        await indexer.delete_index()

        mock_client.indices.delete.assert_called_once_with(
            index="test_index", ignore=[404]
        )


class TestDocumentIndexer:
    """Test suite for DocumentIndexer class."""

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
            embedding_model="test-model",
            embedding_dim=768,
        )

    @pytest.fixture
    def sample_nodes(self):
        """Create sample legal nodes for testing."""
        return [
            LegalNode(
                id="doc-1",
                title="Test Document 1",
                content="Content of document 1",
                doc_type=DocumentType.LAW,
                level=0,
            ),
            LegalNode(
                id="doc-2",
                title="Test Document 2",
                content="Content of document 2",
                doc_type=DocumentType.DECREE,
                level=1,
            ),
        ]

    def test_init_with_settings(self, settings):
        """Test initialization with provided settings."""
        indexer = DocumentIndexer(settings)
        assert indexer.settings is settings
        assert indexer.qdrant_indexer is not None
        assert indexer.opensearch_indexer is not None

    def test_init_without_settings(self):
        """Test initialization without settings loads from environment."""
        with patch("packages.common.config.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings
            indexer = DocumentIndexer()
            mock_get_settings.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_empty_list(self, settings):
        """Test that index returns empty result for empty list."""
        indexer = DocumentIndexer(settings)
        result = await indexer.index([])

        assert result["total_documents"] == 0
        assert result["qdrant_indexed"] == 0
        assert result["opensearch_indexed"] == 0
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_index_success(self, settings, sample_nodes):
        """Test successful indexing to both backends."""
        indexer = DocumentIndexer(settings)

        with patch.object(indexer.qdrant_indexer, "index_documents", return_value=2) as mock_qdrant, \
             patch.object(indexer.opensearch_indexer, "index_documents", return_value=2) as mock_opensearch:
            result = await indexer.index(sample_nodes)

        assert result["total_documents"] == 2
        assert result["qdrant_indexed"] == 2
        assert result["opensearch_indexed"] == 2
        assert result["errors"] == []
        mock_qdrant.assert_called_once_with(sample_nodes, relationship_metadata=None)
        mock_opensearch.assert_called_once_with(sample_nodes, relationship_metadata=None)

    @pytest.mark.asyncio
    async def test_index_qdrant_failure(self, settings, sample_nodes):
        """Test indexing when Qdrant fails but OpenSearch succeeds."""
        indexer = DocumentIndexer(settings)

        with patch.object(indexer.qdrant_indexer, "index_documents", side_effect=Exception("Qdrant error")) as mock_qdrant, \
             patch.object(indexer.opensearch_indexer, "index_documents", return_value=2) as mock_opensearch:
            result = await indexer.index(sample_nodes)

        assert result["total_documents"] == 2
        assert result["qdrant_indexed"] == 0
        assert result["opensearch_indexed"] == 2
        assert len(result["errors"]) == 1
        assert "Qdrant" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_index_opensearch_failure(self, settings, sample_nodes):
        """Test indexing when OpenSearch fails but Qdrant succeeds."""
        indexer = DocumentIndexer(settings)

        with patch.object(indexer.qdrant_indexer, "index_documents", return_value=2) as mock_qdrant, \
             patch.object(indexer.opensearch_indexer, "index_documents", side_effect=Exception("OpenSearch error")) as mock_opensearch:
            result = await indexer.index(sample_nodes)

        assert result["total_documents"] == 2
        assert result["qdrant_indexed"] == 2
        assert result["opensearch_indexed"] == 0
        assert len(result["errors"]) == 1
        assert "OpenSearch" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_index_both_failures(self, settings, sample_nodes):
        """Test indexing when both backends fail."""
        indexer = DocumentIndexer(settings)

        with patch.object(indexer.qdrant_indexer, "index_documents", side_effect=Exception("Qdrant error")), \
             patch.object(indexer.opensearch_indexer, "index_documents", side_effect=Exception("OpenSearch error")):
            result = await indexer.index(sample_nodes)

        assert result["total_documents"] == 2
        assert result["qdrant_indexed"] == 0
        assert result["opensearch_indexed"] == 0
        assert len(result["errors"]) == 2

    @pytest.mark.asyncio
    async def test_index_legal_corpus_alias(self, settings, sample_nodes):
        """Test that index_legal_corpus is an alias for index."""
        indexer = DocumentIndexer(settings)

        with patch.object(indexer, "index", return_value={"total_documents": 2}) as mock_index:
            result = await indexer.index_legal_corpus(sample_nodes)

        mock_index.assert_called_once_with(sample_nodes)
        assert result["total_documents"] == 2

    @pytest.mark.asyncio
    async def test_delete_empty_list(self, settings):
        """Test that delete returns empty result for empty list."""
        indexer = DocumentIndexer(settings)
        result = await indexer.delete([])

        assert result["total_documents"] == 0
        assert result["qdrant_deleted"] == 0
        assert result["opensearch_deleted"] == 0
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_delete_success(self, settings):
        """Test successful deletion from both backends."""
        indexer = DocumentIndexer(settings)
        doc_ids = ["doc-1", "doc-2"]

        mock_qdrant_client = MagicMock()
        mock_collections = MagicMock()
        mock_collection = MagicMock()
        mock_collection.name = "test_collection"
        mock_collections.collections = [mock_collection]
        mock_qdrant_client.get_collections.return_value = mock_collections

        mock_opensearch_client = MagicMock()
        mock_opensearch_client.indices.exists.return_value = True

        with patch.object(indexer.qdrant_indexer, "_get_client", return_value=mock_qdrant_client), \
             patch.object(indexer.opensearch_indexer, "_get_client", return_value=mock_opensearch_client), \
             patch("opensearchpy.helpers.bulk", return_value=(2, [])):
            result = await indexer.delete(doc_ids)

        assert result["total_documents"] == 2
        assert result["qdrant_deleted"] == 2
        assert result["opensearch_deleted"] == 2

    @pytest.mark.asyncio
    async def test_delete_qdrant_failure(self, settings):
        """Test deletion when Qdrant fails."""
        indexer = DocumentIndexer(settings)
        doc_ids = ["doc-1"]

        with patch.object(indexer.qdrant_indexer, "_get_client", side_effect=Exception("Qdrant error")):
            result = await indexer.delete(doc_ids)

        assert result["total_documents"] == 1
        assert len(result["errors"]) == 1
        assert "Qdrant" in result["errors"][0]
