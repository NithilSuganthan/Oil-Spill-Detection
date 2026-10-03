"use client";

import * as React from "react";

export interface SSEEvent {
  id: string;
  type: string;
  payload: Record<string, unknown>;
  timestamp: number;
}

/** All event types the backend actually emits. */
export const BACKEND_EVENT_TYPES = [
  "scene.discovered",
  "scene.download.started",
  "scene.download.completed",
  "scene.extraction.started",
  "scene.extraction.completed",
  "scene.calibration.started",
  "scene.calibration.completed",
  "scene.georeferencing.started",
  "scene.georeferencing.completed",
  "scene.preprocessing.started",
  "scene.preprocessing.completed",
  "scene.inference.started",
  "scene.inference.completed",
  "pipeline.failed",
  "detection.created",
  "attribution.started",
  "attribution.completed",
  "attribution.failed",
  "drift.started",
  "drift.completed",
  "drift.failed",
  "investigation.started",
  "investigation.completed",
  "investigation.failed",
] as const;

export type BackendEventType = (typeof BACKEND_EVENT_TYPES)[number];

interface UseSSEOptions {
  enabled?: boolean;
  onEvent?: (event: SSEEvent) => void;
}

export function useSSE({ enabled = true, onEvent }: UseSSEOptions = {}) {
  const [events, setEvents] = React.useState<SSEEvent[]>([]);
  const [connected, setConnected] = React.useState(false);
  const [lastEventId, setLastEventId] = React.useState(0);
  const onEventRef = React.useRef(onEvent);
  onEventRef.current = onEvent;

  React.useEffect(() => {
    if (!enabled) {
      setConnected(false);
      return;
    }

    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
    const mode = process.env.NEXT_PUBLIC_API_MODE || "mock";

    if (mode === "mock") {
      setConnected(false);
      return;
    }

    const url = `${baseUrl}/events/stream?cursor=${lastEventId}`;
    let eventSource: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      try {
        eventSource = new EventSource(url);

        eventSource.onopen = () => setConnected(true);

        eventSource.onerror = () => {
          setConnected(false);
          eventSource?.close();
          reconnectTimer = setTimeout(connect, 5000);
        };

        // Listen for ALL backend event types
        const eventTypes: readonly string[] = BACKEND_EVENT_TYPES;

        eventTypes.forEach((type) => {
          eventSource!.addEventListener(type, ((e: MessageEvent) => {
            try {
              const data = JSON.parse(e.data);
              const event: SSEEvent = {
                id: e.lastEventId || String(Date.now()),
                type: data.type || type,
                payload: data.payload || {},
                timestamp: Date.now(),
              };
              setEvents((prev) => [...prev.slice(-199), event]);
              setLastEventId(parseInt(e.lastEventId || "0", 10) || Date.now());
              onEventRef.current?.(event);
            } catch {
              // ignore malformed events
            }
          }) as EventListener);
        });

        // Also listen for unknown events as a catch-all
        eventSource.onmessage = ((e: MessageEvent) => {
          try {
            const data = JSON.parse(e.data);
            if (data.type && !eventTypes.includes(data.type)) {
              const event: SSEEvent = {
                id: e.lastEventId || String(Date.now()),
                type: data.type,
                payload: data.payload || {},
                timestamp: Date.now(),
              };
              setEvents((prev) => [...prev.slice(-199), event]);
              onEventRef.current?.(event);
            }
          } catch {
            // ignore
          }
        }) as EventListener;
      } catch {
        reconnectTimer = setTimeout(connect, 5000);
      }
    }

    connect();

    return () => {
      eventSource?.close();
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
  }, [enabled, lastEventId]);

  return { events, connected, lastEvent: events[events.length - 1] ?? null };
}

/**
 * Maps SSE event types to pipeline stage IDs.
 * Returns null if the event doesn't map to a stage.
 */
export function mapEventToStage(
  eventType: string
): { stageId: string; status: "running" | "complete" | "failed" } | null {
  // Scene pipeline stages
  if (eventType === "scene.discovered" || eventType === "scene.download.started")
    return { stageId: "satellite", status: "running" };
  if (eventType === "scene.download.completed" || eventType === "scene.extraction.started")
    return { stageId: "satellite", status: "complete" };

  if (eventType === "scene.preprocessing.started" || eventType === "scene.calibration.started" || eventType === "scene.georeferencing.started")
    return { stageId: "preprocessing", status: "running" };
  if (eventType === "scene.preprocessing.completed" || eventType === "scene.calibration.completed" || eventType === "scene.georeferencing.completed")
    return { stageId: "preprocessing", status: "complete" };

  if (eventType === "scene.inference.started")
    return { stageId: "segmentation", status: "running" };
  if (eventType === "scene.inference.completed")
    return { stageId: "segmentation", status: "complete" };

  if (eventType === "detection.created")
    return { stageId: "detection", status: "complete" };

  // Investigation stages
  if (eventType === "investigation.started")
    return { stageId: "investigation", status: "running" };
  if (eventType === "investigation.completed")
    return { stageId: "investigation", status: "complete" };
  if (eventType === "investigation.failed")
    return { stageId: "investigation", status: "failed" };

  if (eventType === "drift.started")
    return { stageId: "drift", status: "running" };
  if (eventType === "drift.completed")
    return { stageId: "drift", status: "complete" };
  if (eventType === "drift.failed")
    return { stageId: "drift", status: "failed" };

  if (eventType === "attribution.started")
    return { stageId: "attribution", status: "running" };
  if (eventType === "attribution.completed")
    return { stageId: "attribution", status: "complete" };
  if (eventType === "attribution.failed")
    return { stageId: "attribution", status: "failed" };

  if (eventType === "pipeline.failed")
    return { stageId: "segmentation", status: "failed" };

  return null;
}
