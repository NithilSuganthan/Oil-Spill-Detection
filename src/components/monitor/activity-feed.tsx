"use client";

import * as React from "react";
import {
  Activity,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Loader2,
  AlertCircle,
  Radio,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useSSE, type SSEEvent } from "@/lib/hooks/use-sse";
import { formatISTTimeShort } from "@/lib/utils";

const EVENT_LABELS: Record<string, string> = {
  "scene.discovered": "SAR scene discovered",
  "scene.download.started": "Downloading scene…",
  "scene.download.completed": "Scene download complete",
  "scene.extraction.started": "Extracting bands…",
  "scene.extraction.completed": "Band extraction complete",
  "scene.calibration.started": "Calibrating…",
  "scene.calibration.completed": "Calibration complete",
  "scene.georeferencing.started": "Georeferencing…",
  "scene.georeferencing.completed": "Georeferencing complete",
  "scene.preprocessing.started": "Preprocessing…",
  "scene.preprocessing.completed": "Preprocessing complete",
  "scene.inference.started": "Running AI inference…",
  "scene.inference.completed": "AI inference complete",
  "pipeline.failed": "Pipeline failed",
  "detection.created": "Potential slick detected",
  "attribution.started": "AIS attribution started",
  "attribution.completed": "AIS attribution complete",
  "attribution.failed": "AIS attribution failed",
  "drift.started": "Drift analysis started",
  "drift.completed": "Drift analysis complete",
  "drift.failed": "Drift analysis failed",
  "investigation.started": "Investigation started",
  "investigation.completed": "Investigation complete",
  "investigation.failed": "Investigation failed",
};

function getEventIcon(type: string) {
  if (type.includes(".failed")) return <AlertCircle className="h-3 w-3 text-signal-red" />;
  if (type.includes(".completed")) return <CheckCircle2 className="h-3 w-3 text-signal-green" />;
  if (type.includes(".started")) return <Loader2 className="h-3 w-3 animate-spin text-signal-cyan" />;
  if (type === "detection.created") return <Radio className="h-3 w-3 text-signal-amber" />;
  return <Activity className="h-3 w-3 text-ink-faint" />;
}

function getEventColor(type: string) {
  if (type.includes(".failed")) return "text-signal-red";
  if (type.includes(".completed")) return "text-signal-green";
  if (type.includes(".started")) return "text-signal-cyan";
  if (type === "detection.created") return "text-signal-amber";
  return "text-ink-dim";
}

function FeedItem({ event }: { event: SSEEvent }) {
  const label = EVENT_LABELS[event.type] ?? event.type;
  const time = new Date(event.timestamp);
  const timeStr = formatISTTimeShort(time.toISOString());

  return (
    <div className="feed-item flex items-start gap-2 py-1.5">
      {getEventIcon(event.type)}
      <div className="min-w-0 flex-1">
        <p className={cn("text-[10px] leading-tight", getEventColor(event.type))}>
          {label}
        </p>
        <p className="font-mono text-[9px] tabular-nums text-ink-faint">
          {timeStr} IST
        </p>
      </div>
    </div>
  );
}

export function ActivityFeed({
  sseConnected,
  events,
}: {
  sseConnected: boolean;
  events: SSEEvent[];
}) {
  const [collapsed, setCollapsed] = React.useState(false);
  const [maxItems, setMaxItems] = React.useState(8);

  const displayEvents = React.useMemo(() => {
    return events.slice(-maxItems).reverse();
  }, [events, maxItems]);

  return (
    <div className="panel w-full">
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="flex w-full items-center justify-between px-3 py-2"
      >
        <div className="flex items-center gap-2">
          <Activity className="h-3.5 w-3.5 text-signal-cyan" />
          <span className="panel-title">Live Activity</span>
          {sseConnected && (
            <span className="flex items-center gap-1 rounded border border-signal-green/30 bg-signal-green/10 px-1 py-px font-mono text-[8px] text-signal-green">
              <span className="h-1 w-1 rounded-full bg-signal-green animate-pulse-dot" />
              SSE
            </span>
          )}
          {!sseConnected && (
            <span className="rounded border border-line px-1 py-px font-mono text-[8px] text-ink-faint">
              NO SSE
            </span>
          )}
        </div>
        {collapsed ? (
          <ChevronDown className="h-3.5 w-3.5 text-ink-faint" />
        ) : (
          <ChevronUp className="h-3.5 w-3.5 text-ink-faint" />
        )}
      </button>

      {!collapsed && (
        <div className="border-t border-line px-3 py-1.5">
          {displayEvents.length === 0 ? (
            <p className="py-2 text-center text-[10px] text-ink-faint">
              {sseConnected
                ? "Waiting for backend events…"
                : "SSE not connected. Events will appear when the backend is running."}
            </p>
          ) : (
            <div className="space-y-0.5 divide-y divide-line/30">
              {displayEvents.map((event) => (
                <FeedItem key={event.id + event.timestamp} event={event} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
