#!/usr/bin/env python3
"""
Complete Dataset Ingestion Script with Resume Capability and Real-time Progress Tracking.

This script ingests the Vietnamese Legal Documents dataset from HuggingFace into:
- PostgreSQL (document storage)
- Qdrant (vector embeddings)
- OpenSearch (full-text BM25 search)
- Neo4j (graph relationships)

Features:
✓ Resume capability - cache processed IDs, resume from interruption
✓ Real-time progress tracking with Rich library
✓ Parallel processing for speed
✓ Health checks before ingestion
✓ Detailed statistics and timing

Usage:
    python scripts/ingest_complete.py --limit 50
    python scripts/ingest_complete.py --limit 500 --batch-size 20
    python scripts/ingest_complete.py --resume  # Resume from last checkpoint
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
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )
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

from packages.common.config import get_settings
from packages.ingestion.pipeline import IngestionPipeline

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
            "processed_ids": [],
            "failed_ids": [],
            "phases": {
                "download": {"status": "pending", "completed_at": None},
                "processing": {"status": "pending", "completed_at": None},
                "postgres": {"status": "pending", "completed_at": None},
                "qdrant": {"status": "pending", "completed_at": None},
                "opensearch": {"status": "pending", "completed_at": None},
                "neo4j": {"status": "pending", "completed_at": None},
            },
            "started_at": None,
            "last_updated": None,
        }

    def load(self) -> dict[str, Any]:
        """Load checkpoint from file."""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, "r") as f:
                    self.state = json.load(f)
                print_console(f"✓ Loaded checkpoint: {len(self.state['processed_ids'])} documents already processed", style="green")
                return self.state
            except Exception as e:
                print_console(f"⚠️  Failed to load checkpoint: {e}", style="yellow")
        return self.state

    def save(self):
        """Save checkpoint to file."""
        self.state["last_updated"] = time.time()
        with open(self.checkpoint_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def mark_processed(self, doc_id: str):
        """Mark a document as processed."""
        if doc_id not in self.state["processed_ids"]:
            self.state["processed_ids"].append(doc_id)
            self.save()

    def mark_failed(self, doc_id: str):
        """Mark a document as failed."""
        if doc_id not in self.state["failed_ids"]:
            self.state["failed_ids"].append(doc_id)
            self.save()

    def mark_phase_complete(self, phase: str):
        """Mark a phase as complete."""
        self.state["phases"][phase]["status"] = "completed"
        self.state["phases"][phase]["completed_at"] = time.time()
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
        logger.warning(f"Failed to clean HTML: {e}")
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
            print_console(f"  ✓ Using cached {path.name} ({size / 1024 / 1024:.1f} MB)", style="green")
            return

        print_console(f"  ⬇️  Downloading {path.name}...", style=color)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                total_size = int(response.headers.get("Content-Length", 0))
                
                with Progress(
                    SpinnerColumn(),
                    TextColumn(f"[{color}]{{task.description}}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TimeElapsedColumn(),
                    TimeRemainingColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task(description, total=total_size)
                    
                    downloaded = 0
                    with open(path, "wb") as f:
                        async for chunk in response.content.iter_chunked(65536):
                            f.write(chunk)
                            downloaded += len(chunk)
                            progress.update(task, advance=len(chunk))

    await download_file(metadata_url, metadata_path, "Downloading metadata.parquet", "cyan")
    await download_file(content_url, content_path, "Downloading content.parquet", "blue")

    return metadata_path, content_path


def load_and_prepare_documents(
    metadata_path: Path,
    content_path: Path,
    limit: int | None = None,
    processed_ids: list[str] | None = None,
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

    # Clean HTML in parallel
    rows = merged_df.to_dicts()
    
    print_console("  🧹 Cleaning HTML content...", style="dim")
    from concurrent.futures import ThreadPoolExecutor
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
            "metadata": {
                "so_ky_hieu": row.get("so_ky_hieu", "") or "",
                "ngay_ban_hanh": str(row.get("ngay_ban_hanh", "") or ""),
                "ngay_co_hieu_luc": str(row.get("ngay_co_hieu_luc", "") or ""),
                "co_quan_ban_hanh": row.get("co_quan_ban_hanh", "") or "",
            }
        })

    print_console(f"  ✓ Ready to ingest: {len(documents)} documents", style="green")
    if already_processed > 0:
        print_console(f"  ⏭️  Already processed (skipped): {already_processed}", style="yellow")
    if skipped > 0:
        print_console(f"  ⚠️  Skipped (empty/short): {skipped}", style="yellow")

    return documents


async def ingest_documents_with_tracking(
    documents: list[dict[str, Any]],
    pipeline: IngestionPipeline,
    state_manager: IngestionStateManager,
    batch_size: int = 10,
) -> dict[str, Any]:
    """Ingest documents with real-time progress tracking."""
    
    # Create progress display
    from rich.live import Live
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.text import Text
    
    start_time = time.time()
    
    # Stats tracking
    stats = {
        "total": len(documents),
        "success": 0,
        "failed": 0,
        "postgres": 0,
        "qdrant": 0,
        "opensearch": 0,
        "neo4j": 0,
        "errors": [],
    }
    
    if not documents:
        print_console("\n⚠️  No documents to ingest", style="yellow")
        return stats
    
    # Create layout
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="progress", size=3),
        Layout(name="stats", size=10),
        Layout(name="recent", size=5),
    )
    
    recent_docs = []
    current_batch = 0
    total_batches = (len(documents) + batch_size - 1) // batch_size
    
    with Live(layout, refresh_per_second=2, screen=False) as live:
        # Update header
        layout["header"].update(
            Panel(
                f"[bold cyan]📥 Ingesting {len(documents)} documents into 4 databases[/bold cyan]",
                border_style="cyan",
            )
        )
        
        # Process in batches
        for batch_start in range(0, len(documents), batch_size):
            batch_end = min(batch_start + batch_size, len(documents))
            batch = documents[batch_start:batch_end]
            current_batch = batch_start // batch_size + 1
            
            batch_start_time = time.time()
            
            for doc in batch:
                doc_id = doc["id"]
                doc_title = doc["title"][:60]
                
                try:
                    # Ingest document
                    node = await pipeline.ingest_single_document(
                        title=doc["title"],
                        content=doc["content"],
                    )

                    # Update stats
                    stats["success"] += 1
                    stats["postgres"] += 1
                    stats["qdrant"] += 1
                    stats["opensearch"] += 1
                    stats["neo4j"] += 1

                    # Mark as processed in checkpoint
                    state_manager.mark_processed(doc_id)
                    
                    # Track recent docs
                    recent_docs.insert(0, f"✓ {doc_title}")
                    if len(recent_docs) > 5:
                        recent_docs.pop()

                except Exception as e:
                    stats["failed"] += 1
                    error_msg = f"{doc_id}: {str(e)[:80]}"
                    stats["errors"].append(error_msg)
                    state_manager.mark_failed(doc_id)
                    
                    recent_docs.insert(0, f"✗ {doc_title} - {str(e)[:50]}")
                    if len(recent_docs) > 5:
                        recent_docs.pop()
            
            batch_elapsed = time.time() - batch_start_time
            docs_in_batch = batch_end - batch_start
            docs_per_sec = docs_in_batch / batch_elapsed if batch_elapsed > 0 else 0
            
            # Calculate overall progress
            elapsed = time.time() - start_time
            overall_speed = stats["success"] / elapsed if elapsed > 0 else 0
            eta = (len(documents) - stats["success"]) / overall_speed if overall_speed > 0 else 0
            
            # Update progress bar
            progress_pct = stats["success"] / len(documents) * 100
            progress_bar = "━" * int(progress_pct / 5) + "╺" + "━" * (20 - int(progress_pct / 5))
            
            layout["progress"].update(
                Panel(
                    f"[bold]Progress:[/bold] [{progress_bar}] {progress_pct:.1f}%\n"
                    f"Batch {current_batch}/{total_batches} • {docs_per_sec:.1f} docs/s • "
                    f"ETA: {int(eta//60)}m {int(eta%60)}s",
                    border_style="green",
                )
            )
            
            # Update stats panel
            layout["stats"].update(
                Panel(
                    f"[bold cyan]Database Stats:[/bold cyan]\n\n"
                    f"  PostgreSQL:  [green]{stats['postgres']}[/green] documents\n"
                    f"  Qdrant:      [green]{stats['qdrant']}[/green] vectors\n"
                    f"  OpenSearch:  [green]{stats['opensearch']}[/green] indexed\n"
                    f"  Neo4j:       [green]{stats['neo4j']}[/green] graph nodes\n\n"
                    f"[bold]Overall:[/bold]\n"
                    f"  Success: [green]{stats['success']}/{len(documents)}[/green]\n"
                    f"  Failed:  [red]{stats['failed']}[/red]\n"
                    f"  Speed:   {overall_speed:.1f} docs/s\n"
                    f"  Elapsed: {int(elapsed//60)}m {int(elapsed%60)}s",
                    border_style="cyan",
                )
            )
            
            # Update recent docs panel
            recent_text = "\n".join(recent_docs[:5]) if recent_docs else "Waiting..."
            layout["recent"].update(
                Panel(
                    f"[bold]Recent Documents:[/bold]\n{recent_text}",
                    border_style="dim",
                )
            )
            
            # Save checkpoint after each batch
            state_manager.save()
        
        # Final update
        elapsed = time.time() - start_time
        final_speed = stats["success"] / elapsed if elapsed > 0 else 0
        
        layout["progress"].update(
            Panel(
                f"[bold green]✅ Complete![/bold green]\n"
                f"Total time: {int(elapsed//60)}m {int(elapsed%60)}s • Speed: {final_speed:.1f} docs/s",
                border_style="green",
            )
        )
    
    return stats


def display_final_summary(stats: dict[str, Any], start_time: float):
    """Display final ingestion summary."""
    elapsed = time.time() - start_time
    
    print_console("\n" + "=" * 70, style="bold cyan")
    print_console("✅ INGESTION COMPLETE", style="bold green")
    print_console("=" * 70 + "\n", style="bold cyan")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Database", style="cyan")
    table.add_column("Documents", style="green", justify="right")
    table.add_column("Status", style="yellow")

    success_rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0

    table.add_row("PostgreSQL", str(stats["postgres"]), "✓" if stats["postgres"] > 0 else "✗")
    table.add_row("Qdrant", str(stats["qdrant"]), "✓" if stats["qdrant"] > 0 else "✗")
    table.add_row("OpenSearch", str(stats["opensearch"]), "✓" if stats["opensearch"] > 0 else "✗")
    table.add_row("Neo4j", str(stats["neo4j"]), "✓" if stats["neo4j"] > 0 else "✗")
    table.add_row("", "", "")
    table.add_row("Total Success", str(stats["success"]), f"{success_rate:.1f}%")
    table.add_row("Failed", str(stats["failed"]), "⚠️" if stats["failed"] > 0 else "")
    table.add_row("Time Elapsed", f"{elapsed:.1f}s", "")
    table.add_row("Speed", f"{stats['success']/elapsed:.1f} docs/s" if elapsed > 0 else "N/A", "")

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
        description="Complete dataset ingestion with resume capability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest 50 documents
  python scripts/ingest_complete.py --limit 50

  # Ingest 500 documents with batch size 20
  python scripts/ingest_complete.py --limit 500 --batch-size 20

  # Resume from checkpoint
  python scripts/ingest_complete.py --resume

  # Clear checkpoints and start fresh
  python scripts/ingest_complete.py --clear-checkpoints

  # Ingest all documents (no limit)
  python scripts/ingest_complete.py --no-limit
        """,
    )

    parser.add_argument("--limit", type=int, default=50, help="Number of documents to ingest")
    parser.add_argument("--no-limit", action="store_true", help="Ingest all documents (ignore --limit)")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for processing")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--clear-checkpoints", action="store_true", help="Clear all checkpoints")
    parser.add_argument("--no-cache", action="store_true", help="Don't use cached parquet files")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Setup logging - only show errors
    log_level = logging.ERROR  # Only show errors, not info/debug
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Suppress verbose logging from libraries
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
    print_console("🚀 VIETNAMESE LEGAL DATASET - COMPLETE INGESTION", style="bold cyan")
    print_console("=" * 70 + "\n")

    print_console("📊 Configuration:", style="bold")
    print_console(f"   Dataset: th1nhng0/vietnamese-legal-documents")
    print_console(f"   Limit: {'ALL' if limit is None else limit} documents")
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
    
    health_table = Table(show_header=False, box=None)
    for service, is_healthy in health.items():
        status = "✓ Healthy" if is_healthy else "✗ Unhealthy"
        style = "green" if is_healthy else "red"
        health_table.add_row(f"  {service.upper()}", f"[{style}]{status}[/{style}]")
    
    print_console(health_table)

    unhealthy = [k for k, v in health.items() if not v]
    if unhealthy:
        print_console(f"\n⚠️  Warning: {', '.join(unhealthy)} unhealthy. Ingestion may fail.", style="yellow")
        print_console("   Make sure all Docker containers are running:\n")
        print_console("   docker-compose up -d\n", style="dim")
        
        import sys
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
        
        if state_manager.state["phases"]["download"]["status"] == "completed":
            print_console("  ⏭️  Phase 1 already completed (from checkpoint)", style="green")
            metadata_path = CACHE_DIR / "metadata.parquet"
            content_path = CACHE_DIR / "content.parquet"
        else:
            metadata_path, content_path = await download_parquet_files(
                use_cache=not args.no_cache
            )
            state_manager.mark_phase_complete("download")

        # Phase 2: Load and prepare documents
        print_console("\n" + "=" * 70, style="bold yellow")
        print_console("🔄 PHASE 2: Prepare Documents", style="bold yellow")
        print_console("=" * 70)

        processed_ids = state_manager.state["processed_ids"] if args.resume else []
        
        documents = load_and_prepare_documents(
            metadata_path=metadata_path,
            content_path=content_path,
            limit=limit,
            processed_ids=processed_ids,
        )

        if not documents:
            print_console("\n✅ All documents already processed! Nothing to do.", style="bold green")
            return

        state_manager.state["total_documents"] = len(documents) + len(processed_ids)
        state_manager.save()

        # Phase 3: Ingest into all databases
        print_console("\n" + "=" * 70, style="bold yellow")
        print_console("💾 PHASE 3: Ingest into Databases", style="bold yellow")
        print_console("=" * 70 + "\n")

        stats = await ingest_documents_with_tracking(
            documents=documents,
            pipeline=pipeline,
            state_manager=state_manager,
            batch_size=args.batch_size,
        )

        # Display summary
        display_final_summary(stats, start_time)

        # Mark phases complete
        state_manager.mark_phase_complete("postgres")
        state_manager.mark_phase_complete("qdrant")
        state_manager.mark_phase_complete("opensearch")
        state_manager.mark_phase_complete("neo4j")

    except KeyboardInterrupt:
        print_console("\n\n⚠️  Ingestion cancelled by user. Checkpoint saved.", style="bold yellow")
        print_console("   Resume with: python scripts/ingest_complete.py --resume\n", style="dim")
    except Exception as e:
        print_console(f"\n\n❌ Ingestion failed: {e}", style="bold red")
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        print_console("   Checkpoint saved. Resume with: python scripts/ingest_complete.py --resume\n", style="dim")
        raise
    finally:
        try:
            await pipeline.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
