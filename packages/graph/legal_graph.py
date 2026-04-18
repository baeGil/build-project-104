"""Neo4j graph for legal document relationships."""

import logging
from typing import Any, Optional

from packages.common.config import Settings
from packages.common.types import LegalNode

logger = logging.getLogger(__name__)


class LegalGraphClient:
    """
    Neo4j client for legal document relationship graph.
    
    Graph schema:
    - (:Document {id, title, year, doc_type}) -[:CONTAINS]-> (:Article {id, number, title})
    - (:Article) -[:HAS_SUBSECTION]-> (:Subsection {id, number, content})
    - (:Document) -[:AMENDED_BY]-> (:Document) with {effective_date}
    - (:Document) -[:REFERENCES]-> (:Document)
    - (:Article) -[:CITES]-> (:Article)
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._driver = None  # Lazy init
    
    @property
    def driver(self):
        """Lazy-initialize Neo4j driver."""
        if self._driver is None:
            try:
                from neo4j import AsyncGraphDatabase
                self._driver = AsyncGraphDatabase.driver(
                    self.settings.neo4j_uri,
                    auth=(self.settings.neo4j_user, self.settings.neo4j_password),
                )
                logger.info("Neo4j driver initialized")
            except ImportError:
                logger.error("neo4j package not installed. Install with: pip install neo4j")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize Neo4j driver: {e}")
                raise
        return self._driver
    
    async def close(self):
        """Close driver connection."""
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("Neo4j driver closed")

    async def ping(self) -> bool:
        """Check whether Neo4j is reachable."""
        try:
            async with self.driver.session() as session:
                result = await session.run("RETURN 1 AS ok")
                record = await result.single()
                return bool(record and record["ok"] == 1)
        except Exception as e:
            logger.warning(f"Neo4j ping failed: {e}")
            return False

    async def ensure_schema(self) -> None:
        """Ensure the graph constraints and indexes exist."""
        await self.create_constraints()
        await self.create_indexes()
    
    # --- Schema Management ---
    
    async def create_constraints(self):
        """Create uniqueness constraints and indexes."""
        constraints = [
            "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT article_id IF NOT EXISTS FOR (a:Article) REQUIRE a.id IS UNIQUE",
            "CREATE CONSTRAINT subsection_id IF NOT EXISTS FOR (s:Subsection) REQUIRE s.id IS UNIQUE",
        ]
        
        async with self.driver.session() as session:
            for constraint in constraints:
                try:
                    await session.run(constraint)
                    logger.debug(f"Created constraint: {constraint}")
                except Exception as e:
                    logger.warning(f"Constraint creation failed (may already exist): {e}")
    
    async def create_indexes(self):
        """Create indexes for common query patterns."""
        indexes = [
            "CREATE INDEX document_year IF NOT EXISTS FOR (d:Document) ON (d.year)",
            "CREATE INDEX document_type IF NOT EXISTS FOR (d:Document) ON (d.doc_type)",
            "CREATE INDEX document_law_id IF NOT EXISTS FOR (d:Document) ON (d.law_id)",
            "CREATE INDEX article_number IF NOT EXISTS FOR (a:Article) ON (a.number)",
        ]
        
        async with self.driver.session() as session:
            for index in indexes:
                try:
                    await session.run(index)
                    logger.debug(f"Created index: {index}")
                except Exception as e:
                    logger.warning(f"Index creation failed (may already exist): {e}")
    
    # --- Document Operations ---
    
    async def upsert_document(self, node: LegalNode):
        """Create or update a document node with all metadata."""
        query = """
        MERGE (d:Document {id: $id})
        SET d.title = $title,
            d.content = $content,
            d.doc_type = $doc_type,
            d.year = $year,
            d.publish_date = $publish_date,
            d.effective_date = $effective_date,
            d.expiry_date = $expiry_date,
            d.issuing_body = $issuing_body,
            d.document_number = $document_number,
            d.law_id = $law_id,
            d.level = $level,
            d.keywords = $keywords
        RETURN d.id as id
        """
        
        params = {
            "id": node.id,
            "title": node.title,
            "content": node.content,
            "doc_type": node.doc_type.value if node.doc_type else None,
            "year": node.publish_date.year if node.publish_date else None,
            "publish_date": node.publish_date.isoformat() if node.publish_date else None,
            "effective_date": node.effective_date.isoformat() if node.effective_date else None,
            "expiry_date": node.expiry_date.isoformat() if node.expiry_date else None,
            "issuing_body": node.issuing_body,
            "document_number": node.document_number,
            "law_id": node.law_id,
            "level": node.level,
            "keywords": node.keywords,
        }
        
        async with self.driver.session() as session:
            result = await session.run(query, params)
            record = await result.single()
            logger.debug(f"Upserted document: {record['id'] if record else 'unknown'}")
            return record["id"] if record else None
    
    async def upsert_article(self, doc_id: str, article_id: str, number: int | str, title: str, content: str):
        """Create article node linked to parent document."""
        query = """
        MATCH (d:Document {id: $doc_id})
        MERGE (a:Article {id: $article_id})
        SET a.number = $number,
            a.title = $title,
            a.content = $content
        MERGE (d)-[:CONTAINS]->(a)
        RETURN a.id as id
        """
        
        params = {
            "doc_id": doc_id,
            "article_id": article_id,
            "number": number,
            "title": title,
            "content": content,
        }
        
        async with self.driver.session() as session:
            result = await session.run(query, params)
            record = await result.single()
            logger.debug(f"Upserted article: {record['id'] if record else 'unknown'}")
            return record["id"] if record else None

    async def upsert_subsection(
        self,
        article_id: str,
        subsection_id: str,
        number: int | str,
        content: str,
    ):
        """Create subsection node linked to parent article."""
        query = """
        MATCH (a:Article {id: $article_id})
        MERGE (s:Subsection {id: $subsection_id})
        SET s.number = $number,
            s.content = $content
        MERGE (a)-[:HAS_SUBSECTION]->(s)
        RETURN s.id as id
        """

        params = {
            "article_id": article_id,
            "subsection_id": subsection_id,
            "number": str(number),
            "content": content,
        }

        async with self.driver.session() as session:
            result = await session.run(query, params)
            record = await result.single()
            logger.debug(f"Upserted subsection: {record['id'] if record else 'unknown'}")
            return record["id"] if record else None
    
    async def create_amendment_link(self, source_id: str, target_id: str, effective_date: str = None):
        """Create AMENDED_BY relationship."""
        query = """
        MATCH (source:Document {id: $source_id})
        MATCH (target:Document {id: $target_id})
        MERGE (source)-[r:AMENDED_BY]->(target)
        SET r.effective_date = $effective_date
        RETURN r
        """
        
        params = {
            "source_id": source_id,
            "target_id": target_id,
            "effective_date": effective_date,
        }
        
        async with self.driver.session() as session:
            result = await session.run(query, params)
            record = await result.single()
            logger.debug(f"Created amendment link: {source_id} -> {target_id}")
            return record is not None
    
    async def create_citation_link(self, source_id: str, target_id: str):
        """Create CITES relationship."""
        query = """
        MATCH (source {id: $source_id})
        MATCH (target {id: $target_id})
        MERGE (source)-[r:CITES]->(target)
        RETURN r
        """
        
        params = {
            "source_id": source_id,
            "target_id": target_id,
        }
        
        async with self.driver.session() as session:
            result = await session.run(query, params)
            record = await result.single()
            logger.debug(f"Created citation link: {source_id} -> {target_id}")
            return record is not None
    
    async def create_reference_link(self, source_id: str, target_id: str):
        """Create REFERENCES relationship."""
        query = """
        MATCH (source:Document {id: $source_id})
        MATCH (target:Document {id: $target_id})
        MERGE (source)-[r:REFERENCES]->(target)
        RETURN r
        """
        
        params = {
            "source_id": source_id,
            "target_id": target_id,
        }
        
        async with self.driver.session() as session:
            result = await session.run(query, params)
            record = await result.single()
            logger.debug(f"Created reference link: {source_id} -> {target_id}")
            return record is not None
    
    # --- Query Operations ---
    
    async def get_parent_document(self, article_id: str) -> Optional[dict]:
        """Get parent document of an article."""
        query = """
        MATCH (d:Document)-[:CONTAINS]->(a:Article {id: $article_id})
        RETURN d.id as id, d.title as title, d.content as content, d.doc_type as doc_type
        """
        
        async with self.driver.session() as session:
            result = await session.run(query, {"article_id": article_id})
            record = await result.single()
            if record:
                return {
                    "id": record["id"],
                    "title": record["title"],
                    "content": record["content"],
                    "doc_type": record["doc_type"],
                }
            return None
    
    async def get_amendments(self, doc_id: str, max_depth: int = 2) -> list[dict]:
        """Get amendment chain for a document (up to max_depth hops)."""
        # Neo4j doesn't allow parameters in variable-length relationships, so we use string formatting
        # But we sanitize max_depth to prevent injection
        if not isinstance(max_depth, int) or max_depth < 1 or max_depth > 10:
            max_depth = 2  # Safe default
        
        # Include RELATES_TO with amendment-type values from the dataset
        # (dataset stores all rels as RELATES_TO {type: '<Vietnamese name>'})
        query = f"""
        MATCH path = (d:Document {{id: $doc_id}})-
            [:AMENDED_BY|RELATES_TO*1..{max_depth}]->(amendment:Document)
        WHERE amendment.id <> $doc_id
          AND (
            last(relationships(path)).type IS NULL OR
            last(relationships(path)).type IN [
                'V\u0103n b\u1ea3n \u0111\u01b0\u1ee3c s\u1eeda \u0111\u1ed5i',
                'V\u0103n b\u1ea3n s\u1eeda \u0111\u1ed5i',
                'AMENDED_BY'
            ]
          )
        RETURN amendment.id as id,
               amendment.title as title,
               amendment.content as content,
               amendment.year as year,
               length(path) as depth
        ORDER BY depth
        """
        
        async with self.driver.session() as session:
            result = await session.run(query, {"doc_id": doc_id})
            amendments = []
            async for record in result:
                amendments.append({
                    "id": record["id"],
                    "title": record["title"],
                    "content": record["content"],
                    "year": record["year"],
                    "depth": record["depth"],
                })
            return amendments
    
    async def get_citing_articles(self, article_id: str) -> list[dict]:
        """Get nodes that cite or reference this node."""
        query = """
        MATCH (citing)-[:CITES|REFERENCES]->(target {id: $article_id})
        RETURN citing.id as id,
               citing.title as title,
               citing.content as content
        LIMIT 10
        """
        
        async with self.driver.session() as session:
            result = await session.run(query, {"article_id": article_id})
            articles = []
            async for record in result:
                articles.append({
                    "id": record["id"],
                    "title": record["title"],
                    "content": record["content"],
                })
            return articles

    async def resolve_document_reference(
        self,
        doc_type: str | None = None,
        year: int | None = None,
        document_number: str | None = None,
        reference_text: str | None = None,
    ) -> Optional[dict[str, Any]]:
        """Resolve a best-effort document reference to an existing graph node."""
        query = """
        MATCH (d:Document)
        WHERE ($doc_type IS NULL OR d.doc_type = $doc_type)
          AND ($year IS NULL OR d.year = $year)
          AND (
            $document_number IS NULL
            OR d.document_number = $document_number
            OR d.document_number CONTAINS $document_number
          )
          AND (
            $reference_text IS NULL
            OR toLower(d.title) CONTAINS toLower($reference_text)
          )
        RETURN d.id as id,
               d.title as title,
               d.document_number as document_number,
               d.year as year,
               d.doc_type as doc_type
        ORDER BY
          CASE
            WHEN $document_number IS NOT NULL AND d.document_number = $document_number THEN 0
            ELSE 1
          END,
          CASE
            WHEN $year IS NOT NULL AND d.year = $year THEN 0
            ELSE 1
          END
        LIMIT 1
        """

        async with self.driver.session() as session:
            result = await session.run(
                query,
                {
                    "doc_type": doc_type,
                    "year": year,
                    "document_number": document_number,
                    "reference_text": reference_text,
                },
            )
            record = await result.single()
            if not record:
                return None
            return {
                "id": record["id"],
                "title": record["title"],
                "document_number": record["document_number"],
                "year": record["year"],
                "doc_type": record["doc_type"],
            }

    async def resolve_article_reference(
        self,
        article_number: str,
        doc_type: str | None = None,
        year: int | None = None,
        document_number: str | None = None,
    ) -> Optional[dict[str, Any]]:
        """Resolve an article reference by article number and optional document filters."""
        query = """
        MATCH (d:Document)-[:CONTAINS]->(a:Article)
        WHERE a.number = $article_number
          AND ($doc_type IS NULL OR d.doc_type = $doc_type)
          AND ($year IS NULL OR d.year = $year)
          AND (
            $document_number IS NULL
            OR d.document_number = $document_number
            OR d.document_number CONTAINS $document_number
          )
        RETURN a.id as article_id,
               a.title as article_title,
               d.id as document_id,
               d.title as document_title
        LIMIT 1
        """

        async with self.driver.session() as session:
            result = await session.run(
                query,
                {
                    "article_number": str(article_number),
                    "doc_type": doc_type,
                    "year": year,
                    "document_number": document_number,
                },
            )
            record = await result.single()
            if not record:
                return None
            return {
                "article_id": record["article_id"],
                "article_title": record["article_title"],
                "document_id": record["document_id"],
                "document_title": record["document_title"],
            }
    
    async def get_related_by_topic(self, doc_id: str, max_hops: int = 2) -> list[dict]:
        """Multi-hop graph traversal for related documents."""
        # Neo4j doesn't allow parameters in variable-length relationships
        if not isinstance(max_hops, int) or max_hops < 1 or max_hops > 10:
            max_hops = 2
        
        # RELATES_TO covers all dataset relationships; also support typed ones
        query = f"""
        MATCH path = (d:Document {{id: $doc_id}})-[:REFERENCES|CITES|RELATES_TO*1..{max_hops}]-(related:Document)
        WHERE related.id <> $doc_id
        RETURN related.id as id,
               related.title as title,
               related.content as content,
               related.doc_type as doc_type,
               min(length(path)) as distance
        ORDER BY distance
        LIMIT 10
        """
        
        async with self.driver.session() as session:
            result = await session.run(query, {"doc_id": doc_id})
            documents = []
            async for record in result:
                documents.append({
                    "id": record["id"],
                    "title": record["title"],
                    "content": record["content"],
                    "doc_type": record["doc_type"],
                    "distance": record["distance"],
                })
            return documents
    
    async def get_document_hierarchy(self, doc_id: str) -> dict:
        """Get full hierarchy: document -> articles -> subsections."""
        # Step 1: Get document and articles
        query_doc = """
        MATCH (d:Document {id: $doc_id})
        OPTIONAL MATCH (d)-[:CONTAINS]->(a:Article)
        RETURN d.id as doc_id,
               d.title as doc_title,
               collect(DISTINCT {id: a.id, number: a.number, title: a.title}) as articles
        """
        
        async with self.driver.session() as session:
            result = await session.run(query_doc, {"doc_id": doc_id})
            record = await result.single()
            
            if not record:
                return {"id": doc_id, "title": None, "articles": []}
            
            doc_id_result = record["doc_id"]
            doc_title = record["doc_title"]
            articles = record["articles"]
            
            # Step 2: Get subsections for each article
            articles_with_subsections = []
            for article in articles:
                if article.get("id"):  # Skip null articles from OPTIONAL MATCH
                    query_sub = """
                    MATCH (a:Article {id: $article_id})
                    OPTIONAL MATCH (a)-[:HAS_SUBSECTION]->(s:Subsection)
                    RETURN collect(DISTINCT {id: s.id, number: s.number, content: s.content}) as subsections
                    """
                    sub_result = await session.run(query_sub, {"article_id": article["id"]})
                    sub_record = await sub_result.single()
                    
                    article_data = {
                        "id": article["id"],
                        "number": article["number"],
                        "title": article["title"],
                        "subsections": sub_record["subsections"] if sub_record else []
                    }
                    articles_with_subsections.append(article_data)
            
            return {
                "id": doc_id_result,
                "title": doc_title,
                "articles": articles_with_subsections,
            }
    
    # --- GraphRAG for Multi-hop Queries ---
    
    async def graph_augmented_search(
        self,
        seed_doc_ids: list[str],
        max_hops: int = 2,
        max_results: int = 10,
    ) -> list[dict]:
        """
        GraphRAG: expand from seed documents through graph relationships.
        
        1. Start from seed doc IDs (from hybrid retrieval)
        2. Traverse AMENDED_BY, CITES, REFERENCES edges
        3. Collect expanded set of related documents
        4. Return for reranking
        """
        # Neo4j doesn't allow parameters in variable-length relationships
        if not isinstance(max_hops, int) or max_hops < 1 or max_hops > 10:
            max_hops = 2
        
        # RELATES_TO is the type used when ingesting from the dataset;
        # also include domain-specific typed relationships for completeness
        query = f"""
        UNWIND $seed_ids as seed_id
        MATCH (seed {{id: seed_id}})
        OPTIONAL MATCH path = (seed)-[:AMENDED_BY|CITES|REFERENCES|RELATES_TO*1..{max_hops}]-(related)
        WHERE related.id <> seed_id AND NOT related.id IN $seed_ids
        WITH related, min(length(path)) as distance, count(DISTINCT seed_id) as seed_count
        RETURN related.id as id,
               related.title as title,
               related.content as content,
               related.doc_type as doc_type,
               distance,
               seed_count
        ORDER BY seed_count DESC, distance ASC
        LIMIT $max_results
        """
        
        async with self.driver.session() as session:
            result = await session.run(
                query,
                {
                    "seed_ids": seed_doc_ids,
                    "max_results": max_results,
                }
            )
            documents = []
            async for record in result:
                documents.append({
                    "id": record["id"],
                    "title": record["title"],
                    "content": record["content"],
                    "doc_type": record["doc_type"],
                    "distance": record["distance"],
                    "seed_count": record["seed_count"],
                })
            return documents
