#!/usr/bin/env python3
"""
RRF trace: For each clause, show BM25 rank, Dense rank, and final RRF fused rank
for all expected documents. Identifies EXACTLY where docs get dropped.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from packages.common.config import get_settings
from packages.retrieval.hybrid import HybridSearchEngine
from packages.retrieval.rrf import reciprocal_rank_fusion
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
    print("RRF FUSION TRACE: BM25 rank vs Dense rank vs Final fused rank")
    print("=" * 90)
    
    for clause_num, clause_info in CLAUSES.items():
        clause_text = clause_info["text"]
        expected = clause_info["expected"]
        
        query_plan = planner.plan(clause_text)
        
        print(f"\n{'='*90}")
        print(f"CLAUSE {clause_num}: {clause_text}")
        print(f"Query: {query_plan.normalized_query[:80]}")
        print(f"{'='*90}")
        
        # Run individual BM25 and dense searches
        bm25_results = await retriever._bm25_search(
            query_plan.normalized_query, 
            size=100,
            expansion_queries=query_plan.expansion_variants[:5],
        )
        
        dense_results = await retriever._dense_search(
            query_plan.normalized_query,
            limit=100,
        )
        
        # Build rank maps
        bm25_rank_map = {doc_id: rank+1 for rank, (doc_id, _) in enumerate(bm25_results)}
        dense_rank_map = {doc_id: rank+1 for rank, (doc_id, _) in enumerate(dense_results)}
        
        # RRF fusion — equal weight
        fused_results = reciprocal_rank_fusion(
            result_lists=[bm25_results, dense_results],
            k=60,
            top_n=20,
        )
        fused_rank_map = {doc_id: rank+1 for rank, (doc_id, _) in enumerate(fused_results)}
        
        # Weighted RRF — BM25 bias, top-20 pool
        from packages.retrieval.rrf import weighted_rrf
        fused_weighted = weighted_rrf(
            result_lists=[bm25_results, dense_results],
            weights=[0.8, 0.2],
            k=60,
            top_n=20,
        )
        fused_weighted_map = {doc_id: rank+1 for rank, (doc_id, _) in enumerate(fused_weighted)}
        
        # For each expected doc, show BM25 rank, Dense rank, equal RRF rank, weighted RRF rank
        print(f"\n{'Law ID':<20} {'DocID':<6} {'BM25':>6} {'Dense':>6} {'RRF':>6} {'wRRF':>6} {'Status':<30}")
        print("-" * 90)
        
        for law_id in expected:
            doc_id = law_id_to_doc_id.get(law_id, "?")
            bm25_r = bm25_rank_map.get(doc_id, "N/A")
            dense_r = dense_rank_map.get(doc_id, "N/A")
            rrf_r = fused_rank_map.get(doc_id, "N/A")
            wrrf_r = fused_weighted_map.get(doc_id, "N/A")
            
            # Determine status (compare equal vs weighted)
            if isinstance(wrrf_r, int) and wrrf_r <= 5:
                status = "✅ IN TOP-5 (weighted RRF)"
            elif isinstance(rrf_r, int) and rrf_r <= 5:
                status = "✅ IN TOP-5 (equal RRF)"
            elif isinstance(wrrf_r, int) and wrrf_r <= 10:
                status = "⚠️  wRRF top-10 (better than RRF)" if (isinstance(rrf_r, int) and wrrf_r < rrf_r) else "⚠️  In top-10"
            elif isinstance(rrf_r, int) and isinstance(wrrf_r, int) and wrrf_r < rrf_r:
                status = f"🔧 wRRF improves: #{rrf_r}→#{wrrf_r}"
            elif isinstance(bm25_r, int) and isinstance(dense_r, int):
                status = "❌ BM25+Dense found, RRF lost"
            elif isinstance(bm25_r, int):
                status = "❌ BM25 found, Dense lost"
            elif isinstance(dense_r, int):
                status = "❌ Dense found, BM25 lost"
            else:
                status = "❌❌ NOT FOUND AT ALL"
            
            print(f"{law_id:<20} {doc_id:<6} {str(bm25_r):>6} {str(dense_r):>6} {str(rrf_r):>6} {str(wrrf_r):>6} {status}")
        
        # Show TOP-5 final results
        print(f"\n  TOP-5 FINAL RESULTS:")
        for rank, (doc_id, score) in enumerate(fused_results[:5], 1):
            # Get law_id
            law_id = "?"
            for lid, did in law_id_to_doc_id.items():
                if did == doc_id:
                    law_id = lid
                    break
            print(f"    #{rank}: doc_id={doc_id}, law_id={law_id}, RRF score={score:.4f}")
    
    await pool.close()
    await retriever.close()
    
    print(f"\n{'='*90}")
    print("TRACE COMPLETE")
    print(f"{'='*90}")

if __name__ == "__main__":
    asyncio.run(main())
