"use client";

interface ConfidenceBarProps {
  confidence: number; // 0-1
  showLabel?: boolean;
  size?: "sm" | "md";
}

export function ConfidenceBar({
  confidence,
  showLabel = true,
  size = "md",
}: ConfidenceBarProps) {
  const percentage = Math.round(confidence * 100);

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
          {percentage}%
        </span>
      </div>
      <div className={`w-full bg-slate-200 rounded-full ${heightClasses[size]}`}>
        <div
          className={`${heightClasses[size]} rounded-full ${getColor(
            percentage
          )} transition-all duration-500`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
