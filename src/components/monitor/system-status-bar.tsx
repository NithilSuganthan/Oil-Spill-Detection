"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { getSystemStatus } from "@/lib/api/client";
import { API_MODE } from "@/lib/api/client";
import type { Incident } from "@/lib/types";
import { formatISTTimeShort } from "@/lib/utils";
import { cn } from "@/lib/utils";

const STATUS_COLORS: Record<string, string> = {
  LIVE: "text-signal-green",
  RUNNING: "text-signal-green",
  OPERATIONAL: "text-signal-green",
  CONNECTED: "text-signal-green",
};

const STATUS_DESCRIPTIONS: Record<string, string> = {
  SATELLITE_FEED: "Sentinel-1 SAR data ingestion pipeline",
  PROCESSING_ENGINE: "Preprocessing + model inference pipeline",
  AI_MODEL: "TinyUNet segmentation model (v1.0-dev)",
  DATABASE: "PostgreSQL incident store",
  SSE: "Server-Sent Events real-time stream",
};

interface SceneInfo {
  platform: string;
  id: string;
  acquiredAt: string;
  processedAt: string;
  status: string;
}

function StatusIndicator({
  status,
  name,
  lastUpdate,
}: {
  status: string;
  name: string;
  lastUpdate?: string;
}) {
  const isActive = status === "LIVE" || status === "RUNNING" || status === "OPERATIONAL" || status === "CONNECTED";
  const color = STATUS_COLORS[status] ?? "text-ink-faint";
  const description = STATUS_DESCRIPTIONS[name] ?? name;

  return (
    <div className="status-tooltip-trigger relative flex items-center gap-1.5">
      <span className="relative flex h-2 w-2">
        {isActive && (
          <span
            className={cn(
              "absolute inline-flex h-full w-full rounded-full opacity-75 animate-pulse-dot",
              color
            )}
            style={{ backgroundColor: "currentColor" }}
          />
        )}
        <span
          className={cn("relative inline-flex h-2 w-2 rounded-full", color)}
          style={{ backgroundColor: "currentColor" }}
        />
      </span>
      <span className="text-[11px] text-ink-dim">{name}</span>
      <span className={cn("font-mono text-[10px] font-semibold tracking-wider", color)}>
        {status}
      </span>

      {/* Tooltip */}
      <div className="status-tooltip">
        <div className="mb-1 font-mono text-[10px] font-semibold text-ink">{name}</div>
        <div className="text-[9px] text-ink-faint">{description}</div>
        {lastUpdate && (
          <div className="mt-1 text-[9px] text-ink-faint">
            Last update: {lastUpdate}
          </div>
        )}
        <div className="mt-1 flex items-center gap-1">
          <span className={cn("h-1.5 w-1.5 rounded-full", isActive ? "bg-signal-green" : "bg-signal-red")} />
          <span className="text-[9px] text-ink-faint">{isActive ? "Operational" : "Unreachable"}</span>
        </div>
      </div>
    </div>
  );
}

export function SystemStatusBar({ selectedIncident }: { selectedIncident: Incident | null }) {
  const { data, isLoading } = useQuery({ queryKey: ["system-status"], queryFn: getSystemStatus });

  const scene: SceneInfo | null = React.useMemo(() => {
    if (selectedIncident) {
      return {
        platform: selectedIncident.satellite,
        id: selectedIncident.sceneId,
        acquiredAt: selectedIncident.detectedAt,
        processedAt: "",
        status:
          selectedIncident.status === "completed"
            ? "COMPLETED"
            : selectedIncident.status === "processing"
              ? "PROCESSING"
              : "REVIEW",
      };
    }
    const s = data?.activeScene;
    if (!s) return null;
    return {
      platform: s.platform,
      id: s.id,
      acquiredAt: s.acquiredAt,
      processedAt: s.processedAt,
      status: s.status,
    };
  }, [selectedIncident, data]);

  const isMock = API_MODE === "mock";

  return (
    <footer className="flex h-auto shrink-0 flex-wrap items-center gap-x-5 gap-y-1 border-t border-line bg-base-900/90 px-4 py-1.5 md:h-9 md:flex-nowrap md:py-0">
      {/* Data mode badge */}
      <div className="flex items-center gap-1.5">
        <span
          className={cn(
            "rounded border px-1.5 py-px font-mono text-[9px] font-semibold uppercase tracking-wider",
            isMock
              ? "border-signal-amber/40 text-signal-amber"
              : "border-signal-green/40 text-signal-green"
          )}
        >
          {isMock ? "DEMO / MOCK" : "LIVE"}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-ink-faint">
          System
        </span>
        {isLoading ? (
          <span className="font-mono text-[10px] text-ink-faint animate-pulse">Loading…</span>
        ) : (
          (data?.services ?? []).map((svc) => (
            <StatusIndicator key={svc.name} status={svc.status} name={svc.name} />
          ))
        )}
      </div>

      {scene ? (
        <div className="ml-auto hidden items-center gap-x-3 font-mono text-[10px] text-ink-faint lg:flex">
          <span className="uppercase tracking-[0.18em]">Scene</span>
          <span className="text-ink-dim">{scene.platform}</span>
          <span className="max-w-[220px] truncate">{scene.id}</span>
          <span>ACQ {formatISTTimeShort(scene.acquiredAt)} IST</span>
          {scene.processedAt && scene.processedAt !== "—" && (
            <span>PROC {formatISTTimeShort(scene.processedAt)} IST</span>
          )}
          <span
            className={cn(
              "rounded border px-1 py-px uppercase tracking-wider",
              scene.status === "COMPLETED" || scene.status === "processed"
                ? "border-signal-green/40 text-signal-green"
                : scene.status === "PROCESSING" || scene.status === "processing"
                  ? "border-signal-cyan/40 text-signal-cyan animate-pulse"
                  : "border-line text-ink-faint"
            )}
          >
            {scene.status}
          </span>
        </div>
      ) : (
        !data && (
          <span className="ml-auto font-mono text-[10px] uppercase tracking-widest text-ink-faint">
            Status: standby…
          </span>
        )
      )}
    </footer>
  );
}
