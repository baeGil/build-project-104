"""Legal clause verification against regulations."""
from __future__ import annotations

import re
import time
from typing import Any

from prometheus_client import Histogram

from packages.common.config import Settings
from packages.common.types import VerificationLevel

# Prometheus metrics
verification_duration_seconds = Histogram(
    "verification_duration_seconds",
    "Time spent on clause verification",
    ["method"],  # rule_based or llm
)


class LegalVerifier:
    """
    Scores clause-regulation pairs with deterministic classification.
    Two-stage: rule-based fast path + LLM for nuanced cases.
    
    Output: entailed | contradicted | partially_supported | no_reference
    Target: 50-100ms
    """
    
    # Vietnamese negation keywords
    NEGATION_WORDS = [
        "không", "cấm", "nghiêm cấm", "không được", "không thể", 
        "không bao giờ", "chưa", "chẳng", "đừng"
    ]
    
    # Number patterns for Vietnamese text
    NUMBER_PATTERNS = [
        r'\d+\s*(?:năm|tháng|ngày|giờ|phút)',  # Time units
        r'\d+[\d\s]*(?:triệu|tỷ|nghìn|ngàn|đồng|VNĐ|\$|%)',  # Money/percent
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # Dates
        r'\d{2}/\d{2}/\d{4}',  # Standard date format
        r'\d+\.\d+',  # Decimals
        r'\d+%',  # Percentages
    ]
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._llm_client = None  # Lazy init
        self._cache: dict[str, dict] = {}  # In-memory cache for verification results
    
    @property
    def llm_client(self):
        """Lazy-init LLM client (OpenAI-compatible: OpenRouter, Ollama, etc.)."""
        if self._llm_client is None:
            import openai
            self._llm_client = openai.AsyncOpenAI(
                base_url=self.settings.llm_base_url,
                api_key=self.settings.llm_api_key or "no-key",
            )
        return self._llm_client
    
    async def verify(
        self,
        clause: str,
        regulation: str,
        context: str = "",
    ) -> dict[str, Any]:
        """
        Verify clause against regulation.
        
        Returns:
            {
                level: VerificationLevel,
                confidence: float,
                reasoning: str,
                method: str
            }
        """
        start_time = time.time()
        
        # Create cache key
        cache_key = f"{hash(clause)}:{hash(regulation)}"
        if cache_key in self._cache:
            result = self._cache[cache_key].copy()
            result["latency_ms"] = (time.time() - start_time) * 1000
            return result
        
        # Stage 1: Rule-based fast path
        rule_result = self._rule_based_score(clause, regulation)
        if rule_result is not None:
            with verification_duration_seconds.labels(method="rule_based").time():
                result = {
                    "level": rule_result,
                    "confidence": 0.9 if rule_result in [VerificationLevel.ENTAILED, VerificationLevel.CONTRADICTED] else 0.7,
                    "reasoning": f"Rule-based detection: {rule_result.value}",
                    "method": "rule_based",
                }
                self._cache[cache_key] = result.copy()
                result["latency_ms"] = (time.time() - start_time) * 1000
                return result
        
        # Stage 2: LLM-based verification for nuanced cases
        with verification_duration_seconds.labels(method="llm").time():
            llm_result = await self._llm_score(clause, regulation, context)
            llm_result["method"] = "llm"
            self._cache[cache_key] = llm_result.copy()
            llm_result["latency_ms"] = (time.time() - start_time) * 1000
            return llm_result
    
    def _rule_based_score(self, clause: str, regulation: str) -> VerificationLevel | None:
        """
        Fast rule-based heuristics (< 10ms).
        Returns 'entailed'/'contradicted' for obvious cases, None for inconclusive.
        
        Rules:
        - Exact phrase containment -> entailed
        - Negation mismatch (one has "không/cấm", other doesn't in same context) -> contradicted
        - Number mismatch (different amounts, dates, percentages) -> contradicted
        """
        # Handle None or empty inputs
        if not clause or not regulation:
            return None
        clause_lower = clause.lower().strip()
        regulation_lower = regulation.lower().strip()
        
        # Rule 1: Exact phrase containment (substring match for key phrases)
        # Extract key phrases (sentences or clauses) from the contract clause
        key_phrases = self._extract_key_phrases(clause_lower)
        for phrase in key_phrases:
            if len(phrase) > 20 and phrase in regulation_lower:
                return VerificationLevel.ENTAILED
        
        # Rule 2: Negation mismatch detection
        clause_has_negation = self._has_negation(clause_lower)
        regulation_has_negation = self._has_negation(regulation_lower)
        
        if clause_has_negation != regulation_has_negation:
            # Check if the content is otherwise similar
            similarity = self._calculate_similarity(clause_lower, regulation_lower)
            if similarity > 0.6:
                return VerificationLevel.CONTRADICTED
        
        # Rule 3: Number mismatch detection
        clause_numbers = self._extract_numbers(clause_lower)
        regulation_numbers = self._extract_numbers(regulation_lower)
        
        if clause_numbers and regulation_numbers:
            # Check for overlapping numbers with mismatch
            common_numbers = set(clause_numbers) & set(regulation_numbers)
            if not common_numbers and len(clause_numbers) > 0 and len(regulation_numbers) > 0:
                # Both have numbers but none match - potential contradiction
                similarity = self._calculate_similarity(clause_lower, regulation_lower)
                if similarity > 0.5:
                    return VerificationLevel.CONTRADICTED
        
        # Inconclusive - need LLM
        return None
    
    def _extract_key_phrases(self, text: str) -> list[str]:
        """Extract key phrases from text for matching."""
        # Split by common delimiters
        phrases = re.split(r'[;\.\n]', text)
        return [p.strip() for p in phrases if len(p.strip()) > 10]
    
    def _has_negation(self, text: str) -> bool:
        """Check if text contains negation words."""
        return any(neg in text for neg in self.NEGATION_WORDS)
    
    def _extract_numbers(self, text: str) -> list[str]:
        """Extract numbers and quantities from text."""
        numbers = []
        for pattern in self.NUMBER_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            numbers.extend(matches)
        return numbers
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple word overlap similarity."""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0
    
    async def _llm_score(
        self, clause: str, regulation: str, context: str
    ) -> dict[str, Any]:
        """
        LLM-based verification via Groq API for nuanced cases.
        Uses structured prompt for deterministic output.
        Temperature=0 for reproducibility.
        """
        prompt = self._build_verification_prompt(clause, regulation, context)
        
        try:
            response = await self._call_llm(
                prompt,
                temperature=0,
                max_tokens=200,
            )
            return self._parse_llm_response(response)
        except Exception as e:
            # Fallback: return no_reference with error info
            return {
                "level": VerificationLevel.NO_REFERENCE,
                "confidence": 0.0,
                "reasoning": f"Verification failed: {str(e)}",
            }
    
    def _build_verification_prompt(self, clause: str, regulation: str, context: str) -> str:
        """Build structured prompt for LLM verification."""
        prompt = f"""You are a legal verification system for Vietnamese law. Analyze whether the contract clause complies with the regulation.

Contract Clause:
"""
        prompt += clause
        prompt += f"""

Regulation:
"""
        prompt += regulation
        
        if context:
            prompt += f"""

Additional Context:
"""
            prompt += context
        
        prompt += """

Analyze the relationship between the clause and regulation. Respond in this exact format:

LEVEL: [entailed|contradicted|partially_supported|no_reference]
CONFIDENCE: [0.0-1.0]
REASONING: [Brief explanation in English]

Definitions:
- entailed: The clause fully complies with and is supported by the regulation
- contradicted: The clause violates or conflicts with the regulation
- partially_supported: The clause partially complies but has gaps or ambiguities
- no_reference: The regulation does not address this clause topic

Respond only with the structured format above."""
        return prompt
    
    async def _call_llm(
        self, prompt: str, temperature: float, max_tokens: int
    ) -> str:
        """Call LLM via OpenAI-compatible API (OpenRouter, Ollama, etc.)."""
        model = self.settings.llm_model
        last_error = None
        try:
            response = await self.llm_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_completion_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            last_error = e
            raise
        
        # Unreachable but satisfies linter
        raise last_error or Exception("LLM API call failed")
    
    def _parse_llm_response(self, response_text: str) -> dict[str, Any]:
        """Parse structured LLM response into verification result."""
        response_text = response_text.strip()
        
        # Default values
        level = VerificationLevel.NO_REFERENCE
        confidence = 0.5
        reasoning = "Unable to parse LLM response"
        
        # Parse LEVEL
        level_match = re.search(r'LEVEL:\s*(\w+)', response_text, re.IGNORECASE)
        if level_match:
            level_str = level_match.group(1).lower()
            level_map = {
                "entailed": VerificationLevel.ENTAILED,
                "contradicted": VerificationLevel.CONTRADICTED,
                "partially_supported": VerificationLevel.PARTIALLY_SUPPORTED,
                "partially supported": VerificationLevel.PARTIALLY_SUPPORTED,
                "no_reference": VerificationLevel.NO_REFERENCE,
                "no reference": VerificationLevel.NO_REFERENCE,
            }
            level = level_map.get(level_str, VerificationLevel.NO_REFERENCE)
        
        # Parse CONFIDENCE
        confidence_match = re.search(r'CONFIDENCE:\s*(-?\d+\.?\d*)', response_text, re.IGNORECASE)
        if confidence_match:
            try:
                confidence = float(confidence_match.group(1))
                confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
            except ValueError:
                pass
        
        # Parse REASONING
        reasoning_match = re.search(r'REASONING:\s*(.+?)(?:\n\n|$)', response_text, re.IGNORECASE | re.DOTALL)
        if reasoning_match:
            reasoning = reasoning_match.group(1).strip()
        
        return {
            "level": level,
            "confidence": confidence,
            "reasoning": reasoning,
        }
