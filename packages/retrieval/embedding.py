"""Embedding service for Vietnamese legal text."""

import gc
import logging
import os
from typing import Any, Generator, Iterator

import numpy as np

logger = logging.getLogger(__name__)

# Prevent transformers from probing TensorFlow at import time.
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")
os.environ.setdefault("USE_TF", "0")


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
                logger.info("This may take a while on first load (downloading model)...")
                
                # Try to load with extended retry and timeout handling
                try:
                    self._model = SentenceTransformer(
                        self.model_name,
                        trust_remote_code=True,
                    )
                except Exception as download_error:
                    # If download fails, try with local cache or provide better error
                    logger.warning(
                        f"Failed to download model from HuggingFace: {download_error}\n"
                        f"This could be due to:\n"
                        f"  1. Network connectivity issues to huggingface.co\n"
                        f"  2. HuggingFace server being temporarily unavailable\n"
                        f"  3. Firewall/proxy blocking access\n\n"
                        f"Solutions:\n"
                        f"  - Check your internet connection\n"
                        f"  - Try again in a few minutes\n"
                        f"  - Set HF_ENDPOINT=https://hf-mirror.com if in Asia\n"
                        f"  - Download model manually and use local path"
                    )
                    raise
                
                get_dim = getattr(self._model, "get_embedding_dimension", None)
                if get_dim is None:
                    get_dim = self._model.get_sentence_embedding_dimension
                self._embedding_dim = get_dim()
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
        # Ensure texts is a list
        if isinstance(texts, str):
            texts = [texts]

        # Check for empty list before loading model
        if not texts:
            return []

        model = self._load_model()

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

        except MemoryError:
            logger.error(
                f"Out of memory encoding {len(texts)} texts. "
                "Try using encode_batch_iter() for memory-efficient processing."
            )
            raise
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
        batch_size: int = 32,
        normalize: bool = True,
    ) -> list[list[float]]:
        """Encode a batch of texts with memory-efficient processing.

        This method processes texts in chunks to avoid memory issues with large batches.
        It's a drop-in replacement for encode() when you have a large list of texts.

        Args:
            texts: List of texts to encode
            batch_size: Batch size for encoding (default: 32 for better memory efficiency)
            normalize: Whether to L2-normalize embeddings

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        
        # Process in chunks to manage memory
        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            
            try:
                chunk_embeddings = self.encode(chunk, batch_size=batch_size, normalize=normalize)
                all_embeddings.extend(chunk_embeddings)
                
                # Clear memory after each chunk
                if i + batch_size < len(texts):
                    gc.collect()
                    
            except MemoryError:
                # Try with smaller batch size
                smaller_batch = max(1, batch_size // 2)
                logger.warning(
                    f"Memory error at batch {i//batch_size + 1}. "
                    f"Retrying with batch_size={smaller_batch}"
                )
                
                if smaller_batch < batch_size:
                    # Recursively process with smaller batch
                    chunk_embeddings = self.encode_batch(
                        chunk,
                        batch_size=smaller_batch,
                        normalize=normalize,
                    )
                    all_embeddings.extend(chunk_embeddings)
                else:
                    raise
        
        return all_embeddings

    def encode_batch_iter(
        self,
        texts: list[str],
        batch_size: int = 32,
        normalize: bool = True,
    ) -> Iterator[list[list[float]]]:
        """Memory-efficient batch encoding that yields embeddings in chunks.

        This generator yields embeddings in batches rather than holding all
        in memory, making it suitable for very large datasets.

        Args:
            texts: List of texts to encode
            batch_size: Batch size for encoding (default: 32)
            normalize: Whether to L2-normalize embeddings

        Yields:
            Lists of embedding vectors, one batch at a time

        Example:
            >>> service = EmbeddingService()
            >>> for batch_embeddings in service.encode_batch_iter(texts, batch_size=32):
            ...     # Process batch_embeddings without holding all in memory
            ...     process_batch(batch_embeddings)
        """
        if not texts:
            return
        
        model = self._load_model()
        total_batches = (len(texts) + batch_size - 1) // batch_size
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(texts))
            batch_texts = texts[start_idx:end_idx]
            
            try:
                # Generate embeddings for this batch
                embeddings = model.encode(
                    batch_texts,
                    batch_size=len(batch_texts),  # Process whole batch at once
                    normalize_embeddings=normalize,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                )
                
                # Yield as list of lists
                yield embeddings.tolist()
                
                # Clear memory after yielding
                del embeddings
                gc.collect()
                
            except MemoryError as e:
                logger.error(
                    f"Out of memory encoding batch {batch_idx + 1}/{total_batches} "
                    f"({len(batch_texts)} texts). Try smaller batch_size."
                )
                raise MemoryError(
                    f"Out of memory processing batch {batch_idx + 1}. "
                    f"Current batch_size={batch_size}. Try a smaller value."
                ) from e
            except Exception as e:
                logger.error(f"Error encoding batch {batch_idx + 1}: {e}")
                raise

    def encode_stream(
        self,
        texts: Iterator[str],
        batch_size: int = 32,
        normalize: bool = True,
    ) -> Generator[tuple[int, list[float]], None, None]:
        """Stream process texts and yield (index, embedding) tuples.

        This method processes texts from an iterator and yields results
        as they become available, useful for processing very large datasets
        that don't fit in memory.

        Args:
            texts: Iterator of texts to encode
            batch_size: Batch size for encoding (default: 32)
            normalize: Whether to L2-normalize embeddings

        Yields:
            Tuples of (global_index, embedding_vector)

        Example:
            >>> service = EmbeddingService()
            >>> text_iterator = get_large_text_stream()  # yields one text at a time
            >>> for idx, embedding in service.encode_stream(text_iterator, batch_size=50):
            ...     print(f"Processed text {idx}: embedding shape = {len(embedding)}")
        """
        model = self._load_model()
        batch: list[str] = []
        global_idx = 0
        batch_start_idx = 0
        
        for text in texts:
            batch.append(text)
            
            if len(batch) >= batch_size:
                # Process batch
                try:
                    embeddings = model.encode(
                        batch,
                        batch_size=batch_size,
                        normalize_embeddings=normalize,
                        show_progress_bar=False,
                        convert_to_numpy=True,
                    )
                    
                    # Yield individual embeddings with their global indices
                    for i, embedding in enumerate(embeddings):
                        yield (batch_start_idx + i, embedding.tolist())
                    
                    # Update state
                    batch_start_idx += len(batch)
                    batch = []
                    gc.collect()
                    
                except MemoryError as e:
                    logger.error(
                        f"Out of memory with batch_size={batch_size}. "
                        "Try a smaller batch size."
                    )
                    raise
                except Exception as e:
                    logger.error(f"Error encoding streaming batch: {e}")
                    raise
        
        # Process remaining texts
        if batch:
            try:
                embeddings = model.encode(
                    batch,
                    batch_size=len(batch),
                    normalize_embeddings=normalize,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                )
                
                for i, embedding in enumerate(embeddings):
                    yield (batch_start_idx + i, embedding.tolist())
                    
            except Exception as e:
                logger.error(f"Error encoding final streaming batch: {e}")
                raise

    @property
    def embedding_dim(self) -> int:
        """Get the embedding dimension.

        Returns:
            Dimension of the embedding vectors
        """
        if self._model is None:
            return self._embedding_dim
        get_dim = getattr(self._model, "get_embedding_dimension", None)
        if get_dim is None:
            get_dim = self._model.get_sentence_embedding_dimension
        return get_dim()

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
