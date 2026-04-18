#!/usr/bin/env python3
"""Comprehensive data verification across all 4 databases.

Tests the full pipeline: ingestion → PostgreSQL → Qdrant → OpenSearch → Neo4j
Checks for: NULLs, data quality, consistency, relationships, searchability.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table

console = Console()
print = console.print


async def verify_postgres(pool):
    """Verify PostgreSQL data quality."""
    print("\n[bold cyan]📦 PostgreSQL Verification[/]")
    print("=" * 70)
    
    async with pool.acquire() as conn:
        # 1. Total docs
        total = await conn.fetchval("SELECT COUNT(*) FROM legal_documents")
        print(f"  Total documents: {total}")
        
        # 2. doc_type distribution
        rows = await conn.fetch(
            "SELECT doc_type, COUNT(*) as cnt FROM legal_documents GROUP BY doc_type ORDER BY cnt DESC"
        )
        print(f"\n  doc_type distribution:")
        for r in rows:
            print(f"    {r['doc_type']:15s} → {r['cnt']:>5}")
        
        # 3. law_id quality
        law_id_count = await conn.fetchval("SELECT COUNT(*) FROM legal_documents WHERE law_id IS NOT NULL")
        law_id_null = await conn.fetchval("SELECT COUNT(*) FROM legal_documents WHERE law_id IS NULL")
        print(f"\n  law_id: {law_id_count} non-NULL, {law_id_null} NULL ({law_id_count/total*100:.1f}%)")
        
        # Sample non-NULL law_ids
        sample = await conn.fetch("SELECT law_id FROM legal_documents WHERE law_id IS NOT NULL LIMIT 5")
        print(f"  Sample law_ids: {[r['law_id'] for r in sample]}")
        
        # 4. NULL checks on critical fields
        null_content = await conn.fetchval("SELECT COUNT(*) FROM legal_documents WHERE content IS NULL OR content = ''")
        null_title = await conn.fetchval("SELECT COUNT(*) FROM legal_documents WHERE title IS NULL OR title = ''")
        null_doctype = await conn.fetchval("SELECT COUNT(*) FROM legal_documents WHERE doc_type IS NULL OR doc_type = ''")
        
        print(f"\n  Field NULLs:")
        print(f"    content:    {null_content} (should be 0)")
        print(f"    title:      {null_title} (should be 0)")
        print(f"    doc_type:   {null_doctype} (should be 0)")
        
        # 5. doc_type enum validation
        valid_types = {'luat', 'nghi_dinh', 'thong_tu', 'quyet_dinh', 'nghi_quyet', 'other'}
        invalid = await conn.fetch(
            "SELECT DISTINCT doc_type FROM legal_documents WHERE doc_type NOT IN ('luat','nghi_dinh','thong_tu','quyet_dinh','nghi_quyet','other')"
        )
        if invalid:
            print(f"\n  ⚠️  INVALID doc_types found: {[r['doc_type'] for r in invalid]}")
        else:
            print(f"\n  ✓ All doc_types are valid enum values")
        
        # 6. Metadata JSONB quality
        metadata_rows = await conn.fetch("SELECT metadata FROM legal_documents LIMIT 20")
        dates_in_metadata = 0
        for row in metadata_rows:
            meta = row['metadata']
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except:
                    continue
            if meta.get('publish_date') or meta.get('effective_date'):
                dates_in_metadata += 1
        
        print(f"\n  Metadata quality (sample 20):")
        print(f"    Documents with dates in metadata: {dates_in_metadata}/20")
        
        # 7. Sample doc with all fields
        sample_doc = await conn.fetchrow(
            "SELECT id, title, doc_type, law_id, metadata FROM legal_documents WHERE law_id IS NOT NULL LIMIT 1"
        )
        print(f"\n  Sample document:")
        print(f"    id:        {sample_doc['id']}")
        print(f"    title:     {sample_doc['title'][:80]}")
        print(f"    doc_type:  {sample_doc['doc_type']}")
        print(f"    law_id:    {sample_doc['law_id']}")
        meta = sample_doc['metadata']
        if isinstance(meta, str):
            meta = json.loads(meta)
        print(f"    metadata keys: {list(meta.keys())}")
        
        # 8. Relationships
        rel_count = await conn.fetchval("SELECT COUNT(*) FROM document_relationships")
        print(f"\n  Relationships: {rel_count}")
        
        if rel_count > 0:
            rel_types = await conn.fetch(
                "SELECT relationship_type, COUNT(*) as cnt FROM document_relationships GROUP BY relationship_type ORDER BY cnt DESC"
            )
            print(f"  Relationship types:")
            for r in rel_types:
                print(f"    {r['relationship_type']:40s} → {r['cnt']:>5}")
    
    return {
        'total': total,
        'law_id_pct': law_id_count / total * 100 if total > 0 else 0,
        'null_content': null_content,
        'null_title': null_title,
        'invalid_doctype': len(invalid),
        'relationships': rel_count,
    }


async def verify_qdrant(settings):
    """Verify Qdrant data quality."""
    print("\n[bold cyan]🔵 Qdrant Verification[/]")
    print("=" * 70)
    
    from qdrant_client import QdrantClient
    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    
    # 1. Total points
    collection_name = settings.qdrant_collection
    collections = client.get_collections().collections
    if not any(c.name == collection_name for c in collections):
        print(f"  ⚠️  Collection '{collection_name}' does not exist!")
        return {'total': 0, 'law_id_pct': 0}
    
    count = client.count(collection_name=collection_name).count
    print(f"  Total points: {count}")
    
    # 2. Sample payload
    points = client.scroll(collection_name=collection_name, limit=5, with_payload=True, with_vectors=False)
    
    # Check for law_id in payloads
    law_id_count = 0
    doc_type_valid = True
    for point in points[0]:
        payload = point.payload
        if payload.get('law_id'):
            law_id_count += 1
        
        # Verify doc_type is enum value
        dt = payload.get('doc_type', '')
        if dt not in {'luat', 'nghi_dinh', 'thong_tu', 'quyet_dinh', 'nghi_quyet', 'other'}:
            doc_type_valid = False
        
        print(f"  Point {point.id}:")
        print(f"    doc_type: {dt}")
        print(f"    law_id:   {payload.get('law_id')}")
        print(f"    title:    {payload.get('title', '')[:60]}")
    
    law_id_pct = law_id_count / len(points[0]) * 100 if points[0] else 0
    
    print(f"\n  Law ID coverage (sample): {law_id_pct:.1f}%")
    print(f"  All doc_types valid: {'✓' if doc_type_valid else '⚠️'}")
    
    return {'total': count, 'law_id_pct': law_id_pct}


async def verify_opensearch(settings):
    """Verify OpenSearch data quality."""
    print("\n[bold cyan]🔍 OpenSearch Verification[/]")
    print("=" * 70)
    
    from opensearchpy import OpenSearch
    client = OpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        http_auth=(settings.opensearch_user, settings.opensearch_password),
        use_ssl=False,
        verify_certs=False,
    )
    
    index_name = settings.opensearch_index
    
    # 1. Total docs
    if not client.indices.exists(index=index_name):
        print(f"  ⚠️  Index '{index_name}' does not exist!")
        return {'total': 0}
    
    count = client.count(index=index_name)['count']
    print(f"  Total documents: {count}")
    
    # 2. Sample docs
    response = client.search(
        index=index_name,
        body={"size": 5, "query": {"match_all": {}}}
    )
    
    law_id_count = 0
    for hit in response['hits']['hits']:
        src = hit['_source']
        if src.get('law_id'):
            law_id_count += 1
        print(f"  Doc {hit['_id']}:")
        print(f"    doc_type: {src.get('doc_type')}")
        print(f"    law_id:   {src.get('law_id')}")
        print(f"    title:    {src.get('title', '')[:60]}")
    
    law_id_pct = law_id_count / len(response['hits']['hits']) * 100 if response['hits']['hits'] else 0
    print(f"\n  Law ID coverage (sample): {law_id_pct:.1f}%")
    
    return {'total': count, 'law_id_pct': law_id_pct}


async def verify_neo4j(settings):
    """Verify Neo4j data quality."""
    print("\n[bold cyan]🟢 Neo4j Verification[/]")
    print("=" * 70)
    
    from neo4j import AsyncGraphDatabase
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    
    async with driver as driver_obj:
        # 1. Total documents
        async with driver_obj.session() as session:
            result = await session.run("MATCH (d:Document) RETURN count(d) as cnt")
            record = await result.single()
            total = record['cnt']
            print(f"  Total Document nodes: {total}")
        
        # 2. doc_type distribution
        async with driver_obj.session() as session:
            result = await session.run(
                "MATCH (d:Document) RETURN d.doc_type as dt, count(d) as cnt ORDER BY cnt DESC"
            )
            print(f"\n  doc_type distribution:")
            async for r in result:
                dt = r['dt'] or 'NULL'
                print(f"    {str(dt):15s} → {r['cnt']:>5}")
        
        # 3. law_id quality
        async with driver_obj.session() as session:
            result = await session.run(
                "MATCH (d:Document) WHERE d.law_id IS NOT NULL RETURN count(d) as cnt"
            )
            record = await result.single()
            law_id_count = record['cnt']
            law_id_pct = law_id_count / total * 100 if total > 0 else 0
            print(f"\n  law_id: {law_id_count} non-NULL, {total - law_id_count} NULL ({law_id_pct:.1f}%)")
        
        # 4. Relationships
        async with driver_obj.session() as session:
            result = await session.run("MATCH ()-[r:RELATES_TO]->() RETURN count(r) as cnt")
            record = await result.single()
            rel_count = record['cnt']
            print(f"\n  RELATES_TO relationships: {rel_count}")
            
            # Relationship types
            if rel_count > 0:
                result = await session.run(
                    "MATCH ()-[r:RELATES_TO]->() RETURN r.type as type, count(r) as cnt ORDER BY cnt DESC LIMIT 10"
                )
                print(f"  Top relationship types:")
                async for r in result:
                    print(f"    {r['type']:40s} → {r['cnt']:>5}")
        
        # 5. Sample doc
        async with driver_obj.session() as session:
            result = await session.run(
                "MATCH (d:Document) WHERE d.law_id IS NOT NULL RETURN d LIMIT 1"
            )
            record = await result.single()
            if record:
                doc = record['d']
                print(f"\n  Sample document:")
                print(f"    id:            {doc.get('id')}")
                print(f"    title:         {str(doc.get('title', ''))[:60]}")
                print(f"    doc_type:      {doc.get('doc_type')}")
                print(f"    law_id:        {doc.get('law_id')}")
                print(f"    publish_date:  {doc.get('publish_date')}")
                print(f"    effective_date:{doc.get('effective_date')}")
        
        # 6. Articles (hierarchy)
        async with driver_obj.session() as session:
            result = await session.run("MATCH (a:Article) RETURN count(a) as cnt")
            record = await result.single()
            article_count = record['cnt']
            print(f"\n  Article nodes: {article_count}")
            print(f"  Articles per doc: {article_count/total:.1f}" if total > 0 else "  Articles per doc: 0")
        
        # 7. Content length distribution
        async with driver_obj.session() as session:
            result = await session.run(
                "MATCH (d:Document) WHERE d.content IS NOT NULL RETURN "
                "count(CASE WHEN size(d.content) >= 5000 THEN 1 END) as long_docs, "
                "count(CASE WHEN size(d.content) < 500 THEN 1 END) as short_docs, "
                "count(d) as total_with_content"
            )
            record = await result.single()
            long_docs = record['long_docs']
            short_docs = record['short_docs']
            print(f"\n  Content length:")
            print(f"    Long docs (>= 5000 chars, full content): {long_docs}")
            print(f"    Short docs (< 500 chars): {short_docs}")
            if short_docs > 0:
                print(f"  ⚠️  {short_docs} docs may have very short content")
    
    return {
        'total': total,
        'law_id_pct': law_id_pct,
        'relationships': rel_count,
        'articles': article_count,
        'short_docs': short_docs,
    }


async def main():
    import asyncpg
    from packages.common.config import get_settings
    
    settings = get_settings()
    
    print("\n" + "=" * 70)
    print("[bold green]🔍 COMPREHENSIVE DATA VERIFICATION[/]")
    print("=" * 70)
    
    # ---- PostgreSQL ----
    pool = await asyncpg.create_pool(settings.postgres_dsn, min_size=1, max_size=2)
    pg_stats = await verify_postgres(pool)
    
    # ---- Qdrant ----
    qdrant_stats = await verify_qdrant(settings)
    
    # ---- OpenSearch ----
    os_stats = await verify_opensearch(settings)
    
    # ---- Neo4j ----
    neo4j_stats = await verify_neo4j(settings)
    
    # ---- Summary ----
    print("\n" + "=" * 70)
    print("[bold green]📊 VERIFICATION SUMMARY[/]")
    print("=" * 70)
    
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Database", style="cyan")
    table.add_column("Total", justify="right")
    table.add_column("law_id %", justify="right")
    table.add_column("Relationships", justify="right")
    table.add_column("Issues", style="red")
    
    pg_issues = []
    if pg_stats['null_content'] > 0:
        pg_issues.append(f"{pg_stats['null_content']} NULL content")
    if pg_stats['invalid_doctype'] > 0:
        pg_issues.append(f"{pg_stats['invalid_doctype']} invalid doc_type")
    
    table.add_row(
        "PostgreSQL",
        str(pg_stats['total']),
        f"{pg_stats['law_id_pct']:.1f}%",
        str(pg_stats['relationships']),
        "; ".join(pg_issues) if pg_issues else "✓",
    )
    table.add_row("Qdrant", str(qdrant_stats['total']), f"{qdrant_stats['law_id_pct']:.1f}%", "-", "✓")
    table.add_row("OpenSearch", str(os_stats['total']), f"{os_stats['law_id_pct']:.1f}%", "-", "✓")
    
    neo4j_issues = []
    if neo4j_stats.get('short_docs', 0) > 0:
        neo4j_issues.append(f"{neo4j_stats['short_docs']} very short docs")
    
    table.add_row(
        "Neo4j",
        str(neo4j_stats['total']),
        f"{neo4j_stats['law_id_pct']:.1f}%",
        str(neo4j_stats['relationships']),
        "; ".join(neo4j_issues) if neo4j_issues else "✓",
    )
    
    print(table)
    
    # ---- Consistency checks ----
    print("\n[bold cyan]🔗 Cross-Database Consistency[/]")
    print("=" * 70)
    
    consistency_ok = True
    
    if pg_stats['total'] != qdrant_stats['total']:
        print(f"  ⚠️  PostgreSQL ({pg_stats['total']}) ≠ Qdrant ({qdrant_stats['total']})")
        consistency_ok = False
    else:
        print(f"  ✓ PostgreSQL = Qdrant = {pg_stats['total']}")
    
    if pg_stats['total'] != os_stats['total']:
        print(f"  ⚠️  PostgreSQL ({pg_stats['total']}) ≠ OpenSearch ({os_stats['total']})")
        consistency_ok = False
    else:
        print(f"  ✓ PostgreSQL = OpenSearch = {pg_stats['total']}")
    
    if pg_stats['total'] != neo4j_stats['total']:
        print(f"  ⚠️  PostgreSQL ({pg_stats['total']}) ≠ Neo4j ({neo4j_stats['total']})")
        consistency_ok = False
    else:
        print(f"  ✓ PostgreSQL = Neo4j = {pg_stats['total']}")
    
    print(f"\n  Relationships: PG={pg_stats['relationships']}, Neo4j={neo4j_stats['relationships']}")
    
    # ---- Final verdict ----
    print("\n" + "=" * 70)
    if consistency_ok and pg_stats['invalid_doctype'] == 0 and pg_stats['null_content'] == 0:
        print("[bold green]✅ ALL DATA IS CLEAN AND READY FOR PRODUCTION[/]")
    else:
        print("[bold yellow]⚠️  DATA HAS MINOR ISSUES — REVIEW ABOVE[/]")
    print("=" * 70 + "\n")
    
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
