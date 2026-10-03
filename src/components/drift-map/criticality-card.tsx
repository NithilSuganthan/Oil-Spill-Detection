"use client";

import * as React from "react";
import { AlertTriangle, ChevronDown, ChevronRight, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CriticalityScore } from "@/lib/types";

const LEVEL_COLORS = {
  LOW: {
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
    text: "text-emerald-400",
    badge: "border-emerald-500/40 bg-emerald-500/15 text-emerald-400",
    bar: "bg-emerald-400",
  },
  MID: {
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    text: "text-amber-400",
    badge: "border-amber-500/40 bg-amber-500/15 text-amber-400",
    bar: "bg-amber-400",
  },
  HIGH: {
    bg: "bg-orange-500/10",
    border: "border-orange-500/30",
    text: "text-orange-400",
    badge: "border-orange-500/40 bg-orange-500/15 text-orange-400",
    bar: "bg-orange-400",
  },
  CRITICAL: {
    bg: "bg-red-500/10",
    border: "border-red-500/30",
    text: "text-red-400",
    badge: "border-red-500/40 bg-red-500/15 text-red-400",
    bar: "bg-red-400",
  },
} as const;

export function CriticalityCard({
  criticality,
}: {
  criticality: CriticalityScore | null;
}) {
  const [expanded, setExpanded] = React.useState(true);

  if (!criticality) {
    return (
      <div className="rounded bg-base-950/60 border border-line/50 p-2.5 font-mono text-[10px]">
        <div className="flex items-center gap-2 text-ink-faint">
          <AlertTriangle className="h-3 w-3" />
          <span>CRITICALITY SCORE PENDING</span>
        </div>
      </div>
    );
  }

  const colors = LEVEL_COLORS[criticality.level] ?? LEVEL_COLORS.LOW;

  return (
    <div className={cn("rounded border p-2.5", colors.bg, colors.border)}>
      {/* Score Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <AlertTriangle className={cn("h-3.5 w-3.5", colors.text)} />
          <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-ink-dim">
            OPERATIONAL CRITICALITY
          </span>
        </div>
        <span
          className={cn(
            "rounded border px-1.5 py-px font-mono text-[8px] font-extrabold uppercase tracking-wider",
            colors.badge
          )}
        >
          {criticality.level}
        </span>
      </div>

      {/* Score Display */}
      <div className="flex items-baseline gap-2 mb-2">
        <span className={cn("font-mono text-[22px] font-extrabold", colors.text)}>
          {criticality.score}
        </span>
        <span className="font-mono text-[10px] text-ink-faint">/ 100</span>
        <span className="ml-auto font-mono text-[9px] text-ink-faint">
          {criticality.action}
        </span>
      </div>

      {/* Score Bar */}
      <div className="h-1.5 rounded-full bg-base-950/60 overflow-hidden mb-2">
        <div
          className={cn("h-full rounded-full transition-all duration-500", colors.bar)}
          style={{ width: `${criticality.score}%` }}
        />
      </div>

      {/* Factor Count */}
      <div className="flex justify-between items-center text-[9px] font-mono text-ink-faint mb-1">
        <span>
          {criticality.availableFactorCount} / {criticality.totalFactorCount} FACTORS AVAILABLE
        </span>
        <button
          onClick={() => setExpanded((e) => !e)}
          className="flex items-center gap-1 text-ink-faint hover:text-ink transition-colors"
        >
          {expanded ? "HIDE" : "SHOW"} BREAKDOWN
          {expanded ? (
            <ChevronDown className="h-3 w-3" />
          ) : (
            <ChevronRight className="h-3 w-3" />
          )}
        </button>
      </div>

      {/* Factor Breakdown */}
      {expanded && (
        <div className="space-y-1 mt-2">
          {criticality.factors.map((factor) => (
            <div
              key={factor.name}
              className={cn(
                "flex items-center justify-between rounded p-1.5 border text-[9px] font-mono",
                factor.available
                  ? "bg-base-950/40 border-line/40"
                  : "bg-base-950/20 border-line/20 border-dashed"
              )}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1">
                  <span
                    className={cn(
                      "font-semibold truncate",
                      factor.available ? "text-ink-dim" : "text-ink-faint"
                    )}
                  >
                    {factor.label}
                  </span>
                  {!factor.available && (
                    <span className="text-[7px] px-1 py-px rounded bg-amber-500/15 border border-amber-500/30 text-amber-400 font-bold uppercase shrink-0">
                      N/A
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0 ml-2">
                {factor.available ? (
                  <>
                    <div className="w-12 h-1 rounded-full bg-base-950/60 overflow-hidden">
                      <div
                        className={cn("h-full rounded-full", colors.bar)}
                        style={{ width: `${factor.score}%` }}
                      />
                    </div>
                    <span className="text-ink font-semibold w-8 text-right">
                      {Math.round(factor.score)}
                    </span>
                  </>
                ) : (
                  <span className="text-ink-faint text-[8px]">UNAVAILABLE</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Normalization Note (when factors are missing) */}
      {criticality.availableFactorCount < criticality.totalFactorCount && (
        <div className="mt-2 rounded bg-amber-500/10 border border-amber-500/30 p-2">
          <div className="flex items-start gap-1.5">
            <Info className="h-3 w-3 text-amber-400 shrink-0 mt-0.5" />
            <span className="text-[8px] text-amber-300 leading-relaxed">
              {criticality.normalizationNote}
            </span>
          </div>
        </div>
      )}

      {/* Methodology Disclaimer */}
      <div className="mt-2 text-[7px] text-ink-faint font-mono leading-relaxed">
        Heuristic weights — NOT scientifically validated. For operational triage only.
      </div>
    </div>
  );
}
