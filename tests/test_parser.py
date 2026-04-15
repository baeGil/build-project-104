"""Unit tests for the Vietnamese Legal Document Parser."""

from datetime import date
from typing import Any

import pytest

from packages.common.types import DocumentType, LegalNode
from packages.ingestion.parser import (
    DocumentParser,
    extract_amendment_refs,
    extract_articles,
    extract_citation_refs,
    extract_metadata,
    infer_document_type,
    parse_legal_document,
)


class TestInferDocumentType:
    """Tests for infer_document_type function."""

    def test_infer_law_from_title(self) -> None:
        """Test detecting law document type."""
        title = "Luật Doanh nghiệp 2020"
        result = infer_document_type(title)
        assert result == DocumentType.LAW

    def test_infer_law_from_bo_luat(self) -> None:
        """Test detecting law from 'Bộ luật' prefix."""
        title = "Bộ luật Dân sự 2015"
        result = infer_document_type(title)
        assert result == DocumentType.LAW

    def test_infer_decree(self) -> None:
        """Test detecting decree document type."""
        title = "Nghị định về đầu tư nước ngoài"
        result = infer_document_type(title)
        assert result == DocumentType.DECREE

    def test_infer_decree_nd_cp(self) -> None:
        """Test detecting decree from NĐ-CP pattern."""
        title = "NĐ-CP 99/2020 quy định về xử phạt"
        result = infer_document_type(title)
        assert result == DocumentType.DECREE

    def test_infer_circular(self) -> None:
        """Test detecting circular document type."""
        title = "Thông tư hướng dẫn Luật Doanh nghiệp"
        result = infer_document_type(title)
        assert result == DocumentType.CIRCULAR

    def test_infer_circular_tt_btc(self) -> None:
        """Test detecting circular from TT-BTC pattern."""
        title = "TT-BTC 200/2020 hướng dẫn thuế"
        result = infer_document_type(title)
        assert result == DocumentType.CIRCULAR

    def test_infer_decision(self) -> None:
        """Test detecting decision document type."""
        title = "Quyết định phê duyệt dự án"
        result = infer_document_type(title)
        assert result == DocumentType.DECISION

    def test_infer_resolution(self) -> None:
        """Test detecting resolution document type."""
        title = "Nghị quyết của Quốc hội"
        result = infer_document_type(title)
        assert result == DocumentType.RESOLUTION

    def test_infer_other_when_no_match(self) -> None:
        """Test returning OTHER when no pattern matches."""
        title = "Văn bản không xác định loại"
        result = infer_document_type(title)
        assert result == DocumentType.OTHER

    def test_infer_case_insensitive(self) -> None:
        """Test case-insensitive matching."""
        title = "luật doanh nghiệp 2020"
        result = infer_document_type(title)
        assert result == DocumentType.LAW


class TestExtractMetadata:
    """Tests for extract_metadata function."""

    def test_extract_metadata_with_all_fields(self) -> None:
        """Test extracting metadata with complete document."""
        text = """
        Luật Doanh nghiệp 2020
        Căn cứ Hiến pháp năm 2013;
        Quốc hội ban hành Luật Doanh nghiệp.
        Ngày 17 tháng 6 năm 2020
        Luật này có hiệu lực từ ngày 1 tháng 1 năm 2021
        Số: 59/2020/QH14
        """
        result = extract_metadata(text)

        assert result["doc_type"] == DocumentType.LAW
        assert result["publish_date"] == date(2020, 6, 17)
        assert result["effective_date"] == date(2021, 1, 1)
        assert result["document_number"] == "59/2020/QH14"
        assert result["issuing_body"] == "Quốc hội"

    def test_extract_metadata_no_dates(self) -> None:
        """Test extracting metadata without dates."""
        text = "Luật Doanh nghiệp 2020"
        result = extract_metadata(text)

        assert result["doc_type"] == DocumentType.LAW
        assert result["publish_date"] is None
        assert result["effective_date"] is None

    def test_extract_metadata_single_date(self) -> None:
        """Test extracting metadata with only one date."""
        text = "Luật Doanh nghiệp\nNgày 17 tháng 6 năm 2020"
        result = extract_metadata(text)

        assert result["publish_date"] == date(2020, 6, 17)
        assert result["effective_date"] is None

    def test_extract_metadata_issuing_body_government(self) -> None:
        """Test extracting issuing body as Chính phủ."""
        text = "Nghị định của Chính phủ"
        result = extract_metadata(text)
        assert result["issuing_body"] == "Chính phủ"

    def test_extract_metadata_issuing_body_ministry(self) -> None:
        """Test extracting issuing body as ministry."""
        text = "Thông tư của Bộ Tư pháp"
        result = extract_metadata(text)
        assert result["issuing_body"] == "Bộ Tư pháp"

    def test_extract_metadata_issuing_body_prime_minister(self) -> None:
        """Test extracting issuing body as Prime Minister."""
        text = "Quyết định của Thủ tướng"
        result = extract_metadata(text)
        assert result["issuing_body"] == "Thủ tướng"

    def test_extract_metadata_no_document_number(self) -> None:
        """Test extracting metadata without document number."""
        text = "Luật Doanh nghiệp"
        result = extract_metadata(text)
        assert result["document_number"] is None

    def test_extract_metadata_various_doc_numbers(self) -> None:
        """Test extracting various document number formats."""
        text1 = "Số: 99/2020/NĐ-CP"
        result1 = extract_metadata(text1)
        assert result1["document_number"] == "99/2020/NĐ-CP"

        text2 = "Số 13/2020/TT-BTC"
        result2 = extract_metadata(text2)
        assert result2["document_number"] == "13/2020/TT-BTC"


class TestExtractArticles:
    """Tests for extract_articles function."""

    def test_extract_single_article(self) -> None:
        """Test extracting a single article."""
        text = """
        Điều 1. Phạm vi điều chỉnh
        Luật này quy định về doanh nghiệp.
        """
        result = extract_articles(text)

        assert len(result) == 1
        assert result[0]["number"] == "1"
        assert result[0]["title"] == "Phạm vi điều chỉnh"

    def test_extract_multiple_articles(self) -> None:
        """Test extracting multiple articles."""
        text = """
        Điều 1. Phạm vi điều chỉnh
        Luật này quy định về doanh nghiệp.

        Điều 2. Đối tượng áp dụng
        Luật này áp dụng đối với doanh nghiệp.
        """
        result = extract_articles(text)

        assert len(result) == 2
        assert result[0]["number"] == "1"
        assert result[1]["number"] == "2"

    def test_extract_article_with_subsections(self) -> None:
        """Test extracting article with numbered subsections."""
        text = """
        Điều 46. Công ty trách nhiệm hữu hạn
        1. Công ty trách nhiệm hữu hạn là doanh nghiệp.
        2. Công ty trách nhiệm hữu hạn có thể có một hoặc nhiều thành viên.
        """
        result = extract_articles(text)

        assert len(result) == 1
        assert result[0]["number"] == "46"
        assert len(result[0]["subsections"]) == 2
        assert result[0]["subsections"][0]["number"] == "1"
        assert result[0]["subsections"][1]["number"] == "2"

    def test_extract_article_with_clauses(self) -> None:
        """Test extracting article with letter clauses."""
        text = """
        Điều 47. Thành viên công ty
        a) Thành viên có quyền tham dự họp;
        b) Thành viên có quyền biểu quyết;
        c) Thành viên có quyền chia lợi nhuận.
        """
        result = extract_articles(text)

        assert len(result) == 1
        assert len(result[0]["clauses"]) == 3
        assert result[0]["clauses"][0]["letter"] == "a"
        assert result[0]["clauses"][1]["letter"] == "b"

    def test_extract_article_with_subsections_and_clauses(self) -> None:
        """Test extracting article with subsections containing clauses."""
        text = """
        Điều 1. Quy định chung
        1. Về quyền và nghĩa vụ:
        a) Quyền được bảo vệ;
        b) Nghĩa vụ tuân thủ pháp luật.
        2. Về trách nhiệm:
        a) Trách nhiệm dân sự;
        b) Trách nhiệm hình sự.
        """
        result = extract_articles(text)

        assert len(result) == 1
        assert len(result[0]["subsections"]) == 2
        # Check first subsection has clauses
        assert len(result[0]["subsections"][0]["clauses"]) == 2
        assert result[0]["subsections"][0]["clauses"][0]["letter"] == "a"

    def test_extract_no_articles(self) -> None:
        """Test extracting from text with no articles."""
        text = "Văn bản không có điều khoản nào"
        result = extract_articles(text)
        assert len(result) == 0

    def test_extract_article_with_diacritic_letters(self) -> None:
        """Test extracting article with Vietnamese letters like đ."""
        text = """
        Điều 1. Quy định
        a) Khoản a;
        b) Khoản b;
        c) Khoản c;
        đ) Khoản đ;
        e) Khoản e.
        """
        result = extract_articles(text)

        assert len(result) == 1
        assert len(result[0]["clauses"]) == 5
        assert result[0]["clauses"][3]["letter"] == "đ"


class TestExtractAmendmentRefs:
    """Tests for extract_amendment_refs function."""

    def test_extract_single_amendment(self) -> None:
        """Test extracting single amendment reference."""
        text = "Luật này sửa đổi Luật Doanh nghiệp 2005"
        result = extract_amendment_refs(text)
        assert len(result) == 1
        assert "Luật 2005" in result[0]

    def test_extract_multiple_amendments(self) -> None:
        """Test extracting multiple amendment references."""
        text = """
        Luật này sửa đổi Luật Doanh nghiệp 2005 và
        sửa đổi Nghị định 99/2020/NĐ-CP
        """
        result = extract_amendment_refs(text)
        assert len(result) == 2

    def test_extract_amendment_with_document_number(self) -> None:
        """Test extracting amendment with specific document number."""
        text = "Sửa đổi bởi Luật số 12/2020/QH14"
        result = extract_amendment_refs(text)
        assert len(result) >= 1

    def test_no_amendments(self) -> None:
        """Test extracting from text with no amendments."""
        text = "Luật Doanh nghiệp 2020 không có sửa đổi"
        result = extract_amendment_refs(text)
        assert len(result) == 0


class TestExtractCitationRefs:
    """Tests for extract_citation_refs function."""

    def test_extract_single_citation(self) -> None:
        """Test extracting single citation reference."""
        text = "Theo quy định tại Điều 46 Luật Doanh nghiệp 2020"
        result = extract_citation_refs(text)
        assert len(result) == 1
        assert "Điều 46" in result[0]
        assert "Luật" in result[0]
        assert "2020" in result[0]

    def test_extract_multiple_citations(self) -> None:
        """Test extracting multiple citation references."""
        text = """
        Theo Điều 46 Luật Doanh nghiệp 2020 và
        Điều 12 Nghị định 99/2020
        """
        result = extract_citation_refs(text)
        assert len(result) == 2

    def test_extract_citation_decree(self) -> None:
        """Test extracting citation to decree."""
        text = "Căn cứ Điều 5 Nghị định 2020"
        result = extract_citation_refs(text)
        assert len(result) >= 1
        assert "Nghị định" in result[0]

    def test_no_citations(self) -> None:
        """Test extracting from text with no citations."""
        text = "Văn bản không có trích dẫn nào"
        result = extract_citation_refs(text)
        assert len(result) == 0


class TestParseLegalDocument:
    """Tests for parse_legal_document function."""

    def test_parse_simple_document(self) -> None:
        """Test parsing a simple legal document."""
        text = """
        Luật Doanh nghiệp 2020
        Điều 1. Phạm vi điều chỉnh
        Luật này quy định về doanh nghiệp.
        """
        result = parse_legal_document(text, "Luật Doanh nghiệp 2020")

        assert isinstance(result, LegalNode)
        assert result.title == "Luật Doanh nghiệp 2020"
        assert result.doc_type == DocumentType.LAW
        assert result.level == 0
        assert len(result.children_ids) == 1

    def test_parse_document_with_articles(self) -> None:
        """Test parsing document with multiple articles."""
        text = """
        Luật Doanh nghiệp 2020
        Ngày 17 tháng 6 năm 2020
        Số: 59/2020/QH14

        Điều 46. Công ty trách nhiệm hữu hạn
        1. Công ty trách nhiệm hữu hạn là doanh nghiệp.
        2. Công ty có thể có một hoặc nhiều thành viên.

        Điều 47. Quyền của thành viên
        Thành viên có các quyền theo quy định.
        """
        result = parse_legal_document(text)

        assert result.doc_type == DocumentType.LAW
        assert result.publish_date == date(2020, 6, 17)
        assert result.document_number == "59/2020/QH14"
        assert len(result.children_ids) == 2

    def test_parse_document_with_amendments(self) -> None:
        """Test parsing document with amendment references."""
        text = """
        Luật sửa đổi 2021
        Sửa đổi Luật Doanh nghiệp 2005
        Điều 1. Sửa đổi bổ sung
        """
        result = parse_legal_document(text)

        assert len(result.amendment_refs) >= 1

    def test_parse_document_with_citations(self) -> None:
        """Test parsing document with citation references."""
        text = """
        Nghị định hướng dẫn
        Theo Điều 46 Luật Doanh nghiệp 2020
        Điều 1. Hướng dẫn thi hành
        """
        result = parse_legal_document(text)

        assert len(result.citation_refs) >= 1

    def test_parse_document_generates_uuid(self) -> None:
        """Test that parsing generates a valid UUID."""
        text = "Điều 1. Test"
        result = parse_legal_document(text)

        assert result.id is not None
        assert len(result.id) > 0

    def test_parse_document_creates_child_nodes(self) -> None:
        """Test that parsing creates child article nodes."""
        text = """
        Điều 1. Article One
        Content of article one.
        Điều 2. Article Two
        Content of article two.
        """
        result = parse_legal_document(text)

        # Check children_ids are populated
        assert len(result.children_ids) == 2
        # Check article IDs follow expected pattern
        assert "article_1" in result.children_ids[0]
        assert "article_2" in result.children_ids[1]


class TestDocumentParser:
    """Tests for DocumentParser class."""

    @pytest.mark.asyncio
    async def test_parse_text_method(self) -> None:
        """Test parse_text method."""
        parser = DocumentParser()
        text = """
        Luật Doanh nghiệp 2020
        Điều 1. Phạm vi điều chỉnh
        Luật này quy định về doanh nghiệp.
        """
        result = parser.parse_text(text, "Luật Doanh nghiệp 2020")

        assert isinstance(result, LegalNode)
        assert result.title == "Luật Doanh nghiệp 2020"

    @pytest.mark.asyncio
    async def test_parse_txt_format(self) -> None:
        """Test parsing txt format content."""
        parser = DocumentParser()
        content = "Luật Doanh nghiệp\nĐiều 1. Test".encode("utf-8")
        result = await parser.parse(content, "txt", "Test Document")

        assert isinstance(result, LegalNode)
        assert result.title == "Test Document"

    @pytest.mark.asyncio
    async def test_parse_html_format(self) -> None:
        """Test parsing html format content."""
        parser = DocumentParser()
        content = "<p>Luật Doanh nghiệp</p>\n<p>Điều 1. Test</p>".encode("utf-8")
        result = await parser.parse(content, "html", "HTML Document")

        assert isinstance(result, LegalNode)

    @pytest.mark.asyncio
    async def test_parse_pdf_format(self) -> None:
        """Test parsing pdf format content (falls back to utf-8 decode)."""
        parser = DocumentParser()
        content = "Luật Doanh nghiệp\nĐiều 1. Test".encode("utf-8")
        result = await parser.parse(content, "pdf", "PDF Document")

        assert isinstance(result, LegalNode)

    @pytest.mark.asyncio
    async def test_parse_without_title(self) -> None:
        """Test parsing without providing title."""
        parser = DocumentParser()
        content = "First Line Title\nĐiều 1. Test".encode("utf-8")
        result = await parser.parse(content, "txt")

        assert result.title == "First Line Title"


class TestParserEdgeCases:
    """Tests for edge cases in parser functions."""

    def test_empty_text(self) -> None:
        """Test parsing empty text."""
        result = parse_legal_document("")
        assert isinstance(result, LegalNode)
        assert result.title == ""

    def test_whitespace_only(self) -> None:
        """Test parsing whitespace-only text."""
        result = parse_legal_document("   \n\n   ")
        assert isinstance(result, LegalNode)

    def test_article_without_title(self) -> None:
        """Test extracting article without title."""
        text = "Điều 1\nNội dung điều 1"
        result = extract_articles(text)

        assert len(result) == 1
        assert result[0]["number"] == "1"
        assert result[0]["title"] == ""

    def test_article_with_colon_separator(self) -> None:
        """Test extracting article with colon separator."""
        text = "Điều 1: Tiêu đề\nNội dung"
        result = extract_articles(text)

        assert len(result) == 1
        assert "Tiêu đề" in result[0]["title"]

    def test_article_with_dash_separator(self) -> None:
        """Test extracting article with dash separator."""
        text = "Điều 1 - Tiêu đề\nNội dung"
        result = extract_articles(text)

        assert len(result) == 1
        assert "Tiêu đề" in result[0]["title"]
