"""Ingest Vietnamese Legal Documents from HuggingFace dataset.

This script properly ingests the th1nhng0/vietnamese-legal-documents dataset by:
1. Loading metadata config (document info)
2. Loading content config (document content in HTML)
3. Merging them by ID
4. Cleaning HTML to plain text
5. Running through ingestion pipeline

Usage:
    python database/ingest_huggingface.py [--limit 50]
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from typing import Any

import asyncpg
from bs4 import BeautifulSoup

# Add parent directory to path
sys.path.insert(0, "/Users/AI/Vinuni/build project qoder")

from packages.common.config import get_settings
from packages.ingestion.pipeline import IngestionPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def clean_html_to_text(html_content: str) -> str:
    """Convert HTML content to clean plain text.
    
    Args:
        html_content: HTML string
        
    Returns:
        Clean plain text
    """
    if not html_content:
        return ""
    
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Get text content
    text = soup.get_text(separator='\n', strip=True)
    
    # Clean up multiple newlines
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text


async def load_and_merge_dataset(limit: int = 50) -> list[dict[str, Any]]:
    """Load metadata and content configs and merge them.
    
    Args:
        limit: Maximum number of documents to load
        
    Returns:
        List of merged documents
    """
    from datasets import load_dataset
    
    logger.info("Loading metadata config (streaming)...")
    metadata_ds = load_dataset(
        "th1nhng0/vietnamese-legal-documents",
        name="metadata",
        split="data",
        streaming=True,
    )
    
    logger.info("Loading content config (streaming)...")
    content_ds = load_dataset(
        "th1nhng0/vietnamese-legal-documents",
        name="content",
        split="data",
        streaming=True,
    )
    
    # Build content lookup by ID - ONLY first 'limit' items
    logger.info(f"Building content index (first {limit} items)...")
    content_lookup = {}
    for i, item in enumerate(content_ds):
        if i >= limit:
            logger.info(f"  Stopping at {limit} content items")
            break
        doc_id = str(item.get("id", ""))
        content_html = item.get("content_html", "")
        
        # Clean HTML to text
        content_text = clean_html_to_text(content_html)
        
        if content_text:
            content_lookup[doc_id] = content_text
        
        if (i + 1) % 10 == 0:
            logger.info(f"  Indexed {i+1} content items...")
    
    logger.info(f"Content index built: {len(content_lookup)} documents")
    
    # Merge metadata with content - ONLY first 'limit' items
    logger.info("Merging metadata with content...")
    merged_docs = []
    
    for i, meta in enumerate(metadata_ds):
        if i >= limit:
            logger.info(f"  Stopping at {limit} metadata items")
            break
        
        doc_id = str(meta.get("id", ""))
        
        # Get content
        content = content_lookup.get(doc_id, "")
        
        if not content:
            logger.warning(f"Document {doc_id} has no content, skipping")
            continue
        
        # Build merged document
        merged_doc = {
            "id": doc_id,
            "title": meta.get("title", ""),
            "content": content,
            "doc_type": meta.get("loai_van_ban", "unknown"),
            "metadata": {
                "so_ky_hieu": meta.get("so_ky_hieu", ""),
                "ngay_ban_hanh": meta.get("ngay_ban_hanh", ""),
                "ngay_co_hieu_luc": meta.get("ngay_co_hieu_luc", ""),
                "ngay_het_hieu_luc": meta.get("ngay_het_hieu_luc", ""),
                "nguon_thu_thap": meta.get("nguon_thu_thap", ""),
                "nganh": meta.get("nganh", ""),
                "linh_vuc": meta.get("linh_vuc", ""),
                "co_quan_ban_hanh": meta.get("co_quan_ban_hanh", ""),
                "tinh_trang_hieu_luc": meta.get("tinh_trang_hieu_luc", ""),
                "source_dataset": "th1nhng0/vietnamese-legal-documents",
            }
        }
        
        merged_docs.append(merged_doc)
        
        if (i + 1) % 10 == 0:
            logger.info(f"  Merged {i+1} documents...")
    
    logger.info(f"Merged {len(merged_docs)} documents total")
    return merged_docs


async def ingest_documents(pipeline: IngestionPipeline, documents: list[dict[str, Any]]) -> dict[str, Any]:
    """Ingest documents through the pipeline.
    
    Args:
        pipeline: IngestionPipeline instance
        documents: List of documents to ingest
        
    Returns:
        Ingestion statistics
    """
    stats = {
        "total": len(documents),
        "success": 0,
        "failed": 0,
        "errors": [],
        "document_ids": [],
    }
    
    for i, doc in enumerate(documents, 1):
        try:
            logger.info(f"[{i}/{len(documents)}] Ingesting: {doc['title']}")
            
            node = await pipeline.ingest_single_document(
                title=doc["title"],
                content=doc["content"],
            )
            
            stats["success"] += 1
            stats["document_ids"].append(node.id)
            logger.info(f"  ✓ Success: {node.id}")
            
        except Exception as e:
            stats["failed"] += 1
            error_msg = f"Failed to ingest '{doc['title']}': {str(e)}"
            stats["errors"].append(error_msg)
            logger.error(f"  ✗ {error_msg}")
    
    return stats


async def main():
    """Main ingestion script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest Vietnamese legal documents from HuggingFace")
    parser.add_argument("--limit", type=int, default=50, help="Number of documents to ingest")
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Vietnamese Legal Documents - HuggingFace Ingestion")
    logger.info("=" * 60)
    logger.info(f"Dataset: th1nhng0/vietnamese-legal-documents")
    logger.info(f"Limit: {args.limit} documents")
    
    # Check settings
    settings = get_settings()
    logger.info(f"PostgreSQL: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    logger.info(f"Qdrant: {settings.qdrant_host}:{settings.qdrant_port}")
    logger.info(f"OpenSearch: {settings.opensearch_host}:{settings.opensearch_port}")
    
    # Load and merge dataset
    try:
        documents = await load_and_merge_dataset(limit=args.limit)
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}")
        return 1
    
    if not documents:
        logger.error("No documents loaded from dataset")
        return 1
    
    # Initialize pipeline
    try:
        pipeline = IngestionPipeline(settings)
        logger.info("IngestionPipeline initialized")
    except Exception as e:
        logger.error(f"Failed to initialize pipeline: {e}")
        return 1
    
    # Ingest documents
    try:
        stats = await ingest_documents(pipeline, documents)
        
        # Print summary
        logger.info("=" * 60)
        logger.info("INGESTION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total attempted: {stats['total']}")
        logger.info(f"Successfully ingested: {stats['success']}")
        logger.info(f"Failed: {stats['failed']}")
        
        if stats["errors"]:
            logger.info(f"\nFirst 5 errors:")
            for i, error in enumerate(stats["errors"][:5], 1):
                logger.info(f"  {i}. {error}")
        
        logger.info("=" * 60)
        
        if stats["success"] > 0:
            logger.info("✓ Ingestion completed successfully!")
            return 0
        else:
            logger.error("✗ No documents were ingested")
            return 1
            
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        return 1
        
    finally:
        try:
            await pipeline.close()
            logger.info("Pipeline connections closed")
        except Exception as e:
            logger.warning(f"Error closing pipeline: {e}")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
