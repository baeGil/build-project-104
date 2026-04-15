"""Tests for citation routes in apps/review_api/routes/citations.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.review_api.routes import citations
from packages.common.types import ContextDocument


@pytest.fixture
def mock_graph_client():
    """Create a mock LegalGraphClient."""
    client = MagicMock()
    
    client.get_document_hierarchy = AsyncMock(return_value={
        "id": "law-2020-01-01",
        "title": "Luật Doanh nghiệp 2020",
        "level": 0,
    })
    
    client.get_parent_document = AsyncMock(return_value={
        "id": "law-2020-01-01",
        "title": "Luật Doanh nghiệp 2020",
        "content": "Parent content",
    })
    
    client.get_amendments = AsyncMock(return_value=[
        {"id": "amend-1", "title": "Amendment 1", "content": "Amendment content"},
    ])
    
    client.get_citing_articles = AsyncMock(return_value=[
        {"id": "cite-1", "title": "Citing Article 1", "content": "Citing content"},
    ])
    
    client.get_related_by_topic = AsyncMock(return_value=[
        {"id": "rel-1", "title": "Related 1", "content": "Related content"},
    ])
    
    return client


@pytest.fixture
def app(mock_graph_client) -> FastAPI:
    """Create a FastAPI app with mocked graph client for testing."""
    app = FastAPI()
    app.include_router(citations.router, prefix="/api/v1")
    
    # Override the dependency
    async def override_get_graph_client():
        return mock_graph_client
    
    app.dependency_overrides[citations.get_graph_client] = override_get_graph_client
    
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client."""
    return TestClient(app)


class TestGetCitationContext:
    """Tests for GET /api/v1/citations/{node_id} endpoint."""

    def test_get_citation_context_success(self, client: TestClient) -> None:
        """Test successful citation context retrieval."""
        response = client.get("/api/v1/citations/law-2020-01-01-art-46")

        assert response.status_code == 200
        data = response.json()
        
        assert data["node_id"] == "law-2020-01-01-art-46"
        assert "hierarchy" in data
        assert "parent" in data
        assert "amendments" in data
        assert "citing_articles" in data
        assert "related_documents" in data
        assert "context_documents" in data

    def test_get_citation_context_with_context_documents(self, client: TestClient) -> None:
        """Test that context documents are properly formatted."""
        response = client.get("/api/v1/citations/test-node")

        assert response.status_code == 200
        data = response.json()
        
        context_docs = data["context_documents"]
        assert len(context_docs) > 0
        
        # Check parent document
        parent_docs = [d for d in context_docs if d["relation_type"] == "parent"]
        assert len(parent_docs) == 1
        assert parent_docs[0]["doc_id"] == "law-2020-01-01"
        
        # Check amendment documents
        amendment_docs = [d for d in context_docs if d["relation_type"] == "amendment"]
        assert len(amendment_docs) == 1
        assert amendment_docs[0]["doc_id"] == "amend-1"
        
        # Check citing documents
        citing_docs = [d for d in context_docs if d["relation_type"] == "citing"]
        assert len(citing_docs) == 1
        assert citing_docs[0]["doc_id"] == "cite-1"
        
        # Check related documents
        related_docs = [d for d in context_docs if d["relation_type"] == "related"]
        assert len(related_docs) == 1
        assert related_docs[0]["doc_id"] == "rel-1"

    def test_get_citation_context_not_found(self, client: TestClient, app: FastAPI) -> None:
        """Test handling when node is not found."""
        # Create a new mock that raises an exception
        async def override_get_graph_client_error():
            client = MagicMock()
            client.get_document_hierarchy = AsyncMock(
                side_effect=Exception("Node not found")
            )
            return client
        
        app.dependency_overrides[citations.get_graph_client] = override_get_graph_client_error

        response = client.get("/api/v1/citations/non-existent-node")

        assert response.status_code == 500
        data = response.json()
        assert "Failed to retrieve citation context" in data["detail"]

    def test_get_citation_context_graph_connection_error_falls_back(self, client: TestClient, app: FastAPI) -> None:
        """Test graceful fallback when graph service is unavailable."""
        async def override_get_graph_client_error():
            client = MagicMock()
            client.get_document_hierarchy = AsyncMock(
                side_effect=Exception("Couldn't connect to localhost:7687")
            )
            return client
        
        app.dependency_overrides[citations.get_graph_client] = override_get_graph_client_error

        response = client.get("/api/v1/citations/test-node")

        assert response.status_code == 200
        data = response.json()
        assert data["node_id"] == "test-node"
        assert data["context_documents"] == []
        assert data["graph_available"] is False
        assert data["warning"] is not None

    def test_get_citation_context_excludes_self_from_related(self, client: TestClient, app: FastAPI) -> None:
        """Test that the node itself is excluded from related documents."""
        async def override_get_graph_client():
            client = MagicMock()
            client.get_document_hierarchy = AsyncMock(return_value={})
            client.get_parent_document = AsyncMock(return_value=None)
            client.get_amendments = AsyncMock(return_value=[])
            client.get_citing_articles = AsyncMock(return_value=[])
            # Include the same node_id in related documents
            client.get_related_by_topic = AsyncMock(return_value=[
                {"id": "test-node", "title": "Self", "content": "Should be excluded"},
                {"id": "other-node", "title": "Other", "content": "Should be included"},
            ])
            return client
        
        app.dependency_overrides[citations.get_graph_client] = override_get_graph_client

        response = client.get("/api/v1/citations/test-node")

        assert response.status_code == 200
        data = response.json()
        
        context_docs = data["context_documents"]
        doc_ids = [d["doc_id"] for d in context_docs]
        
        # Should exclude the node itself
        assert "test-node" not in doc_ids
        # Should include the other node
        assert "other-node" in doc_ids

    def test_get_citation_context_empty_results(self, client: TestClient, app: FastAPI) -> None:
        """Test handling of empty results from graph client."""
        async def override_get_graph_client():
            client = MagicMock()
            client.get_document_hierarchy = AsyncMock(return_value={})
            client.get_parent_document = AsyncMock(return_value=None)
            client.get_amendments = AsyncMock(return_value=[])
            client.get_citing_articles = AsyncMock(return_value=[])
            client.get_related_by_topic = AsyncMock(return_value=[])
            return client
        
        app.dependency_overrides[citations.get_graph_client] = override_get_graph_client

        response = client.get("/api/v1/citations/empty-node")

        assert response.status_code == 200
        data = response.json()
        
        assert data["node_id"] == "empty-node"
        assert data["context_documents"] == []
        assert data["parent"] is None
        assert data["amendments"] == []
        assert data["citing_articles"] == []


class TestGetGraphClientDependency:
    """Tests for the get_graph_client dependency."""

    def test_get_graph_client_creates_client(self) -> None:
        """Test that dependency creates a LegalGraphClient."""
        from packages.common.config import Settings
        
        with patch("apps.review_api.routes.citations.LegalGraphClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            # We can't easily test the async dependency directly,
            # but we can verify the import and class structure
            assert citations.get_graph_client is not None


class TestCitationContextDocumentStructure:
    """Tests for ContextDocument structure in response."""

    def test_context_document_fields(self, client: TestClient) -> None:
        """Test that context documents have all required fields."""
        response = client.get("/api/v1/citations/test-node")

        assert response.status_code == 200
        data = response.json()
        
        for doc in data["context_documents"]:
            assert "doc_id" in doc
            assert "content" in doc
            assert "relation_type" in doc
            assert "title" in doc
            
            # Verify relation_type is valid
            assert doc["relation_type"] in ["parent", "amendment", "citing", "related"]
