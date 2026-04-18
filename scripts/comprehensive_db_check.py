#!/usr/bin/env python3
"""Comprehensive database health check for all 4 databases."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from packages.common.config import get_settings
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

async def check_postgres():
    """Check PostgreSQL health and stats."""
    import asyncpg
    
    settings = get_settings()
    issues = []
    warnings = []
    stats = {}
    
    try:
        pool = await asyncpg.create_pool(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
        )
        
        async with pool.acquire() as conn:
            # Document count
            doc_count = await conn.fetchval("SELECT COUNT(*) FROM legal_documents")
            stats['documents'] = doc_count
            
            # Relationship count
            rel_count = await conn.fetchval("SELECT COUNT(*) FROM document_relationships")
            stats['relationships'] = rel_count
            
            # Check for NULL required fields
            null_titles = await conn.fetchval(
                "SELECT COUNT(*) FROM legal_documents WHERE title IS NULL OR title = ''"
            )
            if null_titles > 0:
                warnings.append(f"{null_titles} documents with NULL/empty title")
            
            null_content = await conn.fetchval(
                "SELECT COUNT(*) FROM legal_documents WHERE content IS NULL OR content = ''"
            )
            if null_content > 0:
                warnings.append(f"{null_content} documents with NULL/empty content")
            
            # Check for duplicate IDs
            dup_ids = await conn.fetchval("""
                SELECT COUNT(*) FROM (
                    SELECT id FROM legal_documents GROUP BY id HAVING COUNT(*) > 1
                ) dups
            """)
            if dup_ids > 0:
                issues.append(f"{dup_ids} duplicate document IDs")
            
            # Orphaned relationships
            orphaned = await conn.fetchval("""
                SELECT COUNT(*) FROM document_relationships dr
                WHERE NOT EXISTS (SELECT 1 FROM legal_documents ld WHERE ld.id = dr.source_doc_id)
                OR NOT EXISTS (SELECT 1 FROM legal_documents ld WHERE ld.id = dr.target_doc_id)
            """)
            if orphaned > 0:
                warnings.append(f"{orphaned} orphaned relationships")
            
            # Documents with relationships
            docs_with_rels = await conn.fetchval("""
                SELECT COUNT(DISTINCT source_doc_id) FROM document_relationships
            """)
            stats['docs_with_relationships'] = docs_with_rels
            
            if doc_count > 0:
                coverage = docs_with_rels / doc_count * 100
                stats['relationship_coverage'] = coverage
        
        await pool.close()
        
        return "✅ Healthy", issues, warnings, stats
        
    except Exception as e:
        return f"❌ Error: {e}", issues, warnings, stats

async def check_qdrant():
    """Check Qdrant health and stats."""
    from qdrant_client import QdrantClient
    
    settings = get_settings()
    issues = []
    warnings = []
    stats = {}
    
    try:
        client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        
        # Collection info
        collection_info = client.get_collection(settings.qdrant_collection)
        total_points = collection_info.points_count
        stats['total_points'] = total_points
        
        # Check vector dimension
        vector_size = collection_info.config.params.vectors.size
        stats['vector_dim'] = vector_size
        
        # Sample check for missing fields
        if total_points > 0:
            records, _ = client.scroll(
                collection_name=settings.qdrant_collection,
                limit=min(100, total_points),
                with_payload=True,
                with_vectors=False,
            )
                        
            missing_content = 0
            missing_doc_id = 0
                            
            for record in records:
                payload = record.payload or {}
                if not payload.get('content'):
                    missing_content += 1
                # Qdrant uses law_id for root docs, parent_doc_id for articles
                # NOT doc_id - so check for EITHER
                law_id = payload.get('law_id')
                parent_doc_id = payload.get('parent_doc_id')
                                
                chunk_type = payload.get('chunk_type', 'unknown')
                if chunk_type == 'article':
                    # Articles should have parent_doc_id
                    if not parent_doc_id:
                        missing_doc_id += 1
                else:
                    # Root docs should have law_id
                    if not law_id:
                        missing_doc_id += 1
            
            if missing_content > 0:
                pct = missing_content / len(records) * 100
                if pct > 10:
                    issues.append(f"{pct:.1f}% of sampled points missing content")
                else:
                    warnings.append(f"{pct:.1f}% of sampled points missing content")
            
            if missing_doc_id > 0:
                pct = missing_doc_id / len(records) * 100
                if pct > 5:
                    issues.append(f"{pct:.1f}% of sampled points missing doc_id")
        
        client.close()
        
        if total_points == 0:
            warnings.append("Collection is empty")
        
        return "✅ Healthy", issues, warnings, stats
        
    except Exception as e:
        return f"❌ Error: {e}", issues, warnings, stats

async def check_neo4j():
    """Check Neo4j health and stats."""
    from neo4j import GraphDatabase
    
    settings = get_settings()
    issues = []
    warnings = []
    stats = {}
    
    try:
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        
        with driver.session() as session:
            # Node counts by type - Note: label is 'Document', not 'LegalDocument'
            legal_docs = session.run("MATCH (n:Document) RETURN count(n) as count").single()["count"]
            articles = session.run("MATCH (n:Article) RETURN count(n) as count").single()["count"]
            subsections = session.run("MATCH (n:Subsection) RETURN count(n) as count").single()["count"]
            total_nodes = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            
            stats['legal_documents'] = legal_docs
            stats['articles'] = articles
            stats['subsections'] = subsections
            stats['total_nodes'] = total_nodes
            
            # Relationship counts
            total_rels = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
            stats['total_relationships'] = total_rels
            
            # Check for duplicates (true duplicates = same source, target, AND type property)
            duplicates = session.run("""
                MATCH (s)-[r]->(t)
                WITH s, type(r) as rel_type, t, r.type as rel_subtype, count(r) as cnt
                WHERE cnt > 1
                RETURN count(*) as dup_groups
            """).single()["dup_groups"]
            
            if duplicates > 0:
                issues.append(f"{duplicates} duplicate relationship groups")
            
            # Check for nodes without required properties - Note: property is 'id', not 'doc_id'
            nodes_without_id = session.run("""
                MATCH (n:Document)
                WHERE n.id IS NULL OR n.id = ''
                RETURN count(n) as count
            """).single()["count"]
            
            if nodes_without_id > 0:
                issues.append(f"{nodes_without_id} Document nodes without id")
            
            # Orphaned nodes (no relationships)
            orphaned_nodes = session.run("""
                MATCH (n)
                WHERE NOT (n)--()
                RETURN count(n) as count
            """).single()["count"]
            
            if orphaned_nodes > 0:
                warnings.append(f"{orphaned_nodes} orphaned nodes (no relationships)")
        
        driver.close()
        
        return "✅ Healthy", issues, warnings, stats
        
    except Exception as e:
        return f"❌ Error: {e}", issues, warnings, stats

async def check_opensearch():
    """Check OpenSearch health and stats."""
    import requests
    
    settings = get_settings()
    issues = []
    warnings = []
    stats = {}
    
    try:
        base_url = f"http://{settings.opensearch_host}:{settings.opensearch_port}"
        
        # Cluster health
        health_response = requests.get(f"{base_url}/_cluster/health", timeout=5)
        if health_response.status_code == 200:
            cluster_status = health_response.json()["status"]
            if cluster_status == "red":
                issues.append("Cluster status is RED")
            elif cluster_status == "yellow":
                warnings.append("Cluster status is YELLOW")
        
        # Index stats
        index_response = requests.get(f"{base_url}/{settings.opensearch_index}/_count", timeout=5)
        if index_response.status_code == 200:
            doc_count = index_response.json()["count"]
            stats['indexed_documents'] = doc_count
            
            if doc_count == 0:
                warnings.append("Index is empty")
        else:
            issues.append(f"Index not found or error: {index_response.status_code}")
        
        return "✅ Healthy", issues, warnings, stats
        
    except requests.exceptions.ConnectionError:
        return "❌ Not reachable", issues, warnings, stats
    except Exception as e:
        return f"❌ Error: {e}", issues, warnings, stats

async def main():
    console.print("\n" + "=" * 70)
    console.print("🔍 COMPREHENSIVE DATABASE HEALTH CHECK", style="bold cyan")
    console.print("=" * 70 + "\n")
    
    # Check all databases
    checks = {
        "PostgreSQL": await check_postgres(),
        "Qdrant": await check_qdrant(),
        "Neo4j": await check_neo4j(),
        "OpenSearch": await check_opensearch(),
    }
    
    # Summary table
    summary = Table(show_header=True, header_style="bold magenta")
    summary.add_column("Database", style="cyan")
    summary.add_column("Status", style="green")
    summary.add_column("Key Metrics", style="yellow")
    
    all_issues = []
    all_warnings = []
    
    for db_name, (status, issues, warnings, stats) in checks.items():
        # Format metrics
        metrics_parts = []
        for key, value in stats.items():
            if isinstance(value, float):
                metrics_parts.append(f"{key}: {value:.1f}%")
            else:
                metrics_parts.append(f"{key}: {value:,}")
        
        metrics_text = ", ".join(metrics_parts) if metrics_parts else "No data"
        
        summary.add_row(db_name, status, metrics_text)
        
        all_issues.extend([(db_name, issue) for issue in issues])
        all_warnings.extend([(db_name, warning) for warning in warnings])
    
    console.print(summary)
    console.print()
    
    # Show issues
    if all_issues:
        console.print("🔴 ISSUES FOUND:", style="bold red")
        for db_name, issue in all_issues:
            console.print(f"  • [{db_name}] {issue}", style="red")
        console.print()
    
    # Show warnings
    if all_warnings:
        console.print("⚠️  WARNINGS:", style="bold yellow")
        for db_name, warning in all_warnings:
            console.print(f"  • [{db_name}] {warning}", style="yellow")
        console.print()
    
    # Overall status
    if not all_issues and not all_warnings:
        console.print("✅ ALL DATABASES HEALTHY - No issues found!", style="bold green")
    elif not all_issues:
        console.print(f"⚠️  {len(all_warnings)} warning(s) found - System operational", style="yellow")
    else:
        console.print(f"🔴 {len(all_issues)} issue(s) found - Action required!", style="bold red")
    
    console.print("\n" + "=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
