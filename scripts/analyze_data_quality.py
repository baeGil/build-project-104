#!/usr/bin/env python3
"""
Deep data quality analysis for Vietnamese legal dataset.

Checks:
1. Why 19,586 docs were skipped (empty vs short content)
2. Content duplication analysis
3. Relationship orphan analysis
4. Documents without relationships
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import polars as pl
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

CACHE_DIR = Path("data/cache/datasets")


def analyze_content_quality():
    """Analyze why documents were skipped."""
    console.print("\n" + "="*70)
    console.print(Panel.fit("📊 CONTENT QUALITY ANALYSIS", style="bold cyan"))
    console.print("="*70 + "\n")
    
    # Load data
    console.print("📥 Loading content.parquet...")
    content_df = pl.read_parquet(CACHE_DIR / "content.parquet")
    content_df = content_df.with_columns(pl.col("id").cast(pl.Utf8))
    
    console.print(f"   Total rows: {len(content_df):,}")
    unique_ids = content_df.n_unique("id")
    console.print(f"   Unique IDs: {unique_ids:,}")
    console.print(f"   Duplicates: {len(content_df) - unique_ids:,} ({(len(content_df) - unique_ids)/len(content_df)*100:.1f}%)\n")
    
    # Check content length distribution
    console.print("📏 Content length distribution (BEFORE cleaning):")
    content_lengths = content_df.with_columns([
        pl.col("content_html").str.len_chars().alias("html_length"),
        pl.col("content_html").str.replace_all(r"<[^>]+>", "").str.strip_chars().str.len_chars().alias("text_length_estimate")
    ])
    
    stats = content_lengths.select([
        pl.col("text_length_estimate").min().alias("min"),
        pl.col("text_length_estimate").max().alias("max"),
        pl.col("text_length_estimate").mean().alias("mean"),
        pl.col("text_length_estimate").median().alias("median"),
        pl.col("text_length_estimate").quantile(0.25).alias("p25"),
        pl.col("text_length_estimate").quantile(0.75).alias("p75"),
    ])
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    for row in stats.rows(named=True):
        table.add_row("Min", f"{int(row['min']):,} chars")
        table.add_row("P25", f"{int(row['p25']):,} chars")
        table.add_row("Median", f"{int(row['median']):,} chars")
        table.add_row("Mean", f"{int(row['mean']):,} chars")
        table.add_row("P75", f"{int(row['p75']):,} chars")
        table.add_row("Max", f"{int(row['max']):,} chars")
        break
    
    console.print(table)
    console.print()
    
    # Analyze skipped docs
    console.print("🔍 Analyzing potentially skipped docs (< 50 chars after cleaning):")
    
    short_docs = content_lengths.filter(pl.col("text_length_estimate") < 50)
    console.print(f"   Estimated short docs: {len(short_docs):,}")
    
    if len(short_docs) > 0:
        # Sample some to inspect
        console.print("\n   Sample of short documents:")
        samples = short_docs.head(5)
        for idx, row in enumerate(samples.rows(named=True)):
            console.print(f"\n   [yellow]Doc {row['id']}:[/yellow]")
            console.print(f"   HTML length: {row['html_length']:,} chars")
            console.print(f"   Est text length: {row['text_length_estimate']:,} chars")
            
            # Extract first 200 chars of HTML to see what it contains
            html_sample = str(row['content_html'])[:200]
            console.print(f"   HTML sample: {html_sample}...")
    
    # Check content length buckets
    console.print("\n\n📊 Content length buckets:")
    buckets = content_lengths.with_columns([
        pl.when(pl.col("text_length_estimate") < 50).then(pl.lit("0-49 will_skip"))
        .when(pl.col("text_length_estimate") < 100).then(pl.lit("50-99 risky"))
        .when(pl.col("text_length_estimate") < 200).then(pl.lit("100-199 short"))
        .when(pl.col("text_length_estimate") < 500).then(pl.lit("200-499 medium"))
        .when(pl.col("text_length_estimate") < 1000).then(pl.lit("500-999 good"))
        .otherwise(pl.lit("1000+ long"))
        .alias("bucket")
    ]).group_by("bucket").count().sort("bucket")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Length Bucket", style="cyan")
    table.add_column("Count", style="green")
    table.add_column("Percentage", style="yellow")
    
    for row in buckets.rows(named=True):
        pct = int(row['count']) / len(content_lengths) * 100
        table.add_row(row['bucket'], f"{int(row['count']):,}", f"{pct:.1f}%")
    
    console.print(table)


def analyze_duplicate_content():
    """Analyze duplicate content IDs."""
    console.print("\n\n" + "="*70)
    console.print(Panel.fit("🔍 DUPLICATE CONTENT ANALYSIS", style="bold yellow"))
    console.print("="*70 + "\n")
    
    content_df = pl.read_parquet(CACHE_DIR / "content.parquet")
    content_df = content_df.with_columns(pl.col("id").cast(pl.Utf8))
    
    # Find duplicates
    dup_counts = content_df.group_by("id").agg(pl.len().alias("num_versions")).filter(pl.col("num_versions") > 1).sort("num_versions", descending=True)
    
    console.print(f"Documents with multiple content versions: {len(dup_counts):,}\n")
    
    if len(dup_counts) > 0:
        # Show distribution of duplicate counts
        console.print("📊 Duplicate count distribution:")
        dup_distribution = dup_counts.group_by("num_versions").agg(pl.len().alias("num_docs")).sort("num_versions")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Number of Versions", style="cyan")
        table.add_column("Documents", style="green")
        
        for row in dup_distribution.rows(named=True):
            table.add_row(str(int(row['num_versions'])), f"{int(row['num_docs']):,}")
        
        console.print(table)
        
        # Sample high-duplicate docs
        console.print("\n🔍 Sample documents with most duplicates:")
        top_dupes = dup_counts.head(5)
        
        for row in top_dupes.rows(named=True):
            doc_id = row['id']
            num_versions = row['num_versions']
            console.print(f"\n   [yellow]Doc {doc_id}: {num_versions} versions[/yellow]")
            
            # Get all versions
            versions = content_df.filter(pl.col("id") == doc_id).select("content_html")
            for i, version in enumerate(versions.rows(named=True)):
                html = str(version['content_html'])
                text_len = len(html.replace("<", ">").split(">")[1::2]) if html else 0
                console.print(f"   Version {i+1}: {len(html):,} HTML chars")


def analyze_relationships():
    """Analyze relationship quality and orphaned references."""
    console.print("\n\n" + "="*70)
    console.print(Panel.fit("🔗 RELATIONSHIP ANALYSIS", style="bold magenta"))
    console.print("="*70 + "\n")
    
    # Load data
    console.print("📥 Loading data...")
    metadata_df = pl.read_parquet(CACHE_DIR / "metadata.parquet")
    content_df = pl.read_parquet(CACHE_DIR / "content.parquet")
    relationships_df = pl.read_parquet(CACHE_DIR / "relationships.parquet")
    
    # Cast IDs
    metadata_df = metadata_df.with_columns(pl.col("id").cast(pl.Utf8))
    content_df = content_df.with_columns(pl.col("id").cast(pl.Utf8))
    relationships_df = relationships_df.with_columns([
        pl.col("doc_id").cast(pl.Utf8),
        pl.col("other_doc_id").cast(pl.Utf8),
    ])
    
    # Get valid doc IDs (those that exist in both metadata and content)
    valid_ids = set(metadata_df.select("id").to_series().to_list()) & \
                set(content_df.select("id").to_series().to_list())
    
    console.print(f"   Valid document IDs: {len(valid_ids):,}\n")
    
    # Check orphaned relationships
    console.print("🔍 Checking for orphaned relationships...")
    
    total_rels = len(relationships_df)
    
    # Check doc_id
    orphaned_doc = relationships_df.filter(~pl.col("doc_id").is_in(list(valid_ids)))
    console.print(f"   Relationships with invalid doc_id: {len(orphaned_doc):,} ({len(orphaned_doc)/total_rels*100:.1f}%)")
    
    # Check other_doc_id
    orphaned_other = relationships_df.filter(~pl.col("other_doc_id").is_in(list(valid_ids)))
    console.print(f"   Relationships with invalid other_doc_id: {len(orphaned_other):,} ({len(orphaned_other)/total_rels*100:.1f}%)")
    
    # Total unique orphaned
    orphaned_ids = set(orphaned_doc.select("doc_id").to_series().to_list()) | \
                   set(orphaned_other.select("other_doc_id").to_series().to_list())
    console.print(f"   Total orphaned relationships: {len(orphaned_doc) + len(orphaned_other):,}")
    console.print(f"   Unique invalid IDs referenced: {len(orphaned_ids):,}\n")
    
    # Sample orphaned relationships
    if len(orphaned_doc) > 0:
        console.print("   Sample orphaned relationships (invalid doc_id):")
        samples = orphaned_doc.head(3)
        for row in samples.rows(named=True):
            console.print(f"   • {row['doc_id']} --[{row['relationship']}]→ {row['other_doc_id']}")
    
    console.print()
    
    # Analyze documents without relationships
    console.print("📊 Analyzing documents without relationships...")
    
    # Get docs that have relationships
    docs_with_rels = set(relationships_df.select("doc_id").to_series().to_list())
    docs_as_target = set(relationships_df.select("other_doc_id").to_series().to_list())
    
    all_rel_docs = docs_with_rels | docs_as_target
    
    # Check against valid docs
    valid_docs_in_rels = all_rel_docs & valid_ids
    docs_without_rels = valid_ids - valid_docs_in_rels
    
    console.print(f"   Total valid documents: {len(valid_ids):,}")
    console.print(f"   Documents in relationships (as source): {len(docs_with_rels & valid_ids):,}")
    console.print(f"   Documents in relationships (as target): {len(docs_as_target & valid_ids):,}")
    console.print(f"   Documents with ANY relationship: {len(valid_docs_in_rels):,} ({len(valid_docs_in_rels)/len(valid_ids)*100:.1f}%)")
    console.print(f"   Documents WITHOUT relationships: {len(docs_without_rels):,} ({len(docs_without_rels)/len(valid_ids)*100:.1f}%)\n")
    
    # Relationship type distribution
    console.print("📊 Relationship type distribution:")
    rel_types = relationships_df.group_by("relationship").count().sort("count", descending=True)
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Relationship Type", style="cyan")
    table.add_column("Count", style="green")
    table.add_column("Percentage", style="yellow")
    
    for row in rel_types.rows(named=True):
        pct = int(row['count']) / total_rels * 100
        table.add_row(row['relationship'], f"{int(row['count']):,}", f"{pct:.1f}%")
    
    console.print(table)


def analyze_metadata_content_mismatch():
    """Analyze why some metadata doesn't have content."""
    console.print("\n\n" + "="*70)
    console.print(Panel.fit("📄 METADATA vs CONTENT MISMATCH", style="bold red"))
    console.print("="*70 + "\n")
    
    metadata_df = pl.read_parquet(CACHE_DIR / "metadata.parquet")
    content_df = pl.read_parquet(CACHE_DIR / "content.parquet")
    
    metadata_df = metadata_df.with_columns(pl.col("id").cast(pl.Utf8))
    content_df = content_df.with_columns(pl.col("id").cast(pl.Utf8))
    
    metadata_ids = set(metadata_df.select("id").to_series().to_list())
    content_ids = set(content_df.select("id").to_series().to_list())
    
    # Metadata without content
    meta_only = metadata_ids - content_ids
    console.print(f"📥 Metadata IDs: {len(metadata_ids):,}")
    console.print(f"📄 Content IDs: {len(content_ids):,}")
    console.print(f"❌ Metadata WITHOUT content: {len(meta_only):,} ({len(meta_only)/len(metadata_ids)*100:.1f}%)\n")
    
    if len(meta_only) > 0:
        console.print("🔍 Sample metadata without content:")
        # Get metadata for docs without content
        meta_only_df = metadata_df.filter(pl.col("id").is_in(list(meta_only)))
        
        # Show doc type distribution
        if "loai_van_ban" in meta_only_df.columns:
            console.print("\n   Document type distribution:")
            doc_types = meta_only_df.group_by("loai_van_ban").count().sort("count", descending=True)
            
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Document Type", style="cyan")
            table.add_column("Count", style="green")
            
            for row in doc_types.rows(named=True):
                table.add_row(str(row['loai_van_ban']), f"{int(row['count']):,}")
            
            console.print(table)
        
        # Sample 5 docs
        console.print("\n   Sample 5 documents without content:")
        samples = meta_only_df.head(5)
        for row in samples.rows(named=True):
            console.print(f"   • ID: {row.get('id', 'N/A')}")
            console.print(f"     Title: {row.get('title', 'N/A')}")
            console.print(f"     Type: {row.get('loai_van_ban', 'N/A')}")
            console.print(f"     Date: {row.get('ngay_ban_hanh', 'N/A')}")


if __name__ == "__main__":
    console.print("\n" + "="*70)
    console.print(Panel.fit("🔍 VIETNAMESE LEGAL DATASET - DEEP QUALITY ANALYSIS", style="bold cyan"))
    console.print("="*70)
    
    try:
        analyze_content_quality()
        analyze_duplicate_content()
        analyze_relationships()
        analyze_metadata_content_mismatch()
        
        console.print("\n" + "="*70)
        console.print(Panel.fit("✅ ANALYSIS COMPLETE", style="bold green"))
        console.print("="*70 + "\n")
        
    except Exception as e:
        console.print(f"\n❌ Analysis failed: {e}", style="bold red")
        import traceback
        traceback.print_exc()
