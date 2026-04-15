#!/usr/bin/env python3
"""
CLI tool for ingesting HuggingFace dataset with OPTIMIZED processing.

Uses Polars for fast parquet reading and proper ID-based joining.
Implements parallel HTML cleaning and optimized indexing.

Usage:
    python scripts/ingest_dataset.py --limit 50
    python scripts/ingest_dataset.py --limit 500 --batch-size 50
"""

import asyncio
import concurrent.futures
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
        TransferSpeedColumn,
    )
    from rich.table import Table

    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("⚠️  rich library not installed. Install with: pip install rich")

import aiohttp

from packages.common.config import get_settings
from packages.ingestion.pipeline import IngestionPipeline

logger = logging.getLogger(__name__)

# Cache directory for downloaded parquet files
CACHE_DIR = Path("data/cache/datasets")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

if HAS_RICH:
    console = Console()
    print_console = console.print
else:
    print_console = print


def get_parquet_url(dataset_name: str, config_name: str) -> str:
    """Get direct parquet file URL from HuggingFace."""
    return f"https://huggingface.co/datasets/{dataset_name}/resolve/main/data/{config_name}.parquet"


async def download_file_with_progress(
    url: str,
    filename: str,
    description: str = "Downloading",
    color: str = "cyan",
    use_cache: bool = True,
) -> bytes:
    """Download file with real progress bar, with caching and resume support.

    Args:
        url: URL to download from
        filename: Local filename to cache
        description: Progress bar description
        color: Progress bar color
        use_cache: Whether to use cached file if exists

    Returns:
        Downloaded bytes
    """
    cache_file = CACHE_DIR / filename
    temp_file = CACHE_DIR / f"{filename}.tmp"

    # Check if file already cached (complete file)
    if use_cache and cache_file.exists():
        file_size = cache_file.stat().st_size
        print_console(f"  ✓ Using cached {filename} ({file_size / 1024 / 1024:.1f} MB)", style="green")
        return cache_file.read_bytes()

    # Clean up any incomplete temp file from previous interrupted download
    if temp_file.exists():
        print_console(f"  ⚠️  Found incomplete download, resuming...", style="yellow")
        start_byte = temp_file.stat().st_size
    else:
        start_byte = 0

    # Download with resume support
    headers = {}
    if start_byte > 0:
        headers["Range"] = f"bytes={start_byte}-"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 416:  # Range not satisfiable, download from start
                print_console(f"  ⚠️  Cannot resume, downloading from start...", style="yellow")
                start_byte = 0
                temp_file.unlink(missing_ok=True)
                response = await session.get(url)

            response.raise_for_status()

            # Get total size
            if start_byte > 0:
                content_range = response.headers.get("Content-Range", "")
                if content_range:
                    total_size = int(content_range.split("/")[-1])
                else:
                    total_size = int(response.headers.get("Content-Length", 0)) + start_byte
            else:
                total_size = int(response.headers.get("Content-Length", 0))

            # Download in chunks
            downloaded = start_byte

            # Open file in append mode if resuming
            mode = "ab" if start_byte > 0 else "wb"

            if HAS_RICH:
                with Progress(
                    SpinnerColumn(),
                    TextColumn(f"[{color}]{{task.description}}"),
                    BarColumn(),
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    TimeElapsedColumn(),
                    TimeRemainingColumn(),
                    console=console,
                    transient=True,
                ) as progress:
                    task = progress.add_task(description, total=total_size, completed=downloaded)

                    with open(temp_file, mode) as f:
                        async for chunk in response.content.iter_chunked(65536):  # 64KB chunks
                            f.write(chunk)
                            downloaded += len(chunk)
                            progress.update(task, advance=len(chunk))
            else:
                print(f"  Downloading... (total: {total_size / 1024 / 1024:.1f} MB)")
                with open(temp_file, mode) as f:
                    async for chunk in response.content.iter_chunked(65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if downloaded % (1024 * 1024) == 0:  # Print every 1MB
                            print(f"    Downloaded: {downloaded / 1024 / 1024:.1f} MB")

            # Download complete - rename temp file to final cache file (atomic operation)
            temp_file.rename(cache_file)

            return cache_file.read_bytes()


def clean_html_to_text(html_content: str) -> str:
    """Clean HTML content to plain text.

    Args:
        html_content: HTML content string

    Returns:
        Cleaned text string
    """
    if not html_content:
        return ""

    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n\s*\n", "\n\n", text)
        return text.strip()
    except ImportError:
        # Fallback to regex if BeautifulSoup not available
        text = re.sub(r"<[^>]+>", "", html_content)
        return text.strip()
    except Exception as e:
        logger.warning(f"Failed to clean HTML: {e}")
        return ""


def clean_html_batch(html_contents: list[str], max_workers: int = 4) -> list[str]:
    """Clean multiple HTML contents in parallel.

    Args:
        html_contents: List of HTML content strings
        max_workers: Number of parallel workers

    Returns:
        List of cleaned text strings
    """
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(clean_html_to_text, html_contents))
    return results


def load_and_merge_with_polars(
    metadata_path: Path,
    content_path: Path,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Load parquet files with Polars and merge on ID.

    This function:
    1. Reads both parquet files with Polars (fast)
    2. Casts ID columns to string for consistent joining
    3. Deduplicates content by ID (keep first)
    4. Performs inner join on ID (guarantees match)
    5. Applies limit AFTER join (not before!)
    6. Cleans HTML content in parallel

    Args:
        metadata_path: Path to metadata parquet file
        content_path: Path to content parquet file
        limit: Optional limit on number of documents

    Returns:
        List of merged document dictionaries
    """
    import polars as pl

    start_time = time.time()

    # Step 1: Read parquet files with Polars (fast!)
    print_console("    → Reading metadata.parquet with Polars...", style="dim")
    metadata_df = pl.read_parquet(metadata_path)
    elapsed = time.time() - start_time
    print_console(f"    ✓ Metadata loaded: {len(metadata_df)} rows ({elapsed:.2f}s)", style="green")

    step_start = time.time()
    print_console("    → Reading content.parquet with Polars...", style="dim")
    content_df = pl.read_parquet(content_path)
    elapsed = time.time() - step_start
    print_console(f"    ✓ Content loaded: {len(content_df)} rows ({elapsed:.2f}s)", style="green")

    # Step 2: Ensure ID columns are string type for consistent joining
    step_start = time.time()
    print_console("    → Preparing ID columns for join...", style="dim")

    metadata_df = metadata_df.with_columns(pl.col("id").cast(pl.Utf8).alias("id"))
    content_df = content_df.with_columns(pl.col("id").cast(pl.Utf8).alias("id"))

    # Step 3: Deduplicate content (keep first occurrence of each ID)
    unique_content_ids = content_df.n_unique("id")
    if len(content_df) != unique_content_ids:
        print_console(
            f"    ⚠️  Content has {len(content_df)} rows but only {unique_content_ids} unique IDs",
            style="yellow"
        )
        print_console("    → Deduplicating content (keeping first per ID)...", style="dim")
        content_df = content_df.unique(subset=["id"], keep="first")
        print_console(f"    ✓ Content deduplicated: {len(content_df)} rows", style="green")

    elapsed = time.time() - step_start
    print_console(f"    ✓ ID preparation complete ({elapsed:.2f}s)", style="green")

    # Step 4: Inner join on ID - guarantees ALL results have both metadata AND content
    step_start = time.time()
    print_console("    → Performing inner join on ID...", style="dim")

    # Select only needed columns from content
    content_cols = ["id", "content_html"]
    content_for_join = content_df.select(content_cols)

    # Inner join - only rows where ID exists in BOTH dataframes
    merged_df = metadata_df.join(content_for_join, on="id", how="inner")

    elapsed = time.time() - step_start
    match_rate = len(merged_df) / len(metadata_df) * 100 if len(metadata_df) > 0 else 0
    print_console(
        f"    ✓ Join complete: {len(merged_df)} matched ({match_rate:.1f}% match rate, {elapsed:.2f}s)",
        style="green"
    )

    # Step 5: Apply limit AFTER join (not before!)
    if limit and limit < len(merged_df):
        print_console(f"    → Applying limit: {limit} documents", style="dim")
        merged_df = merged_df.head(limit)

    # Step 6: Extract data and clean HTML in parallel
    step_start = time.time()
    print_console(f"    → Cleaning HTML content (parallel processing)...", style="dim")

    # Convert to list of dicts for processing
    rows = merged_df.to_dicts()

    # Extract HTML content for batch cleaning
    html_contents = [row.get("content_html", "") or "" for row in rows]

    # Clean in parallel (4 workers)
    cleaned_texts = clean_html_batch(html_contents, max_workers=4)

    # Build final document list
    documents = []
    skipped_empty = 0

    for row, content_text in zip(rows, cleaned_texts):
        if not content_text or len(content_text.strip()) < 50:
            skipped_empty += 1
            continue

        doc = {
            "id": str(row.get("id", "")),
            "title": row.get("title", "") or f"Document {row.get('id', '')}",
            "content": content_text,
            "doc_type": row.get("loai_van_ban", "unknown") or "unknown",
            "metadata": {
                "so_ky_hieu": row.get("so_ky_hieu", "") or "",
                "ngay_ban_hanh": str(row.get("ngay_ban_hanh", "") or ""),
                "ngay_co_hieu_luc": str(row.get("ngay_co_hieu_luc", "") or ""),
                "co_quan_ban_hanh": row.get("co_quan_ban_hanh", "") or "",
            }
        }
        documents.append(doc)

    elapsed = time.time() - step_start
    print_console(
        f"    ✓ HTML cleaned: {len(documents)} documents ready ({elapsed:.2f}s)",
        style="green"
    )
    if skipped_empty > 0:
        print_console(f"    ⚠️  Skipped {skipped_empty} documents with empty/short content", style="yellow")

    total_elapsed = time.time() - start_time
    print_console(f"\n  ✅ Phase 2 complete: {len(documents)} documents ready ({total_elapsed:.1f}s total)", style="bold green")

    return documents


async def ingest_dataset_optimized(
    limit: int = 50,
    batch_size: int = 10,
    dataset_name: str = "th1nhng0/vietnamese-legal-documents",
    use_cache: bool = True,
) -> None:
    """Main ingestion function with optimized processing.

    Args:
        limit: Maximum number of documents to ingest
        batch_size: Batch size for indexing operations
        dataset_name: HuggingFace dataset name
        use_cache: Whether to use cached parquet files
    """
    print_console("\n" + "=" * 70)
    print_console("🚀 VIETNAMESE LEGAL DATASET INGESTION (OPTIMIZED)", style="bold cyan")
    print_console("=" * 70 + "\n")

    print_console("📊 Configuration:", style="bold")
    print_console(f"   Dataset: {dataset_name}")
    print_console(f"   Documents: {limit}")
    print_console(f"   Batch size: {batch_size}")
    print_console()

    settings = get_settings()
    pipeline = IngestionPipeline(settings)

    metadata_url = get_parquet_url(dataset_name, "metadata")
    content_url = get_parquet_url(dataset_name, "content")

    try:
        # Phase 1: Download parquet files with REAL progress
        print_console("📥 Phase 1: Downloading parquet files", style="bold yellow")
        print_console()

        print_console("  ⬇️  Downloading metadata.parquet...")
        await download_file_with_progress(
            metadata_url,
            filename="metadata.parquet",
            description="Downloading metadata.parquet",
            color="cyan",
            use_cache=use_cache,
        )
        print_console("  ✅ Metadata downloaded\n", style="green")

        print_console("  ⬇️  Downloading content.parquet...")
        await download_file_with_progress(
            content_url,
            filename="content.parquet",
            description="Downloading content.parquet",
            color="blue",
            use_cache=use_cache,
        )
        print_console("  ✅ Content downloaded\n", style="green")

        print_console("✅ Phase 1 complete: Files downloaded", style="bold green")
        print_console()

        # Phase 2: Load and merge with Polars (OPTIMIZED!)
        print_console("\n🔄 Phase 2: Processing documents with Polars", style="bold yellow")
        print_console()

        metadata_path = CACHE_DIR / "metadata.parquet"
        content_path = CACHE_DIR / "content.parquet"

        merged_docs = load_and_merge_with_polars(
            metadata_path=metadata_path,
            content_path=content_path,
            limit=limit,
        )

        if not merged_docs:
            print_console("\n❌ No documents to ingest after processing", style="bold red")
            return

        # Phase 3: Ingest into databases with OPTIMIZED batch processing
        print_console("\n💾 Phase 3: Ingesting into databases (BATCH MODE)", style="bold yellow")
        print_console(f"  🚀 Using parallel processing with batch size: {batch_size}")
        print_console()
        
        start_time = time.time()
        
        # Use optimized batch ingestion
        stats = await pipeline.ingest_batch_documents(
            documents=merged_docs,
            batch_size=batch_size,
        )
        
        total_elapsed = time.time() - start_time

        # Print summary
        print_console("\n" + "=" * 70)
        print_console("✅ INGESTION COMPLETE", style="bold green")
        print_console("=" * 70)
        print_console()

        if HAS_RICH:
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Total Documents", str(stats["total"]))
            table.add_row("Successfully Ingested", str(stats["success"]))
            table.add_row("Failed", str(stats["failed"]))
            success_rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0
            table.add_row("Success Rate", f"{success_rate:.1f}%")
            
            # Show indexing stats if available
            if stats.get("qdrant_indexed"):
                table.add_row("Qdrant Indexed", str(stats["qdrant_indexed"]))
            if stats.get("opensearch_indexed"):
                table.add_row("OpenSearch Indexed", str(stats["opensearch_indexed"]))
            if stats.get("warnings"):
                table.add_row("Warnings", str(len(stats["warnings"])))
            if stats.get("errors"):
                table.add_row("Errors", str(len(stats["errors"])))

            print_console(table)

            if stats["errors"]:
                print_console(f"\n❌ Errors ({len(stats['errors'])}):", style="red")
                for error in stats["errors"][:5]:
                    print_console(f"   • {error}", style="dim red")
                if len(stats["errors"]) > 5:
                    print_console(f"   ... and {len(stats['errors']) - 5} more errors", style="dim")
        else:
            print(f"\nTotal: {stats['total']}")
            print(f"Success: {stats['success']}")
            print(f"Failed: {stats['failed']}")
            success_rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0
            print(f"Success Rate: {success_rate:.1f}%")

            if stats["errors"]:
                print(f"\nErrors (first 5):")
                for error in stats["errors"][:5]:
                    print(f"  • {error}")

        print_console()

    except KeyboardInterrupt:
        print_console("\n\n⚠️  Ingestion cancelled by user", style="bold yellow")
    except Exception as e:
        print_console(f"\n\n❌ Ingestion failed: {e}", style="bold red")
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise
    finally:
        try:
            await pipeline.close()
        except Exception:
            pass


def show_cache_info() -> None:
    """Show cache status and size."""
    print_console("\n" + "=" * 70, style="bold cyan")
    print_console("📦 DATASET CACHE STATUS", style="bold cyan")
    print_console("=" * 70 + "\n")

    if not CACHE_DIR.exists():
        print_console("Cache directory does not exist yet.")
        return

    parquet_files = list(CACHE_DIR.glob("*.parquet"))
    temp_files = list(CACHE_DIR.glob("*.tmp"))

    if not parquet_files and not temp_files:
        print_console("No cached files found.")
        return

    total_size = 0
    print_console(f"Cache location: {CACHE_DIR.absolute()}\n")

    if parquet_files:
        print_console(f"  ✓ Complete files ({len(parquet_files)}):", style="green")
        for f in sorted(parquet_files):
            size = f.stat().st_size
            total_size += size
            print_console(f"    📄 {f.name:30s} {size / 1024 / 1024:8.2f} MB", style="green")

    if temp_files:
        print_console(f"\n  ⚠️  Incomplete downloads ({len(temp_files)}):", style="yellow")
        for f in sorted(temp_files):
            size = f.stat().st_size
            total_size += size
            print_console(f"    ⏳ {f.name:30s} {size / 1024 / 1024:8.2f} MB", style="yellow")

    print_console("\n" + "-" * 70)
    print_console(
        f"  Total: {len(parquet_files) + len(temp_files)} files, {total_size / 1024 / 1024:.2f} MB",
        style="bold"
    )

    if temp_files:
        print_console("  💡 Tip: Run with --clear-cache to remove incomplete downloads", style="dim")

    print_console()


def clear_cache() -> None:
    """Clear all cached parquet files and incomplete downloads."""
    if not CACHE_DIR.exists():
        print_console("Cache directory does not exist.")
        return

    parquet_files = list(CACHE_DIR.glob("*.parquet"))
    temp_files = list(CACHE_DIR.glob("*.tmp"))
    all_files = parquet_files + temp_files

    if not all_files:
        print_console("No cached files to clear.")
        return

    total_size = sum(f.stat().st_size for f in all_files)

    print_console(
        f"\n🗑️  Clearing {len(all_files)} cached files ({total_size / 1024 / 1024:.2f} MB)...",
        style="yellow"
    )

    for f in all_files:
        f.unlink()
        file_type = "incomplete" if f.suffix == ".tmp" else "cached"
        print_console(f"  Deleted {f.name} ({file_type})", style="dim")

    print_console("✅ Cache cleared\n", style="green")


def main() -> None:
    """Parse arguments and run ingestion."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingest Vietnamese legal dataset from HuggingFace (optimized with Polars)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest 50 documents
  python scripts/ingest_dataset.py --limit 50

  # Ingest 500 documents with batch size 20
  python scripts/ingest_dataset.py --limit 500 --batch-size 20

  # Check cache status
  python scripts/ingest_dataset.py --cache-info

  # Clear cache
  python scripts/ingest_dataset.py --clear-cache

  # Download without using cache
  python scripts/ingest_dataset.py --limit 50 --no-cache
        """,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Number of documents to ingest (default: 50)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Batch size for ingestion (default: 10)",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="th1nhng0/vietnamese-legal-documents",
        help="HuggingFace dataset name (default: th1nhng0/vietnamese-legal-documents)",
    )
    parser.add_argument(
        "--cache-info",
        action="store_true",
        help="Show cache status and exit",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear cached files and exit",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Don't use cache, download fresh",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Handle cache commands
    if args.cache_info:
        show_cache_info()
        return

    if args.clear_cache:
        clear_cache()
        return

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run ingestion
    asyncio.run(ingest_dataset_optimized(
        limit=args.limit,
        batch_size=args.batch_size,
        dataset_name=args.dataset,
        use_cache=not args.no_cache,
    ))


if __name__ == "__main__":
    main()
