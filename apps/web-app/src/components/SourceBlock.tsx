"use client";

import { useState } from "react";
import { Reference, Citation } from "@/lib/types";
import { BookOpen, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";

interface SourceBlockProps {
  references: Reference[];
  onCitationClick?: (reference: Reference) => void;
  title?: string;
  collapsible?: boolean;
  defaultExpanded?: boolean;
}

export function SourceBlock({ 
  references, 
  onCitationClick,
  title = "Tài liệu tham khảo",
  collapsible = true,
  defaultExpanded = true
}: SourceBlockProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [expandedQuotes, setExpandedQuotes] = useState<Record<number, boolean>>({});

  if (!references || references.length === 0) {
    return null;
  }

  const handleReferenceClick = (ref: Reference) => {
    if (onCitationClick) {
      onCitationClick(ref);
    }
  };

  return (
    <div className="mt-6 border-t border-slate-200 pt-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-primary" />
          <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          <span className="text-xs text-muted bg-slate-100 px-2 py-0.5 rounded-full">
            {references.length}
          </span>
        </div>
        
        {collapsible && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 hover:bg-slate-100 rounded transition-colors"
          >
            {isExpanded ? (
              <ChevronUp className="w-4 h-4 text-slate-500" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-500" />
            )}
          </button>
        )}
      </div>

      {/* Reference List */}
      {isExpanded && (
        <ol className="space-y-2">
          {references.map((ref, index) => (
            <li key={`${ref.article_id}-${index}`}>
              <div
                onClick={() => onCitationClick && handleReferenceClick(ref)}
                className={`
                  w-full text-left
                  p-3 rounded-lg
                  border border-slate-200
                  bg-slate-50
                  transition-all duration-150
                  ${onCitationClick 
                    ? "hover:bg-slate-100 hover:border-slate-300 cursor-pointer" 
                    : "cursor-default"
                  }
                `}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2 min-w-0">
                    <span className="text-xs text-muted font-mono flex-shrink-0">
                      [{index + 1}]
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-slate-900 truncate">
                        {ref.document_title || ref.law_id}
                      </p>
                      <p className="text-xs text-muted mt-0.5">
                        {ref.article_id}
                      </p>
                    </div>
                  </div>
                  {onCitationClick && (
                    <ExternalLink className="w-4 h-4 text-slate-400 flex-shrink-0 mt-0.5" />
                  )}
                </div>
                
                {/* Quote preview */}
                {ref.quote && (
                  <div className="mt-2">
                    <p className="text-xs text-slate-600 italic border-l-2 border-slate-200 pl-2">
                      "{expandedQuotes[index] ? ref.quote : ref.quote.substring(0, 150)}
                      {!expandedQuotes[index] && ref.quote.length > 150 ? "..." : ""}"
                    </p>
                    {ref.quote.length > 150 && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setExpandedQuotes(prev => ({
                            ...prev,
                            [index]: !prev[index]
                          }));
                        }}
                        className="mt-1 text-xs text-primary hover:text-primary/80 transition-colors"
                      >
                        {expandedQuotes[index] ? "Thu gọn" : "Xem thêm"}
                      </button>
                    )}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

// Alternative compact version for inline use
export function SourceBlockCompact({ 
  references, 
  onCitationClick 
}: SourceBlockProps) {
  if (!references || references.length === 0) {
    return null;
  }

  return (
    <div className="mt-3 p-3 bg-slate-50 rounded-lg border border-slate-200">
      <div className="flex items-center gap-2 mb-2">
        <BookOpen className="w-4 h-4 text-primary" />
        <span className="text-xs font-medium text-slate-700">Tài liệu tham khảo</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {references.map((ref, index) => (
          <button
            key={`${ref.article_id}-${index}`}
            onClick={() => onCitationClick?.(ref)}
            className="text-xs px-2 py-1 bg-white border border-slate-200 rounded hover:bg-slate-100 transition-colors"
          >
            [{index + 1}] {ref.document_title || ref.law_id}
          </button>
        ))}
      </div>
    </div>
  );
}
