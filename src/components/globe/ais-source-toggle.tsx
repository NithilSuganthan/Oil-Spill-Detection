"use client";

import * as React from "react";
import { Radio, MonitorPlay } from "lucide-react";
import { cn } from "@/lib/utils";

interface AisSourceToggleProps {
  aisSource: "realtime" | "demo";
  onSourceChange: (source: "realtime" | "demo") => void;
  isStreamConnected?: boolean;
  className?: string;
}

export function AisSourceToggle({
  aisSource,
  onSourceChange,
  isStreamConnected = false,
  className,
}: AisSourceToggleProps) {
  const isRealtime = aisSource === "realtime";

  return (
    <div className={cn("glass-panel p-3 w-56", className)}>
      <h3 className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-ink-dim mb-2.5">
        AIS Data Source
      </h3>

      {/* Toggle Buttons */}
      <div className="flex gap-1.5 mb-2.5">
        <button
          onClick={() => onSourceChange("realtime")}
          className={cn(
            "flex-1 rounded px-2 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider transition-all",
            isRealtime
              ? "bg-signal-green/15 text-signal-green border border-signal-green/40"
              : "bg-base-800/40 text-ink-faint border border-line hover:bg-base-800/60 hover:text-ink-dim"
          )}
        >
          REAL-TIME
        </button>
        <button
          onClick={() => onSourceChange("demo")}
          className={cn(
            "flex-1 rounded px-2 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider transition-all",
            !isRealtime
              ? "bg-signal-amber/15 text-signal-amber border border-signal-amber/40"
              : "bg-base-800/40 text-ink-faint border border-line hover:bg-base-800/60 hover:text-ink-dim"
          )}
        >
          DEMO
        </button>
      </div>

      {/* Status Indicator */}
      <div className="flex items-center gap-2 rounded bg-base-800/40 px-2 py-1.5">
        <span
          className={cn(
            "status-dot",
            isRealtime
              ? isStreamConnected
                ? "text-signal-green"
                : "text-signal-red"
              : "text-signal-amber"
          )}
        />
        <Radio
          className="h-3 w-3 shrink-0"
          style={{ color: isRealtime ? (isStreamConnected ? "#34d399" : "#f87171") : "#fbbf24" }}
        />
        <div className="min-w-0 flex-1">
          <span className="font-mono text-[10px] font-bold text-ink">
            AISSTREAM
          </span>
          <div className="font-mono text-[9px] text-ink-faint">
            {isRealtime ? (
              isStreamConnected ? "REAL-TIME" : "UNAVAILABLE"
            ) : (
              "DEMO / SIMULATED"
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
