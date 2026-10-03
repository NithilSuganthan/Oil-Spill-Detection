"use client";

import * as React from "react";
import {
  Target,
  Ship,
  Wind,
  MapPin,
  AlertTriangle,
  Clock,
  Compass,
  Waves,
  Shield,
  X,
  Info,
  ChevronDown,
  ChevronRight,
  Database,
  FileText,
  Loader2,
  CheckCircle2,
  Download,
  Activity,
  Layers,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  Incident,
  DriftResult,
  AttributionResult,
  CandidateVessel,
  CriticalityScore,
  EnvironmentalGrid,
} from "@/lib/types";
import { formatArea, formatISTDate, formatISTTime, formatPercent } from "@/lib/utils";
import { CriticalityCard } from "@/components/drift-map/criticality-card";
import { generateInvestigationPDF } from "@/lib/pdf/generate-report-pdf";

export type PanelContext =
  | { type: "incident" }
  | { type: "source" }
  | { type: "vessel"; vessel: CandidateVessel }
  | { type: "environment" }
  | { type: "criticality" };

interface ContextualPanelProps {
  context: PanelContext | null;
  incident: Incident;
  drift: DriftResult | null;
  attribution: AttributionResult | null;
  criticality: CriticalityScore | null;
  envGrid: EnvironmentalGrid | null;
  isRealData: boolean;
  onClearContext?: () => void;
  onSelectVessel?: (vessel: CandidateVessel) => void;
  activeStageId?: string | null;
}

function Section({
  title,
  number,
  icon: Icon,
  children,
  defaultOpen = true,
  badgeText,
}: {
  title: string;
  number?: string;
  icon: React.ElementType;
  children: React.ReactNode;
  defaultOpen?: boolean;
  badgeText?: string;
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <div className="border-b border-line/60 bg-base-950/20">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-left transition-colors hover:bg-base-800/40"
      >
        {number && (
          <span className="font-mono text-[9px] font-extrabold text-cyan-400/80">
            {number}
          </span>
        )}
        <Icon className="h-3.5 w-3.5 text-cyan-400 shrink-0" />
        <span className="font-mono text-[9.5px] font-bold uppercase tracking-wider text-ink">
          {title}
        </span>
        {badgeText && (
          <span className="ml-auto font-mono text-[7.5px] font-bold px-1.5 py-0.5 rounded border border-cyan-400/30 bg-cyan-400/10 text-cyan-300">
            {badgeText}
          </span>
        )}
        <span className={cn("text-ink-faint", badgeText ? "ml-1.5" : "ml-auto")}>
          {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        </span>
      </button>
      {open && <div className="px-3 pb-3 pt-1 space-y-1.5">{children}</div>}
    </div>
  );
}

function MetaRow({
  label,
  value,
  accent,
  subtext,
}: {
  label: string;
  value: React.ReactNode;
  accent?: boolean;
  subtext?: string;
}) {
  return (
    <div className="flex flex-col rounded bg-base-950/80 p-2 border border-line/40">
      <div className="flex items-center justify-between">
        <span className="text-[8px] font-mono text-ink-faint uppercase tracking-wider">{label}</span>
        <span className={cn("font-mono text-[10px] font-bold", accent ? "text-cyan-400" : "text-ink")}>
          {value}
        </span>
      </div>
      {subtext && (
        <span className="font-mono text-[7.5px] text-ink-faint/70 mt-0.5">{subtext}</span>
      )}
    </div>
  );
}

export function ContextualPanel({
  context,
  incident,
  drift,
  attribution,
  criticality,
  envGrid,
  isRealData,
  onClearContext,
  onSelectVessel,
  activeStageId,
}: ContextualPanelProps) {
  const [reportState, setReportState] = React.useState<"idle" | "collecting" | "structuring" | "generating" | "ready">("idle");

  const handleGenerateReport = React.useCallback(async () => {
    setReportState("collecting");
    await new Promise((r) => setTimeout(r, 600));
    setReportState("structuring");
    await new Promise((r) => setTimeout(r, 700));
    setReportState("generating");
    await new Promise((r) => setTimeout(r, 800));

    try {
      generateInvestigationPDF({
        incident,
        drift,
        attribution,
      });
      setReportState("ready");
    } catch (err) {
      console.error("PDF generation failed:", err);
      setReportState("idle");
    }
  }, [incident, drift, attribution]);

  const candidates = attribution?.candidates ?? [];
  const topCandidate = candidates[0];

  return (
    <div className="flex h-full flex-col overflow-hidden bg-base-950/90 shadow-2xl backdrop-blur-xl border-l border-line/60">
      {/* Console Top Header */}
      <div className="border-b border-line/60 px-3.5 py-3 bg-base-950/95 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <div className="flex h-6 w-6 items-center justify-center rounded bg-cyan-400/10 border border-cyan-400/30 shrink-0">
            <Activity className="h-3.5 w-3.5 text-cyan-400" />
          </div>
          <div className="min-w-0">
            <h2 className="font-mono text-[11px] font-bold uppercase tracking-wider text-ink truncate">
              ANALYST CONSOLE
            </h2>
            <p className="font-mono text-[8px] text-cyan-400 font-extrabold truncate">
              INVESTIGATION {incident.id}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <span className="font-mono text-[8px] px-1.5 py-0.5 rounded border border-cyan-400/30 bg-cyan-400/10 text-cyan-300 font-bold uppercase">
            MODEL DETECTION
          </span>
          {context?.type !== "incident" && onClearContext && (
            <button
              onClick={onClearContext}
              className="rounded p-1 text-ink-faint hover:bg-base-800 hover:text-ink transition-colors"
              title="Reset Context"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Primary Key Metrics Header Bar */}
      <div className="grid grid-cols-2 gap-1.5 p-2 bg-base-900/50 border-b border-line/60 shrink-0">
        <div className="rounded bg-base-950/80 p-2 border border-line/40 flex flex-col justify-between">
          <span className="text-[7.5px] font-mono text-ink-faint uppercase">MODEL CONFIDENCE</span>
          <span className="font-mono text-[13px] font-extrabold text-cyan-400">
            {formatPercent(incident.confidence)}
          </span>
        </div>
        <div className="rounded bg-base-950/80 p-2 border border-line/40 flex flex-col justify-between">
          <span className="text-[7.5px] font-mono text-ink-faint uppercase">SPILL AREA</span>
          <span className="font-mono text-[13px] font-extrabold text-red-400">
            {formatArea(incident.areaKm2)} km²
          </span>
        </div>
      </div>

      {/* Scrollable Continuous Investigation Flow */}
      <div className="flex-1 overflow-y-auto scrollbar-thin space-y-0">
        {/* 01 DETECTION EVIDENCE */}
        <Section title="DETECTION EVIDENCE" number="01" icon={Target} defaultOpen={true}>
          <MetaRow label="INCIDENT ID" value={incident.id} accent />
          <MetaRow label="MODEL CONFIDENCE" value={formatPercent(incident.confidence)} accent subtext="Model probability, not ground certainty" />
          <MetaRow label="SPILL AREA" value={`${formatArea(incident.areaKm2)} km²`} />
          <MetaRow label="DETECTED TIMESTAMP" value={`${formatISTDate(incident.detectedAt)} ${formatISTTime(incident.detectedAt)} UTC`} />
          <MetaRow label="CENTROID LOCATION" value={`${incident.centroid.lat.toFixed(4)}° N, ${incident.centroid.lon.toFixed(4)}° E`} subtext={incident.locationDescription} />
          <MetaRow label="PERIMETER" value={`${incident.perimeterKm2.toFixed(1)} km`} />
          <MetaRow label="SATELLITE SOURCE" value={incident.satellite} subtext={`Scene: ${incident.sceneId}`} />
          <MetaRow label="DETECTION MODEL" value={`${incident.model} ${incident.modelVersion}`} />
        </Section>

        {/* 02 ENVIRONMENTAL CONDITIONS */}
        <Section title="ENVIRONMENTAL CONDITIONS" number="02" icon={Wind} defaultOpen={true}>
          {envGrid ? (
            <>
              <MetaRow
                label="DATA FORCING SOURCE"
                value={envGrid.metadata?.provider?.toUpperCase() ?? (isRealData ? "CMEMS NRT + ECMWF" : "ERA5 REANALYSIS")}
                accent
                subtext="Oceanographic & Meteorological Forcing"
              />
              {envGrid.windPoint && (
                <MetaRow
                  label="WIND SPEED & DIR"
                  value={`${envGrid.windPoint.speedKts.toFixed(1)} kts (${Math.round(envGrid.windPoint.directionDeg)}°)`}
                  subtext={`Surface vector u: ${envGrid.windPoint.u.toFixed(2)}, v: ${envGrid.windPoint.v.toFixed(2)}`}
                />
              )}
              {envGrid.currentPoint && (
                <MetaRow
                  label="OCEAN CURRENT"
                  value={`${envGrid.currentPoint.speedMs.toFixed(2)} m/s (${Math.round(envGrid.currentPoint.directionDeg)}°)`}
                  subtext="Surface hydrodynamic current speed"
                />
              )}
              <MetaRow label="DATA AGE" value={envGrid.metadata?.dataAgeMinutes ? `~${Math.round(envGrid.metadata.dataAgeMinutes)} min` : "Near Real-Time"} />
              <div className="rounded bg-cyan-500/10 border border-cyan-400/30 p-2 text-[8px] text-cyan-300 font-mono">
                <Info className="h-3 w-3 inline mr-1 text-cyan-400" />
                Data source: CMEMS NRT / ECMWF Forecast. Environmental fields are numerical model products, not direct observations.
              </div>
            </>
          ) : (
            <div className="rounded bg-base-950/80 border border-line/40 p-3 text-center">
              <span className="font-mono text-[9.5px] text-ink-faint font-bold">
                ENVIRONMENTAL DATA UNAVAILABLE
              </span>
            </div>
          )}
        </Section>

        {/* 03 DRIFT RECONSTRUCTION */}
        <Section title="DRIFT RECONSTRUCTION" number="03" icon={Compass} defaultOpen={true}>
          {drift ? (
            <>
              <MetaRow label="METHOD" value={drift.method.replace(/_/g, " ").toUpperCase()} accent />
              <MetaRow label="ESTIMATED SOURCE ORIGIN" value={`${drift.sourceLatitude.toFixed(4)}° N, ${drift.sourceLongitude.toFixed(4)}° E`} accent />
              <MetaRow label="SPATIAL UNCERTAINTY" value={`±${drift.uncertaintyKm.toFixed(1)} km`} subtext="Ensemble radius boundary" />
              <MetaRow label="TEMPORAL UNCERTAINTY" value={`±${drift.uncertaintyHours.toFixed(1)} hours`} />
              <MetaRow label="RELEASE WINDOW" value={`${formatISTTime(drift.sourceEarliest)} — ${formatISTTime(drift.sourceLatest)}`} />
              <MetaRow label="MODEL CONFIDENCE" value={formatPercent(drift.confidence)} />
              <div className="rounded bg-amber-500/10 border border-amber-500/30 p-2 text-[8px] text-amber-300 font-mono">
                <AlertTriangle className="h-3 w-3 inline mr-1 text-amber-400" />
                Backward trajectory is a mathematical reconstruction from current ocean forcing. Not a confirmed physical origin.
              </div>
            </>
          ) : (
            <div className="rounded bg-base-950/80 border border-amber-500/30 p-3 text-center">
              <span className="font-mono text-[9.5px] text-amber-400 font-bold block">
                DRIFT RECONSTRUCTION UNAVAILABLE
              </span>
              <span className="font-mono text-[8px] text-ink-faint">
                Trajectory has not been computed for this detection
              </span>
            </div>
          )}
        </Section>

        {/* 04 AIS CORRELATION & CANDIDATE VESSELS */}
        <Section title="AIS CORRELATION & ATTRIBUTION" number="04" icon={Ship} defaultOpen={true} badgeText={`${candidates.length} CANDIDATES`}>
          {candidates.length > 0 ? (
            <div className="space-y-2">
              <div className="rounded bg-cyan-500/10 border border-cyan-400/30 p-2 text-[8px] text-cyan-300 font-mono">
                <Shield className="h-3 w-3 inline mr-1 text-cyan-400" />
                CANDIDATE VESSELS &amp; ATTRIBUTION EVIDENCE. Displays proximity and temporal correlation. NEVER implies causal certainty.
              </div>

              {candidates.map((vessel, idx) => {
                const scorePct = Math.round(vessel.attributionScore * 100);
                const isSelected = context?.type === "vessel" && context.vessel.mmsi === vessel.mmsi;

                return (
                  <div
                    key={vessel.mmsi}
                    onClick={() => onSelectVessel?.(vessel)}
                    className={cn(
                      "rounded-md border p-2.5 transition-all cursor-pointer",
                      isSelected
                        ? "bg-amber-500/15 border-amber-400/60 shadow-[0_0_12px_rgba(245,158,11,0.2)]"
                        : idx === 0
                        ? "bg-base-900/80 border-amber-500/30 hover:border-amber-400/50"
                        : "bg-base-950/60 border-line/40 hover:border-cyan-400/40"
                    )}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-[9px] font-extrabold text-amber-400">
                          #{String(idx + 1).padStart(2, "0")}
                        </span>
                        <span className="font-mono text-[11px] font-extrabold text-ink">
                          {vessel.vesselName || `MMSI ${vessel.mmsi}`}
                        </span>
                      </div>
                      <span className="font-mono text-[11px] font-extrabold text-amber-400 bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.5 rounded">
                        {scorePct}%
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-1 font-mono text-[8px] text-ink-faint">
                      <div>MMSI: <span className="text-ink font-semibold">{vessel.mmsi}</span></div>
                      <div>TYPE: <span className="text-ink font-semibold">{vessel.vesselType || "Unknown"}</span></div>
                      <div>DISTANCE: <span className="text-ink font-semibold">{vessel.closestDistanceKm != null ? `${vessel.closestDistanceKm.toFixed(2)} km` : "—"}</span></div>
                      <div>TIME OFFSET: <span className="text-ink font-semibold">{vessel.closestTimeDifferenceMinutes != null ? `${vessel.closestTimeDifferenceMinutes} min` : "—"}</span></div>
                    </div>

                    {/* Attribution Score Breakdown Bar */}
                    {vessel.scoreComponents && (
                      <div className="mt-2 pt-2 border-t border-line/40 space-y-1">
                        <div className="flex items-center justify-between text-[7.5px] font-mono text-ink-faint">
                          <span>DISTANCE ({Math.round(vessel.scoreComponents.distance * 100)}%)</span>
                          <span>TIME ({Math.round(vessel.scoreComponents.time * 100)}%)</span>
                          <span>TRACK ({Math.round(vessel.scoreComponents.trackConsistency * 100)}%)</span>
                        </div>
                        <div className="flex h-1.5 w-full overflow-hidden rounded bg-base-950 border border-line/40">
                          <div className="bg-cyan-400" style={{ width: `${vessel.scoreComponents.distance * 33.3}%` }} title="Distance score" />
                          <div className="bg-amber-400" style={{ width: `${vessel.scoreComponents.time * 33.3}%` }} title="Time score" />
                          <div className="bg-emerald-400" style={{ width: `${vessel.scoreComponents.trackConsistency * 33.3}%` }} title="Track consistency" />
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="rounded bg-base-950/80 border border-line/40 p-3 text-center">
              <span className="font-mono text-[9.5px] text-ink-faint font-bold">
                AIS DATA UNAVAILABLE
              </span>
              <span className="font-mono text-[8px] text-ink-faint block mt-0.5">
                No matching AIS vessel signals correlated in time window
              </span>
            </div>
          )}
        </Section>

        {/* 05 SOURCE ESTIMATE */}
        <Section title="SOURCE ESTIMATE" number="05" icon={Compass} defaultOpen={true}>
          {drift ? (
            <>
              <MetaRow label="ESTIMATED SOURCE REGION" value={`${drift.sourceLatitude.toFixed(4)}° N, ${drift.sourceLongitude.toFixed(4)}° E`} accent />
              <MetaRow label="UNCERTAINTY REGION" value={`±${drift.uncertaintyKm.toFixed(1)} km (Purple region on map)`} />
              <MetaRow label="ESTIMATED RELEASE WINDOW" value={`${formatISTTime(drift.sourceEarliest)} — ${formatISTTime(drift.sourceLatest)}`} />
              <div className="rounded bg-purple-500/10 border border-purple-500/30 p-2 text-[8px] text-purple-300 font-mono">
                <MapPin className="h-3 w-3 inline mr-1 text-purple-400" />
                Displayed on center map as translucent purple uncertainty bounds.
              </div>
            </>
          ) : (
            <div className="rounded bg-base-950/80 border border-line/40 p-3 text-center font-mono text-[9.5px] text-ink-faint">
              SOURCE ESTIMATE UNAVAILABLE
            </div>
          )}
        </Section>

        {/* 06 OPERATIONAL PRIORITY INDEX (CRITICALITY) */}
        <Section title="OPERATIONAL PRIORITY INDEX" number="06" icon={Shield} defaultOpen={true}>
          <div className="space-y-2">
            <CriticalityCard criticality={criticality} />
            <div className="rounded bg-base-950/80 border border-line/40 p-2 font-mono text-[7.5px] text-ink-faint">
              OPERATIONAL PRIORITY INDEX: Composite operational urgency metric combining slick size, detection confidence, spreading risk, and vessel proximity. Not an environmental damage rating.
            </div>
          </div>
        </Section>

        {/* 07 AI REPORT CULMINATION ACTION */}
        <Section title="AI INVESTIGATION REPORT" number="07" icon={FileText} defaultOpen={true}>
          <div className="rounded-md bg-gradient-to-b from-cyan-950/30 to-base-950 border border-cyan-400/30 p-3 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] font-extrabold text-cyan-300 uppercase">
                REPORT CULMINATION
              </span>
              <span className="font-mono text-[8px] text-ink-faint">
                PDF EXPORT
              </span>
            </div>

            <p className="font-mono text-[8.5px] text-ink-dim leading-relaxed">
              Compile full satellite evidence, environmental ocean forcing, backward drift hindcast, and candidate vessel attribution into an intelligence report.
            </p>

            <button
              onClick={handleGenerateReport}
              disabled={reportState !== "idle" && reportState !== "ready"}
              className="w-full flex items-center justify-center gap-2 rounded-md bg-gradient-to-r from-cyan-500/20 via-cyan-400/30 to-emerald-500/20 border border-cyan-400/60 py-2.5 px-3 font-mono text-[11px] font-extrabold text-cyan-200 shadow-[0_0_16px_rgba(34,211,238,0.25)] transition-all hover:scale-[1.02] active:scale-95 disabled:opacity-50"
            >
              {reportState === "idle" && (
                <>
                  <FileText className="h-4 w-4 text-cyan-400" />
                  GENERATE AI REPORT
                </>
              )}
              {reportState === "collecting" && (
                <>
                  <Loader2 className="h-4 w-4 animate-spin text-cyan-400" />
                  COLLECTING EVIDENCE...
                </>
              )}
              {reportState === "structuring" && (
                <>
                  <Loader2 className="h-4 w-4 animate-spin text-amber-400" />
                  STRUCTURING FINDINGS...
                </>
              )}
              {reportState === "generating" && (
                <>
                  <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />
                  GENERATING REPORT...
                </>
              )}
              {reportState === "ready" && (
                <>
                  <Download className="h-4 w-4 text-emerald-400" />
                  DOWNLOAD REPORT PDF
                </>
              )}
            </button>
          </div>
        </Section>
      </div>

      {/* Provenance Footer */}
      <div className="border-t border-line/60 px-3.5 py-2 bg-base-950/95 shrink-0">
        <div className="flex items-center justify-between font-mono text-[8px] text-ink-faint">
          <span className="flex items-center gap-1.5">
            <span className={cn(
              "h-2 w-2 rounded-full",
              isRealData ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" : "bg-amber-400"
            )} />
            {isRealData ? "CMEMS + SENTINEL-1" : "MODEL ANALYSIS DATASET"}
          </span>
          <span className="font-bold text-ink-dim">SAGAR WATCH WORKSTATION</span>
        </div>
      </div>
    </div>
  );
}
