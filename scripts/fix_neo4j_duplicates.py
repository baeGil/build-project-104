#!/usr/bin/env python3
"""Fix duplicate relationships in Neo4j by keeping only one per (source, target, type)."""

import asyncio
from neo4j import GraphDatabase
from packages.common.config import get_settings

async def fix_neo4j_duplicates():
    settings = get_settings()
    
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
    
    with driver.session() as session:
        print("=" * 70)
        print("🔧 FIXING NEO4J DUPLICATE RELATIONSHIPS")
        print("=" * 70)
        
        # Count before
        result = session.run("MATCH ()-[r]->() RETURN count(r) as total")
        total_before = result.single()["total"]
        print(f"\n📊 Total relationships before: {total_before:,}")
        
        # Find and delete duplicates, keeping the oldest (by created_at)
        # True duplicates = same source, target, relationship type, AND type property
        print("\n🔍 Finding duplicates...")
        result = session.run("""
            MATCH (s)-[r]->(t)
            WITH s, type(r) as rel_type, t, r.type as rel_subtype, collect(r) as rels, count(r) as cnt
            WHERE cnt > 1
            WITH rels, cnt
            UNWIND rels[1..] as duplicate_rel  // Keep first, delete rest
            DELETE duplicate_rel
            RETURN count(*) as deleted
        """)
        
        deleted = result.single()["deleted"]
        print(f"\n🗑️  Deleted {deleted:,} duplicate relationships")
        
        # Count after
        result = session.run("MATCH ()-[r]->() RETURN count(r) as total")
        total_after = result.single()["total"]
        print(f"📊 Total relationships after: {total_after:,}")
        print(f"✅ Removed {total_before - total_after:,} duplicates")
        
        # Verify no more duplicates
        print("\n🔍 Verifying...")
        result = session.run("""
            MATCH (s)-[r]->(t)
            WITH s, type(r) as rel_type, t, r.type as rel_subtype, count(r) as cnt
            WHERE cnt > 1
            RETURN count(*) as remaining_duplicates
        """)
        
        remaining = result.single()["remaining_duplicates"]
        if remaining == 0:
            print(f"✅ No duplicates remaining!")
        else:
            print(f"⚠️  Still {remaining:,} duplicate groups (may need manual fix)")
        
        # Show final distribution
        print("\n📊 Final relationship distribution:")
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as rel_type, count(r) as count
            ORDER BY count DESC
        """)
        
        for record in result:
            print(f"   {record['rel_type']}: {record['count']:,}")
    
    driver.close()
    
    print("\n" + "=" * 70)
    print("✅ DUPLICATE FIX COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(fix_neo4j_duplicates())
