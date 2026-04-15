"use client";

import { useState, useRef, ChangeEvent, useMemo, memo } from "react";
import { usePersistedState } from "@/lib/hooks";
import { reviewContract, streamContractReview } from "@/lib/api";
import { ContractReviewResult, ReviewFinding, Citation, InlineCitationInfo, Reference, ReviewStreamEvent } from "@/lib/types";
import { sampleContract } from "@/lib/sampleContract";
import { VerificationBadge } from "@/components/VerificationBadge";
import { RiskIndicator } from "@/components/RiskIndicator";
import { ConfidenceBar } from "@/components/ConfidenceBar";
import { CitationCard } from "@/components/CitationCard";
import { CitationPanel } from "@/components/CitationPanel";
import { InlineCitation } from "@/components/InlineCitation";
import { SourceBlock } from "@/components/SourceBlock";
import { ReviewResultSkeleton } from "@/components/Skeleton";
import { getCitation } from "@/lib/api";
import { CitationDetail } from "@/lib/types";
import {
  FileText,
  Upload,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Lightbulb,
  MessageSquareWarning,
  Clock,
  AlertCircle,
  FileUp,
  RotateCcw,
  Loader2,
  Search,
  BookOpen,
  CheckCircle,
} from "lucide-react";

interface ReviewState {
  contractText: string;
  result: ContractReviewResult | null;
}

type ReviewPhase = "analyzing" | "reviewing" | "retrieving" | "summarizing" | "complete";

interface StreamingState {
  isStreaming: boolean;
  phase: ReviewPhase;
  currentClause: number;
  totalClauses: number;
  message: string;
  partialFindings: ReviewFinding[];
}

export default function ReviewPage() {
  const [persistedState, setPersistedState] = usePersistedState<ReviewState>("review_state", {
    contractText: "",
    result: null,
  });
  const contractText = persistedState.contractText;
  const result = persistedState.result;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedFindings, setExpandedFindings] = useState<Set<number>>(new Set());
  const [selectedCitation, setSelectedCitation] = useState<CitationDetail | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Streaming state
  const [streamingState, setStreamingState] = useState<StreamingState>({
    isStreaming: false,
    phase: "analyzing",
    currentClause: 0,
    totalClauses: 0,
    message: "",
    partialFindings: [],
  });

  const handleFileUpload = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type !== "text/plain" && !file.name.endsWith(".txt")) {
      setError("Vui lòng tải lên tệp .txt");
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      setPersistedState((prev) => ({ ...prev, contractText: text }));
      setError(null);
    };
    reader.onerror = () => {
      setError("Không thể đọc tệp");
    };
    reader.readAsText(file);
  };

  const handleReview = async () => {
    if (!contractText.trim()) {
      setError("Vui lòng nhập nội dung hợp đồng");
      return;
    }

    if (contractText.trim().length < 10) {
      setError("Nội dung hợp đồng phải có ít nhất 10 ký tự");
      return;
    }

    setLoading(true);
    setError(null);
    setPersistedState((prev) => ({ ...prev, result: null }));
    
    // Reset streaming state
    setStreamingState({
      isStreaming: true,
      phase: "analyzing",
      currentClause: 0,
      totalClauses: 0,
      message: "Đang phân tích hợp đồng...",
      partialFindings: [],
    });

    try {
      // Try streaming first
      const stream = streamContractReview({
        contract_text: contractText,
        contract_id: `contract-${Date.now()}`,
      });

      let finalResult: ContractReviewResult | null = null;
      const findings: ReviewFinding[] = [];

      for await (const event of stream) {
        handleStreamEvent(event, findings);
        if (event.type === "summary") {
          finalResult = {
            contract_id: `contract-${Date.now()}`,
            findings: [...findings],
            summary: event.data.summary,
            total_clauses: event.data.total_clauses,
            risk_summary: event.data.risk_summary,
            total_latency_ms: event.data.total_latency_ms,
            timestamp: new Date().toISOString(),
            references: event.data.references,
          };
        }
      }

      if (finalResult) {
        setPersistedState((prev) => ({ ...prev, result: finalResult }));
      } else if (findings.length > 0) {
        // Build result from findings
        finalResult = {
          contract_id: `contract-${Date.now()}`,
          findings: findings,
          summary: "Rà soát hoàn tất",
          total_clauses: findings.length,
          risk_summary: calculateRiskSummary(findings),
          total_latency_ms: 0,
          timestamp: new Date().toISOString(),
        };
        setPersistedState((prev) => ({ ...prev, result: finalResult }));
      }
    } catch (streamErr) {
      // Check for AbortError (timeout)
      if (streamErr instanceof DOMException && streamErr.name === 'AbortError') {
        setError("Yêu cầu đã hết thờI gian chờ. Vui lòng thử lại.");
      } else {
        // Fallback to non-streaming on other errors
        console.log("Streaming failed, falling back to regular review:", streamErr);
        try {
          const data = await reviewContract({
            contract_text: contractText,
            contract_id: `contract-${Date.now()}`,
          });
          setPersistedState((prev) => ({ ...prev, result: data }));
        } catch (err) {
          setError(err instanceof Error ? err.message : "Rà soát thất bại");
        }
      }
    } finally {
      setLoading(false);
      setStreamingState((prev) => ({ ...prev, isStreaming: false, phase: "complete" }));
    }
  };
  
  const handleStreamEvent = (event: ReviewStreamEvent, findings: ReviewFinding[]) => {
    switch (event.type) {
      case "progress":
        setStreamingState((prev) => ({
          ...prev,
          phase: event.data.phase as ReviewPhase,
          message: event.data.message,
          totalClauses: event.data.total_clauses ?? prev.totalClauses,
          currentClause: event.data.current ?? prev.currentClause,
        }));
        break;
      case "finding":
        findings.push(event.data);
        setStreamingState((prev) => ({
          ...prev,
          partialFindings: [...prev.partialFindings, event.data],
          currentClause: prev.currentClause + 1,
        }));
        break;
      case "summary":
        setStreamingState((prev) => ({
          ...prev,
          message: event.data.summary,
        }));
        // Update the result with full data
        const finalResult: ContractReviewResult = {
          contract_id: `contract-${Date.now()}`,
          findings: findings,
          summary: event.data.summary,
          total_clauses: event.data.total_clauses,
          risk_summary: event.data.risk_summary,
          total_latency_ms: event.data.total_latency_ms,
          timestamp: new Date().toISOString(),
          references: event.data.references,
        };
        setPersistedState((prev) => ({ ...prev, result: finalResult }));
        break;
      case "error":
        setError(event.data.message || "Đã xảy ra lỗi khi rà soát");
        setStreamingState((prev) => ({ ...prev, isStreaming: false, phase: "complete" }));
        break;
      case "done":
        setStreamingState((prev) => ({ ...prev, isStreaming: false, phase: "complete" }));
        break;
    }
  };
  
  const calculateRiskSummary = (findings: ReviewFinding[]): Record<string, number> => {
    const summary: Record<string, number> = {
      high: 0,
      medium: 0,
      low: 0,
      none: 0,
    };
    for (const finding of findings) {
      summary[finding.risk_level] = (summary[finding.risk_level] || 0) + 1;
    }
    return summary;
  };

  const toggleFinding = (index: number) => {
    setExpandedFindings((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const handleCitationClick = async (citation: Citation) => {
    try {
      const detail = await getCitation(citation.article_id);
      setSelectedCitation(detail);
    } catch {
      // Fallback to basic citation info
      setSelectedCitation({
        ...citation,
        full_text: citation.quote,
      });
    }
  };

  const handleInlineCitationClick = (citationInfo: InlineCitationInfo, _num: number) => {
    // Convert InlineCitationInfo to CitationDetail for the panel
    setSelectedCitation({
      article_id: citationInfo.doc_id,
      law_id: (citationInfo.metadata?.law_id as string) || "",
      quote: citationInfo.content,
      document_title: citationInfo.title,
      full_text: citationInfo.content,
    });
  };

  const handleReferenceClick = async (ref: Reference) => {
    try {
      const detail = await getCitation(ref.article_id);
      setSelectedCitation(detail);
    } catch {
      setSelectedCitation({
        article_id: ref.article_id,
        law_id: ref.law_id,
        quote: ref.quote,
        document_title: ref.document_title,
        full_text: ref.quote,
      });
    }
  };

  const loadSample = () => {
    setPersistedState((prev) => ({ ...prev, contractText: sampleContract }));
    setError(null);
  };

  const clearAll = () => {
    setPersistedState({ contractText: "", result: null });
    setError(null);
    setExpandedFindings(new Set());
    setStreamingState({
      isStreaming: false,
      phase: "analyzing",
      currentClause: 0,
      totalClauses: 0,
      message: "",
      partialFindings: [],
    });
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };
  
  // Progress indicator component
  const ProgressIndicator = () => {
    const { phase, currentClause, totalClauses, message } = streamingState;
    
    const getPhaseIcon = () => {
      switch (phase) {
        case "analyzing":
          return <Search className="w-5 h-5 text-primary animate-pulse" />;
        case "reviewing":
          return <Loader2 className="w-5 h-5 text-primary animate-spin" />;
        case "retrieving":
          return <BookOpen className="w-5 h-5 text-primary animate-pulse" />;
        case "summarizing":
          return <Sparkles className="w-5 h-5 text-primary animate-pulse" />;
        case "complete":
          return <CheckCircle className="w-5 h-5 text-green-500" />;
        default:
          return <Loader2 className="w-5 h-5 text-primary animate-spin" />;
      }
    };
    
    const getPhaseLabel = () => {
      switch (phase) {
        case "analyzing":
          return "Đang phân tích hợp đồng...";
        case "reviewing":
          return `Đang kiểm tra điều khoản ${currentClause}/${totalClauses}...`;
        case "retrieving":
          return "Đang tra cứu luật liên quan...";
        case "summarizing":
          return "Đang tổng hợp kết quả...";
        case "complete":
          return "Hoàn tất!";
        default:
          return message || "Đang xử lý...";
      }
    };
    
    const progressPercent = totalClauses > 0 
      ? Math.min(((currentClause) / totalClauses) * 100, 100)
      : phase === "analyzing" ? 10 : phase === "summarizing" ? 90 : 50;
    
    return (
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
        <div className="flex items-center gap-3 mb-4">
          {getPhaseIcon()}
          <span className="font-medium text-slate-900">{getPhaseLabel()}</span>
        </div>
        
        {/* Progress bar */}
        <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
          <div 
            className="h-full bg-primary transition-all duration-300 ease-out"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        
        {/* Phase indicators */}
        <div className="flex justify-between mt-3 text-xs text-muted">
          <span className={phase === "analyzing" ? "text-primary font-medium" : ""}>Phân tích</span>
          <span className={phase === "reviewing" ? "text-primary font-medium" : ""}>Kiểm tra</span>
          <span className={phase === "summarizing" ? "text-primary font-medium" : ""}>Tổng hợp</span>
        </div>
        
        {/* Partial findings count */}
        {streamingState.partialFindings.length > 0 && (
          <div className="mt-4 text-sm text-slate-600">
            Đã phát hiện {streamingState.partialFindings.length} vấn đề
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-slate-900">Rà soát Hợp đồng</h1>
        <p className="text-muted mt-1">
          Phân tích tuân thủ hợp đồng với hệ thống pháp luật Việt Nam
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left Panel - Input */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
            <div className="p-4 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-primary" />
                <h2 className="font-semibold text-slate-900">Nội dung hợp đồng</h2>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={loadSample}
                  className="text-sm text-primary hover:text-primary/80 font-medium px-3 py-1.5 rounded-lg hover:bg-primary/5 transition-colors"
                >
                  Tải mẫu
                </button>
                <button
                  onClick={clearAll}
                  className="text-sm text-muted hover:text-slate-700 px-3 py-1.5 rounded-lg hover:bg-slate-100 transition-colors"
                >
                  Xóa
                </button>
              </div>
            </div>

            <div className="p-4">
              <textarea
                value={contractText}
                onChange={(e) => setPersistedState((prev) => ({ ...prev, contractText: e.target.value }))}
                placeholder="Dán nội dung hợp đồng vào đây hoặc tải lên tệp .txt... (tối thiểu 10 ký tự)"
                className="w-full h-96 p-4 border border-slate-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary font-mono text-sm leading-relaxed"
              />

              {/* Upload Area */}
              <div className="mt-4">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".txt"
                  onChange={handleFileUpload}
                  className="hidden"
                  id="file-upload"
                />
                <label
                  htmlFor="file-upload"
                  className="flex items-center justify-center gap-2 w-full py-3 border-2 border-dashed border-slate-300 rounded-lg hover:border-primary hover:bg-primary/5 cursor-pointer transition-colors"
                >
                  <Upload className="w-5 h-5 text-muted" />
                  <span className="text-sm text-muted">
                    Tải lên tệp .txt
                  </span>
                </label>
              </div>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
              <AlertCircle className="w-5 h-5" />
              <span>{error}</span>
            </div>
          )}

          {/* Review Button */}
          <button
            onClick={handleReview}
            disabled={loading || !contractText.trim() || contractText.trim().length < 10}
            className="w-full flex items-center justify-center gap-2 bg-primary text-white font-semibold py-4 rounded-xl hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-lg shadow-primary/20"
          >
            {loading ? (
              <>
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Đang phân tích...
              </>
            ) : (
              <>
                <Sparkles className="w-5 h-5" />
                Rà soát Hợp đồng
              </>
            )}
          </button>
        </div>

        {/* Right Panel - Results */}
        <div className="space-y-4">
          {streamingState.isStreaming ? (
            <>
              <ProgressIndicator />
              
              {/* Progressive findings display */}
              {streamingState.partialFindings.length > 0 && (
                <div className="space-y-3">
                  <h3 className="font-semibold text-slate-900">
                    Kết quả chi tiết ({streamingState.partialFindings.length})
                  </h3>
                  
                  {streamingState.partialFindings.map((finding, index) => (
                    <FindingCard
                      key={index}
                      finding={finding}
                      index={index}
                      isExpanded={expandedFindings.has(index)}
                      onToggle={() => toggleFinding(index)}
                      onCitationClick={handleCitationClick}
                      onInlineCitationClick={handleInlineCitationClick}
                    />
                  ))}
                </div>
              )}
            </>
          ) : loading ? (
            <ReviewResultSkeleton />
          ) : result ? (
            <div className="space-y-4">
              {/* Summary Card */}
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                <h2 className="text-lg font-semibold text-slate-900 mb-4">
                  Tóm tắt rà soát
                </h2>

                <div className="grid grid-cols-4 gap-4 mb-4">
                  <div className="bg-red-50 rounded-lg p-4 text-center">
                    <p className="text-2xl font-bold text-red-600">
                      {result.risk_summary.high || 0}
                    </p>
                    <p className="text-sm text-red-700">Rủi ro cao</p>
                  </div>
                  <div className="bg-yellow-50 rounded-lg p-4 text-center">
                    <p className="text-2xl font-bold text-yellow-600">
                      {result.risk_summary.medium || 0}
                    </p>
                    <p className="text-sm text-yellow-700">Rủi ro trung bình</p>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-4 text-center">
                    <p className="text-2xl font-bold text-blue-600">
                      {result.risk_summary.low || 0}
                    </p>
                    <p className="text-sm text-blue-700">Rủi ro thấp</p>
                  </div>
                  <div className="bg-green-50 rounded-lg p-4 text-center">
                    <p className="text-2xl font-bold text-green-600">
                      {result.risk_summary.none || 0}
                    </p>
                    <p className="text-sm text-green-700">Không có rủi ro</p>
                  </div>
                </div>

                <p className="text-slate-700 text-sm leading-relaxed">
                  {result.summary}
                </p>

                <div className="flex items-center gap-2 mt-4 pt-4 border-t border-slate-200 text-sm text-muted">
                  <Clock className="w-4 h-4" />
                  <span>Thời gian xử lý: {(result.total_latency_ms / 1000).toFixed(2)}s</span>
                  <span className="mx-2">•</span>
                  <span>{result.total_clauses} điều khoản đã phân tích</span>
                </div>
              </div>

              {/* Findings */}
              <div className="space-y-3">
                <h3 className="font-semibold text-slate-900">
                  Kết quả chi tiết ({result.findings.length})
                </h3>

                {result.findings.map((finding, index) => (
                  <FindingCard
                    key={index}
                    finding={finding}
                    index={index}
                    isExpanded={expandedFindings.has(index)}
                    onToggle={() => toggleFinding(index)}
                    onCitationClick={handleCitationClick}
                    onInlineCitationClick={handleInlineCitationClick}
                  />
                ))}
              </div>

              {/* References Section */}
              {result.references && result.references.length > 0 && (
                <SourceBlock
                  references={result.references}
                  onCitationClick={handleReferenceClick}
                  title="Tài liệu tham khảo"
                />
              )}
            </div>
          ) : (
            /* Empty State */
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-12 text-center">
              <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <FileUp className="w-8 h-8 text-muted" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900 mb-2">
                Sẵn sàng rà soát
              </h3>
              <p className="text-muted max-w-sm mx-auto">
                Nhập nội dung hợp đồng hoặc tải lên tệp, sau đó nhấn "Rà soát Hợp đồng" để phân tích tuân thủ pháp luật Việt Nam.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Citation Panel */}
      <CitationPanel
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />
    </div>
  );
}

interface FindingCardProps {
  finding: ReviewFinding;
  index: number;
  isExpanded: boolean;
  onToggle: () => void;
  onCitationClick: (citation: Citation) => void;
  onInlineCitationClick: (citationInfo: InlineCitationInfo, num: number) => void;
}

const FindingCard = memo(function FindingCard({
  finding,
  index,
  isExpanded,
  onToggle,
  onCitationClick,
  onInlineCitationClick,
}: FindingCardProps) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full p-4 flex items-start gap-4 text-left hover:bg-slate-50 transition-colors"
      >
        <div className="flex-shrink-0 w-8 h-8 bg-slate-100 rounded-lg flex items-center justify-center text-sm font-semibold text-slate-700">
          {index + 1}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <VerificationBadge verification={finding.verification} size="sm" />
            <RiskIndicator risk={finding.risk_level} size="sm" />
          </div>
          <p className="mt-2 text-sm text-slate-700 line-clamp-2">
            {finding.clause_text}
          </p>
        </div>

        <div className="flex-shrink-0">
          {isExpanded ? (
            <ChevronUp className="w-5 h-5 text-muted" />
          ) : (
            <ChevronDown className="w-5 h-5 text-muted" />
          )}
        </div>
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 border-t border-slate-100">
          <div className="pt-4 space-y-4">
            {/* Rationale */}
            <div>
              <h4 className="text-sm font-semibold text-slate-900 mb-2">
                Phân tích
              </h4>
              <p className="text-sm text-slate-700 leading-relaxed">
                <InlineCitation
                  text={finding.rationale}
                  citationMap={finding.inline_citation_map}
                  onCitationClick={onInlineCitationClick}
                />
              </p>
            </div>

            {/* Confidence */}
            <ConfidenceBar confidence={finding.confidence} size="sm" />

            {/* Citations */}
            {finding.citations.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-slate-900 mb-2">
                  Trích dẫn pháp lý ({finding.citations.length})
                </h4>
                <div className="grid gap-2">
                  {finding.citations.map((citation, i) => (
                    <CitationCard
                      key={i}
                      citation={citation}
                      onClick={() => onCitationClick(citation)}
                      compact
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Revision Suggestion */}
            {finding.revision_suggestion && (
              <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                <div className="flex items-start gap-2">
                  <Lightbulb className="w-4 h-4 text-blue-600 mt-0.5" />
                  <div>
                    <h4 className="text-sm font-semibold text-blue-900">
                      Đề xuất sửa đổi
                    </h4>
                    <p className="text-sm text-blue-800 mt-1">
                      {finding.revision_suggestion}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Negotiation Note */}
            {finding.negotiation_note && (
              <div className="bg-yellow-50 rounded-lg p-4 border border-yellow-200">
                <div className="flex items-start gap-2">
                  <MessageSquareWarning className="w-4 h-4 text-yellow-600 mt-0.5" />
                  <div>
                    <h4 className="text-sm font-semibold text-yellow-900">
                      Ghi chú đàm phán
                    </h4>
                    <p className="text-sm text-yellow-800 mt-1">
                      {finding.negotiation_note}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
});
