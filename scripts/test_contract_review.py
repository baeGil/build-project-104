#!/usr/bin/env python3
"""
Test contract review with sample contracts.

Tests the system with the 2 contracts you created:
1. Hợp đồng dịch vụ tư vấn pháp lý
2. Hợp đồng thuê văn phòng

Usage:
    uv run python scripts/test_contract_review.py
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from packages.common.config import get_settings
from packages.retrieval.hybrid import HybridSearchEngine

console = Console()


# Read test contracts
def load_test_contract(filename: str) -> str:
    """Load contract from file."""
    contract_path = Path(__file__).parent.parent / "test contracts" / filename
    if contract_path.exists():
        with open(contract_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


async def test_contract_review():
    """Test contract review with sample contracts."""
    
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("📄 CONTRACT REVIEW TEST", style="bold cyan")
    console.print("=" * 80 + "\n")
    
    # Load contracts
    contract1 = load_test_contract("test_contract_1.txt")
    contract2 = load_test_contract("test_contract_2.txt")
    
    if not contract1 or not contract2:
        console.print("[bold red]❌ Could not load test contracts[/bold red]")
        return
    
    console.print("[bold green]✓[/bold green] Loaded 2 test contracts")
    console.print(f"  • Contract 1: {len(contract1)} characters")
    console.print(f"  • Contract 2: {len(contract2)} characters\n")
    
    # Initialize retriever
    console.print("🔧 Initializing retrieval system...", style="dim")
    settings = get_settings()
    retriever = HybridSearchEngine(settings)
    
    # Extract clauses from contracts
    console.print("\n" + "=" * 80, style="bold yellow")
    console.print("STEP 1: Extract key clauses from contracts", style="bold yellow")
    console.print("=" * 80 + "\n")
    
    # Test queries based on contract content
    contract_queries = [
        {
            "contract": "Hợp đồng tư vấn pháp lý",
            "query": "phí dịch vụ tư vấn pháp lý 25 triệu đồng",
            "expected": "Điều 3 - Phí dịch vụ",
        },
        {
            "contract": "Hợp đồng tư vấn pháp lý",
            "query": "bảo mật thông tin 5 năm",
            "expected": "Điều 5 - Bảo mật thông tin",
        },
        {
            "contract": "Hợp đồng tư vấn pháp lý",
            "query": "bất khả kháng thiên tai dịch bệnh",
            "expected": "Điều 7 - Bất khả kháng",
        },
        {
            "contract": "Hợp đồng thuê văn phòng",
            "query": "giá thuê văn phòng 350000 đồng m2",
            "expected": "Điều 3 - Giá thuê",
        },
        {
            "contract": "Hợp đồng thuê văn phòng",
            "query": "phòng cháy chữa cháy PCCC",
            "expected": "Điều 7 - Bảo hiểm và PCCC",
        },
        {
            "contract": "Hợp đồng thuê văn phòng",
            "query": "đơn phương chấm dứt hợp đồng chậm thanh toán",
            "expected": "Điều 12 - Đơn phương chấm dứt",
        },
    ]
    
    # Test each query
    all_results = []
    
    for i, query_data in enumerate(contract_queries, 1):
        contract = query_data["contract"]
        query = query_data["query"]
        expected = query_data["expected"]
        
        console.print(f"\n[bold cyan]Query {i}/6: {query}[/bold cyan]")
        console.print(f"Contract: [dim]{contract}[/dim]")
        console.print(f"Expected: [yellow]{expected}[/yellow]\n")
        
        # Perform hybrid search
        try:
            results = await retriever.search(
                query,
                top_k=3,
                bm25_candidates=20,
                dense_candidates=20,
                sandwich_reorder=True,
            )
            
            # Display results
            if results:
                table = Table(show_header=True, header_style="bold magenta", box=None)
                table.add_column("#", style="dim", width=3)
                table.add_column("Document", style="green", width=60)
                table.add_column("Score", justify="right", style="yellow", width=8)
                table.add_column("Type", style="cyan", width=12)
                
                for j, doc in enumerate(results[:3], 1):
                    title = doc.title[:60] if doc.title else "N/A"
                    score = doc.score
                    doc_type = getattr(doc, 'doc_type', 'unknown')
                    
                    # Check if this is a match
                    is_match = expected.lower() in title.lower() or expected.lower() in doc.content[:100].lower() if doc.content else False
                    match_icon = "✓" if is_match else "✗"
                    match_style = "green" if is_match else "red"
                    
                    table.add_row(
                        f"[{match_style}]{match_icon}[/{match_style}]",
                        title,
                        f"{score:.4f}",
                        doc_type,
                    )
                
                console.print(table)
                
                # Check quality
                has_good_match = any(
                    expected.lower() in (doc.title or "").lower() or
                    expected.lower() in (doc.content or "")[:200].lower()
                    for doc in results[:3]
                )
                
                if has_good_match:
                    console.print("[bold green]✅ Good match found![/bold green]")
                else:
                    console.print("[bold yellow]⚠️  No exact match - may need more data[/bold yellow]")
                
                all_results.append({
                    "query": query,
                    "expected": expected,
                    "found": has_good_match,
                    "top_result": results[0].title if results else None,
                })
            else:
                console.print("[bold red]❌ No results found[/bold red]")
                all_results.append({
                    "query": query,
                    "expected": expected,
                    "found": False,
                    "top_result": None,
                })
                
        except Exception as e:
            console.print(f"[bold red]❌ Error: {e}[/bold red]")
            all_results.append({
                "query": query,
                "expected": expected,
                "found": False,
                "error": str(e),
            })
    
    # Summary
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("📊 TEST SUMMARY", style="bold cyan")
    console.print("=" * 80 + "\n")
    
    success_count = sum(1 for r in all_results if r.get("found", False))
    total_count = len(all_results)
    success_rate = (success_count / total_count * 100) if total_count > 0 else 0
    
    console.print(f"Total queries: [bold]{total_count}[/bold]")
    console.print(f"Successful matches: [bold green]{success_count}[/bold green]")
    console.print(f"Failed matches: [bold red]{total_count - success_count}[/bold red]")
    console.print(f"Success rate: [bold yellow]{success_rate:.1f}%[/bold yellow]\n")
    
    if success_rate >= 70:
        console.print("[bold green]✅ Retrieval quality is GOOD - System is ready![/bold green]\n")
    elif success_rate >= 50:
        console.print("[bold yellow]⚠️  Retrieval quality is MODERATE - Consider ingesting more data[/bold yellow]\n")
    else:
        console.print("[bold red]❌ Retrieval quality is LOW - Need more relevant documents[/bold red]\n")
    
    # Detailed results
    console.print("[bold]Detailed Results:[/bold]\n")
    for i, result in enumerate(all_results, 1):
        status = "✅" if result.get("found") else "❌"
        console.print(f"{i}. {status} Query: [dim]{result['query'][:50]}[/dim]")
        console.print(f"   Expected: {result['expected']}")
        if result.get('top_result'):
            console.print(f"   Found: [green]{result['top_result'][:60]}[/green]")
        console.print()


async def main():
    """Run contract review test."""
    await test_contract_review()


if __name__ == "__main__":
    asyncio.run(main())
