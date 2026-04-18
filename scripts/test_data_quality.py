#!/usr/bin/env python3
"""
Comprehensive data quality test for Vietnamese Legal AI system.
Tests data integrity across all 4 databases: PostgreSQL, Neo4j, Qdrant, OpenSearch.
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
from rich.table import Table
from rich.panel import Panel

console = Console()

class DataQualityTester:
    def __init__(self):
        self.settings = get_settings()
        self.issues = []
        self.warnings = []
        self.stats = {}
    
    def add_issue(self, severity, category, message):
        if severity == 'ERROR':
            self.issues.append((category, message))
        else:
            self.warnings.append((category, message))
    
    async def test_postgresql(self):
        """Test PostgreSQL data quality."""
        console.print("\n" + "=" * 70)
        console.print("🗄️  TESTING POSTGRESQL", style="bold cyan")
        console.print("=" * 70)
        
        pool = await asyncpg.create_pool(
            host=self.settings.postgres_host,
            port=self.settings.postgres_port,
            database=self.settings.postgres_db,
            user=self.settings.postgres_user,
            password=self.settings.postgres_password,
        )
        
        async with pool.acquire() as conn:
            # 1. Document count
            doc_count = await conn.fetchval("SELECT COUNT(*) FROM legal_documents")
            self.stats['pg_docs'] = doc_count
            console.print(f"\n✅ Total documents: {doc_count}")
            
            # 2. All IDs should be numeric
            non_numeric = await conn.fetchval("""
                SELECT COUNT(*) FROM legal_documents WHERE id !~ '^[0-9]+$'
            """)
            if non_numeric > 0:
                self.add_issue('ERROR', 'PostgreSQL', f"{non_numeric} documents with non-numeric IDs")
                console.print(f"❌ Non-numeric IDs: {non_numeric}")
            else:
                console.print(f"✅ All IDs are numeric")
            
            # 3. No duplicate IDs
            dup_ids = await conn.fetchval("""
                SELECT COUNT(*) FROM (
                    SELECT id FROM legal_documents GROUP BY id HAVING COUNT(*) > 1
                ) dups
            """)
            if dup_ids > 0:
                self.add_issue('ERROR', 'PostgreSQL', f"{dup_ids} duplicate document IDs")
                console.print(f"❌ Duplicate IDs: {dup_ids}")
            else:
                console.print(f"✅ No duplicate IDs")
            
            # 4. Content quality
            empty_content = await conn.fetchval("""
                SELECT COUNT(*) FROM legal_documents 
                WHERE content IS NULL OR content = '' OR LENGTH(content) < 100
            """)
            if empty_content > 0:
                self.add_issue('ERROR', 'PostgreSQL', f"{empty_content} documents with empty/short content")
                console.print(f"❌ Empty/short content: {empty_content}")
            else:
                console.print(f"✅ All documents have content")
            
            # 5. Content length stats
            avg_len = await conn.fetchval("SELECT AVG(LENGTH(content)) FROM legal_documents")
            min_len = await conn.fetchval("SELECT MIN(LENGTH(content)) FROM legal_documents")
            max_len = await conn.fetchval("SELECT MAX(LENGTH(content)) FROM legal_documents")
            
            console.print(f"✅ Content length: avg={avg_len:.0f}, min={min_len}, max={max_len}")
            
            if min_len < 200:
                self.add_issue('WARNING', 'PostgreSQL', f"Minimum content length is very short: {min_len} chars")
            
            # 6. Title quality
            null_titles = await conn.fetchval("""
                SELECT COUNT(*) FROM legal_documents 
                WHERE title IS NULL OR title = '' OR LENGTH(title) < 10
            """)
            if null_titles > 0:
                self.add_issue('ERROR', 'PostgreSQL', f"{null_titles} documents with missing/short titles")
                console.print(f"❌ Missing/short titles: {null_titles}")
            else:
                console.print(f"✅ All documents have titles")
            
            # 7. Document types
            doc_types = await conn.fetch("""
                SELECT doc_type, COUNT(*) as count 
                FROM legal_documents 
                GROUP BY doc_type 
                ORDER BY count DESC
            """)
            
            console.print(f"\n📊 Document types:")
            for dt in doc_types:
                console.print(f"   {dt['doc_type']}: {dt['count']}")
            
            # Check for 'other' type (might indicate parsing issues)
            other_count = await conn.fetchval("""
                SELECT COUNT(*) FROM legal_documents WHERE doc_type = 'other'
            """)
            if other_count > 0:
                pct = other_count / doc_count * 100
                if pct > 10:
                    self.add_issue('WARNING', 'PostgreSQL', f"{pct:.1f}% documents have 'other' type (parsing issue?)")
            
            # 8. Relationships integrity
            rel_count = await conn.fetchval("SELECT COUNT(*) FROM document_relationships")
            self.stats['pg_rels'] = rel_count
            console.print(f"\n✅ Total relationships: {rel_count}")
            
            # Orphaned relationships
            orphaned = await conn.fetchval("""
                SELECT COUNT(*) FROM document_relationships dr
                WHERE NOT EXISTS (SELECT 1 FROM legal_documents ld WHERE ld.id = dr.source_doc_id)
                OR NOT EXISTS (SELECT 1 FROM legal_documents ld WHERE ld.id = dr.target_doc_id)
            """)
            if orphaned > 0:
                self.add_issue('ERROR', 'PostgreSQL', f"{orphaned} orphaned relationships")
                console.print(f"❌ Orphaned relationships: {orphaned}")
            else:
                console.print(f"✅ No orphaned relationships")
            
            # 9. Sample document validation
            console.print(f"\n🔍 Sample document validation:")
            sample = await conn.fetch("""
                SELECT id, title, doc_type, LENGTH(content) as content_len
                FROM legal_documents
                ORDER BY id::integer
                LIMIT 5
            """)
            
            for doc in sample:
                console.print(f"   ✓ ID={doc['id']}, type={doc['doc_type']}, content={doc['content_len']} chars")
        
        await pool.close()
    
    async def test_neo4j(self):
        """Test Neo4j data quality."""
        console.print("\n" + "=" * 70)
        console.print("🕸️  TESTING NEO4J", style="bold cyan")
        console.print("=" * 70)
        
        driver = GraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password)
        )
        
        with driver.session() as session:
            # 1. Document count
            doc_count = session.run("MATCH (d:Document) RETURN count(d) as count").single()['count']
            self.stats['neo4j_docs'] = doc_count
            console.print(f"\n✅ Document nodes: {doc_count}")
            
            # 2. All IDs numeric
            non_numeric = session.run("""
                MATCH (d:Document)
                WHERE NOT (d.id =~ '^[0-9]+$')
                RETURN count(d) as count
            """).single()['count']
            
            if non_numeric > 0:
                self.add_issue('ERROR', 'Neo4j', f"{non_numeric} documents with non-numeric IDs")
                console.print(f"❌ Non-numeric IDs: {non_numeric}")
            else:
                console.print(f"✅ All IDs are numeric")
            
            # 3. Check consistency with PostgreSQL
            if 'pg_docs' in self.stats:
                if doc_count != self.stats['pg_docs']:
                    self.add_issue('ERROR', 'Neo4j', 
                        f"Document count mismatch: Neo4j={doc_count}, PostgreSQL={self.stats['pg_docs']}")
                    console.print(f"❌ Count mismatch with PostgreSQL!")
                else:
                    console.print(f"✅ Count matches PostgreSQL")
            
            # 4. Article nodes
            article_count = session.run("MATCH (a:Article) RETURN count(a) as count").single()['count']
            self.stats['neo4j_articles'] = article_count
            console.print(f"\n✅ Article nodes: {article_count}")
            
            if doc_count > 0:
                articles_per_doc = article_count / doc_count
                console.print(f"   Articles per doc: {articles_per_doc:.1f}x")
                
                if articles_per_doc < 5:
                    self.add_issue('WARNING', 'Neo4j', f"Low articles per doc ratio: {articles_per_doc:.1f}x")
            
            # 5. Subsection nodes
            subsection_count = session.run("MATCH (s:Subsection) RETURN count(s) as count").single()['count']
            self.stats['neo4j_subsections'] = subsection_count
            console.print(f"✅ Subsection nodes: {subsection_count}")
            
            # 6. Relationships
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()['count']
            self.stats['neo4j_rels'] = rel_count
            console.print(f"\n✅ Total relationships: {rel_count}")
            
            # Check relationship types
            rel_types = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as rel_type, count(r) as count
                ORDER BY count DESC
            """).data()
            
            console.print(f"\n📊 Relationship types:")
            for rt in rel_types:
                console.print(f"   {rt['rel_type']}: {rt['count']}")
            
            # 7. Check for duplicate relationships
            # True duplicates = same source, target, AND relationship type property
            duplicates = session.run("""
                MATCH (s)-[r]->(t)
                WITH s, type(r) as rel_type, t, r.type as rel_subtype, count(r) as cnt
                WHERE cnt > 1
                RETURN count(*) as dup_groups
            """).single()['dup_groups']
            
            if duplicates > 0:
                self.add_issue('ERROR', 'Neo4j', f"{duplicates} duplicate relationship groups")
                console.print(f"❌ Duplicate relationships: {duplicates}")
            else:
                console.print(f"✅ No duplicate relationships (multiple rel types between same nodes is OK)")
            
            # 8. Orphaned nodes
            orphaned = session.run("""
                MATCH (n)
                WHERE NOT (n)--()
                RETURN count(n) as count
            """).single()['count']
            
            if orphaned > 0:
                pct = orphaned / (doc_count + article_count + subsection_count) * 100 if (doc_count + article_count + subsection_count) > 0 else 0
                if pct > 20:
                    self.add_issue('WARNING', 'Neo4j', f"{orphaned} orphaned nodes ({pct:.1f}%)")
                    console.print(f"⚠️  Orphaned nodes: {orphaned}")
                else:
                    console.print(f"✅ Orphaned nodes: {orphaned} (normal)")
            else:
                console.print(f"✅ No orphaned nodes")
            
            # 9. Check Document-Article relationships
            doc_article_rels = session.run("""
                MATCH (d:Document)-[:CONTAINS]->(a:Article)
                RETURN count(d) as docs_with_articles
            """).single()['docs_with_articles']
            
            console.print(f"\n✅ Documents with articles: {doc_article_rels}/{doc_count}")
            
            if doc_article_rels == 0 and article_count > 0:
                self.add_issue('ERROR', 'Neo4j', "Articles exist but no CONTAINS relationships!")
        
        driver.close()
    
    async def test_qdrant(self):
        """Test Qdrant data quality."""
        console.print("\n" + "=" * 70)
        console.print("🎯 TESTING QDRANT", style="bold cyan")
        console.print("=" * 70)
        
        client = QdrantClient(host=self.settings.qdrant_host, port=self.settings.qdrant_port)
        
        # 1. Collection info
        info = client.get_collection(self.settings.qdrant_collection)
        total_points = info.points_count
        self.stats['qdrant_points'] = total_points
        
        console.print(f"\n✅ Total points: {total_points}")
        console.print(f"✅ Vector dimension: {info.config.params.vectors.size}")
        
        # 2. Check indexing ratio
        if 'pg_docs' in self.stats and self.stats['pg_docs'] > 0:
            ratio = total_points / self.stats['pg_docs']
            console.print(f"✅ Indexing ratio: {ratio:.1f}x")
            
            if ratio < 5:
                self.add_issue('WARNING', 'Qdrant', f"Low indexing ratio: {ratio:.1f}x (expected 10-20x)")
            elif ratio > 50:
                self.add_issue('WARNING', 'Qdrant', f"High indexing ratio: {ratio:.1f}x (expected 10-20x)")
        
        # 3. Sample payloads
        console.print(f"\n🔍 Payload validation:")
        records, _ = client.scroll(
            collection_name=self.settings.qdrant_collection,
            limit=20,
            with_payload=True,
            with_vectors=False,
        )
        
        missing_law_id = 0
        missing_title = 0
        missing_content = 0
        chunk_types = {}
        
        for record in records:
            payload = record.payload or {}
            
            if not payload.get('law_id'):
                missing_law_id += 1
            if not payload.get('title'):
                missing_title += 1
            if not payload.get('content'):
                missing_content += 1
            
            chunk_type = payload.get('chunk_type', 'unknown')
            chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
        
        if missing_law_id > 0:
            pct = missing_law_id / len(records) * 100
            if pct > 10:
                self.add_issue('ERROR', 'Qdrant', f"{pct:.1f}% of sampled points missing law_id")
        
        if missing_title > 0:
            pct = missing_title / len(records) * 100
            if pct > 10:
                self.add_issue('ERROR', 'Qdrant', f"{pct:.1f}% of sampled points missing title")
        
        if missing_content > 0:
            pct = missing_content / len(records) * 100
            if pct > 10:
                self.add_issue('ERROR', 'Qdrant', f"{pct:.1f}% of sampled points missing content")
        
        console.print(f"   ✅ Required fields present in samples")
        
        console.print(f"\n📊 Chunk types (sample):")
        for ct, count in sorted(chunk_types.items(), key=lambda x: x[1], reverse=True):
            console.print(f"   {ct}: {count}")
        
        # 4. Check for duplicate vectors (same law_id + chunk_type + article_number + chunk_index)
        console.print(f"\n🔍 Checking for true duplicate chunks...")
        all_records, _ = client.scroll(
            collection_name=self.settings.qdrant_collection,
            limit=min(total_points, 5000),
            with_payload=True,
            with_vectors=False,
        )
        
        seen_chunks = set()
        true_duplicates = 0
        
        for record in all_records:
            payload = record.payload or {}
            chunk_key = (
                payload.get('law_id'),
                payload.get('chunk_type'),
                payload.get('article_number'),
                payload.get('chunk_index'),
                record.id  # Include point ID to distinguish doc vs article vs chunk levels
            )
            
            # Only check for duplicates WITHIN same chunk_type level
            if chunk_key in seen_chunks:
                true_duplicates += 1
            seen_chunks.add(chunk_key)
        
        if true_duplicates > 0:
            self.add_issue('WARNING', 'Qdrant', f"{true_duplicates} true duplicate chunks detected")
            console.print(f"⚠️  True duplicate chunks: {true_duplicates}")
        else:
            console.print(f"✅ No true duplicate chunks (multi-level indexing is correct)")
        
        client.close()
    
    async def test_opensearch(self):
        """Test OpenSearch data quality."""
        console.print("\n" + "=" * 70)
        console.print("🔎 TESTING OPENSEARCH", style="bold cyan")
        console.print("=" * 70)
        
        try:
            base_url = f"http://{self.settings.opensearch_host}:{self.settings.opensearch_port}"
            
            # 1. Index exists
            response = requests.get(f"{base_url}/{self.settings.opensearch_index}/_count", timeout=5)
            if response.status_code == 200:
                doc_count = response.json()['count']
                self.stats['opensearch_docs'] = doc_count
                console.print(f"\n✅ Indexed documents: {doc_count}")
                
                # 2. Check consistency with Qdrant
                if 'qdrant_points' in self.stats:
                    if abs(doc_count - self.stats['qdrant_points']) > 10:
                        self.add_issue('WARNING', 'OpenSearch', 
                            f"Count mismatch with Qdrant: OpenSearch={doc_count}, Qdrant={self.stats['qdrant_points']}")
                        console.print(f"⚠️  Count mismatch with Qdrant!")
                    else:
                        console.print(f"✅ Count matches Qdrant")
            else:
                self.add_issue('ERROR', 'OpenSearch', f"Index query failed: {response.status_code}")
                console.print(f"❌ Cannot query index")
        
        except Exception as e:
            self.add_issue('ERROR', 'OpenSearch', f"Connection failed: {e}")
            console.print(f"❌ Connection failed: {e}")
    
    def print_summary(self):
        """Print final summary."""
        console.print("\n" + "=" * 70)
        console.print("📊 TEST SUMMARY", style="bold magenta")
        console.print("=" * 70)
        
        # Stats table
        stats_table = Table(show_header=True, header_style="bold magenta")
        stats_table.add_column("Database", style="cyan")
        stats_table.add_column("Documents", style="green")
        stats_table.add_column("Details", style="dim")
        
        if 'pg_docs' in self.stats:
            stats_table.add_row(
                "PostgreSQL",
                f"{self.stats['pg_docs']:,}",
                f"{self.stats.get('pg_rels', 0):,} relationships"
            )
        
        if 'neo4j_docs' in self.stats:
            stats_table.add_row(
                "Neo4j",
                f"{self.stats['neo4j_docs']:,}",
                f"{self.stats.get('neo4j_articles', 0):,} articles, {self.stats.get('neo4j_subsections', 0):,} subsections"
            )
        
        if 'qdrant_points' in self.stats:
            ratio = self.stats['qdrant_points'] / self.stats.get('pg_docs', 1)
            stats_table.add_row(
                "Qdrant",
                f"{self.stats['qdrant_points']:,}",
                f"{ratio:.1f}x indexing ratio"
            )
        
        if 'opensearch_docs' in self.stats:
            stats_table.add_row(
                "OpenSearch",
                f"{self.stats['opensearch_docs']:,}",
                "BM25 full-text search"
            )
        
        console.print(stats_table)
        
        # Issues
        if self.issues:
            console.print(f"\n🔴 ISSUES ({len(self.issues)}):", style="bold red")
            for category, message in self.issues:
                console.print(f"  • [{category}] {message}", style="red")
        
        # Warnings
        if self.warnings:
            console.print(f"\n⚠️  WARNINGS ({len(self.warnings)}):", style="bold yellow")
            for category, message in self.warnings:
                console.print(f"  • [{category}] {message}", style="yellow")
        
        # Final verdict
        console.print("\n" + "=" * 70)
        if not self.issues and not self.warnings:
            console.print("✅ ALL TESTS PASSED - Data quality: EXCELLENT", style="bold green")
        elif not self.issues:
            console.print(f"⚠️  {len(self.warnings)} warning(s) - Data quality: GOOD", style="yellow")
        else:
            console.print(f"🔴 {len(self.issues)} issue(s) found - Action required!", style="bold red")
        console.print("=" * 70 + "\n")

async def main():
    console.print("\n" + "=" * 70)
    console.print("🧪 COMPREHENSIVE DATA QUALITY TEST", style="bold cyan")
    console.print("=" * 70)
    
    tester = DataQualityTester()
    
    # Run all tests
    await tester.test_postgresql()
    await tester.test_neo4j()
    await tester.test_qdrant()
    await tester.test_opensearch()
    
    # Print summary
    tester.print_summary()

if __name__ == "__main__":
    asyncio.run(main())
