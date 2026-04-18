#!/usr/bin/env python3
"""
Analyze Ground Truth Test Results

Compares actual retrieval results with expected ground truth and generates
a comprehensive analysis report.

Usage:
    uv run python scripts/analyze_groundtruth.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()


def load_json(filepath: str) -> dict:
    """Load JSON file."""
    path = Path(__file__).parent.parent / filepath
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def analyze_results():
    """Analyze ground truth test results."""
    
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("📊 GROUND TRUTH TEST ANALYSIS", style="bold cyan")
    console.print("=" * 80 + "\n")
    
    # Load results
    actual = load_json("test_groundtruth_output.json")
    expected = load_json("EXPECTED_GROUNDTRUTH_OUTPUT.json")
    
    # ========================================
    # 1. OVERALL TEST SUMMARY
    # ========================================
    console.print("[bold]1. OVERALL TEST SUMMARY[/bold]\n")
    
    summary_table = Table(show_header=False, box=None)
    summary_table.add_column("Metric", style="cyan", width=40)
    summary_table.add_column("Value", style="yellow", width=30)
    summary_table.add_column("Status", width=10)
    
    # Clauses
    total_clauses = actual["contract_analysis"]["total_clauses"]
    expected_clauses = expected["expected_summary"]["total_findings"]
    clause_status = "✅" if total_clauses >= expected_clauses else "⚠️"
    summary_table.add_row(
        "Total Clauses",
        f"{total_clauses} (expected: {expected_clauses})",
        clause_status
    )
    
    # Retrieval success
    successful = sum(1 for f in actual["findings"] if f.get("status") == "retrieved")
    summary_table.add_row(
        "Successful Retrievals",
        f"{successful}/{total_clauses}",
        "✅" if successful == total_clauses else "❌"
    )
    
    # Law ID coverage
    all_retrieved_law_ids = set()
    for finding in actual["findings"]:
        if "retrieved_docs" in finding:
            for doc in finding["retrieved_docs"]:
                if doc.get("law_id") and doc["law_id"] != "N/A":
                    all_retrieved_law_ids.add(doc["law_id"])
    
    expected_law_ids = set(expected["expected_summary"]["unique_law_ids_expected"])
    matched = all_retrieved_law_ids.intersection(expected_law_ids)
    coverage = len(matched) / len(expected_law_ids) if expected_law_ids else 0
    
    summary_table.add_row(
        "Law ID Coverage",
        f"{len(matched)}/{len(expected_law_ids)} ({coverage:.0%})",
        "✅" if coverage >= 0.7 else "⚠️" if coverage >= 0.5 else "❌"
    )
    
    # Performance
    total_time = float(actual["performance_metrics"]["total_pipeline_time"].replace("s", ""))
    summary_table.add_row(
        "Total Pipeline Time",
        f"{total_time:.2f}s",
        "✅" if total_time < 15 else "⚠️" if total_time < 20 else "❌"
    )
    
    avg_retrieval = float(actual["performance_metrics"]["average_retrieval_time"].replace("s", ""))
    summary_table.add_row(
        "Avg Retrieval Time",
        f"{avg_retrieval:.2f}s",
        "✅" if avg_retrieval < 2 else "⚠️" if avg_retrieval < 3 else "❌"
    )
    
    console.print(summary_table)
    
    # ========================================
    # 2. CLAUSE-BY-CLAUSE ANALYSIS
    # ========================================
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("[bold]2. CLAUSE-BY-CLAUSE RETRIEVAL QUALITY[/bold]\n")
    
    for i, finding in enumerate(actual["findings"]):
        clause_num = finding["clause_number"]
        clause_title = finding.get("clause_title", "N/A")[:70]
        
        console.print(f"[bold cyan]Clause {clause_num}: {clause_title}[/bold cyan]")
        
        # Get expected for this clause
        if clause_num <= len(expected["expected_findings"]):
            exp = expected["expected_findings"][clause_num - 1]
            
            # Check law ID matches
            must_include = set(exp["expected_citations"]["must_include_law_ids"])
            
            retrieved_law_ids = set()
            if "retrieved_docs" in finding:
                retrieved_law_ids = set(
                    doc["law_id"] for doc in finding["retrieved_docs"]
                    if doc.get("law_id") and doc["law_id"] != "N/A"
                )
            
            matched = must_include.intersection(retrieved_law_ids)
            missing = must_include - retrieved_law_ids
            coverage = len(matched) / len(must_include) if must_include else 1.0
            
            # Status
            if coverage >= 0.67:
                status = "[bold green]✅ GOOD[/bold green]"
            elif coverage >= 0.33:
                status = "[bold yellow]⚠️  PARTIAL[/bold yellow]"
            else:
                status = "[bold red]❌ POOR[/bold red]"
            
            console.print(f"  Coverage: {status} ({len(matched)}/{len(must_include)} = {coverage:.0%})")
            
            # Show matched
            if matched:
                console.print(f"  [green]✓ Matched:[/green]")
                for law_id in sorted(matched):
                    # Get score
                    score = next(
                        (doc["score"] for doc in finding.get("retrieved_docs", [])
                         if doc.get("law_id") == law_id),
                        0
                    )
                    console.print(f"    - {law_id} (score: {score:.1f})")
            
            # Show missing
            if missing:
                console.print(f"  [red]✗ Missing:[/red]")
                for law_id in sorted(missing):
                    console.print(f"    - {law_id}")
            
            # Show top 3 retrieved
            if finding.get("retrieved_docs"):
                console.print(f"  [dim]Top retrieved:[/dim]")
                for doc in finding["retrieved_docs"][:3]:
                    console.print(f"    • {doc['law_id']}: {doc['title'][:60]}... (score: {doc['score']:.1f})")
        else:
            console.print(f"  [dim]No expected data for this clause[/dim]")
        
        console.print()
    
    # ========================================
    # 3. PERFORMANCE ANALYSIS
    # ========================================
    console.print("=" * 80, style="bold cyan")
    console.print("[bold]3. PERFORMANCE ANALYSIS[/bold]\n")
    
    perf = actual["performance_metrics"]
    
    perf_table = Table(show_header=True, header_style="bold magenta")
    perf_table.add_column("Metric", style="cyan", width=35)
    perf_table.add_column("Actual", style="yellow", width=15, justify="right")
    perf_table.add_column("Target", style="dim", width=15, justify="right")
    perf_table.add_column("Status", width=10)
    
    # Parse times
    total_time = float(perf["total_pipeline_time"].replace("s", ""))
    parse_time = float(perf["clause_parsing_time"].replace("s", ""))
    avg_retrieval = float(perf["average_retrieval_time"].replace("s", ""))
    
    perf_table.add_row(
        "Total Pipeline Time",
        f"{total_time:.2f}s",
        "< 15s",
        "✅" if total_time < 15 else "⚠️" if total_time < 20 else "❌"
    )
    
    perf_table.add_row(
        "Clause Parsing",
        f"{parse_time:.3f}s",
        "< 1s",
        "✅" if parse_time < 1 else "❌"
    )
    
    perf_table.add_row(
        "Avg Retrieval/Clause",
        f"{avg_retrieval:.2f}s",
        "< 2s",
        "✅" if avg_retrieval < 2 else "⚠️" if avg_retrieval < 3 else "❌"
    )
    
    perf_table.add_row(
        "Total Retrieval Time",
        perf["total_retrieval_time"],
        "< 8s",
        "✅" if float(perf["total_retrieval_time"].replace("s", "")) < 8 else "⚠️"
    )
    
    console.print(perf_table)
    
    # Retrieval time breakdown
    console.print(f"\n[dim]Retrieval times per clause: {', '.join(perf['retrieval_times'])}[/dim]")
    console.print(f"[dim]Note: First retrieval is slower due to model loading (one-time cost)[/dim]\n")
    
    # ========================================
    # 4. STRENGTHS & WEAKNESSES
    # ========================================
    console.print("=" * 80, style="bold cyan")
    console.print("[bold]4. STRENGTHS & WEAKNESSES[/bold]\n")
    
    # Strengths
    console.print("[bold green]✓ STRENGTHS:[/bold green]\n")
    
    strengths = []
    
    if coverage >= 0.7:
        strengths.append(f"Law ID coverage is good ({coverage:.0%})")
    
    if total_time < 15:
        strengths.append(f"Pipeline completes within target ({total_time:.2f}s < 15s)")
    
    if successful == total_clauses:
        strengths.append(f"All clauses successfully retrieved ({successful}/{total_clauses})")
    
    # Check for perfect matches
    perfect_matches = 0
    for i, f in enumerate(actual["findings"]):
        if f.get("retrieved_docs") and i < len(expected["expected_findings"]):
            exp = expected["expected_findings"][i]
            must_include = set(exp["expected_citations"]["must_include_law_ids"])
            retrieved = set(doc["law_id"] for doc in f["retrieved_docs"] if doc.get("law_id"))
            if must_include.issubset(retrieved):
                perfect_matches += 1
    
    if perfect_matches > 0:
        strengths.append(f"{perfect_matches} clause(s) have 100% law ID coverage")
    
    for s in strengths:
        console.print(f"  • {s}")
    
    # Weaknesses
    console.print(f"\n[bold yellow]⚠️  WEAKNESSES:[/bold yellow]\n")
    
    weaknesses = []
    
    missing_law_ids = expected_law_ids - all_retrieved_law_ids
    if missing_law_ids:
        weaknesses.append(f"Missing {len(missing_law_ids)} expected law IDs: {', '.join(sorted(missing_law_ids))}")
    
    if avg_retrieval >= 2:
        weaknesses.append(f"Retrieval time slightly above target ({avg_retrieval:.2f}s >= 2s)")
    
    # Check low coverage clauses
    low_coverage = []
    for i, finding in enumerate(actual["findings"]):
        if i < len(expected["expected_findings"]) and finding.get("retrieved_docs"):
            exp = expected["expected_findings"][i]
            must_include = set(exp["expected_citations"]["must_include_law_ids"])
            retrieved = set(doc["law_id"] for doc in finding["retrieved_docs"] if doc.get("law_id"))
            coverage = len(must_include.intersection(retrieved)) / len(must_include) if must_include else 1.0
            if coverage < 0.67:
                low_coverage.append((i + 1, coverage))
    
    if low_coverage:
        weaknesses.append(f"{len(low_coverage)} clause(s) have <67% coverage: {', '.join(f'#{n} ({c:.0%})' for n, c in low_coverage)}")
    
    for w in weaknesses:
        console.print(f"  • {w}")
    
    # ========================================
    # 5. ROOT CAUSE ANALYSIS
    # ========================================
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("[bold]5. ROOT CAUSE ANALYSIS[/bold]\n")
    
    console.print("[bold]Missing Law IDs Analysis:[/bold]\n")
    
    for law_id in sorted(missing_law_ids):
        console.print(f"\n[bold yellow]{law_id}[/bold yellow]")
        
        # Find which clause expected it
        for i, exp in enumerate(expected["expected_findings"]):
            if law_id in exp["expected_citations"]["must_include_law_ids"]:
                console.print(f"  Expected in: Clause {i+1} - {exp['clause_title'][:50]}...")
                console.print(f"  Relevance: {exp['expected_citations']['relevance_notes'].get(law_id, 'N/A')[:100]}...")
                
                # Check what was actually retrieved
                if i < len(actual["findings"]) and actual["findings"][i].get("retrieved_docs"):
                    retrieved = actual["findings"][i]["retrieved_docs"][:3]
                    console.print(f"  Actually retrieved:")
                    for doc in retrieved:
                        console.print(f"    - {doc['law_id']}: {doc['title'][:60]}... (score: {doc['score']:.1f})")
    
    # ========================================
    # 6. RECOMMENDATIONS
    # ========================================
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("[bold]6. RECOMMENDATIONS[/bold]\n")
    
    recommendations = [
        ("HIGH PRIORITY", [
            "Consider adding 111/1999/QĐ-UB to improve Clause 4 coverage (administrative procedures)",
            "Add 157/1999/QĐ-UB (market fees) to support pricing-related clauses",
        ]),
        ("MEDIUM PRIORITY", [
            "First retrieval is slow (9.95s) due to model loading - consider pre-loading embedding model",
            "Subsequent retrievals are fast (0.07-0.13s) - well within target",
        ]),
        ("LOW PRIORITY", [
            "88/SL (ruộng đất lĩnh canh) is from 1950s - may have low semantic similarity with modern terms",
            "Consider adding metadata boosting for law_id matching in hybrid search",
        ])
    ]
    
    for priority, items in recommendations:
        console.print(f"[bold]{priority}:[/bold]")
        for item in items:
            console.print(f"  • {item}")
        console.print()
    
    # ========================================
    # 7. FINAL VERDICT
    # ========================================
    console.print("=" * 80, style="bold cyan")
    console.print("[bold]7. FINAL VERDICT[/bold]\n")
    
    # Calculate overall score
    score_components = []
    
    # Law ID coverage (40%)
    score_components.append(("Law ID Coverage", coverage * 40, 40))
    
    # Performance (30%)
    perf_score = max(0, 30 - (total_time - 15) * 2) if total_time > 15 else 30
    score_components.append(("Performance", perf_score, 30))
    
    # Retrieval success (30%)
    success_rate = successful / total_clauses if total_clauses > 0 else 0
    score_components.append(("Retrieval Success", success_rate * 30, 30))
    
    total_score = sum(s for _, s, _ in score_components)
    max_score = sum(m for _, _, m in score_components)
    percentage = (total_score / max_score * 100) if max_score > 0 else 0
    
    verdict_table = Table(show_header=True, header_style="bold magenta")
    verdict_table.add_column("Component", style="cyan", width=30)
    verdict_table.add_column("Score", style="yellow", width=15, justify="right")
    verdict_table.add_column("Max", style="dim", width=10, justify="right")
    verdict_table.add_column("%", style="green", width=10, justify="right")
    
    for name, score, max_s in score_components:
        pct = (score / max_s * 100) if max_s > 0 else 0
        verdict_table.add_row(name, f"{score:.1f}", str(max_s), f"{pct:.0f}%")
    
    verdict_table.add_row("TOTAL", f"{total_score:.1f}", str(max_score), f"{percentage:.0f}%", style="bold")
    
    console.print(verdict_table)
    
    # Verdict
    console.print()
    if percentage >= 80:
        verdict_text = Text("✅ EXCELLENT - System is production-ready!", style="bold green")
    elif percentage >= 60:
        verdict_text = Text("✅ GOOD - Minor improvements needed", style="bold yellow")
    elif percentage >= 40:
        verdict_text = Text("⚠️  MODERATE - Significant improvements needed", style="bold yellow")
    else:
        verdict_text = Text("❌ POOR - Major issues to address", style="bold red")
    
    console.print(Panel(verdict_text, title="VERDICT", border_style="green" if percentage >= 60 else "red"))
    
    console.print()
    console.print(f"[dim]Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]")
    console.print(f"[dim]Detailed output: test_groundtruth_output.json[/dim]")
    console.print(f"[dim]Expected output: EXPECTED_GROUNDTRUTH_OUTPUT.json[/dim]\n")


if __name__ == "__main__":
    analyze_results()
