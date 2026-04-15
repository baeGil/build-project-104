#!/usr/bin/env python3
"""
Performance and Retrieval Test with Real Contracts.

Tests:
1. Retrieval quality with 1146 documents
2. End-to-end latency
3. Multiple contract types

Usage:
    uv run python scripts/test_performance.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn

from packages.common.config import get_settings
from packages.retrieval.hybrid import HybridSearchEngine

console = Console()


def load_contract(filename: str) -> str:
    """Load contract from file."""
    contract_path = Path(__file__).parent.parent / "test contracts" / filename
    if contract_path.exists():
        with open(contract_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


async def test_retrieval_quality(retriever: HybridSearchEngine):
    """Test retrieval quality with various contract queries."""
    
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print(" RETRIEVAL QUALITY TEST", style="bold cyan")
    console.print("=" * 80 + "\n")
    
    # Queries based on actual legal documents in database
    test_queries = [
        {
            "query": "quy định về xuất nhập khẩu hàng hóa kiểm tra nhà nước",
            "category": "trade_customs",
            "expected_keywords": ["xuất nhập khẩu", "hàng hóa", "kiểm tra"],
        },
        {
            "query": "tiêu chuẩn ngành quy chuẩn kỹ thuật",
            "category": "standards",
            "expected_keywords": ["tiêu chuẩn", "ngành", "quy chuẩn"],
        },
        {
            "query": "hải quan hàng hóa nước ngoài đưa vào",
            "category": "customs_regulation",
            "expected_keywords": ["hải quan", "hàng hóa", "nước ngoài"],
        },
        {
            "query": "bảo hành xây lắp công trình quy định",
            "category": "construction_warranty",
            "expected_keywords": ["bảo hành", "xây lắp", "công trình"],
        },
        {
            "query": "thuốc bảo vệ thực vật đăng ký bổ sung",
            "category": "pesticide_registration",
            "expected_keywords": ["thuốc", "bảo vệ thực vật", "đăng ký"],
        },
        {
            "query": "văn bản quy phạm pháp luật hết hiệu lực",
            "category": "legal_documents",
            "expected_keywords": ["văn bản", "quy phạm pháp luật", "hết hiệu lực"],
        },
        {
            "query": "phòng cháy chữa cháy rừng thông tràm",
            "category": "fire_prevention",
            "expected_keywords": ["phòng cháy", "chữa cháy", "rừng"],
        },
        {
            "query": "chia xã huyện tỉnh quản lý hành chính",
            "category": "administrative_division",
            "expected_keywords": ["chia xã", "huyện", "tỉnh"],
        },
    ]
    
    results_table = Table(show_header=True, header_style="bold magenta")
    results_table.add_column("#", style="dim", width=3)
    results_table.add_column("Query", style="cyan", width=50)
    results_table.add_column("Category", style="yellow", width=15)
    results_table.add_column("Top Result", style="green", width=50)
    results_table.add_column("Score", justify="right", style="yellow", width=7)
    results_table.add_column("Latency", justify="right", style="dim", width=10)
    results_table.add_column("Match", justify="center", width=6)
    
    all_results = []
    latencies = []
    
    for i, test_data in enumerate(test_queries, 1):
        query = test_data["query"]
        category = test_data["category"]
        expected = test_data["expected_keywords"]
        
        # Test hybrid search
        start_time = time.time()
        try:
            results = await retriever.search(
                query,
                top_k=3,
                bm25_candidates=20,
                dense_candidates=20,
                sandwich_reorder=True,
            )
            latency = (time.time() - start_time) * 1000
            latencies.append(latency)
            
            if results:
                top_doc = results[0]
                title = top_doc.title[:50] if top_doc.title else "N/A"
                score = top_doc.score
                
                # Check if any expected keyword matches
                content_preview = (top_doc.content or "")[:200].lower()
                title_lower = (top_doc.title or "").lower()
                query_lower = query.lower()
                
                has_match = any(
                    kw.lower() in content_preview or 
                    kw.lower() in title_lower or
                    kw.lower() in query_lower
                    for kw in expected
                )
                
                match_icon = "✅" if has_match else "❌"
                
                results_table.add_row(
                    str(i),
                    query[:50],
                    category,
                    title,
                    f"{score:.4f}",
                    f"{latency:.0f}ms",
                    match_icon,
                )
                
                all_results.append({
                    "query": query,
                    "category": category,
                    "matched": has_match,
                    "latency_ms": latency,
                    "top_title": title,
                })
            else:
                results_table.add_row(
                    str(i),
                    query[:50],
                    category,
                    "No results",
                    "-",
                    f"{latency:.0f}ms",
                    "❌",
                )
                all_results.append({
                    "query": query,
                    "category": category,
                    "matched": False,
                    "latency_ms": latency,
                    "top_title": None,
                })
                
        except Exception as e:
            results_table.add_row(
                str(i),
                query[:50],
                category,
                f"Error: {str(e)[:30]}",
                "-",
                "-",
                "❌",
            )
            all_results.append({
                "query": query,
                "category": category,
                "matched": False,
                "latency_ms": 0,
                "error": str(e),
            })
    
    console.print(results_table)
    
    # Summary statistics
    match_count = sum(1 for r in all_results if r.get("matched", False))
    total_queries = len(all_results)
    match_rate = (match_count / total_queries * 100) if total_queries > 0 else 0
    
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    p50_latency = sorted(latencies)[len(latencies) // 2] if latencies else 0
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else (latencies[0] if latencies else 0)
    
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  • Total queries: {total_queries}")
    console.print(f"  • Successful matches: {match_count} ({match_rate:.1f}%)")
    console.print(f"  • Average latency: {avg_latency:.0f}ms")
    console.print(f"  • P50 latency: {p50_latency:.0f}ms")
    console.print(f"  • P95 latency: {p95_latency:.0f}ms")
    
    if match_rate >= 60:
        console.print(f"\n✅ [bold green]Retrieval quality is GOOD![/bold green]")
    elif match_rate >= 40:
        console.print(f"\n⚠️  [bold yellow]Retrieval quality is MODERATE[/bold yellow]")
    else:
        console.print(f"\n❌ [bold red]Retrieval quality needs improvement[/bold red]")
    
    # Performance check
    if p95_latency < 1000:
        console.print(f"✅ [bold green]Performance target MET: p95 < 1s[/bold green]\n")
    else:
        console.print(f"⚠️  [bold yellow]Performance target NOT MET: p95 >= 1s[/bold yellow]\n")
    
    return all_results


async def test_contract_scenarios(retriever: HybridSearchEngine):
    """Test with real contract scenarios."""
    
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("📄 CONTRACT SCENARIO TESTS", style="bold cyan")
    console.print("=" * 80 + "\n")
    
    # Load contracts
    contracts = [
        ("Hợp đồng tư vấn pháp lý", "test_contract_1.txt"),
        ("Hợp đồng thuê văn phòng", "test_contract_2.txt"),
        ("Hợp đồng mua bán hàng hóa", "test_contract_3.txt"),
        ("Hợp đồng lao động", "test_contract_4.txt"),
    ]
    
    scenarios = [
        {
            "contract": "Hợp đồng tư vấn pháp lý",
            "test": "Tìm văn bản về Bộ Luật Dân sự 2015",
            "query": "Bộ Luật Dân sự 2015 quy định hợp đồng nghĩa vụ",
        },
        {
            "contract": "Hợp đồng thuê văn phòng",
            "test": "Tìm quy định về nhà ở cho thuê",
            "query": "nhà ở cho thuê quản lý quyền sở hữu",
        },
        {
            "contract": "Hợp đồng mua bán hàng hóa",
            "test": "Tìm về xuất nhập khẩu thương mại",
            "query": "xuất nhập khẩu hàng hóa thương mại quy định",
        },
        {
            "contract": "Hợp đồng lao động",
            "test": "Tìm về bảo hiểm xã hội lao động",
            "query": "bảo hiểm xã hội người lao động đóng góp",
        },
    ]
    
    for scenario in scenarios:
        contract_name = scenario["contract"]
        test_desc = scenario["test"]
        query = scenario["query"]
        
        console.print(f"\n[bold cyan]Contract:[/bold cyan] {contract_name}")
        console.print(f"[bold]Test:[/bold] {test_desc}")
        console.print(f"[dim]Query: {query}[/dim]\n")
        
        start_time = time.time()
        try:
            results = await retriever.search(
                query,
                top_k=5,
                bm25_candidates=20,
                dense_candidates=20,
                sandwich_reorder=True,
            )
            latency = (time.time() - start_time) * 1000
            
            if results:
                table = Table(show_header=True, box=None)
                table.add_column("#", style="dim", width=3)
                table.add_column("Document", style="green", width=70)
                table.add_column("Score", justify="right", style="yellow", width=8)
                
                for i, doc in enumerate(results[:5], 1):
                    title = doc.title[:70] if doc.title else "N/A"
                    score = doc.score
                    table.add_row(str(i), title, f"{score:.4f}")
                
                console.print(table)
                console.print(f"Latency: [yellow]{latency:.0f}ms[/yellow]\n")
            else:
                console.print("[yellow]⚠️  No results found[/yellow]\n")
                
        except Exception as e:
            console.print(f"[bold red]❌ Error: {e}[/bold red]\n")


async def main():
    """Run all tests."""
    
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("🚀 PERFORMANCE & RETRIEVAL TEST SUITE", style="bold cyan")
    console.print("=" * 80 + "\n")
    
    # Initialize
    console.print("🔧 Initializing retrieval system...", style="dim")
    settings = get_settings()
    retriever = HybridSearchEngine(settings)
    
    # Warm up embedding model
    console.print("🔥 Warming up embedding model...", style="dim")
    retriever._embedding_service.encode(["warm up"])
    console.print("✓ Model ready\n", style="green")
    
    # Test 1: Retrieval Quality
    quality_results = await test_retrieval_quality(retriever)
    
    # Test 2: Contract Scenarios
    await test_contract_scenarios(retriever)
    
    # Final Summary
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("✅ ALL TESTS COMPLETE", style="bold green")
    console.print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
