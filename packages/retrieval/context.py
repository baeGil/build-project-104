"""Context injection: enrich retrieved documents with parent, sibling, and amendment context."""

import logging
import time
from typing import Optional

from prometheus_client import Histogram

from packages.common.config import Settings
from packages.common.types import ContextDocument, DocumentRelationship, RelationshipType, RetrievedDocument

logger = logging.getLogger(__name__)

CONTEXT_INJECTION_DURATION = Histogram(
    "context_injection_duration_seconds",
    "Context injection latency",
    labelnames=["relation_type"],
)


class ContextInjector:
    """
    Enriches retrieved documents with hierarchical legal context.
    
    Fetches:
    - Parent document (traverse up hierarchy) - 5ms
    - Sibling exceptions (same article, different year) - 10ms  
    - Linked amendments (via graph or metadata) - 10-20ms
    - Related articles (via citation refs) - 20ms
    - Related documents from PostgreSQL (primary) and Neo4j (secondary) - 10-30ms
    
    Target: <50ms total for context injection.
    """
    
    def __init__(self, settings: Settings, graph_client=None, postgres_pool=None):
        self.settings = settings
        self._graph_client = graph_client  # Optional Neo4j
        self._postgres_pool = postgres_pool  # Optional PostgreSQL pool (can be set later)
    
    async def inject_context(
        self,
        retrieved_docs: list[RetrievedDocument],
        top_k: int = 5,
        include_pg_relationships: bool = True,
    ) -> list[ContextDocument]:
        """
        Inject context for top retrieved documents.
        Returns list of ContextDocuments to add to EvidencePack.

        Uses PostgreSQL as PRIMARY source for relationships, with Neo4j as
        secondary for deeper graph traversal when available.

        Args:
            retrieved_docs: List of retrieved documents to enrich
            top_k: Number of top documents to process
            include_pg_relationships: Whether to include PostgreSQL relationships (default: True)
        """
        start_time = time.perf_counter()
        context_docs: list[ContextDocument] = []

        # Process top_k documents
        docs_to_process = retrieved_docs[:top_k]

        for doc in docs_to_process:
            # Fetch parent context (5ms target)
            parent = await self._fetch_parent_context(doc)
            if parent:
                context_docs.append(parent)

            # Fetch sibling exceptions (10ms target)
            siblings = await self._fetch_sibling_exceptions(doc)
            context_docs.extend(siblings)

            # Fetch amendments (10-20ms target)
            amendments = await self._fetch_amendments(doc)
            context_docs.extend(amendments)

            # Fetch related articles (20ms target)
            related = await self._fetch_related_articles(doc)
            context_docs.extend(related)

            # Fetch PostgreSQL relationships (PRIMARY source) - 10-30ms target
            if include_pg_relationships:
                pg_related = await self._fetch_pg_relationships(doc)
                context_docs.extend(pg_related)

        total_time = (time.perf_counter() - start_time) * 1000
        logger.info(f"Context injection completed in {total_time:.2f}ms for {len(docs_to_process)} documents")

        # Deduplicate by doc_id
        seen_ids = set()
        unique_context = []
        for ctx in context_docs:
            if ctx.doc_id not in seen_ids:
                seen_ids.add(ctx.doc_id)
                unique_context.append(ctx)

        return unique_context

    async def _fetch_pg_relationships(
        self, doc: RetrievedDocument
    ) -> list[ContextDocument]:
        """Fetch relationships from PostgreSQL (PRIMARY source).

        Args:
            doc: Document to fetch relationships for

        Returns:
            List of ContextDocument objects for related documents
        """
        start_time = time.perf_counter()
        context_docs: list[ContextDocument] = []

        try:
            # Get related documents from PostgreSQL
            related = await self.get_related_documents_pg(doc.doc_id)

            for rel in related:
                # Map relationship type to relation_type
                rel_type = rel.get("relationship_type", "Văn bản liên quan")
                direction = rel.get("direction", "outgoing")

                # Create context document
                context_docs.append(ContextDocument(
                    doc_id=rel["doc_id"],
                    content=rel.get("content", "")[:500],  # Truncated
                    relation_type=f"pg_{direction}_{rel_type}",
                    title=rel.get("title"),
                ))

            # Also try Neo4j for deeper traversal if available
            if self._graph_client:
                try:
                    graph_rels = await self._graph_client.get_related_by_topic(
                        doc.doc_id, max_hops=2
                    )
                    for rel in graph_rels:
                        rel_id = rel.get("id")
                        # Skip if already added from PostgreSQL
                        if rel_id and not any(c.doc_id == rel_id for c in context_docs):
                            context_docs.append(ContextDocument(
                                doc_id=rel_id,
                                content=rel.get("content", "")[:500],
                                relation_type="graph_related",
                                title=rel.get("title"),
                            ))
                except Exception as e:
                    logger.debug(f"Neo4j graph traversal skipped: {e}")

            duration = time.perf_counter() - start_time
            CONTEXT_INJECTION_DURATION.labels(relation_type="pg_relationships").observe(duration)

            return context_docs

        except Exception as e:
            logger.error(f"Error fetching PostgreSQL relationships: {e}")
            return context_docs
    
    async def _fetch_parent_context(self, doc: RetrievedDocument) -> Optional[ContextDocument]:
        """Fetch parent document in legal hierarchy."""
        start_time = time.perf_counter()
        
        try:
            # Try Neo4j first if available
            if self._graph_client:
                try:
                    parent = await self._graph_client.get_parent_document(doc.doc_id)
                    if parent:
                        duration = time.perf_counter() - start_time
                        CONTEXT_INJECTION_DURATION.labels(relation_type="parent").observe(duration)
                        return ContextDocument(
                            doc_id=parent.get("id", ""),
                            content=parent.get("content", ""),
                            relation_type="parent",
                            title=parent.get("title"),
                        )
                except Exception as e:
                    logger.warning(f"Neo4j parent fetch failed, falling back to metadata: {e}")
            
            # Fallback: use metadata parent_id
            parent_id = doc.metadata.get("parent_id")
            if parent_id:
                # In Phase 1, we return a stub - in production this would query the vector DB
                duration = time.perf_counter() - start_time
                CONTEXT_INJECTION_DURATION.labels(relation_type="parent").observe(duration)
                return ContextDocument(
                    doc_id=parent_id,
                    content=f"Parent document reference: {parent_id}",
                    relation_type="parent",
                    title=doc.metadata.get("parent_title"),
                )
            
            return None
        except Exception as e:
            logger.error(f"Error fetching parent context: {e}")
            return None
    
    async def _fetch_sibling_exceptions(self, doc: RetrievedDocument) -> list[ContextDocument]:
        """Fetch sibling documents (same article, different year/version)."""
        start_time = time.perf_counter()
        siblings: list[ContextDocument] = []
        
        try:
            # Try Neo4j first if available
            if self._graph_client:
                try:
                    # Query for documents with same article number but different versions
                    article_number = doc.metadata.get("article_number")
                    doc_type = doc.metadata.get("doc_type")
                    
                    if article_number and doc_type:
                        related = await self._graph_client.get_related_by_topic(
                            doc.doc_id, max_hops=1
                        )
                        for rel in related:
                            if rel.get("id") != doc.doc_id:
                                siblings.append(ContextDocument(
                                    doc_id=rel.get("id", ""),
                                    content=rel.get("content", ""),
                                    relation_type="sibling",
                                    title=rel.get("title"),
                                ))
                except Exception as e:
                    logger.warning(f"Neo4j sibling fetch failed, falling back to metadata: {e}")
            
            # Fallback: use metadata sibling_refs
            sibling_refs = doc.metadata.get("sibling_refs", [])
            for sibling_id in sibling_refs:
                siblings.append(ContextDocument(
                    doc_id=sibling_id,
                    content=f"Sibling document reference: {sibling_id}",
                    relation_type="sibling",
                ))
            
            duration = time.perf_counter() - start_time
            CONTEXT_INJECTION_DURATION.labels(relation_type="sibling").observe(duration)
            
            return siblings
        except Exception as e:
            logger.error(f"Error fetching sibling context: {e}")
            return siblings
    
    async def _fetch_amendments(self, doc: RetrievedDocument) -> list[ContextDocument]:
        """Fetch linked amendments via metadata or Neo4j graph."""
        start_time = time.perf_counter()
        amendments: list[ContextDocument] = []
        
        try:
            # Try Neo4j first if available
            if self._graph_client:
                try:
                    amendment_chain = await self._graph_client.get_amendments(
                        doc.doc_id, max_depth=2
                    )
                    for amd in amendment_chain:
                        amendments.append(ContextDocument(
                            doc_id=amd.get("id", ""),
                            content=amd.get("content", ""),
                            relation_type="amendment",
                            title=amd.get("title"),
                        ))
                except Exception as e:
                    logger.warning(f"Neo4j amendment fetch failed, falling back to metadata: {e}")
            
            # Fallback: use metadata amendment_refs
            amendment_refs = doc.metadata.get("amendment_refs", [])
            for amd_id in amendment_refs:
                amendments.append(ContextDocument(
                    doc_id=amd_id,
                    content=f"Amendment reference: {amd_id}",
                    relation_type="amendment",
                ))
            
            duration = time.perf_counter() - start_time
            CONTEXT_INJECTION_DURATION.labels(relation_type="amendment").observe(duration)
            
            return amendments
        except Exception as e:
            logger.error(f"Error fetching amendment context: {e}")
            return amendments
    
    async def _fetch_related_articles(self, doc: RetrievedDocument) -> list[ContextDocument]:
        """Fetch related articles via citation references."""
        start_time = time.perf_counter()
        related: list[ContextDocument] = []
        
        try:
            # Try Neo4j first if available
            if self._graph_client:
                try:
                    citing = await self._graph_client.get_citing_articles(doc.doc_id)
                    for cite in citing:
                        related.append(ContextDocument(
                            doc_id=cite.get("id", ""),
                            content=cite.get("content", ""),
                            relation_type="related",
                            title=cite.get("title"),
                        ))
                except Exception as e:
                    logger.warning(f"Neo4j citation fetch failed, falling back to metadata: {e}")
            
            # Fallback: use metadata citation_refs
            citation_refs = doc.metadata.get("citation_refs", [])
            for cite_id in citation_refs:
                related.append(ContextDocument(
                    doc_id=cite_id,
                    content=f"Citation reference: {cite_id}",
                    relation_type="related",
                ))
            
            duration = time.perf_counter() - start_time
            CONTEXT_INJECTION_DURATION.labels(relation_type="related").observe(duration)
            
            return related
        except Exception as e:
            logger.error(f"Error fetching related articles: {e}")
            return related

    async def _get_postgres_pool(self):
        """Get or create async PostgreSQL pool."""
        if self._postgres_pool is None:
            try:
                import asyncpg

                self._postgres_pool = await asyncpg.create_pool(
                    self.settings.postgres_dsn,
                    min_size=2,
                    max_size=10,
                )
                logger.debug("Connected to PostgreSQL for context injection")
            except Exception as e:
                logger.error(f"Failed to connect to PostgreSQL: {e}")
                raise
        return self._postgres_pool

    async def get_related_documents_pg(
        self,
        doc_id: str,
        relationship_types: list[str] | None = None,
    ) -> list[dict]:
        """Fetch related documents from PostgreSQL (PRIMARY source for relationships).

        Queries the document_relationships table for both outgoing and incoming
        relationships, joining with legal_documents to get title and content.

        Args:
            doc_id: Source document ID to find relationships for
            relationship_types: Optional filter by relationship type(s)

        Returns:
            List of dicts with: doc_id, title, content (truncated), relationship_type, direction
        """
        start_time = time.perf_counter()
        results: list[dict] = []

        try:
            pool = await self._get_postgres_pool()

            async with pool.acquire() as conn:
                # Build relationship type filter if provided
                type_filter = ""
                params = [doc_id]
                if relationship_types:
                    type_filter = " AND dr.relationship_type = ANY($2)"
                    params.append(relationship_types)

                # Query outgoing relationships (source -> target)
                outgoing_query = f"""
                    SELECT 
                        dr.target_doc_id as related_doc_id,
                        dr.relationship_type,
                        ld.title,
                        LEFT(ld.content, 500) as content_preview
                    FROM document_relationships dr
                    LEFT JOIN legal_documents ld ON dr.target_doc_id = ld.id
                    WHERE dr.source_doc_id = $1{type_filter}
                """

                rows = await conn.fetch(outgoing_query, *params)
                for row in rows:
                    results.append({
                        "doc_id": row["related_doc_id"],
                        "title": row["title"] or "",
                        "content": row["content_preview"] or "",
                        "relationship_type": row["relationship_type"],
                        "direction": "outgoing",
                    })

                # Query incoming relationships (target <- source)
                incoming_query = f"""
                    SELECT 
                        dr.source_doc_id as related_doc_id,
                        dr.relationship_type,
                        ld.title,
                        LEFT(ld.content, 500) as content_preview
                    FROM document_relationships dr
                    LEFT JOIN legal_documents ld ON dr.source_doc_id = ld.id
                    WHERE dr.target_doc_id = $1{type_filter}
                """

                rows = await conn.fetch(incoming_query, *params)
                for row in rows:
                    results.append({
                        "doc_id": row["related_doc_id"],
                        "title": row["title"] or "",
                        "content": row["content_preview"] or "",
                        "relationship_type": row["relationship_type"],
                        "direction": "incoming",
                    })

            duration = (time.perf_counter() - start_time) * 1000
            logger.debug(
                f"PostgreSQL relationship fetch: {len(results)} docs in {duration:.2f}ms"
            )

            return results

        except Exception as e:
            logger.error(f"Error fetching related documents from PostgreSQL: {e}")
            return []

    async def get_document_relationship_graph(
        self,
        doc_id: str,
        depth: int = 1,
    ) -> dict:
        """Get the relationship graph around a document.

        Depth 1: Direct relationships only (from PostgreSQL)
        Depth 2+: Multi-hop traversal (Neo4j if available, else PostgreSQL self-join)

        Args:
            doc_id: Center document ID
            depth: Graph traversal depth (1-3 recommended)

        Returns:
            Dict with center_doc_id and relationships list
        """
        start_time = time.perf_counter()
        relationships: list[dict] = []
        seen_ids = {doc_id}

        try:
            # Depth 1: Always from PostgreSQL (primary source)
            direct_rels = await self.get_related_documents_pg(doc_id)
            for rel in direct_rels:
                if rel["doc_id"] not in seen_ids:
                    seen_ids.add(rel["doc_id"])
                    relationships.append({
                        "doc_id": rel["doc_id"],
                        "title": rel["title"],
                        "relationship_type": rel["relationship_type"],
                        "direction": rel["direction"],
                        "depth": 1,
                    })

            # Depth 2+: Use Neo4j if available for efficient graph traversal
            if depth >= 2 and self._graph_client:
                try:
                    # Neo4j multi-hop query
                    neo4j_rels = await self._graph_client.get_related_by_topic(
                        doc_id, max_hops=min(depth, 3)
                    )
                    for rel in neo4j_rels:
                        rel_id = rel.get("id")
                        if rel_id and rel_id not in seen_ids:
                            seen_ids.add(rel_id)
                            relationships.append({
                                "doc_id": rel_id,
                                "title": rel.get("title", ""),
                                "relationship_type": rel.get("relationship_type", "Văn bản liên quan"),
                                "direction": "graph",
                                "depth": rel.get("depth", 2),
                            })
                except Exception as e:
                    logger.warning(f"Neo4j graph traversal failed: {e}")
                    # Fallback: PostgreSQL self-join for depth 2
                    if depth >= 2:
                        relationships.extend(
                            await self._get_pg_depth_2_relationships(doc_id, seen_ids)
                        )
            elif depth >= 2:
                # No Neo4j, use PostgreSQL self-join
                relationships.extend(
                    await self._get_pg_depth_2_relationships(doc_id, seen_ids)
                )

            duration = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"Relationship graph built: {len(relationships)} docs "
                f"(depth={depth}) in {duration:.2f}ms"
            )

            return {
                "center_doc_id": doc_id,
                "relationships": relationships,
            }

        except Exception as e:
            logger.error(f"Error building relationship graph: {e}")
            return {"center_doc_id": doc_id, "relationships": []}

    async def _get_pg_depth_2_relationships(
        self, doc_id: str, seen_ids: set[str]
    ) -> list[dict]:
        """Get depth-2 relationships using PostgreSQL self-join.

        Args:
            doc_id: Center document ID
            seen_ids: Set of already-seen document IDs (modified in place)

        Returns:
            List of depth-2 relationship dicts
        """
        results: list[dict] = []

        try:
            pool = await self._get_postgres_pool()

            async with pool.acquire() as conn:
                # Find depth-2 relationships through intermediate documents
                query = """
                    SELECT DISTINCT
                        dr2.target_doc_id as related_doc_id,
                        dr2.relationship_type,
                        ld.title,
                        'outgoing' as direction
                    FROM document_relationships dr1
                    JOIN document_relationships dr2 ON dr1.target_doc_id = dr2.source_doc_id
                    LEFT JOIN legal_documents ld ON dr2.target_doc_id = ld.id
                    WHERE dr1.source_doc_id = $1
                      AND dr2.target_doc_id != $1
                    UNION
                    SELECT DISTINCT
                        dr2.source_doc_id as related_doc_id,
                        dr2.relationship_type,
                        ld.title,
                        'incoming' as direction
                    FROM document_relationships dr1
                    JOIN document_relationships dr2 ON dr1.source_doc_id = dr2.target_doc_id
                    LEFT JOIN legal_documents ld ON dr2.source_doc_id = ld.id
                    WHERE dr1.target_doc_id = $1
                      AND dr2.source_doc_id != $1
                """

                rows = await conn.fetch(query, doc_id)
                for row in rows:
                    if row["related_doc_id"] not in seen_ids:
                        seen_ids.add(row["related_doc_id"])
                        results.append({
                            "doc_id": row["related_doc_id"],
                            "title": row["title"] or "",
                            "relationship_type": row["relationship_type"],
                            "direction": row["direction"],
                            "depth": 2,
                        })

            return results

        except Exception as e:
            logger.error(f"Error fetching depth-2 relationships from PostgreSQL: {e}")
            return []

    async def enrich_with_relationships(
        self,
        doc: RetrievedDocument,
    ) -> RetrievedDocument:
        """Enrich a RetrievedDocument with related documents from PostgreSQL.

        This method populates the related_documents field of a RetrievedDocument.

        Args:
            doc: Document to enrich

        Returns:
            The same document with related_documents populated
        """
        try:
            related = await self.get_related_documents_pg(doc.doc_id)
            doc.related_documents = related
            return doc
        except Exception as e:
            logger.error(f"Error enriching document with relationships: {e}")
            doc.related_documents = []
            return doc
