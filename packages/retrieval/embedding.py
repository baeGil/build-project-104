"""Embedding service for Vietnamese legal text."""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Manages the Vietnamese legal embedding model.

    Uses Quockhanh05/Vietnam_legal_embeddings (768d).
    Supports batch encoding for efficiency.
    """

    _instance = None  # Singleton to avoid loading model multiple times

    def __init__(self, model_name: str = "Quockhanh05/Vietnam_legal_embeddings"):
        """Initialize the embedding service.

        Args:
            model_name: Name of the HuggingFace embedding model
        """
        self.model_name = model_name
        self._model = None  # Lazy loading
        self._embedding_dim = 768  # Expected dimension for Vietnam_legal_embeddings

    def _load_model(self) -> Any:
        """Lazy load the embedding model.

        Returns:
            The loaded embedding model
        """
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading embedding model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                self._embedding_dim = self._model.get_sentence_embedding_dimension()
                logger.info(f"Embedding model loaded. Dimension: {self._embedding_dim}")
            except ImportError as e:
                logger.error(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
                raise ImportError(
                    "sentence-transformers is required for embedding generation"
                ) from e
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise

        return self._model

    def encode(
        self,
        texts: str | list[str],
        batch_size: int = 64,
        normalize: bool = True,
    ) -> list[list[float]]:
        """Encode text(s) into embeddings.

        Args:
            texts: Single text or list of texts to encode
            batch_size: Batch size for encoding
            normalize: Whether to L2-normalize embeddings

        Returns:
            List of embedding vectors
        """
        model = self._load_model()

        # Ensure texts is a list
        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return []

        try:
            # Generate embeddings
            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=normalize,
                show_progress_bar=False,
                convert_to_numpy=True,
            )

            # Convert to list of lists
            return embeddings.tolist()

        except Exception as e:
            logger.error(f"Error encoding texts: {e}")
            raise

    def encode_query(self, query: str, normalize: bool = True) -> list[float]:
        """Encode a single query.

        Args:
            query: Query text to encode
            normalize: Whether to L2-normalize the embedding

        Returns:
            Query embedding vector
        """
        embeddings = self.encode(query, batch_size=1, normalize=normalize)
        return embeddings[0]

    def encode_batch(
        self,
        texts: list[str],
        batch_size: int = 64,
        normalize: bool = True,
    ) -> list[list[float]]:
        """Encode a batch of texts.

        Args:
            texts: List of texts to encode
            batch_size: Batch size for encoding
            normalize: Whether to L2-normalize embeddings

        Returns:
            List of embedding vectors
        """
        return self.encode(texts, batch_size=batch_size, normalize=normalize)

    @property
    def embedding_dim(self) -> int:
        """Get the embedding dimension.

        Returns:
            Dimension of the embedding vectors
        """
        if self._model is None:
            return self._embedding_dim
        return self._model.get_sentence_embedding_dimension()

    @classmethod
    def get_instance(cls, model_name: str | None = None) -> "EmbeddingService":
        """Get singleton instance.

        Args:
            model_name: Optional model name to use (only used on first call)

        Returns:
            Singleton EmbeddingService instance
        """
        if cls._instance is None:
            cls._instance = cls(model_name=model_name or "Quockhanh05/Vietnam_legal_embeddings")
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (useful for testing)."""
        cls._instance = None
