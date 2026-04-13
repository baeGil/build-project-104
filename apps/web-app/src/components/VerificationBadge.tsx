"use client";

import { VerificationLevel } from "@/lib/types";
import { CheckCircle, XCircle, AlertCircle, HelpCircle } from "lucide-react";

interface VerificationBadgeProps {
  verification: VerificationLevel;
  showLabel?: boolean;
  size?: "sm" | "md" | "lg";
}

const config: Record<
  VerificationLevel,
  {
    icon: React.ElementType;
    label: string;
    bgColor: string;
    textColor: string;
    borderColor: string;
  }
> = {
  entailed: {
    icon: CheckCircle,
    label: "Compliant",
    bgColor: "bg-green-50",
    textColor: "text-green-700",
    borderColor: "border-green-200",
  },
  contradicted: {
    icon: XCircle,
    label: "Contradicted",
    bgColor: "bg-red-50",
    textColor: "text-red-700",
    borderColor: "border-red-200",
  },
  partially_supported: {
    icon: AlertCircle,
    label: "Partial",
    bgColor: "bg-yellow-50",
    textColor: "text-yellow-700",
    borderColor: "border-yellow-200",
  },
  no_reference: {
    icon: HelpCircle,
    label: "No Reference",
    bgColor: "bg-gray-50",
    textColor: "text-gray-700",
    borderColor: "border-gray-200",
  },
};

export function VerificationBadge({
  verification,
  showLabel = true,
  size = "md",
}: VerificationBadgeProps) {
  const { icon: Icon, label, bgColor, textColor, borderColor } =
    config[verification] || config.no_reference;

  const sizeClasses = {
    sm: "px-2 py-0.5 text-xs gap-1",
    md: "px-3 py-1 text-sm gap-1.5",
    lg: "px-4 py-2 text-base gap-2",
  };

  const iconSizes = {
    sm: "w-3 h-3",
    md: "w-4 h-4",
    lg: "w-5 h-5",
  };

  return (
    <span
      className={`inline-flex items-center rounded-full border ${bgColor} ${textColor} ${borderColor} ${sizeClasses[size]} font-medium`}
    >
      <Icon className={iconSizes[size]} />
      {showLabel && <span>{label}</span>}
    </span>
  );
}
