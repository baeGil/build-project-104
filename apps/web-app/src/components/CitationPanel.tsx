"use client";

import { CitationDetail } from "@/lib/types";
import { X, BookOpen, FileText, Link2, History } from "lucide-react";

interface CitationPanelProps {
  citation: CitationDetail | null;
  onClose: () => void;
}

export function CitationPanel({ citation, onClose }: CitationPanelProps) {
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
              <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">
                {citation.full_text || citation.quote}
              </p>
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
