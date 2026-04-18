#!/usr/bin/env python3
"""
Quick Test Script - Contract Review with Detailed Logging

Tests the contract review pipeline with comprehensive performance metrics.
Outputs detailed logs for monitoring and debugging.

Usage:
    uv run python scripts/quick_test.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from packages.common.config import get_settings
from packages.common.types import EvidencePack, ReviewFinding
from packages.ingestion.pipeline import IngestionPipeline
from packages.retrieval.hybrid import HybridRetriever
from packages.reasoning.generator import LegalGenerator
from packages.reasoning.review_pipeline import ContractReviewPipeline

console = Console()


class PerformanceMonitor:
    """Track and log performance metrics."""
    
    def __init__(self):
        self.metrics: dict[str, Any] = {
            "total_time": 0.0,
            "parsing_time": 0.0,
            "retrieval_times": [],
            "generation_times": [],
            "verification_time": 0.0,
            "summary_time": 0.0,
            "total_clauses": 0,
            "total_findings": 0,
            "error_count": 0,
            "errors": [],
        }
    
    def log_metric(self, name: str, value: float):
        """Log a timing metric."""
        if name == "retrieval" or name == "generation":
            self.metrics[f"{name}_times"].append(value)
        else:
            self.metrics[f"{name}_time"] = value
        console.print(f"⏱️  {name}: {value:.2f}s")
    
    def log_error(self, error: str):
        """Log an error."""
        self.metrics["error_count"] += 1
        self.metrics["errors"].append(error)
        console.print(f"❌ Error: {error}", style="red")
    
    def print_summary(self):
        """Print performance summary table."""
        table = Table(title="⚡ Performance Metrics", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="yellow")
        table.add_column("Target", justify="right", style="green")
        table.add_column("Status", style="bold")
        
        # Total time
        total = self.metrics["total_time"]
        table.add_row(
            "Total Pipeline Time",
            f"{total:.2f}s",
            "< 15s",
            "✅" if total < 15 else "❌",
        )
        
        # Parsing
        parsing = self.metrics["parsing_time"]
        table.add_row(
            "Contract Parsing",
            f"{parsing:.2f}s",
            "< 1s",
            "✅" if parsing < 1 else "❌",
        )
        
        # Retrieval (avg)
        if self.metrics["retrieval_times"]:
            avg_retrieval = sum(self.metrics["retrieval_times"]) / len(self.metrics["retrieval_times"])
            max_retrieval = max(self.metrics["retrieval_times"])
            table.add_row(
                "Retrieval (avg/max)",
                f"{avg_retrieval:.2f}s / {max_retrieval:.2f}s",
                "< 2s avg",
                "✅" if avg_retrieval < 2 else "❌",
            )
        
        # Generation (avg)
        if self.metrics["generation_times"]:
            avg_gen = sum(self.metrics["generation_times"]) / len(self.metrics["generation_times"])
            max_gen = max(self.metrics["generation_times"])
            table.add_row(
                "Generation (avg/max)",
                f"{avg_gen:.2f}s / {max_gen:.2f}s",
                "< 2s avg",
                "✅" if avg_gen < 2 else "❌",
            )
        
        # Clauses & Findings
        table.add_row(
            "Clauses Processed",
            str(self.metrics["total_clauses"]),
            "5",
            "✅" if self.metrics["total_clauses"] == 5 else "⚠️",
        )
        
        table.add_row(
            "Findings Generated",
            str(self.metrics["total_findings"]),
            "4-5",
            "✅" if 4 <= self.metrics["total_findings"] <= 5 else "⚠️",
        )
        
        # Errors
        table.add_row(
            "Errors",
            str(self.metrics["error_count"]),
            "0",
            "✅" if self.metrics["error_count"] == 0 else "❌",
        )
        
        console.print(table)
        
        # Detailed breakdown
        if self.metrics["errors"]:
            console.print("\n❌ Errors:", style="bold red")
            for error in self.metrics["errors"]:
                console.print(f"  - {error}", style="red")


async def run_quick_test():
    """Run the quick contract review test."""
    console.print(Panel.fit("🚀 Quick Test - Contract Review Pipeline", style="bold cyan"))
    
    # Initialize
    settings = get_settings()
    monitor = PerformanceMonitor()
    
    # Load test contract
    contract_file = Path(__file__).parent.parent / "test contracts" / "quick_test_contract.txt"
    console.print(f"\n📄 Loading contract: {contract_file}")
    
    if not contract_file.exists():
        console.print(f"❌ Contract file not found: {contract_file}", style="red")
        return
    
    contract_text = contract_file.read_text(encoding="utf-8")
    console.print(f"✅ Contract loaded: {len(contract_text)} characters")
    
    # Initialize pipeline
    console.print("\n🔧 Initializing pipeline...")
    start_time = time.time()
    
    try:
        pipeline = ContractReviewPipeline(settings)
        console.print("✅ Pipeline initialized")
    except Exception as e:
        console.print(f"❌ Failed to initialize pipeline: {e}", style="red")
        return
    
    # Run review
    console.print("\n🔍 Running contract review...\n")
    
    try:
        result = await pipeline.review_contract(contract_text)
        
        # Calculate total time
        monitor.metrics["total_time"] = time.time() - start_time
        monitor.metrics["total_clauses"] = len(result.findings) if result.findings else 0
        monitor.metrics["total_findings"] = len(result.findings)
        
        # Print results
        console.print("\n" + "="*80)
        console.print("📊 REVIEW RESULTS", style="bold cyan")
        console.print("="*80 + "\n")
        
        # Summary statistics
        risk_counts = {"high": 0, "medium": 0, "low": 0, "none": 0}
        for finding in result.findings:
            risk_level = finding.risk_level.value if hasattr(finding.risk_level, 'value') else str(finding.risk_level)
            risk_counts[risk_level] = risk_counts.get(risk_level, 0) + 1
        
        summary_table = Table(title="📈 Risk Distribution", show_header=True, header_style="bold")
        summary_table.add_column("Risk Level", style="bold")
        summary_table.add_column("Count", justify="center")
        summary_table.add_column("Percentage", justify="right")
        
        for level, color in [("high", "red"), ("medium", "yellow"), ("low", "blue"), ("none", "green")]:
            count = risk_counts[level]
            pct = (count / max(1, len(result.findings))) * 100
            summary_table.add_row(
                f"[{color}]{level.upper()}[/{color}]",
                str(count),
                f"{pct:.1f}%",
            )
        
        console.print(summary_table)
        
        # Detailed findings
        console.print("\n📝 Detailed Findings:\n")
        for i, finding in enumerate(result.findings, 1):
            risk_level = finding.risk_level.value if hasattr(finding.risk_level, 'value') else str(finding.risk_level)
            risk_color = {"high": "red", "medium": "yellow", "low": "blue", "none": "green"}.get(risk_level, "white")
            
            console.print(f"[bold]Finding {i}:[/bold] [{risk_color}]{risk_level.upper()}[/{risk_color}]")
            console.print(f"  Clause: {finding.clause_text[:100]}...")
            console.print(f"  Confidence: {finding.confidence:.1f}%")
            console.print(f"  Citations: {len(finding.citations)}")
            console.print(f"  Rationale: {finding.rationale[:200]}...")
            
            if finding.revision_suggestion and finding.revision_suggestion != "Không cần sửa đổi":
                console.print(f"  Revision: {finding.revision_suggestion[:150]}...")
            
            console.print()
        
        # Save full JSON output
        output_file = Path(__file__).parent.parent / "test_output.json"
        
        # Custom JSON serializer to handle datetime objects
        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj):
                from datetime import datetime, date
                if isinstance(obj, (datetime, date)):
                    return obj.isoformat()
                return super().default(obj)
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, indent=2, ensure_ascii=False, cls=DateTimeEncoder)
        console.print(f"💾 Full output saved to: {output_file}")
        
    except Exception as e:
        monitor.log_error(f"Pipeline execution failed: {str(e)}")
        import traceback
        console.print(f"\n❌ Error details:\n{traceback.format_exc()}", style="red")
    
    finally:
        # Print performance summary
        console.print("\n" + "="*80)
        monitor.print_summary()
        console.print("="*80)
        
        # Next steps
        console.print("\n📤 Next Steps:")
        console.print("1. Review the output in: test_output.json")
        console.print("2. Compare with expected output in: EXPECTED_QUICK_TEST.md")
        console.print("3. Send results back to AI assistant for analysis")
        console.print("\n✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(run_quick_test())
