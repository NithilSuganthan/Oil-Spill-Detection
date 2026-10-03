"use client";

import * as React from "react";
import {
  Satellite,
  Cpu,
  Brain,
  MapPin,
  Waves,
  Anchor,
  FileText,
  CheckCircle2,
  Loader2,
  AlertCircle,
  Clock,
  Ban,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatISTTimeShort } from "@/lib/utils";
import type { StageStatus } from "@/app/live-analysis/page";

interface StageState {
  id: string;
  status: StageStatus;
  label: string;
  sublabel: string;
  detail?: string;
  timestamp?: string;
}

const STAGE_ICONS: Record<string, React.ReactNode> = {
  satellite: <Satellite className="h-4 w-4" />,
  preprocessing: <Cpu className="h-4 w-4" />,
  segmentation: <Brain className="h-4 w-4" />,
  detection: <MapPin className="h-4 w-4" />,
  drift: <Waves className="h-4 w-4" />,
  attribution: <Anchor className="h-4 w-4" />,
  report: <FileText className="h-4 w-4" />,
};

function StatusIcon({ status }: { status: StageStatus }) {
  switch (status) {
    case "complete":
      return <CheckCircle2 className="h-3.5 w-3.5 text-signal-green" />;
    case "running":
      return <Loader2 className="h-3.5 w-3.5 animate-spin text-signal-cyan" />;
    case "failed":
      return <AlertCircle className="h-3.5 w-3.5 text-signal-red" />;
    case "skipped":
      return <Ban className="h-3.5 w-3.5 text-ink-faint" />;
    default:
      return <div className="h-3.5 w-3.5 rounded-full border border-line-bright" />;
  }
}

function StageCard({
  stage,
  index,
  onGenerateReport,
}: {
  stage: StageState;
  index: number;
  onGenerateReport?: () => void;
}) {
  const isActive = stage.status === "running";
  const isComplete = stage.status === "complete";

  return (
    <div className="flex flex-col items-center">
      <div
        className={cn(
          "relative flex w-full flex-col items-center rounded-lg border px-3 py-3 text-center transition-all duration-500",
          isActive
            ? "border-signal-cyan/60 bg-signal-cyan/[0.07] shadow-[0_0_20px_rgba(56,189,248,0.1)]"
            : isComplete
              ? "border-signal-green/30 bg-signal-green/[0.04]"
              : stage.status === "failed"
                ? "border-signal-red/40 bg-signal-red/5"
                : "border-line bg-base-900/50"
        )}
      >
        <span className="absolute -left-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full border border-line bg-base-950 font-mono text-[9px] text-ink-faint">
          {String(index + 1).padStart(2, "0")}
        </span>

        <div
          className={cn(
            "mb-2 flex h-8 w-8 items-center justify-center rounded-full border transition-colors",
            isActive
              ? "border-signal-cyan/50 bg-signal-cyan/15 text-signal-cyan"
              : isComplete
                ? "border-signal-green/40 bg-signal-green/10 text-signal-green"
                : "border-line bg-base-800 text-ink-faint"
          )}
        >
          {STAGE_ICONS[stage.id] ?? <Cpu className="h-4 w-4" />}
        </div>

        <p className="font-mono text-[10px] font-bold tracking-widest text-ink">
          {stage.label}
        </p>
        <p className="mt-0.5 font-mono text-[9px] text-ink-faint">
          {stage.sublabel}
        </p>

        <div className="mt-2 flex items-center gap-1.5">
          <StatusIcon status={stage.status} />
          <span
            className={cn(
              "font-mono text-[9px] uppercase tracking-wider",
              isActive
                ? "text-signal-cyan"
                : isComplete
                  ? "text-signal-green"
                  : stage.status === "failed"
                    ? "text-signal-red"
                    : "text-ink-faint"
            )}
          >
            {stage.status.toUpperCase()}
          </span>
        </div>

        {stage.timestamp && (
          <p className="mt-1 font-mono text-[8px] text-ink-faint">
            {formatISTTimeShort(stage.timestamp)}
          </p>
        )}

        {stage.id === "report" && stage.status === "waiting" && onGenerateReport && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onGenerateReport();
            }}
            className="mt-2 rounded border border-signal-cyan/40 bg-signal-cyan/10 px-2 py-0.5 font-mono text-[8px] text-signal-cyan hover:bg-signal-cyan/20"
          >
            GENERATE
          </button>
        )}
      </div>

      {index < 6 && (
        <div className="relative mt-1 flex h-6 w-px items-center">
          <div
            className={cn(
              "h-full w-px transition-colors duration-500",
              isComplete ? "bg-signal-green/40" : "bg-line"
            )}
          />
        </div>
      )}
    </div>
  );
}

export function PipelineStages({
  stages,
  simulationMode,
  pipelineStartTime,
  onGenerateReport,
}: {
  stages: StageState[];
  simulationMode: boolean;
  pipelineStartTime: number | null;
  onGenerateReport?: () => void;
}) {
  return (
    <div className="panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-ink-dim">
          Investigation Pipeline
        </h2>
        {simulationMode && (
          <span className="rounded border border-signal-amber/40 bg-signal-amber/10 px-2 py-0.5 font-mono text-[9px] tracking-wider text-signal-amber">
            SIMULATION
          </span>
        )}
      </div>

      {/* Desktop: horizontal */}
      <div className="hidden lg:grid lg:grid-cols-7 lg:gap-1">
        {stages.map((stage, idx) => (
          <StageCard
            key={stage.id}
            stage={stage}
            index={idx}
            onGenerateReport={onGenerateReport}
          />
        ))}
      </div>

      {/* Mobile: vertical */}
      <div className="space-y-2 lg:hidden">
        {stages.map((stage, idx) => (
          <div key={stage.id} className="flex items-center gap-3">
            <div
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border transition-colors",
                stage.status === "running"
                  ? "border-signal-cyan/50 bg-signal-cyan/15 text-signal-cyan"
                  : stage.status === "complete"
                    ? "border-signal-green/40 bg-signal-green/10 text-signal-green"
                    : "border-line bg-base-800 text-ink-faint"
              )}
            >
              {STAGE_ICONS[stage.id] ?? <Cpu className="h-4 w-4" />}
            </div>
            <div className="min-h-0 flex-1">
              <div className="flex items-center gap-2">
                <p className="font-mono text-[10px] font-bold tracking-widest text-ink">
                  {stage.label}
                </p>
                <StatusIcon status={stage.status} />
              </div>
              <p className="font-mono text-[9px] text-ink-faint">{stage.sublabel}</p>
            </div>
            <span
              className={cn(
                "font-mono text-[9px] uppercase tracking-wider",
                stage.status === "running"
                  ? "text-signal-cyan"
                  : stage.status === "complete"
                    ? "text-signal-green"
                    : "text-ink-faint"
              )}
            >
              {stage.status.toUpperCase()}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
