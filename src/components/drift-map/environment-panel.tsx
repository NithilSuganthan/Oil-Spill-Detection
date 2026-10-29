"use client";

import * as React from "react";
import { Wind, Waves, AlertTriangle, Clock, Database } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DriftResult, EnvironmentalGrid } from "@/lib/types";

function directionArrow(deg: number | null): string {
  if (deg === null) return "—";
  const dirs = ["→", "↗", "↑", "↖", "←", "↙", "↓", "↘"];
  const idx = Math.round(deg / 45) % 8;
  return dirs[idx];
}

function formatDataAge(minutes: number | null): string {
  if (minutes === null) return "—";
  if (minutes < 1) return "<1 min";
  if (minutes < 60) return `~${Math.round(minutes)} min`;
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  return `~${hours}h ${mins}m`;
}

export function EnvironmentPanel({
  drift,
  grid,
}: {
  drift: DriftResult | null | undefined;
  grid: EnvironmentalGrid | null | undefined;
}) {
  const metadata = grid?.metadata;
  const windPoint = grid?.windPoint;
  const currentPoint = grid?.currentPoint;

  // Fallback to drift provenance if no grid data
  const prov = (drift?.provenance ?? {}) as Record<string, unknown>;
  const isRealFromProv = prov.environmentalProvider === "real" || prov.environmental_provider === "real";
  const isReal = metadata?.status === "REAL" || isRealFromProv;

  const status = metadata?.status ?? (isReal ? "REAL" : "DEMO");
  const provider = metadata?.provider ?? (isReal ? "CMEMS+ERA5" : "Simulated");

  const hasData = windPoint !== null || currentPoint !== null || status !== "DATA_UNAVAILABLE";

  const statusColor = {
    REAL: "border-signal-green/40 text-signal-green",
    DEMO: "border-signal-amber/40 text-signal-amber",
    DATA_UNAVAILABLE: "border-red-400/40 text-red-400",
    CREDENTIALS_REQUIRED: "border-red-400/40 text-red-400",
  }[status] ?? "border-signal-amber/40 text-signal-amber";

  return (
    <div className="panel w-full p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Wind className="h-3 w-3 text-signal-cyan" />
          <span className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-ink-dim">
            Environment
          </span>
        </div>
        <span
          className={cn(
            "rounded border px-1.5 py-px font-mono text-[8px] font-bold uppercase tracking-wider",
            statusColor,
          )}
        >
          {status}
        </span>
      </div>

      {hasData ? (
        <div className="space-y-2">
          {/* Wind */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Wind className="h-2.5 w-2.5 text-ink-faint" />
              <span className="text-[10px] text-ink-faint">WIND</span>
            </div>
            {windPoint ? (
              <span className="font-mono text-[11px] text-ink">
                {windPoint.speedKts.toFixed(1)} kt {directionArrow(windPoint.directionDeg)} {Math.round(windPoint.directionDeg)}°
              </span>
            ) : (
              <span className="font-mono text-[10px] text-ink-faint">N/A</span>
            )}
          </div>

          {/* Current */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Waves className="h-2.5 w-2.5 text-ink-faint" />
              <span className="text-[10px] text-ink-faint">CURRENT</span>
            </div>
            {currentPoint ? (
              <span className="font-mono text-[11px] text-ink">
                {currentPoint.speedMs.toFixed(2)} m/s {directionArrow(currentPoint.directionDeg)} {Math.round(currentPoint.directionDeg)}°
              </span>
            ) : (
              <span className="font-mono text-[10px] text-ink-faint">N/A</span>
            )}
          </div>

          {/* Metadata */}
          <div className="border-t border-line pt-1.5 space-y-1">
            <div className="flex items-center justify-between text-[9px]">
              <div className="flex items-center gap-1 text-ink-faint">
                <Database className="h-2 w-2" />
                <span>SOURCE:</span>
              </div>
              <span className="font-mono text-ink-dim">{provider}</span>
            </div>
            {metadata?.dataTime && (
              <div className="flex items-center justify-between text-[9px]">
                <div className="flex items-center gap-1 text-ink-faint">
                  <Clock className="h-2 w-2" />
                  <span>DATA TIME:</span>
                </div>
                <span className="font-mono text-ink-dim">
                  {new Date(metadata.dataTime).toLocaleString("en-IN", {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                    hour12: false,
                    timeZone: "UTC",
                  })} UTC
                </span>
              </div>
            )}
            {metadata?.dataAgeMinutes !== null && metadata?.dataAgeMinutes !== undefined && (
              <div className="flex items-center justify-between text-[9px]">
                <span className="text-ink-faint">AGE:</span>
                <span className="font-mono text-ink-dim">{formatDataAge(metadata.dataAgeMinutes)}</span>
              </div>
            )}
            {metadata?.spatialResolutionDeg && (
              <div className="flex items-center justify-between text-[9px]">
                <span className="text-ink-faint">GRID:</span>
                <span className="font-mono text-ink-dim">{metadata.gridSize.join("×")} ({metadata.spatialResolutionDeg}°)</span>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-1.5 text-[10px] text-ink-faint">
          <AlertTriangle className="h-3 w-3" />
          Environmental data unavailable
        </div>
      )}
    </div>
  );
}
