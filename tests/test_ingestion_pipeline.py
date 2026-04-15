"""Tests for ingestion pipeline in packages/ingestion/pipeline.py."""

from datetime import date
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from packages.common.config import Settings
from packages.common.types import LegalNode, DocumentType
from packages.ingestion.pipeline import IngestionPipeline


class TestIngestionPipeline:
    """Test suite for IngestionPipeline class."""

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
    def sample_node(self):
        """Create a sample legal node."""
        return LegalNode(
            id="test-doc-1",
            title="Test Document",
            content="Normalized test content",
            doc_type=DocumentType.LAW,
            level=0,
            publish_date=date(2020, 1, 1),
            issuing_body="Test Body",
            document_number="01/2020",
        )

    @pytest.mark.asyncio
    async def test_ingest_single_document_success(self, settings, sample_node):
        """Test successful ingestion of a single document."""
        pipeline = IngestionPipeline(settings)

        with patch("packages.ingestion.pipeline.normalize_legal_text", return_value="normalized content") as mock_normalize, \
             patch("packages.ingestion.pipeline.parse_legal_document", return_value=sample_node) as mock_parse, \
             patch.object(pipeline.indexer, "index", return_value={"qdrant_indexed": 1}) as mock_index:
            result = await pipeline.ingest_single_document("Test Title", "Raw content")

        assert result is sample_node
        mock_normalize.assert_called_once_with("Raw content")
        mock_parse.assert_called_once_with("normalized content", "Test Title")
        mock_index.assert_called_once_with([sample_node])

    @pytest.mark.asyncio
    async def test_ingest_single_document_empty_content(self, settings):
        """Test ingestion with empty content still processes."""
        pipeline = IngestionPipeline(settings)
        sample_node = LegalNode(
            id="empty-doc",
            title="Empty",
            content="",
            doc_type=DocumentType.OTHER,
            level=0,
        )

        with patch("packages.ingestion.pipeline.normalize_legal_text", return_value=""), \
             patch("packages.ingestion.pipeline.parse_legal_document", return_value=sample_node), \
             patch.object(pipeline.indexer, "index", return_value={"qdrant_indexed": 1}):
            result = await pipeline.ingest_single_document("Empty", "")

        assert result.id == "empty-doc"

    @pytest.mark.asyncio
    async def test_ingest_from_text_success(self, settings, sample_node):
        """Test successful ingestion from text documents."""
        pipeline = IngestionPipeline(settings)
        documents = [
            {"title": "Doc 1", "content": "Content 1"},
            {"title": "Doc 2", "content": "Content 2"},
        ]

        with patch("packages.ingestion.pipeline.normalize_legal_text", return_value="normalized") as mock_normalize, \
             patch("packages.ingestion.pipeline.parse_legal_document", return_value=sample_node) as mock_parse, \
             patch.object(pipeline.indexer, "index", return_value={"qdrant_indexed": 2, "opensearch_indexed": 2}) as mock_index:
            result = await pipeline.ingest_from_text(documents)

        assert result["total"] == 2
        assert result["normalized"] == 2
        assert result["parsed"] == 2
        assert result["indexed"] == 2
        assert result["qdrant_count"] == 2
        assert result["opensearch_count"] == 2
        assert len(result["errors"]) == 0
        assert len(result["document_ids"]) == 2

    @pytest.mark.asyncio
    async def test_ingest_from_text_with_empty_documents(self, settings, sample_node):
        """Test ingestion skips empty documents."""
        pipeline = IngestionPipeline(settings)
        documents = [
            {"title": "Doc 1", "content": "Content 1"},
            {"title": "Doc 2", "content": ""},  # Empty content
            {"title": "Doc 3", "content": "Content 3"},
        ]

        with patch("packages.ingestion.pipeline.normalize_legal_text", return_value="normalized"), \
             patch("packages.ingestion.pipeline.parse_legal_document", return_value=sample_node), \
             patch.object(pipeline.indexer, "index", return_value={"qdrant_indexed": 2}):
            result = await pipeline.ingest_from_text(documents)

        assert result["total"] == 3
        assert result["normalized"] == 2  # One skipped
        assert result["parsed"] == 2

    @pytest.mark.asyncio
    async def test_ingest_from_text_missing_title(self, settings, sample_node):
        """Test ingestion handles missing title."""
        pipeline = IngestionPipeline(settings)
        documents = [{"content": "Content without title"}]

        with patch("packages.ingestion.pipeline.normalize_legal_text", return_value="normalized"), \
             patch("packages.ingestion.pipeline.parse_legal_document", return_value=sample_node), \
             patch.object(pipeline.indexer, "index", return_value={"qdrant_indexed": 1}):
            result = await pipeline.ingest_from_text(documents)

        assert result["total"] == 1
        assert result["parsed"] == 1

    @pytest.mark.asyncio
    async def test_ingest_from_text_parse_error(self, settings):
        """Test ingestion handles parse errors gracefully."""
        pipeline = IngestionPipeline(settings)
        documents = [
            {"title": "Doc 1", "content": "Content 1"},
            {"title": "Doc 2", "content": "Content 2"},
        ]

        def side_effect(content, title):
            if title == "Doc 1":
                raise ValueError("Parse error")
            return LegalNode(
                id="doc-2",
                title=title,
                content=content,
                doc_type=DocumentType.LAW,
                level=0,
            )

        with patch("packages.ingestion.pipeline.normalize_legal_text", return_value="normalized"), \
             patch("packages.ingestion.pipeline.parse_legal_document", side_effect=side_effect), \
             patch.object(pipeline.indexer, "index", return_value={"qdrant_indexed": 1}):
            result = await pipeline.ingest_from_text(documents)

        assert result["total"] == 2
        assert result["normalized"] == 2
        assert result["parsed"] == 1
        assert len(result["errors"]) == 1
        assert "Doc 1" in result["errors"][0] or "0" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_ingest_from_text_index_error(self, settings, sample_node):
        """Test ingestion handles indexing errors."""
        pipeline = IngestionPipeline(settings)
        documents = [{"title": "Doc 1", "content": "Content 1"}]

        with patch("packages.ingestion.pipeline.normalize_legal_text", return_value="normalized"), \
             patch("packages.ingestion.pipeline.parse_legal_document", return_value=sample_node), \
             patch.object(pipeline.indexer, "index", side_effect=Exception("Index failed")):
            result = await pipeline.ingest_from_text(documents)

        assert result["total"] == 1
        assert result["parsed"] == 1
        assert result["indexed"] == 0
        assert len(result["errors"]) == 1
        assert "Indexing failed" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_ingest_from_file_success(self, settings, sample_node, tmp_path):
        """Test successful ingestion from file."""
        pipeline = IngestionPipeline(settings)

        # Create a temporary file
        test_file = tmp_path / "test_document.txt"
        test_file.write_text("File content here", encoding="utf-8")

        with patch("packages.ingestion.pipeline.normalize_legal_text", return_value="normalized"), \
             patch("packages.ingestion.pipeline.parse_legal_document", return_value=sample_node), \
             patch.object(pipeline.indexer, "index", return_value={"qdrant_indexed": 1}):
            result = await pipeline.ingest_from_file(str(test_file))

        assert result is sample_node

    @pytest.mark.asyncio
    async def test_ingest_from_file_with_custom_title(self, settings, sample_node, tmp_path):
        """Test ingestion from file with custom title."""
        pipeline = IngestionPipeline(settings)

        test_file = tmp_path / "test_document.txt"
        test_file.write_text("File content", encoding="utf-8")

        with patch("packages.ingestion.pipeline.normalize_legal_text", return_value="normalized"), \
             patch("packages.ingestion.pipeline.parse_legal_document") as mock_parse, \
             patch.object(pipeline.indexer, "index", return_value={"qdrant_indexed": 1}):
            await pipeline.ingest_from_file(str(test_file), title="Custom Title")

        mock_parse.assert_called_once_with("normalized", "Custom Title")

    @pytest.mark.asyncio
    async def test_ingest_from_file_uses_filename_as_title(self, settings, sample_node, tmp_path):
        """Test that filename is used as title when not provided."""
        pipeline = IngestionPipeline(settings)

        test_file = tmp_path / "my_document.txt"
        test_file.write_text("File content", encoding="utf-8")

        with patch("packages.ingestion.pipeline.normalize_legal_text", return_value="normalized"), \
             patch("packages.ingestion.pipeline.parse_legal_document") as mock_parse, \
             patch.object(pipeline.indexer, "index", return_value={"qdrant_indexed": 1}):
            await pipeline.ingest_from_file(str(test_file))

        mock_parse.assert_called_once_with("normalized", "my_document.txt")

    @pytest.mark.asyncio
    async def test_ingest_batch_success(self, settings, sample_node):
        """Test successful batch ingestion."""
        pipeline = IngestionPipeline(settings)
        documents = [
            {"title": f"Doc {i}", "content": f"Content {i}"}
            for i in range(5)
        ]

        with patch("packages.ingestion.pipeline.normalize_legal_text", return_value="normalized"), \
             patch("packages.ingestion.pipeline.parse_legal_document", return_value=sample_node), \
             patch.object(pipeline.indexer, "index", return_value={"qdrant_indexed": 2}):
            result = await pipeline.ingest_batch(documents, batch_size=2)

        assert result["total"] == 5
        assert result["processed"] == 5
        assert result["failed"] == 0
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_ingest_batch_with_errors(self, settings):
        """Test batch ingestion handles errors in batches."""
        pipeline = IngestionPipeline(settings)
        documents = [
            {"title": f"Doc {i}", "content": f"Content {i}"}
            for i in range(4)
        ]

        call_count = 0
        async def mock_ingest_from_text(docs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Batch failed")
            return {"parsed": len(docs), "errors": []}

        with patch.object(pipeline, "ingest_from_text", side_effect=mock_ingest_from_text):
            result = await pipeline.ingest_batch(documents, batch_size=2)

        assert result["total"] == 4
        assert result["processed"] == 2  # Only second batch succeeded
        assert result["failed"] == 2
        assert len(result["errors"]) == 1
        assert "Batch 1 failed" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_ingest_batch_with_partial_failures(self, settings, sample_node):
        """Test batch ingestion with partial failures within batches."""
        pipeline = IngestionPipeline(settings)
        documents = [
            {"title": f"Doc {i}", "content": f"Content {i}"}
            for i in range(4)
        ]

        async def mock_ingest_from_text(docs):
            return {"parsed": len(docs) - 1, "errors": ["One error"]}

        with patch.object(pipeline, "ingest_from_text", side_effect=mock_ingest_from_text):
            result = await pipeline.ingest_batch(documents, batch_size=2)

        assert result["total"] == 4
        assert result["processed"] == 2  # 2 batches, 1 success each
        assert result["failed"] == 2
        assert len(result["errors"]) == 2

    @pytest.mark.asyncio
    async def test_ingest_batch_empty_documents(self, settings):
        """Test batch ingestion with empty document list."""
        pipeline = IngestionPipeline(settings)
        result = await pipeline.ingest_batch([], batch_size=10)

        assert result["total"] == 0
        assert result["processed"] == 0
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_ingest_from_huggingface_success(self, settings, sample_node):
        """Test ingestion from HuggingFace dataset."""
        pipeline = IngestionPipeline(settings)

        # Mock dataset items
        mock_items = [
            {"title": "Doc 1", "content": "Content 1"},
            {"title": "Doc 2", "content": "Content 2"},
        ]

        mock_dataset = iter(mock_items)

        with patch("datasets.load_dataset") as mock_load_dataset, \
             patch("packages.ingestion.pipeline.normalize_legal_text", return_value="normalized"), \
             patch("packages.ingestion.pipeline.parse_legal_document", return_value=sample_node), \
             patch.object(pipeline.indexer, "index", return_value={"qdrant_indexed": 2}):
            mock_load_dataset.return_value = mock_dataset
            result = await pipeline.ingest_from_huggingface("test/dataset", limit=2)

        assert result["source"] == "test/dataset"
        assert result["total_loaded"] == 2
        assert result["normalized"] == 2
        assert result["parsed"] == 2
        assert result["indexed"] == 2

    @pytest.mark.asyncio
    async def test_ingest_from_huggingface_load_error(self, settings):
        """Test handling when dataset loading fails."""
        pipeline = IngestionPipeline(settings)

        with patch("datasets.load_dataset", side_effect=Exception("Dataset load failed")):
            result = await pipeline.ingest_from_huggingface("test/dataset")

        assert result["source"] == "test/dataset"
        assert len(result["errors"]) == 1
        assert "Failed to load or process dataset" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_ingest_from_huggingface_with_limit(self, settings, sample_node):
        """Test ingestion with limit parameter."""
        pipeline = IngestionPipeline(settings)

        mock_items = [{"title": f"Doc {i}", "content": f"Content {i}"} for i in range(10)]

        with patch("datasets.load_dataset") as mock_load_dataset, \
             patch("packages.ingestion.pipeline.normalize_legal_text", return_value="normalized"), \
             patch("packages.ingestion.pipeline.parse_legal_document", return_value=sample_node), \
             patch.object(pipeline.indexer, "index", return_value={"qdrant_indexed": 5}):
            mock_load_dataset.return_value = iter(mock_items)
            result = await pipeline.ingest_from_huggingface("test/dataset", limit=5)

        assert result["total_loaded"] == 5
        assert result["parsed"] == 5

    @pytest.mark.asyncio
    async def test_ingest_from_huggingface_empty_content(self, settings, sample_node):
        """Test ingestion skips empty content from dataset."""
        pipeline = IngestionPipeline(settings)

        mock_items = [
            {"title": "Doc 1", "content": "Content 1"},
            {"title": "Doc 2", "content": ""},  # Empty
            {"title": "Doc 3", "content": "Content 3"},
        ]

        with patch("datasets.load_dataset") as mock_load_dataset, \
             patch("packages.ingestion.pipeline.normalize_legal_text", return_value="normalized"), \
             patch("packages.ingestion.pipeline.parse_legal_document", return_value=sample_node), \
             patch.object(pipeline.indexer, "index", return_value={"qdrant_indexed": 2}):
            mock_load_dataset.return_value = iter(mock_items)
            result = await pipeline.ingest_from_huggingface("test/dataset")

        assert result["total_loaded"] == 2  # One skipped due to empty content
        assert result["parsed"] == 2
