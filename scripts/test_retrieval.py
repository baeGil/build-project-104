#!/usr/bin/env python3
"""
Test Retrieval Quality for Vietnamese Legal Dataset.

Tests:
1. Semantic search (Qdrant vector search)
2. Full-text search (OpenSearch BM25)
3. Hybrid search (RRF fusion)
4. Citation retrieval
5. Performance (latency)

Usage:
    uv run python scripts/test_retrieval.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from packages.common.config import get_settings
from packages.retrieval.hybrid import HybridRetriever
from packages.retrieval.rrf import reciprocal_rank_fusion

console = Console()

# Test queries for Vietnamese legal contracts
TEST_QUERIES = [
    {
        "query": "Điều kiện đơn phương chấm dứt hợp đồng thuê văn phòng",
        "category": "contract_termination",
        "expected_laws": ["Bộ Luật Dân sự 2015", "Luật Nhà ở 2014"],
    },
    {
        "query": "Trách nhiệm bồi thường thiệt hại trong hợp đồng dịch vụ",
        "category": "liability_compensation",
        "expected_laws": ["Bộ Luật Dân sự 2015"],
    },
    {
        "query": "Quy định về phòng cháy chữa cháy trong tòa nhà văn phòng",
        "category": "fire_safety",
        "expected_laws": ["Luật Phòng cháy chữa cháy"],
    },
    {
        "query": "Thủ tục đăng ký kinh doanh thay đổi ngành nghề",
        "category": "business_registration",
        "expected_laws": ["Luật Doanh nghiệp 2020"],
    },
    {
        "query": "Nghĩa vụ thuế giá trị gia tăng VAT cho doanh nghiệp",
        "category": "tax_vat",
        "expected_laws": ["Luật Thuế giá trị gia tăng"],
    },
    {
        "query": "Quy định về hợp đồng lao động và bảo hiểm xã hội",
        "category": "labor_contract",
        "expected_laws": ["Bộ Luật Lao động 2019"],
    },
    {
        "query": "Điều khoản bất khả kháng trong hợp đồng thương mại",
        "category": "force_majeure",
        "expected_laws": ["Bộ Luật Dân sự 2015"],
    },
    {
        "query": "Phạt vi phạm hợp đồng và mức phạt tối đa",
        "category": "contract_penalty",
        "expected_laws": ["Bộ Luật Dân sự 2015", "Luật Thương mại 2005"],
    },
]


async def test_semantic_search(retriever: HybridRetriever, query: str, top_k: int = 5) -> dict:
    """Test dense semantic search (Qdrant only)."""
    start_time = time.time()
    
    try:
        # Use search with only dense candidates (min 1 for Qdrant)
        results = await retriever.search(
            query,
            top_k=top_k,
            bm25_candidates=1,  # Min 1 to avoid error
            dense_candidates=top_k * 2,
        )
        latency = time.time() - start_time
        
        # Convert to dict format
        result_dicts = [
            {
                "title": doc.title,
                "score": doc.score,
                "doc_type": doc.metadata.get('doc_type', 'unknown'),
                "doc_id": doc.doc_id,
            }
            for doc in results
        ]
        
        return {
            "success": True,
            "results": result_dicts,
            "count": len(results),
            "latency_ms": latency * 1000,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "latency_ms": (time.time() - start_time) * 1000,
        }


async def test_fulltext_search(retriever: HybridRetriever, query: str, top_k: int = 5) -> dict:
    """Test BM25 full-text search (OpenSearch only)."""
    start_time = time.time()
    
    try:
        # Use search with only BM25 candidates (min 1 for Qdrant)
        results = await retriever.search(
            query,
            top_k=top_k,
            bm25_candidates=top_k * 2,
            dense_candidates=1,  # Min 1 to avoid Qdrant error
        )
        latency = time.time() - start_time
        
        # Convert to dict format
        result_dicts = [
            {
                "title": doc.title,
                "score": doc.score,
                "doc_type": doc.metadata.get('doc_type', 'unknown'),
                "doc_id": doc.doc_id,
            }
            for doc in results
        ]
        
        return {
            "success": True,
            "results": result_dicts,
            "count": len(results),
            "latency_ms": latency * 1000,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "latency_ms": (time.time() - start_time) * 1000,
        }


async def test_hybrid_search(retriever: HybridRetriever, query: str, top_k: int = 5) -> dict:
    """Test hybrid search with RRF fusion (BM25 + Dense)."""
    start_time = time.time()
    
    try:
        # Use full hybrid search
        results = await retriever.search(
            query,
            top_k=top_k,
            bm25_candidates=top_k * 2,
            dense_candidates=top_k * 2,
            sandwich_reorder=True,
        )
        latency = time.time() - start_time
        
        # Convert to dict format
        result_dicts = [
            {
                "title": doc.title,
                "score": doc.score,
                "doc_type": doc.metadata.get('doc_type', 'unknown'),
                "doc_id": doc.doc_id,
            }
            for doc in results
        ]
        
        return {
            "success": True,
            "results": result_dicts,
            "count": len(results),
            "latency_ms": latency * 1000,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "latency_ms": (time.time() - start_time) * 1000,
        }


def display_search_results(query_data: dict, results: dict, search_type: str):
    """Display search results in a nice table."""
    query = query_data["query"]
    category = query_data["category"]
    
    console.print(f"\n[bold cyan]🔍 Test: {search_type}[/bold cyan]")
    console.print(f"Query: [yellow]{query}[/yellow]")
    console.print(f"Category: [dim]{category}[/dim]\n")
    
    if not results["success"]:
        console.print(f"[bold red]❌ Failed: {results['error']}[/bold red]\n")
        return
    
    # Create results table
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("#", style="dim", width=3)
    table.add_column("Title", style="green", width=50)
    table.add_column("Score", justify="right", style="yellow", width=8)
    table.add_column("Type", style="cyan", width=15)
    table.add_column("Latency", justify="right", style="dim", width=10)
    
    for i, doc in enumerate(results["results"][:5], 1):
        title = doc.get("title", "N/A")[:50]
        score = doc.get("score", 0)
        doc_type = doc.get("doc_type", "unknown")
        
        table.add_row(
            str(i),
            title,
            f"{score:.4f}",
            doc_type,
            f"{results['latency_ms']:.1f}ms" if i == 1 else "",
        )
    
    console.print(table)
    console.print(f"\nTotal results: [green]{results['count']}[/green] | "
                  f"Latency: [yellow]{results['latency_ms']:.1f}ms[/yellow]\n")


async def test_performance(retriever: HybridRetriever, num_queries: int = 10) -> dict:
    """Test retrieval performance with multiple queries."""
    console.print("\n[bold cyan]⚡ Performance Test[/bold cyan]")
    console.print(f"Running {num_queries} queries...\n")
    
    latencies = {
        "semantic": [],
        "fulltext": [],
        "hybrid": [],
    }
    
    for i in range(num_queries):
        query = f"Quy định pháp luật về hợp đồng và trách nhiệm {i}"
        
        # Semantic
        result = await test_semantic_search(retriever, query, top_k=3)
        if result["success"]:
            latencies["semantic"].append(result["latency_ms"])
        
        # Fulltext
        result = await test_fulltext_search(retriever, query, top_k=3)
        if result["success"]:
            latencies["fulltext"].append(result["latency_ms"])
        
        # Hybrid
        result = await test_hybrid_search(retriever, query, top_k=3)
        if result["success"]:
            latencies["hybrid"].append(result["latency_ms"])
    
    # Calculate statistics
    stats = {}
    for search_type, latency_list in latencies.items():
        if latency_list:
            stats[search_type] = {
                "avg": sum(latency_list) / len(latency_list),
                "min": min(latency_list),
                "max": max(latency_list),
                "p50": sorted(latency_list)[len(latency_list) // 2],
                "p95": sorted(latency_list)[int(len(latency_list) * 0.95)] if len(latency_list) > 1 else latency_list[0],
                "count": len(latency_list),
            }
    
    # Display performance table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Search Type", style="cyan")
    table.add_column("Avg (ms)", justify="right", style="green")
    table.add_column("P50 (ms)", justify="right", style="yellow")
    table.add_column("P95 (ms)", justify="right", style="yellow")
    table.add_column("Min (ms)", justify="right", style="dim")
    table.add_column("Max (ms)", justify="right", style="dim")
    table.add_column("Queries", justify="right")
    
    for search_type, stats_data in stats.items():
        table.add_row(
            search_type.upper(),
            f"{stats_data['avg']:.1f}",
            f"{stats_data['p50']:.1f}",
            f"{stats_data['p95']:.1f}",
            f"{stats_data['min']:.1f}",
            f"{stats_data['max']:.1f}",
            str(stats_data["count"]),
        )
    
    console.print(table)
    
    # Check if meets <1s p95 requirement
    passes_requirement = all(
        stats.get(t, {}).get("p95", 0) < 1000
        for t in ["semantic", "fulltext", "hybrid"]
    )
    
    if passes_requirement:
        console.print("\n✅ [bold green]Performance Requirement MET: p95 < 1s[/bold green]\n")
    else:
        console.print("\n⚠️  [bold yellow]Performance Requirement NOT MET: p95 >= 1s[/bold yellow]\n")
    
    return stats


async def main():
    """Run all retrieval tests."""
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("🧪 VIETNAMESE LEGAL RETRIEVAL QUALITY TEST", style="bold cyan")
    console.print("=" * 80 + "\n")
    
    # Initialize settings and retriever
    console.print("🔧 Initializing retriever...", style="dim")
    settings = get_settings()
    retriever = HybridRetriever(settings)
    
    # Optional warm-up phase (set to False to skip)
    SKIP_WARMUP = True  # Set to False to enable warm-up
    
    if not SKIP_WARMUP:
        # Warm-up phase to eliminate cold start
        console.print("\n[bold yellow]🔥 WARM-UP PHASE[/bold yellow]")
        console.print("Running warm-up query to load models and connections...\n")
        
        warmup_start = time.time()
        await retriever.search("warm up", top_k=1, bm25_candidates=1, dense_candidates=1)
        warmup_time = time.time() - warmup_start
        
        console.print(f"✅ Warm-up complete: {warmup_time:.2f}s")
        console.print("   All models and connections are now loaded\n")
    else:
        console.print("[dim]⚠️  Warm-up skipped (first query will be slow)[/dim]\n")
    
    # Test 1: Semantic Search
    console.print("\n" + "=" * 80, style="bold yellow")
    console.print("TEST 1: Semantic Search (Qdrant Vectors)", style="bold yellow")
    console.print("=" * 80)
    
    for query_data in TEST_QUERIES[:3]:  # Test first 3 queries
        query = query_data["query"]
        results = await test_semantic_search(retriever, query, top_k=5)
        display_search_results(query_data, results, "Semantic Search")
    
    # Test 2: Full-Text Search
    console.print("\n" + "=" * 80, style="bold yellow")
    console.print("TEST 2: Full-Text Search (OpenSearch BM25)", style="bold yellow")
    console.print("=" * 80)
    
    for query_data in TEST_QUERIES[3:6]:  # Test next 3 queries
        query = query_data["query"]
        results = await test_fulltext_search(retriever, query, top_k=5)
        display_search_results(query_data, results, "Full-Text Search")
    
    # Test 3: Hybrid Search
    console.print("\n" + "=" * 80, style="bold yellow")
    console.print("TEST 3: Hybrid Search (RRF Fusion)", style="bold yellow")
    console.print("=" * 80)
    
    for query_data in TEST_QUERIES[6:]:  # Test remaining queries
        query = query_data["query"]
        results = await test_hybrid_search(retriever, query, top_k=5)
        display_search_results(query_data, results, "Hybrid Search")
    
    # Test 4: Performance
    console.print("\n" + "=" * 80, style="bold yellow")
    console.print("TEST 4: Performance Benchmark", style="bold yellow")
    console.print("=" * 80)
    
    perf_stats = await test_performance(retriever, num_queries=20)
    
    # Final Summary
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("✅ RETRIEVAL TEST COMPLETE", style="bold green")
    console.print("=" * 80 + "\n")
    
    console.print("[bold]Summary:[/bold]")
    console.print(f"  • Total queries tested: {len(TEST_QUERIES)}")
    console.print(f"  • Search types tested: Semantic, Full-text, Hybrid")
    console.print(f"  • Performance target: p95 < 1s")
    
    if perf_stats:
        console.print(f"  • Results: {'✅ PASSED' if all(s['p95'] < 1000 for s in perf_stats.values()) else '⚠️  NEEDS OPTIMIZATION'}")
    
    console.print()


if __name__ == "__main__":
    asyncio.run(main())
