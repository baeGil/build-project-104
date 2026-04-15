"""Dataset downloader with progress tracking and chunked processing."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

import aiohttp
from datasets import load_dataset

logger = logging.getLogger(__name__)


class DownloadStatus(Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    INGESTING = "ingesting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressInfo:
    """Progress tracking information."""
    status: DownloadStatus = DownloadStatus.PENDING
    current_step: str = ""
    total_steps: int = 0
    current_item: int = 0
    total_items: int = 0
    percentage: float = 0.0
    message: str = ""
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "current_item": self.current_item,
            "total_items": self.total_items,
            "percentage": round(self.percentage, 2),
            "message": self.message,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "metadata": self.metadata,
            "elapsed_seconds": round(time.time() - self.started_at, 2) if self.started_at else 0,
        }


class DatasetDownloader:
    """Download and process HuggingFace datasets with progress tracking."""
    
    def __init__(
        self,
        dataset_name: str = "th1nhng0/vietnamese-legal-documents",
        data_dir: Optional[Path] = None,
    ):
        self.dataset_name = dataset_name
        self.data_dir = data_dir or Path("data/datasets")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.progress = ProgressInfo()
        self._cancelled = False
        self._progress_callback: Optional[Callable] = None
    
    def set_progress_callback(self, callback: Callable):
        """Set callback function for progress updates."""
        self._progress_callback = callback
    
    def cancel(self):
        """Cancel the current download."""
        self._cancelled = True
        logger.info("Download cancellation requested")
    
    def _update_progress(
        self,
        status: DownloadStatus,
        current_step: str,
        current_item: int = 0,
        total_items: int = 0,
        message: str = "",
        error: Optional[str] = None,
        **metadata,
    ):
        """Update progress and notify callback."""
        self.progress.status = status
        self.progress.current_step = current_step
        self.progress.current_item = current_item
        self.progress.total_items = total_items
        self.progress.message = message
        self.progress.error = error
        self.progress.metadata.update(metadata)
        
        if total_items > 0:
            self.progress.percentage = (current_item / total_items) * 100
        
        if status == DownloadStatus.DOWNLOADING and not self.progress.started_at:
            self.progress.started_at = time.time()
        
        if status in (DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED):
            self.progress.completed_at = time.time()
        
        # Notify callback
        if self._progress_callback:
            try:
                if asyncio.iscoroutinefunction(self._progress_callback):
                    asyncio.create_task(self._progress_callback(self.progress.to_dict()))
                else:
                    self._progress_callback(self.progress.to_dict())
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
    
    async def download_and_prepare(self, limit: int = 50) -> list[dict[str, Any]]:
        """Download dataset and prepare documents for ingestion.
        
        Args:
            limit: Maximum number of documents to process
            
        Returns:
            List of prepared documents
        """
        self._cancelled = False
        
        try:
            # Step 1: Load metadata
            self._update_progress(
                DownloadStatus.DOWNLOADING,
                "Loading metadata",
                message="Connecting to HuggingFace...",
            )
            
            metadata_ds = load_dataset(
                self.dataset_name,
                name="metadata",
                split="data",
                streaming=True,
                trust_remote_code=True,
            )
            
            # Step 2: Load content
            self._update_progress(
                DownloadStatus.DOWNLOADING,
                "Loading content",
                message="Downloading content data...",
            )
            
            content_ds = load_dataset(
                self.dataset_name,
                name="content",
                split="data",
                streaming=True,
                trust_remote_code=True,
            )
            
            # Step 3: Build content index
            self._update_progress(
                DownloadStatus.PROCESSING,
                "Building content index",
                current_item=0,
                total_items=limit,
                message="Processing content items...",
            )
            
            content_lookup = {}
            for i, item in enumerate(content_ds):
                if self._cancelled:
                    self._update_progress(
                        DownloadStatus.CANCELLED,
                        "Cancelled",
                        message="Download was cancelled",
                    )
                    return []
                
                if i >= limit:
                    break
                
                doc_id = str(item.get("id", ""))
                content_html = item.get("content_html", "")
                
                # Clean HTML (simple version, can be enhanced)
                content_text = self._clean_html(content_html)
                
                if content_text:
                    content_lookup[doc_id] = content_text
                
                if (i + 1) % 10 == 0:
                    self._update_progress(
                        DownloadStatus.PROCESSING,
                        "Building content index",
                        current_item=i + 1,
                        total_items=limit,
                        message=f"Indexed {i+1} content items",
                    )
            
            logger.info(f"Content index built: {len(content_lookup)} documents")
            
            # Step 4: Merge metadata with content
            self._update_progress(
                DownloadStatus.PROCESSING,
                "Merging documents",
                current_item=0,
                total_items=limit,
                message="Merging metadata with content...",
            )
            
            merged_docs = []
            for i, meta in enumerate(metadata_ds):
                if self._cancelled:
                    self._update_progress(
                        DownloadStatus.CANCELLED,
                        "Cancelled",
                        message="Download was cancelled",
                    )
                    return []
                
                if i >= limit:
                    break
                
                doc_id = str(meta.get("id", ""))
                content = content_lookup.get(doc_id, "")
                
                if not content:
                    continue
                
                merged_doc = {
                    "id": doc_id,
                    "title": meta.get("title", ""),
                    "content": content,
                    "doc_type": meta.get("loai_van_ban", "unknown"),
                    "metadata": {
                        "so_ky_hieu": meta.get("so_ky_hieu", ""),
                        "ngay_ban_hanh": meta.get("ngay_ban_hanh", ""),
                        "ngay_co_hieu_luc": meta.get("ngay_co_hieu_luc", ""),
                        "co_quan_ban_hanh": meta.get("co_quan_ban_hanh", ""),
                        "source_dataset": self.dataset_name,
                    }
                }
                
                merged_docs.append(merged_doc)
                
                if (i + 1) % 10 == 0:
                    self._update_progress(
                        DownloadStatus.PROCESSING,
                        "Merging documents",
                        current_item=i + 1,
                        total_items=limit,
                        message=f"Merged {i+1} documents",
                    )
            
            self._update_progress(
                DownloadStatus.PROCESSING,
                "Completed",
                current_item=len(merged_docs),
                total_items=len(merged_docs),
                message=f"Prepared {len(merged_docs)} documents for ingestion",
            )
            
            return merged_docs
            
        except Exception as e:
            logger.error(f"Download failed: {e}", exc_info=True)
            self._update_progress(
                DownloadStatus.FAILED,
                "Failed",
                message=f"Download failed: {str(e)}",
                error=str(e),
            )
            raise
    
    def _clean_html(self, html_content: str) -> str:
        """Clean HTML content to plain text."""
        if not html_content:
            return ""
        
        try:
            from bs4 import BeautifulSoup
            import re
            
            soup = BeautifulSoup(html_content, 'html.parser')
            text = soup.get_text(separator='\n', strip=True)
            text = re.sub(r'\n\s*\n', '\n\n', text)
            return text.strip()
        except Exception as e:
            logger.warning(f"Failed to clean HTML: {e}")
            # Fallback: simple tag removal
            import re
            text = re.sub(r'<[^>]+>', '', html_content)
            return text.strip()
