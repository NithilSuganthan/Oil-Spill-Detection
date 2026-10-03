"use client";

import * as React from "react";

export function DriftLegend() {
  return (
    <div className="panel border-line bg-base-900/90 px-3 py-2.5 shadow-xl backdrop-blur-md">
      <div className="mb-2 font-mono text-[9px] font-bold uppercase tracking-widest text-ink-dim border-b border-line/60 pb-1 flex items-center justify-between">
        <span>LEGEND</span>
        <span className="text-[8px] text-ink-faint">HINDCAST FLOW</span>
      </div>
      <div className="space-y-1.5 font-mono text-[9px]">
        <div className="flex items-center gap-2">
          <div className="h-2.5 w-2.5 rounded-sm bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.7)]" />
          <span className="text-ink font-medium">Detected Slick</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-2 w-2.5 rounded-sm bg-amber-500" />
          <span className="text-ink-dim">Backward Drift (0–2h)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-2 w-2.5 rounded-sm bg-yellow-500" />
          <span className="text-ink-dim">Backward Drift (2–4h)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-2 w-2.5 rounded-sm bg-teal-400" />
          <span className="text-ink-dim">Backward Drift (4–6h)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-2 w-2.5 rounded-sm bg-cyan-400" />
          <span className="text-ink-dim">Backward Drift (6–8h)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
          <span className="text-emerald-400 font-semibold">Estimated Source</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-2.5 w-2.5 rounded-full border border-dashed border-cyan-400/80 bg-cyan-400/10" />
          <span className="text-ink-faint">Source Uncertainty</span>
        </div>
      </div>
    </div>
  );
}
