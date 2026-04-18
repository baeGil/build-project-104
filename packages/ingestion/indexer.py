"""Document Indexer for Vector and Full-Text Search.

This module handles indexing of parsed legal documents into:
- Qdrant (vector search with dense embeddings)
- OpenSearch (full-text BM25 and hybrid search)
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
from typing import Any, Callable

from packages.common.config import Settings
from packages.common.types import LegalNode

logger = logging.getLogger(__name__)


def chunk_document(
    title: str,
    content: str,
    chunk_size_tokens: int = 400,
    chunk_overlap: float = 0.5,
    min_chunk_tokens: int = 100,
) -> list[dict]:
    """Split document into overlapping chunks using Vietnamese sentence boundaries.

    Args:
        title: Document title (prepended to each chunk for context)
        content: Document content to chunk
        chunk_size_tokens: Target chunk size in tokens (approximated by words)
        chunk_overlap: Overlap ratio between chunks (0.0-1.0)
        min_chunk_tokens: Minimum chunk size to trigger chunking

    Returns:
        List of dicts: [{"text": str, "chunk_index": int, "start_char": int, "end_char": int}]
        Returns empty list if content is shorter than min_chunk_tokens.
    """
    # Approximate token count by word count (Vietnamese: ~1.3 tokens/word)
    words = content.split()
    approx_tokens = len(words) * 1.3

    if approx_tokens < min_chunk_tokens:
        # Document is short enough, no chunking needed
        return []

    # Vietnamese sentence boundary detection: split on ., \n, ; followed by whitespace
    # This pattern captures sentence-ending punctuation in Vietnamese legal texts
    sentence_pattern = r'(?<=[.\n;])\s+'
    sentences = re.split(sentence_pattern, content)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return []

    # Calculate chunk parameters (convert tokens to approximate words)
    chunk_size_words = int(chunk_size_tokens / 1.3)
    overlap_words = int(chunk_size_words * chunk_overlap)
    stride_words = chunk_size_words - overlap_words

    chunks = []
    current_chunk_sentences = []
    current_chunk_word_count = 0
    chunk_index = 0
    start_char = 0

    for sentence in sentences:
        sentence_word_count = len(sentence.split())

        if current_chunk_word_count + sentence_word_count <= chunk_size_words:
            # Add sentence to current chunk
            current_chunk_sentences.append(sentence)
            current_chunk_word_count += sentence_word_count
        else:
            # Finalize current chunk
            if current_chunk_sentences:
                chunk_text = " ".join(current_chunk_sentences)
                end_char = start_char + len(chunk_text)
                # Prepend title for embedding context
                full_text = f"{title}\n{chunk_text}" if title else chunk_text
                chunks.append({
                    "text": full_text,
                    "chunk_index": chunk_index,
                    "start_char": start_char,
                    "end_char": end_char,
                    "content": chunk_text,  # Store original chunk content without title
                })
                chunk_index += 1

                # Calculate overlap for next chunk
                # Keep last N sentences that fit within overlap budget
                overlap_sentences = []
                overlap_word_count = 0
                for s in reversed(current_chunk_sentences):
                    s_word_count = len(s.split())
                    if overlap_word_count + s_word_count <= overlap_words:
                        overlap_sentences.insert(0, s)
                        overlap_word_count += s_word_count
                    else:
                        break

                # Start new chunk with overlap sentences + current sentence
                current_chunk_sentences = overlap_sentences + [sentence]
                current_chunk_word_count = overlap_word_count + sentence_word_count
                start_char = end_char - len(" ".join(overlap_sentences)) if overlap_sentences else end_char

    # Don't forget the last chunk
    if current_chunk_sentences:
        chunk_text = " ".join(current_chunk_sentences)
        end_char = start_char + len(chunk_text)
        full_text = f"{title}\n{chunk_text}" if title else chunk_text
        chunks.append({
            "text": full_text,
            "chunk_index": chunk_index,
            "start_char": start_char,
            "end_char": end_char,
            "content": chunk_text,
        })

    return chunks

# Prevent transformers from probing TensorFlow at import time.
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")
os.environ.setdefault("USE_TF", "0")


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
        except (
            ConnectionError,
            TimeoutError,
            OSError,
            ConnectionResetError,
            BrokenPipeError,
        ) as e:
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
            # Check if it's a retryable error message
            error_str = str(e).lower()
            if any(x in error_str for x in ["connection reset", "timeout", "timed out", "broken pipe"]):
                last_exception = e
                if attempt < max_retries:
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                    logger.warning(
                        f"{operation_name} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                    continue
            # Non-retryable exceptions
            logger.error(f"{operation_name} failed with non-retryable error: {e}")
            raise
    
    raise last_exception


class QdrantIndexer:
    """Manages Qdrant collection for vector search.

    Handles embedding generation and upserts documents with metadata payloads.
    Uses sentence-transformers with Vietnamese legal embedding models.
    """

    def __init__(
        self,
        settings: Settings,
        batch_size: int = 50,
        connect_timeout: int = 10,
        request_timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        """Initialize the Qdrant indexer.

        Args:
            settings: Application settings containing Qdrant configuration.
            batch_size: Batch size for upsert operations (default: 50).
            connect_timeout: Connection timeout in seconds (default: 10).
            request_timeout: Request timeout in seconds (default: 30).
            max_retries: Maximum retry attempts for transient failures (default: 3).
        """
        self.settings = settings
        self._client: Any = None
        self._embedding_model: Any = None
        self._batch_size = batch_size
        self._connect_timeout = connect_timeout
        self._request_timeout = request_timeout
        self._max_retries = max_retries

    async def _get_client(self) -> Any:
        """Get or create Qdrant client with connection pool reuse.

        Returns:
            Qdrant client instance.
        """
        if self._client is None:
            try:
                from qdrant_client import QdrantClient

                self._client = QdrantClient(
                    host=self.settings.qdrant_host,
                    port=self.settings.qdrant_port,
                    timeout=self._request_timeout,
                )
                logger.info(f"Created Qdrant client (timeout: {self._request_timeout}s)")
            except ImportError as e:
                logger.error(f"qdrant-client not installed: {e}")
                logger.error(f"Python executable: {__import__('sys').executable}")
                logger.error(f"Python path: {__import__('sys').path[:3]}")
                raise
            except Exception as e:
                logger.error(f"Failed to create Qdrant client: {type(e).__name__}: {e}")
                raise
        return self._client

    async def _get_embedding_model(self) -> Any:
        """Get or load embedding model with GPU acceleration.
        
        Device priority: CUDA > MPS (Apple Silicon) > CPU

        Returns:
            SentenceTransformer model instance.
        """
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                import torch

                logger.info(f"Loading embedding model: {self.settings.embedding_model}")
                
                # Determine best available device
                if torch.cuda.is_available():
                    device = 'cuda'
                    device_name = torch.cuda.get_device_name(0)
                    logger.info(f"✓ Using GPU (CUDA): {device_name}")
                elif torch.backends.mps.is_available():
                    device = 'mps'
                    device_name = 'Apple Silicon GPU (MPS)'
                    logger.info(f"✓ Using GPU (MPS): {device_name}")
                else:
                    device = 'cpu'
                    device_name = 'CPU'
                    logger.info(f"⚠️  Using CPU (no GPU available)")
                
                # Print device info
                logger.info(f"📊 Device: {device.upper()} | PyTorch {torch.__version__}")
                
                self._embedding_model = SentenceTransformer(
                    self.settings.embedding_model,
                    device=device
                )
                
                # Print model info
                max_seq_length = self._embedding_model.max_seq_length
                embedding_dim = self._embedding_model.get_embedding_dimension()
                logger.info(f"📝 Model: {self.settings.embedding_model}")
                logger.info(f"📏 Embedding dim: {embedding_dim} | Max seq length: {max_seq_length}")
                
            except ImportError:
                logger.error("sentence-transformers not installed")
                raise
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise
        return self._embedding_model

    async def ensure_collection(self) -> None:
        """Create Qdrant collection if it doesn't exist.

        Creates collection with:
        - Vector size from settings (default 768)
        - Cosine distance metric
        - HNSW index configuration for efficient search
        """
        client = await self._get_client()
        collection_name = self.settings.qdrant_collection

        try:
            # Check if collection exists
            collections = client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if collection_name not in collection_names:
                logger.info(f"Creating Qdrant collection: {collection_name}")

                from qdrant_client.models import (
                    Distance,
                    HnswConfigDiff,
                    VectorParams,
                )

                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.settings.embedding_dim,
                        distance=Distance.COSINE,
                    ),
                    hnsw_config=HnswConfigDiff(
                        m=16,
                        ef_construct=100,
                    ),
                )
                logger.info(f"Created collection '{collection_name}' with {self.settings.embedding_dim}d vectors")
            else:
                logger.debug(f"Collection '{collection_name}' already exists")
        except Exception as e:
            logger.error(f"Failed to ensure Qdrant collection: {e}")
            raise

    async def index_documents(
        self,
        nodes: list[LegalNode],
        batch_size: int | None = None,
        relationship_metadata: dict[str, dict[str, Any]] | None = None,
    ) -> int:
        """Batch embed and upsert documents into Qdrant.

        Args:
            nodes: List of LegalNode objects to index.
            batch_size: Batch size for upsert operations (uses instance default if None).
            relationship_metadata: Optional dict mapping doc_id to relationship metadata:
                {"doc_id": {"related_doc_ids": [...], "relationship_types": [...], "related_doc_count": N}}

        Returns:
            Number of documents successfully indexed (including chunks).
        """
        if not nodes:
            return 0

        client = await self._get_client()
        model = await self._get_embedding_model()
        collection_name = self.settings.qdrant_collection
        batch_size = batch_size or self._batch_size

        # Get chunking parameters from config
        chunk_size_tokens = getattr(self.settings, 'search_chunk_size_tokens', 400)
        chunk_overlap = getattr(self.settings, 'search_chunk_overlap', 0.5)
        min_chunk_tokens = getattr(self.settings, 'search_min_chunk_tokens', 100)

        # Ensure collection exists
        await self.ensure_collection()

        indexed_count = 0

        try:
            from qdrant_client.models import PointStruct

            # Process in batches
            for i in range(0, len(nodes), batch_size):
                batch = nodes[i : i + batch_size]

                # Prepare texts and chunk info for embedding
                # Each item: (text, node, is_chunk, chunk_info)
                items_to_embed = []
                for node in batch:
                    # Check if document should be chunked
                    chunks = chunk_document(
                        title=node.title,
                        content=node.content,
                        chunk_size_tokens=chunk_size_tokens,
                        chunk_overlap=chunk_overlap,
                        min_chunk_tokens=min_chunk_tokens,
                    )

                    # Get original doc ID
                    if node.id.isdigit():
                        original_doc_id = int(node.id)
                    elif "_article_" in node.id:
                        try:
                            parts = node.id.split("_article_")
                            doc_id_part = parts[0]
                            article_num_part = parts[1]
                            if doc_id_part.isdigit() and article_num_part.isdigit():
                                original_doc_id = int(doc_id_part) * 10000 + int(article_num_part)
                            else:
                                original_doc_id = hash(node.id) % 1000000000
                        except Exception:
                            original_doc_id = hash(node.id) % 1000000000
                    else:
                        original_doc_id = node.id

                    if chunks:
                        # Add chunks for embedding
                        for chunk in chunks:
                            items_to_embed.append((
                                chunk["text"],
                                node,
                                True,  # is_chunk
                                {
                                    "chunk_index": chunk["chunk_index"],
                                    "chunk_content": chunk["content"],
                                    "original_doc_id": original_doc_id,
                                }
                            ))

                    # Always add the original full document (backward compatibility)
                    items_to_embed.append((
                        f"{node.title}\n{node.content}",
                        node,
                        False,  # is_chunk
                        {"original_doc_id": original_doc_id}
                    ))

                # Generate embeddings for all items
                texts = [item[0] for item in items_to_embed]
                logger.debug(f"Generating embeddings for batch {i//batch_size + 1} ({len(texts)} items)")
                embeddings = model.encode(texts, show_progress_bar=False)

                # Prepare points for upsert
                points = []
                for (text, node, is_chunk, chunk_info), embedding in zip(items_to_embed, embeddings):
                    original_doc_id = chunk_info["original_doc_id"]

                    # Build base payload
                    payload = {
                        "title": node.title,
                        "doc_type": node.doc_type.value,
                        "level": node.level,
                        "parent_id": node.parent_id,
                        "children_ids": node.children_ids,
                        "publish_date": node.publish_date.isoformat() if node.publish_date else None,
                        "effective_date": node.effective_date.isoformat() if node.effective_date else None,
                        "issuing_body": node.issuing_body,
                        "document_number": node.document_number,
                        "law_id": node.law_id,
                        "amendment_refs": node.amendment_refs,
                        "citation_refs": node.citation_refs,
                        "keywords": node.keywords,
                    }

                    if is_chunk:
                        # Chunk-specific fields
                        chunk_index = chunk_info["chunk_index"]
                        qdrant_id = original_doc_id * 100000 + chunk_index
                        payload.update({
                            "content": chunk_info["chunk_content"],
                            "chunk_type": "chunk",
                            "chunk_index": chunk_index,
                            "doc_id": original_doc_id,
                            "parent_doc_id": original_doc_id,
                            "article_number": node.metadata.get("article_number"),
                        })
                    else:
                        # Full document fields - use original_doc_id as qdrant_id
                        qdrant_id = original_doc_id
                        payload.update({
                            "content": node.content,
                            "chunk_type": node.metadata.get('chunk_type', 'article' if node.level == 2 else 'document'),
                            "article_number": node.metadata.get('article_number', int(node.id.split("_")[-1]) if node.level == 2 and "_article_" in node.id else None),
                            "parent_doc_id": node.metadata.get('parent_doc_id', node.parent_id if node.level == 2 else None),
                        })

                    # Enrich with relationship metadata if provided
                    if relationship_metadata and node.id in relationship_metadata:
                        rel_meta = relationship_metadata[node.id]
                        payload["related_doc_ids"] = rel_meta.get("related_doc_ids", [])
                        payload["relationship_types"] = rel_meta.get("relationship_types", [])
                        payload["related_doc_count"] = rel_meta.get("related_doc_count", 0)

                    points.append(
                        PointStruct(
                            id=qdrant_id,
                            vector=embedding.tolist(),
                            payload=payload,
                        )
                    )

                # Upsert to Qdrant with retry
                async def _do_upsert():
                    client.upsert(
                        collection_name=collection_name,
                        points=points,
                    )

                await _retry_with_backoff(
                    _do_upsert,
                    max_retries=self._max_retries,
                    operation_name=f"Qdrant upsert batch {i//batch_size + 1}",
                )

                indexed_count += len(points)
                logger.debug(f"Indexed batch of {len(points)} points ({len(batch)} documents + chunks)")

            logger.info(f"Successfully indexed {indexed_count} points to Qdrant")
            return indexed_count

        except Exception as e:
            logger.error(f"Failed to index documents to Qdrant: {e}")
            raise

    async def delete_collection(self) -> None:
        """Delete the Qdrant collection."""
        client = await self._get_client()
        collection_name = self.settings.qdrant_collection

        try:
            client.delete_collection(collection_name=collection_name)
            logger.info(f"Deleted Qdrant collection: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to delete Qdrant collection: {e}")
            raise

    async def close(self) -> None:
        """Close Qdrant client connection."""
        if self._client is not None:
            try:
                self._client.close()
                logger.info("Qdrant client closed")
            except Exception as e:
                logger.warning(f"Error closing Qdrant client: {e}")
            finally:
                self._client = None


class OpenSearchIndexer:
    """Manages OpenSearch index for full-text BM25 search.

    Handles bulk indexing with Vietnamese-optimized text analysis.
    """

    def __init__(
        self,
        settings: Settings,
        batch_size: int = 100,
        connect_timeout: int = 10,
        request_timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        """Initialize the OpenSearch indexer.

        Args:
            settings: Application settings containing OpenSearch configuration.
            batch_size: Batch size for bulk operations (default: 100).
            connect_timeout: Connection timeout in seconds (default: 10).
            request_timeout: Request timeout in seconds (default: 30).
            max_retries: Maximum retry attempts for transient failures (default: 3).
        """
        self.settings = settings
        self._client: Any = None
        self._batch_size = batch_size
        self._connect_timeout = connect_timeout
        self._request_timeout = request_timeout
        self._max_retries = max_retries

    async def _get_client(self) -> Any:
        """Get or create OpenSearch client with connection pool reuse.

        Returns:
            OpenSearch client instance.
        """
        if self._client is None:
            try:
                from opensearchpy import OpenSearch

                self._client = OpenSearch(
                    hosts=[{
                        "host": self.settings.opensearch_host,
                        "port": self.settings.opensearch_port,
                    }],
                    http_auth=(
                        self.settings.opensearch_user,
                        self.settings.opensearch_password,
                    ),
                    use_ssl=self.settings.opensearch_use_ssl,
                    verify_certs=self.settings.opensearch_verify_certs,
                    timeout=self._request_timeout,
                    max_retries=0,  # We handle retries ourselves
                    retry_on_timeout=False,
                )
                logger.info(f"Created OpenSearch client (timeout: {self._request_timeout}s)")
            except ImportError as e:
                logger.error(f"opensearch-py not installed: {e}")
                logger.error(f"Python executable: {__import__('sys').executable}")
                logger.error(f"Python path: {__import__('sys').path[:3]}")
                raise
            except Exception as e:
                logger.error(f"Failed to create OpenSearch client: {type(e).__name__}: {e}")
                raise
        return self._client

    async def ensure_index(self) -> None:
        """Create OpenSearch index with Vietnamese-optimized mappings.

        Creates index with:
        - Vietnamese analyzer for text fields
        - Keyword fields for exact matching
        - Date fields for temporal filtering
        """
        client = await self._get_client()
        index_name = self.settings.opensearch_index

        try:
            # Check if index exists
            if not client.indices.exists(index=index_name):
                logger.info(f"Creating OpenSearch index: {index_name}")

                index_body = {
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                        "analysis": {
                            "analyzer": {
                                "vietnamese_analyzer": {
                                    "type": "custom",
                                    "tokenizer": "standard",
                                    "filter": [
                                        "lowercase",
                                        "asciifolding",
                                    ],
                                },
                            },
                        },
                    },
                    "mappings": {
                        "properties": {
                            "title": {
                                "type": "text",
                                "analyzer": "vietnamese_analyzer",
                                "fields": {
                                    "keyword": {"type": "keyword"},
                                },
                            },
                            "content": {
                                "type": "text",
                                "analyzer": "vietnamese_analyzer",
                            },
                            "doc_type": {"type": "keyword"},
                            "level": {"type": "integer"},
                            "publish_date": {"type": "date"},
                            "effective_date": {"type": "date"},
                            "expiry_date": {"type": "date"},
                            "issuing_body": {
                                "type": "text",
                                "fields": {
                                    "keyword": {"type": "keyword"},
                                },
                            },
                            "document_number": {"type": "keyword"},
                            "law_id": {"type": "keyword"},  # Explicit keyword mapping for exact matching
                            "keywords": {"type": "keyword"},
                            "parent_id": {"type": "keyword"},
                            "children_ids": {"type": "keyword"},
                            "amendment_refs": {"type": "keyword"},
                            "citation_refs": {"type": "keyword"},
                            # Relationship metadata fields
                            "related_doc_ids": {"type": "keyword"},
                            "relationship_types": {"type": "keyword"},
                            "related_doc_count": {"type": "integer"},
                            # Chunk metadata fields
                            "chunk_type": {"type": "keyword"},
                            "chunk_index": {"type": "integer"},
                            "parent_doc_id": {"type": "keyword"},
                        },
                    },
                }

                client.indices.create(index=index_name, body=index_body)
                logger.info(f"Created OpenSearch index: {index_name}")
            else:
                logger.debug(f"OpenSearch index '{index_name}' already exists")
        except Exception as e:
            logger.error(f"Failed to ensure OpenSearch index: {e}")
            raise

    async def index_documents(
        self,
        nodes: list[LegalNode],
        batch_size: int | None = None,
        relationship_metadata: dict[str, dict[str, Any]] | None = None,
    ) -> int:
        """Bulk index documents into OpenSearch.

        Args:
            nodes: List of LegalNode objects to index.
            batch_size: Batch size for bulk operations (uses instance default if None).
            relationship_metadata: Optional dict mapping doc_id to relationship metadata:
                {"doc_id": {"related_doc_ids": [...], "relationship_types": [...], "related_doc_count": N}}

        Returns:
            Number of documents successfully indexed (including chunks).
        """
        if not nodes:
            return 0

        client = await self._get_client()
        index_name = self.settings.opensearch_index
        batch_size = batch_size or self._batch_size

        # Get chunking parameters from config
        chunk_size_tokens = getattr(self.settings, 'search_chunk_size_tokens', 400)
        chunk_overlap = getattr(self.settings, 'search_chunk_overlap', 0.5)
        min_chunk_tokens = getattr(self.settings, 'search_min_chunk_tokens', 100)

        # Ensure index exists
        await self.ensure_index()

        indexed_count = 0

        try:
            from opensearchpy.helpers import bulk

            def generate_actions():
                for node in nodes:
                    # Check if document should be chunked
                    chunks = chunk_document(
                        title=node.title,
                        content=node.content,
                        chunk_size_tokens=chunk_size_tokens,
                        chunk_overlap=chunk_overlap,
                        min_chunk_tokens=min_chunk_tokens,
                    )

                    # Build base source for both chunks and full document
                    def build_source(content: str, is_chunk: bool = False, chunk_index: int | None = None) -> dict:
                        source = {
                            "title": node.title,
                            "content": content,
                            "doc_type": node.doc_type.value,
                            "level": node.level,
                            "publish_date": node.publish_date.isoformat() if node.publish_date else None,
                            "effective_date": node.effective_date.isoformat() if node.effective_date else None,
                            "expiry_date": node.expiry_date.isoformat() if node.expiry_date else None,
                            "issuing_body": node.issuing_body,
                            "document_number": node.document_number,
                            "law_id": node.law_id,
                            "keywords": node.keywords,
                            "parent_id": node.parent_id,
                            "children_ids": node.children_ids,
                            "amendment_refs": node.amendment_refs,
                            "citation_refs": node.citation_refs,
                        }

                        if is_chunk:
                            source.update({
                                "chunk_type": "chunk",
                                "chunk_index": chunk_index,
                                "parent_doc_id": node.id,
                                "article_number": node.metadata.get("article_number"),
                            })
                        else:
                            source.update({
                                "chunk_type": node.metadata.get('chunk_type', 'article' if node.level == 2 else 'document'),
                                "article_number": node.metadata.get('article_number', int(node.id.split("_")[-1]) if node.level == 2 and "_article_" in node.id else None),
                                "parent_doc_id": node.metadata.get('parent_doc_id', node.parent_id if node.level == 2 else None),
                            })

                        # Enrich with relationship metadata if provided
                        if relationship_metadata and node.id in relationship_metadata:
                            rel_meta = relationship_metadata[node.id]
                            source["related_doc_ids"] = rel_meta.get("related_doc_ids", [])
                            source["relationship_types"] = rel_meta.get("relationship_types", [])
                            source["related_doc_count"] = rel_meta.get("related_doc_count", 0)

                        return source

                    # Yield chunks if document was chunked
                    if chunks:
                        for chunk in chunks:
                            chunk_id = f"{node.id}_chunk_{chunk['chunk_index']}"
                            yield {
                                "_index": index_name,
                                "_id": chunk_id,
                                "_source": build_source(chunk["content"], is_chunk=True, chunk_index=chunk["chunk_index"]),
                            }

                    # Always yield the original full document (backward compatibility)
                    yield {
                        "_index": index_name,
                        "_id": node.id,
                        "_source": build_source(node.content, is_chunk=False),
                    }

            # Perform bulk indexing with retry
            async def _do_bulk():
                def _bulk_op():
                    return bulk(
                        client,
                        generate_actions(),
                        chunk_size=batch_size,
                        raise_on_error=False,
                    )
                return await asyncio.to_thread(_bulk_op)

            success, errors = await _retry_with_backoff(
                _do_bulk,
                max_retries=self._max_retries,
                operation_name="OpenSearch bulk index",
            )

            indexed_count = success

            if errors:
                logger.warning(f"{len(errors)} documents failed to index to OpenSearch")

            logger.info(f"Successfully indexed {indexed_count} documents to OpenSearch")
            return indexed_count

        except Exception as e:
            logger.error(f"Failed to index documents to OpenSearch: {e}")
            raise

    async def delete_index(self) -> None:
        """Delete the OpenSearch index."""
        client = await self._get_client()
        index_name = self.settings.opensearch_index

        try:
            client.indices.delete(index=index_name, ignore=[404])
            logger.info(f"Deleted OpenSearch index: {index_name}")
        except Exception as e:
            logger.error(f"Failed to delete OpenSearch index: {e}")
            raise

    async def close(self) -> None:
        """Close OpenSearch client connection."""
        if self._client is not None:
            try:
                self._client.close()
                logger.info("OpenSearch client closed")
            except Exception as e:
                logger.warning(f"Error closing OpenSearch client: {e}")
            finally:
                self._client = None


class DocumentIndexer:
    """Indexer for legal documents.

    Indexes documents into multiple backends:
    - Qdrant: Dense vector embeddings for semantic search
    - OpenSearch: Sparse BM25 and hybrid search

    Also handles embedding generation using Vietnamese legal embedding models.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        qdrant_batch_size: int = 50,
        opensearch_batch_size: int = 100,
        connect_timeout: int = 10,
        request_timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        """Initialize the document indexer.

        Args:
            settings: Optional application settings. If not provided,
                     will load from environment.
            qdrant_batch_size: Batch size for Qdrant upsert operations.
            opensearch_batch_size: Batch size for OpenSearch bulk operations.
            connect_timeout: Connection timeout in seconds.
            request_timeout: Request timeout in seconds.
            max_retries: Maximum retry attempts for transient failures.
        """
        if settings is None:
            from packages.common.config import get_settings

            settings = get_settings()

        self.settings = settings
        self.qdrant_indexer = QdrantIndexer(
            settings,
            batch_size=qdrant_batch_size,
            connect_timeout=connect_timeout,
            request_timeout=request_timeout,
            max_retries=max_retries,
        )
        self.opensearch_indexer = OpenSearchIndexer(
            settings,
            batch_size=opensearch_batch_size,
            connect_timeout=connect_timeout,
            request_timeout=request_timeout,
            max_retries=max_retries,
        )

    async def index(
        self,
        documents: list[LegalNode],
        relationship_metadata: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Index a batch of documents into all backends.

        Args:
            documents: List of parsed and normalized LegalNode documents.
            relationship_metadata: Optional dict mapping doc_id to relationship metadata:
                {"doc_id": {"related_doc_ids": [...], "relationship_types": [...], "related_doc_count": N}}

        Returns:
            Indexing result with success/failure counts per backend.
        """
        if not documents:
            return {
                "total_documents": 0,
                "qdrant_indexed": 0,
                "opensearch_indexed": 0,
                "errors": [],
            }

        result = {
            "total_documents": len(documents),
            "qdrant_indexed": 0,
            "opensearch_indexed": 0,
            "errors": [],
        }

        # Index to Qdrant
        try:
            result["qdrant_indexed"] = await self.qdrant_indexer.index_documents(
                documents, relationship_metadata=relationship_metadata
            )
            logger.info(f"✓ Qdrant indexing successful: {result['qdrant_indexed']} docs")
        except ImportError as e:
            logger.warning(f"⚠️  Qdrant skipped (not installed): {e}")
            result["qdrant_indexed"] = 0
            result["warnings"] = result.get("warnings", []) + [f"Qdrant not available: {str(e)}"]
        except Exception as e:
            logger.error(f"❌ Qdrant indexing failed: {type(e).__name__}: {e}")
            result["errors"] = result.get("errors", []) + [f"Qdrant: {str(e)}"]

        # Index to OpenSearch
        try:
            result["opensearch_indexed"] = await self.opensearch_indexer.index_documents(
                documents, relationship_metadata=relationship_metadata
            )
            logger.info(f"✓ OpenSearch indexing successful: {result['opensearch_indexed']} docs")
        except ImportError as e:
            logger.warning(f"⚠️  OpenSearch skipped (not installed): {e}")
            result["opensearch_indexed"] = 0
            result["warnings"] = result.get("warnings", []) + [f"OpenSearch not available: {str(e)}"]
        except Exception as e:
            logger.error(f"❌ OpenSearch indexing failed: {type(e).__name__}: {e}")
            result["errors"] = result.get("errors", []) + [f"OpenSearch: {str(e)}"]

        return result

    async def index_legal_corpus(self, nodes: list[LegalNode]) -> dict[str, Any]:
        """Index legal corpus into both Qdrant and OpenSearch.

        This is an alias for the index() method for clarity.

        Args:
            nodes: List of LegalNode objects to index.

        Returns:
            Dictionary with indexing statistics.
        """
        return await self.index(nodes)

    async def delete(self, doc_ids: list[str]) -> dict[str, Any]:
        """Delete documents from all indexes.

        Args:
            doc_ids: List of document IDs to delete.

        Returns:
            Deletion result.
        """
        if not doc_ids:
            return {
                "total_documents": 0,
                "qdrant_deleted": 0,
                "opensearch_deleted": 0,
                "errors": [],
            }

        result = {
            "total_documents": len(doc_ids),
            "qdrant_deleted": 0,
            "opensearch_deleted": 0,
            "errors": [],
        }

        async def delete_qdrant() -> None:
            try:
                client = await self.qdrant_indexer._get_client()
                collection_name = self.settings.qdrant_collection

                def _delete() -> int:
                    collections = client.get_collections()
                    collection_names = [c.name for c in collections.collections]
                    if collection_name not in collection_names:
                        return 0

                    client.delete(
                        collection_name=collection_name,
                        points_selector=doc_ids,
                        wait=True,
                    )
                    return len(doc_ids)

                result["qdrant_deleted"] = await asyncio.to_thread(_delete)
            except Exception as e:
                logger.error(f"Qdrant deletion failed: {e}")
                result["errors"].append(f"Qdrant: {str(e)}")

        async def delete_opensearch() -> None:
            try:
                client = await self.opensearch_indexer._get_client()
                index_name = self.settings.opensearch_index

                def _delete() -> int:
                    if not client.indices.exists(index=index_name):
                        return 0

                    from opensearchpy.helpers import bulk

                    def generate_actions():
                        for doc_id in doc_ids:
                            yield {
                                "_op_type": "delete",
                                "_index": index_name,
                                "_id": doc_id,
                            }

                    success, errors = bulk(
                        client,
                        generate_actions(),
                        chunk_size=1000,
                        raise_on_error=False,
                    )
                    if errors:
                        logger.warning(f"{len(errors)} documents failed to delete from OpenSearch")
                    return success

                result["opensearch_deleted"] = await asyncio.to_thread(_delete)
            except Exception as e:
                logger.error(f"OpenSearch deletion failed: {e}")
                result["errors"].append(f"OpenSearch: {str(e)}")

        await asyncio.gather(delete_qdrant(), delete_opensearch())
        return result

    async def close(self) -> None:
        """Close all indexer connections."""
        errors = []
        
        try:
            await self.qdrant_indexer.close()
        except Exception as e:
            logger.error(f"Error closing Qdrant indexer: {e}")
            errors.append(f"Qdrant: {e}")
        
        try:
            await self.opensearch_indexer.close()
        except Exception as e:
            logger.error(f"Error closing OpenSearch indexer: {e}")
            errors.append(f"OpenSearch: {e}")
        
        if errors:
            logger.warning(f"Errors during indexer cleanup: {errors}")
