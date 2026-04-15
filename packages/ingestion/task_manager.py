"""Ingestion task manager with state tracking."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Optional

from packages.ingestion.dataset_downloader import DatasetDownloader, DownloadStatus, ProgressInfo

logger = logging.getLogger(__name__)


class IngestionTask:
    """Represents a single ingestion task."""
    
    def __init__(self, task_id: str, limit: int = 50):
        self.task_id = task_id
        self.limit = limit
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        
        self.downloader = DatasetDownloader()
        self.downloader.set_progress_callback(self._on_progress)
        
        self.status = DownloadStatus.PENDING
        self.progress = ProgressInfo()
        self.result: dict[str, Any] = {}
        self.error: Optional[str] = None
        
        self._task: Optional[asyncio.Task] = None
    
    def _on_progress(self, progress_dict: dict[str, Any]):
        """Callback from downloader."""
        self.progress = ProgressInfo(
            status=DownloadStatus(progress_dict["status"]),
            current_step=progress_dict["current_step"],
            total_steps=progress_dict["total_steps"],
            current_item=progress_dict["current_item"],
            total_items=progress_dict["total_items"],
            percentage=progress_dict["percentage"],
            message=progress_dict["message"],
            started_at=progress_dict["started_at"],
            completed_at=progress_dict["completed_at"],
            error=progress_dict["error"],
            metadata=progress_dict["metadata"],
        )
        self.status = self.progress.status
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "limit": self.limit,
            "status": self.status.value,
            "progress": self.progress.to_dict(),
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
        }
    
    async def run(self, pipeline) -> dict[str, Any]:
        """Run the ingestion task."""
        self.started_at = time.time()
        self._task = asyncio.current_task()
        
        try:
            # Phase 1: Download and prepare
            logger.info(f"[Task {self.task_id}] Starting download (limit={self.limit})")
            documents = await self.downloader.download_and_prepare(limit=self.limit)
            
            if not documents:
                raise Exception("No documents were downloaded")
            
            logger.info(f"[Task {self.task_id}] Downloaded {len(documents)} documents")
            
            # Phase 2: Ingest into system
            self.progress.status = DownloadStatus.INGESTING
            self.progress.current_step = "Ingesting documents"
            
            stats = {
                "total": len(documents),
                "success": 0,
                "failed": 0,
                "errors": [],
            }
            
            for i, doc in enumerate(documents, 1):
                try:
                    self.progress.current_item = i
                    self.progress.total_items = len(documents)
                    self.progress.percentage = ((len(documents) + i) / (2 * len(documents))) * 100
                    self.progress.message = f"Ingesting document {i}/{len(documents)}"
                    
                    node = await pipeline.ingest_single_document(
                        title=doc["title"],
                        content=doc["content"],
                    )
                    
                    stats["success"] += 1
                    
                except Exception as e:
                    stats["failed"] += 1
                    stats["errors"].append(f"Document {i}: {str(e)}")
                    logger.error(f"[Task {self.task_id}] Failed to ingest document {i}: {e}")
            
            # Complete
            self.status = DownloadStatus.COMPLETED
            self.completed_at = time.time()
            self.result = {
                "documents_downloaded": len(documents),
                "documents_ingested": stats["success"],
                "documents_failed": stats["failed"],
                "errors": stats["errors"][:10],  # Limit errors in result
                "duration_seconds": round(self.completed_at - self.started_at, 2),
            }
            
            logger.info(f"[Task {self.task_id}] Completed: {stats['success']} ingested, {stats['failed']} failed")
            return self.result
            
        except asyncio.CancelledError:
            self.status = DownloadStatus.CANCELLED
            self.completed_at = time.time()
            logger.info(f"[Task {self.task_id}] Cancelled")
            raise
            
        except Exception as e:
            self.status = DownloadStatus.FAILED
            self.error = str(e)
            self.completed_at = time.time()
            logger.error(f"[Task {self.task_id}] Failed: {e}", exc_info=True)
            raise
    
    def cancel(self):
        """Cancel the task."""
        if self._task and not self._task.done():
            self._task.cancel()
            self.downloader.cancel()


class IngestionTaskManager:
    """Manage multiple ingestion tasks."""
    
    def __init__(self, max_concurrent_tasks: int = 1):
        self.tasks: dict[str, IngestionTask] = {}
        self.max_concurrent_tasks = max_concurrent_tasks
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
    
    def create_task(self, limit: int = 50) -> str:
        """Create a new ingestion task. Returns task_id."""
        task_id = str(uuid.uuid4())
        task = IngestionTask(task_id, limit)
        self.tasks[task_id] = task
        logger.info(f"Created task {task_id} with limit={limit}")
        return task_id
    
    async def start_task(self, task_id: str, pipeline) -> dict[str, Any]:
        """Start an ingestion task."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")
        
        task = self.tasks[task_id]
        
        async with self._semaphore:
            return await task.run(pipeline)
    
    def get_task(self, task_id: str) -> Optional[dict[str, Any]]:
        """Get task status."""
        if task_id not in self.tasks:
            return None
        return self.tasks[task_id].to_dict()
    
    def list_tasks(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent tasks."""
        sorted_tasks = sorted(
            self.tasks.values(),
            key=lambda t: t.created_at,
            reverse=True,
        )[:limit]
        return [t.to_dict() for t in sorted_tasks]
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        if task.status in (DownloadStatus.PENDING, DownloadStatus.DOWNLOADING, 
                          DownloadStatus.PROCESSING, DownloadStatus.INGESTING):
            task.cancel()
            return True
        return False
    
    def cleanup_old_tasks(self, max_age_seconds: int = 3600):
        """Remove completed/failed tasks older than max_age_seconds."""
        current_time = time.time()
        to_remove = []
        
        for task_id, task in self.tasks.items():
            if task.completed_at and (current_time - task.completed_at) > max_age_seconds:
                to_remove.append(task_id)
        
        for task_id in to_remove:
            del self.tasks[task_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tasks")


# Global task manager instance
task_manager = IngestionTaskManager(max_concurrent_tasks=1)
