"""Tests for LegalGenerator in packages/reasoning/generator.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.common.config import Settings
from packages.common.types import (
    Citation,
    EvidencePack,
    RetrievedDocument,
    ReviewFinding,
    RiskLevel,
    VerificationLevel,
)
from packages.reasoning.generator import LegalGenerator


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for testing."""
    settings = MagicMock(spec=Settings)
    settings.groq_api_key = "test-api-key"
    settings.groq_model_primary = "llama-3.1-8b-instant"
    settings.groq_model_fallback = "llama-3.3-70b-versatile"
    return settings


@pytest.fixture
def generator(mock_settings: Settings) -> LegalGenerator:
    """Create a LegalGenerator instance for testing."""
    return LegalGenerator(mock_settings)


@pytest.fixture
def mock_groq_response() -> MagicMock:
    """Create a mock Groq API response."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = """RATIONALE: This clause complies with Article 46 of the Enterprise Law 2020.
RISK_LEVEL: none
"""
    return response


class TestGenerateFinding:
    """Tests for LegalGenerator.generate_finding method."""

    async def test_generate_finding_success(
        self,
        generator: LegalGenerator,
        sample_evidence_pack: EvidencePack,
        mock_groq_response: MagicMock,
    ) -> None:
        """Test successful finding generation with primary model."""
        with patch.object(generator, "_groq_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_groq_response)

            result = await generator.generate_finding(sample_evidence_pack)

            assert isinstance(result, ReviewFinding)
            assert result.clause_text == sample_evidence_pack.clause
            assert result.risk_level == RiskLevel.NONE
            assert "Article 46" in result.rationale
            assert result.latency_ms > 0

    async def test_generate_finding_uses_cache(
        self,
        generator: LegalGenerator,
        sample_evidence_pack: EvidencePack,
        mock_groq_response: MagicMock,
    ) -> None:
        """Test that caching works for repeated findings."""
        with patch.object(generator, "_groq_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_groq_response)

            # First call
            result1 = await generator.generate_finding(sample_evidence_pack)
            # Second call should use cache
            result2 = await generator.generate_finding(sample_evidence_pack)

            # Should only call API once
            assert mock_client.chat.completions.create.call_count == 1
            assert result1.clause_text == result2.clause_text

    async def test_generate_finding_fallback_model(
        self,
        generator: LegalGenerator,
        sample_evidence_pack: EvidencePack,
        mock_groq_response: MagicMock,
    ) -> None:
        """Test fallback to secondary model on rate limit error."""
        rate_limit_error = Exception("Rate limit exceeded: 429")

        with patch.object(generator, "_groq_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=[rate_limit_error, mock_groq_response]
            )

            result = await generator.generate_finding(sample_evidence_pack)

            assert isinstance(result, ReviewFinding)
            assert mock_client.chat.completions.create.call_count == 2
            # Verify both models were tried
            calls = mock_client.chat.completions.create.call_args_list
            assert calls[0][1]["model"] == generator.settings.groq_model_primary
            assert calls[1][1]["model"] == generator.settings.groq_model_fallback

    async def test_generate_finding_error_handling(
        self,
        generator: LegalGenerator,
        sample_evidence_pack: EvidencePack,
    ) -> None:
        """Test error handling when both models fail."""
        with patch.object(generator, "_groq_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("Service unavailable")
            )

            result = await generator.generate_finding(sample_evidence_pack)

            assert isinstance(result, ReviewFinding)
            assert "Generation failed" in result.rationale
            assert result.revision_suggestion is not None
            assert "review manually" in result.revision_suggestion.lower()


class TestGenerateReviewSummary:
    """Tests for LegalGenerator.generate_review_summary method."""

    async def test_generate_summary_success(
        self,
        generator: LegalGenerator,
        sample_review_finding: ReviewFinding,
    ) -> None:
        """Test successful summary generation."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Executive summary of contract review."

        with patch.object(generator, "_groq_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            findings = [sample_review_finding]
            result = await generator.generate_review_summary(findings)

            assert isinstance(result, str)
            assert "Executive summary" in result

    async def test_generate_summary_empty_findings(
        self,
        generator: LegalGenerator,
    ) -> None:
        """Test summary generation with empty findings list."""
        result = await generator.generate_review_summary([])

        assert result == "No findings to summarize."

    async def test_generate_summary_error_handling(
        self,
        generator: LegalGenerator,
        sample_review_finding: ReviewFinding,
    ) -> None:
        """Test error handling in summary generation."""
        with patch.object(generator, "_groq_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("API error")
            )

            findings = [sample_review_finding]
            result = await generator.generate_review_summary(findings)

            assert "Summary generation failed" in result
            assert "high" in result.lower() or "Risk distribution" in result


class TestGenerateChatAnswer:
    """Tests for LegalGenerator.generate_chat_answer method."""

    async def test_generate_chat_answer_success(
        self,
        generator: LegalGenerator,
        sample_evidence_pack: EvidencePack,
    ) -> None:
        """Test successful chat answer generation."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "According to Article 46..."

        with patch.object(generator, "_groq_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await generator.generate_chat_answer(
                query="How many members can an LLC have?",
                evidence_pack=sample_evidence_pack,
            )

            assert result.answer == "According to Article 46..."
            assert result.citations == sample_evidence_pack.citations
            assert result.latency_ms > 0

    async def test_generate_chat_answer_error(
        self,
        generator: LegalGenerator,
        sample_evidence_pack: EvidencePack,
    ) -> None:
        """Test chat answer error handling."""
        with patch.object(generator, "_groq_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("API error")
            )

            result = await generator.generate_chat_answer(
                query="Test question?",
                evidence_pack=sample_evidence_pack,
            )

            assert "apologize" in result.answer.lower()
            assert "error" in result.answer.lower()


class TestStreamChatAnswer:
    """Tests for LegalGenerator.stream_chat_answer method."""

    async def test_stream_chat_answer_success(
        self,
        generator: LegalGenerator,
        sample_evidence_pack: EvidencePack,
    ) -> None:
        """Test successful streaming chat answer."""
        # Create mock chunks
        chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello "))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="world"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="!"))]),
        ]

        async def mock_stream():
            for chunk in chunks:
                yield chunk

        with patch.object(generator, "_groq_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            tokens = []
            async for token in generator.stream_chat_answer(
                query="Test?",
                evidence_pack=sample_evidence_pack,
            ):
                tokens.append(token)

            assert "".join(tokens) == "Hello world!"

    async def test_stream_chat_answer_fallback(
        self,
        generator: LegalGenerator,
        sample_evidence_pack: EvidencePack,
    ) -> None:
        """Test streaming with fallback on rate limit."""
        rate_limit_error = Exception("429 rate limit")

        chunks = [MagicMock(choices=[MagicMock(delta=MagicMock(content="Fallback"))])]

        async def mock_stream():
            for chunk in chunks:
                yield chunk

        with patch.object(generator, "_groq_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=[rate_limit_error, mock_stream()]
            )

            tokens = []
            async for token in generator.stream_chat_answer(
                query="Test?",
                evidence_pack=sample_evidence_pack,
            ):
                tokens.append(token)

            assert tokens == ["Fallback"]
            assert mock_client.chat.completions.create.call_count == 2

    async def test_stream_chat_answer_both_models_fail(
        self,
        generator: LegalGenerator,
        sample_evidence_pack: EvidencePack,
    ) -> None:
        """Test streaming when both models fail."""
        with patch.object(generator, "_groq_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=[
                    Exception("429 rate limit"),
                    Exception("429 rate limit"),
                ]
            )

            tokens = []
            async for token in generator.stream_chat_answer(
                query="Test?",
                evidence_pack=sample_evidence_pack,
            ):
                tokens.append(token)

            assert len(tokens) == 1
            assert "Service temporarily unavailable" in tokens[0]


class TestCallGroqWithFallback:
    """Tests for LegalGenerator._call_groq_with_fallback method."""

    async def test_primary_model_success(
        self,
        generator: LegalGenerator,
    ) -> None:
        """Test successful call with primary model."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response from primary model"

        with patch.object(generator, "_groq_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await generator._call_groq_with_fallback(
                prompt="Test prompt",
                temperature=0.1,
                max_tokens=100,
            )

            assert result == "Response from primary model"
            mock_client.chat.completions.create.assert_called_once()

    async def test_fallback_on_rate_limit(
        self,
        generator: LegalGenerator,
    ) -> None:
        """Test fallback to secondary model on rate limit."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response from fallback model"

        with patch.object(generator, "_groq_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=[
                    Exception("Rate limit: 429"),
                    mock_response,
                ]
            )

            result = await generator._call_groq_with_fallback(
                prompt="Test prompt",
                temperature=0.1,
                max_tokens=100,
            )

            assert result == "Response from fallback model"
            assert mock_client.chat.completions.create.call_count == 2

    async def test_non_rate_limit_error_propagates(
        self,
        generator: LegalGenerator,
    ) -> None:
        """Test that non-rate-limit errors propagate immediately."""
        with patch.object(generator, "_groq_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("Authentication failed")
            )

            with pytest.raises(Exception, match="Authentication failed"):
                await generator._call_groq_with_fallback(
                    prompt="Test prompt",
                    temperature=0.1,
                    max_tokens=100,
                )


class TestParseFindingResponse:
    """Tests for LegalGenerator._parse_finding_response method."""

    def test_parse_complete_response(self, generator: LegalGenerator) -> None:
        """Test parsing a complete response with all fields."""
        response = """RATIONALE: This clause violates Article 46.
RISK_LEVEL: high
REVISION_SUGGESTION: Add proper member count specification.
NEGOTIATION_NOTE: Negotiate for clarity on member requirements.
"""
        result = generator._parse_finding_response(response)

        assert result["rationale"] == "This clause violates Article 46."
        assert result["risk_level"] == RiskLevel.HIGH
        assert result["revision_suggestion"] == "Add proper member count specification."
        assert result["negotiation_note"] == "Negotiate for clarity on member requirements."

    def test_parse_partial_response(self, generator: LegalGenerator) -> None:
        """Test parsing a partial response with only rationale."""
        response = "RATIONALE: This clause is compliant."
        result = generator._parse_finding_response(response)

        assert result["rationale"] == "This clause is compliant."
        assert "risk_level" not in result

    def test_parse_risk_levels(self, generator: LegalGenerator) -> None:
        """Test parsing different risk level values."""
        for risk_str, expected_level in [
            ("high", RiskLevel.HIGH),
            ("medium", RiskLevel.MEDIUM),
            ("low", RiskLevel.LOW),
            ("none", RiskLevel.NONE),
        ]:
            response = f"RISK_LEVEL: {risk_str}"
            result = generator._parse_finding_response(response)
            assert result["risk_level"] == expected_level

    def test_parse_case_insensitive(self, generator: LegalGenerator) -> None:
        """Test that parsing is case insensitive."""
        response = """rationale: Lower case rationale.
risk_level: MEDIUM
"""
        result = generator._parse_finding_response(response)

        assert result["rationale"] == "Lower case rationale."
        assert result["risk_level"] == RiskLevel.MEDIUM
