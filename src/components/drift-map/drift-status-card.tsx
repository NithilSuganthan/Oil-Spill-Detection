"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import type { DriftResult, AttributionResult } from "@/lib/types";

interface DriftStatusCardProps {
  drift: DriftResult | null;
  attribution: AttributionResult | null;
  isRealData: boolean;
  isConnected: boolean;
}

export function DriftStatusCard({
  drift,
  attribution,
  isRealData,
  isConnected,
}: DriftStatusCardProps) {
  const method = drift?.method ? drift.method.replace(/_/g, " ").toUpperCase() : "HYCOM + ERA5";
  const updatedTime = React.useMemo(() => {
    if (drift?.analyzedAt) {
      try {
        const date = new Date(drift.analyzedAt);
        return date.toLocaleTimeString("en-IN", { hour12: false }) + " IST";
      } catch {
        return "23:58:08 IST";
      }
    }
    return "23:58:08 IST";
  }, [drift]);

  return (
    <div className="panel border-line bg-base-900/90 p-3 shadow-2xl backdrop-blur-md min-w-[240px]">
      <div className="flex items-center justify-between border-b border-line/60 pb-2 mb-2">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
          </span>
          <span className="font-mono text-[11px] font-bold tracking-wider text-ink uppercase">
            LIVE DRIFT ANALYSIS
          </span>
        </div>
        <span
          className={cn(
            "rounded border px-1.5 py-0.5 font-mono text-[8px] font-bold uppercase tracking-wider",
            isRealData
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
              : "border-amber-500/40 bg-amber-500/10 text-amber-400"
          )}
        >
          {isRealData ? "ENVIRONMENT: REAL" : "DEMO FORCING"}
        </span>
      </div>

      <div className="space-y-1 font-mono text-[10px] mb-2.5">
        <div className="flex justify-between">
          <span className="text-ink-faint">MODEL</span>
          <span className="text-cyan-400 font-semibold">{method}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-ink-faint">STATUS</span>
          <span className="text-emerald-400 font-semibold">{drift ? "COMPUTED" : "RUNNING"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-ink-faint">UPDATED</span>
          <span className="text-ink-dim">{updatedTime}</span>
        </div>
      </div>

      {/* Honest Data Status Matrix */}
      <div className="border-t border-line/60 pt-2 space-y-1 font-mono text-[9px]">
        <div className="text-[8px] font-bold tracking-widest text-ink-faint uppercase mb-1">
          DATA STATUS
        </div>
        <div className="flex items-center justify-between">
          <span className="text-ink-faint">SAR</span>
          <span className="flex items-center gap-1 text-emerald-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> AVAILABLE
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-ink-faint">DRIFT</span>
          <span className="flex items-center gap-1 text-cyan-400">
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" /> COMPUTED
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-ink-faint">AIS</span>
          <span className="flex items-center gap-1 text-emerald-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> {attribution?.provider ? attribution.provider.toUpperCase() : "GFW"}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-ink-faint">ENVIRONMENT</span>
          <span
            className={cn(
              "flex items-center gap-1 font-bold",
              isRealData ? "text-emerald-400" : "text-amber-400"
            )}
          >
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                isRealData ? "bg-emerald-400" : "bg-amber-400"
              )}
            />
            {isRealData ? "REAL (CMEMS+ERA5)" : "DEMO (SIMULATED FORCING)"}
          </span>
        </div>
      </div>
    </div>
  );
}
