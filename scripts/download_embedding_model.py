#!/usr/bin/env python3
"""Pre-download the embedding model to avoid timeout issues during app startup.

This script downloads the Vietnam_legal_embeddings model from HuggingFace
and caches it locally. Subsequent runs will use the cached model.

Usage:
    python scripts/download_embedding_model.py

If you're in Asia and having connectivity issues, use the mirror:
    HF_ENDPOINT=https://hf-mirror.com python scripts/download_embedding_model.py
"""

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Set extended timeouts before importing anything else
import os
os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "300")  # 5 minutes
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "600")  # 10 minutes

# Optional: Use mirror for Asia region
# os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

MODEL_NAME = "Quockhanh05/Vietnam_legal_embeddings"


def download_model():
    """Download and cache the embedding model."""
    logger.info("=" * 70)
    logger.info("Downloading Vietnam Legal Embeddings Model")
    logger.info("=" * 70)
    logger.info(f"Model: {MODEL_NAME}")
    logger.info("")
    
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.error("sentence-transformers not installed!")
        logger.error("Install it with: pip install sentence-transformers")
        sys.exit(1)
    
    logger.info("Starting download (this may take several minutes)...")
    logger.info("The model will be cached locally for future use.")
    logger.info("")
    
    try:
        # This will download and cache the model
        model = SentenceTransformer(
            MODEL_NAME,
            trust_remote_code=True,
        )
        
        # Get model info
        dim = model.get_sentence_embedding_dimension()
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ Model downloaded successfully!")
        logger.info("=" * 70)
        logger.info(f"Model: {MODEL_NAME}")
        logger.info(f"Embedding dimension: {dim}")
        logger.info("")
        logger.info("The model is now cached and will load quickly on next startup.")
        logger.info("You can now start your application with:")
        logger.info("  uvicorn apps.review_api.main:app --reload")
        logger.info("")
        
    except Exception as e:
        logger.error("")
        logger.error("=" * 70)
        logger.error("❌ Failed to download model")
        logger.error("=" * 70)
        logger.error(f"Error: {e}")
        logger.error("")
        logger.error("Possible solutions:")
        logger.error("1. Check your internet connection")
        logger.error("2. Try again in a few minutes (HuggingFace might be temporarily down)")
        logger.error("3. If you're in Asia, use the mirror:")
        logger.error("   HF_ENDPOINT=https://hf-mirror.com python scripts/download_embedding_model.py")
        logger.error("4. Check if a firewall/proxy is blocking access to huggingface.co")
        logger.error("")
        sys.exit(1)


if __name__ == "__main__":
    download_model()
