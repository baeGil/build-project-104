"""Benchmark suite for contract review pipeline."""

from __future__ import annotations

import asyncio
import statistics
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

from packages.common.types import (
    Citation,
    ContractReviewResult,
    EvidencePack,
    RetrievedDocument,
    ReviewFinding,
    RiskLevel,
    VerificationLevel,
)


# Sample contract clauses for benchmarking
SAMPLE_CLAUSES = [
    "Điều 1. Đối tượng hợp đồng: Bên B cung cấp dịch vụ thiết kế, phát triển và bàn giao phần mềm quản lý bán hàng cho Bên A.",
    "Điều 2. Tiến độ và nghiệm thu: Bên B bàn giao bản thử nghiệm trong vòng 20 ngày kể từ ngày hợp đồng có hiệu lực.",
    "Điều 3. Thanh toán: Bên A thanh toán 40% giá trị hợp đồng trong vòng 05 ngày kể từ ngày ký.",
    "Điều 4. Phạt vi phạm: Nếu Bên B chậm bàn giao quá 10 ngày, Bên B phải chịu phạt vi phạm bằng 12% giá trị phần nghĩa vụ bị vi phạm.",
    "Điều 5. Bảo mật: Hai bên có nghĩa vụ bảo mật toàn bộ tài liệu, dữ liệu khách hàng trong quá trình thực hiện hợp đồng.",
    "Điều 6. Quyền sở hữu: Sau khi Bên A hoàn tất thanh toán đầy đủ, toàn bộ sản phẩm thuộc quyền sở hữu của Bên A.",
    "Điều 7. Chấm dứt hợp đồng: Một bên có quyền chấm dứt hợp đồng nếu bên kia vi phạm nghiêm trọng nghĩa vụ.",
    "Điều 8. Giải quyết tranh chấp: Mọi tranh chấp phát sinh từ hợp đồng này trước hết được giải quyết bằng thương lượng.",
]


class MockReviewPipeline:
    """Mock review pipeline for benchmarking without external dependencies."""
    
    def __init__(
        self,
        planning_latency_ms: float = 5.0,
        retrieval_latency_ms: float = 50.0,
        reranking_latency_ms: float = 30.0,
        verification_latency_ms: float = 100.0,
        generation_latency_ms: float = 200.0,
    ):
        self.planning_latency_ms = planning_latency_ms
        self.retrieval_latency_ms = retrieval_latency_ms
        self.reranking_latency_ms = reranking_latency_ms
        self.verification_latency_ms = verification_latency_ms
        self.generation_latency_ms = generation_latency_ms
        
        self.call_stats = {
            "planning": 0,
            "retrieval": 0,
            "reranking": 0,
            "verification": 0,
            "generation": 0,
        }
    
    async def review_clause(self, clause_text: str, clause_index: int) -> ReviewFinding:
        """Simulate reviewing a single clause."""
        # Planning
        self.call_stats["planning"] += 1
        await asyncio.sleep(self.planning_latency_ms / 1000)
        
        # Retrieval
        self.call_stats["retrieval"] += 1
        await asyncio.sleep(self.retrieval_latency_ms / 1000)
        
        # Reranking
        self.call_stats["reranking"] += 1
        await asyncio.sleep(self.reranking_latency_ms / 1000)
        
        # Verification
        self.call_stats["verification"] += 1
        await asyncio.sleep(self.verification_latency_ms / 1000)
        
        # Generation
        self.call_stats["generation"] += 1
        await asyncio.sleep(self.generation_latency_ms / 1000)
        
        # Return mock finding
        return ReviewFinding(
            clause_text=clause_text,
            clause_index=clause_index,
            verification=VerificationLevel.ENTAILED,
            confidence=0.85,
            risk_level=RiskLevel.LOW,
            rationale="Mock rationale for clause review",
            citations=[
                Citation(
                    article_id=f"article_{clause_index}",
                    law_id="LDN2020",
                    quote="Mock legal quote",
                )
            ],
            latency_ms=(
                self.planning_latency_ms
                + self.retrieval_latency_ms
                + self.reranking_latency_ms
                + self.verification_latency_ms
                + self.generation_latency_ms
            ),
        )
    
    async def review_contract(self, contract_text: str) -> ContractReviewResult:
        """Simulate reviewing a full contract."""
        # Parse clauses (sync, minimal latency)
        clauses = self._parse_clauses(contract_text)
        
        # Review each clause
        findings: list[ReviewFinding] = []
        for idx, clause in enumerate(clauses):
            finding = await self.review_clause(clause, idx)
            findings.append(finding)
        
        total_latency = sum(f.latency_ms for f in findings)
        
        return ContractReviewResult(
            contract_id=f"bench_contract_{int(time.time())}",
            findings=findings,
            summary=f"Reviewed {len(clauses)} clauses with mock pipeline",
            total_clauses=len(clauses),
            risk_summary={
                RiskLevel.HIGH: 0,
                RiskLevel.MEDIUM: 0,
                RiskLevel.LOW: len(clauses),
                RiskLevel.NONE: 0,
            },
            total_latency_ms=total_latency,
        )
    
    def _parse_clauses(self, contract_text: str) -> list[str]:
        """Parse contract into clauses."""
        import re
        
        # Split by article markers
        pattern = r'(?:^|\n)\s*(Điều\s+\d+)'
        parts = re.split(f'(?={pattern})', contract_text, flags=re.IGNORECASE)
        
        clauses = []
        for part in parts:
            part = part.strip()
            if len(part) > 20:  # Skip headers
                clauses.append(part)
        
        return clauses if clauses else [contract_text]


class ReviewPipelineBenchmark:
    """Benchmark suite for contract review pipeline."""
    
    def __init__(self):
        self.pipeline = None
        self.results: dict[str, Any] = {}
        
        # Load sample contract
        self.sample_contract = self._load_sample_contract()
    
    def _load_sample_contract(self) -> str:
        """Load sample contract from test contracts directory."""
        contract_path = Path(__file__).parent.parent.parent / "test contracts" / "1.txt"
        
        if contract_path.exists():
            return contract_path.read_text(encoding="utf-8")
        
        # Fallback to embedded sample
        return "\n\n".join(SAMPLE_CLAUSES)
    
    async def _init_pipeline(self):
        """Initialize mock pipeline."""
        self.pipeline = MockReviewPipeline(
            planning_latency_ms=5.0,
            retrieval_latency_ms=50.0,
            reranking_latency_ms=30.0,
            verification_latency_ms=100.0,
            generation_latency_ms=200.0,
        )
    
    async def run(self, iterations: int = 5) -> dict:
        """Run full benchmark suite. Returns stats dict."""
        await self._init_pipeline()
        
        print(f"\n{'='*80}")
        print("CONTRACT REVIEW PIPELINE BENCHMARK")
        print(f"{'='*80}")
        print(f"Iterations: {iterations}")
        print(f"Sample contract length: {len(self.sample_contract)} chars")
        print(f"{'='*80}\n")
        
        # Run benchmarks
        full_contract_results = await self.bench_full_contract(iterations)
        single_clause_results = await self.bench_single_clause(iterations)
        batch_results = await self.bench_batch_processing(iterations)
        
        self.results = {
            "full_contract": full_contract_results,
            "single_clause": single_clause_results,
            "batch_processing": batch_results,
            "metadata": {
                "iterations": iterations,
                "sample_contract_chars": len(self.sample_contract),
            }
        }
        
        return self.results
    
    async def bench_full_contract(self, iterations: int) -> dict:
        """Benchmark full contract review."""
        latencies: list[float] = []
        clause_counts: list[int] = []
        
        print("Benchmarking Full Contract Review...")
        
        for i in range(iterations):
            start = time.perf_counter()
            result = await self.pipeline.review_contract(self.sample_contract)
            elapsed = (time.perf_counter() - start) * 1000
            
            latencies.append(elapsed)
            clause_counts.append(result.total_clauses)
            
            print(f"  Iteration {i+1}/{iterations}: {elapsed:.2f}ms ({result.total_clauses} clauses)")
        
        stats = self._calculate_percentiles(latencies)
        stats["component"] = "Full Contract Review"
        stats["unit"] = "ms"
        stats["avg_clauses"] = statistics.mean(clause_counts) if clause_counts else 0
        return stats
    
    async def bench_single_clause(self, iterations: int) -> dict:
        """Benchmark single clause review."""
        latencies: list[float] = []
        
        print("Benchmarking Single Clause Review...")
        
        test_clause = SAMPLE_CLAUSES[0]
        
        for i in range(iterations):
            start = time.perf_counter()
            await self.pipeline.review_clause(test_clause, 0)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
        
        stats = self._calculate_percentiles(latencies)
        stats["component"] = "Single Clause Review"
        stats["unit"] = "ms"
        return stats
    
    async def bench_batch_processing(self, iterations: int) -> dict:
        """Benchmark batch clause processing (parallel)."""
        latencies: list[float] = []
        
        print("Benchmarking Batch Processing (parallel clauses)...")
        
        # Use first 4 clauses for batch testing
        batch_clauses = SAMPLE_CLAUSES[:4]
        
        for i in range(iterations):
            start = time.perf_counter()
            
            # Process all clauses in parallel
            await asyncio.gather(*[
                self.pipeline.review_clause(clause, idx)
                for idx, clause in enumerate(batch_clauses)
            ])
            
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
        
        stats = self._calculate_percentiles(latencies)
        stats["component"] = "Batch Processing (4 clauses parallel)"
        stats["unit"] = "ms"
        stats["clauses_per_batch"] = len(batch_clauses)
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
        header = f"{'Component':<35} {'P50':>10} {'P95':>10} {'P99':>10} {'Mean':>10} {'Min':>10} {'Max':>10} {'Count':>8}"
        print(header)
        print("-" * 100)
        
        # Results rows
        components = ["full_contract", "single_clause", "batch_processing"]
        for comp_key in components:
            if comp_key in results:
                stats = results[comp_key]
                unit = stats.get("unit", "ms")
                row = (
                    f"{stats.get('component', comp_key):<35} "
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
            "full_contract": (5000, "Full Contract Review"),
            "single_clause": (500, "Single Clause Review"),
            "batch_processing": (1000, "Batch Processing (4 clauses)"),
        }
        
        for comp_key, (slo_ms, name) in slos.items():
            if comp_key in results:
                p95 = results[comp_key]["p95"]
                status = "✅ PASS" if p95 <= slo_ms else "❌ FAIL"
                print(f"{name}: P95={p95:.2f}ms (SLO: {slo_ms}ms) {status}")
        
        # Additional stats
        if "full_contract" in results:
            avg_clauses = results["full_contract"].get("avg_clauses", 0)
            print(f"\nAverage clauses per contract: {avg_clauses:.1f}")
        
        print()


# CLI entry point
if __name__ == "__main__":
    import sys
    
    iterations = 5
    if len(sys.argv) > 1:
        try:
            iterations = int(sys.argv[1])
        except ValueError:
            print(f"Usage: python bench_review.py [iterations]")
            sys.exit(1)
    
    bench = ReviewPipelineBenchmark()
    results = asyncio.run(bench.run(iterations=iterations))
    bench.print_report(results)
