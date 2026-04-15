"""Tests for chat routes in apps/review_api/routes/chat.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.review_api.routes import chat
from packages.common.types import (
    ChatAnswer,
    ChatRequest,
    QueryPlan,
    QueryStrategy,
    RetrievedDocument,
)


@pytest.fixture
def mock_app_state():
    """Create a mock app state with all required components."""
    state = MagicMock()
    
    # Mock planner
    state.query_planner = MagicMock()
    state.query_planner.plan = Mock(return_value=QueryPlan(
        original_query="test query",
        normalized_query="test query",
        strategy=QueryStrategy.SEMANTIC,
    ))
    
    # Mock retriever
    state.hybrid_retriever = MagicMock()
    state.hybrid_retriever.search = AsyncMock(return_value=[{
        "id": "doc-1",
        "content": "Test content",
        "title": "Test Document",
        "score": 0.95,
        "metadata": {"law_id": "law-2020"},
    }])
    
    # Mock generator
    state.legal_generator = MagicMock()
    state.legal_generator.generate_chat_answer = AsyncMock(return_value=ChatAnswer(
        answer="Test answer",
        citations=[],
        confidence=0.95,
    ))
    
    async def mock_stream(query, evidence_pack):
        yield "Hello "
        yield "world"
        yield "!"
    
    state.legal_generator.stream_chat_answer = mock_stream
    
    return state


@pytest.fixture
def app(mock_app_state) -> FastAPI:
    """Create a FastAPI app with mocked state for testing."""
    app = FastAPI()
    app.include_router(chat.router, prefix="/api/v1")
    app.state = mock_app_state
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client."""
    return TestClient(app)


class TestLegalChat:
    """Tests for POST /api/v1/chat/legal endpoint."""

    def test_legal_chat_success(self, client: TestClient) -> None:
        """Test successful legal chat request."""
        response = client.post(
            "/api/v1/chat/legal",
            json={"query": "What is an LLC?"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Test answer"
        assert data["confidence"] == 0.95

    def test_legal_chat_with_filters(self, client: TestClient) -> None:
        """Test legal chat with filters."""
        response = client.post(
            "/api/v1/chat/legal",
            json={
                "query": "What is an LLC?",
                "filters": {"doc_type": "luat"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data

    def test_legal_chat_missing_query(self, client: TestClient) -> None:
        """Test legal chat with missing query field."""
        response = client.post(
            "/api/v1/chat/legal",
            json={},
        )

        assert response.status_code == 422  # Validation error

    def test_legal_chat_empty_query(self, client: TestClient) -> None:
        """Test legal chat with empty query."""
        response = client.post(
            "/api/v1/chat/legal",
            json={"query": ""},
        )

        assert response.status_code == 422  # Validation error

    def test_legal_chat_error_handling(self, client: TestClient, app: FastAPI) -> None:
        """Test error handling in legal chat."""
        app.state.query_planner.plan = Mock(
            side_effect=Exception("Planner error")
        )

        response = client.post(
            "/api/v1/chat/legal",
            json={"query": "Test query?"},
        )

        assert response.status_code == 500
        data = response.json()
        assert "Chat processing failed" in data["detail"]

    def test_legal_chat_uses_app_state_components(self, client: TestClient, app: FastAPI) -> None:
        """Test that endpoint uses components from app.state."""
        response = client.post(
            "/api/v1/chat/legal",
            json={"query": "Test?"},
        )

        assert response.status_code == 200
        # Verify app.state components were used
        app.state.query_planner.plan.assert_called_once()
        app.state.hybrid_retriever.search.assert_called_once()
        app.state.legal_generator.generate_chat_answer.assert_called_once()

    def test_legal_chat_accepts_retrieved_document_models(self, client: TestClient, app: FastAPI) -> None:
        """Test chat endpoint with real RetrievedDocument model outputs."""
        app.state.hybrid_retriever.search = AsyncMock(return_value=[
            RetrievedDocument(
                doc_id="doc-123",
                content="Nội dung pháp lý mẫu",
                title="Điều 1",
                score=0.91,
                metadata={"law_id": "law-123"},
            )
        ])

        response = client.post(
            "/api/v1/chat/legal",
            json={"query": "Test with model output?"},
        )

        assert response.status_code == 200
        app.state.legal_generator.generate_chat_answer.assert_called_once()


class TestLegalChatStream:
    """Tests for POST /api/v1/chat/legal/stream endpoint."""

    def test_legal_chat_stream_success(self, client: TestClient) -> None:
        """Test successful streaming chat request."""
        response = client.post(
            "/api/v1/chat/legal/stream",
            json={"query": "What is an LLC?"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        # Read SSE events
        content = response.content.decode("utf-8")
        assert "data: Hello " in content
        assert "data: world" in content
        assert "data: !" in content
        assert "data: [DONE]" in content

    def test_legal_chat_stream_includes_citations(self, client: TestClient) -> None:
        """Test that streaming includes citations before [DONE]."""
        response = client.post(
            "/api/v1/chat/legal/stream",
            json={"query": "Test?"},
        )

        content = response.content.decode("utf-8")
        # Check for citations marker
        assert "[CITATIONS]" in content
        assert "data: [DONE]" in content

    def test_legal_chat_stream_sse_format(self, client: TestClient) -> None:
        """Test SSE format with proper line endings."""
        response = client.post(
            "/api/v1/chat/legal/stream",
            json={"query": "Test?"},
        )

        content = response.content.decode("utf-8")
        # Each event should end with \n\n
        lines = content.split("\n\n")
        # Filter out empty strings
        events = [line for line in lines if line.strip()]
        
        # Each event should start with "data: "
        for event in events:
            if event.strip():
                assert event.startswith("data: ")

    def test_legal_chat_stream_headers(self, client: TestClient) -> None:
        """Test streaming response headers."""
        response = client.post(
            "/api/v1/chat/legal/stream",
            json={"query": "Test?"},
        )

        assert response.headers["Cache-Control"] == "no-cache"
        assert response.headers["Connection"] == "keep-alive"
        assert response.headers["X-Accel-Buffering"] == "no"

    def test_legal_chat_stream_accepts_retrieved_document_models(self, client: TestClient, app: FastAPI) -> None:
        """Test streaming chat endpoint with real RetrievedDocument model outputs."""
        app.state.hybrid_retriever.search = AsyncMock(return_value=[
            RetrievedDocument(
                doc_id="doc-123",
                content="Nội dung pháp lý mẫu",
                title="Điều 1",
                score=0.91,
                metadata={"law_id": "law-123"},
            )
        ])

        response = client.post(
            "/api/v1/chat/legal/stream",
            json={"query": "Test stream with model output?"},
        )

        assert response.status_code == 200

    def test_legal_chat_stream_error_handling(self, client: TestClient, app: FastAPI) -> None:
        """Test error handling in streaming chat."""
        app.state.query_planner.plan = Mock(
            side_effect=Exception("Planner error")
        )

        response = client.post(
            "/api/v1/chat/legal/stream",
            json={"query": "Test query?"},
        )

        assert response.status_code == 500
        data = response.json()
        assert "Chat streaming failed" in data["detail"]

    def test_legal_chat_stream_missing_query(self, client: TestClient) -> None:
        """Test streaming chat with missing query."""
        response = client.post(
            "/api/v1/chat/legal/stream",
            json={},
        )

        assert response.status_code == 422  # Validation error


class TestChatRequestValidation:
    """Tests for ChatRequest model validation."""

    def test_chat_request_min_length(self) -> None:
        """Test that query must be at least 1 character."""
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            ChatRequest(query="")

    def test_chat_request_valid(self) -> None:
        """Test valid chat request creation."""
        request = ChatRequest(query="Valid question?")
        assert request.query == "Valid question?"
        assert request.session_id is None
        assert request.filters == {}

    def test_chat_request_with_optional_fields(self) -> None:
        """Test chat request with all fields."""
        request = ChatRequest(
            query="Test?",
            session_id="session-123",
            filters={"doc_type": "luat"},
        )
        assert request.session_id == "session-123"
        assert request.filters == {"doc_type": "luat"}
