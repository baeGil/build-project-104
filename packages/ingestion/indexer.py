"""Document Indexer for Vector and Full-Text Search.

This module handles indexing of parsed legal documents into:
- Qdrant (vector search with dense embeddings)
- OpenSearch (full-text BM25 and hybrid search)
"""

from __future__ import annotations

import logging
from typing import Any

from packages.common.config import Settings
from packages.common.types import LegalNode

logger = logging.getLogger(__name__)


class QdrantIndexer:
    """Manages Qdrant collection for vector search.

    Handles embedding generation and upserts documents with metadata payloads.
    Uses sentence-transformers with Vietnamese legal embedding models.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the Qdrant indexer.

        Args:
            settings: Application settings containing Qdrant configuration.
        """
        self.settings = settings
        self._client: Any = None
        self._embedding_model: Any = None

    async def _get_client(self) -> Any:
        """Get or create Qdrant client.

        Returns:
            Qdrant client instance.
        """
        if self._client is None:
            try:
                from qdrant_client import QdrantClient

                self._client = QdrantClient(
                    host=self.settings.qdrant_host,
                    port=self.settings.qdrant_port,
                )
            except ImportError:
                logger.error("qdrant-client not installed")
                raise
        return self._client

    async def _get_embedding_model(self) -> Any:
        """Get or load embedding model.

        Returns:
            SentenceTransformer model instance.
        """
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading embedding model: {self.settings.embedding_model}")
                self._embedding_model = SentenceTransformer(self.settings.embedding_model)
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

    async def index_documents(self, nodes: list[LegalNode], batch_size: int = 64) -> int:
        """Batch embed and upsert documents into Qdrant.

        Args:
            nodes: List of LegalNode objects to index.
            batch_size: Batch size for embedding generation.

        Returns:
            Number of documents successfully indexed.
        """
        if not nodes:
            return 0

        client = await self._get_client()
        model = await self._get_embedding_model()
        collection_name = self.settings.qdrant_collection

        # Ensure collection exists
        await self.ensure_collection()

        indexed_count = 0

        try:
            from qdrant_client.models import PointStruct

            # Process in batches
            for i in range(0, len(nodes), batch_size):
                batch = nodes[i : i + batch_size]

                # Prepare texts for embedding
                texts = [f"{node.title}\n{node.content}" for node in batch]

                # Generate embeddings
                logger.debug(f"Generating embeddings for batch {i//batch_size + 1}")
                embeddings = model.encode(texts, show_progress_bar=False)

                # Prepare points for upsert
                points = []
                for node, embedding in zip(batch, embeddings):
                    payload = {
                        "title": node.title,
                        "content": node.content,
                        "doc_type": node.doc_type.value,
                        "level": node.level,
                        "publish_date": node.publish_date.isoformat() if node.publish_date else None,
                        "effective_date": node.effective_date.isoformat() if node.effective_date else None,
                        "issuing_body": node.issuing_body,
                        "document_number": node.document_number,
                        "keywords": node.keywords,
                    }

                    points.append(
                        PointStruct(
                            id=node.id,
                            vector=embedding.tolist(),
                            payload=payload,
                        )
                    )

                # Upsert to Qdrant
                client.upsert(
                    collection_name=collection_name,
                    points=points,
                )

                indexed_count += len(batch)
                logger.debug(f"Indexed batch of {len(batch)} documents")

            logger.info(f"Successfully indexed {indexed_count} documents to Qdrant")
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


class OpenSearchIndexer:
    """Manages OpenSearch index for full-text BM25 search.

    Handles bulk indexing with Vietnamese-optimized text analysis.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the OpenSearch indexer.

        Args:
            settings: Application settings containing OpenSearch configuration.
        """
        self.settings = settings
        self._client: Any = None

    async def _get_client(self) -> Any:
        """Get or create OpenSearch client.

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
                    use_ssl=False,
                    verify_certs=False,
                )
            except ImportError:
                logger.error("opensearch-py not installed")
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
                            "keywords": {"type": "keyword"},
                            "parent_id": {"type": "keyword"},
                            "children_ids": {"type": "keyword"},
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

    async def index_documents(self, nodes: list[LegalNode], batch_size: int = 100) -> int:
        """Bulk index documents into OpenSearch.

        Args:
            nodes: List of LegalNode objects to index.
            batch_size: Batch size for bulk operations.

        Returns:
            Number of documents successfully indexed.
        """
        if not nodes:
            return 0

        client = await self._get_client()
        index_name = self.settings.opensearch_index

        # Ensure index exists
        await self.ensure_index()

        indexed_count = 0

        try:
            from opensearchpy.helpers import bulk

            def generate_actions():
                for node in nodes:
                    yield {
                        "_index": index_name,
                        "_id": node.id,
                        "_source": {
                            "title": node.title,
                            "content": node.content,
                            "doc_type": node.doc_type.value,
                            "level": node.level,
                            "publish_date": node.publish_date.isoformat() if node.publish_date else None,
                            "effective_date": node.effective_date.isoformat() if node.effective_date else None,
                            "expiry_date": node.expiry_date.isoformat() if node.expiry_date else None,
                            "issuing_body": node.issuing_body,
                            "document_number": node.document_number,
                            "keywords": node.keywords,
                            "parent_id": node.parent_id,
                            "children_ids": node.children_ids,
                            "amendment_refs": node.amendment_refs,
                            "citation_refs": node.citation_refs,
                        },
                    }

            # Perform bulk indexing
            success, errors = bulk(
                client,
                generate_actions(),
                chunk_size=batch_size,
                raise_on_error=False,
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


class DocumentIndexer:
    """Indexer for legal documents.

    Indexes documents into multiple backends:
    - Qdrant: Dense vector embeddings for semantic search
    - OpenSearch: Sparse BM25 and hybrid search

    Also handles embedding generation using Vietnamese legal embedding models.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the document indexer.

        Args:
            settings: Optional application settings. If not provided,
                     will load from environment.
        """
        if settings is None:
            from packages.common.config import get_settings

            settings = get_settings()

        self.settings = settings
        self.qdrant_indexer = QdrantIndexer(settings)
        self.opensearch_indexer = OpenSearchIndexer(settings)

    async def index(self, documents: list[LegalNode]) -> dict[str, Any]:
        """Index a batch of documents into all backends.

        Args:
            documents: List of parsed and normalized LegalNode documents.

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
            result["qdrant_indexed"] = await self.qdrant_indexer.index_documents(documents)
        except Exception as e:
            logger.error(f"Qdrant indexing failed: {e}")
            result["errors"].append(f"Qdrant: {str(e)}")

        # Index to OpenSearch
        try:
            result["opensearch_indexed"] = await self.opensearch_indexer.index_documents(documents)
        except Exception as e:
            logger.error(f"OpenSearch indexing failed: {e}")
            result["errors"].append(f"OpenSearch: {str(e)}")

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
        # TODO: Implement deletion logic
        raise NotImplementedError("Document deletion not yet implemented")
