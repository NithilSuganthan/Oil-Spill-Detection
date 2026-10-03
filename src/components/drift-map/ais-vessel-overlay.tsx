"use client";

import * as React from "react";
import { Ship, MapPin, ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CandidateVessel } from "@/lib/types";

export function AisVesselOverlay({
  candidates,
  isRealData,
}: {
  candidates: CandidateVessel[];
  isRealData: boolean;
}) {
  const [expanded, setExpanded] = React.useState(false);

  if (candidates.length === 0) return null;

  const sorted = [...candidates].sort((a, b) => b.attributionScore - a.attributionScore);
  const topScore = sorted[0]?.attributionScore ?? 0;

  return (
    <div className="panel w-64 shadow-panel">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
      >
        <Ship className="h-3.5 w-3.5 text-signal-cyan" />
        <span className="font-mono text-[10px] font-medium uppercase tracking-wider text-ink-dim">
          AIS ({candidates.length})
        </span>
        <span
          className={cn(
            "ml-auto rounded border px-1.5 py-px font-mono text-[8px] font-bold uppercase tracking-wider",
            isRealData
              ? "border-signal-green/40 text-signal-green"
              : "border-signal-amber/40 text-signal-amber"
          )}
        >
          {isRealData ? "LIVE" : "DEMO"}
        </span>
        {expanded ? (
          <ChevronDown className="h-3 w-3 text-ink-faint" />
        ) : (
          <ChevronRight className="h-3 w-3 text-ink-faint" />
        )}
      </button>

      {expanded && (
        <div className="max-h-40 space-y-1 overflow-y-auto border-t border-line px-2 py-1.5">
          {sorted.map((vessel) => {
            const isTop = vessel.attributionScore === topScore;
            return (
              <div
                key={vessel.mmsi}
                className={cn(
                  "flex items-center gap-2 rounded px-2 py-1.5 transition-colors",
                  isTop ? "bg-signal-cyan/10" : "hover:bg-base-700/50"
                )}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className="truncate text-[10px] font-medium text-ink">
                      {vessel.vesselName ?? `MMSI ${vessel.mmsi}`}
                    </span>
                    {isTop && (
                      <span className="shrink-0 rounded bg-signal-cyan/20 px-1 py-px text-[7px] font-bold text-signal-cyan">
                        TOP
                      </span>
                    )}
                  </div>
                    <div className="text-[8px] text-ink-faint">
                      {vessel.vesselType ?? "Unknown"} · {vessel.flag ?? "—"} · {vessel.closestDistanceKm?.toFixed(1) ?? "?"} km
                    </div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-[10px] text-signal-amber">
                    {(vessel.attributionScore * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
