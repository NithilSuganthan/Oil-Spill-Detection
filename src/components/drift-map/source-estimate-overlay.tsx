"use client";

import * as React from "react";
import { Target, AlertTriangle } from "lucide-react";
import type { DriftResult } from "@/lib/types";

export function SourceEstimateOverlay({
  drift,
  onLocate,
}: {
  drift: DriftResult | null;
  onLocate?: () => void;
}) {
  if (!drift || drift.sourceLatitude == null || drift.sourceLongitude == null) {
    return (
      <div className="panel flex items-center gap-2 px-3 py-2">
        <AlertTriangle className="h-3.5 w-3.5 text-signal-amber" />
        <span className="text-[10px] text-ink-faint">No source estimate available</span>
      </div>
    );
  }

  return (
    <div className="panel flex items-center gap-3 px-3 py-2">
      <div className="flex h-6 w-6 items-center justify-center rounded bg-signal-cyan/15">
        <Target className="h-3.5 w-3.5 text-signal-cyan" />
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[9px] font-medium uppercase tracking-wider text-ink-dim">
            Source Estimate
          </span>
          {drift.uncertaintyKm !== undefined && (
            <span className="rounded bg-signal-cyan/10 px-1.5 py-px font-mono text-[8px] text-signal-cyan">
              ± {drift.uncertaintyKm.toFixed(1)} km
            </span>
          )}
        </div>
        <span className="font-mono text-[11px] text-ink">
          {drift.sourceLatitude.toFixed(4)}°, {drift.sourceLongitude.toFixed(4)}°
        </span>
      </div>
      {onLocate && (
        <button
          onClick={onLocate}
          className="rounded border border-line px-2 py-1 font-mono text-[8px] text-ink-dim transition-colors hover:border-line-bright hover:text-ink"
        >
          LOCATE
        </button>
      )}
    </div>
  );
}
