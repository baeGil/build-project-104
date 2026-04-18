"""Tests for the LegalVerifier class."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.common.config import Settings
from packages.common.types import VerificationLevel
from packages.reasoning.verifier import LegalVerifier


class TestLegalVerifierInit:
    """Test LegalVerifier initialization."""

    @pytest.fixture
    def settings(self) -> Settings:
        """Create test settings."""
        return Settings(
            llm_base_url="http://localhost:11434/v1",
            llm_api_key="test-key",
            llm_model="test-model",
        )

    def test_init(self, settings: Settings) -> None:
        """Test verifier initialization."""
        verifier = LegalVerifier(settings)

        assert verifier.settings == settings
        assert verifier._llm_client is None
        assert verifier._cache == {}

    def test_ollama_client_lazy_init(self, settings: Settings) -> None:
        """Test that LLM client is lazily initialized."""
        verifier = LegalVerifier(settings)
        assert verifier._llm_client is None

        # Access the property
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            client = verifier.llm_client
            assert client is not None
            mock_openai.assert_called_once_with(
                base_url="http://localhost:11434/v1",
                api_key="test-key",
            )


class TestLegalVerifierVerify:
    """Test LegalVerifier.verify() method."""

    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(
            llm_base_url="https://openrouter.ai/api/v1",
            llm_api_key="test-key",
            llm_model="test-model",
        )

    @pytest.fixture
    def verifier(self, settings: Settings) -> LegalVerifier:
        return LegalVerifier(settings)

    async def test_verify_cache_hit(self, verifier: LegalVerifier) -> None:
        """Test that cached results are returned immediately."""
        clause = "Test clause"
        regulation = "Test regulation"
        cache_key = f"{hash(clause)}:{hash(regulation)}"

        # Pre-populate cache
        cached_result = {
            "level": VerificationLevel.ENTAILED,
            "confidence": 0.95,
            "reasoning": "Cached reasoning",
            "method": "rule_based",
        }
        verifier._cache[cache_key] = cached_result

        result = await verifier.verify(clause, regulation)

        assert result["level"] == VerificationLevel.ENTAILED
        assert result["confidence"] == 0.95
        assert "latency_ms" in result

    async def test_verify_rule_based_entailed(self, verifier: LegalVerifier) -> None:
        """Test rule-based verification returning ENTAILED."""
        clause = "This is a very long clause text that should match"
        regulation = "This is a very long clause text that should match with the regulation"

        with patch.object(verifier, "_rule_based_score", return_value=VerificationLevel.ENTAILED):
            result = await verifier.verify(clause, regulation)

        assert result["level"] == VerificationLevel.ENTAILED
        assert result["confidence"] == 0.9
        assert result["method"] == "rule_based"

    async def test_verify_rule_based_contradicted(self, verifier: LegalVerifier) -> None:
        """Test rule-based verification returning CONTRADICTED."""
        clause = "Test clause"
        regulation = "Test regulation"

        with patch.object(verifier, "_rule_based_score", return_value=VerificationLevel.CONTRADICTED):
            result = await verifier.verify(clause, regulation)

        assert result["level"] == VerificationLevel.CONTRADICTED
        assert result["confidence"] == 0.9
        assert result["method"] == "rule_based"

    async def test_verify_falls_back_to_llm(self, verifier: LegalVerifier) -> None:
        """Test that inconclusive rule-based falls back to LLM."""
        clause = "Test clause"
        regulation = "Test regulation"

        with patch.object(verifier, "_rule_based_score", return_value=None):
            with patch.object(verifier, "_llm_score", new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = {
                    "level": VerificationLevel.PARTIALLY_SUPPORTED,
                    "confidence": 0.7,
                    "reasoning": "LLM reasoning",
                }
                result = await verifier.verify(clause, regulation)

        assert result["level"] == VerificationLevel.PARTIALLY_SUPPORTED
        assert result["method"] == "llm"

    def test_rule_based_empty_inputs(self, verifier: LegalVerifier) -> None:
        """Test rule-based with empty inputs returns None."""
        assert verifier._rule_based_score("", "regulation") is None
        assert verifier._rule_based_score("clause", "") is None
        assert verifier._rule_based_score(None, "regulation") is None  # type: ignore[arg-type]

    def test_rule_based_exact_phrase_match(self, verifier: LegalVerifier) -> None:
        """Test ENTAILED when exact phrase is found in regulation."""
        clause = "This is a very long phrase that should be contained"
        regulation = "This is a very long phrase that should be contained in the regulation"

        result = verifier._rule_based_score(clause, regulation)
        assert result == VerificationLevel.ENTAILED

    def test_rule_based_negation_mismatch(self, verifier: LegalVerifier) -> None:
        """Test CONTRADICTED on negation mismatch with similar content."""
        clause = "Công ty không được phép chấm dứt hợp đồng"
        regulation = "Công ty được phép chấm dứt hợp đồng"

        result = verifier._rule_based_score(clause, regulation)
        assert result == VerificationLevel.CONTRADICTED

    def test_rule_based_no_negation_mismatch(self, verifier: LegalVerifier) -> None:
        """Test no contradiction when both have negation."""
        clause = "Công ty không được phép làm điều này"
        regulation = "Công ty không được phép làm điều kia"

        result = verifier._rule_based_score(clause, regulation)
        # Both have negation, so no contradiction based on negation alone
        assert result is None

    def test_rule_based_number_mismatch(self, verifier: LegalVerifier) -> None:
        """Test CONTRADICTED on number mismatch."""
        clause = "ThờI hạn 30 ngày"
        regulation = "ThờI hạn 60 ngày"

        result = verifier._rule_based_score(clause, regulation)
        assert result == VerificationLevel.CONTRADICTED

    def test_rule_based_inconclusive(self, verifier: LegalVerifier) -> None:
        """Test None when no clear rule applies."""
        clause = "Some clause"
        regulation = "Some different regulation"

        result = verifier._rule_based_score(clause, regulation)
        assert result is None


class TestLegalVerifierLLMVerify:
    """Test LegalVerifier._llm_score() method with mocked Ollama client."""

    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(
            llm_base_url="https://openrouter.ai/api/v1",
            llm_api_key="test-key",
            llm_model="test-model",
        )

    @pytest.fixture
    def verifier(self, settings: Settings) -> LegalVerifier:
        return LegalVerifier(settings)

    async def test_llm_verify_success(self, verifier: LegalVerifier) -> None:
        """Test successful LLM verification."""
        clause = "Test clause"
        regulation = "Test regulation"
        context = "Test context"

        mock_response = """LEVEL: entailed
CONFIDENCE: 0.95
REASONING: The clause fully complies with the regulation."""

        with patch.object(verifier, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            result = await verifier._llm_score(clause, regulation, context)

        assert result["level"] == VerificationLevel.ENTAILED
        assert result["confidence"] == 0.95
        assert "complies" in result["reasoning"].lower()

    async def test_llm_verify_contradicted(self, verifier: LegalVerifier) -> None:
        """Test LLM verification returning contradicted."""
        mock_response = """LEVEL: contradicted
CONFIDENCE: 0.85
REASONING: The clause violates the regulation."""

        with patch.object(verifier, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            result = await verifier._llm_score("clause", "regulation", "")

        assert result["level"] == VerificationLevel.CONTRADICTED
        assert result["confidence"] == 0.85

    async def test_llm_verify_partially_supported(self, verifier: LegalVerifier) -> None:
        """Test LLM verification returning partially_supported."""
        mock_response = """LEVEL: partially_supported
CONFIDENCE: 0.6
REASONING: The clause partially complies."""

        with patch.object(verifier, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            result = await verifier._llm_score("clause", "regulation", "")

        assert result["level"] == VerificationLevel.PARTIALLY_SUPPORTED

    async def test_llm_verify_no_reference(self, verifier: LegalVerifier) -> None:
        """Test LLM verification returning no_reference."""
        mock_response = """LEVEL: no_reference
CONFIDENCE: 0.5
REASONING: The regulation does not address this topic."""

        with patch.object(verifier, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            result = await verifier._llm_score("clause", "regulation", "")

        assert result["level"] == VerificationLevel.NO_REFERENCE

    async def test_llm_verify_error_fallback(self, verifier: LegalVerifier) -> None:
        """Test fallback when LLM call fails."""
        with patch.object(verifier, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = Exception("API Error")
            result = await verifier._llm_score("clause", "regulation", "")

        assert result["level"] == VerificationLevel.NO_REFERENCE
        assert result["confidence"] == 0.0
        assert "Verification failed" in result["reasoning"]


class TestLegalVerifierParseLLMResponse:
    """Test LegalVerifier._parse_llm_response() method."""

    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(llm_model="test-model")

    @pytest.fixture
    def verifier(self, settings: Settings) -> LegalVerifier:
        return LegalVerifier(settings)

    def test_parse_entailed_response(self, verifier: LegalVerifier) -> None:
        """Test parsing entailed response."""
        response = "LEVEL: entailed\nCONFIDENCE: 0.95\nREASONING: Full compliance"
        result = verifier._parse_llm_response(response)

        assert result["level"] == VerificationLevel.ENTAILED
        assert result["confidence"] == 0.95
        assert result["reasoning"] == "Full compliance"

    def test_parse_contradicted_response(self, verifier: LegalVerifier) -> None:
        """Test parsing contradicted response."""
        response = "LEVEL: contradicted\nCONFIDENCE: 0.85\nREASONING: Violation found"
        result = verifier._parse_llm_response(response)

        assert result["level"] == VerificationLevel.CONTRADICTED

    def test_parse_partially_supported_response(self, verifier: LegalVerifier) -> None:
        """Test parsing partially_supported response."""
        response = "LEVEL: partially_supported\nCONFIDENCE: 0.7\nREASONING: Partial match"
        result = verifier._parse_llm_response(response)

        assert result["level"] == VerificationLevel.PARTIALLY_SUPPORTED

    def test_parse_no_reference_response(self, verifier: LegalVerifier) -> None:
        """Test parsing no_reference response."""
        response = "LEVEL: no_reference\nCONFIDENCE: 0.5\nREASONING: Not addressed"
        result = verifier._parse_llm_response(response)

        assert result["level"] == VerificationLevel.NO_REFERENCE

    def test_parse_invalid_level(self, verifier: LegalVerifier) -> None:
        """Test parsing with invalid level defaults to NO_REFERENCE."""
        response = "LEVEL: invalid\nCONFIDENCE: 0.5\nREASONING: Unknown"
        result = verifier._parse_llm_response(response)

        assert result["level"] == VerificationLevel.NO_REFERENCE

    def test_parse_missing_fields(self, verifier: LegalVerifier) -> None:
        """Test parsing with missing fields uses defaults."""
        response = "Some random text"
        result = verifier._parse_llm_response(response)

        assert result["level"] == VerificationLevel.NO_REFERENCE
        assert result["confidence"] == 0.5
        assert "Unable to parse" in result["reasoning"]

    def test_parse_confidence_clamping(self, verifier: LegalVerifier) -> None:
        """Test that confidence is clamped to [0, 1]."""
        response = "LEVEL: entailed\nCONFIDENCE: 1.5\nREASONING: Test"
        result = verifier._parse_llm_response(response)
        assert result["confidence"] == 1.0

        response = "LEVEL: entailed\nCONFIDENCE: -0.5\nREASONING: Test"
        result = verifier._parse_llm_response(response)
        assert result["confidence"] == 0.0


class TestLegalVerifierCallLLM:
    """Test LegalVerifier._call_llm() method."""

    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(
            llm_base_url="https://openrouter.ai/api/v1",
            llm_api_key="test-key",
            llm_model="test-model",
        )

    @pytest.fixture
    def verifier(self, settings: Settings) -> LegalVerifier:
        verifier = LegalVerifier(settings)
        verifier._llm_client = MagicMock()
        return verifier

    async def test_call_success(self, verifier: LegalVerifier) -> None:
        """Test successful call to Ollama model."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Test response"
        verifier.llm_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await verifier._call_llm("prompt", 0.0, 100)

        assert result == "Test response"
        verifier.llm_client.chat.completions.create.assert_called_once()
        call_args = verifier.llm_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "test-model"

    async def test_error_propagates(self, verifier: LegalVerifier) -> None:
        """Test that errors propagate from _call_llm."""
        verifier.llm_client.chat.completions.create = AsyncMock(
            side_effect=Exception("connection refused")
        )

        with pytest.raises(Exception, match="connection refused"):
            await verifier._call_llm("prompt", 0.0, 100)


class TestLegalVerifierHelperMethods:
    """Test LegalVerifier helper methods."""

    @pytest.fixture
    def verifier(self) -> LegalVerifier:
        return LegalVerifier(Settings(llm_model="test-model"))

    def test_extract_key_phrases(self, verifier: LegalVerifier) -> None:
        """Test extracting key phrases from text."""
        text = "First phrase. Second phrase; Third phrase"
        phrases = verifier._extract_key_phrases(text)

        assert len(phrases) >= 2
        assert "First phrase" in phrases

    def test_has_negation(self, verifier: LegalVerifier) -> None:
        """Test negation detection."""
        assert verifier._has_negation("không được phép") is True
        assert verifier._has_negation("cấm hành vi") is True
        assert verifier._has_negation("nghiêm cấm") is True
        assert verifier._has_negation("không thể") is True
        assert verifier._has_negation("được phép") is False

    def test_extract_numbers(self, verifier: LegalVerifier) -> None:
        """Test number extraction from text."""
        text = "30 ngày, 100 triệu đồng, 50%"
        numbers = verifier._extract_numbers(text)

        assert "30 ngày" in numbers
        assert "100 triệu" in str(numbers)
        assert "50%" in numbers

    def test_calculate_similarity(self, verifier: LegalVerifier) -> None:
        """Test similarity calculation."""
        text1 = "công ty tnhh"
        text2 = "công ty tnhh thành viên"
        text3 = "hoàn toàn khác biệt"

        sim1 = verifier._calculate_similarity(text1, text2)
        sim2 = verifier._calculate_similarity(text1, text3)

        assert sim1 > sim2  # More similar texts have higher score
        assert 0 <= sim1 <= 1
        assert 0 <= sim2 <= 1

    def test_calculate_similarity_empty(self, verifier: LegalVerifier) -> None:
        """Test similarity with empty inputs."""
        assert verifier._calculate_similarity("", "text") == 0.0
        assert verifier._calculate_similarity("text", "") == 0.0
        assert verifier._calculate_similarity("", "") == 0.0


class TestVerificationLevelOutcomes:
    """Test VerificationLevel enum values and outcomes."""

    def test_verification_level_values(self) -> None:
        """Test that VerificationLevel has expected values."""
        assert VerificationLevel.ENTAILED.value == "entailed"
        assert VerificationLevel.CONTRADICTED.value == "contradicted"
        assert VerificationLevel.PARTIALLY_SUPPORTED.value == "partially_supported"
        assert VerificationLevel.NO_REFERENCE.value == "no_reference"

    def test_verification_level_comparison(self) -> None:
        """Test VerificationLevel comparison."""
        assert VerificationLevel.ENTAILED == VerificationLevel.ENTAILED
        assert VerificationLevel.ENTAILED != VerificationLevel.CONTRADICTED
