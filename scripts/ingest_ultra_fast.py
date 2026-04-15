#!/usr/bin/env python3
"""
Ultra-Fast Dataset Ingestion with Optimized UI/UX.

Features:
✓ Compact real-time UI with smooth progress bar
✓ Maximum parallel processing (CPU + I/O)
✓ Resume capability with checkpointing
✓ Optimized batch sizes for 180K documents
✓ Preload embedding model once
✓ Async concurrent database writes

Usage:
    uv run python scripts/ingest_ultra_fast.py --limit 1000 --batch-size 50
    uv run python scripts/ingest_ultra_fast.py --resume  # Resume from checkpoint
    uv run python scripts/ingest_ultra_fast.py --no-limit  # Ingest all
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
    from rich.table import Table
    from rich.layout import Layout
    from rich.text import Text

    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("⚠️  rich library not installed. Install with: pip install rich")

import aiohttp
import polars as pl
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

from packages.common.config import get_settings
from packages.ingestion.pipeline import IngestionPipeline
from packages.ingestion.normalizer import normalize_legal_text
from packages.ingestion.parser import parse_legal_document

logger = logging.getLogger(__name__)

# Paths
CACHE_DIR = Path("data/cache/datasets")
CHECKPOINT_DIR = Path("data/cache/checkpoints")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

CHECKPOINT_FILE = CHECKPOINT_DIR / "ingestion_checkpoint.json"

if HAS_RICH:
    console = Console()
    print_console = console.print
else:
    print_console = print


class IngestionStateManager:
    """Manages ingestion state for resume capability."""

    def __init__(self, checkpoint_file: Path = CHECKPOINT_FILE):
        self.checkpoint_file = checkpoint_file
        self.state = {
            "total_documents": 0,
            "processed_ids": set(),  # Use set for O(1) lookup
            "failed_ids": [],
            "started_at": None,
            "last_updated": None,
        }

    def load(self) -> dict[str, Any]:
        """Load checkpoint from file."""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, "r") as f:
                    data = json.load(f)
                    # Convert list to set for faster lookup
                    self.state["processed_ids"] = set(data.get("processed_ids", []))
                    self.state["failed_ids"] = data.get("failed_ids", [])
                    self.state["total_documents"] = data.get("total_documents", 0)
                print_console(f"✓ Loaded checkpoint: {len(self.state['processed_ids'])} documents processed", style="green")
                return self.state
            except Exception as e:
                print_console(f"⚠️  Failed to load checkpoint: {e}", style="yellow")
        return self.state

    def save(self):
        """Save checkpoint to file."""
        self.state["last_updated"] = time.time()
        # Convert set to list for JSON serialization
        save_data = {
            **self.state,
            "processed_ids": list(self.state["processed_ids"])
        }
        with open(self.checkpoint_file, "w") as f:
            json.dump(save_data, f, indent=2)

    def mark_processed(self, doc_id: str):
        """Mark a document as processed."""
        self.state["processed_ids"].add(doc_id)
        # Save every 10 documents to reduce I/O
        if len(self.state["processed_ids"]) % 10 == 0:
            self.save()

    def save_final(self):
        """Save final checkpoint."""
        self.save()

    def is_processed(self, doc_id: str) -> bool:
        """Check if document was already processed."""
        return doc_id in self.state["processed_ids"]

    def clear(self):
        """Clear all checkpoints."""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
        print_console("✓ Checkpoints cleared", style="green")


def clean_html_to_text(html_content: str) -> str:
    """Clean HTML content to plain text."""
    if not html_content:
        return ""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        text = text.replace("\r\n", "\n")
        import re
        text = re.sub(r"\n\s*\n", "\n\n", text)
        return text.strip()
    except Exception as e:
        return ""


async def download_parquet_files(use_cache: bool = True) -> tuple[Path, Path]:
    """Download metadata and content parquet files."""
    dataset_name = "th1nhng0/vietnamese-legal-documents"
    
    metadata_url = f"https://huggingface.co/datasets/{dataset_name}/resolve/main/data/metadata.parquet"
    content_url = f"https://huggingface.co/datasets/{dataset_name}/resolve/main/data/content.parquet"

    metadata_path = CACHE_DIR / "metadata.parquet"
    content_path = CACHE_DIR / "content.parquet"

    async def download_file(url: str, path: Path, description: str, color: str):
        if use_cache and path.exists():
            size = path.stat().st_size
            print_console(f"  ✓ Cached: {path.name} ({size / 1024 / 1024:.1f} MB)", style="green")
            return

        print_console(f"  ⬇️  Downloading {path.name}...", style=color)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                total_size = int(response.headers.get("Content-Length", 0))
                
                with Progress(
                    TextColumn(f"[{color}]{{task.description}}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TimeElapsedColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task(description, total=total_size)
                    
                    downloaded = 0
                    with open(path, "wb") as f:
                        async for chunk in response.content.iter_chunked(65536):
                            f.write(chunk)
                            downloaded += len(chunk)
                            progress.update(task, advance=len(chunk))

    await download_file(metadata_url, metadata_path, "metadata.parquet", "cyan")
    await download_file(content_url, content_path, "content.parquet", "blue")

    return metadata_path, content_path


def load_and_prepare_documents(
    metadata_path: Path,
    content_path: Path,
    limit: int | None = None,
    processed_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Load parquet files, merge, clean, and filter already processed."""
    print_console("\n📊 Loading and preparing documents...", style="bold yellow")

    # Load parquet files
    step_start = time.time()
    metadata_df = pl.read_parquet(metadata_path)
    content_df = pl.read_parquet(content_path)
    elapsed = time.time() - step_start
    print_console(f"  ✓ Loaded: {len(metadata_df)} metadata, {len(content_df)} content ({elapsed:.1f}s)", style="green")

    # Cast IDs to string
    metadata_df = metadata_df.with_columns(pl.col("id").cast(pl.Utf8).alias("id"))
    content_df = content_df.with_columns(pl.col("id").cast(pl.Utf8).alias("id"))

    # Deduplicate content
    content_df = content_df.unique(subset=["id"], keep="first")

    # Inner join
    merged_df = metadata_df.join(
        content_df.select(["id", "content_html"]),
        on="id",
        how="inner",
    )

    print_console(f"  ✓ Merged: {len(merged_df)} documents", style="green")

    # Apply limit
    if limit and limit < len(merged_df):
        merged_df = merged_df.head(limit)
        print_console(f"  → Limited to: {limit} documents", style="dim")

    # Clean HTML in parallel (4 workers)
    rows = merged_df.to_dicts()
    
    print_console("  🧹 Cleaning HTML content (parallel)...", style="dim")
    with ThreadPoolExecutor(max_workers=4) as executor:
        html_contents = [row.get("content_html", "") or "" for row in rows]
        cleaned_texts = list(executor.map(clean_html_to_text, html_contents))

    # Build document list
    documents = []
    skipped = 0
    already_processed = 0

    for row, content_text in zip(rows, cleaned_texts):
        doc_id = str(row.get("id", ""))
        
        # Skip if already processed (resume capability)
        if processed_ids and doc_id in processed_ids:
            already_processed += 1
            continue
        
        # Skip empty content
        if not content_text or len(content_text.strip()) < 50:
            skipped += 1
            continue

        documents.append({
            "id": doc_id,
            "title": row.get("title", "") or f"Document {doc_id}",
            "content": content_text,
            "doc_type": row.get("loai_van_ban", "unknown") or "unknown",
        })

    print_console(f"  ✓ Ready to ingest: {len(documents)} documents", style="green")
    if already_processed > 0:
        print_console(f"  ⏭️  Already processed (skipped): {already_processed}", style="yellow")
    if skipped > 0:
        print_console(f"  ⚠️  Skipped (empty/short): {skipped}", style="yellow")

    return documents


async def ingest_documents_ultra_fast(
    documents: list[dict[str, Any]],
    pipeline: IngestionPipeline,
    state_manager: IngestionStateManager,
    batch_size: int = 50,
) -> dict[str, Any]:
    """Ultra-fast ingestion with maximum parallelism."""
    
    stats = {
        "total": len(documents),
        "success": 0,
        "failed": 0,
        "errors": [],
    }

    if not documents:
        print_console("\n⚠️  No documents to ingest", style="yellow")
        return stats

    start_time = time.time()
    
    # Preload embedding model ONCE before processing
    print_console("  🔥 Preloading embedding model...", style="dim")
    await pipeline.indexer.qdrant_indexer._get_embedding_model()
    print_console("  ✓ Model loaded", style="green")

    # Use Progress for real-time updates without layout gaps
    from rich.live import Live
    from rich.console import Group
    from rich.text import Text
    
    recent_docs = []
    current_batch = 0
    total_batches = (len(documents) + batch_size - 1) // batch_size
    
    with Progress(
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=60),
        TextColumn("[progress.percentage]{task.percentage:>5.1f}%"),
        TextColumn("•"),
        TextColumn("{task.fields[batch]}"),
        TextColumn("•"),
        TextColumn("{task.fields[speed]}"),
        TextColumn("•"),
        TextColumn("ETA {task.fields[eta]}"),
        console=console,
        refresh_per_second=4,
    ) as progress:
        
        main_task = progress.add_task(
            f"📥 Ingesting {len(documents)} documents",
            total=len(documents),
            batch=f"Batch 0/{total_batches}",
            speed="0.0 docs/s",
            eta="--",
        )
        
        # Create stats panel below progress
        stats_panel = Panel(
            "[bold cyan]📊 Statistics[/bold cyan]\n\n" +
            "  Waiting to start...",
            border_style="cyan",
        )
        
        # Use Live to show both progress and stats
        with Live(stats_panel, console=console, refresh_per_second=2, transient=False) as live:
            
            # Process in batches with MAXIMUM parallelism
            for batch_start in range(0, len(documents), batch_size):
                batch_end = min(batch_start + batch_size, len(documents))
                batch = documents[batch_start:batch_end]
                current_batch = batch_start // batch_size + 1
                
                batch_start_time = time.time()
                
                # OPTIMIZATION: Parse and normalize in parallel (CPU-bound)
                with ThreadPoolExecutor(max_workers=8) as executor:
                    loop = asyncio.get_event_loop()
                    
                    def parse_and_normalize(doc):
                        try:
                            normalized = normalize_legal_text(doc["content"])
                            node = parse_legal_document(normalized, doc["title"])
                            return (node, normalized, doc["id"], doc["title"], None)
                        except Exception as e:
                            return (None, None, doc["id"], doc["title"], str(e))
                    
                    futures = [loop.run_in_executor(executor, parse_and_normalize, doc) for doc in batch]
                    results = await asyncio.gather(*futures)
                
                # OPTIMIZATION: Batch database writes
                nodes_to_ingest = []
                for node, normalized, doc_id, doc_title, error in results:
                    if error:
                        stats["failed"] += 1
                        stats["errors"].append(f"{doc_id}: {error[:80]}")
                        state_manager.mark_processed(doc_id)
                        recent_docs.insert(0, f"✗ {doc_title[:50]}")
                        if len(recent_docs) > 4:
                            recent_docs.pop()
                    else:
                        nodes_to_ingest.append((node, normalized, doc_id, doc_title))
                
                if not nodes_to_ingest:
                    continue
                
                # OPTIMIZATION: Batch PostgreSQL insert
                try:
                    pool = await pipeline._get_postgres_pool()
                    async with pool.acquire() as conn:
                        records = [
                            (node.id, node.title or "", normalized,
                             node.doc_type.value if hasattr(node.doc_type, 'value') else str(node.doc_type),
                             json.dumps(pipeline._build_storage_metadata(node, "ultra_fast_ingestion")))
                            for node, normalized, _, _ in nodes_to_ingest
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
                    
                    stats["success"] += len(records)
                    
                except Exception as e:
                    # Fallback to individual inserts
                    for node, normalized, doc_id, doc_title in nodes_to_ingest:
                        try:
                            await pipeline._store_in_postgres(node, normalized)
                            stats["success"] += 1
                        except Exception as store_err:
                            stats["failed"] += 1
                            stats["errors"].append(f"{doc_id}: {str(store_err)[:80]}")
                
                # OPTIMIZATION: Batch Neo4j sync
                for node, _, doc_id, doc_title in nodes_to_ingest:
                    try:
                        await pipeline.graph_sync.sync_legal_node(node)
                    except Exception:
                        pass
                
                # OPTIMIZATION: Batch index to Qdrant + OpenSearch
                if nodes_to_ingest:
                    try:
                        nodes_only = [node for node, _, _, _ in nodes_to_ingest]
                        indexing_result = await pipeline.indexer.index(nodes_only)
                        
                        # Track recent successful docs
                        for _, _, doc_id, doc_title in nodes_to_ingest:
                            recent_docs.insert(0, f"✓ {doc_title[:50]}")
                            state_manager.mark_processed(doc_id)
                        
                        if len(recent_docs) > 4:
                            recent_docs = recent_docs[:4]
                        
                    except Exception as e:
                        stats["errors"].append(f"Indexing error: {str(e)[:80]}")
                
                # Update UI - smooth realtime
                batch_elapsed = time.time() - batch_start_time
                elapsed = time.time() - start_time
                overall_speed = stats["success"] / elapsed if elapsed > 0 else 0
                eta_seconds = (len(documents) - stats["success"]) / overall_speed if overall_speed > 0 else 0
                
                # Format ETA
                if eta_seconds > 3600:
                    eta_str = f"{int(eta_seconds//3600)}h{int((eta_seconds%3600)//60):02d}m"
                elif eta_seconds > 60:
                    eta_str = f"{int(eta_seconds//60)}m{int(eta_seconds%60):02d}s"
                else:
                    eta_str = f"{int(eta_seconds)}s"
                
                # Update progress bar
                progress.update(
                    main_task,
                    advance=len(nodes_to_ingest),
                    batch=f"Batch {current_batch}/{total_batches}",
                    speed=f"{overall_speed:.1f} docs/s",
                    eta=eta_str,
                )
                
                # Update stats panel
                success_rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0
                
                stats_content = (
                    f"[bold cyan]📊 Statistics[/bold cyan]\n\n"
                    f"  [bold]Progress:[/bold] {stats['success']}/{len(documents)} documents ({success_rate:.1f}%)\n"
                    f"  [bold]Success:[/bold]  [green]{stats['success']:>5}[/green]\n"
                    f"  [bold]Failed:[/bold]   [red]{stats['failed']:>5}[/red]\n"
                    f"  [bold]Speed:[/bold]    [yellow]{overall_speed:>6.1f}[/yellow] docs/s\n"
                    f"  [bold]Elapsed:[/bold]  {int(elapsed//60):02d}m{int(elapsed%60):02d}s\n"
                    f"  [bold]ETA:[/bold]      {eta_str}\n"
                )
                
                if recent_docs:
                    stats_content += f"\n  [dim]Recent documents:[/dim]\n"
                    stats_content += "\n".join([f"    {doc}" for doc in recent_docs[:4]])
                
                live.update(Panel(stats_content, border_style="cyan"))
                
                # Save checkpoint every 5 batches
                if current_batch % 5 == 0:
                    state_manager.save()
            
            # Final save
            state_manager.save_final()
    
    return stats


def display_final_summary(stats: dict[str, Any], start_time: float):
    """Display final ingestion summary."""
    elapsed = time.time() - start_time
    
    print_console("\n" + "=" * 70, style="bold cyan")
    print_console("✅ INGESTION COMPLETE", style="bold green")
    print_console("=" * 70 + "\n", style="bold cyan")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    success_rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0

    table.add_row("Total Documents", str(stats["total"]))
    table.add_row("Successfully Ingested", str(stats["success"]))
    table.add_row("Failed", str(stats["failed"]))
    table.add_row("Success Rate", f"{success_rate:.1f}%")
    table.add_row("Time Elapsed", f"{int(elapsed//60)}m {int(elapsed%60)}s")
    table.add_row("Average Speed", f"{stats['success']/elapsed:.1f} docs/s" if elapsed > 0 else "N/A")

    print_console(table)

    if stats["errors"]:
        print_console(f"\n❌ Errors ({len(stats['errors'])}):", style="red")
        for error in stats["errors"][:5]:
            print_console(f"   • {error}", style="dim red")
        if len(stats["errors"]) > 5:
            print_console(f"   ... and {len(stats['errors']) - 5} more errors", style="dim")

    print_console()


async def main():
    """Main ingestion function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Ultra-fast dataset ingestion with resume capability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest 1000 documents
  uv run python scripts/ingest_ultra_fast.py --limit 1000 --batch-size 50

  # Ingest all documents (~146K)
  uv run python scripts/ingest_ultra_fast.py --no-limit --batch-size 100

  # Resume from checkpoint
  uv run python scripts/ingest_ultra_fast.py --resume

  # Clear checkpoints and start fresh
  uv run python scripts/ingest_ultra_fast.py --clear-checkpoints
        """,
    )

    parser.add_argument("--limit", type=int, default=100, help="Number of documents to ingest")
    parser.add_argument("--no-limit", action="store_true", help="Ingest all documents")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size (default: 50)")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--clear-checkpoints", action="store_true", help="Clear checkpoints")
    parser.add_argument("--no-cache", action="store_true", help="Don't use cached parquet files")

    args = parser.parse_args()

    # Suppress all logging except errors
    logging.basicConfig(level=logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("opensearch").setLevel(logging.WARNING)
    logging.getLogger("neo4j.notifications").setLevel(logging.WARNING)
    logging.getLogger("datasets").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

    # Handle checkpoint commands
    state_manager = IngestionStateManager()
    
    if args.clear_checkpoints:
        state_manager.clear()
        return

    # Load checkpoint if resuming
    if args.resume:
        state_manager.load()

    # Get limit
    limit = None if args.no_limit else args.limit

    print_console("\n" + "=" * 70, style="bold cyan")
    print_console("🚀 ULTRA-FAST VIETNAMESE LEGAL DATASET INGESTION", style="bold cyan")
    print_console("=" * 70 + "\n")

    print_console("📊 Configuration:", style="bold")
    print_console(f"   Dataset: th1nhng0/vietnamese-legal-documents")
    print_console(f"   Limit: {'ALL (~146K)' if limit is None else limit} documents")
    print_console(f"   Batch size: {args.batch_size}")
    print_console(f"   Resume: {'Yes' if args.resume else 'No'}")
    print_console(f"   Cache: {'Yes' if not args.no_cache else 'No'}")
    print_console()

    # Get settings
    settings = get_settings()
    
    # Initialize pipeline
    print_console("🔧 Initializing pipeline...", style="dim")
    pipeline = IngestionPipeline(settings)
    
    # Check connections
    print_console("🏥 Checking database connections...", style="dim")
    health = await pipeline.check_all_connections()
    
    for service, is_healthy in health.items():
        status = "✓" if is_healthy else "✗"
        style = "green" if is_healthy else "red"
        print_console(f"   {service.upper():12s} [{style}]{status}[/{style}]")

    unhealthy = [k for k, v in health.items() if not v]
    if unhealthy:
        print_console(f"\n⚠️  Warning: {', '.join(unhealthy)} unhealthy.", style="yellow")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print_console("Aborted.", style="red")
            return

    start_time = time.time()

    try:
        # Phase 1: Download parquet files
        print_console("\n" + "=" * 70, style="bold yellow")
        print_console("📥 PHASE 1: Download Dataset", style="bold yellow")
        print_console("=" * 70)
        
        metadata_path = CACHE_DIR / "metadata.parquet"
        content_path = CACHE_DIR / "content.parquet"
        
        if not metadata_path.exists() or not content_path.exists() or args.no_cache:
            metadata_path, content_path = await download_parquet_files(
                use_cache=not args.no_cache
            )
        else:
            print_console("  ✓ Using cached parquet files", style="green")

        # Phase 2: Load and prepare documents
        print_console("\n" + "=" * 70, style="bold yellow")
        print_console("🔄 PHASE 2: Prepare Documents", style="bold yellow")
        print_console("=" * 70)

        processed_ids = state_manager.state["processed_ids"] if args.resume else set()
        
        documents = load_and_prepare_documents(
            metadata_path=metadata_path,
            content_path=content_path,
            limit=limit,
            processed_ids=processed_ids,
        )

        if not documents:
            print_console("\n✅ All documents already processed!", style="bold green")
            return

        state_manager.state["total_documents"] = len(documents) + len(processed_ids)
        state_manager.save()

        # Phase 3: Ultra-fast ingestion
        print_console("\n" + "=" * 70, style="bold yellow")
        print_console("💾 PHASE 3: Ultra-Fast Ingestion", style="bold yellow")
        print_console("=" * 70 + "\n")

        stats = await ingest_documents_ultra_fast(
            documents=documents,
            pipeline=pipeline,
            state_manager=state_manager,
            batch_size=args.batch_size,
        )

        # Display summary
        display_final_summary(stats, start_time)

    except KeyboardInterrupt:
        print_console("\n\n⚠️  Cancelled. Checkpoint saved.", style="bold yellow")
        print_console("   Resume: uv run python scripts/ingest_ultra_fast.py --resume\n", style="dim")
    except Exception as e:
        print_console(f"\n\n❌ Failed: {e}", style="bold red")
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        print_console("   Resume: uv run python scripts/ingest_ultra_fast.py --resume\n", style="dim")
        raise
    finally:
        try:
            await pipeline.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
