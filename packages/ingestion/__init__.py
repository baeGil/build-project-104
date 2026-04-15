"""Document ingestion pipeline for Vietnamese legal documents.

This package provides tools for parsing, normalizing, and indexing
Vietnamese legal documents into vector and full-text search backends.

Example usage:
    from packages.ingestion import IngestionPipeline, parse_legal_document
    
    pipeline = IngestionPipeline()
    result = await pipeline.ingest_single_document("Title", "Content...")
"""

from packages.ingestion.indexer import (
    DocumentIndexer,
    OpenSearchIndexer,
    QdrantIndexer,
)
from packages.ingestion.normalizer import (
    LEGAL_ABBREVIATIONS,
    TextNormalizer,
    detect_missing_diacritics,
    expand_abbreviations,
    normalize_date_format,
    normalize_legal_text,
    normalize_unicode,
    normalize_whitespace,
)
from packages.ingestion.parser import (
    DocumentParser,
    extract_amendment_refs,
    extract_articles,
    extract_citation_refs,
    extract_metadata,
    infer_document_type,
    parse_legal_document,
)
__all__ = [
    # Parser
    "DocumentParser",
    "parse_legal_document",
    "extract_metadata",
    "extract_articles",
    "extract_amendment_refs",
    "extract_citation_refs",
    "infer_document_type",
    # Normalizer
    "TextNormalizer",
    "normalize_legal_text",
    "normalize_unicode",
    "normalize_whitespace",
    "expand_abbreviations",
    "detect_missing_diacritics",
    "normalize_date_format",
    "LEGAL_ABBREVIATIONS",
    # Indexer
    "DocumentIndexer",
    "QdrantIndexer",
    "OpenSearchIndexer",
    # Pipeline
    "IngestionPipeline",
]


def __getattr__(name: str):
    """Lazily import heavy modules to avoid package import cycles."""
    if name == "IngestionPipeline":
        from packages.ingestion.pipeline import IngestionPipeline

        return IngestionPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
