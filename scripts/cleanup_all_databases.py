#!/usr/bin/env python3
"""
Complete database cleanup - removes ALL data from all 4 databases.
Use this to start fresh before reindexing.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
import requests
from packages.common.config import get_settings
from rich.console import Console

console = Console()

async def cleanup_postgresql():
    """Remove all data from PostgreSQL."""
    console.print("\n" + "=" * 70)
    console.print("🗄️  CLEANING POSTGRESQL", style="bold cyan")
    console.print("=" * 70)
    
    settings = get_settings()
    pool = await asyncpg.create_pool(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )
    
    async with pool.acquire() as conn:
        # Count before
        doc_count = await conn.fetchval("SELECT COUNT(*) FROM legal_documents")
        rel_count = await conn.fetchval("SELECT COUNT(*) FROM document_relationships")
        console.print(f"\nBefore cleanup:")
        console.print(f"  Documents: {doc_count}")
        console.print(f"  Relationships: {rel_count}")
        
        # Delete relationships first (foreign key constraint)
        await conn.execute("DELETE FROM document_relationships")
        console.print(f"\n✅ Deleted all relationships")
        
        # Delete all documents
        await conn.execute("DELETE FROM legal_documents")
        console.print(f"✅ Deleted all documents")
        
        # Verify
        doc_count_after = await conn.fetchval("SELECT COUNT(*) FROM legal_documents")
        rel_count_after = await conn.fetchval("SELECT COUNT(*) FROM document_relationships")
        console.print(f"\nAfter cleanup:")
        console.print(f"  Documents: {doc_count_after} ✅")
        console.print(f"  Relationships: {rel_count_after} ✅")
    
    await pool.close()

def cleanup_neo4j():
    """Remove all data from Neo4j."""
    console.print("\n" + "=" * 70)
    console.print("🕸️  CLEANING NEO4J", style="bold cyan")
    console.print("=" * 70)
    
    settings = get_settings()
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
    
    with driver.session() as session:
        # Count before
        total_nodes = session.run("MATCH (n) RETURN count(n) as count").single()['count']
        total_rels = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()['count']
        
        console.print(f"\nBefore cleanup:")
        console.print(f"  Total nodes: {total_nodes}")
        console.print(f"  Total relationships: {total_rels}")
        
        # Delete all relationships first
        session.run("MATCH ()-[r]->() DELETE r")
        console.print(f"\n✅ Deleted all relationships")
        
        # Delete all nodes
        session.run("MATCH (n) DELETE n")
        console.print(f"✅ Deleted all nodes")
        
        # Verify
        total_nodes_after = session.run("MATCH (n) RETURN count(n) as count").single()['count']
        total_rels_after = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()['count']
        console.print(f"\nAfter cleanup:")
        console.print(f"  Total nodes: {total_nodes_after} ✅")
        console.print(f"  Total relationships: {total_rels_after} ✅")
    
    driver.close()

def cleanup_qdrant():
    """Remove all data from Qdrant."""
    console.print("\n" + "=" * 70)
    console.print("🎯 CLEANING QDRANT", style="bold cyan")
    console.print("=" * 70)
    
    settings = get_settings()
    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    
    try:
        # Get collection info
        info = client.get_collection(settings.qdrant_collection)
        points_before = info.points_count
        console.print(f"\nBefore cleanup:")
        console.print(f"  Points: {points_before}")
        
        # Delete collection
        client.delete_collection(settings.qdrant_collection)
        console.print(f"\n✅ Deleted collection: {settings.qdrant_collection}")
        
        # Verify
        try:
            info_after = client.get_collection(settings.qdrant_collection)
            console.print(f"⚠️  Collection still exists with {info_after.points_count} points")
        except:
            console.print(f"✅ Collection deleted successfully")
    except Exception as e:
        if "doesn't exist" in str(e):
            console.print(f"\n✅ Collection already doesn't exist")
        else:
            console.print(f"\n❌ Error: {e}")
            raise
    
    client.close()

def cleanup_opensearch():
    """Remove all data from OpenSearch."""
    console.print("\n" + "=" * 70)
    console.print("🔎 CLEANING OPENSEARCH", style="bold cyan")
    console.print("=" * 70)
    
    settings = get_settings()
    base_url = f"http://{settings.opensearch_host}:{settings.opensearch_port}"
    
    try:
        # Check if index exists
        response = requests.get(f"{base_url}/{settings.opensearch_index}", timeout=5)
        
        if response.status_code == 200:
            # Get doc count
            count_response = requests.get(f"{base_url}/{settings.opensearch_index}/_count", timeout=5)
            doc_count = count_response.json()['count']
            console.print(f"\nBefore cleanup:")
            console.print(f"  Indexed documents: {doc_count}")
            
            # Delete index
            delete_response = requests.delete(f"{base_url}/{settings.opensearch_index}", timeout=5)
            if delete_response.status_code == 200:
                console.print(f"\n✅ Deleted index: {settings.opensearch_index}")
            else:
                console.print(f"\n❌ Failed to delete index: {delete_response.status_code}")
        else:
            console.print(f"\n✅ Index already doesn't exist")
    
    except Exception as e:
        console.print(f"\n❌ Error: {e}")
        raise

def main():
    console.print("\n" + "=" * 70)
    console.print("🧹 COMPLETE DATABASE CLEANUP", style="bold red")
    console.print("=" * 70)
    
    console.print("\n⚠️  WARNING: This will delete ALL data from:")
    console.print("  • PostgreSQL (legal_documents, document_relationships)")
    console.print("  • Neo4j (all nodes and relationships)")
    console.print("  • Qdrant (entire collection)")
    console.print("  • OpenSearch (entire index)")
    
    # Ask for confirmation
    console.print("\n" + "=" * 70)
    confirm = console.input("Are you sure you want to continue? Type 'YES' to confirm: ")
    
    if confirm != 'YES':
        console.print("\n❌ Cleanup cancelled")
        return
    
    try:
        # Run cleanup for all databases
        asyncio.run(cleanup_postgresql())
        cleanup_neo4j()
        cleanup_qdrant()
        cleanup_opensearch()
        
        console.print("\n" + "=" * 70)
        console.print("✅ CLEANUP COMPLETE - ALL DATABASES ARE NOW EMPTY", style="bold green")
        console.print("=" * 70)
        console.print("\n📋 Next steps:")
        console.print("  1. Run ingest: uv run python scripts/ingest_dataset.py --limit 115")
        console.print("  2. Verify: uv run python scripts/test_data_quality.py")
        console.print("  3. Check stats: uv run python scripts/comprehensive_db_check.py")
        console.print()
        
    except Exception as e:
        console.print(f"\n❌ Cleanup failed: {e}")
        console.print_exception()
        sys.exit(1)

if __name__ == "__main__":
    main()
