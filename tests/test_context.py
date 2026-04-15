"""Tests for context injection in packages/retrieval/context.py."""

from datetime import date
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from packages.common.config import Settings
from packages.common.types import RetrievedDocument, ContextDocument
from packages.retrieval.context import ContextInjector


class TestContextInjector:
    """Test suite for ContextInjector class."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="password",
        )

    @pytest.fixture
    def sample_retrieved_docs(self):
        """Create sample retrieved documents."""
        return [
            RetrievedDocument(
                doc_id="doc-1",
                content="Content of document 1",
                title="Document 1",
                score=0.95,
                metadata={
                    "doc_type": "luat",
                    "parent_id": "parent-1",
                    "parent_title": "Parent Document",
                    "article_number": "46",
                    "sibling_refs": ["sibling-1", "sibling-2"],
                    "amendment_refs": ["amd-1"],
                    "citation_refs": ["cite-1", "cite-2"],
                },
            ),
            RetrievedDocument(
                doc_id="doc-2",
                content="Content of document 2",
                title="Document 2",
                score=0.85,
                metadata={
                    "doc_type": "nghi_dinh",
                    "parent_id": "parent-2",
                },
            ),
        ]

    @pytest.mark.asyncio
    async def test_inject_context_empty_list(self, settings):
        """Test inject_context with empty document list."""
        injector = ContextInjector(settings)
        result = await injector.inject_context([])
        assert result == []

    @pytest.mark.asyncio
    async def test_inject_context_single_document(self, settings, sample_retrieved_docs):
        """Test inject_context with single document."""
        injector = ContextInjector(settings)

        with patch.object(injector, "_fetch_parent_context", return_value=None), \
             patch.object(injector, "_fetch_sibling_exceptions", return_value=[]), \
             patch.object(injector, "_fetch_amendments", return_value=[]), \
             patch.object(injector, "_fetch_related_articles", return_value=[]):
            result = await injector.inject_context([sample_retrieved_docs[0]], top_k=1)

        assert result == []

    @pytest.mark.asyncio
    async def test_inject_context_multiple_documents(self, settings, sample_retrieved_docs):
        """Test inject_context with multiple documents."""
        injector = ContextInjector(settings)

        # Different parents for each document to avoid deduplication
        parent_context_1 = ContextDocument(
            doc_id="parent-1",
            content="Parent content 1",
            relation_type="parent",
            title="Parent Document 1",
        )
        parent_context_2 = ContextDocument(
            doc_id="parent-2",
            content="Parent content 2",
            relation_type="parent",
            title="Parent Document 2",
        )

        call_count = 0
        async def mock_parent_fetch(doc):
            nonlocal call_count
            call_count += 1
            return parent_context_1 if call_count == 1 else parent_context_2

        with patch.object(injector, "_fetch_parent_context", side_effect=mock_parent_fetch), \
             patch.object(injector, "_fetch_sibling_exceptions", return_value=[]), \
             patch.object(injector, "_fetch_amendments", return_value=[]), \
             patch.object(injector, "_fetch_related_articles", return_value=[]):
            result = await injector.inject_context(sample_retrieved_docs, top_k=2)

        assert len(result) == 2  # One parent for each document (different IDs)
        assert result[0].doc_id == "parent-1"
        assert result[1].doc_id == "parent-2"
        assert result[0].relation_type == "parent"

    @pytest.mark.asyncio
    async def test_inject_context_deduplication(self, settings, sample_retrieved_docs):
        """Test that inject_context deduplicates by doc_id."""
        injector = ContextInjector(settings)

        # Same context for both documents
        shared_context = ContextDocument(
            doc_id="shared-1",
            content="Shared content",
            relation_type="related",
        )

        with patch.object(injector, "_fetch_parent_context", return_value=None), \
             patch.object(injector, "_fetch_sibling_exceptions", return_value=[shared_context]), \
             patch.object(injector, "_fetch_amendments", return_value=[]), \
             patch.object(injector, "_fetch_related_articles", return_value=[]):
            result = await injector.inject_context(sample_retrieved_docs, top_k=2)

        # Should be deduplicated to single entry
        assert len(result) == 1
        assert result[0].doc_id == "shared-1"

    @pytest.mark.asyncio
    async def test_inject_context_with_top_k_limit(self, settings, sample_retrieved_docs):
        """Test that top_k limits documents processed."""
        injector = ContextInjector(settings)

        call_count = 0
        async def mock_fetch(*args):
            nonlocal call_count
            call_count += 1
            return None

        with patch.object(injector, "_fetch_parent_context", side_effect=mock_fetch), \
             patch.object(injector, "_fetch_sibling_exceptions", return_value=[]), \
             patch.object(injector, "_fetch_amendments", return_value=[]), \
             patch.object(injector, "_fetch_related_articles", return_value=[]):
            await injector.inject_context(sample_retrieved_docs, top_k=1)

        # Should only process first document due to top_k=1
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_fetch_parent_context_with_neo4j(self, settings):
        """Test fetching parent context using Neo4j."""
        injector = ContextInjector(settings)

        mock_graph_client = AsyncMock()
        mock_graph_client.get_parent_document.return_value = {
            "id": "parent-1",
            "content": "Parent content",
            "title": "Parent Title",
        }
        injector._graph_client = mock_graph_client

        doc = RetrievedDocument(
            doc_id="doc-1",
            content="Content",
            title="Title",
            score=0.9,
        )

        result = await injector._fetch_parent_context(doc)

        assert result is not None
        assert result.doc_id == "parent-1"
        assert result.relation_type == "parent"
        assert result.title == "Parent Title"

    @pytest.mark.asyncio
    async def test_fetch_parent_context_with_metadata_fallback(self, settings):
        """Test fetching parent context using metadata fallback."""
        injector = ContextInjector(settings)
        # No graph client
        injector._graph_client = None

        doc = RetrievedDocument(
            doc_id="doc-1",
            content="Content",
            title="Title",
            score=0.9,
            metadata={"parent_id": "parent-1", "parent_title": "Parent Title"},
        )

        result = await injector._fetch_parent_context(doc)

        assert result is not None
        assert result.doc_id == "parent-1"
        assert result.relation_type == "parent"
        assert result.title == "Parent Title"

    @pytest.mark.asyncio
    async def test_fetch_parent_context_no_parent(self, settings):
        """Test fetching parent context when no parent exists."""
        injector = ContextInjector(settings)
        injector._graph_client = None

        doc = RetrievedDocument(
            doc_id="doc-1",
            content="Content",
            title="Title",
            score=0.9,
            metadata={},  # No parent_id
        )

        result = await injector._fetch_parent_context(doc)

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_parent_context_neo4j_error(self, settings):
        """Test parent context fetch handles Neo4j errors."""
        injector = ContextInjector(settings)

        mock_graph_client = AsyncMock()
        mock_graph_client.get_parent_document.side_effect = Exception("Neo4j error")
        injector._graph_client = mock_graph_client

        doc = RetrievedDocument(
            doc_id="doc-1",
            content="Content",
            title="Title",
            score=0.9,
            metadata={"parent_id": "parent-1"},  # Fallback available
        )

        result = await injector._fetch_parent_context(doc)

        # Should fallback to metadata
        assert result is not None
        assert result.doc_id == "parent-1"

    @pytest.mark.asyncio
    async def test_fetch_sibling_exceptions_with_neo4j(self, settings):
        """Test fetching sibling exceptions using Neo4j."""
        injector = ContextInjector(settings)

        mock_graph_client = AsyncMock()
        mock_graph_client.get_related_by_topic.return_value = [
            {"id": "sibling-1", "content": "Sibling 1 content", "title": "Sibling 1"},
            {"id": "sibling-2", "content": "Sibling 2 content", "title": "Sibling 2"},
        ]
        injector._graph_client = mock_graph_client

        doc = RetrievedDocument(
            doc_id="doc-1",
            content="Content",
            title="Title",
            score=0.9,
            metadata={"article_number": "46", "doc_type": "luat"},
        )

        result = await injector._fetch_sibling_exceptions(doc)

        assert len(result) == 2
        assert result[0].relation_type == "sibling"
        assert result[0].doc_id == "sibling-1"

    @pytest.mark.asyncio
    async def test_fetch_sibling_exceptions_with_metadata_fallback(self, settings):
        """Test fetching sibling exceptions using metadata fallback."""
        injector = ContextInjector(settings)
        injector._graph_client = None

        doc = RetrievedDocument(
            doc_id="doc-1",
            content="Content",
            title="Title",
            score=0.9,
            metadata={"sibling_refs": ["sibling-1", "sibling-2"]},
        )

        result = await injector._fetch_sibling_exceptions(doc)

        assert len(result) == 2
        assert result[0].doc_id == "sibling-1"
        assert result[0].relation_type == "sibling"
        assert result[1].doc_id == "sibling-2"

    @pytest.mark.asyncio
    async def test_fetch_sibling_exceptions_empty(self, settings):
        """Test fetching sibling exceptions when none exist."""
        injector = ContextInjector(settings)
        injector._graph_client = None

        doc = RetrievedDocument(
            doc_id="doc-1",
            content="Content",
            title="Title",
            score=0.9,
            metadata={},  # No sibling_refs
        )

        result = await injector._fetch_sibling_exceptions(doc)

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_sibling_exceptions_neo4j_error(self, settings):
        """Test sibling fetch handles Neo4j errors."""
        injector = ContextInjector(settings)

        mock_graph_client = AsyncMock()
        mock_graph_client.get_related_by_topic.side_effect = Exception("Neo4j error")
        injector._graph_client = mock_graph_client

        doc = RetrievedDocument(
            doc_id="doc-1",
            content="Content",
            title="Title",
            score=0.9,
            metadata={"article_number": "46", "doc_type": "luat", "sibling_refs": ["fallback-sibling"]},
        )

        result = await injector._fetch_sibling_exceptions(doc)

        # Should fallback to metadata
        assert len(result) == 1
        assert result[0].doc_id == "fallback-sibling"

    @pytest.mark.asyncio
    async def test_fetch_amendments_with_neo4j(self, settings):
        """Test fetching amendments using Neo4j."""
        injector = ContextInjector(settings)

        mock_graph_client = AsyncMock()
        mock_graph_client.get_amendments.return_value = [
            {"id": "amd-1", "content": "Amendment 1", "title": "Amendment 1"},
        ]
        injector._graph_client = mock_graph_client

        doc = RetrievedDocument(
            doc_id="doc-1",
            content="Content",
            title="Title",
            score=0.9,
        )

        result = await injector._fetch_amendments(doc)

        assert len(result) == 1
        assert result[0].doc_id == "amd-1"
        assert result[0].relation_type == "amendment"

    @pytest.mark.asyncio
    async def test_fetch_amendments_with_metadata_fallback(self, settings):
        """Test fetching amendments using metadata fallback."""
        injector = ContextInjector(settings)
        injector._graph_client = None

        doc = RetrievedDocument(
            doc_id="doc-1",
            content="Content",
            title="Title",
            score=0.9,
            metadata={"amendment_refs": ["amd-1", "amd-2"]},
        )

        result = await injector._fetch_amendments(doc)

        assert len(result) == 2
        assert result[0].doc_id == "amd-1"
        assert result[0].relation_type == "amendment"
        assert result[1].doc_id == "amd-2"

    @pytest.mark.asyncio
    async def test_fetch_amendments_empty(self, settings):
        """Test fetching amendments when none exist."""
        injector = ContextInjector(settings)
        injector._graph_client = None

        doc = RetrievedDocument(
            doc_id="doc-1",
            content="Content",
            title="Title",
            score=0.9,
            metadata={},  # No amendment_refs
        )

        result = await injector._fetch_amendments(doc)

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_related_articles_with_neo4j(self, settings):
        """Test fetching related articles using Neo4j."""
        injector = ContextInjector(settings)

        mock_graph_client = AsyncMock()
        mock_graph_client.get_citing_articles.return_value = [
            {"id": "cite-1", "content": "Citing article 1", "title": "Article 1"},
            {"id": "cite-2", "content": "Citing article 2", "title": "Article 2"},
        ]
        injector._graph_client = mock_graph_client

        doc = RetrievedDocument(
            doc_id="doc-1",
            content="Content",
            title="Title",
            score=0.9,
        )

        result = await injector._fetch_related_articles(doc)

        assert len(result) == 2
        assert result[0].doc_id == "cite-1"
        assert result[0].relation_type == "related"

    @pytest.mark.asyncio
    async def test_fetch_related_articles_with_metadata_fallback(self, settings):
        """Test fetching related articles using metadata fallback."""
        injector = ContextInjector(settings)
        injector._graph_client = None

        doc = RetrievedDocument(
            doc_id="doc-1",
            content="Content",
            title="Title",
            score=0.9,
            metadata={"citation_refs": ["cite-1", "cite-2", "cite-3"]},
        )

        result = await injector._fetch_related_articles(doc)

        assert len(result) == 3
        assert result[0].doc_id == "cite-1"
        assert result[0].relation_type == "related"

    @pytest.mark.asyncio
    async def test_fetch_related_articles_empty(self, settings):
        """Test fetching related articles when none exist."""
        injector = ContextInjector(settings)
        injector._graph_client = None

        doc = RetrievedDocument(
            doc_id="doc-1",
            content="Content",
            title="Title",
            score=0.9,
            metadata={},  # No citation_refs
        )

        result = await injector._fetch_related_articles(doc)

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_related_articles_neo4j_error(self, settings):
        """Test related articles fetch handles Neo4j errors."""
        injector = ContextInjector(settings)

        mock_graph_client = AsyncMock()
        mock_graph_client.get_citing_articles.side_effect = Exception("Neo4j error")
        injector._graph_client = mock_graph_client

        doc = RetrievedDocument(
            doc_id="doc-1",
            content="Content",
            title="Title",
            score=0.9,
            metadata={"citation_refs": ["fallback-cite"]},
        )

        result = await injector._fetch_related_articles(doc)

        # Should fallback to metadata
        assert len(result) == 1
        assert result[0].doc_id == "fallback-cite"

    @pytest.mark.asyncio
    async def test_full_context_injection_integration(self, settings):
        """Test full context injection with all relation types."""
        injector = ContextInjector(settings)

        parent = ContextDocument(doc_id="parent-1", content="Parent", relation_type="parent")
        sibling = ContextDocument(doc_id="sibling-1", content="Sibling", relation_type="sibling")
        amendment = ContextDocument(doc_id="amd-1", content="Amendment", relation_type="amendment")
        related = ContextDocument(doc_id="cite-1", content="Related", relation_type="related")

        doc = RetrievedDocument(
            doc_id="doc-1",
            content="Content",
            title="Title",
            score=0.9,
        )

        with patch.object(injector, "_fetch_parent_context", return_value=parent), \
             patch.object(injector, "_fetch_sibling_exceptions", return_value=[sibling]), \
             patch.object(injector, "_fetch_amendments", return_value=[amendment]), \
             patch.object(injector, "_fetch_related_articles", return_value=[related]):
            result = await injector.inject_context([doc], top_k=1)

        assert len(result) == 4
        relation_types = {r.relation_type for r in result}
        assert relation_types == {"parent", "sibling", "amendment", "related"}
