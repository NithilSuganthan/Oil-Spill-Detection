"use client";

import * as React from "react";
import { Clock, CheckCircle2, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatISTTime } from "@/lib/utils";
import type { DriftResult, Incident } from "@/lib/types";
import type { StageStatus } from "@/app/live-analysis/page";

interface TimelineEvent {
  time: string;
  label: string;
  description: string;
  status: StageStatus;
}

export function SlickTimeline({
  stages,
  pipelineStartTime,
  drift,
  incident,
  simulationMode,
}: {
  stages: { id: string; status: StageStatus; label: string; timestamp?: string }[];
  pipelineStartTime: number | null;
  drift: DriftResult | null | undefined;
  incident: Incident | null;
  simulationMode: boolean;
}) {
  const events: TimelineEvent[] = React.useMemo(() => {
    const baseTime = pipelineStartTime ?? Date.now();
    return stages.map((s, idx) => {
      const time = s.timestamp
        ? formatISTTime(s.timestamp)
        : formatISTTime(new Date(baseTime + idx * 180000).toISOString());

      let description = "";
      if (s.status === "complete") description = "Complete";
      else if (s.status === "running") description = "In progress…";
      else if (s.status === "failed") description = "Failed";
      else description = "Awaiting";

      return { time, label: s.label, description, status: s.status };
    });
  }, [stages, pipelineStartTime]);

  return (
    <div className="panel p-4">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-signal-cyan" />
          <h2 className="font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-ink-dim">
            Investigation Timeline
          </h2>
        </div>
        {simulationMode && (
          <span className="rounded border border-signal-amber/40 bg-signal-amber/10 px-1.5 py-0.5 font-mono text-[8px] text-signal-amber">
            SIM
          </span>
        )}
      </div>

      <ol className="relative space-y-3 border-l border-line pl-4">
        {events.map((event, idx) => {
          const isActive = event.status === "running";
          const isComplete = event.status === "complete";

          return (
            <li
              key={`${event.label}-${idx}`}
              className="relative animate-fade-up"
              style={{ animationDelay: `${idx * 50}ms` }}
            >
              <span
                className={cn(
                  "absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full border transition-colors",
                  isActive
                    ? "border-signal-cyan bg-signal-cyan/40"
                    : isComplete
                      ? "border-signal-green bg-signal-green/40"
                      : event.status === "failed"
                        ? "border-signal-red bg-signal-red/40"
                        : "border-line-bright bg-base-950"
                )}
              />
              {isActive && (
                <span className="absolute -left-[21px] top-1 h-2.5 w-2.5 animate-ring-pulse rounded-full border border-signal-cyan/40" />
              )}
              <div className="flex items-baseline gap-3">
                <span className="font-mono text-[10px] tabular-nums text-ink-faint">
                  {event.time}
                </span>
                <div>
                  <p className="text-xs font-medium text-ink">{event.label}</p>
                  <div className="flex items-center gap-1">
                    {isComplete ? (
                      <CheckCircle2 className="h-2.5 w-2.5 text-signal-green" />
                    ) : isActive ? (
                      <Loader2 className="h-2.5 w-2.5 animate-spin text-signal-cyan" />
                    ) : event.status === "failed" ? (
                      <span className="h-2.5 w-2.5 text-signal-red">✗</span>
                    ) : null}
                    <p
                      className={cn(
                        "text-[10px]",
                        isActive
                          ? "text-signal-cyan"
                          : isComplete
                            ? "text-signal-green"
                            : event.status === "failed"
                              ? "text-signal-red"
                              : "text-ink-faint"
                      )}
                    >
                      {event.description}
                    </p>
                  </div>
                </div>
              </div>
            </li>
          );
        })}
      </ol>

      {/* Estimated spill age */}
      {drift && drift.sourceEarliest && drift.sourceLatest && (
        <div className="mt-4 border-t border-line pt-4">
          <div className="rounded border border-signal-amber/30 bg-signal-amber/5 px-3 py-2">
            <p className="font-mono text-[9px] uppercase tracking-wider text-ink-faint">
              Estimated Release Age
            </p>
            <p className="mt-1 font-mono text-lg font-bold text-signal-amber">
              ~{drift.uncertaintyHours.toFixed(0)}–{Math.round(drift.uncertaintyHours * 2)} HOURS
            </p>
            <p className="font-mono text-[9px] text-ink-faint">MODERATE CONFIDENCE</p>
          </div>
          <p className="mt-2 text-[8px] italic text-ink-faint/60">
            Derived from backward drift hindcast. Not a direct measurement of oil weathering.
          </p>
        </div>
      )}

      {/* Data provenance */}
      <div className="mt-4 border-t border-line pt-3">
        <p className="mb-1.5 font-mono text-[9px] uppercase tracking-widest text-ink-faint">
          Data Provenance
        </p>
        <div className="space-y-1">
          {incident && (
            <div className="flex justify-between text-[9px]">
              <span className="text-ink-faint">Detection</span>
              <span className="font-mono text-ink">{incident.model} {incident.modelVersion}</span>
            </div>
          )}
          {drift && (
            <div className="flex justify-between text-[9px]">
              <span className="text-ink-faint">Environmental</span>
              <span className={cn("font-mono", drift.qualityFlags.includes("DEMO_ENVIRONMENTAL_FORCING") ? "text-signal-amber" : "text-signal-green")}>
                {drift.provenance?.environmentalProvider === "real" ? "REAL (CMEMS+ERA5)" : "DEMO (synthetic)"}
              </span>
            </div>
          )}
          <div className="flex justify-between text-[9px]">
            <span className="text-ink-faint">AIS</span>
            <span className="font-mono text-ink-faint">See engine card</span>
          </div>
        </div>
      </div>
    </div>
  );
}
