"""Synchronization helpers for loading legal documents into Neo4j."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Awaitable, Callable

import asyncpg

from packages.common.config import Settings
from packages.common.types import DocumentType, LegalNode
from packages.graph.legal_graph import LegalGraphClient
from packages.ingestion.parser import (
    AMENDMENT_PATTERN,
    CITATION_PATTERN,
    DOC_NUMBER_PATTERN,
    extract_articles,
    infer_document_type,
    parse_legal_document,
)

logger = logging.getLogger(__name__)


class GraphSyncService:
    """Sync legal documents from PostgreSQL or parser output into Neo4j."""

    def __init__(
        self,
        settings: Settings,
        graph_client: LegalGraphClient | None = None,
        postgres_pool_getter: Callable[[], Awaitable[Any]] | None = None,
    ):
        self.settings = settings
        self.graph_client = graph_client or LegalGraphClient(settings)
        self._postgres_pool = None
        self._postgres_pool_getter = postgres_pool_getter
        self._schema_ready = False

    async def _get_postgres_pool(self):
        """Get a PostgreSQL pool, reusing the app pool when available."""
        if self._postgres_pool_getter is not None:
            return await self._postgres_pool_getter()

        if self._postgres_pool is None:
            self._postgres_pool = await asyncpg.create_pool(
                self.settings.postgres_dsn,
                min_size=1,
                max_size=5,
            )
        return self._postgres_pool

    async def ensure_ready(self) -> None:
        """Ensure Neo4j schema exists before syncing."""
        if self._schema_ready:
            return
        await self.graph_client.ensure_schema()
        self._schema_ready = True

    async def sync_legal_node(self, node: LegalNode) -> dict[str, int]:
        """Sync one parsed legal node tree into Neo4j."""
        await self.ensure_ready()

        stats = {
            "documents": 0,
            "articles": 0,
            "subsections": 0,
            "reference_links": 0,
            "amendment_links": 0,
            "citation_links": 0,
        }

        await self.graph_client.upsert_document(node)
        stats["documents"] += 1

        articles = extract_articles(node.content)
        for article in articles:
            article_number = str(article["number"])
            article_id = f"{node.id}_article_{article_number}"
            article_title = f"Điều {article_number}. {article['title']}".strip(". ")
            article_content = article["content"] or article_title

            await self.graph_client.upsert_article(
                node.id,
                article_id,
                article_number,
                article_title,
                article_content,
            )
            stats["articles"] += 1

            for subsection in article["subsections"]:
                subsection_number = str(subsection["number"])
                subsection_id = f"{article_id}_subsection_{subsection_number}"
                subsection_content = subsection.get("content") or subsection.get("text") or ""
                await self.graph_client.upsert_subsection(
                    article_id,
                    subsection_id,
                    subsection_number,
                    subsection_content,
                )
                stats["subsections"] += 1

            citation_links = await self._sync_article_citations(node.id, article_id, article_content)
            stats["citation_links"] += citation_links
            stats["reference_links"] += citation_links

        root_reference_links = await self._sync_document_references(node)
        stats["reference_links"] += root_reference_links["reference_links"]
        stats["amendment_links"] += root_reference_links["amendment_links"]
        stats["citation_links"] += root_reference_links["citation_links"]

        return stats

    async def sync_existing_documents(self, limit: int | None = None) -> dict[str, Any]:
        """Backfill Neo4j from documents already stored in PostgreSQL."""
        pool = await self._get_postgres_pool()
        query = """
            SELECT id, title, content, metadata
            FROM legal_documents
            ORDER BY created_at ASC
        """
        params: tuple[Any, ...] = ()
        if limit is not None:
            query += " LIMIT $1"
            params = (limit,)

        stats = {
            "documents": 0,
            "articles": 0,
            "subsections": 0,
            "reference_links": 0,
            "amendment_links": 0,
            "citation_links": 0,
            "failed": 0,
        }

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        for row in rows:
            try:
                node = parse_legal_document(row["content"], row["title"])
                node.id = row["id"]
                node.children_ids = [
                    f"{row['id']}_article_{article['number']}"
                    for article in extract_articles(row["content"])
                ]

                metadata_value = row.get("metadata")
                metadata = {}
                if isinstance(metadata_value, str):
                    try:
                        metadata = json.loads(metadata_value)
                    except json.JSONDecodeError:
                        metadata = {}
                elif isinstance(metadata_value, dict):
                    metadata = metadata_value

                if metadata.get("document_number") and not node.document_number:
                    node.document_number = metadata["document_number"]

                result = await self.sync_legal_node(node)
                for key in ("documents", "articles", "subsections", "reference_links", "amendment_links", "citation_links"):
                    stats[key] += result.get(key, 0)
            except Exception as exc:
                stats["failed"] += 1
                logger.error("Failed to sync document %s to Neo4j: %s", row["id"], exc)

        return stats

    async def close(self) -> None:
        """Close only the internal PostgreSQL pool if this service owns it."""
        if self._postgres_pool is not None:
            await self._postgres_pool.close()
            self._postgres_pool = None

    async def _sync_article_citations(
        self,
        source_document_id: str,
        source_article_id: str,
        article_content: str,
    ) -> int:
        """Create citation/reference edges extracted from an article body."""
        link_count = 0
        for match in CITATION_PATTERN.finditer(article_content):
            article_number = match.group(1)
            target_doc_type = self._normalize_doc_type(match.group(2))
            target_year = self._extract_year(match.group(0))

            target_article = await self.graph_client.resolve_article_reference(
                article_number=article_number,
                doc_type=target_doc_type,
                year=target_year,
            )
            if target_article:
                await self.graph_client.create_citation_link(
                    source_article_id,
                    target_article["article_id"],
                )
                await self.graph_client.create_reference_link(
                    source_document_id,
                    target_article["document_id"],
                )
                link_count += 1
                continue

            target_document = await self.graph_client.resolve_document_reference(
                doc_type=target_doc_type,
                year=target_year,
            )
            if target_document and target_document["id"] != source_document_id:
                await self.graph_client.create_citation_link(source_article_id, target_document["id"])
                await self.graph_client.create_reference_link(source_document_id, target_document["id"])
                link_count += 1

        return link_count

    async def _sync_document_references(self, node: LegalNode) -> dict[str, int]:
        """Create document-level reference and amendment edges."""
        stats = {
            "reference_links": 0,
            "amendment_links": 0,
            "citation_links": 0,
        }

        for citation_match in CITATION_PATTERN.finditer(node.content):
            target_doc_type = self._normalize_doc_type(citation_match.group(2))
            target_year = self._extract_year(citation_match.group(0))
            target_document = await self.graph_client.resolve_document_reference(
                doc_type=target_doc_type,
                year=target_year,
            )
            if target_document and target_document["id"] != node.id:
                await self.graph_client.create_reference_link(node.id, target_document["id"])
                await self.graph_client.create_citation_link(node.id, target_document["id"])
                stats["reference_links"] += 1
                stats["citation_links"] += 1

        for amendment_match in AMENDMENT_PATTERN.finditer(node.content):
            target_doc_type = self._normalize_doc_type(amendment_match.group(1))
            ref_text = amendment_match.group(0)
            target_year = self._extract_year(ref_text)
            target_document_number = self._extract_document_number(ref_text)
            target_document = await self.graph_client.resolve_document_reference(
                doc_type=target_doc_type,
                year=target_year,
                document_number=target_document_number,
                reference_text=ref_text,
            )
            if target_document and target_document["id"] != node.id:
                await self.graph_client.create_amendment_link(node.id, target_document["id"])
                stats["amendment_links"] += 1

        return stats

    def _normalize_doc_type(self, label: str | None) -> str | None:
        """Map Vietnamese document labels into internal enum values."""
        if not label:
            return None
        doc_type = infer_document_type(label)
        if isinstance(doc_type, DocumentType):
            return doc_type.value
        return None

    def _extract_year(self, text: str) -> int | None:
        """Extract the first 4-digit year from a reference string."""
        match = re.search(r"(19|20)\d{2}", text)
        if not match:
            return None
        return int(match.group(0))

    def _extract_document_number(self, text: str) -> str | None:
        """Extract a legal document number from a reference string."""
        match = DOC_NUMBER_PATTERN.search(text)
        if not match:
            return None
        return match.group(1)
