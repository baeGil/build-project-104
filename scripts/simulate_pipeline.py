#!/usr/bin/env python3
"""
Simulate the ACTUAL review pipeline (with reranker) for each clause.
Shows what the reranker does vs raw RRF.
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from packages.common.config import get_settings
from packages.retrieval.hybrid import HybridSearchEngine
from packages.retrieval.reranker import LegalReranker
from packages.reasoning.planner import QueryPlanner

import asyncpg

CLAUSES = {
    1: {"text": "DỊCH VỤ GIỮ XE PHÍ CHỢ NIÊM YẾT GIÁ", "expected": ["166/1999/QĐ-UB", "157/1999/QĐ-UB", "28/1999/CT-UB"]},
    2: {"text": "TỔ CHỨC BỘ MÁY BAN QUẢN LÝ DỰ ÁN UBND", "expected": ["75/1999/QĐ-UB", "99/QĐ-UB", "171/1999/QĐ-UB"]},
    3: {"text": "ĐẤT LÂM NGHIỆP KHOÁNG SẢN KÝ QUỸ SỬ DỤNG ĐẤT", "expected": ["181/1999/QĐ-UB", "24/1999/CT-UB", "90/SL", "88/SL"]},
    4: {"text": "BÁO CÁO ĐỊNH KỲ NIÊM YẾT GIÁ THANH TRA PHẠT TIỀN", "expected": ["28/1999/CT-UB", "111/1999/QĐ-UB"]},
}

async def main():
    settings = get_settings()
    retriever = HybridSearchEngine(settings)
    reranker = LegalReranker(budget_ms=200)
    planner = QueryPlanner()
    
    pool = await asyncpg.create_pool(settings.postgres_dsn)
    
    # Build law_id → doc_id map
    law_id_to_doc_id = {}
    async with pool.acquire() as conn:
        all_expected = set()
        for c in CLAUSES.values():
            all_expected.update(c["expected"])
        rows = await conn.fetch(
            "SELECT id, law_id FROM legal_documents WHERE law_id = ANY($1)",
            list(all_expected)
        )
        for r in rows:
            law_id_to_doc_id[r["law_id"]] = str(r["id"])
    
    print("=" * 90)
    print("FULL PIPELINE SIMULATION: RRF → Reranker → Final Top-5")
    print("=" * 90)
    
    for clause_num, clause_info in CLAUSES.items():
        clause_text = clause_info["text"]
        expected = clause_info["expected"]
        
        query_plan = planner.plan(clause_text)
        
        print(f"\n{'='*90}")
        print(f"CLAUSE {clause_num}: {clause_text}")
        print(f"Query: {query_plan.normalized_query[:80]}")
        print(f"{'='*90}")
        
        # Simulate review_pipeline: search top_k=20 → reranker → top 5
        start = time.perf_counter()
        raw_results = await retriever.search(
            query=query_plan.normalized_query,
            query_plan=query_plan,
            top_k=20,  # Pipeline now fetches 20
        )
        search_time = time.perf_counter() - start
        
        print(f"\n  RAW RRF top-20 (after hybrid search):")
        for i, doc in enumerate(raw_results, 1):
            law_id = doc.metadata.get("law_id", "?")
            print(f"    #{i}: {law_id} (score={doc.score:.1f})")
        
        # Check which expected docs are in raw top-10
        raw_law_ids = [doc.metadata.get("law_id") for doc in raw_results]
        raw_matches = [lid for lid in expected if lid in raw_law_ids]
        print(f"  Expected in raw top-10: {len(raw_matches)}/{len(expected)}")
        
        # Rerank
        start = time.perf_counter()
        reranked = await reranker.rerank(
            query=query_plan.normalized_query,
            candidates=list(raw_results),
            top_k=5,
        )
        rerank_time = time.perf_counter() - start
        
        print(f"\n  RERANKED top-5 (after LegalReranker, {rerank_time:.3f}s):")
        for i, doc in enumerate(reranked, 1):
            law_id = doc.metadata.get("law_id", "?")
            print(f"    #{i}: {law_id} (rerank_score={doc.rerank_score:.4f})")
        
        # Check which expected docs are in reranked top-5
        reranked_law_ids = [doc.metadata.get("law_id") for doc in reranked]
        reranked_matches = [lid for lid in expected if lid in reranked_law_ids]
        print(f"  Expected in reranked top-5: {len(reranked_matches)}/{len(expected)}")
        
        # Show improvement
        if len(reranked_matches) > len(raw_matches):
            gained = set(reranked_matches) - set(raw_matches)
            print(f"  🎉 Reranker IMPROVED: +{', '.join(gained)}")
        elif len(reranked_matches) < len(raw_matches):
            lost = set(raw_matches) - set(reranked_matches)
            print(f"  ⚠️  Reranker LOST: -{', '.join(lost)}")
        else:
            print(f"  → Reranker same as raw RRF")
    
    await pool.close()
    await retriever.close()
    
    print(f"\n{'='*90}")
    print("SIMULATION COMPLETE")
    print(f"{'='*90}")

if __name__ == "__main__":
    asyncio.run(main())
