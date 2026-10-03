"use client";

import * as React from "react";
import { Ship, X, AlertTriangle, Clock, MapPin, Anchor, ShieldAlert } from "lucide-react";
import type { CandidateVessel } from "@/lib/types";

interface AisVesselCardProps {
  vessel: CandidateVessel | null;
  onClose: () => void;
}

export function AisVesselCard({ vessel, onClose }: AisVesselCardProps) {
  if (!vessel) return null;

  const vesselName = vessel.vesselName || `MMSI ${vessel.mmsi}`;
  const scorePct = Math.round(vessel.attributionScore * 100);

  return (
    <div className="panel border-amber-500/40 bg-base-900/95 p-4 shadow-2xl backdrop-blur-xl w-80 max-w-sm">
      <div className="flex items-center justify-between border-b border-line pb-2.5 mb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-amber-500/15 border border-amber-500/30">
            <Ship className="h-4 w-4 text-amber-400" />
          </div>
          <div>
            <h3 className="font-mono text-[12px] font-bold text-ink tracking-wide uppercase">
              POTENTIAL SOURCE VESSEL
            </h3>
            <p className="font-mono text-[9px] text-amber-400 font-medium">
              AIS CORRELATION SIGNAL
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
        {/* Name and MMSI */}
        <div className="rounded-md bg-base-950/80 p-2.5 border border-line/80 flex items-center justify-between">
          <div>
            <span className="text-[13px] font-bold text-ink block">
              {vesselName}
            </span>
            <span className="text-[9px] text-ink-faint">
              MMSI: {vessel.mmsi} {vessel.imo ? `| IMO: ${vessel.imo}` : ""}
            </span>
          </div>
          <span className="rounded bg-amber-500/20 border border-amber-500/40 px-2 py-1 text-[11px] font-extrabold text-amber-400">
            {scorePct}%
          </span>
        </div>

        {/* Vessel specs */}
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-md bg-base-950/60 p-2 border border-line/50">
            <span className="text-[8px] text-ink-faint uppercase block">TYPE</span>
            <span className="text-[10px] text-cyan-400 font-semibold">
              {vessel.vesselType || "Unknown"}
            </span>
          </div>
          <div className="rounded-md bg-base-950/60 p-2 border border-line/50">
            <span className="text-[8px] text-ink-faint uppercase block">FLAG</span>
            <span className="text-[10px] text-ink font-semibold">
              {vessel.flag || "—"}
            </span>
          </div>
        </div>

        {/* Distance & Time gap */}
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-md bg-base-950/60 p-2 border border-line/50">
            <span className="text-[8px] text-ink-faint uppercase block">CLOSEST DISTANCE</span>
            <span className="text-[10px] text-emerald-400 font-semibold">
              {vessel.closestDistanceKm != null ? `${vessel.closestDistanceKm.toFixed(2)} km` : "—"}
            </span>
          </div>
          <div className="rounded-md bg-base-950/60 p-2 border border-line/50">
            <span className="text-[8px] text-ink-faint uppercase block">TIME DIFFERENCE</span>
            <span className="text-[10px] text-emerald-400 font-semibold">
              {vessel.closestTimeDifferenceMinutes != null
                ? `${vessel.closestTimeDifferenceMinutes} min`
                : "0 min"}
            </span>
          </div>
        </div>

        {/* Component scores */}
        {vessel.scoreComponents && (
          <div className="space-y-1 rounded-md bg-base-950/60 p-2 border border-line/50 text-[9px]">
            <div className="flex justify-between">
              <span className="text-ink-faint">DISTANCE PROXIMITY SCORE</span>
              <span className="text-cyan-400">{(vessel.scoreComponents.distance * 100).toFixed(0)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-faint">TIME ALIGNMENT SCORE</span>
              <span className="text-cyan-400">{(vessel.scoreComponents.time * 100).toFixed(0)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-faint">TRACK CONSISTENCY SCORE</span>
              <span className="text-cyan-400">{(vessel.scoreComponents.trackConsistency * 100).toFixed(0)}%</span>
            </div>
          </div>
        )}

        {/* Scientific Disclaimer */}
        <div className="flex items-start gap-2 rounded-md bg-amber-500/10 border border-amber-500/30 p-2 text-[9px] text-amber-300">
          <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-amber-400 mt-0.5" />
          <p className="leading-tight">
            Ranking signal — NOT causation probability. Human review required. Do not use as sole attribution proof.
          </p>
        </div>
      </div>
    </div>
  );
}
