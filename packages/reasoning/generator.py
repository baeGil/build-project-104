"""Legal finding generator using EvidencePack pattern."""
from __future__ import annotations

import time
from typing import Any, AsyncGenerator

from prometheus_client import Histogram

from packages.common.config import Settings
from packages.common.types import (
    Citation,
    ChatAnswer,
    EvidencePack,
    ReviewFinding,
    RiskLevel,
    VerificationLevel,
)

# Prometheus metrics
generation_duration_seconds = Histogram(
    "generation_duration_seconds",
    "Time spent on text generation",
    ["task_type"],  # review, chat, summary
)


class LegalGenerator:
    """
    Generator consumes ONLY pre-assembled EvidencePack.
    It NEVER initiates searches or retrieval.
    Ensures deterministic, auditable reasoning.
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._groq_client = None
        self._cache: dict[str, Any] = {}  # In-memory cache for generation results
    
    @property
    def groq_client(self):
        """Lazy-init Groq client."""
        if self._groq_client is None:
            import groq
            self._groq_client = groq.AsyncGroq(api_key=self.settings.groq_api_key)
        return self._groq_client
    
    async def generate_finding(self, evidence_pack: EvidencePack) -> ReviewFinding:
        """
        Generate a review finding from pre-assembled evidence.
        
        Output includes:
        - rationale (explanation)
        - citations (article references)
        - risk_level (high/medium/low/none)
        - revision_suggestion (if contradicted/partially_supported)
        - negotiation_note (practical advice)
        """
        start_time = time.time()
        
        # Create cache key
        cache_key = f"finding:{hash(evidence_pack.clause)}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            finding = ReviewFinding(**cached)
            finding.latency_ms = (time.time() - start_time) * 1000
            return finding
        
        with generation_duration_seconds.labels(task_type="review").time():
            prompt = self._build_review_prompt(evidence_pack)
            
            try:
                response = await self._call_groq_with_fallback(
                    prompt,
                    temperature=0.1,
                    max_tokens=800,
                )
                parsed = self._parse_finding_response(response)
            except Exception as e:
                # Fallback response on error
                parsed = {
                    "rationale": f"Generation failed: {str(e)}",
                    "risk_level": RiskLevel.HIGH if evidence_pack.verification_level == VerificationLevel.CONTRADICTED else RiskLevel.LOW,
                    "revision_suggestion": "Please review manually due to generation error.",
                    "negotiation_note": "System encountered an error. Manual review recommended.",
                }
            
            # Map verification level to risk level if not provided
            risk_level = parsed.get("risk_level") or self._extract_risk_level(
                evidence_pack.verification_level or VerificationLevel.NO_REFERENCE
            )
            
            finding = ReviewFinding(
                clause_text=evidence_pack.clause,
                clause_index=0,  # Will be set by caller
                verification=evidence_pack.verification_level or VerificationLevel.NO_REFERENCE,
                confidence=evidence_pack.verification_confidence,
                risk_level=risk_level,
                rationale=parsed.get("rationale", "No rationale generated"),
                citations=evidence_pack.citations,
                revision_suggestion=parsed.get("revision_suggestion"),
                negotiation_note=parsed.get("negotiation_note"),
                evidence_pack=evidence_pack,
                latency_ms=(time.time() - start_time) * 1000,
            )
            
            # Cache the finding (as dict for serialization)
            self._cache[cache_key] = finding.model_dump()
            return finding
    
    async def generate_chat_answer(
        self, query: str, evidence_pack: EvidencePack
    ) -> ChatAnswer:
        """Generate chat answer with citations for legal QA."""
        start_time = time.time()
        
        with generation_duration_seconds.labels(task_type="chat").time():
            prompt = self._build_chat_prompt(query, evidence_pack)
            
            try:
                response = await self._call_groq_with_fallback(
                    prompt,
                    temperature=0.1,
                    max_tokens=1000,
                )
                answer_text = response.strip()
            except Exception as e:
                answer_text = f"I apologize, but I encountered an error generating the answer: {str(e)}. Please try again or rephrase your question."
            
            return ChatAnswer(
                answer=answer_text,
                citations=evidence_pack.citations,
                confidence=evidence_pack.verification_confidence,
                evidence_pack=evidence_pack,
                latency_ms=(time.time() - start_time) * 1000,
            )
    
    async def generate_review_summary(
        self, findings: list[ReviewFinding]
    ) -> str:
        """Generate overall contract review summary."""
        if not findings:
            return "No findings to summarize."
        
        with generation_duration_seconds.labels(task_type="summary").time():
            risk_counts = self._build_risk_summary(findings)
            
            # Build summary prompt
            prompt = f"""You are a legal contract review assistant. Summarize the following contract review findings.

Risk Summary:
- High Risk Issues: {risk_counts.get(RiskLevel.HIGH, 0)}
- Medium Risk Issues: {risk_counts.get(RiskLevel.MEDIUM, 0)}
- Low Risk Issues: {risk_counts.get(RiskLevel.LOW, 0)}
- No Risk: {risk_counts.get(RiskLevel.NONE, 0)}

Key Findings:
"""
            
            # Include top findings (high risk first)
            sorted_findings = sorted(
                findings,
                key=lambda f: (
                    0 if f.risk_level == RiskLevel.HIGH else
                    1 if f.risk_level == RiskLevel.MEDIUM else
                    2 if f.risk_level == RiskLevel.LOW else 3
                )
            )
            
            for i, finding in enumerate(sorted_findings[:10], 1):  # Top 10
                prompt += f"\n{i}. [{finding.risk_level.value.upper()}] {finding.clause_text[:100]}...\n"
                prompt += f"   Rationale: {finding.rationale[:150]}...\n"
            
            prompt += """

Provide a concise executive summary (2-3 paragraphs) highlighting:
1. Overall risk assessment
2. Key areas of concern
3. Recommended actions

Summary:"""
            
            try:
                response = await self._call_groq_with_fallback(
                    prompt,
                    temperature=0.2,
                    max_tokens=500,
                )
                return response.strip()
            except Exception as e:
                return f"Summary generation failed: {str(e)}. Risk distribution: {risk_counts}"
    
    async def stream_chat_answer(
        self, query: str, evidence_pack: EvidencePack
    ) -> AsyncGenerator[str, None]:
        """
        Async generator yielding tokens for SSE streaming.
        Uses Groq streaming API.
        """
        prompt = self._build_chat_prompt(query, evidence_pack)
        
        models = [
            self.settings.groq_model_primary,
            self.settings.groq_model_fallback,
        ]
        
        last_error = None
        for model in models:
            try:
                stream = await self.groq_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=1000,
                    stream=True,
                )
                
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                
                return  # Success, exit
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                if "rate limit" in error_str or "ratelimit" in error_str or "429" in error_str:
                    continue  # Try fallback
                
                # Yield error message
                yield f"\n\n[Error: {str(e)}]"
                return
        
        # Both models failed
        yield f"\n\n[Error: Service temporarily unavailable. Please try again later.]"
    
    def _build_review_prompt(self, evidence_pack: EvidencePack) -> str:
        """Build structured prompt from EvidencePack for review."""
        prompt = """You are a Vietnamese legal contract review assistant. Analyze the contract clause against the provided legal evidence.

"""
        prompt += self._format_evidence_context(evidence_pack)
        
        prompt += f"""

Contract Clause to Review:
"{evidence_pack.clause}"

Verification Status: {evidence_pack.verification_level.value if evidence_pack.verification_level else "unknown"}

Provide your analysis in this exact format:

RATIONALE: [Clear explanation of whether the clause complies with regulations and why]
RISK_LEVEL: [high|medium|low|none]
"""
        
        if evidence_pack.verification_level in [VerificationLevel.CONTRADICTED, VerificationLevel.PARTIALLY_SUPPORTED]:
            prompt += """REVISION_SUGGESTION: [Specific suggestion on how to revise the clause to comply with regulations]
NEGOTIATION_NOTE: [Practical advice for contract negotiation based on this finding]
"""
        
        prompt += """
Keep your response structured and concise."""
        return prompt
    
    def _build_chat_prompt(self, query: str, evidence_pack: EvidencePack) -> str:
        """Build prompt for chat answer."""
        prompt = """You are a Vietnamese legal assistant. Answer the user's question based on the provided legal evidence.

"""
        prompt += self._format_evidence_context(evidence_pack)
        
        prompt += f"""

User Question: {query}

Provide a clear, accurate answer based on the legal evidence above. Include specific citations to relevant laws or articles when possible. If the evidence doesn't fully answer the question, acknowledge the limitations.

Answer:"""
        return prompt
    
    def _extract_risk_level(self, verification: VerificationLevel) -> RiskLevel:
        """Map verification level to risk level."""
        mapping = {
            VerificationLevel.ENTAILED: RiskLevel.NONE,
            VerificationLevel.CONTRADICTED: RiskLevel.HIGH,
            VerificationLevel.PARTIALLY_SUPPORTED: RiskLevel.MEDIUM,
            VerificationLevel.NO_REFERENCE: RiskLevel.LOW,
        }
        return mapping.get(verification, RiskLevel.LOW)
    
    def _format_evidence_context(self, evidence_pack: EvidencePack) -> str:
        """Format evidence documents into prompt context string."""
        context = "Legal Evidence:\n"
        
        # Add retrieved documents
        if evidence_pack.retrieved_documents:
            context += "\nRetrieved Legal Documents:\n"
            for i, doc in enumerate(evidence_pack.retrieved_documents[:5], 1):
                context += f"\n[{i}] {doc.title or doc.doc_id}\n"
                context += f"Content: {doc.content[:500]}...\n"
                if doc.metadata:
                    context += f"Metadata: {doc.metadata}\n"
        
        # Add context documents
        if evidence_pack.context_documents:
            context += "\nAdditional Context:\n"
            for doc in evidence_pack.context_documents[:3]:
                context += f"\n- {doc.title or doc.doc_id} ({doc.relation_type}): {doc.content[:300]}...\n"
        
        # Add citations
        if evidence_pack.citations:
            context += "\nCitations:\n"
            for citation in evidence_pack.citations:
                context += f"- {citation.article_id} ({citation.law_id}): {citation.quote[:200]}...\n"
        
        return context
    
    def _parse_finding_response(self, response_text: str) -> dict[str, Any]:
        """Parse LLM response for finding generation."""
        import re
        
        result: dict[str, Any] = {}
        
        # Parse RATIONALE
        rationale_match = re.search(r'RATIONALE:\s*(.+?)(?=\n\w+:|$)', response_text, re.DOTALL | re.IGNORECASE)
        if rationale_match:
            result["rationale"] = rationale_match.group(1).strip()
        
        # Parse RISK_LEVEL
        risk_match = re.search(r'RISK_LEVEL:\s*(\w+)', response_text, re.IGNORECASE)
        if risk_match:
            risk_str = risk_match.group(1).lower()
            risk_map = {
                "high": RiskLevel.HIGH,
                "medium": RiskLevel.MEDIUM,
                "low": RiskLevel.LOW,
                "none": RiskLevel.NONE,
            }
            result["risk_level"] = risk_map.get(risk_str, RiskLevel.LOW)
        
        # Parse REVISION_SUGGESTION
        revision_match = re.search(r'REVISION_SUGGESTION:\s*(.+?)(?=\n\w+:|$)', response_text, re.DOTALL | re.IGNORECASE)
        if revision_match:
            result["revision_suggestion"] = revision_match.group(1).strip()
        
        # Parse NEGOTIATION_NOTE
        negotiation_match = re.search(r'NEGOTIATION_NOTE:\s*(.+?)(?=\n\w+:|$)', response_text, re.DOTALL | re.IGNORECASE)
        if negotiation_match:
            result["negotiation_note"] = negotiation_match.group(1).strip()
        
        return result
    
    def _build_risk_summary(self, findings: list[ReviewFinding]) -> dict[str, int]:
        """Count findings by risk level."""
        summary: dict[str, int] = {
            RiskLevel.HIGH: 0,
            RiskLevel.MEDIUM: 0,
            RiskLevel.LOW: 0,
            RiskLevel.NONE: 0,
        }
        for finding in findings:
            summary[finding.risk_level] = summary.get(finding.risk_level, 0) + 1
        return summary
    
    async def _call_groq_with_fallback(
        self, prompt: str, temperature: float, max_tokens: int
    ) -> str:
        """Call Groq API with fallback model on rate limit."""
        models = [
            self.settings.groq_model_primary,
            self.settings.groq_model_fallback,
        ]
        
        last_error = None
        for model in models:
            try:
                response = await self.groq_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                if "rate limit" in error_str or "ratelimit" in error_str or "429" in error_str:
                    continue  # Try fallback model
                raise  # Other errors propagate
        
        # Both models failed
        raise last_error or Exception("Groq API call failed")
