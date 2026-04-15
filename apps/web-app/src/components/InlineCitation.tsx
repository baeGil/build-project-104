"use client";

import { useState, useRef, useEffect, ReactNode } from "react";
import { InlineCitationInfo } from "@/lib/types";

interface InlineCitationProps {
  text: string;
  citationMap?: Record<number, InlineCitationInfo>;
  onCitationClick?: (citation: InlineCitationInfo, number: number) => void;
}

interface ParsedPart {
  type: "text" | "citation";
  content: string;
  citationNumber?: number;
}

export function InlineCitation({ text, citationMap = {}, onCitationClick }: InlineCitationProps) {
  const [hoveredCitation, setHoveredCitation] = useState<number | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<"top" | "bottom">("top");
  const tooltipRef = useRef<HTMLDivElement>(null);
  const badgeRefs = useRef<Record<number, HTMLSpanElement>>({});

  // Parse text to split on [n] markers
  const parseText = (input: string): ParsedPart[] => {
    const parts: ParsedPart[] = [];
    const regex = /\[(\d+)\]/g;
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(input)) !== null) {
      // Add text before the match
      if (match.index > lastIndex) {
        parts.push({
          type: "text",
          content: input.slice(lastIndex, match.index),
        });
      }

      // Add the citation marker
      parts.push({
        type: "citation",
        content: match[0],
        citationNumber: parseInt(match[1], 10),
      });

      lastIndex = match.index + match[0].length;
    }

    // Add remaining text
    if (lastIndex < input.length) {
      parts.push({
        type: "text",
        content: input.slice(lastIndex),
      });
    }

    return parts;
  };

  const parts = parseText(text);

  // Calculate tooltip position based on available space
  useEffect(() => {
    if (hoveredCitation !== null && badgeRefs.current[hoveredCitation]) {
      const badge = badgeRefs.current[hoveredCitation];
      const rect = badge.getBoundingClientRect();
      const spaceAbove = rect.top;
      const spaceBelow = window.innerHeight - rect.bottom;
      
      // Show tooltip above if more space above, or below if more space below
      setTooltipPosition(spaceAbove > spaceBelow ? "top" : "bottom");
    }
  }, [hoveredCitation]);

  const handleMouseEnter = (num: number) => {
    setHoveredCitation(num);
  };

  const handleMouseLeave = () => {
    setHoveredCitation(null);
  };

  const handleClick = (num: number, e: React.MouseEvent) => {
    e.stopPropagation();
    const citationInfo = citationMap[num];
    if (citationInfo && onCitationClick) {
      onCitationClick(citationInfo, num);
    }
  };

  const renderPart = (part: ParsedPart, index: number): ReactNode => {
    if (part.type === "text") {
      return <span key={index}>{part.content}</span>;
    }

    const num = part.citationNumber!;
    const citationInfo = citationMap[num];
    const hasInfo = !!citationInfo;

    return (
      <span key={index} className="relative inline-flex items-center">
        <span
          ref={(el) => {
            if (el) badgeRefs.current[num] = el;
          }}
          className={`
            inline-flex items-center justify-center
            text-xs font-medium
            rounded-full px-1.5 py-0.5
            cursor-pointer
            transition-all duration-150
            ${hasInfo 
              ? "bg-blue-100 text-blue-700 hover:bg-blue-200 hover:text-blue-800" 
              : "bg-slate-100 text-slate-500 cursor-default"
            }
          `}
          onMouseEnter={() => hasInfo && handleMouseEnter(num)}
          onMouseLeave={handleMouseLeave}
          onClick={(e) => hasInfo && handleClick(num, e)}
        >
          {num}
        </span>

        {/* Tooltip */}
        {hoveredCitation === num && citationInfo && (
          <div
            ref={tooltipRef}
            className={`
              absolute z-50
              ${tooltipPosition === "top" ? "bottom-full mb-2" : "top-full mt-2"}
              left-1/2 -translate-x-1/2
              w-64 p-3
              bg-slate-900 text-white
              rounded-lg shadow-lg
              text-xs leading-relaxed
              pointer-events-none
            `}
          >
            {/* Arrow */}
            <div
              className={`
                absolute left-1/2 -translate-x-1/2
                w-2 h-2 bg-slate-900
                rotate-45
                ${tooltipPosition === "top" ? "bottom-0 translate-y-1/2" : "top-0 -translate-y-1/2"}
              `}
            />
            
            <div className="relative">
              <p className="font-semibold mb-1 truncate">
                {citationInfo.title}
              </p>
              <p className="text-slate-300 line-clamp-6 max-h-36 overflow-y-auto">
                {citationInfo.content.substring(0, 400)}
                {citationInfo.content.length > 400 ? "..." : ""}
              </p>
            </div>
          </div>
        )}
      </span>
    );
  };

  // If no citation markers or empty citationMap, just render text
  if (!parts.some(p => p.type === "citation") || Object.keys(citationMap).length === 0) {
    return <span>{text}</span>;
  }

  return <span className="inline">{parts.map(renderPart)}</span>;
}
