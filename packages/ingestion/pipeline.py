"""Full Ingestion Pipeline for Vietnamese Legal Documents.

This module orchestrates the complete ingestion flow:
load -> normalize -> parse -> structure -> index
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any, Callable, Optional

import asyncpg

from packages.common.config import Settings, get_settings
from packages.common.types import LegalNode
from packages.graph.sync import GraphSyncService
from packages.ingestion.indexer import DocumentIndexer
from packages.ingestion.normalizer import normalize_legal_text
from packages.ingestion.parser import parse_legal_document

logger = logging.getLogger(__name__)


async def _retry_with_backoff(
    coro_func: Callable[[], Any],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    operation_name: str = "operation",
) -> Any:
    """Execute a coroutine with exponential backoff retry logic.
    
    Args:
        coro_func: Async function to execute.
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay in seconds for exponential backoff.
        max_delay: Maximum delay between retries.
        operation_name: Name of operation for logging.
        
    Returns:
        Result of the coroutine.
        
    Raises:
        Last exception if all retries fail.
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await coro_func()
        except (ConnectionError, TimeoutError, OSError, asyncpg.PostgresError) as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                logger.warning(
                    f"{operation_name} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"{operation_name} failed after {max_retries + 1} attempts: {e}")
                raise
        except Exception as e:
            # Non-retryable exceptions
            logger.error(f"{operation_name} failed with non-retryable error: {e}")
            raise
    
    raise last_exception


class IngestionPipeline:
    """Orchestrates the full ingestion pipeline.

    Pipeline stages:
    1. Load: Fetch documents from various sources
    2. Normalize: Clean and standardize text
    3. Parse: Extract hierarchical structure
    4. Structure: Build LegalNode hierarchy
    5. Index: Store in Qdrant and OpenSearch
    """

    def __init__(
        self,
        settings: Settings | None = None,
        max_concurrent: int = 5,
        max_retries: int = 3,
    ) -> None:
        """Initialize the ingestion pipeline.

        Args:
            settings: Optional application settings. If not provided,
                     will load from environment.
            max_concurrent: Maximum concurrent operations (default: 5).
            max_retries: Maximum retry attempts for storage operations (default: 3).
        """
        self.settings = settings or get_settings()
        self.indexer = DocumentIndexer(self.settings)
        self.graph_sync = GraphSyncService(self.settings)
        self._postgres_pool = None
        self._max_concurrent = max_concurrent
        self._max_retries = max_retries
        self._semaphore: asyncio.Semaphore | None = None

    async def _get_semaphore(self) -> asyncio.Semaphore:
        """Get or create the concurrency semaphore.
        
        Returns:
            asyncio.Semaphore instance.
        """
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrent)
        return self._semaphore

    async def _get_postgres_pool(self):
        """Get or create PostgreSQL connection pool.
        
        Returns:
            asyncpg connection pool
        """
        if self._postgres_pool is None:
            self._postgres_pool = await asyncpg.create_pool(
                self.settings.postgres_dsn,
                min_size=2,
                max_size=10,
            )
            logger.info("Connected to PostgreSQL")
        return self._postgres_pool

    async def _check_postgres_health(self) -> bool:
        """Check PostgreSQL connectivity.
        
        Returns:
            True if connection is healthy, False otherwise.
        """
        try:
            pool = await self._get_postgres_pool()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            logger.debug("PostgreSQL health check passed")
            return True
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")
            return False

    async def _check_qdrant_health(self) -> bool:
        """Check Qdrant connectivity.
        
        Returns:
            True if connection is healthy, False otherwise.
        """
        try:
            await self.indexer.qdrant_indexer.ensure_collection()
            logger.debug("Qdrant health check passed")
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False

    async def _check_opensearch_health(self) -> bool:
        """Check OpenSearch connectivity.
        
        Returns:
            True if connection is healthy, False otherwise.
        """
        try:
            await self.indexer.opensearch_indexer.ensure_index()
            logger.debug("OpenSearch health check passed")
            return True
        except Exception as e:
            logger.error(f"OpenSearch health check failed: {e}")
            return False

    async def _check_neo4j_health(self) -> bool:
        """Check Neo4j connectivity."""
        try:
            return await self.graph_sync.graph_client.ping()
        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
            return False

    async def check_all_connections(self) -> dict[str, bool]:
        """Check all backend connections.
        
        Returns:
            Dictionary with health status for each backend.
        """
        results = await asyncio.gather(
            self._check_postgres_health(),
            self._check_qdrant_health(),
            self._check_opensearch_health(),
            self._check_neo4j_health(),
            return_exceptions=True,
        )
        
        return {
            "postgres": results[0] if isinstance(results[0], bool) else False,
            "qdrant": results[1] if isinstance(results[1], bool) else False,
            "opensearch": results[2] if isinstance(results[2], bool) else False,
            "neo4j": results[3] if isinstance(results[3], bool) else False,
        }

    def _build_storage_metadata(self, node: LegalNode, source: str) -> dict[str, Any]:
        """Build consistent metadata stored alongside raw documents."""
        return {
            "doc_type": node.doc_type.value if hasattr(node.doc_type, "value") else str(node.doc_type),
            "source": source,
            "parent_id": node.parent_id,
            "children_ids": node.children_ids,
            "publish_date": node.publish_date.isoformat() if node.publish_date else None,
            "effective_date": node.effective_date.isoformat() if node.effective_date else None,
            "expiry_date": node.expiry_date.isoformat() if node.expiry_date else None,
            "issuing_body": node.issuing_body,
            "document_number": node.document_number,
            "amendment_refs": node.amendment_refs,
            "citation_refs": node.citation_refs,
            "keywords": node.keywords,
            "level": node.level,
        }

    async def _store_in_postgres(self, node: LegalNode, original_content: str) -> None:
        """Store document in PostgreSQL with retry logic.
        
        Args:
            node: Parsed LegalNode
            original_content: Original document content
        """
        async def _do_store():
            pool = await self._get_postgres_pool()
            
            metadata = self._build_storage_metadata(node, "ingestion_pipeline")
            
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO legal_documents (id, title, content, doc_type, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        content = EXCLUDED.content,
                        doc_type = EXCLUDED.doc_type,
                        metadata = EXCLUDED.metadata,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    node.id,
                    node.title or "",
                    original_content,
                    node.doc_type.value if hasattr(node.doc_type, 'value') else str(node.doc_type),
                    json.dumps(metadata)
                )
                logger.debug(f"Stored document in PostgreSQL: {node.id}")
        
        try:
            sem = await self._get_semaphore()
            async with sem:
                await _retry_with_backoff(
                    _do_store,
                    max_retries=self._max_retries,
                    operation_name=f"PostgreSQL store for {node.id}",
                )
        except Exception as e:
            logger.error(f"Failed to store document in PostgreSQL after retries: {e}")
            # Don't raise - PostgreSQL storage is secondary to indexing

    async def ingest_single_document(self, title: str, content: str) -> LegalNode:
        """Ingest a single document through the pipeline.

        Args:
            title: Document title.
            content: Raw document content.

        Returns:
            Parsed and indexed LegalNode.
        """
        logger.debug(f"Ingesting single document: {title}")

        # Stage 1: Normalize
        normalized_text = normalize_legal_text(content)
        logger.debug(f"Normalized text length: {len(normalized_text)}")

        # Stage 2: Parse
        node = parse_legal_document(normalized_text, title)
        logger.debug(f"Parsed document with ID: {node.id}")

        # Stage 3: Store in PostgreSQL
        await self._store_in_postgres(node, normalized_text)

        # Stage 4: Sync document hierarchy into Neo4j.
        try:
            await self.graph_sync.sync_legal_node(node)
        except Exception as e:
            logger.debug(f"Neo4j sync failed for {node.id}: {type(e).__name__}: {e}")

        # Stage 5: Index with retry
        indexing_result = None
        async def _do_index():
            nonlocal indexing_result
            indexing_result = await self.indexer.index([node])
            return indexing_result
        
        try:
            await _retry_with_backoff(
                _do_index,
                max_retries=self._max_retries,
                operation_name=f"Indexing document {node.id}",
            )
        except Exception as e:
            logger.debug(f"Indexing failed for {node.id}: {type(e).__name__}: {e}")
            # Don't raise - indexing is optional if PostgreSQL succeeded

        return node

    async def ingest_batch_documents(
        self,
        documents: list[dict[str, str]],
        batch_size: int = 50,
    ) -> dict[str, Any]:
        """Ingest multiple documents with optimized batching.
        
        Uses concurrent embedding generation and batch indexing
        for much better throughput.
        
        Args:
            documents: List of {title, content} dicts
            batch_size: Number of docs to process in parallel
            
        Returns:
            Stats dict
        """
        import time
        from concurrent.futures import ThreadPoolExecutor
        import asyncio
        
        logger.info(f"Starting batch ingestion of {len(documents)} documents")
        
        # Preload embedding model BEFORE processing to avoid cold start
        logger.info("Preloading embedding model...")
        model_start = time.time()
        await self.indexer.qdrant_indexer._get_embedding_model()
        model_elapsed = time.time() - model_start
        logger.info(f"✓ Embedding model loaded in {model_elapsed:.1f}s")
        
        stats = {
            "total": len(documents),
            "success": 0,
            "failed": 0,
            "errors": [],
            "qdrant_indexed": 0,
            "opensearch_indexed": 0,
        }
        
        start_time = time.time()
        
        # Process in batches for better parallelism
        for batch_start in range(0, len(documents), batch_size):
            batch_end = min(batch_start + batch_size, len(documents))
            batch = documents[batch_start:batch_end]
            
            batch_start_time = time.time()
            logger.info(f"Processing batch {batch_start//batch_size + 1}: {len(batch)} docs")
            
            # Stage 1-2: Normalize & Parse (CPU-bound, can parallelize)
            nodes = []
            failed_docs = []
            
            # Use thread pool for CPU-bound parsing
            with ThreadPoolExecutor(max_workers=4) as executor:
                loop = asyncio.get_event_loop()
                
                def parse_doc(doc):
                    try:
                        normalized = normalize_legal_text(doc["content"])
                        node = parse_legal_document(normalized, doc["title"])
                        return (node, normalized, None)
                    except Exception as e:
                        return (None, None, (doc["id"], str(e)))
                
                # Parse all docs in parallel
                futures = [loop.run_in_executor(executor, parse_doc, doc) for doc in batch]
                results = await asyncio.gather(*futures)
                
                for node, normalized, error in results:
                    if error:
                        doc_id, error_msg = error
                        failed_docs.append((doc_id, error_msg))
                        stats["failed"] += 1
                        logger.debug(f"Failed to parse {doc_id}: {error_msg}")
                    else:
                        nodes.append((node, normalized))
            
            if not nodes:
                continue
            
            # Stage 3: Batch store in PostgreSQL
            try:
                pool = await self._get_postgres_pool()
                async with pool.acquire() as conn:
                    # Use COPY for faster bulk insert
                    records = [
                        (node.id, node.title or "", normalized,
                         node.doc_type.value if hasattr(node.doc_type, 'value') else str(node.doc_type),
                         json.dumps(self._build_storage_metadata(node, "batch_ingestion")))
                        for node, normalized in nodes
                    ]
                    
                    await conn.executemany(
                        """
                        INSERT INTO legal_documents (id, title, content, doc_type, metadata)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (id) DO UPDATE SET
                            title = EXCLUDED.title,
                            content = EXCLUDED.content,
                            doc_type = EXCLUDED.doc_type,
                            metadata = EXCLUDED.metadata,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        records
                    )
                
                logger.info(f"Stored {len(records)} docs in PostgreSQL")
                stats["success"] += len(records)
                
            except Exception as e:
                logger.error(f"Batch PostgreSQL store failed: {e}")
                # Fallback to individual stores
                for node, normalized in nodes:
                    try:
                        await self._store_in_postgres(node, normalized)
                        stats["success"] += 1
                    except Exception as store_err:
                        stats["failed"] += 1
                        stats["errors"].append(f"{node.id}: {str(store_err)[:100]}")

            for node, _ in nodes:
                try:
                    await self.graph_sync.sync_legal_node(node)
                except Exception as e:
                    logger.debug(f"Neo4j sync failed for {node.id}: {type(e).__name__}: {e}")
            
            # Stage 5: Batch index (embedding generation is the bottleneck)
            if nodes:
                try:
                    nodes_only = [node for node, _ in nodes]
                    indexing_result = await self.indexer.index(nodes_only)
                    
                    qdrant_count = indexing_result.get("qdrant_indexed", 0)
                    opensearch_count = indexing_result.get("opensearch_indexed", 0)
                    
                    stats["qdrant_indexed"] += qdrant_count
                    stats["opensearch_indexed"] += opensearch_count
                    
                    logger.info(f"Indexed batch: Qdrant={qdrant_count}, OpenSearch={opensearch_count}")
                    
                except Exception as e:
                    logger.debug(f"Batch indexing failed: {e}")
            
            batch_elapsed = time.time() - batch_start_time
            docs_in_batch = stats["success"] + stats["failed"]
            overall_speed = docs_in_batch / (time.time() - start_time) if (time.time() - start_time) > 0 else 0
            
            logger.info(
                f"Batch complete in {batch_elapsed:.1f}s | "
                f"Overall: {docs_in_batch}/{len(documents)} docs | "
                f"Speed: {overall_speed:.1f} docs/s"
            )
        
        total_elapsed = time.time() - start_time
        final_speed = (stats["success"] + stats["failed"]) / total_elapsed if total_elapsed > 0 else 0
        
        logger.info(
            f"Batch ingestion complete: {stats['success']} success, {stats['failed']} failed | "
            f"Total time: {total_elapsed:.1f}s | Speed: {final_speed:.1f} docs/s"
        )
        
        return stats

    async def ingest_from_text(
        self,
        documents: list[dict[str, Any]],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> dict[str, Any]:
        """Ingest documents from text input.

        Args:
            documents: List of document dictionaries with 'title' and 'content' keys.
            progress_callback: Optional callback function(current, total, status) for progress updates.

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
        total = len(documents)

        for i, doc in enumerate(documents):
            current = i + 1
            
            try:
                title = doc.get("title", f"Document {i + 1}")
                content = doc.get("content", "")

                if not content:
                    logger.warning(f"Skipping empty document: {title}")
                    if progress_callback:
                        progress_callback(current, total, f"Skipped empty: {title}")
                    continue

                # Normalize
                if progress_callback:
                    progress_callback(current, total, f"Normalizing: {title}")
                normalized = normalize_legal_text(content)
                stats["normalized"] += 1

                # Parse
                if progress_callback:
                    progress_callback(current, total, f"Parsing: {title}")
                node = parse_legal_document(normalized, title)
                stats["parsed"] += 1
                nodes.append(node)
                stats["document_ids"].append(node.id)
                
                # Store in PostgreSQL
                if progress_callback:
                    progress_callback(current, total, f"Storing: {title}")
                await self._store_in_postgres(node, normalized)

                try:
                    await self.graph_sync.sync_legal_node(node)
                except Exception as e:
                    logger.debug(f"Neo4j sync failed for {node.id}: {type(e).__name__}: {e}")

            except Exception as e:
                error_msg = f"Failed to process document {i} ({doc.get('title', 'unknown')}): {str(e)}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)
                if progress_callback:
                    progress_callback(current, total, f"Error: {error_msg}")

        # Index all parsed nodes
        if nodes:
            try:
                if progress_callback:
                    progress_callback(total, total, "Indexing documents...")
                
                async def _do_index():
                    return await self.indexer.index(nodes)
                
                index_result = await _retry_with_backoff(
                    _do_index,
                    max_retries=self._max_retries,
                    operation_name="Batch indexing",
                )
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
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        config: str | None = None,  # Add config parameter for datasets with multiple configurations
    ) -> dict[str, Any]:
        """Ingest documents from a HuggingFace dataset.

        Args:
            dataset_name: Name of the HuggingFace dataset.
            split: Dataset split to use.
            limit: Optional limit on number of documents to ingest.
            progress_callback: Optional callback function(current, total, status) for progress updates.
            config: Dataset configuration name (for datasets with multiple configs).

        Returns:
            Ingestion statistics.
        """
        logger.info(f"Loading dataset from HuggingFace: {dataset_name}")
        if config:
            logger.info(f"Using config: {config}")

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
            if config:
                dataset = load_dataset(dataset_name, name=config, split=split, streaming=True)
            else:
                dataset = load_dataset(dataset_name, split=split, streaming=True)

            nodes: list[LegalNode] = []
            total = limit or float('inf')
            processed = 0

            for i, item in enumerate(dataset):
                if limit and i >= limit:
                    break

                processed = i + 1
                current_total = limit if limit else processed

                try:
                    # Extract fields (adapt based on actual dataset schema)
                    title = item.get("title", item.get("name", f"Document {i + 1}"))
                    content = item.get("content", item.get("text", item.get("body", "")))

                    if not content:
                        logger.warning(f"Skipping empty document at index {i}")
                        if progress_callback:
                            progress_callback(processed, current_total, f"Skipped empty at index {i}")
                        continue

                    stats["total_loaded"] += 1

                    # Normalize
                    if progress_callback:
                        progress_callback(processed, current_total, f"Normalizing: {title}")
                    normalized = normalize_legal_text(content)
                    stats["normalized"] += 1

                    # Parse
                    if progress_callback:
                        progress_callback(processed, current_total, f"Parsing: {title}")
                    node = parse_legal_document(normalized, title)
                    stats["parsed"] += 1
                    nodes.append(node)
                    stats["document_ids"].append(node.id)

                    try:
                        await self._store_in_postgres(node, normalized)
                    except Exception as store_error:
                        logger.debug(f"PostgreSQL store failed for {node.id}: {store_error}")

                    try:
                        await self.graph_sync.sync_legal_node(node)
                    except Exception as graph_error:
                        logger.debug(f"Neo4j sync failed for {node.id}: {graph_error}")

                    # Index in batches
                    if len(nodes) >= 100:
                        if progress_callback:
                            progress_callback(processed, current_total, "Indexing batch...")
                        
                        async def _do_batch_index():
                            return await self.indexer.index(nodes)
                        
                        index_result = await _retry_with_backoff(
                            _do_batch_index,
                            max_retries=self._max_retries,
                            operation_name="Batch indexing from HuggingFace",
                        )
                        stats["indexed"] += index_result.get("qdrant_indexed", 0)
                        nodes = []

                        logger.info(f"Processed {stats['parsed']} documents...")

                except Exception as e:
                    error_msg = f"Failed to process dataset item {i}: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)
                    if progress_callback:
                        progress_callback(processed, current_total, f"Error: {error_msg}")

            # Index remaining nodes
            if nodes:
                if progress_callback:
                    progress_callback(processed, total if limit else processed, "Indexing remaining documents...")
                
                async def _do_final_index():
                    return await self.indexer.index(nodes)
                
                index_result = await _retry_with_backoff(
                    _do_final_index,
                    max_retries=self._max_retries,
                    operation_name="Final batch indexing",
                )
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
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> dict[str, Any]:
        """Ingest a large batch of documents with progress tracking.

        Args:
            documents: List of document dictionaries.
            batch_size: Number of documents to process per batch.
            progress_callback: Optional callback function(current, total, status) for progress updates.

        Returns:
            Ingestion statistics.
        """
        logger.info(f"Starting batch ingestion of {len(documents)} documents")

        # Health check before starting
        if progress_callback:
            progress_callback(0, len(documents), "Checking connections...")
        
        health = await self.check_all_connections()
        unhealthy = [k for k, v in health.items() if not v]
        if unhealthy:
            logger.warning(f"Some connections are unhealthy: {unhealthy}")
            # Continue anyway - individual operations will handle errors

        stats = {
            "total": len(documents),
            "processed": 0,
            "failed": 0,
            "errors": [],
        }

        total_batches = (len(documents) + batch_size - 1) // batch_size

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            batch_num = i // batch_size + 1

            try:
                if progress_callback:
                    progress_callback(
                        i,
                        len(documents),
                        f"Processing batch {batch_num}/{total_batches}",
                    )
                
                batch_stats = await self.ingest_from_text(batch)
                stats["processed"] += batch_stats.get("parsed", 0)

                if batch_stats.get("errors"):
                    stats["failed"] += len(batch_stats["errors"])
                    stats["errors"].extend(batch_stats["errors"])

                logger.info(f"Processed batch {batch_num}: {len(batch)} documents")

            except Exception as e:
                error_msg = f"Batch {batch_num} failed: {str(e)}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)
                stats["failed"] += len(batch)

        if progress_callback:
            progress_callback(len(documents), len(documents), "Complete")
        
        logger.info(f"Batch ingestion complete: {stats['processed']}/{stats['total']} documents")
        return stats

    async def close(self):
        """Close all connections with proper error handling."""
        errors = []
        
        # Close PostgreSQL pool
        if self._postgres_pool:
            try:
                await self._postgres_pool.close()
                logger.info("PostgreSQL connection pool closed")
            except Exception as e:
                logger.error(f"Error closing PostgreSQL pool: {e}")
                errors.append(f"PostgreSQL: {e}")
            finally:
                self._postgres_pool = None

        try:
            await self.graph_sync.close()
            await self.graph_sync.graph_client.close()
            logger.info("Graph sync resources closed")
        except Exception as e:
            logger.error(f"Error closing graph sync resources: {e}")
            errors.append(f"GraphSync: {e}")
        
        # Close indexer connections
        if self.indexer:
            try:
                await self.indexer.close()
                logger.info("Indexer closed")
            except Exception as e:
                logger.error(f"Error closing indexer: {e}")
                errors.append(f"Indexer: {e}")
        
        if errors:
            logger.warning(f"Errors during cleanup: {errors}")
