"use client";

import { RiskLevel } from "@/lib/types";

interface RiskIndicatorProps {
  risk: RiskLevel;
  showLabel?: boolean;
  size?: "sm" | "md" | "lg";
}

const config: Record<
  RiskLevel,
  {
    label: string;
    bgColor: string;
    textColor: string;
    dotColor: string;
  }
> = {
  high: {
    label: "High Risk",
    bgColor: "bg-red-100",
    textColor: "text-red-800",
    dotColor: "bg-red-500",
  },
  medium: {
    label: "Medium Risk",
    bgColor: "bg-yellow-100",
    textColor: "text-yellow-800",
    dotColor: "bg-yellow-500",
  },
  low: {
    label: "Low Risk",
    bgColor: "bg-blue-100",
    textColor: "text-blue-800",
    dotColor: "bg-blue-500",
  },
  none: {
    label: "No Risk",
    bgColor: "bg-green-100",
    textColor: "text-green-800",
    dotColor: "bg-green-500",
  },
};

export function RiskIndicator({
  risk,
  showLabel = true,
  size = "md",
}: RiskIndicatorProps) {
  const { label, bgColor, textColor, dotColor } = config[risk] || config.none;

  const sizeClasses = {
    sm: "px-2 py-0.5 text-xs gap-1.5",
    md: "px-3 py-1 text-sm gap-2",
    lg: "px-4 py-2 text-base gap-2.5",
  };

  const dotSizes = {
    sm: "w-1.5 h-1.5",
    md: "w-2 h-2",
    lg: "w-2.5 h-2.5",
  };

  return (
    <span
      className={`inline-flex items-center rounded-full ${bgColor} ${textColor} ${sizeClasses[size]} font-medium`}
    >
      <span className={`rounded-full ${dotColor} ${dotSizes[size]}`} />
      {showLabel && <span>{label}</span>}
    </span>
  );
}
