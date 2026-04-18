#!/usr/bin/env python3
"""Re-index existing documents with article-level chunking.

This script clears existing Qdrant and OpenSearch indices,
then re-indexes all documents from PostgreSQL with article-level chunks.

Usage:
    uv run python scripts/reindex_with_articles.py
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from packages.common.config import get_settings
from packages.ingestion.pipeline import IngestionPipeline
from packages.ingestion.parser import parse_legal_document, extract_articles
from packages.common.types import LegalNode

console = Console()


async def main():
    console.print("\n" + "=" * 70, style="bold yellow")
    console.print("🔄 RE-INDEXING WITH ARTICLE-LEVEL CHUNKING", style="bold yellow")
    console.print("=" * 70 + "\n")
    
    settings = get_settings()
    pipeline = IngestionPipeline(settings)
    
    # Step 1: Clear existing indices
    console.print("Step 1: Clearing existing indices...", style="bold cyan")
    
    console.print("  Clearing Qdrant collection...", style="dim")
    try:
        await pipeline.indexer.qdrant_indexer.delete_collection()
        await pipeline.indexer.qdrant_indexer.ensure_collection()
        console.print("  ✓ Qdrant cleared", style="green")
    except Exception as e:
        console.print(f"  ⚠️  Qdrant clear warning: {e}", style="yellow")
    
    console.print("  Clearing OpenSearch index...", style="dim")
    try:
        await pipeline.indexer.opensearch_indexer.delete_index()
        await pipeline.indexer.opensearch_indexer.create_index()
        console.print("  ✓ OpenSearch cleared", style="green")
    except Exception as e:
        console.print(f"  ⚠️  OpenSearch clear warning: {e}", style="yellow")
    
    # Step 2: Load documents from PostgreSQL
    console.print("\nStep 2: Loading documents from PostgreSQL...", style="bold cyan")
    
    pool = await pipeline._get_postgres_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, title, content, doc_type, law_id, metadata
            FROM legal_documents
            ORDER BY id
        """)
    
    console.print(f"  ✓ Loaded {len(rows)} documents", style="green")
    
    if len(rows) == 0:
        console.print("\n❌ No documents found in PostgreSQL!", style="bold red")
        console.print("Please run ingestion first: uv run python scripts/ingest_ultra_fast.py")
        return
    
    # Step 3: Re-index with articles
    console.print("\nStep 3: Re-indexing with article-level chunking...", style="bold cyan")
    
    total_chunks = 0
    total_articles = 0
    errors = 0
    
    for i, row in enumerate(rows, 1):
        try:
            # Re-parse document
            node = parse_legal_document(
                row["content"],
                title=row["title"],
                doc_id=row["id"],
                law_id=row["law_id"],
            )
            
            # Extract articles
            articles = extract_articles(node.content)
            
            # Build chunks list
            chunks_to_index = [node]
            
            for article in articles:
                article_number = str(article["number"])
                article_id = f"{node.id}_article_{article_number}"
                article_title = f"Điều {article_number}. {article['title']}".strip(". ")
                article_content = article["content"] or article_title
                
                article_node = LegalNode(
                    id=article_id,
                    title=article_title,
                    content=article_content,
                    doc_type=node.doc_type,
                    parent_id=node.id,
                    level=2,
                    publish_date=node.publish_date,
                    effective_date=node.effective_date,
                    issuing_body=node.issuing_body,
                    document_number=node.document_number,
                    law_id=node.law_id,
                    keywords=node.keywords,
                    metadata={
                        'chunk_type': 'article',
                        'article_number': int(article_number),
                        'parent_doc_id': node.id,
                    }
                )
                
                chunks_to_index.append(article_node)
            
            # Index all chunks
            await pipeline.indexer.index(chunks_to_index)
            
            total_chunks += len(chunks_to_index)
            total_articles += len(articles)
            
            # Progress update
            if i % 10 == 0 or i == len(rows):
                console.print(
                    f"  Processed {i}/{len(rows)} documents "
                    f"({total_chunks} chunks, {total_articles} articles)",
                    style="dim"
                )
        
        except Exception as e:
            errors += 1
            console.print(f"  ✗ Error processing doc {row['id']}: {e}", style="red")
    
    # Final summary
    console.print("\n" + "=" * 70, style="bold green")
    console.print("✅ RE-INDEXING COMPLETE", style="bold green")
    console.print("=" * 70 + "\n")
    
    console.print("📊 Summary:", style="bold cyan")
    console.print(f"  Documents processed: {len(rows)}")
    console.print(f"  Total chunks indexed: {total_chunks}")
    console.print(f"  Total articles: {total_articles}")
    console.print(f"  Avg chunks/doc: {total_chunks / len(rows):.1f}")
    console.print(f"  Avg articles/doc: {total_articles / len(rows):.1f}")
    console.print(f"  Errors: {errors}")
    
    console.print("\n🔍 Next steps:", style="bold yellow")
    console.print("  1. Verify counts: uv run python scripts/check_index_counts.py")
    console.print("  2. Run ground truth test: uv run python scripts/test_groundtruth.py")
    console.print("  3. Check RRF trace: uv run python scripts/trace_rrf.py")
    console.print()


if __name__ == "__main__":
    asyncio.run(main())
