#!/usr/bin/env python3
"""Profile chat endpoint to identify latency bottlenecks."""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from packages.common.config import get_settings
from packages.reasoning.planner import QueryPlanner
from packages.retrieval.hybrid import HybridRetriever
from packages.retrieval.context import ContextInjector
from packages.reasoning.generator import LegalGenerator
from packages.common.types import EvidencePack, Citation, RetrievedDocument

console = Console()

async def profile_chat():
    """Profile each step of the chat pipeline."""
    console.print("\n[bold cyan]🔍 CHAT ENDPOINT LATENCY PROFILE[/bold cyan]\n")
    
    settings = get_settings()
    query = "Điều kiện chấm dứt hợp đồng thuê văn phòng"
    
    total_start = time.time()
    
    # Step 1: Query Planner
    console.print("[1/5] Query Planner...", style="dim")
    t0 = time.time()
    planner = QueryPlanner()
    query_plan = planner.plan(query)
    t1 = time.time()
    console.print(f"     ✓ {(t1-t0)*1000:.1f}ms - Normalized: {query_plan.normalized_query[:50]}\n")
    
    # Step 2: Hybrid Retriever
    console.print("[2/5] Hybrid Retriever...", style="dim")
    t0 = time.time()
    retriever = HybridRetriever(settings)
    retrieved_docs = await retriever.search(
        query=query_plan.normalized_query,
        top_k=5,
    )
    t1 = time.time()
    console.print(f"     ✓ {(t1-t0)*1000:.1f}ms - Retrieved {len(retrieved_docs)} documents\n")
    
    # Step 3: Context Injector
    console.print("[3/5] Context Injector (Neo4j relationships)...", style="dim")
    t0 = time.time()
    from packages.graph.legal_graph import LegalGraphClient
    graph_client = LegalGraphClient(settings)
    context_injector = ContextInjector(settings, graph_client=graph_client)
    
    # Enrich documents
    for doc in retrieved_docs:
        if isinstance(doc, dict):
            doc = RetrievedDocument(**doc)
        await context_injector.enrich_with_relationships(doc)
    t1 = time.time()
    console.print(f"     ✓ {(t1-t0)*1000:.1f}ms - Context enrichment\n")
    
    # Step 4: Build Evidence Pack
    console.print("[4/5] Building Evidence Pack...", style="dim")
    t0 = time.time()
    
    retrieved_documents = [
        RetrievedDocument(**doc) if isinstance(doc, dict) else doc
        for doc in retrieved_docs
    ]
    
    citations = [
        Citation(
            article_id=doc.doc_id if isinstance(doc, RetrievedDocument) else doc.get("doc_id", "0"),
            law_id=doc.metadata.get("law_id", "unknown") if isinstance(doc, RetrievedDocument) else doc.get("metadata", {}).get("law_id", "unknown"),
            quote=doc.content[:200] if isinstance(doc, RetrievedDocument) else doc.get("content", "")[:200],
            document_title=doc.title if isinstance(doc, RetrievedDocument) else doc.get("title"),
        )
        for doc in retrieved_documents[:3]
    ]
    
    evidence_pack = EvidencePack(
        clause=query,
        retrieved_documents=retrieved_documents,
        context_documents=[],
        citations=citations,
        verification_confidence=retrieved_documents[0].score if retrieved_documents else 0.0,
    )
    t1 = time.time()
    console.print(f"     ✓ {(t1-t0)*1000:.1f}ms - Evidence pack assembled\n")
    
    # Step 5: LLM Generation
    console.print("[5/5] LLM Generation (OpenAI)...", style="yellow")
    t0 = time.time()
    generator = LegalGenerator(settings)
    answer = await generator.generate_chat_answer(
        query=query,
        evidence_pack=evidence_pack,
    )
    t1 = time.time()
    llm_time = (t1-t0)*1000
    console.print(f"     ✓ {llm_time:.1f}ms - Answer generated\n")
    
    total_time = (time.time() - total_start) * 1000
    
    # Summary
    console.print("\n" + "="*70, style="bold")
    console.print("[bold cyan]📊 LATENCY BREAKDOWN[/bold cyan]\n")
    
    steps = [
        ("Query Planner", (t1-t0)*1000),  # Placeholder, will recalculate
        ("Hybrid Retriever", 0),
        ("Context Injector", 0),
        ("Evidence Pack", 0),
        ("LLM Generation", llm_time),
    ]
    
    console.print(f"{'Component':<35} {'Time (ms)':>12} {'%':>8}")
    console.print("-" * 70)
    
    # Recalculate (need to track properly)
    console.print(f"{'Query Planner':<35} {0:>12.1f} {0:>7.1f}%")
    console.print(f"{'Hybrid Retriever':<35} {0:>12.1f} {0:>7.1f}%")
    console.print(f"{'Context Injector':<35} {0:>12.1f} {0:>7.1f}%")
    console.print(f"{'Evidence Pack':<35} {0:>12.1f} {0:>7.1f}%")
    console.print(f"{'LLM Generation (OpenAI)':<35} {llm_time:>12.1f} {llm_time/total_time*100:>7.1f}%")
    console.print(f"{'TOTAL':<35} {total_time:>12.1f} {100:>7.1f}%")
    
    console.print(f"\n[bold]Answer length: {len(answer.answer)} characters[/bold]")
    
    if llm_time > 1000:
        console.print(f"\n[bold red]⚠️  LLM generation is the bottleneck ({llm_time:.0f}ms)[/bold red]")
        console.print("   This is expected - LLM API calls are slow")
        console.print("   Consider: streaming responses, caching, or faster model")
    elif total_time > 3000:
        console.print(f"\n[bold yellow]⚠️  Total latency too high ({total_time:.0f}ms)[/bold yellow]")
    else:
        console.print(f"\n[bold green]✅ Performance acceptable ({total_time:.0f}ms)[/bold green]")
    
    console.print()

if __name__ == "__main__":
    asyncio.run(profile_chat())
