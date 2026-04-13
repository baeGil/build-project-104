"use client";

import { Citation } from "@/lib/types";
import { BookOpen, ExternalLink } from "lucide-react";

interface CitationCardProps {
  citation: Citation;
  onClick?: () => void;
  compact?: boolean;
}

export function CitationCard({ citation, onClick, compact = false }: CitationCardProps) {
  if (compact) {
    return (
      <button
        onClick={onClick}
        className="text-left w-full p-3 bg-slate-50 hover:bg-slate-100 rounded-lg border border-slate-200 transition-colors"
      >
        <div className="flex items-start gap-2">
          <BookOpen className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
          <div className="min-w-0">
            <p className="text-sm font-medium text-slate-900 truncate">
              {citation.document_title || citation.law_id}
            </p>
            <p className="text-xs text-muted mt-0.5">
              Article {citation.article_id}
            </p>
          </div>
        </div>
      </button>
    );
  }

  return (
    <button
      onClick={onClick}
      className="text-left w-full p-4 bg-slate-50 hover:bg-slate-100 rounded-lg border border-slate-200 transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center flex-shrink-0">
            <BookOpen className="w-4 h-4 text-primary" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="font-medium text-slate-900">
              {citation.document_title || citation.law_id}
            </p>
            <p className="text-sm text-muted mt-0.5">
              Article {citation.article_id}
            </p>
          </div>
        </div>
        <ExternalLink className="w-4 h-4 text-muted flex-shrink-0" />
      </div>
      {citation.quote && (
        <blockquote className="mt-3 text-sm text-slate-700 italic border-l-2 border-primary/30 pl-3">
          &ldquo;{citation.quote.substring(0, 150)}
          {citation.quote.length > 150 ? "..." : ""}&rdquo;
        </blockquote>
      )}
    </button>
  );
}
