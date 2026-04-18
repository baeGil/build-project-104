#!/usr/bin/env python3
"""Force cleanup Neo4j - delete ALL non-numeric ID documents."""

from neo4j import GraphDatabase
from packages.common.config import get_settings

def cleanup_neo4j():
    settings = get_settings()
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
    
    print("=" * 70)
    print("🧹 NEO4J FORCE CLEANUP")
    print("=" * 70)
    
    with driver.session() as session:
        # Count before
        total_before = session.run("MATCH (d:Document) RETURN count(d) as count").single()['count']
        print(f"\nTotal Document nodes before: {total_before}")
        
        # Count numeric (keep these)
        numeric_count = session.run("""
            MATCH (d:Document)
            WHERE d.id =~ '^[0-9]+$'
            RETURN count(d) as count
        """).single()['count']
        print(f"Numeric IDs (will keep): {numeric_count}")
        
        # Count non-numeric (delete these)
        non_numeric_count = session.run("""
            MATCH (d:Document)
            WHERE NOT (d.id =~ '^[0-9]+$')
            RETURN count(d) as count
        """).single()['count']
        print(f"Non-numeric IDs (will delete): {non_numeric_count}")
        
        if non_numeric_count == 0:
            print("\n✅ No cleanup needed!")
            driver.close()
            return
        
        print(f"\n🗑️  Deleting {non_numeric_count} test/sample documents...")
        
        # Delete non-numeric ID documents and their relationships
        result = session.run("""
            MATCH (d:Document)
            WHERE NOT (d.id =~ '^[0-9]+$')
            WITH d
            OPTIONAL MATCH (d)-[r]-()
            DELETE d, r
            RETURN count(d) as deleted
        """)
        
        deleted = result.single()['deleted']
        print(f"✅ Deleted {deleted} documents")
        
        # Verify
        total_after = session.run("MATCH (d:Document) RETURN count(d) as count").single()['count']
        print(f"\nTotal Document nodes after: {total_after}")
        print(f"Removed: {total_before - total_after} documents")
        
        if total_after == numeric_count:
            print("✅ Cleanup successful! Only real legal documents remain.")
        else:
            print(f"⚠️  Expected {numeric_count}, got {total_after}")
        
        # Check for other node types
        print("\n📊 Node type distribution:")
        labels = session.run("CALL db.labels()").data()
        for label in labels:
            label_name = label['label']
            count = session.run(f"MATCH (n:{label_name}) RETURN count(n) as count").single()['count']
            print(f"  {label_name}: {count}")
    
    driver.close()
    
    print("\n" + "=" * 70)
    print("✅ NEO4J CLEANUP COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    cleanup_neo4j()
