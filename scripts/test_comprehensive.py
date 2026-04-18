#!/usr/bin/env python3
"""
Comprehensive Multi-Domain Contract Review Test

Tests the contract review pipeline with a complex contract covering 7 different domains:
1. Healthcare services
2. Pricing & public services
3. Water resources & irrigation
4. Environmental protection & mining
5. Organization & personnel management
6. Reporting & inspection
7. Penalties & incentives

Usage:
    uv run python scripts/test_comprehensive.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from packages.common.config import get_settings
from packages.retrieval.hybrid import HybridSearchEngine
from packages.reasoning.review_pipeline import ContractReviewPipeline
from packages.reasoning.planner import QueryPlanner

console = Console()


def load_contract(filepath: str) -> str:
    """Load contract from file."""
    contract_path = Path(__file__).parent.parent / filepath
    with open(contract_path, "r", encoding="utf-8") as f:
        return f.read()


def load_expected_output(filepath: str) -> dict:
    """Load expected output (ground truth)."""
    expected_path = Path(__file__).parent.parent / filepath
    with open(expected_path, "r", encoding="utf-8") as f:
        return json.load(f)


async def run_comprehensive_test():
    """Run comprehensive multi-domain contract test."""
    
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("🎯 COMPREHENSIVE MULTI-DOMAIN CONTRACT REVIEW TEST", style="bold cyan")
    console.print("=" * 80 + "\n")
    
    # Load contract
    console.print("📄 Loading comprehensive contract...", style="dim")
    contract_text = load_contract("test contracts/test_contract_comprehensive.txt")
    console.print(f"✅ Contract loaded: {len(contract_text)} characters\n")
    
    # Load expected output
    console.print("📋 Loading expected output (ground truth)...", style="dim")
    expected = load_expected_output("EXPECTED_COMPREHENSIVE_OUTPUT.json")
    console.print(f"✅ Expected: {expected['expected_summary']['total_findings']} findings across {len(expected['expected_summary']['domains_analysis'])} domains\n")
    
    # Initialize pipeline
    console.print("🔧 Initializing pipeline...", style="dim")
    settings = get_settings()
    retriever = HybridSearchEngine(settings)
    pipeline = ContractReviewPipeline(settings)
    planner = QueryPlanner()
    console.print("✅ Pipeline initialized\n")

    # Warmup - pre-load models and connections to eliminate cold-start latency
    console.print("🔥 Warming up models and connections...", style="dim")
    warmup_start = time.perf_counter()
    await pipeline.warmup()
    warmup_end = time.perf_counter()
    warmup_time = warmup_end - warmup_start
    console.print(f"🔥 Warmup completed in {warmup_time:.2f}s\n", style="bold green")

    # Performance tracking
    perf_metrics = {
        "total_start": time.perf_counter(),
        "warmup_time": warmup_time,
        "parsing_time": 0,
        "retrieval_times": [],
        "total_time": 0
    }
    
    # Parse contract
    console.print("=" * 80, style="bold yellow")
    console.print("STEP 1: Parsing Contract Clauses", style="bold yellow")
    console.print("=" * 80 + "\n")
    
    parse_start = time.perf_counter()
    clauses_with_idx = pipeline._parse_contract_clauses(contract_text)
    parse_end = time.perf_counter()
    perf_metrics["parsing_time"] = parse_end - parse_start
    
    # Convert to dict format
    clauses = [
        {"index": idx, "text": text, "title": text.split('\n')[0][:100]}
        for idx, text in clauses_with_idx
    ]
    
    console.print(f"✅ Parsed {len(clauses)} clauses in {perf_metrics['parsing_time']:.2f}s\n")
    
    for i, clause in enumerate(clauses, 1):
        title = clause.get('title', 'N/A')[:60]
        console.print(f"  Clause {i}: {title}...")
    
    # Review each clause
    console.print("\n" + "=" * 80, style="bold yellow")
    console.print("STEP 2: Reviewing Each Clause", style="bold yellow")
    console.print("=" * 80 + "\n")
    
    findings = []
    
    for i, clause in enumerate(clauses):
        clause_title = clause.get('title', f'Clause {i+1}')
        clause_text = clause.get('text', '')[:100]
        
        console.print(f"\n[bold cyan]Clause {i+1}/{len(clauses)}: {clause_title[:70]}...[/bold cyan]")
        console.print(f"Text: [dim]{clause_text}...[/dim]\n")
        
        # Build query from clause text and plan it for expansion variants
        query_plan = planner.plan(clause.get('text', ''))
        
        # Search for relevant laws, passing query_plan for expansion-variant boosting
        retrieval_start = time.perf_counter()
        
        try:
            # Hybrid retrieve with large candidate pool for better recall
            retrieval_start = time.perf_counter()
            
            search_results = await retriever.search(
                query_plan.normalized_query,
                query_plan=query_plan,
                top_k=20,  # Return top-20 for comprehensive coverage
                bm25_candidates=200,  # Large pool for better recall
                dense_candidates=200,
                sandwich_reorder=True,
            )
            
            retrieval_end = time.perf_counter()
            retrieval_time = retrieval_end - retrieval_start
            perf_metrics["retrieval_times"].append(retrieval_time)
            
            console.print(f"  🔍 Retrieved {len(search_results)} documents in {retrieval_time:.2f}s")
            
            # Show top 5 results
            if search_results:
                table = Table(show_header=True, header_style="bold magenta", box=None)
                table.add_column("#", style="dim", width=3)
                table.add_column("Law ID", style="yellow", width=20)
                table.add_column("Title", style="green", width=50)
                table.add_column("Score", justify="right", style="cyan", width=8)
                
                for j, doc in enumerate(search_results[:5], 1):
                    law_id = doc.metadata.get('law_id', 'N/A') if hasattr(doc, 'metadata') else 'N/A'
                    title = (doc.title or 'N/A')[:50]
                    score = doc.score
                    
                    table.add_row(
                        str(j),
                        str(law_id),
                        title,
                        f"{score:.1f}"
                    )
                
                console.print(table)
            
            # Store finding
            finding = {
                "clause_number": i + 1,
                "clause_title": clause.get('title', ''),
                "clause_text": clause.get('text', ''),
                "retrieved_docs": [
                    {
                        "doc_id": doc.doc_id if hasattr(doc, 'doc_id') else 'N/A',
                        "law_id": doc.metadata.get('law_id', 'N/A') if hasattr(doc, 'metadata') else 'N/A',
                        "title": doc.title or 'N/A',
                        "score": doc.score,
                        "content_preview": (doc.content or '')[:200]
                    }
                    for doc in search_results[:20]  # Store all 20 results for coverage analysis
                ],
                "status": "retrieved",
                "retrieval_time": retrieval_time
            }
            
            findings.append(finding)
            
        except Exception as e:
            console.print(f"  [bold red]❌ Error: {e}[/bold red]")
            findings.append({
                "clause_number": i + 1,
                "clause_title": clause.get('title', ''),
                "status": "error",
                "error": str(e)
            })
    
    # Calculate total time
    perf_metrics["total_end"] = time.perf_counter()
    perf_metrics["total_time"] = perf_metrics["total_end"] - perf_metrics["total_start"]
    
    # Save detailed output
    output = {
        "test_metadata": {
            "test_name": "Comprehensive Multi-Domain Contract Review Test",
            "contract_file": "test contracts/test_contract_comprehensive.txt",
            "timestamp": datetime.now().isoformat(),
            "pipeline_version": "1.0"
        },
        "contract_analysis": {
            "total_clauses": len(clauses),
            "parsing_time": perf_metrics["parsing_time"],
            "clauses": [
                {
                    "number": i + 1,
                    "title": clause.get('title', ''),
                    "text_preview": clause.get('text', '')[:200]
                }
                for i, clause in enumerate(clauses)
            ]
        },
        "findings": findings,
        "performance_metrics": {
            "warmup_time": f"{perf_metrics['warmup_time']:.2f}s",
            "total_pipeline_time": f"{perf_metrics['total_time']:.2f}s",
            "clause_parsing_time": f"{perf_metrics['parsing_time']:.2f}s",
            "average_retrieval_time": f"{sum(perf_metrics['retrieval_times'])/len(perf_metrics['retrieval_times']):.2f}s" if perf_metrics['retrieval_times'] else "0s",
            "retrieval_times": [f"{t:.2f}s" for t in perf_metrics["retrieval_times"]],
            "total_retrieval_time": f"{sum(perf_metrics['retrieval_times']):.2f}s"
        },
        "raw_clauses": clauses
    }
    
    # Save to file
    output_file = Path(__file__).parent.parent / "test_comprehensive_output.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    console.print(f"\n💾 Detailed output saved to: test_comprehensive_output.json")
    
    # Performance summary
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("⚡ PERFORMANCE METRICS", style="bold cyan")
    console.print("=" * 80 + "\n")
    
    perf_table = Table(show_header=True, header_style="bold magenta")
    perf_table.add_column("Metric", style="cyan", width=35)
    perf_table.add_column("Value", style="yellow", width=15)
    perf_table.add_column("Target", style="dim", width=15)
    perf_table.add_column("Status", style="green", width=10)

    total_time = perf_metrics["total_time"]
    parse_time = perf_metrics["parsing_time"]
    warmup_time = perf_metrics["warmup_time"]
    avg_retrieval = sum(perf_metrics["retrieval_times"]) / len(perf_metrics["retrieval_times"]) if perf_metrics["retrieval_times"] else 0

    perf_table.add_row(
        "Warmup Time",
        f"{warmup_time:.2f}s",
        "< 10s",
        "✅" if warmup_time < 10 else "⚠️"
    )

    perf_table.add_row(
        "Total Pipeline Time",
        f"{total_time:.2f}s",
        "< 20s",
        "✅" if total_time < 20 else "⚠️" if total_time < 25 else "❌"
    )
    
    perf_table.add_row(
        "Contract Parsing",
        f"{parse_time:.2f}s",
        "< 1s",
        "✅" if parse_time < 1 else "❌"
    )
    
    perf_table.add_row(
        "Avg Retrieval/Clause",
        f"{avg_retrieval:.2f}s",
        "< 2s",
        "✅" if avg_retrieval < 2 else "❌"
    )
    
    perf_table.add_row(
        "Clauses Processed",
        str(len(clauses)),
        "7",
        "✅" if len(clauses) == 7 else "⚠️"
    )
    
    perf_table.add_row(
        "Findings Generated",
        str(len(findings)),
        str(len(clauses)),
        "✅" if len(findings) == len(clauses) else "❌"
    )
    
    console.print(perf_table)
    
    # Coverage analysis
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("📊 COVERAGE ANALYSIS", style="bold cyan")
    console.print("=" * 80 + "\n")
    
    # Check which law_ids were found
    all_law_ids = set()
    for finding in findings:
        if "retrieved_docs" in finding:
            for doc in finding["retrieved_docs"]:
                if doc.get("law_id") and doc["law_id"] != "N/A":
                    all_law_ids.add(doc["law_id"])
    
    expected_law_ids = set(expected["expected_summary"]["unique_law_ids_expected"])
    matched_law_ids = all_law_ids.intersection(expected_law_ids)
    missing_law_ids = expected_law_ids - all_law_ids
    
    console.print(f"[bold]Retrieved Law IDs:[/bold] {len(all_law_ids)}")
    console.print(f"[bold]Expected Law IDs:[/bold] {len(expected_law_ids)}")
    console.print(f"[bold green]Matched:[/bold green] {len(matched_law_ids)}")
    console.print(f"[bold red]Missing:[/bold red] {len(missing_law_ids)}\n")
    
    if matched_law_ids:
        console.print("[bold green]✓ Matched Law IDs:[/bold green]")
        for law_id in sorted(matched_law_ids):
            console.print(f"  {law_id}")
    
    if missing_law_ids:
        console.print(f"\n[bold yellow]⚠️  Missing Law IDs:[/bold yellow]")
        for law_id in sorted(missing_law_ids):
            console.print(f"  {law_id}")
    
    # Domain coverage
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("🌐 DOMAIN COVERAGE", style="bold cyan")
    console.print("=" * 80 + "\n")
    
    domains = expected["expected_summary"]["domains_analysis"]
    domain_table = Table(show_header=True, header_style="bold magenta")
    domain_table.add_column("Domain", style="cyan", width=25)
    domain_table.add_column("Clause", style="yellow", width=8)
    domain_table.add_column("Expected Laws", style="green", width=15)
    domain_table.add_column("Risk Level", style="red", width=12)
    
    for domain_name, domain_info in domains.items():
        domain_table.add_row(
            domain_name.replace('_', ' ').title(),
            str(domain_info['clause']),
            str(domain_info['expected_laws']),
            domain_info['risk_level']
        )
    
    console.print(domain_table)
    
    # Retrieval quality per clause
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("🔍 RETRIEVAL QUALITY PER CLAUSE", style="bold cyan")
    console.print("=" * 80 + "\n")
    
    for finding in findings:
        if finding.get("status") == "error":
            console.print(f"[bold red]Clause {finding['clause_number']}: ERROR - {finding['error']}[/bold red]")
            continue
        
        clause_num = finding["clause_number"]
        retrieved = finding.get("retrieved_docs", [])
        
        # Check if expected law_ids are in retrieved docs
        expected_for_clause = expected["expected_findings"][clause_num - 1]
        must_include = set(expected_for_clause["expected_citations"]["must_include_law_ids"])
        
        retrieved_law_ids = set(
            doc["law_id"] for doc in retrieved 
            if doc.get("law_id") and doc["law_id"] != "N/A"
        )
        
        matched = must_include.intersection(retrieved_law_ids)
        coverage = len(matched) / len(must_include) if must_include else 1.0
        
        status_icon = "✅" if coverage >= 0.67 else "⚠️" if coverage >= 0.33 else "❌"
        
        console.print(f"{status_icon} Clause {clause_num}: {finding['clause_title'][:50]}...")
        console.print(f"   Expected: {len(must_include)} specific law_ids")
        console.print(f"   Matched: {len(matched)}/{len(must_include)} ({coverage:.0%})")
        
        if retrieved:
            top_score = retrieved[0].get("score", 0)
            console.print(f"   Top score: {top_score:.1f}")
        
        console.print()
    
    # Missing document analysis
    console.print("\n[bold]Missing Document Analysis:[/bold]")
    for finding in findings:
        clause_num = finding["clause_number"]
        retrieved = finding.get("retrieved_docs", [])
            
        # Check if expected law_ids are in retrieved docs
        expected_for_clause = expected["expected_findings"][clause_num - 1]
        must_include = set(expected_for_clause["expected_citations"]["must_include_law_ids"])
            
        retrieved_law_ids = set(
            doc["law_id"] for doc in retrieved 
            if doc.get("law_id") and doc["law_id"] != "N/A"
        )
            
        matched = must_include.intersection(retrieved_law_ids)
        missing = must_include - retrieved_law_ids
            
        if missing:
            console.print(f"\n[bold red]Clause {clause_num} - Missing Documents:[/bold red]")
            console.print(f"  Expected but NOT retrieved: {sorted(missing)}")
            for law_id in sorted(missing):
                # Find the relevance note
                relevance_notes = expected_for_clause["expected_citations"].get("relevance_notes", {})
                note = relevance_notes.get(law_id, "No note available")
                console.print(f"    - {law_id}: {note}")
    
    console.print()
    
    # Final summary
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("📋 TEST SUMMARY", style="bold cyan")
    console.print("=" * 80 + "\n")
    
    total_clauses = len(clauses)
    successful_retrievals = sum(1 for f in findings if f.get("status") == "retrieved")
    
    console.print(f"Total clauses: [bold]{total_clauses}[/bold]")
    console.print(f"Successful retrievals: [bold green]{successful_retrievals}[/bold green]")
    console.print(f"Failed retrievals: [bold red]{total_clauses - successful_retrievals}[/bold red]")
    console.print(f"Success rate: [bold yellow]{(successful_retrievals/total_clauses*100) if total_clauses > 0 else 0:.1f}%[/bold yellow]\n")
    
    console.print("[bold]Test Characteristics:[/bold]")
    console.print(f"  • Contract length: {len(contract_text)} characters")
    console.print(f"  • Number of clauses: {len(clauses)}")
    console.print(f"  • Legal domains covered: {len(expected['expected_summary']['domains_analysis'])}")
    console.print(f"  • Expected unique citations: {len(expected_law_ids)}")
    console.print(f"  • Contract complexity: High (multi-domain)")
    console.print()
    
    # Close retriever
    try:
        await retriever.close()
        console.print("[dim]🔌 Connections closed successfully[/dim]\n")
    except Exception as e:
        console.print(f"[bold yellow]⚠️  Warning: Error closing connections: {e}[/bold yellow]\n")
    
    console.print("[bold green]✅ Comprehensive test complete![/bold green]\n")


async def main():
    """Run the test."""
    await run_comprehensive_test()


if __name__ == "__main__":
    asyncio.run(main())
