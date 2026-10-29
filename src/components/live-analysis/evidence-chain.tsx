"use client";

import * as React from "react";
import { Link2, ArrowDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { StageStatus } from "@/app/live-analysis/page";

interface ChainStage {
  id: string;
  label: string;
}

const CHAIN_STAGES: ChainStage[] = [
  { id: "satellite", label: "SAR" },
  { id: "preprocessing", label: "PREPROC" },
  { id: "segmentation", label: "AI MODEL" },
  { id: "detection", label: "DETECTION" },
  { id: "drift", label: "DRIFT" },
  { id: "attribution", label: "AIS" },
  { id: "report", label: "REPORT" },
];

export function EvidenceChain({ stages }: { stages: { id: string; status: StageStatus }[] }) {
  const stageStatusMap = React.useMemo(() => {
    const map: Record<string, StageStatus> = {};
    stages.forEach((s) => {
      map[s.id] = s.status;
    });
    return map;
  }, [stages]);

  const completedCount = stages.filter((s) => s.status === "complete").length;

  return (
    <div className="panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link2 className="h-4 w-4 text-signal-cyan" />
          <h2 className="font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-ink-dim">
            Evidence Chain
          </h2>
        </div>
        <span className="font-mono text-[9px] tabular-nums text-ink-faint">
          {completedCount}/{CHAIN_STAGES.length}
        </span>
      </div>

      <div className="flex items-center justify-between">
        {CHAIN_STAGES.map((stage, idx) => {
          const status = stageStatusMap[stage.id] ?? "waiting";
          const isActive = status === "running";
          const isComplete = status === "complete";

          return (
            <React.Fragment key={stage.id}>
              <div className="flex flex-col items-center">
                <div
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-lg border text-[9px] font-mono font-bold transition-all duration-500",
                    isActive
                      ? "border-signal-cyan/60 bg-signal-cyan/15 text-signal-cyan shadow-[0_0_12px_rgba(56,189,248,0.2)]"
                      : isComplete
                        ? "border-signal-green/40 bg-signal-green/10 text-signal-green"
                        : status === "failed"
                          ? "border-signal-red/40 bg-signal-red/10 text-signal-red"
                          : "border-line bg-base-850 text-ink-faint"
                  )}
                >
                  {isComplete ? "✓" : isActive ? "◉" : idx + 1}
                </div>
                <p
                  className={cn(
                    "mt-1.5 text-center font-mono text-[7px] uppercase tracking-wider",
                    isActive ? "text-signal-cyan" : isComplete ? "text-signal-green" : "text-ink-faint"
                  )}
                >
                  {stage.label}
                </p>
              </div>
              {idx < CHAIN_STAGES.length - 1 && (
                <div className="mt-[-14px] flex flex-col items-center">
                  <div
                    className={cn(
                      "h-px w-6 transition-colors duration-500 sm:w-8 md:w-12",
                      isComplete ? "bg-signal-green/40" : "bg-line"
                    )}
                  />
                  <ArrowDown
                    className={cn(
                      "hidden h-3 w-3 sm:block",
                      isComplete ? "text-signal-green/60" : "text-line-bright"
                    )}
                  />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      <p className="mt-3 text-center text-[9px] italic text-ink-faint/70">
        Evidence flows from SAR acquisition through AI segmentation, drift modelling, and AIS correlation to vessel attribution.
      </p>
    </div>
  );
}
