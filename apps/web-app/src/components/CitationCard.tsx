"use client";

import { useState } from "react";
import { Citation } from "@/lib/types";
import { BookOpen, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";

interface CitationCardProps {
  citation: Citation;
  onClick?: () => void;
  compact?: boolean;
}

export function CitationCard({ citation, onClick, compact = false }: CitationCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
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
        <div className="mt-3">
          <blockquote className="text-sm text-slate-700 italic border-l-2 border-primary/30 pl-3">
            &ldquo;{isExpanded ? citation.quote : citation.quote.substring(0, 150)}
            {!isExpanded && citation.quote.length > 150 ? "..." : ""}&rdquo;
          </blockquote>
          {citation.quote.length > 150 && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setIsExpanded(!isExpanded);
              }}
              className="mt-2 text-xs text-primary hover:text-primary/80 flex items-center gap-1 transition-colors"
            >
              {isExpanded ? (
                <>
                  <ChevronUp className="w-3 h-3" />
                  Thu gọn
                </>
              ) : (
                <>
                  <ChevronDown className="w-3 h-3" />
                  Xem thêm
                </>
              )}
            </button>
          )}
        </div>
      )}
    </button>
  );
}
