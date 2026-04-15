"""Process-wide Python startup tweaks for local development.

This disables TensorFlow integration in transformers before any model imports
so sentence-transformers does not try to load incompatible TF plugins from the
current environment.

Also configures HuggingFace Hub extended timeouts to prevent HTTP 504 errors
on slow or unreliable networks.
"""

from __future__ import annotations

import os

# HuggingFace Hub extended timeouts (for slow/unreliable networks)
os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "300")    # 5 minutes for metadata
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "600")  # 10 minutes for downloads

os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")
os.environ.setdefault("USE_TF", "0")
