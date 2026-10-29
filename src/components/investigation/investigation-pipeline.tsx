"use client";

import * as React from "react";
import {
  Target,
  Wind,
  Route,
  Ship,
  Shield,
  ClipboardCheck,
  FileText,
  Check,
  Loader2,
  AlertCircle,
  Ban,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type StageStatus = "complete" | "active" | "available" | "pending" | "unavailable" | "error";

export interface PipelineStage {
  id: string;
  number: string;
  label: string;
  icon: React.ElementType;
  status: StageStatus;
  statusText: string;
  detail?: string;
}

interface InvestigationPipelineProps {
  stages: PipelineStage[];
  activeStageId?: string | null;
  onStageClick?: (stageId: string) => void;
}

function StatusIndicator({ status }: { status: StageStatus }) {
  switch (status) {
    case "complete":
      return (
        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 border border-emerald-400/50 shadow-[0_0_8px_rgba(52,211,153,0.3)]">
          <Check className="h-3 w-3 text-emerald-400" />
        </div>
      );
    case "active":
      return (
        <div className="relative flex h-5 w-5 items-center justify-center">
          <div className="absolute inset-0 rounded-full border border-cyan-400/80 bg-cyan-400/20 animate-ping" />
          <div className="relative flex h-4.5 w-4.5 items-center justify-center rounded-full bg-cyan-500/30 border border-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.5)]">
            <Loader2 className="h-2.5 w-2.5 text-cyan-300 animate-spin" />
          </div>
        </div>
      );
    case "available":
      return (
        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-cyan-500/10 border border-cyan-400/40">
          <div className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse" />
        </div>
      );
    case "error":
      return (
        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-red-500/20 border border-red-500/50">
          <AlertCircle className="h-3 w-3 text-red-400" />
        </div>
      );
    case "unavailable":
      return (
        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-base-900 border border-line/50">
          <Ban className="h-2.5 w-2.5 text-ink-faint/40" />
        </div>
      );
    default:
      return (
        <div className="h-5 w-5 rounded-full border border-line/60 bg-base-900 flex items-center justify-center">
          <div className="h-1.5 w-1.5 rounded-full bg-ink-faint/30" />
        </div>
      );
  }
}

export function InvestigationPipeline({
  stages,
  activeStageId,
  onStageClick,
}: InvestigationPipelineProps) {
  const completedCount = stages.filter((s) => s.status === "complete").length;

  return (
    <div className="flex h-full flex-col bg-base-950/80 border-r border-line/60 backdrop-blur-xl select-none">
      {/* Pipeline Title Header */}
      <div className="border-b border-line/60 px-3.5 py-3 bg-base-950/90 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded bg-cyan-400/10 border border-cyan-400/30">
            <Activity className="h-3.5 w-3.5 text-cyan-400" />
          </div>
          <div>
            <h2 className="font-mono text-[11px] font-bold uppercase tracking-wider text-ink">
              INVESTIGATION PIPELINE
            </h2>
            <p className="font-mono text-[8px] text-ink-faint tracking-tight">
              EVIDENCE PROGRESSION ({completedCount}/{stages.length})
            </p>
          </div>
        </div>
      </div>

      {/* Vertical Pipeline Stage List */}
      <div className="flex-1 overflow-y-auto py-2 px-1.5 space-y-1 scrollbar-thin">
        {stages.map((stage, idx) => {
          const isActive = activeStageId === stage.id;
          const Icon = stage.icon;

          return (
            <div key={stage.id} className="relative group">
              <button
                onClick={() => onStageClick?.(stage.id)}
                disabled={stage.status === "unavailable"}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left transition-all duration-200 border",
                  isActive
                    ? "bg-cyan-500/15 border-cyan-400/50 shadow-[0_0_12px_rgba(34,211,238,0.15)]"
                    : stage.status === "complete"
                    ? "bg-base-900/50 border-emerald-500/20 hover:bg-base-800/60 hover:border-emerald-500/40"
                    : stage.status === "available"
                    ? "bg-base-900/40 border-line/40 hover:bg-base-800/50 hover:border-cyan-400/30"
                    : stage.status === "active"
                    ? "bg-cyan-500/10 border-cyan-400/40"
                    : stage.status === "unavailable"
                    ? "bg-base-950/40 border-line/20 opacity-45 cursor-not-allowed"
                    : "bg-base-900/20 border-line/30 hover:bg-base-800/30"
                )}
              >
                {/* Stage Number */}
                <span className={cn(
                  "font-mono text-[10px] font-extrabold tracking-tight shrink-0",
                  stage.status === "complete" ? "text-emerald-400" :
                  stage.status === "active" || isActive ? "text-cyan-400" :
                  stage.status === "unavailable" ? "text-ink-faint/30" :
                  "text-ink-faint/70"
                )}>
                  {stage.number}
                </span>

                {/* Status dot indicator */}
                <StatusIndicator status={stage.status} />

                {/* Label and State */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className={cn(
                      "font-mono text-[10px] font-bold uppercase tracking-wider truncate",
                      isActive ? "text-cyan-200" :
                      stage.status === "complete" ? "text-ink-dim" :
                      stage.status === "active" ? "text-cyan-300" :
                      stage.status === "unavailable" ? "text-ink-faint/40" :
                      "text-ink-faint"
                    )}>
                      {stage.label}
                    </span>

                    <Icon className={cn(
                      "h-3 w-3 shrink-0 ml-1 opacity-70",
                      stage.status === "complete" ? "text-emerald-400" :
                      stage.status === "active" ? "text-cyan-400" :
                      stage.status === "unavailable" ? "text-ink-faint/30" :
                      "text-ink-faint"
                    )} />
                  </div>

                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className={cn(
                      "font-mono text-[8px] font-semibold tracking-widest uppercase truncate",
                      stage.status === "complete" ? "text-emerald-400/90" :
                      stage.status === "active" ? "text-cyan-400" :
                      stage.status === "available" ? "text-cyan-300/80" :
                      stage.status === "unavailable" ? "text-ink-faint/40" :
                      "text-ink-faint/60"
                    )}>
                      ● {stage.statusText}
                    </span>
                  </div>
                </div>
              </button>

              {/* Vertical connector line */}
              {idx < stages.length - 1 && (
                <div className="ml-[34px] my-0.5 h-2 w-0.5 bg-line/40 rounded-full" />
              )}
            </div>
          );
        })}
      </div>

      {/* Footer status summary */}
      <div className="border-t border-line/60 px-3 py-2 bg-base-950/90">
        <div className="flex items-center justify-between font-mono text-[7.5px] tracking-wider text-ink-faint">
          <span className="text-emerald-400/80 font-bold">{completedCount} READY</span>
          <span className="text-cyan-400/80 font-bold">{stages.filter((s) => s.status === "active" || s.status === "available").length} ACTIVE</span>
          <span>{stages.filter((s) => s.status === "unavailable").length} N/A</span>
        </div>
      </div>
    </div>
  );
}

/**
 * Compute pipeline stage states from available data.
 */
export function computePipelineStages(opts: {
  hasIncident: boolean;
  hasDrift: boolean;
  hasAttribution: boolean;
  hasEnvGrid: boolean;
  hasCriticality: boolean;
  hasReport: boolean;
  isDriftLoading: boolean;
  isAttributionLoading: boolean;
  isInvestigationLoading: boolean;
}): PipelineStage[] {
  const {
    hasIncident,
    hasDrift,
    hasAttribution,
    hasEnvGrid,
    hasCriticality,
    hasReport,
    isDriftLoading,
    isAttributionLoading,
    isInvestigationLoading,
  } = opts;

  return [
    {
      id: "detection",
      number: "01",
      label: "DETECTION",
      icon: Target,
      status: hasIncident ? "complete" : "pending",
      statusText: hasIncident ? "ANALYZED" : "PENDING",
      detail: "Sentinel-1 SAR segmentation",
    },
    {
      id: "environment",
      number: "02",
      label: "ENVIRONMENT",
      icon: Wind,
      status: hasEnvGrid ? "complete" : isInvestigationLoading ? "active" : "available",
      statusText: hasEnvGrid ? "AVAILABLE" : isInvestigationLoading ? "FETCHING" : "AVAILABLE",
      detail: "Wind & current ocean grid",
    },
    {
      id: "drift",
      number: "03",
      label: "DRIFT",
      icon: Route,
      status: hasDrift ? "complete" : isDriftLoading ? "active" : "available",
      statusText: hasDrift ? "RECONSTRUCTED" : isDriftLoading ? "COMPUTING" : "AVAILABLE",
      detail: "Backward hindcast trajectory",
    },
    {
      id: "ais",
      number: "04",
      label: "AIS",
      icon: Ship,
      status: hasAttribution ? "complete" : isAttributionLoading ? "active" : "available",
      statusText: hasAttribution ? "CORRELATED" : isAttributionLoading ? "SCANNING" : "AVAILABLE",
      detail: "Candidate vessel tracks",
    },
    {
      id: "attribution",
      number: "05",
      label: "ATTRIBUTION",
      icon: Shield,
      status: hasAttribution ? "complete" : isAttributionLoading ? "active" : "pending",
      statusText: hasAttribution ? "RANKED" : "UNDER REVIEW",
      detail: "Potential source association",
    },
    {
      id: "assessment",
      number: "06",
      label: "ASSESSMENT",
      icon: ClipboardCheck,
      status: hasCriticality ? "complete" : "pending",
      statusText: hasCriticality ? "SCORED" : "PENDING",
      detail: "Operational Priority Index",
    },
    {
      id: "report",
      number: "07",
      label: "REPORT",
      icon: FileText,
      status: hasReport ? "complete" : "available",
      statusText: hasReport ? "GENERATED" : "AVAILABLE",
      detail: "AI Intelligence summary",
    },
  ];
}

