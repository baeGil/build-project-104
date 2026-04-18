"""Vietnamese Legal Document Parser.

This module provides regex-based parsing for Vietnamese legal documents,
extracting hierarchical structure (Điều/Khoan/Điểm) and metadata.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Any

from packages.common.types import DocumentType, LegalNode


# Regex patterns for Vietnamese legal document structure
ARTICLE_PATTERN = re.compile(
    r"^\s*Điều\s+(\d+)\s*(?:[\.:\-]\s*(.*)|\s*$)",
    re.IGNORECASE | re.UNICODE | re.MULTILINE,
)

SUBSECTION_PATTERN = re.compile(
    r"^\s*(\d+)\.\s+(.*)",
    re.MULTILINE | re.UNICODE,
)

CLAUSE_PATTERN = re.compile(
    r"^\s*([a-zđ])\)\s+(.*)",
    re.MULTILINE | re.UNICODE,
)

# Date patterns
DATE_PATTERN = re.compile(
    r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
    re.IGNORECASE | re.UNICODE,
)

# Amendment references
AMENDMENT_PATTERN = re.compile(
    r"sửa\s+đổi.*?(Luật|Nghị\s+định|Thông\s+tư|Quyết\s+định).*?(\d{4}|\d+/[\w\-]+|số\s+\d+)",
    re.IGNORECASE | re.UNICODE,
)

# Cross-references to other documents
CITATION_PATTERN = re.compile(
    r"Điều\s+(\d+).*?(Luật|Nghị\s+định|Thông\s+tư|Quyết\s+định).*?(\d{4})",
    re.IGNORECASE | re.UNICODE,
)

# Document type detection patterns
DOC_TYPE_PATTERNS = {
    DocumentType.LAW: re.compile(
        r"\b(Luật|Bộ\s+luật)\b", re.IGNORECASE | re.UNICODE
    ),
    DocumentType.DECREE: re.compile(
        r"\b(Nghị\s+định|NĐ-CP)\b", re.IGNORECASE | re.UNICODE
    ),
    DocumentType.CIRCULAR: re.compile(
        r"\b(Thông\s+tư|TT|TT-BTC|TT-BTP)\b", re.IGNORECASE | re.UNICODE
    ),
    DocumentType.DECISION: re.compile(
        r"\b(Quyết\s+định|QĐ)\b", re.IGNORECASE | re.UNICODE
    ),
    DocumentType.RESOLUTION: re.compile(
        r"\b(Nghị\s+quyết|NQ)\b", re.IGNORECASE | re.UNICODE
    ),
}

# Document number patterns
# Examples: "số: 36/1999/NĐ-CP", "số 61/2020/QH14", "Số: 71/HĐBT"
# Use \d+ to match ANY number of digits - no hardcoded limits
DOC_NUMBER_PATTERN = re.compile(
    r"(?:số|Số)\s*[:\s]\s*(\d+/[\w\-]+(?:/[\w\-]+)*)",
    re.IGNORECASE | re.UNICODE,
)

# Alternative pattern: look for document number in first 200 chars with context
# Matches patterns like "36/1999/NĐ-CP", "61/2020/QH14", "103/SL"
DOC_NUMBER_CONTEXT_PATTERN = re.compile(
    r"(?:văn\s+bản|công\s+văn|quyết\s+định|nghị\s+định|thông\s+tư|sắc\s+lệnh)?\s*(\d+/\d*/?[\w\-\u00C0-\u1EF9]*)",
    re.IGNORECASE | re.UNICODE,
)

# Issuing body patterns
ISSUING_BODY_PATTERNS = [
    re.compile(r"Quốc\s+hội", re.IGNORECASE | re.UNICODE),
    re.compile(r"Chính\s+phủ", re.IGNORECASE | re.UNICODE),
    re.compile(r"Thủ\s+tướng", re.IGNORECASE | re.UNICODE),
    re.compile(r"Bộ\s+(?:Tư\s+pháp|Tài\s+chính|Công\s+thương|Lao\s+động)", re.IGNORECASE | re.UNICODE),
    re.compile(r"Ngân\s+hàng\s+Nhà\s+nước", re.IGNORECASE | re.UNICODE),
    re.compile(r"UBND\s+(?:tỉnh|thành\s+phố)", re.IGNORECASE | re.UNICODE),
]


def infer_document_type(title: str) -> DocumentType:
    """Classify document type from title or content.

    Args:
        title: Document title or content to analyze.

    Returns:
        Detected DocumentType enum value.
    """
    # Find the first match in the text (by position), not by pattern order
    first_match: tuple[int, DocumentType] | None = None
    for doc_type, pattern in DOC_TYPE_PATTERNS.items():
        match = pattern.search(title)
        if match:
            if first_match is None or match.start() < first_match[0]:
                first_match = (match.start(), doc_type)
    
    if first_match:
        return first_match[1]
    return DocumentType.OTHER


def extract_metadata(text: str) -> dict[str, Any]:
    """Extract document metadata from text.

    Extracts:
    - Document type
    - Publication/effective dates
    - Document number
    - Law ID (extracted from document number)
    - Issuing body

    Args:
        text: Raw document text.

    Returns:
        Dictionary containing extracted metadata.
    """
    metadata: dict[str, Any] = {
        "doc_type": DocumentType.OTHER,
        "publish_date": None,
        "effective_date": None,
        "expiry_date": None,
        "document_number": None,
        "law_id": None,  # New field
        "issuing_body": None,
    }

    # Detect document type from first 500 chars
    header = text[:500]
    metadata["doc_type"] = infer_document_type(header)

    # Extract dates
    dates = DATE_PATTERN.findall(text)
    if dates:
        # First date is usually publication date
        day, month, year = dates[0]
        metadata["publish_date"] = date(int(year), int(month), int(day))

        # Second date might be effective date
        if len(dates) > 1:
            day, month, year = dates[1]
            metadata["effective_date"] = date(int(year), int(month), int(day))

    # Extract document number
    doc_num_match = DOC_NUMBER_PATTERN.search(text)
    
    # If primary pattern doesn't match, try context-based extraction
    if not doc_num_match:
        # Look for document number in header (first 300 chars)
        header = text[:300]
        doc_num_match = DOC_NUMBER_CONTEXT_PATTERN.search(header)
    
    if doc_num_match:
        raw_doc_num = doc_num_match.group(1)
        
        # Clean up: detect truncated Vietnamese words
        # Strategy: split by / and check if last part is a complete abbreviation or truncated word
        parts = raw_doc_num.split('/')
        
        # Vietnamese document types typically end with:
        # - Standard abbreviations: NĐ-CP, TT, QĐ, SL, CP, QH14, HĐBT, etc. (2-6 chars)
        # - Full words: "Luật", "Pháp lệnh" (rare in number field)
        # If a part is 4-6 chars and looks like Vietnamese word (not abbreviation), it's truncated
        # Clean up: detect truncated Vietnamese words using GENERAL rules
        # Strategy: Vietnamese legal document numbers follow pattern:
        #   [number]/[year?]/[abbreviation]
        # Where:
        #   - number: digits only (e.g., "36", "103")
        #   - year: 4 digits (e.g., "1999", "2020") - OPTIONAL
        #   - abbreviation: UPPERCASE letters, may contain hyphens/digits (e.g., "NĐ-CP", "QH14")
        #
        # Truncated words are lowercase Vietnamese words with diacritics
        
        cleaned_parts = []
        for i, part in enumerate(parts):
            # Rule 1: First part must be pure digits (document number)
            if i == 0:
                if part.isdigit():
                    cleaned_parts.append(part)
                else:
                    # Invalid format - stop processing
                    break
            
            # Rule 2: Middle parts - accept if numeric (year) or abbreviation pattern
            else:
                # Check if this part matches abbreviation pattern:
                # - All uppercase (may include Vietnamese uppercase like Đ, Ô)
                # - OR contains structural chars (hyphen, digits)
                # - NOT lowercase Vietnamese words
                
                is_numeric = part.isdigit()
                
                # Detect if it's a Vietnamese word (has lowercase + diacritics)
                has_lowercase_diacritics = any(
                    c in 'áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởợúùủũụưứừửữựýỳỷỹỵđ'
                    for c in part  # Check original case, not lower()
                ) and not part.isupper()
                
                # Vietnamese truncated words: lowercase with diacritics
                # Examples: "Chính", "Nghị", "định" 
                if has_lowercase_diacritics:
                    # This is a Vietnamese word, not an abbreviation - stop
                    break
                
                # Accept: pure numbers, uppercase abbreviations, or mixed with structural chars
                if is_numeric or part.isupper() or '-' in part or any(c.isdigit() for c in part):
                    cleaned_parts.append(part)
                else:
                    # Doesn't match any valid pattern - stop
                    break
        
        metadata["document_number"] = '/'.join(cleaned_parts)
        
        # Extract law_id from document_number
        # Use the cleaned document number as law_id
        # General pattern: starts with digits followed by /
        if re.match(r'\d+/', metadata["document_number"]):
            metadata["law_id"] = metadata["document_number"]

    # Extract issuing body
    for pattern in ISSUING_BODY_PATTERNS:
        match = pattern.search(text)
        if match:
            metadata["issuing_body"] = match.group(0)
            break

    return metadata


def extract_articles(text: str) -> list[dict[str, Any]]:
    """Extract all articles with their subsections and clauses.

    Args:
        text: Raw document text.

    Returns:
        List of article dictionaries with hierarchical structure.
    """
    articles = []

    # Find all article positions
    article_matches = list(ARTICLE_PATTERN.finditer(text))

    for i, match in enumerate(article_matches):
        article_num = match.group(1)
        article_title = match.group(2).strip() if match.group(2) else ""

        # Determine article content boundaries
        start_pos = match.end()
        end_pos = article_matches[i + 1].start() if i + 1 < len(article_matches) else len(text)
        article_content = text[start_pos:end_pos].strip()

        # Extract subsections within this article
        subsections = []
        subsection_matches = list(SUBSECTION_PATTERN.finditer(article_content))

        for j, sub_match in enumerate(subsection_matches):
            sub_num = sub_match.group(1)
            sub_text = sub_match.group(2).strip()

            # Determine subsection boundaries
            sub_start = sub_match.end()
            sub_end = (
                subsection_matches[j + 1].start()
                if j + 1 < len(subsection_matches)
                else len(article_content)
            )
            sub_content = article_content[sub_start:sub_end].strip()

            # Extract clauses within this subsection
            clauses = []
            clause_matches = list(CLAUSE_PATTERN.finditer(sub_content))

            for clause_match in clause_matches:
                clause_letter = clause_match.group(1)
                clause_text = clause_match.group(2).strip()
                clauses.append({
                    "letter": clause_letter,
                    "text": clause_text,
                })

            subsections.append({
                "number": sub_num,
                "text": sub_text,
                "content": sub_content,
                "clauses": clauses,
            })

        # If no subsections found, check for direct clauses
        clauses = []
        if not subsections:
            clause_matches = list(CLAUSE_PATTERN.finditer(article_content))
            for clause_match in clause_matches:
                clause_letter = clause_match.group(1)
                clause_text = clause_match.group(2).strip()
                clauses.append({
                    "letter": clause_letter,
                    "text": clause_text,
                })

        articles.append({
            "number": article_num,
            "title": article_title,
            "content": article_content,
            "subsections": subsections,
            "clauses": clauses if not subsections else [],
        })

    return articles


def extract_amendment_refs(text: str) -> list[str]:
    """Find amendment references in the text.

    Args:
        text: Raw document text.

    Returns:
        List of amendment reference strings.
    """
    refs = []
    for match in AMENDMENT_PATTERN.finditer(text):
        doc_type = match.group(1)
        doc_num = match.group(2)
        refs.append(f"{doc_type} {doc_num}")
    return refs


def extract_citation_refs(text: str) -> list[str]:
    """Find cross-document citations in the text.

    Args:
        text: Raw document text.

    Returns:
        List of citation reference strings.
    """
    refs = []
    for match in CITATION_PATTERN.finditer(text):
        article = match.group(1)
        doc_type = match.group(2)
        year = match.group(3)
        refs.append(f"Điều {article} {doc_type} {year}")
    return refs


def parse_legal_document(
    text: str,
    title: str | None = None,
    doc_id: str | None = None,
    law_id: str | None = None,
    document_number: str | None = None,
    doc_type: "DocumentType | None" = None,
    publish_date: "date | None" = None,
    effective_date: "date | None" = None,
    issuing_body: str | None = None,
) -> LegalNode:
    """Parse a full legal document into a hierarchical LegalNode structure.

    Args:
        text: Raw document text.
        title: Optional document title. If not provided, will extract from text.
        doc_id: Optional document ID from the source dataset. If not provided,
                a new UUID will be generated.
        law_id: Optional law_id directly from dataset (so_ky_hieu). Takes
                priority over regex-extracted value from text.
        document_number: Optional document number directly from dataset.
        doc_type: Optional document type from dataset. Takes priority over
                  the type inferred from content text.
        publish_date: Optional publish date from dataset (ngay_ban_hanh).
                      Takes priority over regex-extracted date.
        effective_date: Optional effective date from dataset (ngay_co_hieu_luc).
                        Takes priority over regex-extracted date.
        issuing_body: Optional issuing organisation from dataset
                      (co_quan_ban_hanh). Takes priority over regex-extracted.

    Returns:
        Root LegalNode containing the full document hierarchy.
    """
    # Extract metadata from content text
    metadata = extract_metadata(text)

    # Use provided title or extract from first line
    doc_title = title or text.split("\n")[0].strip()

    # Use provided doc_id (from dataset) or generate UUID as fallback
    doc_id = doc_id or str(uuid.uuid4())

    # Dataset values take priority over regex-extracted values
    if law_id:
        metadata["law_id"] = law_id
    if document_number:
        metadata["document_number"] = document_number
    if doc_type is not None:
        metadata["doc_type"] = doc_type
    if publish_date is not None:
        metadata["publish_date"] = publish_date
    if effective_date is not None:
        metadata["effective_date"] = effective_date
    if issuing_body:
        metadata["issuing_body"] = issuing_body

    # Extract articles
    articles = extract_articles(text)

    # Extract amendment and citation references
    amendment_refs = extract_amendment_refs(text)
    citation_refs = extract_citation_refs(text)

    # Build children IDs
    children_ids = []
    child_nodes = []

    for article in articles:
        article_id = f"{doc_id}_article_{article['number']}"
        children_ids.append(article_id)

        # Build article content
        article_content = article["content"]
        if article["subsections"]:
            article_content = "\n".join(
                f"{sub['number']}. {sub['text']}" for sub in article["subsections"]
            )
        elif article["clauses"]:
            article_content = "\n".join(
                f"{clause['letter']}) {clause['text']}" for clause in article["clauses"]
            )

        article_node = LegalNode(
            id=article_id,
            title=f"Điều {article['number']}. {article['title']}".strip(". "),
            content=article_content,
            doc_type=metadata["doc_type"],
            parent_id=doc_id,
            level=2,  # Article level
            publish_date=metadata["publish_date"],
            effective_date=metadata["effective_date"],
            expiry_date=metadata["expiry_date"],
            issuing_body=metadata["issuing_body"],
            document_number=metadata["document_number"],
            law_id=metadata["law_id"],  # Add law_id
        )
        child_nodes.append(article_node)

    # Create root document node
    root_node = LegalNode(
        id=doc_id,
        title=doc_title,
        content=text,
        doc_type=metadata["doc_type"],
        level=0,  # Document level
        children_ids=children_ids,
        publish_date=metadata["publish_date"],
        effective_date=metadata["effective_date"],
        expiry_date=metadata["expiry_date"],
        issuing_body=metadata["issuing_body"],
        document_number=metadata["document_number"],
        law_id=metadata["law_id"],  # Add law_id
        amendment_refs=amendment_refs,
        citation_refs=citation_refs,
    )

    return root_node


class DocumentParser:
    """Parser for Vietnamese legal documents.

    Extracts structured content from legal documents including:
    - Document metadata (issuing body, dates, document number)
    - Hierarchical structure (chapters, articles, clauses)
    - Cross-references to other legal documents
    - Amendment and citation relationships
    """

    def __init__(self) -> None:
        """Initialize the document parser."""
        pass

    async def parse(self, content: bytes, format: str, title: str | None = None) -> LegalNode:
        """Parse a document and extract structured content.

        Args:
            content: Raw document content as bytes
            format: Document format (pdf, docx, txt, html)
            title: Optional document title

        Returns:
            LegalNode containing parsed document structure and metadata
        """
        # Decode content based on format
        if format.lower() in ("txt", "html", "md"):
            text = content.decode("utf-8", errors="replace")
        else:
            # For binary formats like PDF/DOCX, we'd need additional libraries
            # For now, assume text extraction is done externally
            text = content.decode("utf-8", errors="replace")

        return parse_legal_document(text, title)

    def parse_text(self, text: str, title: str | None = None) -> LegalNode:
        """Parse text directly into a LegalNode.

        Args:
            text: Raw document text
            title: Optional document title

        Returns:
            LegalNode containing parsed document structure
        """
        return parse_legal_document(text, title)
