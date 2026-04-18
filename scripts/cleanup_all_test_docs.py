#!/usr/bin/env python3
"""Clean up ALL test/sample documents from all databases."""

import asyncio
import asyncpg
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from packages.common.config import get_settings

async def cleanup_postgres():
    """Remove test documents from PostgreSQL."""
    settings = get_settings()
    pool = await asyncpg.create_pool(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )
    
    async with pool.acquire() as conn:
        print("=" * 70)
        print("🧹 POSTGRESQL CLEANUP")
        print("=" * 70)
        
        # Find test/sample docs
        test_docs = await conn.fetch("""
            SELECT id, title, doc_type
            FROM legal_documents
            WHERE id IN ('test-doc-1', 'doc-2', 'empty-doc')
               OR id LIKE '%test%'
               OR id LIKE '%sample%'
               OR id LIKE '%demo%'
               OR title = 'Test Document'
               OR title = 'Document 1'
               OR title = 'Law 1'
               OR title = 'Law 2'
               OR title = 'Doc 2'
               OR doc_type = 'other'
        """)
        
        if not test_docs:
            print("✅ No test documents found")
            await pool.close()
            return 0
        
        print(f"\nFound {len(test_docs)} test/sample documents:")
        for doc in test_docs[:10]:
            print(f"  - {doc['id']}: {doc['title']} ({doc['doc_type']})")
        if len(test_docs) > 10:
            print(f"  ... and {len(test_docs) - 10} more")
        
        # Delete relationships first
        for doc in test_docs:
            await conn.execute("""
                DELETE FROM document_relationships
                WHERE source_doc_id = $1 OR target_doc_id = $1
            """, doc['id'])
        
        # Delete documents
        for doc in test_docs:
            await conn.execute("""
                DELETE FROM legal_documents
                WHERE id = $1
            """, doc['id'])
        
        print(f"\n✅ Deleted {len(test_docs)} test documents from PostgreSQL")
        
        # Verify
        remaining = await conn.fetchval("SELECT COUNT(*) FROM legal_documents")
        print(f"   Remaining documents: {remaining}")
        
        await pool.close()
        return len(test_docs)

async def cleanup_neo4j():
    """Remove test documents from Neo4j."""
    settings = get_settings()
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
    
    print("\n" + "=" * 70)
    print("🧹 NEO4J CLEANUP")
    print("=" * 70)
    
    with driver.session() as session:
        # Find and delete test docs and their relationships
        result = session.run("""
            MATCH (d:Document)
            WHERE d.id IN ['test-doc-1', 'doc-2', 'empty-doc']
               OR d.id CONTAINS 'test'
               OR d.id CONTAINS 'sample'
               OR d.title = 'Test Document'
               OR d.title = 'Document 1'
               OR d.title = 'Law 1'
               OR d.title = 'Law 2'
               OR d.title = 'Doc 2'
            WITH d
            OPTIONAL MATCH (d)-[r]-()
            DELETE r, d
            RETURN count(d) as deleted
        """)
        
        deleted = result.single()['deleted']
        print(f"✅ Deleted {deleted} test documents from Neo4j")
        
        # Verify
        remaining = session.run("MATCH (d:Document) RETURN count(d) as count").single()['count']
        print(f"   Remaining Document nodes: {remaining}")
    
    driver.close()
    return deleted

async def cleanup_qdrant():
    """Remove test documents from Qdrant."""
    settings = get_settings()
    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    
    print("\n" + "=" * 70)
    print("🧹 QDRANT CLEANUP")
    print("=" * 70)
    
    # Get all points and filter test docs
    records, _ = client.scroll(
        collection_name=settings.qdrant_collection,
        limit=10000,
        with_payload=True,
        with_vectors=False,
    )
    
    test_point_ids = []
    
    for record in records:
        payload = record.payload or {}
        law_id = payload.get('law_id', '')
        title = payload.get('title', '')
        
        # Check if test doc
        if (law_id in ['test-doc-1', 'doc-2', 'empty-doc'] or
            'test' in law_id.lower() or
            'sample' in law_id.lower() or
            title in ['Test Document', 'Document 1', 'Law 1', 'Law 2', 'Doc 2']):
            test_point_ids.append(record.id)
    
    if not test_point_ids:
        print("✅ No test documents found in Qdrant")
        client.close()
        return 0
    
    print(f"Found {len(test_point_ids)} test points in Qdrant")
    
    # Delete in batches
    batch_size = 100
    for i in range(0, len(test_point_ids), batch_size):
        batch = test_point_ids[i:i+batch_size]
        client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=batch,
        )
    
    print(f"✅ Deleted {len(test_point_ids)} test points from Qdrant")
    
    # Verify
    info = client.get_collection(settings.qdrant_collection)
    print(f"   Remaining points: {info.points_count}")
    
    client.close()
    return len(test_point_ids)

async def main():
    print("\n" + "=" * 70)
    print("🗑️  COMPREHENSIVE DATABASE CLEANUP")
    print("   Removing all test/sample documents")
    print("=" * 70 + "\n")
    
    # Cleanup all databases
    pg_deleted = await cleanup_postgres()
    neo4j_deleted = await cleanup_neo4j()
    qdrant_deleted = await cleanup_qdrant()
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ CLEANUP SUMMARY")
    print("=" * 70)
    print(f"  PostgreSQL: {pg_deleted} documents deleted")
    print(f"  Neo4j:      {neo4j_deleted} documents deleted")
    print(f"  Qdrant:     {qdrant_deleted} points deleted")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
