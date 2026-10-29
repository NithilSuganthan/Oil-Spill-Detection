"use client";

import * as React from "react";

/**
 * Maximum number of position history points per vessel.
 * Keeps memory bounded while providing enough history for visible tracks.
 */
const MAX_HISTORY_PER_VESSEL = 50;

/**
 * Maximum time gap (seconds) between consecutive observations before
 * starting a new track segment. Prevents drawing misleading lines across
 * large gaps (e.g. vessel went out of range for hours).
 */
const MAX_TIME_GAP_SECONDS = 3600; // 1 hour

/**
 * Maximum distance gap (degrees, rough) between consecutive observations
 * before starting a new track segment. At equator, 1° ≈ 111 km.
 * A vessel traveling at 15 kn covers ~0.13°/hour in latitude.
 * A gap of 2° (~222 km) is unreasonable for a single update interval.
 */
const MAX_DISTANCE_GAP_DEG = 2.0;

export interface TrackPoint {
  lon: number;
  lat: number;
  timestamp: number; // Unix epoch seconds
}

export interface VesselTrack {
  mmsi: string;
  points: TrackPoint[];
}

function haversineDeg(a: TrackPoint, b: TrackPoint): number {
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLon = ((b.lon - a.lon) * Math.PI) / 180;
  const lat1 = (a.lat * Math.PI) / 180;
  const lat2 = (b.lat * Math.PI) / 180;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * Math.asin(Math.sqrt(h)) * (180 / Math.PI); // returns degrees
}

/**
 * Hook that accumulates real AIS vessel positions over time and builds
 * track LineStrings from actual observations only.
 *
 * No positions are fabricated. No heading-based extrapolation.
 * Tracks are built only from received PositionReports for the same MMSI.
 */
export function useAisTrackHistory(
  vesselGeoJSON: GeoJSON.FeatureCollection | null,
): VesselTrack[] {
  const historyRef = React.useRef<Map<string, TrackPoint[]>>(new Map());

  // Update history when new vessel data arrives
  React.useEffect(() => {
    if (!vesselGeoJSON?.features) return;

    for (const feat of vesselGeoJSON.features) {
      const props = feat.properties as Record<string, unknown> | undefined;
      const coords = (feat.geometry as GeoJSON.Point)?.coordinates;
      if (!props || !coords) continue;

      const mmsi = String(props.mmsi ?? "");
      if (!mmsi) continue;

      const lon = coords[0];
      const lat = coords[1];
      const lastUpdate = props.last_update as string | undefined;
      const timestamp = lastUpdate
        ? new Date(lastUpdate).getTime() / 1000
        : Date.now() / 1000;

      let history = historyRef.current.get(mmsi);
      if (!history) {
        history = [];
        historyRef.current.set(mmsi, history);
      }

      // Don't add duplicate timestamp
      if (history.length > 0) {
        const last = history[history.length - 1];
        if (Math.abs(last.timestamp - timestamp) < 1) continue;
      }

      history.push({ lon, lat, timestamp });

      // Keep bounded
      if (history.length > MAX_HISTORY_PER_VESSEL) {
        history.splice(0, history.length - MAX_HISTORY_PER_VESSEL);
      }
    }
  }, [vesselGeoJSON]);

  // Build tracks from accumulated history
  const tracks = React.useMemo(() => {
    const result: VesselTrack[] = [];
    for (const [mmsi, points] of Array.from(historyRef.current.entries())) {
      if (points.length < 2) continue; // Need at least 2 points for a line

      // Sort chronologically
      const sorted = [...points].sort((a, b) => a.timestamp - b.timestamp);

      // Split into segments at gaps
      const segments: TrackPoint[][] = [[]];
      for (let i = 0; i < sorted.length; i++) {
        const pt = sorted[i];
        const seg = segments[segments.length - 1];

        if (seg.length > 0) {
          const prev = seg[seg.length - 1];
          const timeGap = pt.timestamp - prev.timestamp;
          const distGap = haversineDeg(prev, pt);

          if (
            timeGap > MAX_TIME_GAP_SECONDS ||
            distGap > MAX_DISTANCE_GAP_DEG
          ) {
            // Start new segment
            segments.push([pt]);
            continue;
          }
        }
        seg.push(pt);
      }

      // Use the longest segment as the track
      const longest = segments.reduce((a, b) =>
        a.length >= b.length ? a : b,
        segments[0],
      );

      if (longest.length >= 2) {
        result.push({ mmsi, points: longest });
      }
    }
    return result;
  }, [vesselGeoJSON]); // Rebuild when vessel data changes

  return tracks;
}
