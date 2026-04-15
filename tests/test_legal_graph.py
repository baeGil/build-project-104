"""Unit tests for LegalGraphClient with mocked Neo4j async driver."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.common.config import Settings
from packages.common.types import DocumentType, LegalNode
from packages.graph.legal_graph import LegalGraphClient


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for testing."""
    return Settings(
        neo4j_uri="bolt://test:7687",
        neo4j_user="test_user",
        neo4j_password="test_password",
    )


@pytest.fixture
def mock_neo4j_driver():
    """Create a mocked Neo4j AsyncGraphDatabase driver."""
    mock_driver = MagicMock()
    mock_session = AsyncMock()
    mock_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_driver, mock_session


@pytest.fixture
def legal_graph_client(mock_settings) -> LegalGraphClient:
    """Create a LegalGraphClient with mocked settings."""
    return LegalGraphClient(settings=mock_settings)


@pytest.fixture
def sample_legal_node() -> LegalNode:
    """Create a sample legal node for testing."""
    return LegalNode(
        id="law-2020-01-01",
        title="Luật Doanh nghiệp 2020",
        content="Nội dung luật doanh nghiệp...",
        doc_type=DocumentType.LAW,
        level=0,
        publish_date=date(2020, 1, 1),
        effective_date=date(2020, 7, 1),
        issuing_body="Quốc hội",
        document_number="59/2020/QH14",
        keywords=["doanh nghiệp", "công ty"],
    )


class TestDriverLifecycle:
    """Test driver initialization and lifecycle."""

    def test_driver_lazy_initialization(self, legal_graph_client, mock_settings):
        """Test that driver is lazily initialized."""
        assert legal_graph_client._driver is None
        
        mock_driver = MagicMock()
        mock_db_class = MagicMock()
        mock_db_class.driver.return_value = mock_driver
        
        with patch.dict("sys.modules", {"neo4j": MagicMock(AsyncGraphDatabase=mock_db_class)}):
            driver = legal_graph_client.driver
            
            mock_db_class.driver.assert_called_once_with(
                mock_settings.neo4j_uri,
                auth=(mock_settings.neo4j_user, mock_settings.neo4j_password),
            )
            assert legal_graph_client._driver is mock_driver

    def test_driver_lazy_initialization_import_error(self, legal_graph_client):
        """Test driver initialization handles ImportError."""
        # Simulate ImportError by removing neo4j from sys.modules and making import fail
        with patch.dict("sys.modules", {"neo4j": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module named 'neo4j'")):
                with pytest.raises(ImportError):
                    _ = legal_graph_client.driver

    async def test_close_driver(self, legal_graph_client):
        """Test closing the driver connection."""
        mock_driver = AsyncMock()
        legal_graph_client._driver = mock_driver
        
        await legal_graph_client.close()
        
        mock_driver.close.assert_called_once()
        assert legal_graph_client._driver is None

    async def test_close_no_driver(self, legal_graph_client):
        """Test closing when driver was never initialized."""
        assert legal_graph_client._driver is None
        
        # Should not raise any error
        await legal_graph_client.close()
        
        assert legal_graph_client._driver is None


class TestSchemaOperations:
    """Test schema management operations."""

    async def test_create_constraints(self, legal_graph_client, mock_neo4j_driver):
        """Test creating constraints."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        mock_result = AsyncMock()
        mock_session.run.return_value = mock_result
        
        await legal_graph_client.create_constraints()
        
        # Should create 3 constraints
        assert mock_session.run.call_count == 3
        calls = mock_session.run.call_args_list
        
        # Check constraint queries
        assert "CREATE CONSTRAINT document_id" in calls[0][0][0]
        assert "CREATE CONSTRAINT article_id" in calls[1][0][0]
        assert "CREATE CONSTRAINT subsection_id" in calls[2][0][0]

    async def test_create_constraints_handles_errors(self, legal_graph_client, mock_neo4j_driver):
        """Test that constraint creation handles errors gracefully."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        # First call succeeds, second raises exception
        mock_session.run.side_effect = [
            AsyncMock(),
            Exception("Constraint already exists"),
            AsyncMock(),
        ]
        
        # Should not raise exception
        await legal_graph_client.create_constraints()

    async def test_create_indexes(self, legal_graph_client, mock_neo4j_driver):
        """Test creating indexes."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        mock_result = AsyncMock()
        mock_session.run.return_value = mock_result
        
        await legal_graph_client.create_indexes()
        
        # Should create 3 indexes
        assert mock_session.run.call_count == 3
        calls = mock_session.run.call_args_list
        
        # Check index queries
        assert "CREATE INDEX document_year" in calls[0][0][0]
        assert "CREATE INDEX document_type" in calls[1][0][0]
        assert "CREATE INDEX article_number" in calls[2][0][0]


class TestDocumentOperations:
    """Test document CRUD operations."""

    async def test_upsert_document(self, legal_graph_client, mock_neo4j_driver, sample_legal_node):
        """Test upserting a document."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        mock_record = {"id": "law-2020-01-01"}
        mock_result = AsyncMock()
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.upsert_document(sample_legal_node)
        
        assert result == "law-2020-01-01"
        mock_session.run.assert_called_once()
        
        # Check query and params
        call_args = mock_session.run.call_args
        assert "MERGE (d:Document {id: $id})" in call_args[0][0]
        # Params are passed as second positional arg or keyword
        if call_args[1]:
            params = call_args[1].get("parameters") or call_args[0][1] if len(call_args[0]) > 1 else None
        else:
            params = call_args[0][1] if len(call_args[0]) > 1 else None
        
        # Verify query contains expected clauses
        assert "SET d.title" in call_args[0][0]
        assert "RETURN d.id" in call_args[0][0]

    async def test_upsert_document_no_publish_date(self, legal_graph_client, mock_neo4j_driver):
        """Test upserting a document without publish date."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        node = LegalNode(
            id="doc-001",
            title="Test Document",
            content="Test content",
            doc_type=DocumentType.DECREE,
            level=0,
        )
        
        mock_record = {"id": "doc-001"}
        mock_result = AsyncMock()
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.upsert_document(node)
        
        assert result == "doc-001"
        call_args = mock_session.run.call_args
        # Check that query was executed
        assert "MERGE (d:Document" in call_args[0][0]

    async def test_upsert_document_no_record(self, legal_graph_client, mock_neo4j_driver, sample_legal_node):
        """Test upserting a document when no record is returned."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        mock_result = AsyncMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.upsert_document(sample_legal_node)
        
        assert result is None


class TestArticleOperations:
    """Test article CRUD operations."""

    async def test_upsert_article(self, legal_graph_client, mock_neo4j_driver):
        """Test upserting an article."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        mock_record = {"id": "law-2020-art-1"}
        mock_result = AsyncMock()
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.upsert_article(
            doc_id="law-2020-01-01",
            article_id="law-2020-art-1",
            number=1,
            title="Điều 1. Phạm vi điều chỉnh",
            content="Nội dung điều 1...",
        )
        
        assert result == "law-2020-art-1"
        mock_session.run.assert_called_once()
        
        call_args = mock_session.run.call_args
        assert "MERGE (a:Article {id: $article_id})" in call_args[0][0]
        assert "MERGE (d)-[:CONTAINS]->(a)" in call_args[0][0]

    async def test_upsert_article_no_record(self, legal_graph_client, mock_neo4j_driver):
        """Test upserting an article when no record is returned."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        mock_result = AsyncMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.upsert_article(
            doc_id="law-2020-01-01",
            article_id="law-2020-art-1",
            number=1,
            title="Test",
            content="Content",
        )
        
        assert result is None


class TestRelationshipOperations:
    """Test relationship creation operations."""

    async def test_create_amendment_link(self, legal_graph_client, mock_neo4j_driver):
        """Test creating an amendment link."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        mock_record = {"r": MagicMock()}
        mock_result = AsyncMock()
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.create_amendment_link(
            source_id="law-2015-01-01",
            target_id="law-2020-01-01",
            effective_date="2020-07-01",
        )
        
        assert result is True
        call_args = mock_session.run.call_args
        assert "AMENDED_BY" in call_args[0][0]

    async def test_create_amendment_link_no_record(self, legal_graph_client, mock_neo4j_driver):
        """Test creating amendment link when no record is returned."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        mock_result = AsyncMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.create_amendment_link(
            source_id="law-2015-01-01",
            target_id="law-2020-01-01",
        )
        
        assert result is False

    async def test_create_citation_link(self, legal_graph_client, mock_neo4j_driver):
        """Test creating a citation link."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        mock_record = {"r": MagicMock()}
        mock_result = AsyncMock()
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.create_citation_link(
            source_id="art-46",
            target_id="art-45",
        )
        
        assert result is True
        call_args = mock_session.run.call_args
        assert "CITES" in call_args[0][0]

    async def test_create_reference_link(self, legal_graph_client, mock_neo4j_driver):
        """Test creating a reference link."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        mock_record = {"r": MagicMock()}
        mock_result = AsyncMock()
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.create_reference_link(
            source_id="nghi-dinh-01",
            target_id="luat-2020-01",
        )
        
        assert result is True
        call_args = mock_session.run.call_args
        assert "REFERENCES" in call_args[0][0]


class TestQueryOperations:
    """Test query operations."""

    async def test_get_parent_document(self, legal_graph_client, mock_neo4j_driver):
        """Test getting parent document of an article."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        mock_record = {
            "id": "law-2020-01-01",
            "title": "Luật Doanh nghiệp 2020",
            "content": "Nội dung luật...",
            "doc_type": "luat",
        }
        mock_result = AsyncMock()
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.get_parent_document("art-46")
        
        assert result is not None
        assert result["id"] == "law-2020-01-01"
        assert result["title"] == "Luật Doanh nghiệp 2020"
        mock_session.run.assert_called_once()

    async def test_get_parent_document_not_found(self, legal_graph_client, mock_neo4j_driver):
        """Test getting parent document when not found."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        mock_result = AsyncMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.get_parent_document("non-existent")
        
        assert result is None

    async def test_get_amendments(self, legal_graph_client, mock_neo4j_driver):
        """Test getting amendment chain."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        records = [
            {"id": "law-2020-01", "title": "Law 2020", "content": "Content", "year": 2020, "depth": 1},
            {"id": "law-2025-01", "title": "Law 2025", "content": "Content", "year": 2025, "depth": 2},
        ]
        
        # Create proper async iterator mock
        async def async_iterator():
            for record in records:
                yield record
        
        mock_result = async_iterator()
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.get_amendments("law-2015-01", max_depth=2)
        
        assert len(result) == 2
        assert result[0]["id"] == "law-2020-01"
        assert result[0]["depth"] == 1
        assert result[1]["depth"] == 2

    async def test_get_amendments_empty(self, legal_graph_client, mock_neo4j_driver):
        """Test getting amendments when none exist."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        async def async_iterator():
            return
            yield  # Make it a generator
        
        mock_result = async_iterator()
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.get_amendments("law-2015-01")
        
        assert result == []

    async def test_get_citing_articles(self, legal_graph_client, mock_neo4j_driver):
        """Test getting articles that cite a given article."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        records = [
            {"id": "art-47", "title": "Article 47", "content": "Content 47"},
            {"id": "art-48", "title": "Article 48", "content": "Content 48"},
        ]
        
        async def async_iterator():
            for record in records:
                yield record
        
        mock_result = async_iterator()
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.get_citing_articles("art-46")
        
        assert len(result) == 2
        assert result[0]["id"] == "art-47"
        assert "LIMIT 10" in mock_session.run.call_args[0][0]

    async def test_get_related_by_topic(self, legal_graph_client, mock_neo4j_driver):
        """Test getting related documents by topic."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        records = [
            {"id": "doc-2", "title": "Doc 2", "content": "Content", "doc_type": "nghi_dinh", "distance": 1},
            {"id": "doc-3", "title": "Doc 3", "content": "Content", "doc_type": "thong_tu", "distance": 2},
        ]
        
        async def async_iterator():
            for record in records:
                yield record
        
        mock_result = async_iterator()
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.get_related_by_topic("doc-1", max_hops=2)
        
        assert len(result) == 2
        assert result[0]["distance"] == 1
        assert result[1]["distance"] == 2

    async def test_get_document_hierarchy(self, legal_graph_client, mock_neo4j_driver):
        """Test getting document hierarchy."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        mock_record = {
            "doc_id": "law-2020-01",
            "doc_title": "Luật Doanh nghiệp",
            "articles": [
                {"id": "art-1", "number": 1, "title": "Article 1", "subsections": []},
            ],
        }
        mock_result = AsyncMock()
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.get_document_hierarchy("law-2020-01")
        
        assert result["id"] == "law-2020-01"
        assert result["title"] == "Luật Doanh nghiệp"
        assert len(result["articles"]) == 1

    async def test_get_document_hierarchy_not_found(self, legal_graph_client, mock_neo4j_driver):
        """Test getting hierarchy when document not found."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        mock_result = AsyncMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.get_document_hierarchy("non-existent")
        
        assert result["id"] == "non-existent"
        assert result["title"] is None
        assert result["articles"] == []


class TestGraphAugmentedSearch:
    """Test GraphRAG search functionality."""

    async def test_graph_augmented_search(self, legal_graph_client, mock_neo4j_driver):
        """Test graph augmented search."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        records = [
            {
                "id": "doc-2",
                "title": "Related Doc",
                "content": "Content",
                "doc_type": "nghi_dinh",
                "distance": 1,
                "seed_count": 2,
            },
        ]
        
        async def async_iterator():
            for record in records:
                yield record
        
        mock_result = async_iterator()
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.graph_augmented_search(
            seed_doc_ids=["doc-1", "doc-3"],
            max_hops=2,
            max_results=10,
        )
        
        assert len(result) == 1
        assert result[0]["id"] == "doc-2"
        assert result[0]["seed_count"] == 2

    async def test_graph_augmented_search_empty_seeds(self, legal_graph_client, mock_neo4j_driver):
        """Test graph augmented search with empty seeds."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        async def async_iterator():
            return
            yield
        
        mock_result = async_iterator()
        mock_session.run.return_value = mock_result
        
        result = await legal_graph_client.graph_augmented_search(seed_doc_ids=[])
        
        assert result == []


class TestErrorHandling:
    """Test error handling scenarios."""

    async def test_session_run_error(self, legal_graph_client, mock_neo4j_driver):
        """Test handling of session run errors."""
        mock_driver, mock_session = mock_neo4j_driver
        legal_graph_client._driver = mock_driver
        
        mock_session.run.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            await legal_graph_client.get_parent_document("art-1")

    async def test_driver_initialization_error(self, legal_graph_client):
        """Test driver initialization error handling."""
        mock_db_class = MagicMock()
        mock_db_class.driver.side_effect = Exception("Connection refused")
        
        with patch.dict("sys.modules", {"neo4j": MagicMock(AsyncGraphDatabase=mock_db_class)}):
            with pytest.raises(Exception, match="Connection refused"):
                _ = legal_graph_client.driver
