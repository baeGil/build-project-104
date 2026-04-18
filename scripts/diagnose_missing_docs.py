#!/usr/bin/env python3
"""
Deep diagnostic: For each clause, trace WHY expected documents are missing.
Compares BM25 scores, dense scores, and actual ranking positions.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from packages.common.config import get_settings
from packages.retrieval.hybrid import HybridSearchEngine
from packages.reasoning.planner import QueryPlanner

import asyncpg
import json

# Ground truth: clause → expected missing law_ids
MISSING_DOCS = {
    1: ["157/1999/QĐ-UB", "28/1999/CT-UB"],  # Was matched before, lost after opt
    2: ["171/1999/QĐ-UB"],  # Was #1 before, lost after title^4
    3: ["24/1999/CT-UB", "90/SL"],
    4: ["111/1999/QĐ-UB"],
}

# Clause texts
CLAUSES = {
    1: "DỊCH VỤ GIỮ XE PHÍ CHỢ NIÊM YẾT GIÁ",
    2: "TỔ CHỨC BỘ MÁY BAN QUẢN LÝ DỰ ÁN UBND",
    3: "ĐẤT LÂM NGHIỆP KHOÁNG SẢN KÝ QUỸ SỬ DỤNG ĐẤT",
    4: "BÁO CÁO ĐỊNH KỲ NIÊM YẾT GIÁ THANH TRA PHẠT TIỀN",
}

async def main():
    settings = get_settings()
    retriever = HybridSearchEngine(settings)
    planner = QueryPlanner()
    
    # Get pool for DB lookups
    pool = await asyncpg.create_pool(settings.postgres_dsn)
    
    print("=" * 80)
    print("DEEP DIAGNOSTIC: Why are expected documents missing?")
    print("=" * 80)
    
    for clause_num, expected_missing in MISSING_DOCS.items():
        clause_text = CLAUSES[clause_num]
        
        print(f"\n{'='*60}")
        print(f"CLAUSE {clause_num}: {clause_text}")
        print(f"{'='*60}")
        
        # Plan query
        query_plan = planner.plan(clause_text)
        print(f"\nNormalized query: {query_plan.normalized_query[:100]}")
        print(f"Expansion variants: {query_plan.expansion_variants[:3]}")
        
        # Run search with BM25+Dense and check where missing docs rank
        async with pool.acquire() as conn:
            for missing_law_id in expected_missing:
                # Get the document
                rows = await conn.fetch('''
                    SELECT id, title, LEFT(content, 300) as content_preview
                    FROM legal_documents WHERE law_id = $1
                ''', missing_law_id)
                
                if not rows:
                    print(f"\n  ❌ {missing_law_id}: NOT IN DATABASE")
                    continue
                
                doc = rows[0]
                print(f"\n  --- {missing_law_id} ---")
                print(f"  Title: {doc['title'][:100]}")
                print(f"  Content preview: {doc['content_preview'][:150]}...")
                
                # Check if this doc is in OpenSearch
                try:
                    from opensearchpy import AsyncOpenSearch
                    os_client = AsyncOpenSearch(
                        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
                        http_auth=(settings.opensearch_user, settings.opensearch_password),
                        use_ssl=False, verify_certs=False,
                    )
                    
                    # Search for this specific doc with the clause query
                    resp = await os_client.get(
                        index=settings.opensearch_index,
                        id=str(doc['id']),
                        ignore=[404]
                    )
                    
                    if resp.get('found'):
                        print(f"  ✅ In OpenSearch: YES (id={doc['id']})")
                        
                        # Now run BM25-only search and check rank
                        bm25_resp = await os_client.search(
                            index=settings.opensearch_index,
                            body={
                                "query": {
                                    "multi_match": {
                                        "query": query_plan.normalized_query,
                                        "fields": ["title^1.5", "content^1"],
                                        "type": "best_fields",
                                        "tie_breaker": 0.3,
                                    }
                                },
                                "size": 20,
                                "_source": ["title", "law_id"],
                            }
                        )
                        
                        # Find rank of this doc
                        found_rank = None
                        bm25_score = None
                        for i, hit in enumerate(bm25_resp['hits']['hits']):
                            if hit['_id'] == str(doc['id']):
                                found_rank = i + 1
                                bm25_score = hit['_score']
                                break
                        
                        if found_rank:
                            print(f"  BM25 rank: #{found_rank} (score={bm25_score:.2f})")
                            if found_rank <= 10:
                                print(f"  → Should be in top-10 candidates ✅")
                            elif found_rank <= 20:
                                print(f"  → In top-20 BM25 candidates but RRF might drop it ⚠️")
                            else:
                                print(f"  → TOO LOW for RRF fusion ❌")
                        else:
                            print(f"  BM25 rank: NOT IN TOP 20")
                            print(f"  → BM25 doesn't find it at all ❌")
                        
                        # Also check dense search
                        from qdrant_client import AsyncQdrantClient
                        qdrant = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
                        
                        # Get embedding
                        from packages.retrieval.embedding import EmbeddingService
                        embedding_service = EmbeddingService.get_instance(model_name=settings.embedding_model)
                        query_vec = embedding_service.encode_query(query_plan.normalized_query)
                        
                        dense_resp = await qdrant.search(
                            collection_name=settings.qdrant_collection,
                            query_vector=query_vec.tolist(),
                            limit=20,
                        )
                        
                        found_dense_rank = None
                        dense_score = None
                        for i, point in enumerate(dense_resp):
                            if str(point.id) == str(doc['id']):
                                found_dense_rank = i + 1
                                dense_score = point.score
                                break
                        
                        if found_dense_rank:
                            print(f"  Dense rank: #{found_dense_rank} (score={dense_score:.4f})")
                        else:
                            print(f"  Dense rank: NOT IN TOP 20")
                        
                        await qdrant.close()
                    else:
                        print(f"  ❌ In OpenSearch: NO (id={doc['id']} not found)")
                    
                    await os_client.close()
                    
                except Exception as e:
                    print(f"  ⚠️ Error checking: {e}")
    
    await pool.close()
    await retriever.close()
    
    print(f"\n{'='*80}")
    print("DIAGNOSTIC COMPLETE")
    print(f"{'='*80}")

if __name__ == "__main__":
    asyncio.run(main())
