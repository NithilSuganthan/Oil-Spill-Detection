"use client";

import * as React from "react";
import { Link2, ArrowRight } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import type { Incident } from "@/lib/types";

interface ProgressStage {
  id: string;
  label: string;
  shortLabel: string;
}

const PROGRESS_STAGES: ProgressStage[] = [
  { id: "satellite", label: "SAR ACQUIRED", shortLabel: "SAR" },
  { id: "preprocessing", label: "PREPROCESSED", shortLabel: "PRE" },
  { id: "segmentation", label: "SEGMENTATION", shortLabel: "SEG" },
  { id: "detection", label: "DETECTION", shortLabel: "DET" },
  { id: "drift", label: "DRIFT", shortLabel: "DRF" },
  { id: "attribution", label: "AIS", shortLabel: "AIS" },
  { id: "report", label: "REPORT", shortLabel: "RPT" },
];

type StageStatus = "waiting" | "running" | "complete" | "failed";

function getStageStatus(
  stageId: string,
  incident: Incident
): StageStatus {
  // Map incident status to stage completion
  if (incident.status === "completed") {
    // All stages except report are complete for completed incidents
    if (stageId === "report") return "waiting";
    return "complete";
  }
  if (incident.status === "processing") {
    // Detection and earlier are done, later stages are waiting
    const stageOrder = ["satellite", "preprocessing", "segmentation", "detection", "drift", "attribution", "report"];
    const stageIdx = stageOrder.indexOf(stageId);
    if (stageIdx <= 3) return "complete"; // through detection
    if (stageIdx === 4) return "running"; // drift
    return "waiting";
  }
  // review status
  return "waiting";
}

export function InvestigationProgress({ incident }: { incident: Incident | null }) {
  if (!incident) return null;

  const completedCount = PROGRESS_STAGES.filter(
    (s) => getStageStatus(s.id, incident) === "complete"
  ).length;

  return (
    <div className="panel px-3 py-2.5">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link2 className="h-3.5 w-3.5 text-signal-cyan" />
          <span className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-ink-dim">
            Investigation Status
          </span>
        </div>
        <span className="font-mono text-[9px] tabular-nums text-ink-faint">
          {completedCount}/{PROGRESS_STAGES.length}
        </span>
      </div>

      <div className="flex items-center gap-1">
        {PROGRESS_STAGES.map((stage, idx) => {
          const status = getStageStatus(stage.id, incident);
          const isComplete = status === "complete";
          const isActive = status === "running";

          return (
            <React.Fragment key={stage.id}>
              <div
                className={cn(
                  "flex h-6 items-center justify-center rounded px-1.5 font-mono text-[8px] font-bold uppercase tracking-wider transition-all",
                  isComplete
                    ? "bg-signal-green/15 text-signal-green"
                    : isActive
                      ? "bg-signal-cyan/15 text-signal-cyan progress-active"
                      : "bg-base-800 text-ink-faint"
                )}
                title={stage.label}
              >
                <span className="hidden sm:inline">{stage.shortLabel}</span>
                <span className="sm:hidden">{idx + 1}</span>
              </div>
              {idx < PROGRESS_STAGES.length - 1 && (
                <div
                  className={cn(
                    "h-px flex-1 min-w-[4px] transition-colors",
                    isComplete ? "bg-signal-green/40" : "bg-line"
                  )}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>

      <Link
        href="/live-analysis"
        className="mt-2 flex items-center justify-center gap-1 rounded border border-line py-1 font-mono text-[9px] uppercase tracking-wider text-ink-faint transition-colors hover:border-signal-cyan/40 hover:text-signal-cyan"
      >
        View Live Analysis <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  );
}
