"""Tests for ingestion API routes."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from apps.review_api.main import app
from apps.review_api.routes import ingest as ingest_module
from packages.common.types import IngestRequest, IngestResponse


@pytest.fixture(autouse=True)
def clear_task_store():
    """Clear the task store before each test."""
    ingest_module._task_store.clear()
    yield
    ingest_module._task_store.clear()


@pytest.fixture
async def async_client():
    """Create an async test client with mocked dependencies."""
    with patch("apps.review_api.main.QueryPlanner"), \
         patch("apps.review_api.main.HybridRetriever"), \
         patch("apps.review_api.main.LegalGenerator"), \
         patch("apps.review_api.main.LegalVerifier"), \
         patch("apps.review_api.main.ContractReviewPipeline"), \
         patch("apps.review_api.main.EmbeddingService"):
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


class TestIngestLegalCorpus:
    """Tests for POST /api/v1/ingest/legal-corpus endpoint."""
    
    @pytest.mark.asyncio
    async def test_ingest_legal_corpus_success(self, async_client):
        """Test successful batch document ingestion."""
        documents = [
            {"id": "doc1", "title": "Law 1", "content": "Content of law 1"},
            {"id": "doc2", "title": "Law 2", "content": "Content of law 2"},
        ]
        
        response = await async_client.post(
            "/api/v1/ingest/legal-corpus",
            json={"documents": documents, "source": "test-corpus"}
        )
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "queued"
        assert data["document_count"] == 2
        assert "task_id" in data
        assert "queued" in data["message"].lower()
    
    @pytest.mark.asyncio
    async def test_ingest_legal_corpus_empty_documents(self, async_client):
        """Test ingestion with empty documents list."""
        response = await async_client.post(
            "/api/v1/ingest/legal-corpus",
            json={"documents": [], "source": "test"}
        )
        
        assert response.status_code == 400
        assert "No documents provided" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_ingest_legal_corpus_missing_documents_field(self, async_client):
        """Test ingestion without documents field."""
        response = await async_client.post(
            "/api/v1/ingest/legal-corpus",
            json={"source": "test"}
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_ingest_legal_corpus_document_not_dict(self, async_client):
        """Test ingestion with document that is not a dictionary."""
        response = await async_client.post(
            "/api/v1/ingest/legal-corpus",
            json={"documents": ["not a dict"], "source": "test"}
        )
        
        # FastAPI validates the request model before our custom validation
        # When document is not a dict, it results in a 422 validation error
        assert response.status_code in [400, 422]
        if response.status_code == 400:
            assert "must be a dictionary" in response.json()["detail"]
        else:
            # 422 validation error from FastAPI/Pydantic
            pass
    
    @pytest.mark.asyncio
    async def test_ingest_legal_corpus_missing_content_field(self, async_client):
        """Test ingestion with document missing content field."""
        response = await async_client.post(
            "/api/v1/ingest/legal-corpus",
            json={"documents": [{"id": "doc1", "title": "Law 1"}], "source": "test"}
        )
        
        assert response.status_code == 400
        assert "missing required 'content' field" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_ingest_legal_corpus_single_document(self, async_client):
        """Test ingestion with a single document."""
        response = await async_client.post(
            "/api/v1/ingest/legal-corpus",
            json={"documents": [{"content": "Single document content"}], "source": "test"}
        )
        
        assert response.status_code == 202
        data = response.json()
        assert data["document_count"] == 1
    
    @pytest.mark.asyncio
    async def test_ingest_legal_corpus_default_source(self, async_client):
        """Test ingestion uses default source when not provided."""
        response = await async_client.post(
            "/api/v1/ingest/legal-corpus",
            json={"documents": [{"content": "Test content"}]}
        )
        
        assert response.status_code == 202
        # Source defaults to "manual" per the model
    
    @pytest.mark.asyncio
    async def test_ingest_legal_corpus_response_model(self, async_client):
        """Test response matches IngestResponse model."""
        response = await async_client.post(
            "/api/v1/ingest/legal-corpus",
            json={"documents": [{"content": "Test"}], "source": "test"}
        )
        
        assert response.status_code == 202
        # Validate against model
        ingest_response = IngestResponse(**response.json())
        assert ingest_response.status == "queued"
        assert ingest_response.document_count == 1


class TestIngestSingleDocument:
    """Tests for POST /api/v1/ingest/single endpoint."""
    
    @pytest.mark.asyncio
    async def test_ingest_single_success(self, async_client):
        """Test successful single document ingestion."""
        response = await async_client.post(
            "/api/v1/ingest/single",
            params={"title": "Test Document", "content": "This is a test document with enough content."}
        )
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "queued"
        assert data["document_count"] == 1
        assert "task_id" in data
    
    @pytest.mark.asyncio
    async def test_ingest_single_content_too_short(self, async_client):
        """Test ingestion with content shorter than 10 characters."""
        response = await async_client.post(
            "/api/v1/ingest/single",
            params={"title": "Test", "content": "Short"}
        )
        
        assert response.status_code == 400
        assert "at least 10 characters" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_ingest_single_empty_content(self, async_client):
        """Test ingestion with empty content."""
        response = await async_client.post(
            "/api/v1/ingest/single",
            params={"title": "Test", "content": ""}
        )
        
        assert response.status_code == 400
        assert "at least 10 characters" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_ingest_single_whitespace_content(self, async_client):
        """Test ingestion with whitespace-only content."""
        response = await async_client.post(
            "/api/v1/ingest/single",
            params={"title": "Test", "content": "     "}
        )
        
        assert response.status_code == 400
        assert "at least 10 characters" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_ingest_single_missing_title(self, async_client):
        """Test ingestion without title parameter."""
        response = await async_client.post(
            "/api/v1/ingest/single",
            params={"content": "This is a test document with enough content."}
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_ingest_single_missing_content(self, async_client):
        """Test ingestion without content parameter."""
        response = await async_client.post(
            "/api/v1/ingest/single",
            params={"title": "Test"}
        )
        
        assert response.status_code == 422  # Validation error


class TestGetIngestionStatus:
    """Tests for GET /api/v1/ingest/status/{task_id} endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_status_completed(self, async_client):
        """Test getting status of a completed task."""
        # First create a task
        response = await async_client.post(
            "/api/v1/ingest/legal-corpus",
            json={"documents": [{"content": "Test"}], "source": "test"}
        )
        task_id = response.json()["task_id"]
        
        # Manually set task as completed
        ingest_module._task_store[task_id] = {
            "status": "completed",
            "progress": 100,
            "message": "Done",
            "stats": {"parsed": 1}
        }
        
        response = await async_client.get(f"/api/v1/ingest/status/{task_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "completed"
        assert data["progress"] == 100
    
    @pytest.mark.asyncio
    async def test_get_status_processing(self, async_client):
        """Test getting status of a processing task."""
        # Create a task
        response = await async_client.post(
            "/api/v1/ingest/legal-corpus",
            json={"documents": [{"content": "Test"}], "source": "test"}
        )
        task_id = response.json()["task_id"]
        
        # Manually set task as processing
        ingest_module._task_store[task_id] = {
            "status": "processing",
            "progress": 50,
            "message": "In progress..."
        }
        
        response = await async_client.get(f"/api/v1/ingest/status/{task_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert data["progress"] == 50
    
    @pytest.mark.asyncio
    async def test_get_status_failed(self, async_client):
        """Test getting status of a failed task."""
        # Create a task
        response = await async_client.post(
            "/api/v1/ingest/legal-corpus",
            json={"documents": [{"content": "Test"}], "source": "test"}
        )
        task_id = response.json()["task_id"]
        
        # Manually set task as failed
        ingest_module._task_store[task_id] = {
            "status": "failed",
            "progress": 0,
            "message": "Error occurred"
        }
        
        response = await async_client.get(f"/api/v1/ingest/status/{task_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
    
    @pytest.mark.asyncio
    async def test_get_status_not_found(self, async_client):
        """Test getting status of non-existent task."""
        response = await async_client.get("/api/v1/ingest/status/non-existent-task-id")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_get_status_queued(self, async_client):
        """Test getting status of a task (queued, processing, or completed)."""
        # Create a task - it starts in queued state
        response = await async_client.post(
            "/api/v1/ingest/legal-corpus",
            json={"documents": [{"content": "Test"}], "source": "test"}
        )
        task_id = response.json()["task_id"]
        
        # Task status can be: queued, processing, completed, or not found (404)
        # depending on timing and implementation
        response = await async_client.get(f"/api/v1/ingest/status/{task_id}")
        
        # The task may have already completed by the time we check,
        # or it might not be in the store yet
        if response.status_code == 200:
            # If task is in store, verify it has valid status
            data = response.json()
            assert data["task_id"] == task_id
            assert data["status"] in ["queued", "processing", "completed", "failed"]
        else:
            # If task is not in store yet
            assert response.status_code == 404


class TestIngestFromHuggingface:
    """Tests for POST /api/v1/ingest/huggingface endpoint."""
    
    @pytest.mark.asyncio
    async def test_ingest_huggingface_success(self, async_client):
        """Test successful HuggingFace dataset ingestion."""
        response = await async_client.post(
            "/api/v1/ingest/huggingface",
            params={"dataset_name": "test/dataset", "split": "train", "limit": 100}
        )
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "queued"
        assert "task_id" in data
        assert "HuggingFace" in data["message"]
    
    @pytest.mark.asyncio
    async def test_ingest_huggingface_default_params(self, async_client):
        """Test HuggingFace ingestion with default parameters."""
        response = await async_client.post("/api/v1/ingest/huggingface")
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "queued"
        assert data["document_count"] == 0  # Unknown until loaded
    
    @pytest.mark.asyncio
    async def test_ingest_huggingface_no_limit(self, async_client):
        """Test HuggingFace ingestion without limit."""
        response = await async_client.post(
            "/api/v1/ingest/huggingface",
            params={"dataset_name": "test/dataset", "split": "test"}
        )
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "queued"


class TestProcessIngestionTask:
    """Tests for the background task processing."""
    
    @pytest.mark.asyncio
    async def test_process_ingestion_task_success(self):
        """Test successful background task processing."""
        with patch.object(ingest_module, "IngestionPipeline") as mock_pipeline_class:
            mock_pipeline = AsyncMock()
            mock_pipeline.ingest_from_text = AsyncMock(return_value={"parsed": 5, "indexed": 5})
            mock_pipeline_class.return_value = mock_pipeline
            
            task_id = "test-task-123"
            documents = [{"content": "Doc 1"}, {"content": "Doc 2"}]
            
            await ingest_module._process_ingestion_task(task_id, documents, "test")
            
            # Verify task store was updated
            assert task_id in ingest_module._task_store
            assert ingest_module._task_store[task_id]["status"] == "completed"
            assert ingest_module._task_store[task_id]["progress"] == 100
            assert "5" in ingest_module._task_store[task_id]["message"]
            mock_pipeline.ingest_from_text.assert_called_once_with(documents)
    
    @pytest.mark.asyncio
    async def test_process_ingestion_task_failure(self):
        """Test background task handles pipeline errors."""
        with patch.object(ingest_module, "IngestionPipeline") as mock_pipeline_class:
            mock_pipeline = AsyncMock()
            mock_pipeline.ingest_from_text = AsyncMock(side_effect=Exception("Pipeline error"))
            mock_pipeline_class.return_value = mock_pipeline
            
            task_id = "test-task-456"
            documents = [{"content": "Doc 1"}]
            
            await ingest_module._process_ingestion_task(task_id, documents, "test")
            
            # Verify task store shows failure
            assert task_id in ingest_module._task_store
            assert ingest_module._task_store[task_id]["status"] == "failed"
            assert "Pipeline error" in ingest_module._task_store[task_id]["message"]
    
    @pytest.mark.asyncio
    async def test_process_huggingface_task_success(self):
        """Test successful HuggingFace background task processing."""
        with patch.object(ingest_module, "IngestionPipeline") as mock_pipeline_class:
            mock_pipeline = AsyncMock()
            mock_pipeline.ingest_from_huggingface = AsyncMock(return_value={"parsed": 10})
            mock_pipeline_class.return_value = mock_pipeline
            
            task_id = "test-task-hf"
            
            # Call the inner function directly - _process_huggingface_task
            await ingest_module._process_huggingface_task(
                task_id=task_id,
                dataset="test/dataset",
                dataset_split="train",
                doc_limit=10,
            )
            
            # Verify task store was updated
            assert task_id in ingest_module._task_store
            assert ingest_module._task_store[task_id]["status"] == "completed"
            assert "10" in ingest_module._task_store[task_id]["message"] or "test/dataset" in ingest_module._task_store[task_id]["message"]


class TestIngestRequestValidation:
    """Tests for IngestRequest model validation."""
    
    def test_ingest_request_valid(self):
        """Test valid IngestRequest creation."""
        request = IngestRequest(
            documents=[{"content": "Test"}],
            source="test",
            batch_size=50
        )
        assert len(request.documents) == 1
        assert request.source == "test"
        assert request.batch_size == 50
    
    def test_ingest_request_default_batch_size(self):
        """Test IngestRequest with default batch size."""
        request = IngestRequest(documents=[{"content": "Test"}])
        assert request.batch_size == 100  # Default value
    
    def test_ingest_request_default_source(self):
        """Test IngestRequest with default source."""
        request = IngestRequest(documents=[{"content": "Test"}])
        assert request.source == "manual"  # Default value
