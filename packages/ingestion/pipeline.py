"""Full Ingestion Pipeline for Vietnamese Legal Documents.

This module orchestrates the complete ingestion flow:
load -> normalize -> parse -> structure -> index
"""

from __future__ import annotations

import logging
from typing import Any

from packages.common.config import Settings, get_settings
from packages.common.types import LegalNode
from packages.ingestion.indexer import DocumentIndexer
from packages.ingestion.normalizer import normalize_legal_text
from packages.ingestion.parser import parse_legal_document

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Orchestrates the full ingestion pipeline.

    Pipeline stages:
    1. Load: Fetch documents from various sources
    2. Normalize: Clean and standardize text
    3. Parse: Extract hierarchical structure
    4. Structure: Build LegalNode hierarchy
    5. Index: Store in Qdrant and OpenSearch
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the ingestion pipeline.

        Args:
            settings: Optional application settings. If not provided,
                     will load from environment.
        """
        self.settings = settings or get_settings()
        self.indexer = DocumentIndexer(self.settings)

    async def ingest_single_document(self, title: str, content: str) -> LegalNode:
        """Ingest a single document through the pipeline.

        Args:
            title: Document title.
            content: Raw document content.

        Returns:
            Parsed and indexed LegalNode.
        """
        logger.info(f"Ingesting single document: {title}")

        # Stage 1: Normalize
        normalized_text = normalize_legal_text(content)
        logger.debug(f"Normalized text length: {len(normalized_text)}")

        # Stage 2: Parse
        node = parse_legal_document(normalized_text, title)
        logger.debug(f"Parsed document with ID: {node.id}")

        # Stage 3: Index
        await self.indexer.index([node])
        logger.info(f"Successfully ingested document: {title}")

        return node

    async def ingest_from_text(self, documents: list[dict[str, Any]]) -> dict[str, Any]:
        """Ingest documents from text input.

        Args:
            documents: List of document dictionaries with 'title' and 'content' keys.

        Returns:
            Ingestion statistics.
        """
        logger.info(f"Starting ingestion of {len(documents)} documents from text")

        stats = {
            "total": len(documents),
            "normalized": 0,
            "parsed": 0,
            "indexed": 0,
            "errors": [],
            "document_ids": [],
        }

        nodes: list[LegalNode] = []

        for i, doc in enumerate(documents):
            try:
                title = doc.get("title", f"Document {i + 1}")
                content = doc.get("content", "")

                if not content:
                    logger.warning(f"Skipping empty document: {title}")
                    continue

                # Normalize
                normalized = normalize_legal_text(content)
                stats["normalized"] += 1

                # Parse
                node = parse_legal_document(normalized, title)
                stats["parsed"] += 1
                nodes.append(node)
                stats["document_ids"].append(node.id)

            except Exception as e:
                error_msg = f"Failed to process document {i}: {str(e)}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)

        # Index all parsed nodes
        if nodes:
            try:
                index_result = await self.indexer.index(nodes)
                stats["indexed"] = index_result.get("qdrant_indexed", 0)
                stats["qdrant_count"] = index_result.get("qdrant_indexed", 0)
                stats["opensearch_count"] = index_result.get("opensearch_indexed", 0)

                if index_result.get("errors"):
                    stats["errors"].extend(index_result["errors"])

            except Exception as e:
                error_msg = f"Indexing failed: {str(e)}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)

        logger.info(f"Ingestion complete: {stats['parsed']}/{stats['total']} documents processed")
        return stats

    async def ingest_from_huggingface(
        self,
        dataset_name: str = "th1nhng0/vietnamese-legal-documents",
        split: str = "train",
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Ingest documents from a HuggingFace dataset.

        Args:
            dataset_name: Name of the HuggingFace dataset.
            split: Dataset split to use.
            limit: Optional limit on number of documents to ingest.

        Returns:
            Ingestion statistics.
        """
        logger.info(f"Loading dataset from HuggingFace: {dataset_name}")

        stats = {
            "source": dataset_name,
            "total_loaded": 0,
            "normalized": 0,
            "parsed": 0,
            "indexed": 0,
            "errors": [],
            "document_ids": [],
        }

        try:
            from datasets import load_dataset
        except ImportError:
            error_msg = "datasets library not installed. Install with: pip install datasets"
            logger.error(error_msg)
            stats["errors"].append(error_msg)
            return stats

        try:
            # Load dataset
            dataset = load_dataset(dataset_name, split=split, streaming=True)

            nodes: list[LegalNode] = []

            for i, item in enumerate(dataset):
                if limit and i >= limit:
                    break

                try:
                    # Extract fields (adapt based on actual dataset schema)
                    title = item.get("title", item.get("name", f"Document {i + 1}"))
                    content = item.get("content", item.get("text", item.get("body", "")))

                    if not content:
                        logger.warning(f"Skipping empty document at index {i}")
                        continue

                    stats["total_loaded"] += 1

                    # Normalize
                    normalized = normalize_legal_text(content)
                    stats["normalized"] += 1

                    # Parse
                    node = parse_legal_document(normalized, title)
                    stats["parsed"] += 1
                    nodes.append(node)
                    stats["document_ids"].append(node.id)

                    # Index in batches
                    if len(nodes) >= 100:
                        index_result = await self.indexer.index(nodes)
                        stats["indexed"] += index_result.get("qdrant_indexed", 0)
                        nodes = []

                        logger.info(f"Processed {stats['parsed']} documents...")

                except Exception as e:
                    error_msg = f"Failed to process dataset item {i}: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)

            # Index remaining nodes
            if nodes:
                index_result = await self.indexer.index(nodes)
                stats["indexed"] += index_result.get("qdrant_indexed", 0)

            logger.info(
                f"Dataset ingestion complete: {stats['parsed']}/{stats['total_loaded']} documents"
            )

        except Exception as e:
            error_msg = f"Failed to load or process dataset: {str(e)}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)

        return stats

    async def ingest_from_file(self, file_path: str, title: str | None = None) -> LegalNode:
        """Ingest a document from a file.

        Args:
            file_path: Path to the file to ingest.
            title: Optional document title. If not provided, uses filename.

        Returns:
            Parsed and indexed LegalNode.
        """
        import os

        logger.info(f"Ingesting document from file: {file_path}")

        # Determine title
        if title is None:
            title = os.path.basename(file_path)

        # Read file
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        return await self.ingest_single_document(title, content)

    async def ingest_batch(
        self,
        documents: list[dict[str, Any]],
        batch_size: int = 100,
    ) -> dict[str, Any]:
        """Ingest a large batch of documents with progress tracking.

        Args:
            documents: List of document dictionaries.
            batch_size: Number of documents to process per batch.

        Returns:
            Ingestion statistics.
        """
        logger.info(f"Starting batch ingestion of {len(documents)} documents")

        stats = {
            "total": len(documents),
            "processed": 0,
            "failed": 0,
            "errors": [],
        }

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]

            try:
                batch_stats = await self.ingest_from_text(batch)
                stats["processed"] += batch_stats.get("parsed", 0)

                if batch_stats.get("errors"):
                    stats["failed"] += len(batch_stats["errors"])
                    stats["errors"].extend(batch_stats["errors"])

                logger.info(f"Processed batch {i//batch_size + 1}: {len(batch)} documents")

            except Exception as e:
                error_msg = f"Batch {i//batch_size + 1} failed: {str(e)}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)
                stats["failed"] += len(batch)

        logger.info(f"Batch ingestion complete: {stats['processed']}/{stats['total']} documents")
        return stats
