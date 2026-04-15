"""Legal finding generator using EvidencePack pattern."""
from __future__ import annotations

import logging
import time
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)

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
            self._groq_client = groq.AsyncGroq(
                api_key=self.settings.groq_api_key,
                timeout=30.0,
            )
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
                    temperature=0,
                    max_tokens=800,
                )
                
                # DEBUG: Log raw response to see what LLM returns
                logger.debug(f"Raw LLM response:\n{response}")
                
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
            
            # Fix confidence if LLM didn't return it (calculate from verification level)
            if parsed.get("confidence", 0) == 0:
                # Use verification level to determine meaningful confidence
                confidence_map = {
                    VerificationLevel.ENTAILED: 95.0,           # Fully supported
                    VerificationLevel.CONTRADICTED: 85.0,       # Clear contradiction
                    VerificationLevel.PARTIALLY_SUPPORTED: 75.0, # Partially supported
                    VerificationLevel.NO_REFERENCE: 60.0,        # No reference found
                }
                parsed["confidence"] = confidence_map.get(
                    evidence_pack.verification_level or VerificationLevel.NO_REFERENCE,
                    60.0
                )
                logger.debug(f"Confidence set from verification level: {parsed['confidence']}")
            
            # Build inline_citation_map from retrieved documents
            inline_citation_map = self._build_inline_citation_map(evidence_pack)
            
            # Validate grounding - remove hallucinated citations
            rationale = parsed.get("rationale", "No rationale generated")
            rationale = self._validate_grounding(rationale, inline_citation_map)
            
            finding = ReviewFinding(
                clause_text=evidence_pack.clause,
                clause_index=0,  # Will be set by caller
                verification=evidence_pack.verification_level or VerificationLevel.NO_REFERENCE,
                confidence=parsed.get("confidence", 75.0),  # Use parsed confidence (from LLM or fallback)
                risk_level=risk_level,
                rationale=rationale,
                citations=evidence_pack.citations,
                revision_suggestion=parsed.get("revision_suggestion", "Không cần sửa đổi"),  # Default if missing
                negotiation_note=parsed.get("negotiation_note", "Không có ý kiến đàm phán"),  # Default if missing
                inline_citation_map=inline_citation_map,
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
                    temperature=0,
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
            return "Không có kết quả để tóm tắt."
        
        with generation_duration_seconds.labels(task_type="summary").time():
            risk_counts = self._build_risk_summary(findings)
            
            # Build summary prompt
            prompt = f"""Bạn là trợ lý rà soát hợp đồng pháp luật. Tóm tắt các kết quả rà soát hợp đồng sau.

LUÔN trả lời hoàn toàn bằng tiếng Việt. KHÔNG sử dụng tiếng Anh.

Tóm tắt rủi ro:
- Vấn đề rủi ro cao: {risk_counts.get(RiskLevel.HIGH, 0)}
- Vấn đề rủi ro trung bình: {risk_counts.get(RiskLevel.MEDIUM, 0)}
- Vấn đề rủi ro thấp: {risk_counts.get(RiskLevel.LOW, 0)}
- Không có rủi ro: {risk_counts.get(RiskLevel.NONE, 0)}

Các phát hiện chính:
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
                prompt += f"   Lý do: {finding.rationale[:150]}...\n"
            
            prompt += """

Cung cấp tóm tắt điều hành ngắn gọn (2-3 đoạn) nêu bật:
1. Đánh giá rủi ro tổng thể
2. Các vấn đề chính cần quan tâm
3. Các hành động được khuyến nghị

Tóm tắt:"""
            
            try:
                response = await self._call_groq_with_fallback(
                    prompt,
                    temperature=0,
                    max_tokens=500,
                )
                summary = response.strip()
                
                # Append references section
                references_section = self._build_references_section(findings)
                if references_section:
                    summary += "\n\n" + references_section
                
                return summary
            except Exception as e:
                return f"Tạo tóm tắt thất bại: {str(e)}. Phân bổ rủi ro: {risk_counts}"
    
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
                logger.info(f"Streaming with Groq model: {model}")
                stream = await self.groq_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=1000,
                    stream=True,
                )
                
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                
                return  # Success, exit
            except Exception as e:
                last_error = e
                logger.warning(f"Streaming model {model} failed: {e}")
                continue  # Always try next model
        
        # Both models failed
        logger.error(f"All streaming models failed: {last_error}")
        yield f"\n\n[Error: Service temporarily unavailable. Please try again later.]"
    
    def _build_review_prompt(self, evidence_pack: EvidencePack) -> str:
        """Build structured prompt from EvidencePack for review with chain-of-thought and strict grounding."""
        prompt = """Bạn là trợ lý rà soát hợp đồng pháp luật Việt Nam. Phân tích điều khoản hợp đồng dựa trên bằng chứng pháp lý được cung cấp.

QUAN TRỌNG - NGUYÊN TẮC NGHIÊM NGẬT:
- LUÔN trả lời hoàn toàn bằng tiếng Việt. KHÔNG sử dụng tiếng Anh.
- Bạn PHẢI tham chiếu các tài liệu pháp lý cụ thể bằng ký hiệu [1], [2], [3] trong phần phân tích.
- Mỗi nhận định về pháp luật PHẢI có trích dẫn tương ứng từ tài liệu được cung cấp.
- KHÔNG ĐƯỢC đưa ra thông tin không có trong tài liệu tham khảo. Mọi nhận định pháp lý PHẢI có trích dẫn [n] tương ứng.
- Nếu không tìm thấy căn cứ pháp lý, hãy nêu rõ "Không tìm thấy căn cứ pháp luật cụ thể".

PHÂN TÍCH THEO CÁC BƯỚC SAU:
Bước 1: Xác định nội dung điều khoản
Bước 2: So sánh với quy định pháp luật liên quan [trích dẫn nguồn]
Bước 3: Đánh giá mức độ tuân thủ
Bước 4: Đề xuất sửa đổi (nếu cần)

"""
        prompt += self._format_evidence_context(evidence_pack)
        
        prompt += f"""

Điều khoản hợp đồng cần rà soát:
"{evidence_pack.clause}"

Trạng thái xác minh: {evidence_pack.verification_level.value if evidence_pack.verification_level else "unknown"}

Cung cấp phân tích theo định dạng SAU ĐÂY - MỖI FIELD PHẢI Ở DÒNG RIÊNG:

RATIONALE: [Chỉ chứa phân tích 4 bước. SỬ DỤNG [1], [2], [3] để tham chiếu. KHÔNG được chứa revision suggestion hay negotiation note ở đây.]

RISK_LEVEL: high

CONFIDENCE: 85

REVISION_SUGGESTION: [Chỉ chứa đề xuất sửa đổi cụ thể. Nếu không cần sửa, ghi: "Không cần sửa đổi"]

NEGOTIATION_NOTE: [Chỉ chứa lời khuyên đàm phán. Nếu không có, ghi: "Không có ý kiến đàm phán"]

QUAN TRỌNG:
- MỖI field PHẢI bắt đầu bằng tên field + dấu hai chấm
- KHÔNG được chèn field này vào field khác
- CONFIDENCE phải là số từ 0-100
- RISK_LEVEL phải là một trong: high, medium, low, none

Giữ câu trả lời có cấu trúc và ngắn gọn. Nhớ sử dụng tiếng Việt hoàn toàn."""
        return prompt
    
    def _build_chat_prompt(self, query: str, evidence_pack: EvidencePack) -> str:
        """Build prompt for chat answer."""
        prompt = """Bạn là trợ lý pháp luật Việt Nam. Trả lời câu hỏi của người dùng dựa trên bằng chứng pháp lý được cung cấp.

QUAN TRỌNG:
- LUÔN trả lời hoàn toàn bằng tiếng Việt. KHÔNG sử dụng tiếng Anh.
- Bạn PHẢI tham chiếu các tài liệu pháp lý cụ thể bằng ký hiệu [1], [2], [3] trong câu trả lời.
- Mỗi nhận định về pháp luật phải có trích dẫn tương ứng từ tài liệu được cung cấp.

"""
        prompt += self._format_evidence_context(evidence_pack)
        
        prompt += f"""

Câu hỏi của người dùng: {query}

Cung cấp câu trả lời rõ ràng, chính xác dựa trên bằng chứng pháp lý ở trên. Sử dụng ký hiệu [1], [2], [3] để tham chiếu tài liệu pháp lý cụ thể khi đưa ra nhận định. Nếu bằng chứng không trả lời đầy đủ câu hỏi, hãy thừa nhận những hạn chế.

Câu trả lời:"""
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
                # Reduced from 500 to 300 chars to avoid 413 rate limit errors
                context += f"Content: {doc.content[:300]}...\n"
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
                # Reduced from 200 to 150 chars to avoid 413 rate limit errors
                context += f"- {citation.article_id} ({citation.law_id}): {citation.quote[:150]}...\n"
        
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
        
        # Parse CONFIDENCE (NEW)
        confidence_match = re.search(r'CONFIDENCE:\s*(\d+)', response_text, re.IGNORECASE)
        if confidence_match:
            confidence_val = int(confidence_match.group(1))
            # Clamp to 0-100
            result["confidence"] = float(max(0, min(100, confidence_val)))
        else:
            # Default confidence based on verification level
            result["confidence"] = 75.0  # Default
        
        # Parse REVISION_SUGGESTION
        revision_match = re.search(r'REVISION_SUGGESTION:\s*(.+?)(?=\n\w+:|$)', response_text, re.DOTALL | re.IGNORECASE)
        if revision_match:
            result["revision_suggestion"] = revision_match.group(1).strip()
        else:
            result["revision_suggestion"] = "Không cần sửa đổi"  # Default
        
        # Parse NEGOTIATION_NOTE
        negotiation_match = re.search(r'NEGOTIATION_NOTE:\s*(.+?)(?=\n\w+:|$)', response_text, re.DOTALL | re.IGNORECASE)
        if negotiation_match:
            result["negotiation_note"] = negotiation_match.group(1).strip()
        else:
            result["negotiation_note"] = "Không có ý kiến đàm phán"  # Default
        
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
    
    def _build_inline_citation_map(self, evidence_pack: EvidencePack) -> dict[int, dict[str, Any]]:
        """Build a map from citation number [n] to citation info."""
        citation_map: dict[int, dict[str, Any]] = {}
        
        if evidence_pack.retrieved_documents:
            for i, doc in enumerate(evidence_pack.retrieved_documents[:5], 1):
                citation_map[i] = {
                    "doc_id": doc.doc_id,
                    "title": doc.title or doc.doc_id,
                    "content": doc.content[:500],
                    "score": doc.score,
                    "metadata": doc.metadata,
                }
        
        return citation_map
    
    def _validate_grounding(self, text: str, citation_map: dict[int, dict[str, Any]]) -> str:
        """
        Validate that all [n] citations in text map to real citations.
        
        Args:
            text: Generated text with citation markers
            citation_map: Map of valid citation numbers to citation info
            
        Returns:
            Text with hallucinated citations removed
        """
        import re
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Extract all [n] markers from text
        citation_pattern = r'\[(\d+)\]'
        matches = list(re.finditer(citation_pattern, text))
        
        # Track which citations are hallucinated
        hallucinated: list[int] = []
        valid_citations = set(citation_map.keys())
        
        for match in matches:
            citation_num = int(match.group(1))
            if citation_num not in valid_citations:
                hallucinated.append(citation_num)
        
        # Remove hallucinated citations from text
        if hallucinated:
            logger.warning(f"Hallucinated citations detected: {hallucinated}")
            for num in hallucinated:
                # Remove the citation marker
                text = re.sub(rf'\[{num}\]', '', text)
        
        # Clean up any double spaces left from removal
        text = re.sub(r'  +', ' ', text)
        
        return text.strip()
    
    
    def _build_references_section(self, findings: list[ReviewFinding]) -> str:
        """Build a references section listing all cited documents."""
        # Collect all unique citations across all findings
        seen_article_ids: set[str] = set()
        references: list[dict[str, Any]] = []
        
        for finding in findings:
            for citation in finding.citations:
                if citation.article_id not in seen_article_ids:
                    seen_article_ids.add(citation.article_id)
                    references.append({
                        "article_id": citation.article_id,
                        "law_id": citation.law_id,
                        "document_title": citation.document_title,
                        "quote": citation.quote,
                    })
        
        
        if not references:
            return ""
        
        # Build formatted references section
        section = "## Tài liệu tham khảo\n\n"
        for i, ref in enumerate(references, 1):
            title = ref.get("document_title") or ref.get("law_id", "Unknown")
            article = ref.get("article_id", "")
            section += f"[{i}] {title} - {article}\n"
        
        
        return section
    
    
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
                logger.info(f"Calling Groq with model: {model}")
                response = await self.groq_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                last_error = e
                logger.warning(f"Groq model {model} failed: {e}")
                continue  # Always try next model
    
        # Both models failed
        logger.error(f"All Groq models failed: {last_error}")
        raise last_error or Exception("Groq API call failed")
