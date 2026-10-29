"use client";

import * as React from "react";
import { Ship, Satellite, Waves, Wind, Info } from "lucide-react";
import { cn } from "@/lib/utils";

export interface DataSourceItem {
  id: string;
  label: string;
  icon: React.ElementType;
  status: "LIVE" | "NRT" | "FORECAST" | "UNAVAILABLE" | "DISCONNECTED";
  detail?: string;
  updated?: string;
  color: string;
}

interface DataSourcesPanelProps {
  sources: DataSourceItem[];
  className?: string;
}

function StatusDot({ status }: { status: DataSourceItem["status"] }) {
  const colorMap: Record<string, string> = {
    LIVE: "text-signal-green",
    NRT: "text-signal-cyan",
    FORECAST: "text-signal-amber",
    UNAVAILABLE: "text-ink-faint",
    DISCONNECTED: "text-signal-red",
  };
  return <span className={cn("status-dot", colorMap[status] || "text-ink-faint")} />;
}

function StatusLabel({ status }: { status: DataSourceItem["status"] }) {
  const colorMap: Record<string, string> = {
    LIVE: "text-signal-green",
    NRT: "text-signal-cyan",
    FORECAST: "text-signal-amber",
    UNAVAILABLE: "text-ink-faint",
    DISCONNECTED: "text-signal-red",
  };
  return (
    <span className={cn("font-mono text-[9px] font-bold", colorMap[status] || "text-ink-faint")}>
      {status}
    </span>
  );
}

export function DataSourcesPanel({ sources, className }: DataSourcesPanelProps) {
  return (
    <div className={cn("glass-panel p-3 w-56", className)}>
      <h3 className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-ink-dim mb-2.5">
        Data Sources
      </h3>
      <div className="space-y-2.5">
        {sources.map((src) => {
          const Icon = src.icon;
          return (
            <div key={src.id} className="flex items-start gap-2">
              <div
                className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded"
                style={{ backgroundColor: `${src.color}15` }}
              >
                <Icon className="h-3 w-3" style={{ color: src.color }} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-[10px] font-medium text-ink truncate">
                    {src.label}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <StatusDot status={src.status} />
                  <StatusLabel status={src.status} />
                  {src.detail && (
                    <span className="font-mono text-[9px] text-ink-faint">
                      {src.detail}
                    </span>
                  )}
                </div>
                {src.updated && (
                  <div className="font-mono text-[8px] text-ink-faint/70 mt-0.5">
                    Updated: {src.updated}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
