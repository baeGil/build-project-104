"""Context injection: enrich retrieved documents with parent, sibling, and amendment context."""

import logging
import time
from typing import Optional

from prometheus_client import Histogram

from packages.common.config import Settings
from packages.common.types import ContextDocument, RetrievedDocument

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
    
    Target: <50ms total for context injection.
    """
    
    def __init__(self, settings: Settings, graph_client=None):
        self.settings = settings
        self._graph_client = graph_client  # Optional Neo4j
    
    async def inject_context(
        self,
        retrieved_docs: list[RetrievedDocument],
        top_k: int = 5,
    ) -> list[ContextDocument]:
        """
        Inject context for top retrieved documents.
        Returns list of ContextDocuments to add to EvidencePack.
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
