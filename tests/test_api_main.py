"""Tests for FastAPI main application."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from apps.review_api.main import app, lifespan
from packages.common.types import HealthResponse


@pytest.fixture
def mock_app_state():
    """Create a mock app state with all required attributes."""
    state = MagicMock()
    
    # Mock hybrid_retriever
    mock_retriever = AsyncMock()
    mock_qdrant_client = AsyncMock()
    mock_qdrant_client.get_collections = AsyncMock()
    mock_opensearch_client = AsyncMock()
    mock_opensearch_client.cluster = MagicMock()
    mock_opensearch_client.cluster.health = AsyncMock(return_value={"status": "green"})
    mock_postgres_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)
    mock_postgres_pool.acquire = MagicMock()
    mock_postgres_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_postgres_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    
    mock_retriever._get_qdrant_client = AsyncMock(return_value=mock_qdrant_client)
    mock_retriever._get_opensearch_client = AsyncMock(return_value=mock_opensearch_client)
    mock_retriever._get_postgres_pool = AsyncMock(return_value=mock_postgres_pool)
    mock_retriever.close = AsyncMock()
    
    state.hybrid_retriever = mock_retriever
    state.graph_client = AsyncMock()
    state.graph_client.ping = AsyncMock(return_value=True)
    state.graph_client.ensure_schema = AsyncMock()
    state.graph_client.close = AsyncMock()
    return state


@pytest.fixture
async def async_client(mock_app_state):
    """Create an async test client with mocked app state."""
    mock_redis_client = AsyncMock()
    mock_redis_client.ping = AsyncMock(return_value=True)
    mock_redis_client.aclose = AsyncMock()
    mock_redis_module = SimpleNamespace(from_url=MagicMock(return_value=mock_redis_client))

    # Mock the lifespan to avoid actual startup
    with patch("apps.review_api.main.QueryPlanner") as mock_planner, \
         patch("apps.review_api.main.HybridRetriever") as mock_hybrid, \
         patch("apps.review_api.main.LegalGenerator") as mock_generator, \
         patch("apps.review_api.main.LegalVerifier") as mock_verifier, \
         patch("apps.review_api.main.ContractReviewPipeline") as mock_pipeline, \
         patch("apps.review_api.main.EmbeddingService") as mock_embedding, \
         patch("apps.review_api.main.LegalGraphClient") as mock_graph, \
         patch("apps.review_api.main.GraphSyncService") as mock_graph_sync, \
         patch("apps.review_api.main.ContextInjector") as mock_context, \
         patch.dict("sys.modules", {"redis": SimpleNamespace(asyncio=mock_redis_module), "redis.asyncio": mock_redis_module}):
        
        # Configure mocks
        mock_planner.return_value = MagicMock()
        mock_hybrid.return_value = mock_app_state.hybrid_retriever
        mock_generator.return_value = MagicMock()
        mock_verifier.return_value = MagicMock()
        mock_pipeline_instance = MagicMock()
        mock_pipeline_instance.retriever = mock_app_state.hybrid_retriever
        mock_pipeline.return_value = mock_pipeline_instance
        mock_graph.return_value = mock_app_state.graph_client
        mock_graph_sync.return_value = MagicMock()
        mock_context.return_value = MagicMock()
        mock_embedding.get_instance.return_value = MagicMock()
        mock_embedding.get_instance.return_value._load_model = MagicMock()
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


class TestRootEndpoint:
    """Tests for the root endpoint."""
    
    def test_root_endpoint_sync(self, mock_app_state):
        """Test root endpoint returns API info (sync)."""
        with patch("apps.review_api.main.QueryPlanner") as mock_planner, \
             patch("apps.review_api.main.HybridRetriever") as mock_hybrid, \
             patch("apps.review_api.main.LegalGenerator") as mock_generator, \
             patch("apps.review_api.main.LegalVerifier") as mock_verifier, \
             patch("apps.review_api.main.ContractReviewPipeline") as mock_pipeline, \
             patch("apps.review_api.main.EmbeddingService") as mock_embedding, \
             patch("apps.review_api.main.LegalGraphClient") as mock_graph, \
             patch("apps.review_api.main.GraphSyncService") as mock_graph_sync, \
             patch("apps.review_api.main.ContextInjector") as mock_context:
            mock_planner.return_value = MagicMock()
            mock_hybrid.return_value = mock_app_state.hybrid_retriever
            mock_generator.return_value = MagicMock()
            mock_verifier.return_value = MagicMock()
            mock_pipeline_instance = MagicMock()
            mock_pipeline_instance.retriever = mock_app_state.hybrid_retriever
            mock_pipeline.return_value = mock_pipeline_instance
            mock_embedding.get_instance.return_value = MagicMock()
            mock_graph.return_value = mock_app_state.graph_client
            mock_graph_sync.return_value = MagicMock()
            mock_context.return_value = MagicMock()

            with TestClient(app) as client:
                response = client.get("/")

                assert response.status_code == 200
                data = response.json()
                assert data["name"] == "Vietnamese Legal Contract Review API"
                assert data["version"] == "0.1.0"
                assert data["docs"] == "/docs"
    
    @pytest.mark.asyncio
    async def test_root_endpoint_async(self, async_client):
        """Test root endpoint returns API info (async)."""
        response = await async_client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Vietnamese Legal Contract Review API"
        assert data["version"] == "0.1.0"
        assert data["docs"] == "/docs"
    
    @pytest.mark.asyncio
    async def test_root_endpoint_method_not_allowed(self, async_client):
        """Test root endpoint rejects non-GET methods."""
        response = await async_client.post("/")
        assert response.status_code == 405
        
        response = await async_client.put("/")
        assert response.status_code == 405
        
        response = await async_client.delete("/")
        assert response.status_code == 405


class TestHealthEndpoint:
    """Tests for the health check endpoint."""
    
    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self, async_client, mock_app_state):
        """Test health check when all services are healthy."""
        # Set up the mock retriever on app.state
        app.state.hybrid_retriever = mock_app_state.hybrid_retriever
        app.state.graph_client = mock_app_state.graph_client
        
        response = await async_client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"
        assert "services" in data
        assert data["services"]["api"] == "ok"
        assert data["services"]["qdrant"] == "ok"
        assert data["services"]["opensearch"] == "green"
        assert data["services"]["postgres"] == "ok"
        assert data["services"]["neo4j"] == "ok"
    
    @pytest.mark.asyncio
    async def test_health_check_qdrant_unhealthy(self, async_client, mock_app_state):
        """Test health check when Qdrant is unhealthy."""
        # Make Qdrant fail
        mock_app_state.hybrid_retriever._get_qdrant_client.side_effect = Exception("Connection refused")
        app.state.hybrid_retriever = mock_app_state.hybrid_retriever
        app.state.graph_client = mock_app_state.graph_client
        
        response = await async_client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["qdrant"] == "unhealthy"
    
    @pytest.mark.asyncio
    async def test_health_check_opensearch_unhealthy(self, async_client, mock_app_state):
        """Test health check when OpenSearch is unhealthy."""
        # Make OpenSearch fail
        mock_app_state.hybrid_retriever._get_opensearch_client.side_effect = Exception("Connection refused")
        app.state.hybrid_retriever = mock_app_state.hybrid_retriever
        app.state.graph_client = mock_app_state.graph_client
        
        response = await async_client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["opensearch"] == "unhealthy"
    
    @pytest.mark.asyncio
    async def test_health_check_postgres_unhealthy(self, async_client, mock_app_state):
        """Test health check when PostgreSQL is unhealthy."""
        # Make PostgreSQL fail
        mock_app_state.hybrid_retriever._get_postgres_pool.side_effect = Exception("Connection refused")
        app.state.hybrid_retriever = mock_app_state.hybrid_retriever
        app.state.graph_client = mock_app_state.graph_client
        
        response = await async_client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["postgres"] == "unhealthy"
    
    @pytest.mark.asyncio
    async def test_health_check_no_retriever(self, async_client):
        """Test health check when retriever is not available."""
        app.state.hybrid_retriever = None
        app.state.graph_client = None
        
        response = await async_client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["qdrant"] == "unavailable"
        assert data["services"]["opensearch"] == "unavailable"
        assert data["services"]["postgres"] == "unavailable"
        assert data["services"]["neo4j"] == "unavailable"
    
    @pytest.mark.asyncio
    async def test_health_check_opensearch_yellow_status(self, async_client, mock_app_state):
        """Test health check treats yellow OpenSearch as healthy."""
        mock_opensearch_client = AsyncMock()
        mock_opensearch_client.cluster = MagicMock()
        mock_opensearch_client.cluster.health = AsyncMock(return_value={"status": "yellow"})
        mock_app_state.hybrid_retriever._get_opensearch_client = AsyncMock(return_value=mock_opensearch_client)
        app.state.hybrid_retriever = mock_app_state.hybrid_retriever
        app.state.graph_client = mock_app_state.graph_client
        
        response = await async_client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["services"]["opensearch"] == "yellow"
        # Yellow is considered healthy
        assert data["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_health_check_response_model(self, async_client, mock_app_state):
        """Test health check response matches HealthResponse model."""
        app.state.hybrid_retriever = mock_app_state.hybrid_retriever
        app.state.graph_client = mock_app_state.graph_client
        
        response = await async_client.get("/api/v1/health")
        
        assert response.status_code == 200
        # Validate against model
        health_response = HealthResponse(**response.json())
        assert health_response.status in ["ok", "degraded"]
        assert health_response.version == "0.1.0"
        assert isinstance(health_response.services, dict)


class TestLifespan:
    """Tests for application lifespan."""
    
    @pytest.mark.asyncio
    async def test_lifespan_startup_shutdown(self):
        """Test lifespan context manager initializes and cleans up properly."""
        mock_app = MagicMock()
        
        with patch("apps.review_api.main.QueryPlanner") as mock_planner, \
             patch("apps.review_api.main.HybridRetriever") as mock_hybrid, \
             patch("apps.review_api.main.LegalGenerator") as mock_generator, \
             patch("apps.review_api.main.LegalVerifier") as mock_verifier, \
             patch("apps.review_api.main.ContractReviewPipeline") as mock_pipeline, \
             patch("apps.review_api.main.EmbeddingService") as mock_embedding, \
             patch("apps.review_api.main.LegalGraphClient") as mock_graph, \
             patch("apps.review_api.main.GraphSyncService") as mock_graph_sync, \
             patch("apps.review_api.main.ContextInjector") as mock_context:
            
            # Configure mocks
            mock_planner.return_value = MagicMock()
            mock_hybrid_retriever = AsyncMock()
            mock_hybrid_retriever._get_qdrant_client = AsyncMock(return_value=AsyncMock())
            mock_hybrid_retriever._get_opensearch_client = AsyncMock(return_value=AsyncMock())
            mock_hybrid_retriever._get_postgres_pool = AsyncMock(return_value=AsyncMock())
            mock_hybrid_retriever.close = AsyncMock()
            mock_hybrid.return_value = mock_hybrid_retriever
            
            mock_generator.return_value = MagicMock()
            mock_verifier.return_value = MagicMock()
            mock_pipeline_instance = MagicMock()
            mock_pipeline_instance.retriever = mock_hybrid_retriever
            mock_pipeline.return_value = mock_pipeline_instance
            mock_graph_client = AsyncMock()
            mock_graph_client.ping = AsyncMock(return_value=True)
            mock_graph_client.ensure_schema = AsyncMock()
            mock_graph_client.close = AsyncMock()
            mock_graph.return_value = mock_graph_client
            mock_graph_sync.return_value = MagicMock(close=AsyncMock())
            mock_context.return_value = MagicMock()
            
            mock_embedding_service = MagicMock()
            mock_embedding_service._load_model = MagicMock()
            mock_embedding.get_instance.return_value = mock_embedding_service
            
            # Test startup
            async with lifespan(mock_app):
                # Verify state was set
                assert mock_app.state.settings is not None
                assert mock_app.state.query_planner is not None
                assert mock_app.state.hybrid_retriever is not None
                assert mock_app.state.legal_generator is not None
                assert mock_app.state.legal_verifier is not None
                assert mock_app.state.review_pipeline is not None
                assert mock_app.state.graph_client is not None
                assert mock_app.state.graph_sync is not None
                assert mock_app.state.context_injector is not None
                assert mock_app.state.embedding_service is not None
                
                # Verify pipeline connections
                assert mock_app.state.review_pipeline.retriever == mock_app.state.hybrid_retriever
                assert mock_app.state.review_pipeline.generator == mock_app.state.legal_generator
                assert mock_app.state.review_pipeline.verifier == mock_app.state.legal_verifier
            
            # After exit, verify cleanup was attempted
            mock_hybrid_retriever.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_lifespan_startup_with_warmup_errors(self):
        """Test lifespan handles warmup errors gracefully."""
        mock_app = MagicMock()
        
        with patch("apps.review_api.main.QueryPlanner") as mock_planner, \
             patch("apps.review_api.main.HybridRetriever") as mock_hybrid, \
             patch("apps.review_api.main.LegalGenerator") as mock_generator, \
             patch("apps.review_api.main.LegalVerifier") as mock_verifier, \
             patch("apps.review_api.main.ContractReviewPipeline") as mock_pipeline, \
             patch("apps.review_api.main.EmbeddingService") as mock_embedding:
            
            mock_planner.return_value = MagicMock()
            mock_hybrid_retriever = AsyncMock()
            # Simulate warmup errors
            mock_hybrid_retriever._get_qdrant_client = AsyncMock(side_effect=Exception("Qdrant connection failed"))
            mock_hybrid_retriever._get_opensearch_client = AsyncMock(side_effect=Exception("OpenSearch connection failed"))
            mock_hybrid_retriever._get_postgres_pool = AsyncMock(side_effect=Exception("PostgreSQL connection failed"))
            mock_hybrid.return_value = mock_hybrid_retriever
            mock_generator.return_value = MagicMock()
            mock_verifier.return_value = MagicMock()
            mock_pipeline_instance = MagicMock()
            mock_pipeline_instance.retriever = mock_hybrid_retriever
            mock_pipeline.return_value = mock_pipeline_instance
            mock_embedding.get_instance.return_value = MagicMock()
            
            # Should not raise despite errors
            async with lifespan(mock_app):
                pass  # Startup completed despite errors


class TestAppConfiguration:
    """Tests for FastAPI app configuration."""
    
    def test_app_metadata(self):
        """Test FastAPI app has correct metadata."""
        from apps.review_api.main import app
        
        assert app.title == "Vietnamese Legal Contract Review API"
        assert "AI-powered legal contract review" in app.description
        assert app.version == "0.1.0"
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"
    
    def test_app_routers_registered(self):
        """Test all routers are registered with correct prefixes."""
        from apps.review_api.main import app
        
        routes = [route.path for route in app.routes]
        
        # Check that our endpoints are registered
        assert any("/api/v1/ingest" in route for route in routes)
        assert any("/api/v1/review" in route for route in routes)
        assert any("/api/v1/chat" in route for route in routes)
        assert any("/api/v1/citations" in route for route in routes)
        assert "/api/v1/health" in routes
        assert "/" in routes
    
    def test_cors_middleware_configured(self):
        """Test CORS middleware is configured."""
        from apps.review_api.main import app
        
        # Check that middleware is registered - middleware is wrapped in starlette.middleware.Middleware
        # with the actual class in the `cls` attribute
        middleware_classes = [str(m.cls) for m in app.user_middleware]
        assert any("CORSMiddleware" in cls for cls in middleware_classes)
    
    def test_timing_middleware_configured(self):
        """Test TimingMiddleware is configured."""
        from apps.review_api.main import app
        
        # Check that middleware is registered - middleware is wrapped in starlette.middleware.Middleware
        middleware_classes = [str(m.cls) for m in app.user_middleware]
        assert any("TimingMiddleware" in cls for cls in middleware_classes)
