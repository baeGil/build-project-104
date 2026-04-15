#!/usr/bin/env python3
"""
Ingest relationships from HuggingFace dataset into Neo4j.

This script:
1. Downloads relationships.parquet from HuggingFace
2. Loads relationship data (doc_id, other_doc_id, relationship_type)
3. Creates relationships in Neo4j between legal documents
4. Supports batch processing with progress tracking

Usage:
    python database/ingest_relationships.py --limit 1000
    python database/ingest_relationships.py --limit 50000 --batch-size 500
    python database/ingest_relationships.py  # Ingest all relationships

Relationships types:
- "Văn bản căn cứ" (Legal basis)
- "Văn bản được sửa đổi" (Amended document)
- "Văn bản sửa đổi" (Amending document)
- "Văn bản hướng dẫn" (Guidance document)
- And more...
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import logging

import polars as pl
from neo4j import AsyncGraphDatabase
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from packages.common.config import get_settings

logger = logging.getLogger(__name__)
console = Console()

# Cache directory
CACHE_DIR = Path("data/cache/datasets")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


async def download_relationships_parquet(use_cache: bool = True) -> Path:
    """Download relationships.parquet from HuggingFace."""
    import aiohttp
    
    dataset_name = "th1nhng0/vietnamese-legal-documents"
    url = f"https://huggingface.co/datasets/{dataset_name}/resolve/main/data/relationships.parquet"
    cache_path = CACHE_DIR / "relationships.parquet"
    
    if use_cache and cache_path.exists():
        size_mb = cache_path.stat().st_size / 1024 / 1024
        console.print(f"✓ Using cached relationships.parquet ({size_mb:.1f} MB)", style="green")
        return cache_path
    
    console.print(f"⬇️  Downloading relationships.parquet from HuggingFace...", style="cyan")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            total_size = int(response.headers.get("Content-Length", 0))
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Downloading relationships.parquet", total=total_size)
                
                downloaded = 0
                with open(cache_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress.update(task, advance=len(chunk))
    
    size_mb = cache_path.stat().st_size / 1024 / 1024
    console.print(f"✓ Downloaded relationships.parquet ({size_mb:.1f} MB)", style="green")
    return cache_path


def load_relationships(parquet_path: Path, limit: int | None = None) -> pl.DataFrame:
    """Load relationships from parquet file using Polars."""
    console.print(f"\n📊 Loading relationships from {parquet_path}...", style="yellow")
    
    df = pl.read_parquet(parquet_path)
    
    console.print(f"  Total relationships: {len(df):,}", style="dim")
    console.print(f"  Columns: {df.columns}", style="dim")
    
    # Show relationship types
    if "relationship" in df.columns:
        rel_types = df["relationship"].value_counts().sort("count", descending=True)
        console.print(f"\n  Relationship types:", style="dim")
        for row in rel_types.iter_rows():
            console.print(f"    - {row[0]}: {row[1]:,}", style="dim")
    
    if limit:
        df = df.head(limit)
        console.print(f"\n  Limited to: {limit:,} relationships", style="yellow")
    
    return df


async def ingest_relationships_to_neo4j(
    relationships_df: pl.DataFrame,
    batch_size: int = 500,
) -> dict:
    """Ingest relationships into Neo4j graph database."""
    settings = get_settings()
    
    console.print(f"\n🔗 Connecting to Neo4j...", style="yellow")
    
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    
    async with driver as driver:
        # Test connection
        await driver.verify_connectivity()
        console.print(f"✓ Connected to Neo4j at {settings.neo4j_uri}", style="green")
        
        # Create index on doc_id for faster relationship creation
        console.print(f"\n📝 Creating indexes if not exist...", style="yellow")
        async with driver.session() as session:
            await session.run(
                "CREATE INDEX legal_doc_id_idx IF NOT EXISTS FOR (n:LegalDocument) ON (n.doc_id)"
            )
        console.print(f"✓ Indexes ready", style="green")
        
        # Process in batches
        total = len(relationships_df)
        stats = {
            "total": total,
            "success": 0,
            "failed": 0,
            "errors": [],
        }
        
        console.print(f"\n🚀 Ingesting relationships in batches of {batch_size}...", style="yellow")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[yellow]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Ingesting relationships",
                total=total,
            )
            
            for batch_start in range(0, total, batch_size):
                batch_end = min(batch_start + batch_size, total)
                batch_df = relationships_df[batch_start:batch_end]
                
                try:
                    # Build Cypher query for batch
                    # Using UNWIND for efficient batch insert
                    params = {
                        "relationships": [
                            {
                                "doc_id": str(row["doc_id"]),
                                "other_doc_id": str(row["other_doc_id"]),
                                "relationship_type": row["relationship"],
                            }
                            for row in batch_df.iter_rows(named=True)
                        ]
                    }
                    
                    cypher = """
                    UNWIND $relationships AS rel
                    MATCH (source:LegalDocument {doc_id: rel.doc_id})
                    MATCH (target:LegalDocument {doc_id: rel.other_doc_id})
                    CALL apoc.create.relationship(
                        source, 
                        rel.relationship_type,
                        {created_at: datetime()},
                        target
                    ) YIELD rel AS created_rel
                    RETURN count(*) AS count
                    """
                    
                    async with driver.session() as session:
                        result = await session.run(cypher, params)
                        record = await result.single()
                        
                        if record:
                            count = record["count"]
                            stats["success"] += count
                    
                    progress.update(task, advance=len(batch_df))
                    
                except Exception as e:
                    stats["failed"] += len(batch_df)
                    error_msg = f"Batch {batch_start}-{batch_end}: {str(e)}"
                    stats["errors"].append(error_msg)
                    logger.error(error_msg)
                    
                    # Try fallback without apoc
                    try:
                        await ingest_relationships_fallback(
                            driver, batch_df, stats, progress, task
                        )
                    except Exception as fallback_error:
                        logger.error(f"Fallback also failed: {fallback_error}")
        
        return stats


async def ingest_relationships_fallback(
    driver,
    batch_df: pl.DataFrame,
    stats: dict,
    progress,
    task,
):
    """Fallback method without APOC - use MERGE for relationships."""
    params = {
        "relationships": [
            {
                "doc_id": str(row["doc_id"]),
                "other_doc_id": str(row["other_doc_id"]),
                "relationship_type": row["relationship"],
            }
            for row in batch_df.iter_rows(named=True)
        ]
    }
    
    # Use MERGE to avoid duplicate relationships
    cypher = """
    UNWIND $relationships AS rel
    MATCH (source:LegalDocument {doc_id: rel.doc_id})
    MATCH (target:LegalDocument {doc_id: rel.other_doc_id})
    MERGE (source)-[r:RELATES_TO {type: rel.relationship_type}]->(target)
    ON CREATE SET r.created_at = datetime()
    RETURN count(*) AS count
    """
    
    async with driver.session() as session:
        result = await session.run(cypher, params)
        record = await result.single()
        
        if record:
            count = record["count"]
            stats["success"] += count
    
    progress.update(task, advance=len(batch_df))


async def main():
    """Main ingestion script."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Ingest relationships from HuggingFace dataset into Neo4j"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of relationships to ingest (default: all)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch size for Neo4j ingestion (default: 500)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Don't use cached parquet file",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    console.print("\n" + "=" * 70, style="bold cyan")
    console.print("🔗 NEO4J RELATIONSHIPS INGESTION", style="bold cyan")
    console.print("=" * 70 + "\n")
    
    console.print("📊 Configuration:", style="bold")
    console.print(f"   Dataset: th1nhng0/vietnamese-legal-documents")
    console.print(f"   Config: relationships")
    console.print(f"   Limit: {'ALL' if args.limit is None else f'{args.limit:,}'}")
    console.print(f"   Batch size: {args.batch_size}")
    console.print(f"   Cache: {'No' if args.no_cache else 'Yes'}")
    console.print()
    
    start_time = time.time()
    
    try:
        # Step 1: Download relationships.parquet
        console.print("[bold yellow]Step 1/3: Download relationships.parquet[/bold yellow]")
        parquet_path = await download_relationships_parquet(use_cache=not args.no_cache)
        
        # Step 2: Load relationships with Polars
        console.print("\n[bold yellow]Step 2/3: Load relationships[/bold yellow]")
        relationships_df = load_relationships(parquet_path, limit=args.limit)
        
        if len(relationships_df) == 0:
            console.print("\n❌ No relationships to ingest!", style="bold red")
            return 1
        
        # Step 3: Ingest into Neo4j
        console.print("\n[bold yellow]Step 3/3: Ingest into Neo4j[/bold yellow]")
        stats = await ingest_relationships_to_neo4j(
            relationships_df,
            batch_size=args.batch_size,
        )
        
        # Summary
        elapsed = time.time() - start_time
        
        console.print("\n" + "=" * 70, style="bold green")
        console.print("✅ RELATIONSHIPS INGESTION COMPLETE", style="bold green")
        console.print("=" * 70 + "\n")
        
        console.print(f"[bold]Summary:[/bold]")
        console.print(f"  Total relationships: {stats['total']:,}")
        console.print(f"  Successfully ingested: {stats['success']:,}")
        console.print(f"  Failed: {stats['failed']:,}")
        console.print(f"  Time elapsed: {elapsed:.1f}s")
        console.print(f"  Rate: {stats['success'] / elapsed:,.0f} relationships/second")
        
        if stats['errors']:
            console.print(f"\n[bold yellow]Errors ({len(stats['errors'])}):[/bold yellow]")
            for error in stats['errors'][:5]:  # Show first 5 errors
                console.print(f"  ⚠️  {error}", style="yellow")
        
        console.print("\n[bold green]✓ Relationships are now available in Neo4j![/bold green]")
        console.print("  You can query them with:")
        console.print("  MATCH (a)-[r]->(b) RETURN a.doc_id, type(r), b.doc_id LIMIT 10")
        
        return 0
        
    except Exception as e:
        console.print(f"\n❌ Ingestion failed: {e}", style="bold red")
        logger.exception("Full error details:")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
