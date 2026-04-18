#!/usr/bin/env python3
"""Clean up test/invalid documents from PostgreSQL."""

import asyncio
import asyncpg
from packages.common.config import get_settings

async def cleanup():
    settings = get_settings()
    pool = await asyncpg.create_pool(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )
    
    async with pool.acquire() as conn:
        # Find test/invalid docs
        test_docs = await conn.fetch("""
            SELECT id, title, doc_type, LENGTH(content) as content_length
            FROM legal_documents
            WHERE id IN ('empty-doc', 'test-doc', 'sample-doc')
               OR content IS NULL 
               OR content = ''
               OR title IS NULL
               OR title = ''
        """)
        
        if not test_docs:
            print("✅ No test/invalid documents found")
            await pool.close()
            return
        
        print(f"Found {len(test_docs)} test/invalid document(s):")
        for doc in test_docs:
            print(f"  - {doc['id']}: {doc['title']} (content: {doc['content_length']} chars)")
        
        print("\nCleaning up...")
        
        total_rels_deleted = 0
        
        for doc in test_docs:
            doc_id = doc['id']
            
            # Delete relationships first
            rel_count = await conn.fetchval("""
                SELECT COUNT(*) FROM document_relationships
                WHERE source_doc_id = $1 OR target_doc_id = $1
            """, doc_id)
            
            if rel_count > 0:
                await conn.execute("""
                    DELETE FROM document_relationships
                    WHERE source_doc_id = $1 OR target_doc_id = $1
                """, doc_id)
                total_rels_deleted += rel_count
            
            # Delete document
            await conn.execute("""
                DELETE FROM legal_documents
                WHERE id = $1
            """, doc_id)
            
            print(f"  ✅ Deleted '{doc_id}' ({rel_count} relationships)")
        
        print(f"\n✅ Cleanup complete!")
        print(f"   Deleted {len(test_docs)} document(s)")
        print(f"   Deleted {total_rels_deleted} relationship(s)")
        
        # Verify
        remaining = await conn.fetchval("""
            SELECT COUNT(*) FROM legal_documents
            WHERE content IS NULL OR content = ''
               OR title IS NULL OR title = ''
        """)
        print(f"   Remaining invalid docs: {remaining}")
    
    await pool.close()

if __name__ == "__main__":
    asyncio.run(cleanup())
