import type { ConfidenceLevel } from "@/lib/types";

export const LEVEL_COLORS: Record<ConfidenceLevel, { fill: string; line: string }> = {
  HIGH: { fill: "#f87171", line: "#fca5a5" },
  MEDIUM: { fill: "#fb923c", line: "#fdba74" },
  LOW: { fill: "#facc15", line: "#eab308" },
};

export function detectionFillExpression(selectedId: string | null): unknown[] {
  return [
    "case",
    ["==", ["get", "id"], selectedId ?? "__none__"],
    ["match", ["get", "level"], "HIGH", "#ef4444", "MEDIUM", "#ea580c", "#ca8a04"],
    [
      "match",
      ["get", "level"],
      "HIGH",
      LEVEL_COLORS.HIGH.fill,
      "MEDIUM",
      LEVEL_COLORS.MEDIUM.fill,
      LEVEL_COLORS.LOW.fill,
    ],
  ];
}
