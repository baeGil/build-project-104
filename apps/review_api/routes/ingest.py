"""Ingestion routes for legal corpus documents."""
import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from packages.common.config import get_settings
from packages.common.types import IngestRequest, IngestResponse
from packages.ingestion.pipeline import IngestionPipeline

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ingestion"])

# Store for background task status (in production, use Redis)
_task_store: dict[str, dict[str, Any]] = {}


async def _process_ingestion_task(task_id: str, documents: list[dict[str, Any]], source: str) -> None:
    """Background task to process document ingestion.

    Args:
        task_id: Unique task identifier.
        documents: List of documents to ingest.
        source: Source identifier for the documents.
    """
    try:
        _task_store[task_id] = {
            "status": "processing",
            "progress": 0,
            "message": "Starting ingestion...",
        }

        pipeline = IngestionPipeline()
        try:
            stats = await pipeline.ingest_from_text(documents)
        finally:
            await pipeline.close()

        _task_store[task_id] = {
            "status": "completed",
            "progress": 100,
            "message": f"Successfully ingested {stats.get('parsed', 0)} documents",
            "stats": stats,
        }

        logger.info(f"Ingestion task {task_id} completed: {stats}")

    except Exception as e:
        error_msg = f"Ingestion failed: {str(e)}"
        logger.error(error_msg)
        _task_store[task_id] = {
            "status": "failed",
            "progress": 0,
            "message": error_msg,
        }


async def _process_huggingface_task(
    task_id: str, dataset: str, dataset_split: str, doc_limit: int | None
) -> None:
    """Background task to process HuggingFace dataset ingestion.

    Args:
        task_id: Unique task identifier.
        dataset: Name of the HuggingFace dataset.
        dataset_split: Dataset split to use.
        doc_limit: Optional limit on number of documents.
    """
    try:
        _task_store[task_id] = {
            "status": "processing",
            "progress": 0,
            "message": f"Loading dataset: {dataset}",
        }

        pipeline = IngestionPipeline()
        try:
            stats = await pipeline.ingest_from_huggingface(dataset, dataset_split, doc_limit)
        finally:
            await pipeline.close()

        _task_store[task_id] = {
            "status": "completed",
            "progress": 100,
            "message": f"Successfully ingested from {dataset}",
            "stats": stats,
        }

        logger.info(f"HuggingFace ingestion task {task_id} completed")

    except Exception as e:
        error_msg = f"HuggingFace ingestion failed: {str(e)}"
        logger.error(error_msg)
        _task_store[task_id] = {
            "status": "failed",
            "progress": 0,
            "message": error_msg,
        }


@router.post(
    "/ingest/legal-corpus",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest legal corpus documents",
    description="Ingest a batch of legal documents into the system for indexing and search.",
)
async def ingest_legal_corpus(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
) -> IngestResponse:
    """Ingest legal corpus documents.

    This endpoint accepts a batch of legal documents and processes them
    through the ingestion pipeline (normalize -> parse -> index).

    Args:
        request: Ingestion request with documents to process.
        background_tasks: FastAPI background tasks for async processing.

    Returns:
        Ingestion response with task ID and status.

    Raises:
        HTTPException: If ingestion request is invalid.
    """
    if not request.documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No documents provided for ingestion",
        )

    # Generate task ID
    task_id = str(uuid.uuid4())

    # Validate documents
    valid_documents = []
    for i, doc in enumerate(request.documents):
        if not isinstance(doc, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document at index {i} must be a dictionary",
            )
        if "content" not in doc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document at index {i} missing required 'content' field",
            )
        valid_documents.append(doc)

    # Queue background task
    background_tasks.add_task(
        _process_ingestion_task,
        task_id,
        valid_documents,
        request.source,
    )

    logger.info(f"Queued ingestion task {task_id} with {len(valid_documents)} documents")

    return IngestResponse(
        task_id=task_id,
        status="queued",
        document_count=len(valid_documents),
        message=f"Document ingestion queued successfully. Task ID: {task_id}",
    )


@router.post(
    "/ingest/single",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a single legal document",
    description="Ingest a single legal document into the system.",
)
async def ingest_single_document(
    title: str,
    content: str,
    background_tasks: BackgroundTasks,
) -> IngestResponse:
    """Ingest a single legal document.

    Args:
        title: Document title.
        content: Document content.
        background_tasks: FastAPI background tasks.

    Returns:
        Ingestion response with task ID.
    """
    if not content or len(content.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document content must be at least 10 characters",
        )

    task_id = str(uuid.uuid4())

    background_tasks.add_task(
        _process_ingestion_task,
        task_id,
        [{"title": title, "content": content}],
        "manual",
    )

    return IngestResponse(
        task_id=task_id,
        status="queued",
        document_count=1,
        message=f"Single document ingestion queued. Task ID: {task_id}",
    )


@router.get(
    "/ingest/status/{task_id}",
    summary="Get ingestion task status",
    description="Check the status of a background ingestion task.",
)
async def get_ingestion_status(task_id: str) -> dict[str, Any]:
    """Get the status of an ingestion task.

    Args:
        task_id: The task ID returned from ingestion endpoint.

    Returns:
        Task status information.

    Raises:
        HTTPException: If task ID not found.
    """
    if task_id not in _task_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    return {
        "task_id": task_id,
        **_task_store[task_id],
    }


@router.post(
    "/ingest/huggingface",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest from HuggingFace dataset",
    description="Ingest legal documents from a HuggingFace dataset.",
)
async def ingest_from_huggingface(
    dataset_name: str = "th1nhng0/vietnamese-legal-documents",
    split: str = "train",
    limit: int | None = None,
    background_tasks: BackgroundTasks = None,  # type: ignore
) -> IngestResponse:
    """Ingest documents from a HuggingFace dataset.

    Args:
        dataset_name: Name of the HuggingFace dataset.
        split: Dataset split to use.
        limit: Optional limit on number of documents.
        background_tasks: FastAPI background tasks.

    Returns:
        Ingestion response with task ID.
    """
    task_id = str(uuid.uuid4())

    if background_tasks:
        background_tasks.add_task(
            _process_huggingface_task,
            task_id,
            dataset_name,
            split,
            limit,
        )

        return IngestResponse(
            task_id=task_id,
            status="queued",
            document_count=0,  # Unknown until loaded
            message=f"HuggingFace dataset ingestion queued. Task ID: {task_id}",
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Background tasks not available",
        )
