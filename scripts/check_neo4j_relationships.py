#!/usr/bin/env python3
"""Check for duplicate relationships in Neo4j."""

import asyncio
from neo4j import GraphDatabase
from packages.common.config import get_settings

async def check_neo4j_duplicates():
    settings = get_settings()
    
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
    
    with driver.session() as session:
        print("=" * 70)
        print("🔍 NEO4J RELATIONSHIP DUPLICATE CHECK")
        print("=" * 70)
        
        # 1. Total relationships
        result = session.run("MATCH ()-[r]->() RETURN count(r) as total")
        total = result.single()["total"]
        print(f"\n📊 Total relationships: {total:,}")
        
        # 2. Check for duplicates (same source, target, type, AND type property)
        print("\n🔍 Checking for duplicate relationships...")
        result = session.run("""
            MATCH (s)-[r]->(t)
            WITH s, type(r) as rel_type, t, r.type as rel_subtype, count(r) as cnt
            WHERE cnt > 1
            RETURN count(*) as duplicate_groups, sum(cnt) as duplicate_rels
        """)
        record = result.single()
        
        if record and record["duplicate_groups"] > 0:
            dup_groups = record["duplicate_groups"]
            dup_rels = record["duplicate_rels"]
            print(f"\n🔴 FOUND DUPLICATES!")
            print(f"   Duplicate groups: {dup_groups:,}")
            print(f"   Total duplicate relationships: {dup_rels:,}")
            print(f"   Unique relationships should be: {total - dup_rels + dup_groups:,}")
            
            # Show top 10 duplicates
            print("\n📋 Top 10 most duplicated relationships:")
            result = session.run("""
                MATCH (s:Document)-[r]->(t:Document)
                WITH s.id as source, type(r) as rel_type, r.type as rel_subtype, t.id as target, count(r) as cnt
                WHERE cnt > 1
                RETURN source, rel_type, rel_subtype, target, cnt
                ORDER BY cnt DESC
                LIMIT 10
            """)
            
            for record in result:
                print(f"   {record['source']} --[{record['rel_type']} {{type: {record['rel_subtype']}}}]→ {record['target']}: {record['cnt']} copies")
        else:
            print(f"\n✅ No duplicates found!")
            
        # 3. Relationship type distribution
        print("\n📊 Relationship type distribution:")
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as rel_type, count(r) as count
            ORDER BY count DESC
        """)
        
        for record in result:
            print(f"   {record['rel_type']}: {record['count']:,}")
        
        # 4. Check RELATES_TO relationships with type property
        print("\n🔍 Checking RELATES_TO relationships...")
        result = session.run("""
            MATCH ()-[r:RELATES_TO]->()
            RETURN count(r) as total, 
                   count(CASE WHEN r.type IS NOT NULL THEN 1 END) as with_type_prop,
                   count(CASE WHEN r.type IS NULL THEN 1 END) as without_type_prop
        """)
        record = result.single()
        print(f"   Total RELATES_TO: {record['total']:,}")
        print(f"   With 'type' property: {record['with_type_prop']:,}")
        print(f"   Without 'type' property: {record['without_type_prop']:,}")
        
    driver.close()
    
    print("\n" + "=" * 70)
    print("💡 RECOMMENDATION:")
    print("=" * 70)
    print("If duplicates found, run: python scripts/fix_neo4j_duplicates.py")

if __name__ == "__main__":
    asyncio.run(check_neo4j_duplicates())
