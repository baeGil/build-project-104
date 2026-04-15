"use client";

import { useState, useEffect } from "react";
import { CitationDetail } from "@/lib/types";
import { getCitationFullText } from "@/lib/api";
import { X, BookOpen, FileText, Link2, History, Loader2 } from "lucide-react";

interface CitationPanelProps {
  citation: CitationDetail | null;
  onClose: () => void;
}

export function CitationPanel({ citation, onClose }: CitationPanelProps) {
  const [fullText, setFullText] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Debug: Log citation when it changes
  useEffect(() => {
    if (citation) {
      console.log("📋 CitationPanel opened with:", {
        article_id: citation.article_id,
        law_id: citation.law_id,
        document_title: citation.document_title,
        has_full_text: !!citation.full_text,
        quote_length: citation.quote?.length,
        // Check if it's a CitationDetail (from getCitation API)
        has_node_id: !!(citation as any).node_id,
        has_hierarchy: !!(citation as any).hierarchy,
      });
    }
  }, [citation]);

  // Fetch full text when citation changes
  useEffect(() => {
    if (!citation) {
      setFullText(null);
      setError(null);
      return;
    }

    // Handle CitationDetail type (from getCitation API)
    const citationDetail = citation as any;
    if (citationDetail.node_id) {
      // This is a CitationDetail from /citations/{node_id} API
      const docId = citationDetail.node_id;
      const title = citationDetail.hierarchy?.title || citation.document_title || "Unknown";
      
      console.log("📄 CitationDetail detected, fetching full text for:", docId);
      
      setFullText(null);
      setIsLoading(true);
      setError(null);
      
      // Fetch full text from PostgreSQL
      getCitationFullText(docId)
        .then(data => {
          console.log("✅ Full text loaded:", data.full_text?.length, "chars");
          setFullText(data.full_text);
        })
        .catch(err => {
          console.error("❌ Failed to fetch full text:", err);
          setError("Không thể tải nội dung đầy đủ");
          setFullText(title); // Fallback to title
        })
        .finally(() => setIsLoading(false));
      
      return;
    }

    // Validate article_id for regular Citation type
    if (!citation.article_id) {
      console.error("Citation missing article_id:", citation);
      setError("Thiếu thông tin document ID");
      setFullText(citation.quote || "Không có nội dung");
      return;
    }

    // If we already have full_text, use it
    if (citation.full_text) {
      setFullText(citation.full_text);
      return;
    }

    // Fetch from API for regular Citation type
    const fetchFullText = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        console.log("Fetching full text for:", citation.article_id);
        const data = await getCitationFullText(citation.article_id);
        console.log("Full text loaded:", data.full_text?.length, "chars");
        setFullText(data.full_text);
      } catch (err) {
        console.error("Failed to fetch full text:", err);
        setError("Không thể tải nội dung đầy đủ");
        setFullText(citation.quote); // Fallback to quote
      } finally {
        setIsLoading(false);
      }
    };

    fetchFullText();
  }, [citation]);

  if (!citation) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-40"
        onClick={onClose}
      />

      {/* Panel */}
      <aside className="fixed right-0 top-0 h-screen w-full max-w-lg bg-white shadow-2xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-200">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
              <BookOpen className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h2 className="font-semibold text-slate-900">
                {citation.document_title || citation.law_id}
              </h2>
              <p className="text-sm text-muted">
                Article {citation.article_id}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Full Text */}
          <section>
            <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wide mb-3 flex items-center gap-2">
              <FileText className="w-4 h-4" />
              Full Text
            </h3>
            <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 text-primary animate-spin" />
                  <span className="ml-2 text-slate-600">Đang tải nội dung...</span>
                </div>
              ) : error ? (
                <div className="text-red-600 text-sm">
                  <p>{error}</p>
                  <p className="text-xs mt-1 text-slate-500">Hiển thị đoạn trích dẫn thay thế</p>
                </div>
              ) : (
                <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">
                  {fullText || citation.full_text || citation.quote}
                </p>
              )}
            </div>
          </section>

          {/* Parent Document */}
          {citation.parent_document && (
            <section>
              <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wide mb-3 flex items-center gap-2">
                <BookOpen className="w-4 h-4" />
                Parent Document
              </h3>
              <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                <p className="text-slate-700">{citation.parent_document}</p>
              </div>
            </section>
          )}

          {/* Related Amendments */}
          {citation.related_amendments && citation.related_amendments.length > 0 && (
            <section>
              <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wide mb-3 flex items-center gap-2">
                <History className="w-4 h-4" />
                Related Amendments
              </h3>
              <ul className="space-y-2">
                {citation.related_amendments.map((amendment, index) => (
                  <li
                    key={index}
                    className="bg-slate-50 rounded-lg p-3 border border-slate-200 text-sm text-slate-700"
                  >
                    {amendment}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Original Source */}
          {citation.original_source_url && (
            <section>
              <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wide mb-3 flex items-center gap-2">
                <Link2 className="w-4 h-4" />
                Original Source
              </h3>
              <a
                href={citation.original_source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-primary hover:underline"
              >
                View on Official Source
                <Link2 className="w-4 h-4" />
              </a>
            </section>
          )}
        </div>
      </aside>
    </>
  );
}
