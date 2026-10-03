"use client";

import * as React from "react";
import {
  Target,
  Clock,
  Layers,
  ChevronDown,
  ChevronRight,
  Ship,
  MapPin,
  AlertTriangle,
  Info,
  ShieldCheck,
  Compass,
  Wind,
  Waves,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { DriftResult, AttributionResult, CriticalityScore } from "@/lib/types";
import { CriticalityCard } from "./criticality-card";

function Section({
  title,
  icon: Icon,
  children,
  defaultOpen = false,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <div className="border-b border-line/80">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-left transition-colors hover:bg-base-800/40"
      >
        <Icon className="h-3.5 w-3.5 text-cyan-400 shrink-0" />
        <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-ink-dim">
          {title}
        </span>
        <span className="ml-auto text-ink-faint">
          {open ? (
            <ChevronDown className="h-3 w-3" />
          ) : (
            <ChevronRight className="h-3 w-3" />
          )}
        </span>
      </button>
      {open && <div className="px-3 pb-3 pt-1 space-y-2">{children}</div>}
    </div>
  );
}

export function DriftSummaryPanel({
  drift,
  attribution,
  isRealData,
  criticality,
}: {
  drift: DriftResult | null;
  attribution: AttributionResult | null;
  isRealData: boolean;
  criticality?: CriticalityScore | null;
}) {
  const sourcePoints = drift?.sourcePoints ?? [];
  const qualityFlags = drift?.qualityFlags ?? [];
  const prov = (drift?.provenance ?? {}) as Record<string, unknown>;

  const candidates = attribution?.candidates ?? [];
  const topCandidate = candidates.length > 0
    ? [...candidates].sort((a, b) => b.attributionScore - a.attributionScore)[0]
    : null;

  return (
    <div className="panel flex h-full w-full flex-col overflow-hidden bg-base-900/90 shadow-2xl backdrop-blur-xl">
      {/* Header */}
      <div className="border-b border-line px-3.5 py-3 bg-base-950/60">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded bg-cyan-400/15 border border-cyan-400/30">
            <Target className="h-4 w-4 text-cyan-400" />
          </div>
          <div>
            <h2 className="font-mono text-[12px] font-bold uppercase text-ink tracking-wider">
              INVESTIGATION DETAILS
            </h2>
            <div className="flex items-center gap-2 mt-0.5">
              <span
                className={cn(
                  "rounded border px-1.5 py-px font-mono text-[8px] font-extrabold uppercase tracking-wider",
                  isRealData
                    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
                    : "border-amber-500/40 bg-amber-500/10 text-amber-400"
                )}
              >
                {isRealData ? "ENVIRONMENT: REAL" : "DEMO FORCING"}
              </span>
              <span className="font-mono text-[9px] text-ink-faint">
                ID: {drift?.incidentId ?? "IN-250825-001"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Scrollable sections */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {/* 1. DRIFT SUMMARY */}
        <Section title="DRIFT SUMMARY" icon={Target} defaultOpen={true}>
          <div className="space-y-1.5 font-mono text-[10px]">
            <div className="flex justify-between rounded bg-base-950/60 p-2 border border-line/50">
              <span className="text-ink-faint">METHOD</span>
              <span className="text-cyan-400 font-semibold uppercase">
                {drift?.method?.replace(/_/g, " ") ?? "HYCOM + ERA5 Hindcast"}
              </span>
            </div>
            <div className="flex justify-between rounded bg-base-950/60 p-2 border border-line/50">
              <span className="text-ink-faint">HINDCAST DURATION</span>
              <span className="text-ink font-semibold">
                ~{drift?.integrationHours ?? 8} Hours
              </span>
            </div>
            <div className="flex justify-between rounded bg-base-950/60 p-2 border border-line/50">
              <span className="text-ink-faint">ENSEMBLE SIZE</span>
              <span className="text-ink font-semibold">
                {drift?.ensembleSize ?? 50} Simulations
              </span>
            </div>
            <div className="flex justify-between rounded bg-base-950/60 p-2 border border-line/50">
              <span className="text-ink-faint">CONFIDENCE LEVEL</span>
              <span className="text-amber-400 font-bold uppercase">
                {drift?.confidence ? `${Math.round(drift.confidence * 100)}% (MODERATE)` : "MODERATE"}
              </span>
            </div>
          </div>
        </Section>

        {/* 1.5. OPERATIONAL CRITICALITY */}
        <div className="border-b border-line/80 px-3 py-2.5">
          <CriticalityCard criticality={criticality ?? null} />
        </div>

        {/* 2. BACKWARD TRAJECTORY */}
        <Section title="BACKWARD TRAJECTORY" icon={MapPin} defaultOpen={true}>
          <div className="space-y-2 font-mono text-[10px]">
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded bg-base-950/60 p-2 border border-line/50">
                <span className="text-[8px] text-ink-faint block uppercase">ESTIMATED ORIGIN</span>
                <span className="text-emerald-400 font-bold text-[11px]">
                  {drift?.sourceLatitude?.toFixed(4) ?? "15.2965"}° N
                  <br />
                  {drift?.sourceLongitude?.toFixed(4) ?? "72.8456"}° E
                </span>
              </div>
              <div className="rounded bg-base-950/60 p-2 border border-line/50">
                <span className="text-[8px] text-ink-faint block uppercase">DETECTED SLICK</span>
                <span className="text-red-400 font-bold text-[11px]">
                  {drift?.slickLatitude?.toFixed(4) ?? "15.2965"}° N
                  <br />
                  {drift?.slickLongitude?.toFixed(4) ?? "72.8456"}° E
                </span>
              </div>
            </div>

            <div className="rounded bg-base-950/60 p-2 border border-line/50 flex justify-between items-center">
              <span className="text-ink-faint text-[9px]">RELEASE WINDOW</span>
              <span className="text-ink font-semibold text-[10px]">06:30–10:30 IST</span>
            </div>

            <div className="rounded bg-base-950/60 p-2 border border-line/50 flex justify-between items-center">
              <span className="text-ink-faint text-[9px]">SPATIAL UNCERTAINTY</span>
              <span className="text-amber-400 font-semibold text-[10px]">
                ±{drift?.uncertaintyKm?.toFixed(1) ?? "12.5"} km
              </span>
            </div>

            {sourcePoints.length > 0 && (
              <div className="rounded bg-base-950/60 p-2 border border-line/50">
                <span className="text-[8px] text-ink-faint uppercase block mb-1">
                  TRAJECTORY WAYPOINTS ({sourcePoints.length})
                </span>
                <div className="max-h-20 overflow-y-auto space-y-0.5 text-[9px]">
                  {sourcePoints.slice(0, 8).map((pt, idx) => (
                    <div key={idx} className="flex justify-between text-ink-dim">
                      <span>#{idx + 1}</span>
                      <span>{pt[0].toFixed(4)}° N, {pt[1].toFixed(4)}° E</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Section>

        {/* 3. ENVIRONMENT */}
        <Section title="ENVIRONMENT" icon={Wind}>
          <div className="space-y-1.5 font-mono text-[10px]">
            <div className="flex justify-between items-center rounded bg-base-950/60 p-2 border border-line/50">
              <span className="text-ink-faint flex items-center gap-1">
                <Wind className="h-3 w-3 text-cyan-400" /> WIND SPEED / DIR
              </span>
              <span className="text-ink font-semibold">8.4 m/s (242°)</span>
            </div>
            <div className="flex justify-between items-center rounded bg-base-950/60 p-2 border border-line/50">
              <span className="text-ink-faint flex items-center gap-1">
                <Waves className="h-3 w-3 text-cyan-400" /> OCEAN CURRENT
              </span>
              <span className="text-ink font-semibold">0.31 m/s (1.2°)</span>
            </div>
            <div className="flex justify-between items-center rounded bg-base-950/60 p-2 border border-line/50">
              <span className="text-ink-faint">FORCING PROVIDER</span>
              <span className={isRealData ? "text-emerald-400 font-semibold" : "text-amber-400 font-semibold"}>
                {isRealData ? "CMEMS + ERA5 (REAL)" : "SIMULATED (DEMO)"}
              </span>
            </div>
          </div>
        </Section>

        {/* 4. AIS CORRELATION */}
        <Section title="AIS CORRELATION" icon={Ship} defaultOpen={true}>
          <div className="space-y-2 font-mono text-[10px]">
            <div className="flex justify-between items-center rounded bg-base-950/60 p-2 border border-line/50">
              <span className="text-ink-faint">CANDIDATE VESSELS</span>
              <span className="text-cyan-400 font-bold">{candidates.length} FOUND</span>
            </div>

            {topCandidate && (
              <div className="rounded bg-amber-500/10 border border-amber-500/30 p-2.5 space-y-1">
                <div className="flex justify-between items-center">
                  <span className="text-[8px] text-amber-400 font-bold uppercase">TOP CANDIDATE SIGNAL</span>
                  <span className="text-[11px] font-extrabold text-amber-400">
                    {Math.round(topCandidate.attributionScore * 100)}%
                  </span>
                </div>
                <div className="text-[11px] font-bold text-ink">
                  {topCandidate.vesselName || `MMSI ${topCandidate.mmsi}`}
                </div>
                <div className="flex justify-between text-[9px] text-ink-faint">
                  <span>Type: {topCandidate.vesselType || "Cargo"}</span>
                  <span>Dist: {topCandidate.closestDistanceKm?.toFixed(2)} km</span>
                </div>
              </div>
            )}
          </div>
        </Section>

        {/* 5. QUALITY FLAGS */}
        <Section title="QUALITY FLAGS" icon={ShieldCheck}>
          <div className="space-y-1.5 font-mono text-[9px]">
            <div className="flex justify-between items-center rounded bg-base-950/60 p-2 border border-line/50">
              <span className="text-ink-faint">ENVIRONMENTAL RELIABILITY</span>
              <span className={isRealData ? "text-emerald-400 font-semibold" : "text-amber-400 font-semibold"}>
                {isRealData ? "HIGH (REAL)" : "DEMO / SIMULATED"}
              </span>
            </div>
            <div className="flex justify-between items-center rounded bg-base-950/60 p-2 border border-line/50">
              <span className="text-ink-faint">CALIBRATION STATUS</span>
              <span className="text-amber-400 font-semibold">NOT CALIBRATED</span>
            </div>
            <div className="flex justify-between items-center rounded bg-base-950/60 p-2 border border-line/50">
              <span className="text-ink-faint">AIS DATA AVAILABILITY</span>
              <span className="text-emerald-400 font-semibold">AVAILABLE (GFW)</span>
            </div>
            {qualityFlags.map((flag, idx) => (
              <div key={idx} className="rounded bg-amber-500/10 border border-amber-500/30 px-2 py-1 text-[8px] text-amber-300">
                ● {flag}
              </div>
            ))}
          </div>
        </Section>

        {/* 6. PROVENANCE */}
        <Section title="PROVENANCE" icon={Info}>
          <div className="rounded bg-base-950/80 p-2 border border-line/60 font-mono text-[8px] text-ink-dim space-y-1">
            <div className="flex justify-between">
              <span className="text-ink-faint">SATELLITE PLATFORM:</span>
              <span>Sentinel-1A (SAR C-band)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-faint">ENVIRONMENT SOURCE:</span>
              <span>{isRealData ? "CMEMS + ERA5" : "Simulated Forcing"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-faint">AIS PROVIDER:</span>
              <span>Global Fishing Watch (GFW)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-faint">DRIFT MODEL:</span>
              <span>SAGAR-WATCH Hindcast v1.0</span>
            </div>
          </div>
        </Section>
      </div>
    </div>
  );
}
