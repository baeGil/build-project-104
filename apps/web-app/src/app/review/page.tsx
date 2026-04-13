"use client";

import { useState, useRef, ChangeEvent } from "react";
import { reviewContract } from "@/lib/api";
import { ContractReviewResult, ReviewFinding, Citation } from "@/lib/types";
import { sampleContract } from "@/lib/sampleContract";
import { VerificationBadge } from "@/components/VerificationBadge";
import { RiskIndicator } from "@/components/RiskIndicator";
import { ConfidenceBar } from "@/components/ConfidenceBar";
import { CitationCard } from "@/components/CitationCard";
import { CitationPanel } from "@/components/CitationPanel";
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
} from "lucide-react";

export default function ReviewPage() {
  const [contractText, setContractText] = useState("");
  const [result, setResult] = useState<ContractReviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedFindings, setExpandedFindings] = useState<Set<number>>(new Set());
  const [selectedCitation, setSelectedCitation] = useState<CitationDetail | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type !== "text/plain" && !file.name.endsWith(".txt")) {
      setError("Please upload a .txt file");
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      setContractText(text);
      setError(null);
    };
    reader.onerror = () => {
      setError("Failed to read file");
    };
    reader.readAsText(file);
  };

  const handleReview = async () => {
    if (!contractText.trim()) {
      setError("Please enter contract text");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await reviewContract({
        contract_text: contractText,
        contract_id: `contract-${Date.now()}`,
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed");
    } finally {
      setLoading(false);
    }
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

  const loadSample = () => {
    setContractText(sampleContract);
    setError(null);
  };

  const clearAll = () => {
    setContractText("");
    setResult(null);
    setError(null);
    setExpandedFindings(new Set());
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-slate-900">Contract Review</h1>
        <p className="text-muted mt-1">
          Analyze contract compliance with Vietnamese legal corpus
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left Panel - Input */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
            <div className="p-4 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-primary" />
                <h2 className="font-semibold text-slate-900">Contract Text</h2>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={loadSample}
                  className="text-sm text-primary hover:text-primary/80 font-medium px-3 py-1.5 rounded-lg hover:bg-primary/5 transition-colors"
                >
                  Load Sample
                </button>
                <button
                  onClick={clearAll}
                  className="text-sm text-muted hover:text-slate-700 px-3 py-1.5 rounded-lg hover:bg-slate-100 transition-colors"
                >
                  Clear
                </button>
              </div>
            </div>

            <div className="p-4">
              <textarea
                value={contractText}
                onChange={(e) => setContractText(e.target.value)}
                placeholder="Paste your contract text here or upload a .txt file..."
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
                    Click to upload .txt file
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
            disabled={loading || !contractText.trim()}
            className="w-full flex items-center justify-center gap-2 bg-primary text-white font-semibold py-4 rounded-xl hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-lg shadow-primary/20"
          >
            {loading ? (
              <>
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Analyzing Contract...
              </>
            ) : (
              <>
                <Sparkles className="w-5 h-5" />
                Review Contract
              </>
            )}
          </button>
        </div>

        {/* Right Panel - Results */}
        <div className="space-y-4">
          {loading ? (
            <ReviewResultSkeleton />
          ) : result ? (
            <div className="space-y-4">
              {/* Summary Card */}
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                <h2 className="text-lg font-semibold text-slate-900 mb-4">
                  Review Summary
                </h2>

                <div className="grid grid-cols-3 gap-4 mb-4">
                  <div className="bg-red-50 rounded-lg p-4 text-center">
                    <p className="text-2xl font-bold text-red-600">
                      {result.risk_summary.high || 0}
                    </p>
                    <p className="text-sm text-red-700">High Risk</p>
                  </div>
                  <div className="bg-yellow-50 rounded-lg p-4 text-center">
                    <p className="text-2xl font-bold text-yellow-600">
                      {result.risk_summary.medium || 0}
                    </p>
                    <p className="text-sm text-yellow-700">Medium Risk</p>
                  </div>
                  <div className="bg-green-50 rounded-lg p-4 text-center">
                    <p className="text-2xl font-bold text-green-600">
                      {result.risk_summary.low || 0}
                    </p>
                    <p className="text-sm text-green-700">Low Risk</p>
                  </div>
                </div>

                <p className="text-slate-700 text-sm leading-relaxed">
                  {result.summary}
                </p>

                <div className="flex items-center gap-2 mt-4 pt-4 border-t border-slate-200 text-sm text-muted">
                  <Clock className="w-4 h-4" />
                  <span>Processed in {(result.total_latency_ms / 1000).toFixed(2)}s</span>
                  <span className="mx-2">•</span>
                  <span>{result.total_clauses} clauses analyzed</span>
                </div>
              </div>

              {/* Findings */}
              <div className="space-y-3">
                <h3 className="font-semibold text-slate-900">
                  Detailed Findings ({result.findings.length})
                </h3>

                {result.findings.map((finding, index) => (
                  <FindingCard
                    key={index}
                    finding={finding}
                    index={index}
                    isExpanded={expandedFindings.has(index)}
                    onToggle={() => toggleFinding(index)}
                    onCitationClick={handleCitationClick}
                  />
                ))}
              </div>
            </div>
          ) : (
            /* Empty State */
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-12 text-center">
              <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <FileUp className="w-8 h-8 text-muted" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900 mb-2">
                Ready to Review
              </h3>
              <p className="text-muted max-w-sm mx-auto">
                Enter your contract text or upload a file, then click "Review
                Contract" to analyze compliance with Vietnamese law.
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
}

function FindingCard({
  finding,
  index,
  isExpanded,
  onToggle,
  onCitationClick,
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
                Analysis
              </h4>
              <p className="text-sm text-slate-700 leading-relaxed">
                {finding.rationale}
              </p>
            </div>

            {/* Confidence */}
            <ConfidenceBar confidence={finding.confidence} size="sm" />

            {/* Citations */}
            {finding.citations.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-slate-900 mb-2">
                  Legal Citations ({finding.citations.length})
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
                      Suggested Revision
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
                      Negotiation Note
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
}
