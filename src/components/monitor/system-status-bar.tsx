"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { getSystemStatus } from "@/lib/api/client";
import type { Incident } from "@/lib/types";
import { formatISTTimeShort } from "@/lib/utils";
import { cn } from "@/lib/utils";

const STATUS_COLORS: Record<string, string> = {
  LIVE: "text-signal-green",
  RUNNING: "text-signal-green",
  OPERATIONAL: "text-signal-green",
  CONNECTED: "text-signal-green",
};

interface SceneInfo {
  platform: string;
  id: string;
  acquiredAt: string;
  processedAt: string;
  status: string;
}

export function SystemStatusBar({ selectedIncident }: { selectedIncident: Incident | null }) {
  const { data } = useQuery({ queryKey: ["system-status"], queryFn: getSystemStatus });

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

  return (
    <footer className="flex h-auto shrink-0 flex-wrap items-center gap-x-5 gap-y-1 border-t border-line bg-base-900/90 px-4 py-1.5 md:h-9 md:flex-nowrap md:py-0">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-ink-faint">
          System
        </span>
        {(data?.services ?? []).map((svc) => (
          <span key={svc.name} className="flex items-center gap-1.5">
            <span className={cn("h-1.5 w-1.5 rounded-full", STATUS_COLORS[svc.status] ?? "bg-ink-faint")} style={{ backgroundColor: "currentColor" }} />
            <span className="text-[11px] text-ink-dim">{svc.name}</span>
            <span className={cn("font-mono text-[10px] font-semibold tracking-wider", STATUS_COLORS[svc.status])}>
              {svc.status}
            </span>
          </span>
        ))}
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
          <span className="rounded border border-line px-1 py-px uppercase tracking-wider text-signal-cyan">
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
