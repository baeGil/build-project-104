"""Dataset ingestion routes with task management."""

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from packages.common.config import get_settings
from packages.ingestion.pipeline import IngestionPipeline
from packages.ingestion.task_manager import task_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["dataset-ingestion"])


@router.post(
    "/ingest/dataset/start",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start dataset ingestion",
    description="Start a new background task to ingest data from HuggingFace dataset",
)
async def start_dataset_ingestion(
    background_tasks: BackgroundTasks,
    limit: int = 50,
) -> dict[str, Any]:
    """Start dataset ingestion task.
    
    Args:
        limit: Number of documents to ingest
        background_tasks: FastAPI background tasks
        
    Returns:
        Task ID and initial status
    """
    if limit < 1 or limit > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 1000",
        )
    
    # Create task
    task_id = task_manager.create_task(limit=limit)
    
    # Get settings and create pipeline
    settings = get_settings()
    pipeline = IngestionPipeline(settings)
    
    # Start in background
    async def run_ingestion():
        try:
            result = await task_manager.start_task(task_id, pipeline)
            logger.info(f"Task {task_id} completed: {result}")
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
        finally:
            try:
                await pipeline.close()
            except:
                pass
    
    background_tasks.add_task(run_ingestion)
    
    return {
        "task_id": task_id,
        "status": "queued",
        "limit": limit,
        "message": f"Dataset ingestion started. Use task_id to track progress.",
    }


@router.get(
    "/ingest/dataset/status/{task_id}",
    summary="Get ingestion task status",
    description="Get detailed progress of an ingestion task",
)
async def get_ingestion_status(task_id: str) -> dict[str, Any]:
    """Get task status and progress.
    
    Args:
        task_id: Task ID from start endpoint
        
    Returns:
        Detailed task status and progress
    """
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    
    return task


@router.get(
    "/ingest/dataset/tasks",
    summary="List ingestion tasks",
    description="List recent ingestion tasks",
)
async def list_ingestion_tasks(limit: int = 20) -> list[dict[str, Any]]:
    """List recent ingestion tasks.
    
    Args:
        limit: Maximum number of tasks to return
        
    Returns:
        List of tasks with status
    """
    return task_manager.list_tasks(limit=limit)


@router.post(
    "/ingest/dataset/cancel/{task_id}",
    summary="Cancel ingestion task",
    description="Cancel a running ingestion task",
)
async def cancel_ingestion_task(task_id: str) -> dict[str, Any]:
    """Cancel a running task.
    
    Args:
        task_id: Task ID to cancel
        
    Returns:
        Cancellation status
    """
    success = task_manager.cancel_task(task_id)
    
    if not success:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found",
            )
        return {
            "task_id": task_id,
            "status": "already_completed",
            "message": f"Task is already in {task['status']} state",
        }
    
    return {
        "task_id": task_id,
        "status": "cancelling",
        "message": "Task cancellation requested",
    }
