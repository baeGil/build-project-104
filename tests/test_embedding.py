"""Tests for EmbeddingService in packages/retrieval/embedding.py."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from packages.retrieval.embedding import EmbeddingService


class TestEmbeddingService:
    """Test suite for EmbeddingService class."""

    def setup_method(self):
        """Reset singleton before each test."""
        EmbeddingService.reset_instance()

    def teardown_method(self):
        """Reset singleton after each test."""
        EmbeddingService.reset_instance()

    def test_singleton_pattern(self):
        """Test that EmbeddingService follows singleton pattern."""
        instance1 = EmbeddingService.get_instance()
        instance2 = EmbeddingService.get_instance()
        
        assert instance1 is instance2
        assert EmbeddingService._instance is instance1

    def test_singleton_with_custom_model_name(self):
        """Test singleton creation with custom model name."""
        instance = EmbeddingService.get_instance(model_name="custom-model")
        
        assert instance.model_name == "custom-model"
        # Second call should return same instance with original model name
        instance2 = EmbeddingService.get_instance()
        assert instance2 is instance
        assert instance2.model_name == "custom-model"

    def test_reset_instance(self):
        """Test reset_instance clears the singleton."""
        instance1 = EmbeddingService.get_instance()
        EmbeddingService.reset_instance()
        instance2 = EmbeddingService.get_instance()
        
        assert instance1 is not instance2

    def test_encode_single_text(self):
        """Test encoding a single text string."""
        mock_model = MagicMock()
        mock_embeddings = np.array([[0.1, 0.2, 0.3, 0.4]])
        mock_model.encode.return_value = mock_embeddings
        mock_model.get_sentence_embedding_dimension.return_value = 768
        
        with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
            service = EmbeddingService(model_name="test-model")
            result = service.encode("test text")
        
        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3, 0.4]
        mock_model.encode.assert_called_once()
        call_args = mock_model.encode.call_args
        assert call_args[0][0] == ["test text"]  # Single text wrapped in list
        assert call_args[1]["normalize_embeddings"] is True
        assert call_args[1]["batch_size"] == 64

    def test_encode_multiple_texts(self):
        """Test encoding multiple texts."""
        mock_model = MagicMock()
        mock_embeddings = np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]])
        mock_model.encode.return_value = mock_embeddings
        mock_model.get_sentence_embedding_dimension.return_value = 768
        
        with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
            service = EmbeddingService(model_name="test-model")
            texts = ["text1", "text2", "text3"]
            result = service.encode(texts)
        
        assert len(result) == 3
        assert result[0] == [0.1, 0.2]
        assert result[1] == [0.3, 0.4]
        assert result[2] == [0.5, 0.6]

    def test_encode_empty_list(self):
        """Test encoding an empty list returns empty result."""
        service = EmbeddingService(model_name="test-model")
        # Empty list should return empty result without loading model
        result = service.encode([])
        
        assert result == []

    def test_encode_without_normalization(self):
        """Test encoding with normalize=False."""
        mock_model = MagicMock()
        mock_embeddings = np.array([[0.1, 0.2, 0.3]])
        mock_model.encode.return_value = mock_embeddings
        mock_model.get_sentence_embedding_dimension.return_value = 768
        
        with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
            service = EmbeddingService(model_name="test-model")
            result = service.encode("test", normalize=False)
        
        assert result == [[0.1, 0.2, 0.3]]
        call_args = mock_model.encode.call_args
        assert call_args[1]["normalize_embeddings"] is False

    def test_encode_custom_batch_size(self):
        """Test encoding with custom batch size."""
        mock_model = MagicMock()
        mock_embeddings = np.array([[0.1, 0.2]])
        mock_model.encode.return_value = mock_embeddings
        mock_model.get_sentence_embedding_dimension.return_value = 768
        
        with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
            service = EmbeddingService(model_name="test-model")
            result = service.encode("test", batch_size=32)
        
        call_args = mock_model.encode.call_args
        assert call_args[1]["batch_size"] == 32

    def test_encode_query(self):
        """Test encode_query method for single query."""
        mock_model = MagicMock()
        mock_embeddings = np.array([[0.1, 0.2, 0.3]])
        mock_model.encode.return_value = mock_embeddings
        mock_model.get_sentence_embedding_dimension.return_value = 768
        
        with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
            service = EmbeddingService(model_name="test-model")
            result = service.encode_query("query text")
        
        assert result == [0.1, 0.2, 0.3]
        call_args = mock_model.encode.call_args
        assert call_args[1]["batch_size"] == 1

    def test_encode_batch(self):
        """Test encode_batch method."""
        mock_model = MagicMock()
        mock_embeddings = np.array([[0.1, 0.2], [0.3, 0.4]])
        mock_model.encode.return_value = mock_embeddings
        mock_model.get_sentence_embedding_dimension.return_value = 768
        
        with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
            service = EmbeddingService(model_name="test-model")
            result = service.encode_batch(["text1", "text2"], batch_size=16)
        
        assert len(result) == 2
        call_args = mock_model.encode.call_args
        assert call_args[1]["batch_size"] == 16

    def test_embedding_dim_before_load(self):
        """Test embedding_dim property before model is loaded."""
        service = EmbeddingService(model_name="test-model")
        
        # Should return default dimension before model load
        assert service.embedding_dim == 768

    def test_embedding_dim_after_load(self):
        """Test embedding_dim property after model is loaded."""
        mock_model = MagicMock()
        # The property first checks for get_embedding_dimension, then falls back to get_sentence_embedding_dimension
        # Make get_embedding_dimension return None so it uses get_sentence_embedding_dimension
        mock_model.get_embedding_dimension = None
        mock_model.get_sentence_embedding_dimension.return_value = 512
        mock_embeddings = np.array([[0.1, 0.2]])
        mock_model.encode.return_value = mock_embeddings
        
        with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
            service = EmbeddingService(model_name="test-model")
            # Trigger model load
            service.encode("test")
            
            # embedding_dim should return the actual dimension from the model
            assert service.embedding_dim == 512

    def test_embedding_dim_with_get_embedding_dimension(self):
        """Test embedding_dim when model has get_embedding_dimension method."""
        mock_model = MagicMock()
        mock_model.get_embedding_dimension.return_value = 1024
        mock_embeddings = np.array([[0.1, 0.2]])
        mock_model.encode.return_value = mock_embeddings
        
        with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
            service = EmbeddingService(model_name="test-model")
            service.encode("test")
            
            assert service.embedding_dim == 1024

    def test_lazy_model_loading(self):
        """Test that model is loaded lazily."""
        with patch("sentence_transformers.SentenceTransformer") as mock_st:
            service = EmbeddingService(model_name="test-model")
            # Model should not be loaded yet
            mock_st.assert_not_called()
            
            # Trigger load
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 768
            mock_embeddings = np.array([[0.1, 0.2]])
            mock_model.encode.return_value = mock_embeddings
            mock_st.return_value = mock_model
            
            service.encode("test")
            # Now model should be loaded
            mock_st.assert_called_once_with("test-model", trust_remote_code=True)

    def test_import_error_handling(self):
        """Test handling of ImportError when sentence-transformers not installed."""
        with patch("sentence_transformers.SentenceTransformer", side_effect=ImportError("No module named 'sentence_transformers'")):
            service = EmbeddingService(model_name="test-model")
            
            with pytest.raises(ImportError) as exc_info:
                service.encode("test")
            
            assert "sentence-transformers is required" in str(exc_info.value)

    def test_model_load_error_handling(self):
        """Test handling of general model load errors."""
        with patch("sentence_transformers.SentenceTransformer", side_effect=RuntimeError("Model load failed")):
            service = EmbeddingService(model_name="test-model")
            
            with pytest.raises(RuntimeError) as exc_info:
                service.encode("test")
            
            assert "Model load failed" in str(exc_info.value)

    def test_encode_error_handling(self):
        """Test handling of encoding errors."""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        mock_model.encode.side_effect = RuntimeError("Encoding failed")
        
        with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
            service = EmbeddingService(model_name="test-model")
            
            with pytest.raises(RuntimeError) as exc_info:
                service.encode("test")
            
            assert "Encoding failed" in str(exc_info.value)
