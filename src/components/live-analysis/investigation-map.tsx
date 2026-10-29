"use client";

import * as React from "react";
import { MapPin } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Incident, DriftResult, AttributionResult } from "@/lib/types";

export function InvestigationMap({
  incident,
  drift,
  attribution,
}: {
  incident: Incident | null;
  drift: DriftResult | null | undefined;
  attribution: AttributionResult | null | undefined;
}) {
  if (!incident) {
    return (
      <div className="panel flex min-h-[400px] items-center justify-center p-4">
        <div className="text-center">
          <MapPin className="mx-auto h-6 w-6 text-line-bright" />
          <p className="mt-2 font-mono text-[11px] uppercase tracking-wider text-ink-faint">
            Select an incident to view investigation map
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-2">
        <h2 className="font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-ink-dim">
          Investigation Map
        </h2>
        <span className="font-mono text-[9px] text-ink-faint">{incident.id}</span>
      </div>

      {/* Map placeholder with data overlay */}
      <div className="relative min-h-[400px] bg-base-950">
        {/* SVG visualization of the investigation */}
        <svg
          className="h-full w-full"
          viewBox="0 0 800 400"
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Grid */}
          {Array.from({ length: 21 }).map((_, i) => (
            <React.Fragment key={i}>
              <line
                x1={i * 40}
                y1="0"
                x2={i * 40}
                y2="400"
                stroke="#1b2a44"
                strokeWidth="0.5"
              />
              <line
                x1="0"
                y1={i * 20}
                x2="800"
                y2={i * 20}
                stroke="#1b2a44"
                strokeWidth="0.5"
              />
            </React.Fragment>
          ))}

          {/* Detection polygon */}
          {incident.geometry?.coordinates?.[0] && (
            <polygon
              points={incident.geometry.coordinates[0]
                .map(
                  ([lon, lat]) =>
                    `${400 + (lon - incident.centroid.lon) * 800},${200 + (incident.centroid.lat - lat) * 800}`
                )
                .join(" ")}
              fill={
                incident.level === "HIGH"
                  ? "rgba(248,113,113,0.2)"
                  : incident.level === "MEDIUM"
                    ? "rgba(251,146,60,0.2)"
                    : "rgba(250,204,21,0.2)"
              }
              stroke={
                incident.level === "HIGH"
                  ? "#f87171"
                  : incident.level === "MEDIUM"
                    ? "#fb923c"
                    : "#facc15"
              }
              strokeWidth="1.5"
            />
          )}

          {/* Centroid */}
          <circle cx="400" cy="200" r="4" fill="#ef4444" />
          <circle cx="400" cy="200" r="8" fill="none" stroke="#ef4444" strokeWidth="0.5" opacity="0.5">
            <animate attributeName="r" values="8;12;8" dur="2s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.5;0.2;0.5" dur="2s" repeatCount="indefinite" />
          </circle>

          {/* Drift source estimate */}
          {drift && (
            <>
              <circle
                cx={400 + (drift.sourceLongitude - incident.centroid.lon) * 800}
                cy={200 + (incident.centroid.lat - drift.sourceLatitude) * 800}
                r="5"
                fill="#f59e0b"
              />
              <circle
                cx={400 + (drift.sourceLongitude - incident.centroid.lon) * 800}
                cy={200 + (incident.centroid.lat - drift.sourceLatitude) * 800}
                r={Math.min(drift.uncertaintyKm * 2, 60)}
                fill="none"
                stroke="#f59e0b"
                strokeWidth="0.5"
                strokeDasharray="3,3"
                opacity="0.4"
              />
              {/* Drift trajectory lines */}
              {drift.sourcePoints?.slice(0, 10).map(([lat, lon], idx) => (
                <line
                  key={idx}
                  x1={400 + (lon - incident.centroid.lon) * 800}
                  y1={200 + (incident.centroid.lat - lat) * 800}
                  x2="400"
                  y2="200"
                  stroke="#22d3ee"
                  strokeWidth="0.5"
                  opacity="0.3"
                />
              ))}
            </>
          )}

          {/* AIS candidates */}
          {attribution?.candidates?.slice(0, 3).map((c, idx) => {
            const offsetLat = (idx + 1) * 0.02;
            const offsetLon = (idx + 1) * 0.03;
            return (
              <React.Fragment key={c.mmsi}>
                <circle
                  cx={400 + offsetLon * 800}
                  cy={200 - offsetLat * 800}
                  r={idx === 0 ? 5 : 3}
                  fill={idx === 0 ? "#f59e0b" : "#38bdf8"}
                />
                <text
                  x={400 + offsetLon * 800 + 8}
                  y={200 - offsetLat * 800 + 3}
                  fill="#93a4bd"
                  fontSize="8"
                  fontFamily="monospace"
                >
                  {c.vesselName || c.mmsi}
                </text>
              </React.Fragment>
            );
          })}

          {/* Labels */}
          <text x="400" y="190" fill="#ef4444" fontSize="8" fontFamily="monospace" textAnchor="middle">
            DETECTION
          </text>
          {drift && (
            <text
              x={400 + (drift.sourceLongitude - incident.centroid.lon) * 800}
              y={200 + (incident.centroid.lat - drift.sourceLatitude) * 800 - 10}
              fill="#f59e0b"
              fontSize="8"
              fontFamily="monospace"
              textAnchor="middle"
            >
              EST. SOURCE
            </text>
          )}
        </svg>

        {/* Legend */}
        <div className="absolute bottom-2 left-2 flex flex-wrap gap-3 rounded border border-line bg-base-950/80 px-2 py-1 font-mono text-[8px]">
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full bg-signal-red" />
            DETECTION
          </span>
          {drift && (
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full bg-signal-amber" />
              EST. SOURCE
            </span>
          )}
          {attribution && (
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full bg-signal-cyan" />
              AIS VESSELS
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
