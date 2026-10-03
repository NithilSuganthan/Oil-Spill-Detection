"use client";

import * as React from "react";
import { Target, X, AlertTriangle, Clock, MapPin, Compass, ShieldAlert } from "lucide-react";
import type { DriftResult } from "@/lib/types";

interface SourceEstimateCardProps {
  drift: DriftResult | null;
  onClose: () => void;
  onLocate?: () => void;
}

export function SourceEstimateCard({ drift, onClose, onLocate }: SourceEstimateCardProps) {
  if (!drift || drift.sourceLatitude == null || drift.sourceLongitude == null) return null;

  const lat = drift.sourceLatitude.toFixed(4);
  const lon = drift.sourceLongitude.toFixed(4);
  const uncertaintyKm = drift.uncertaintyKm ?? 12.5;
  const uncertaintyHours = drift.uncertaintyHours ?? 4.0;
  const confidencePct = Math.round((drift.confidence ?? 0.62) * 100);
  const method = drift.method ? drift.method.replace(/_/g, " ") : "first order backward hindcast";
  const prov = (drift.provenance ?? {}) as Record<string, unknown>;
  const isReal = prov.environmentalProvider === "real" || prov.environmental_provider === "real";

  return (
    <div className="panel border-emerald-500/40 bg-base-900/95 p-4 shadow-2xl backdrop-blur-xl w-80 max-w-sm">
      <div className="flex items-center justify-between border-b border-line pb-2.5 mb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-emerald-500/15 border border-emerald-500/30">
            <Target className="h-4 w-4 text-emerald-400" />
          </div>
          <div>
            <h3 className="font-mono text-[12px] font-bold text-ink tracking-wide uppercase">
              ESTIMATED SOURCE
            </h3>
            <p className="font-mono text-[9px] text-emerald-400 font-medium">
              BACKWARD DRIFT HINDCAST
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded p-1 text-ink-faint hover:bg-base-800 hover:text-ink transition-colors"
          aria-label="Close details"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="space-y-2.5 font-mono text-[10px]">
        {/* Coordinates */}
        <div className="rounded-md bg-base-950/80 p-2.5 border border-line/80 flex items-center justify-between">
          <div>
            <span className="text-[8px] text-ink-faint uppercase tracking-wider block">
              LAT / LON COORDINATES
            </span>
            <span className="text-[13px] font-bold text-emerald-400">
              {lat}° N, {lon}° E
            </span>
          </div>
          {onLocate && (
            <button
              onClick={onLocate}
              className="rounded bg-emerald-500/15 border border-emerald-500/30 px-2 py-1 text-[9px] text-emerald-400 hover:bg-emerald-500/25 transition-colors"
            >
              LOCATE
            </button>
          )}
        </div>

        {/* Release window */}
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-md bg-base-950/60 p-2 border border-line/50">
            <span className="text-[8px] text-ink-faint uppercase block">RELEASE WINDOW</span>
            <span className="text-[10px] text-ink font-semibold">
              {drift.sourceEarliest ? `${drift.sourceEarliest.slice(11, 16)} IST` : "06:30–10:30 IST"}
            </span>
          </div>
          <div className="rounded-md bg-base-950/60 p-2 border border-line/50">
            <span className="text-[8px] text-ink-faint uppercase block">ESTIMATED AGE</span>
            <span className="text-[10px] text-cyan-400 font-semibold">
              ~8h before detection
            </span>
          </div>
        </div>

        {/* Uncertainty */}
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-md bg-base-950/60 p-2 border border-line/50">
            <span className="text-[8px] text-ink-faint uppercase block">SPATIAL UNCERTAINTY</span>
            <span className="text-[10px] text-amber-400 font-semibold">
              ±{uncertaintyKm.toFixed(1)} km
            </span>
          </div>
          <div className="rounded-md bg-base-950/60 p-2 border border-line/50">
            <span className="text-[8px] text-ink-faint uppercase block">TEMPORAL UNCERTAINTY</span>
            <span className="text-[10px] text-amber-400 font-semibold">
              ±{uncertaintyHours.toFixed(1)} h
            </span>
          </div>
        </div>

        {/* Model confidence & method */}
        <div className="space-y-1.5 rounded-md bg-base-950/60 p-2 border border-line/50">
          <div className="flex justify-between items-center">
            <span className="text-[8px] text-ink-faint uppercase">CONFIDENCE</span>
            <span className="text-[10px] font-bold text-amber-400 uppercase">
              MODERATE ({confidencePct}%)
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-[8px] text-ink-faint uppercase">METHOD</span>
            <span className="text-[9px] text-ink-dim capitalize">{method}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-[8px] text-ink-faint uppercase">ENVIRONMENTAL FORCING</span>
            <span className={isReal ? "text-emerald-400 text-[9px]" : "text-amber-400 text-[9px]"}>
              {isReal ? "CMEMS + ERA5 (REAL)" : "DEMO FORCING"}
            </span>
          </div>
        </div>

        {/* Disclaimer */}
        <div className="flex items-start gap-2 rounded-md bg-amber-500/10 border border-amber-500/30 p-2 text-[9px] text-amber-300">
          <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-amber-400 mt-0.5" />
          <p className="leading-tight">
            Source location is an estimate based on backward hindcast modeling, not a confirmed origin point. Human verification required.
          </p>
        </div>
      </div>
    </div>
  );
}
