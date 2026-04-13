"""Benchmark suite for retrieval pipeline latency and accuracy."""

from __future__ import annotations

import asyncio
import statistics
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

# Test queries covering different types:
BENCHMARK_QUERIES = [
    # Citation queries (should route to CITATION strategy)
    {"query": "Điều 15 Luật Doanh Nghiệp năm 2020", "type": "citation"},
    {"query": "Nghị định 01/2021/NĐ-CP", "type": "citation"},
    
    # Negation queries (should route to NEGATION strategy)
    {"query": "Công ty không được phép sử dụng lao động trẻ em", "type": "negation"},
    {"query": "Cấm các hành vi gian lận thương mại", "type": "negation"},
    
    # Semantic queries (standard hybrid)
    {"query": "Điều kiện thành lập doanh nghiệp tại Việt Nam", "type": "semantic"},
    {"query": "Quy định về bảo hiểm xã hội cho ngườI lao động", "type": "semantic"},
    {"query": "Trách nhiệm bồi thường thiệt hại trong hợp đồng thương mại", "type": "semantic"},
    
    # Complex mixed queries (hard - half affirmation half negation)
    {"query": "Công ty phải đóng bảo hiểm nhưng không bắt buộc đóng quỹ hưu trí bổ sung", "type": "mixed"},
    {"query": "Được phép kinh doanh online nhưng không được bán hàng giả", "type": "mixed"},
]


class MockHybridSearchEngine:
    """Mock hybrid search engine for benchmarking without DB connections."""
    
    def __init__(self, latency_ms: float = 50.0):
        self.latency_ms = latency_ms
        self.call_count = 0
    
    async def search(
        self,
        query: str,
        query_plan: Any | None = None,
        top_k: int = 5,
        **kwargs
    ) -> list[Any]:
        """Simulate search with configurable latency."""
        self.call_count += 1
        # Simulate variable latency based on query complexity
        base_latency = self.latency_ms / 1000
        variable = (hash(query) % 20) / 1000  # 0-20ms variation
        await asyncio.sleep(base_latency + variable)
        
        # Return mock results
        from packages.common.types import RetrievedDocument
        return [
            RetrievedDocument(
                doc_id=f"doc_{i}_{self.call_count}",
                content=f"Mock content for query: {query[:50]}...",
                title=f"Document {i}",
                score=0.9 - (i * 0.1),
                bm25_score=0.85 - (i * 0.05),
                dense_score=0.88 - (i * 0.08),
            )
            for i in range(top_k)
        ]


class MockReranker:
    """Mock reranker for benchmarking without model loading."""
    
    def __init__(self, latency_ms: float = 30.0):
        self.latency_ms = latency_ms
        self.call_count = 0
    
    async def rerank(
        self,
        query: str,
        candidates: list[Any],
        top_k: int = 5,
    ) -> list[Any]:
        """Simulate reranking with configurable latency."""
        self.call_count += 1
        base_latency = self.latency_ms / 1000
        variable = (hash(query) % 10) / 1000  # 0-10ms variation
        await asyncio.sleep(base_latency + variable)
        
        # Update rerank scores
        for i, doc in enumerate(candidates):
            doc.rerank_score = doc.score * (1.0 - i * 0.05)
        
        return candidates[:top_k]


class RetrievalBenchmark:
    """Run retrieval benchmarks and report latency percentiles."""
    
    def __init__(self):
        self.planner = None
        self.search_engine = None
        self.reranker = None
        self.results: dict[str, Any] = {}
    
    async def _init_components(self):
        """Initialize benchmark components with mocks."""
        from packages.reasoning.planner import LegalQueryPlanner
        
        self.planner = LegalQueryPlanner()
        self.search_engine = MockHybridSearchEngine(latency_ms=50.0)
        self.reranker = MockReranker(latency_ms=30.0)
    
    async def run(self, iterations: int = 10) -> dict:
        """Run full benchmark suite. Returns stats dict."""
        await self._init_components()
        
        print(f"\n{'='*80}")
        print("RETRIEVAL PIPELINE BENCHMARK")
        print(f"{'='*80}")
        print(f"Iterations per query: {iterations}")
        print(f"Total queries: {len(BENCHMARK_QUERIES)}")
        print(f"{'='*80}\n")
        
        queries = [q["query"] for q in BENCHMARK_QUERIES]
        
        # Run individual component benchmarks
        planning_results = await self.bench_query_planning(queries, iterations)
        hybrid_results = await self.bench_hybrid_search(queries, iterations)
        reranking_results = await self.bench_reranking(queries, iterations)
        end_to_end_results = await self.bench_end_to_end(queries, iterations)
        
        self.results = {
            "query_planning": planning_results,
            "hybrid_search": hybrid_results,
            "reranking": reranking_results,
            "end_to_end": end_to_end_results,
            "metadata": {
                "iterations": iterations,
                "num_queries": len(queries),
            }
        }
        
        return self.results
    
    async def bench_query_planning(self, queries: list[str], iterations: int) -> dict:
        """Benchmark query planner latency."""
        latencies: list[float] = []
        
        print("Benchmarking Query Planning...")
        
        for query in queries:
            for _ in range(iterations):
                start = time.perf_counter()
                self.planner.plan(query)
                elapsed = (time.perf_counter() - start) * 1000
                latencies.append(elapsed)
        
        stats = self._calculate_percentiles(latencies)
        stats["component"] = "Query Planning"
        stats["unit"] = "ms"
        return stats
    
    async def bench_hybrid_search(self, queries: list[str], iterations: int) -> dict:
        """Benchmark hybrid search latency."""
        latencies: list[float] = []
        
        print("Benchmarking Hybrid Search...")
        
        for query in queries:
            for _ in range(iterations):
                start = time.perf_counter()
                await self.search_engine.search(query, top_k=5)
                elapsed = (time.perf_counter() - start) * 1000
                latencies.append(elapsed)
        
        stats = self._calculate_percentiles(latencies)
        stats["component"] = "Hybrid Search"
        stats["unit"] = "ms"
        return stats
    
    async def bench_reranking(self, queries: list[str], iterations: int) -> dict:
        """Benchmark reranker latency."""
        latencies: list[float] = []
        
        print("Benchmarking Reranking...")
        
        # Pre-generate mock candidates
        from packages.common.types import RetrievedDocument
        mock_candidates = [
            RetrievedDocument(
                doc_id=f"doc_{i}",
                content=f"Mock document content {i}",
                title=f"Doc {i}",
                score=0.9 - (i * 0.05),
            )
            for i in range(10)
        ]
        
        for query in queries:
            for _ in range(iterations):
                # Copy candidates for each iteration
                candidates = [
                    RetrievedDocument(
                        doc_id=doc.doc_id,
                        content=doc.content,
                        title=doc.title,
                        score=doc.score,
                    )
                    for doc in mock_candidates
                ]
                
                start = time.perf_counter()
                await self.reranker.rerank(query, candidates, top_k=5)
                elapsed = (time.perf_counter() - start) * 1000
                latencies.append(elapsed)
        
        stats = self._calculate_percentiles(latencies)
        stats["component"] = "Reranking"
        stats["unit"] = "ms"
        return stats
    
    async def bench_end_to_end(self, queries: list[str], iterations: int) -> dict:
        """Benchmark full pipeline latency."""
        latencies: list[float] = []
        
        print("Benchmarking End-to-End Pipeline...")
        
        for query in queries:
            for _ in range(iterations):
                start = time.perf_counter()
                
                # Full pipeline: plan -> search -> rerank
                query_plan = self.planner.plan(query)
                candidates = await self.search_engine.search(
                    query_plan.normalized_query, 
                    query_plan=query_plan, 
                    top_k=10
                )
                await self.reranker.rerank(query, candidates, top_k=5)
                
                elapsed = (time.perf_counter() - start) * 1000
                latencies.append(elapsed)
        
        stats = self._calculate_percentiles(latencies)
        stats["component"] = "End-to-End"
        stats["unit"] = "ms"
        return stats
    
    def _calculate_percentiles(self, latencies: list[float]) -> dict:
        """Calculate p50, p95, p99, mean, min, max."""
        if not latencies:
            return {
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "mean": 0.0,
                "min": 0.0,
                "max": 0.0,
                "count": 0,
            }
        
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        
        def percentile(p: float) -> float:
            idx = int(n * p / 100)
            return sorted_latencies[min(idx, n - 1)]
        
        return {
            "p50": percentile(50),
            "p95": percentile(95),
            "p99": percentile(99),
            "mean": statistics.mean(latencies),
            "min": min(latencies),
            "max": max(latencies),
            "count": n,
        }
    
    def print_report(self, results: dict | None = None):
        """Pretty-print benchmark results table."""
        if results is None:
            results = self.results
        
        if not results:
            print("No results to display.")
            return
        
        print(f"\n{'='*100}")
        print("BENCHMARK RESULTS SUMMARY")
        print(f"{'='*100}")
        
        # Header
        header = f"{'Component':<20} {'P50':>10} {'P95':>10} {'P99':>10} {'Mean':>10} {'Min':>10} {'Max':>10} {'Count':>8}"
        print(header)
        print("-" * 100)
        
        # Results rows
        components = ["query_planning", "hybrid_search", "reranking", "end_to_end"]
        for comp_key in components:
            if comp_key in results:
                stats = results[comp_key]
                unit = stats.get("unit", "ms")
                row = (
                    f"{stats.get('component', comp_key):<20} "
                    f"{stats['p50']:>9.2f}{unit} "
                    f"{stats['p95']:>9.2f}{unit} "
                    f"{stats['p99']:>9.2f}{unit} "
                    f"{stats['mean']:>9.2f}{unit} "
                    f"{stats['min']:>9.2f}{unit} "
                    f"{stats['max']:>9.2f}{unit} "
                    f"{stats['count']:>8}"
                )
                print(row)
        
        print(f"{'='*100}\n")
        
        # SLO Compliance Check
        print("SLO COMPLIANCE CHECK")
        print("-" * 50)
        
        slos = {
            "query_planning": (50, "Query Planning"),
            "hybrid_search": (1000, "Hybrid Search"),
            "reranking": (300, "Reranking"),
            "end_to_end": (2000, "End-to-End"),
        }
        
        for comp_key, (slo_ms, name) in slos.items():
            if comp_key in results:
                p95 = results[comp_key]["p95"]
                status = "✅ PASS" if p95 <= slo_ms else "❌ FAIL"
                print(f"{name}: P95={p95:.2f}ms (SLO: {slo_ms}ms) {status}")
        
        print()


# CLI entry point
if __name__ == "__main__":
    import sys
    
    iterations = 10
    if len(sys.argv) > 1:
        try:
            iterations = int(sys.argv[1])
        except ValueError:
            print(f"Usage: python bench_retrieval.py [iterations]")
            sys.exit(1)
    
    bench = RetrievalBenchmark()
    results = asyncio.run(bench.run(iterations=iterations))
    bench.print_report(results)
