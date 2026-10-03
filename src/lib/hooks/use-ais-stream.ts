"use client";

import * as React from "react";
import {
  getAISStatus,
  connectAISStream,
  type AISStreamStatus,
  type AISStreamEvent,
} from "@/lib/api/http-client";

/**
 * Hook for consuming real-time AIS vessel data from the backend.
 *
 * Provides:
 * - connection status + data freshness
 * - vessel GeoJSON updates (efficiently throttled)
 * - auto-reconnect behavior
 *
 * Usage:
 *   const { status, vesselGeoJSON } = useAISStream();
 */
export function useAISStream() {
  const [status, setStatus] = React.useState<AISStreamStatus>({
    connected: false,
    freshness: "UNAVAILABLE",
    total_vessels: 0,
    recent_vessels: 0,
    total_messages: 0,
    last_message_time: null,
    reconnect_count: 0,
  });

  const [vesselGeoJSON, setVesselGeoJSON] = React.useState<GeoJSON.FeatureCollection | null>(null);

  // Initial status fetch
  React.useEffect(() => {
    let active = true;

    const fetchStatus = async () => {
      try {
        const s = await getAISStatus();
        if (active) setStatus(s);
      } catch {
        // Backend may not be running
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 15000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  // SSE connection for real-time updates
  React.useEffect(() => {
    let active = true;

    const handleEvent = (event: AISStreamEvent) => {
      if (!active) return;

      if (event.type === "ais.status") {
        const p = event.payload as Record<string, unknown>;
        setStatus({
          connected: Boolean(p.connected),
          freshness: String(p.freshness ?? "UNAVAILABLE"),
          total_vessels: Number(p.total_vessels ?? 0),
          recent_vessels: Number(p.recent_vessels ?? 0),
          total_messages: Number(p.total_messages ?? 0),
          last_message_time: p.last_message_time as string | null,
          reconnect_count: Number(p.reconnect_count ?? 0),
        });
      } else if (event.type === "ais.vessels.update") {
        const p = event.payload as Record<string, unknown>;
        if (p.geojson) {
          setVesselGeoJSON(p.geojson as GeoJSON.FeatureCollection);
        }
      }
    };

    const handleError = () => {
      if (active) {
        setStatus((prev) => ({ ...prev, connected: false, freshness: "UNAVAILABLE" }));
      }
    };

    const disconnect = connectAISStream(handleEvent, handleError);

    return () => {
      active = false;
      disconnect();
    };
  }, []);

  return React.useMemo(
    () => ({ status, vesselGeoJSON }),
    [status, vesselGeoJSON],
  );
}
