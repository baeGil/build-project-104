"""Tests for the QueryPlanner class."""
from __future__ import annotations

import pytest

from packages.common.types import QueryStrategy
from packages.reasoning.planner import LegalQueryPlanner, QueryPlanner


class TestQueryPlannerPlan:
    """Test QueryPlanner.plan() method."""

    @pytest.fixture
    def planner(self) -> LegalQueryPlanner:
        """Create a fresh planner instance."""
        return LegalQueryPlanner()

    def test_plan_basic_query(self, planner: LegalQueryPlanner) -> None:
        """Test planning a basic query without special features."""
        query = "Công ty TNHH có bao nhiêu thành viên?"
        result = planner.plan(query)

        assert result.original_query == query
        assert result.normalized_query == query.lower()
        assert result.strategy == QueryStrategy.SEMANTIC
        assert not result.has_negation
        assert result.citations == []

    def test_plan_with_citations(self, planner: LegalQueryPlanner) -> None:
        """Test planning a query with legal citations."""
        query = "Theo Điều 46 Luật Doanh nghiệp năm 2020, công ty TNHH có mấy thành viên?"
        result = planner.plan(query)

        assert result.original_query == query
        assert "Điều 46" in result.citations
        # Citations are extracted from the expanded text, which may have different case
        assert any("Luật" in c and "doanh nghiệp" in c.lower() and "2020" in c for c in result.citations)
        assert result.strategy == QueryStrategy.CITATION

    def test_plan_with_negation(self, planner: LegalQueryPlanner) -> None:
        """Test planning a query with negation words."""
        query = "Công ty không được phép làm gì?"
        result = planner.plan(query)

        assert result.has_negation is True
        assert result.negation_scope is not None
        assert result.strategy == QueryStrategy.NEGATION

    def test_plan_with_abbreviations(self, planner: LegalQueryPlanner) -> None:
        """Test that abbreviations are expanded in the query."""
        query = "LDN2020 quy định gì về công ty?"
        result = planner.plan(query)

        # Abbreviation expansion happens in the expanded text, not normalized_query
        # normalized_query is lowercase, expansion_variants contains the expanded forms
        assert any("Luật Doanh Nghiệp năm 2020" in variant for variant in result.expansion_variants)
        # The citation should also contain the expanded form
        assert any("Luật Doanh Nghiệp năm 2020" in c for c in result.citations)

    def test_plan_preserves_original(self, planner: LegalQueryPlanner) -> None:
        """Test that original query is preserved."""
        query = "  Công   ty   TNHH  "
        result = planner.plan(query)

        assert result.original_query == query
        # Normalized should be cleaned up
        assert result.normalized_query == "công ty tnhh"


class TestQueryPlannerNormalizeQuery:
    """Test QueryPlanner.normalize_query() method."""

    @pytest.fixture
    def planner(self) -> LegalQueryPlanner:
        return LegalQueryPlanner()

    def test_normalize_whitespace(self, planner: LegalQueryPlanner) -> None:
        """Test whitespace normalization."""
        query = "Công    ty    TNHH"
        result = planner.normalize_query(query)
        assert result == "công ty tnhh"

    def test_normalize_newlines(self, planner: LegalQueryPlanner) -> None:
        """Test newline normalization."""
        query = "Công ty\n\n\nTNHH"
        result = planner.normalize_query(query)
        assert result == "công ty tnhh"

    def test_normalize_lowercase(self, planner: LegalQueryPlanner) -> None:
        """Test lowercase conversion."""
        query = "CÔNG TY TNHH"
        result = planner.normalize_query(query)
        assert result == "công ty tnhh"

    def test_normalize_strip(self, planner: LegalQueryPlanner) -> None:
        """Test leading/trailing whitespace stripping."""
        query = "  Công ty TNHH  "
        result = planner.normalize_query(query)
        assert result == "công ty tnhh"

    def test_normalize_unicode(self, planner: LegalQueryPlanner) -> None:
        """Test Unicode NFC normalization."""
        # Using a decomposed character sequence
        query = "Công ty TNHH"  # This should be normalized
        result = planner.normalize_query(query)
        assert result == "công ty tnhh"


class TestQueryPlannerExpandSynonyms:
    """Test QueryPlanner.expand_synonyms() method."""

    @pytest.fixture
    def planner(self) -> LegalQueryPlanner:
        return LegalQueryPlanner()

    def test_expand_synonyms_basic(self, planner: LegalQueryPlanner) -> None:
        """Test basic synonym expansion."""
        text = "nhân viên làm việc"
        variants = planner.expand_synonyms(text)

        # Should include original and variants with synonyms
        assert text in variants
        # Should include variants with "ngườI_lao_động" or "công_nhân"
        assert len(variants) > 1

    def test_expand_synonyms_multiple_terms(self, planner: LegalQueryPlanner) -> None:
        """Test expansion with multiple synonym terms."""
        text = "công_ty và nhân_viên"
        variants = planner.expand_synonyms(text)

        # Should have original plus variants
        assert len(variants) >= 1
        assert text in variants

    def test_expand_synonyms_no_matches(self, planner: LegalQueryPlanner) -> None:
        """Test expansion with no matching synonyms."""
        text = "xyz abc 123"
        variants = planner.expand_synonyms(text)

        # Should just return original
        assert variants == [text]

    def test_expand_synonyms_negation(self, planner: LegalQueryPlanner) -> None:
        """Test expansion of negation synonyms."""
        text = "không được làm"
        variants = planner.expand_synonyms(text)

        # Should include variants with "cấm", "nghiêm cấm", etc.
        assert len(variants) > 1


class TestQueryPlannerDetectNegation:
    """Test QueryPlanner.detect_negation() method with Vietnamese negation words."""

    @pytest.fixture
    def planner(self) -> LegalQueryPlanner:
        return LegalQueryPlanner()

    def test_detect_negation_khong(self, planner: LegalQueryPlanner) -> None:
        """Test detecting 'không' negation."""
        text = "Công ty không được làm điều này"
        has_negation, scope = planner.detect_negation(text)

        assert has_negation is True
        assert scope is not None

    def test_detect_negation_cam(self, planner: LegalQueryPlanner) -> None:
        """Test detecting 'cấm' (prohibition) negation."""
        text = "Cấm hành vi này trong hợp đồng"
        has_negation, scope = planner.detect_negation(text)

        assert has_negation is True
        assert scope is not None

    def test_detect_negation_khong_duoc(self, planner: LegalQueryPlanner) -> None:
        """Test detecting 'không được' (not allowed) negation."""
        text = "NgườI lao động không được vi phạm quy định"
        has_negation, scope = planner.detect_negation(text)

        assert has_negation is True
        assert "vi phạm quy định" in scope.lower()

    def test_detect_negation_nghiem_cam(self, planner: LegalQueryPlanner) -> None:
        """Test detecting 'nghiêm cấm' (strictly prohibited) negation."""
        text = "Nghiêm cấm mọi hành vi gian lận"
        has_negation, scope = planner.detect_negation(text)

        assert has_negation is True
        assert scope is not None

    def test_detect_negation_scope_extraction(self, planner: LegalQueryPlanner) -> None:
        """Test that negation scope is correctly extracted."""
        text = "Bên A không được chấm dứt hợp đồng trước thờI hạn"
        has_negation, scope = planner.detect_negation(text)

        assert has_negation is True
        assert "chấm dứt" in scope.lower()

    def test_detect_no_negation(self, planner: LegalQueryPlanner) -> None:
        """Test text without negation."""
        text = "Công ty có quyền ký kết hợp đồng"
        has_negation, scope = planner.detect_negation(text)

        assert has_negation is False
        assert scope is None


class TestQueryPlannerExtractCitations:
    """Test QueryPlanner.extract_citations() method."""

    @pytest.fixture
    def planner(self) -> LegalQueryPlanner:
        return LegalQueryPlanner()

    def test_extract_article_citation(self, planner: LegalQueryPlanner) -> None:
        """Test extracting article citations (Điều)."""
        text = "Theo Điều 46 của Luật Doanh nghiệp"
        citations = planner.extract_citations(text)

        assert "Điều 46" in citations

    def test_extract_law_year_citation(self, planner: LegalQueryPlanner) -> None:
        """Test extracting law with year citations."""
        text = "Luật Lao động năm 2019 quy định"
        citations = planner.extract_citations(text)

        assert "Luật Lao động năm 2019" in citations

    def test_extract_decree_citation(self, planner: LegalQueryPlanner) -> None:
        """Test extracting decree citations."""
        text = "Theo Nghị định 145/2020/NĐ-CP"
        citations = planner.extract_citations(text)

        assert "Nghị định 145/2020/NĐ-CP" in citations

    def test_extract_circular_citation(self, planner: LegalQueryPlanner) -> None:
        """Test extracting circular citations."""
        text = "Thông tư 10/2020/TT-BLĐTBXH quy định"
        citations = planner.extract_citations(text)

        assert "Thông tư 10/2020/TT-BLĐTBXH" in citations

    def test_extract_subsection_citation(self, planner: LegalQueryPlanner) -> None:
        """Test extracting subsection (Khoản) citations."""
        text = "Khoản 1 Điều 46 quy định rõ"
        citations = planner.extract_citations(text)

        assert "Khoản 1" in citations

    def test_extract_multiple_citations(self, planner: LegalQueryPlanner) -> None:
        """Test extracting multiple citations from text."""
        text = "Điều 46 và Điều 47 của Luật Doanh nghiệp năm 2020"
        citations = planner.extract_citations(text)

        assert "Điều 46" in citations
        assert "Điều 47" in citations
        assert "Luật Doanh nghiệp năm 2020" in citations

    def test_extract_no_citations(self, planner: LegalQueryPlanner) -> None:
        """Test text with no citations."""
        text = "Công ty có bao nhiêu thành viên?"
        citations = planner.extract_citations(text)

        assert citations == []

    def test_extract_duplicate_citations(self, planner: LegalQueryPlanner) -> None:
        """Test that duplicate citations are removed."""
        text = "Điều 46 và Điều 46 quy định"
        citations = planner.extract_citations(text)

        # Should only have one "Điều 46"
        assert citations.count("Điều 46") == 1


class TestQueryPlannerRouteStrategy:
    """Test QueryPlanner.classify_strategy() method for routing."""

    @pytest.fixture
    def planner(self) -> LegalQueryPlanner:
        return LegalQueryPlanner()

    def test_route_citation_strategy(self, planner: LegalQueryPlanner) -> None:
        """Test CITATION routing when citations are present."""
        strategy = planner.classify_strategy(
            has_negation=False,
            citations=["Điều 46"]
        )
        assert strategy == QueryStrategy.CITATION

    def test_route_negation_strategy(self, planner: LegalQueryPlanner) -> None:
        """Test NEGATION routing when negation detected but no citations."""
        strategy = planner.classify_strategy(
            has_negation=True,
            citations=[]
        )
        assert strategy == QueryStrategy.NEGATION

    def test_route_semantic_strategy(self, planner: LegalQueryPlanner) -> None:
        """Test SEMANTIC routing as default."""
        strategy = planner.classify_strategy(
            has_negation=False,
            citations=[]
        )
        assert strategy == QueryStrategy.SEMANTIC

    def test_route_citation_over_negation(self, planner: LegalQueryPlanner) -> None:
        """Test that CITATION takes priority over NEGATION."""
        strategy = planner.classify_strategy(
            has_negation=True,
            citations=["Điều 46"]
        )
        # Citations take priority
        assert strategy == QueryStrategy.CITATION


class TestQueryPlannerAlias:
    """Test that QueryPlanner is an alias for LegalQueryPlanner."""

    def test_query_planner_alias(self) -> None:
        """Test that QueryPlanner is the same as LegalQueryPlanner."""
        assert QueryPlanner is LegalQueryPlanner
