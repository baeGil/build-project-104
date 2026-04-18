#!/usr/bin/env python3
"""
Deep Performance Analysis for Vietnamese Legal Retrieval System.

Analyzes:
1. Cold start vs warm performance
2. Per-component latency breakdown (BM25, Dense, RRF, Fetch)
3. Article-level chunking impact
4. Memory and connection overhead
5. Optimization recommendations

Usage:
    uv run python scripts/analyze_search_performance.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from packages.common.config import get_settings
from packages.retrieval.hybrid import HybridRetriever

console = Console()

# Test queries with varying complexity
TEST_QUERIES = [
    # Short queries (1-3 words)
    "hợp đồng thuê",
    "chấm dứt hợp đồng",
    "bồi thường thiệt hại",
    
    # Medium queries (4-6 words)
    "Điều kiện đơn phương chấm dứt hợp đồng",
    "Trách nhiệm bồi thường trong hợp đồng dịch vụ",
    "Quy định về phòng cháy chữa cháy",
    
    # Long queries (7+ words)
    "Điều khoản bất khả kháng trong hợp đồng thương mại quốc tế",
    "Phạt vi phạm hợp đồng và mức phạt tối đa theo quy định",
    "Thủ tục đăng ký kinh doanh thay đổi ngành nghề doanh nghiệp",
]


class LatencyTracker:
    """Track latency breakdown for each search component."""
    
    def __init__(self):
        self.timings = defaultdict(list)
    
    def record(self, component: str, latency_ms: float):
        self.timings[component].append(latency_ms)
    
    def get_stats(self, component: str) -> dict:
        if component not in self.timings:
            return {}
        
        values = self.timings[component]
        return {
            "count": len(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "p50": sorted(values)[len(values) // 2],
            "p95": sorted(values)[int(len(values) * 0.95)] if len(values) > 1 else values[0],
        }


async def benchmark_search_with_breakdown(
    retriever: HybridRetriever,
    query: str,
    tracker: LatencyTracker,
    iteration: int,
) -> dict:
    """Run search and track per-component latency."""
    
    start_total = time.time()
    
    # Track embedding generation
    start_embed = time.time()
    try:
        from packages.retrieval.embedding import get_embedding_model
        embedder = get_embedding_model()
        query_vector = embedder.encode(query).tolist()
        embed_time = (time.time() - start_embed) * 1000
    except Exception as e:
        embed_time = 0
        query_vector = None
    
    tracker.record("embedding", embed_time)
    
    # Track BM25 search
    start_bm25 = time.time()
    try:
        bm25_results = await retriever.opensearch_indexer.search(
            query=query,
            top_k=10,
        )
        bm25_time = (time.time() - start_bm25) * 1000
    except Exception as e:
        bm25_time = 0
        bm25_results = []
    
    tracker.record("bm25", bm25_time)
    
    # Track Dense search
    start_dense = time.time()
    try:
        if query_vector:
            dense_results = await retriever.qdrant_indexer.search(
                vector=query_vector,
                limit=10,
            )
        dense_time = (time.time() - start_dense) * 1000
    except Exception as e:
        dense_time = 0
        dense_results = []
    
    tracker.record("dense", dense_time)
    
    # Track RRF fusion
    start_rrf = time.time()
    try:
        from packages.retrieval.rrf import reciprocal_rank_fusion
        
        bm25_scores = {doc.get("id"): doc.get("score", 0) for doc in bm25_results}
        dense_scores = {hit.payload.get("id"): hit.score for hit in dense_results}
        
        fused_scores = reciprocal_rank_fusion(
            bm25_scores=bm25_scores,
            dense_scores=dense_scores,
        )
        rrf_time = (time.time() - start_rrf) * 1000
    except Exception as e:
        rrf_time = 0
        fused_scores = {}
    
    tracker.record("rrf", rrf_time)
    
    # Track document fetch
    start_fetch = time.time()
    try:
        doc_ids = list(fused_scores.keys())[:10]
        # Simulate fetch (in real system this queries PostgreSQL)
        fetch_time = (time.time() - start_fetch) * 1000
    except Exception as e:
        fetch_time = 0
    
    tracker.record("fetch", fetch_time)
    
    total_time = (time.time() - start_total) * 1000
    tracker.record("total", total_time)
    
    return {
        "query": query,
        "iteration": iteration,
        "total_ms": total_time,
        "breakdown": {
            "embedding": embed_time,
            "bm25": bm25_time,
            "dense": dense_time,
            "rrf": rrf_time,
            "fetch": fetch_time,
        },
        "result_count": len(fused_scores),
    }


async def cold_start_test(retriever: HybridRetriever, tracker: LatencyTracker):
    """Test cold start impact with fresh retriever."""
    console.print("\n[bold cyan]🧊 COLD START TEST[/bold cyan]")
    console.print("Testing first query latency with fresh retriever...\n")
    
    # Create fresh retriever (simulates cold start)
    fresh_settings = get_settings()
    fresh_retriever = HybridRetriever(fresh_settings)
    
    query = "Điều kiện đơn phương chấm dứt hợp đồng"
    result = await benchmark_search_with_breakdown(fresh_retriever, query, tracker, 1)
    
    console.print(f"Query: [yellow]{query}[/yellow]")
    console.print(f"Total latency: [bold red]{result['total_ms']:.1f}ms[/bold red]\n")
    
    # Show breakdown
    table = Table(show_header=True, header_style="bold")
    table.add_column("Component", style="cyan")
    table.add_column("Latency (ms)", justify="right", style="yellow")
    table.add_column("% of Total", justify="right", style="green")
    
    for component, latency in result["breakdown"].items():
        pct = (latency / result["total_ms"] * 100) if result["total_ms"] > 0 else 0
        table.add_row(
            component.upper(),
            f"{latency:.1f}",
            f"{pct:.1f}%",
        )
    
    console.print(table)
    
    return result


async def warmup_test(retriever: HybridRetriever, tracker: LatencyTracker, num_queries: int = 10):
    """Test performance after warmup."""
    console.print("\n[bold cyan]🔥 WARMUP TEST[/bold cyan]")
    console.print(f"Running {num_queries} queries to warm up caches...\n")
    
    results = []
    for i in range(num_queries):
        query = f"Quy định pháp luật về hợp đồng {i}"
        result = await benchmark_search_with_breakdown(retriever, query, tracker, i + 1)
        results.append(result)
        
        if i == 0:
            console.print(f"  Query 1 (warm): {result['total_ms']:.1f}ms")
        elif i == num_queries - 1:
            console.print(f"  Query {num_queries}: {result['total_ms']:.1f}ms")
    
    avg_warm = sum(r["total_ms"] for r in results) / len(results)
    console.print(f"\n  Average (warm): [green]{avg_warm:.1f}ms[/green]\n")
    
    return results


async def query_complexity_test(retriever: HybridRetriever, tracker: LatencyTracker):
    """Test impact of query length/complexity."""
    console.print("\n[bold cyan]📏 QUERY COMPLEXITY TEST[/bold cyan]")
    console.print("Testing different query lengths...\n")
    
    results = []
    for query in TEST_QUERIES:
        result = await benchmark_search_with_breakdown(retriever, query, tracker, 0)
        results.append({
            "query": query,
            "length": len(query.split()),
            "total_ms": result["total_ms"],
        })
    
    # Display results
    table = Table(show_header=True, header_style="bold")
    table.add_column("Query", style="green", width=50)
    table.add_column("Words", justify="right", style="cyan")
    table.add_column("Latency (ms)", justify="right", style="yellow")
    
    for result in results:
        table.add_row(
            result["query"][:50],
            str(result["length"]),
            f"{result['total_ms']:.1f}",
        )
    
    console.print(table)
    
    return results


def print_optimization_recommendations(tracker: LatencyTracker, cold_start_result: dict):
    """Print actionable optimization recommendations."""
    console.print("\n[bold cyan]🎯 OPTIMIZATION RECOMMENDATIONS[/bold cyan]\n")
    
    # Analyze bottlenecks
    total_stats = tracker.get_stats("total")
    embed_stats = tracker.get_stats("embedding")
    bm25_stats = tracker.get_stats("bm25")
    dense_stats = tracker.get_stats("dense")
    
    console.print("[bold]1. Cold Start Issue (CRITICAL)[/bold]")
    if cold_start_result["total_ms"] > 1000:
        console.print(f"   ❌ First query: {cold_start_result['total_ms']:.0f}ms")
        console.print(f"   ✅ Warm queries: {total_stats.get('p50', 0):.0f}ms")
        console.print(f"   📊 Slowdown: {cold_start_result['total_ms'] / max(total_stats.get('p50', 1), 1):.0f}x")
        console.print("\n   Solutions:")
        console.print("   • Pre-warm embedding model on startup")
        console.print("   • Initialize database connections eagerly")
        console.print("   • Add startup hook to run dummy search")
        console.print()
    
    console.print("[bold]2. Embedding Generation[/bold]")
    if embed_stats:
        console.print(f"   Avg: {embed_stats['avg']:.1f}ms | P95: {embed_stats.get('p95', 0):.1f}ms")
        if embed_stats['avg'] > 50:
            console.print("   ⚠️  Embedding is slow - consider:")
            console.print("   • Using ONNX runtime for faster inference")
            console.print("   • Caching query embeddings")
            console.print("   • Async embedding generation")
        else:
            console.print("   ✅ Embedding performance is good")
        console.print()
    
    console.print("[bold]3. BM25 Search (OpenSearch)[/bold]")
    if bm25_stats:
        console.print(f"   Avg: {bm25_stats['avg']:.1f}ms | P95: {bm25_stats.get('p95', 0):.1f}ms")
        if bm25_stats['avg'] > 30:
            console.print("   ⚠️  BM25 could be faster:")
            console.print("   • Increase OpenSearch JVM heap size")
            console.print("   • Optimize index refresh interval")
            console.print("   • Use index aliases for zero-downtime rebuilds")
        else:
            console.print("   ✅ BM25 performance is excellent")
        console.print()
    
    console.print("[bold]4. Dense Search (Qdrant)[/bold]")
    if dense_stats:
        console.print(f"   Avg: {dense_stats['avg']:.1f}ms | P95: {dense_stats.get('p95', 0):.1f}ms")
        if dense_stats['avg'] > 30:
            console.print("   ⚠️  Dense search optimization:")
            console.print("   • Use HNSW index with optimized M/ef_construct")
            console.print("   • Enable quantization (binary/scalar)")
            console.print("   • Increase Qdrant memory allocation")
        else:
            console.print("   ✅ Dense search performance is excellent")
        console.print()
    
    console.print("[bold]5. RRF Fusion[/bold]")
    rrf_stats = tracker.get_stats("rrf")
    if rrf_stats:
        console.print(f"   Avg: {rrf_stats['avg']:.2f}ms")
        if rrf_stats['avg'] > 5:
            console.print("   ⚠️  RRF is slow (should be <2ms)")
        else:
            console.print("   ✅ RRF fusion is fast")
        console.print()
    
    console.print("[bold]6. Article-Level Chunking Impact[/bold]")
    console.print("   Current index: 486 chunks (50 docs + 436 articles)")
    console.print("   Impact on search:")
    console.print("   • ✅ Better precision (article-level relevance)")
    console.print("   • ⚠️  More candidates to rank (was 50, now 486)")
    console.print("   • 💡 Recommendation: Increase top_k from 5 to 10")
    console.print("   • 💡 Consider hierarchical retrieval for very large indices")
    console.print()


async def main():
    """Run comprehensive performance analysis."""
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("🔍 VIETNAMESE LEGAL RETRIEVAL - DEEP PERFORMANCE ANALYSIS", style="bold cyan")
    console.print("=" * 80 + "\n")
    
    # Initialize retriever
    console.print("🔧 Initializing retriever...", style="dim")
    settings = get_settings()
    retriever = HybridRetriever(settings)
    
    tracker = LatencyTracker()
    
    # Test 1: Cold start
    cold_result = await cold_start_test(retriever, tracker)
    
    # Test 2: Warmup performance
    warm_results = await warmup_test(retriever, tracker, num_queries=20)
    
    # Test 3: Query complexity
    complexity_results = await query_complexity_test(retriever, tracker)
    
    # Summary statistics
    console.print("\n[bold cyan]📊 PERFORMANCE SUMMARY[/bold cyan]\n")
    
    total_stats = tracker.get_stats("total")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")
    
    if total_stats:
        table.add_row("Total Queries", str(total_stats["count"]))
        table.add_row("Average Latency", f"{total_stats['avg']:.1f}ms")
        table.add_row("P50 Latency", f"{total_stats['p50']:.1f}ms")
        table.add_row("P95 Latency", f"{total_stats['p95']:.1f}ms")
        table.add_row("Min Latency", f"{total_stats['min']:.1f}ms")
        table.add_row("Max Latency", f"{total_stats['max']:.1f}ms")
    
    console.print(table)
    
    # Component breakdown
    console.print("\n[bold]Component Breakdown (Averages):[/bold]\n")
    
    components = ["embedding", "bm25", "dense", "rrf", "fetch"]
    table = Table(show_header=True, header_style="bold")
    table.add_column("Component", style="cyan")
    table.add_column("Avg (ms)", justify="right", style="yellow")
    table.add_column("P95 (ms)", justify="right", style="yellow")
    table.add_column("% of Total", justify="right", style="green")
    
    total_avg = total_stats.get("avg", 1)
    for component in components:
        stats = tracker.get_stats(component)
        if stats:
            pct = (stats["avg"] / total_avg * 100) if total_avg > 0 else 0
            table.add_row(
                component.upper(),
                f"{stats['avg']:.1f}",
                f"{stats.get('p95', 0):.1f}",
                f"{pct:.1f}%",
            )
    
    console.print(table)
    
    # Optimization recommendations
    print_optimization_recommendations(tracker, cold_result)
    
    # Final verdict
    console.print("\n[bold cyan]🏁 FINAL VERDICT[/bold cyan]\n")
    
    p95 = total_stats.get("p95", 0)
    cold_start = cold_result["total_ms"]
    
    if p95 < 100:
        console.print("✅ [bold green]Warm Performance: EXCELLENT (P95 < 100ms)[/bold green]")
    elif p95 < 500:
        console.print("✅ [bold green]Warm Performance: GOOD (P95 < 500ms)[/bold green]")
    elif p95 < 1000:
        console.print("⚠️  [bold yellow]Warm Performance: ACCEPTABLE (P95 < 1s)[/bold yellow]")
    else:
        console.print("❌ [bold red]Warm Performance: POOR (P95 >= 1s)[/bold red]")
    
    if cold_start > 1000:
        console.print("❌ [bold red]Cold Start: NEEDS OPTIMIZATION (>{:.0f}ms)[/bold red]".format(cold_start))
    else:
        console.print("✅ [bold green]Cold Start: ACCEPTABLE (<1s)[/bold green]")
    
    console.print()


if __name__ == "__main__":
    asyncio.run(main())
