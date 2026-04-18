"use client";

interface ConfidenceBarProps {
  confidence: number; // 0-100 (percentage)
  showLabel?: boolean;
  size?: "sm" | "md";
}

export function ConfidenceBar({
  confidence,
  showLabel = true,
  size = "md",
}: ConfidenceBarProps) {
  // Backend sends confidence as 0-100, but component expects 0-1
  // Normalize: if > 1, assume it's already percentage
  const normalizedConfidence = confidence > 1 ? confidence / 100 : confidence;
  const percentage = Math.round(normalizedConfidence * 100);
  
  // Clamp to 0-100 range
  const clampedPercentage = Math.max(0, Math.min(100, percentage));

  const getColor = (p: number) => {
    if (p >= 80) return "bg-green-500";
    if (p >= 60) return "bg-blue-500";
    if (p >= 40) return "bg-yellow-500";
    return "bg-red-500";
  };

  const heightClasses = {
    sm: "h-1.5",
    md: "h-2",
  };

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-1">
        {showLabel && (
          <span className="text-xs text-muted">Confidence</span>
        )}
        <span className="text-xs font-medium text-slate-700">
          {clampedPercentage}%
        </span>
      </div>
      <div className={`w-full bg-slate-200 rounded-full ${heightClasses[size]}`}>
        <div
          className={`${heightClasses[size]} rounded-full ${getColor(
            clampedPercentage
          )} transition-all duration-500`}
          style={{ width: `${clampedPercentage}%` }}
        />
      </div>
    </div>
  );
}
