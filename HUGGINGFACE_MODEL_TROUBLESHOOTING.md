# HuggingFace Model Download Troubleshooting

## Problem
Getting timeout errors (HTTP 504/503) when downloading the embedding model:
```
HTTP Error 504 thrown while requesting HEAD https://huggingface.co/Quockhanh05/Vietnam_legal_embeddings/...
Embedding model warmup timed out after 20s; continuing without blocking startup.
```

## Solutions (in order of preference)

### Solution 1: Use the Pre-download Script (Recommended)

Download the model separately before starting the app:

```bash
python scripts/download_embedding_model.py
```

This gives the model more time to download (up to 10 minutes) with better error messages.

### Solution 2: Increase Timeout in .env

Add this to your `.env` file:

```env
# Use HuggingFace mirror for better connectivity in Asia
HF_ENDPOINT=https://hf-mirror.com
```

### Solution 3: Manually Download with huggingface-cli

```bash
# Install huggingface-cli if not already installed
pip install huggingface_hub

# Download the model
huggingface-cli download Quockhanh05/Vietnam_legal_embeddings

# The model will be cached in ~/.cache/huggingface/
```

### Solution 4: Check Network Connectivity

Test if you can reach HuggingFace:

```bash
curl -I https://huggingface.co
```

If this fails or is very slow:
- Check your internet connection
- Check if a firewall/proxy is blocking access
- Try using a VPN
- Use the HuggingFace mirror (Solution 2)

## What Changed in This Fix

1. **Increased timeouts**:
   - Metadata timeout: 60s → 120s (2 minutes)
   - Download timeout: 60s → 300s (5 minutes)
   - Warmup timeout: 20s → 120s (2 minutes)

2. **Better error messages**: Clear guidance on what went wrong and how to fix it

3. **Pre-download script**: `scripts/download_embedding_model.py` for manual download

4. **Mirror support**: Option to use `HF_ENDPOINT=https://hf-mirror.com` for Asia regions

## Technical Details

The model is downloaded from:
- URL: `https://huggingface.co/Quockhanh05/Vietnam_legal_embeddings`
- Size: ~270MB (varies)
- Cached in: `~/.cache/huggingface/hub/`

Once downloaded, the model is cached locally and subsequent startups will be fast (no download needed).

## Still Having Issues?

1. **Check logs**: Look for detailed error messages in the console
2. **Check disk space**: Ensure you have at least 1GB free for model cache
3. **Check Python version**: Must be Python 3.10+
4. **Check dependencies**: `pip install sentence-transformers`

If the problem persists, you can temporarily use a fallback embedding model by modifying the code to use a different model that's already available locally.
