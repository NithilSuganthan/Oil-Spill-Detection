"use client";

import * as React from "react";
import {
  Brain,
  Waves,
  Anchor,
  FileText,
  Satellite,
  CheckCircle2,
  Loader2,
  AlertCircle,
  Nfc,
  Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatISTTime } from "@/lib/utils";
import type { DriftResult, AttributionResult, StoredReport, Incident, SatelliteScene } from "@/lib/types";
import type { SatelliteProviderInfo } from "@/lib/api/http-client";

function EngineCard({
  title,
  icon,
  status,
  statusLabel,
  isDemo,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  status: "idle" | "running" | "complete" | "failed";
  statusLabel: string;
  isDemo?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "panel p-4 transition-all",
        status === "running" && "border-signal-cyan/40 shadow-[0_0_15px_rgba(56,189,248,0.08)]",
        status === "complete" && "border-signal-green/20",
        status === "failed" && "border-signal-red/30"
      )}
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon}
          <h3 className="font-mono text-[10px] font-bold uppercase tracking-widest text-ink">
            {title}
          </h3>
        </div>
        <div className="flex items-center gap-1.5">
          {isDemo && (
            <span className="rounded border border-signal-amber/30 bg-signal-amber/10 px-1.5 py-0.5 font-mono text-[7px] tracking-wider text-signal-amber">
              DEMO
            </span>
          )}
          <span
            className={cn(
              "flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[8px] tracking-wider",
              status === "complete"
                ? "border-signal-green/40 text-signal-green"
                : status === "running"
                  ? "border-signal-cyan/40 text-signal-cyan"
                  : status === "failed"
                    ? "border-signal-red/40 text-signal-red"
                    : "border-line text-ink-faint"
            )}
          >
            {status === "complete" ? (
              <CheckCircle2 className="h-2.5 w-2.5" />
            ) : status === "running" ? (
              <Loader2 className="h-2.5 w-2.5 animate-spin" />
            ) : status === "failed" ? (
              <AlertCircle className="h-2.5 w-2.5" />
            ) : null}
            {statusLabel}
          </span>
        </div>
      </div>
      <div className="space-y-1.5">{children}</div>
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-2 py-0.5">
      <span className="shrink-0 font-mono text-[9px] uppercase tracking-widest text-ink-faint">
        {label}
      </span>
      <span className="text-right font-mono text-[10px] tabular-nums text-ink">{value}</span>
    </div>
  );
}

export function EngineCards({
  drift,
  attribution,
  report,
  scene,
  satProvider,
  incident,
  simulationMode,
}: {
  drift: DriftResult | null | undefined;
  attribution: AttributionResult | null | undefined;
  report: StoredReport | null | undefined;
  scene: SatelliteScene | null | undefined;
  satProvider: SatelliteProviderInfo | null | undefined;
  incident: Incident | null;
  simulationMode: boolean;
}) {
  const isDriftDemo = drift?.qualityFlags?.includes("DEMO_ENVIRONMENTAL_FORCING");
  const isAisDemo = attribution?.provider === "mock";
  const isReportDemo = report?.provider === "mock";

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-4">
      {/* SAR Segmentation Engine */}
      <EngineCard
        title="SAR SEGMENTATION"
        icon={<Brain className="h-4 w-4 text-signal-cyan" />}
        status={drift ? "complete" : incident ? "idle" : "idle"}
        statusLabel={drift ? "AVAILABLE" : incident ? "READY" : "IDLE"}
      >
        <MetaRow label="Model" value={incident?.model ?? "TinyUNet"} />
        <MetaRow label="Version" value={incident?.modelVersion ?? "1.0-dev"} />
        <MetaRow label="Input" value="VV + VH" />
        <MetaRow label="Format" value="[2, H, W]" />
        <MetaRow label="Normalization" value="p1–p99 robust" />
        <MetaRow label="Threshold" value="0.5" />
        {incident && (
          <>
            <div className="border-t border-line pt-1.5">
              <MetaRow label="Confidence" value={`${(incident.confidence * 100).toFixed(1)}%`} />
              <MetaRow label="Area" value={`${incident.areaKm2.toFixed(1)} km²`} />
              <MetaRow label="Status" value={incident.status} />
            </div>
            <p className="text-[8px] italic text-ink-faint/60">
              Model prediction — not confirmed oil. Requires human verification.
            </p>
          </>
        )}
        {!incident && (
          <p className="text-[9px] text-ink-faint/60">
            Select an incident to view model details.
          </p>
        )}
      </EngineCard>

      {/* Backward Drift Engine */}
      <EngineCard
        title="BACKWARD DRIFT ENGINE"
        icon={<Waves className="h-4 w-4 text-signal-cyan" />}
        status={drift ? "complete" : "idle"}
        statusLabel={drift ? "COMPLETE" : "IDLE"}
        isDemo={isDriftDemo}
      >
        {drift ? (
          <>
            <MetaRow label="Method" value={drift.method.replace(/_/g, " ")} />
            <MetaRow
              label="Env. Provider"
              value={
                drift.provenance?.environmentalProvider === "real"
                  ? "CMEMS + ERA5"
                  : "Mock (synthetic)"
              }
            />
            <MetaRow label="Ensemble" value={`${drift.ensembleSize} particles`} />
            <MetaRow label="Window" value={`${drift.integrationHours}h`} />
            <MetaRow label="Timestep" value={`${drift.timestepMinutes}min`} />
            <div className="border-t border-line pt-1.5">
              <MetaRow
                label="Source"
                value={`${drift.sourceLatitude.toFixed(4)}°N, ${drift.sourceLongitude.toFixed(4)}°E`}
              />
              <MetaRow label="Uncertainty" value={`±${drift.uncertaintyKm.toFixed(1)} km`} />
              <MetaRow label="Confidence" value={`${(drift.confidence * 100).toFixed(0)}%`} />
              <MetaRow
                label="Release Window"
                value={`${formatISTTime(drift.sourceEarliest)} – ${formatISTTime(drift.sourceLatest)}`}
              />
            </div>
            <p className="text-[8px] italic text-ink-faint/60">
              Estimated source region — not a confirmed origin point.
            </p>
          </>
        ) : (
          <p className="text-[9px] text-ink-faint/60">
            Run investigation to compute backward drift.
          </p>
        )}
      </EngineCard>

      {/* AIS Attribution Engine */}
      <EngineCard
        title="AIS ATTRIBUTION"
        icon={<Anchor className="h-4 w-4 text-signal-cyan" />}
        status={attribution ? "complete" : "idle"}
        statusLabel={attribution ? "COMPLETE" : "IDLE"}
        isDemo={isAisDemo}
      >
        {attribution ? (
          <>
            <MetaRow
              label="Provider"
              value={attribution.provider === "gfw" ? "Global Fishing Watch" : "Mock AIS"}
            />
            <MetaRow label="Observations" value={attribution.totalObservations} />
            <MetaRow label="Candidates" value={attribution.candidateCount} />
            {attribution.candidates.length > 0 && (
              <div className="border-t border-line pt-1.5">
                <MetaRow
                  label="Top Candidate"
                  value={attribution.candidates[0].vesselName || attribution.candidates[0].mmsi}
                />
                <MetaRow
                  label="Score"
                  value={`${(attribution.candidates[0].attributionScore * 100).toFixed(0)}%`}
                />
                <MetaRow
                  label="Distance"
                  value={`${attribution.candidates[0].closestDistanceKm.toFixed(1)} km`}
                />
                {attribution.candidates[0].scoreComponents && (
                  <>
                    <MetaRow
                      label="Distance Score"
                      value={`${(attribution.candidates[0].scoreComponents.distance * 100).toFixed(0)}%`}
                    />
                    <MetaRow
                      label="Time Score"
                      value={`${(attribution.candidates[0].scoreComponents.time * 100).toFixed(0)}%`}
                    />
                    <MetaRow
                      label="Track Score"
                      value={`${(attribution.candidates[0].scoreComponents.trackConsistency * 100).toFixed(0)}%`}
                    />
                  </>
                )}
              </div>
            )}
            <p className="text-[8px] italic text-ink-faint/60">
              Attribution score ranks potential vessels — not causation probability.
            </p>
          </>
        ) : (
          <p className="text-[9px] text-ink-faint/60">
            Run investigation to perform AIS correlation.
          </p>
        )}
      </EngineCard>

      {/* Groq Report Engine */}
      <EngineCard
        title="AI REPORT ENGINE"
        icon={<FileText className="h-4 w-4 text-signal-cyan" />}
        status={report ? "complete" : "idle"}
        statusLabel={report ? "COMPLETE" : "IDLE"}
        isDemo={isReportDemo}
      >
        {report ? (
          <>
            <MetaRow label="Provider" value={report.provider} />
            <MetaRow label="Model" value={report.model} />
            <MetaRow label="Evidence Version" value={report.evidenceVersion} />
            <MetaRow label="Prompt Version" value={report.promptVersion} />
            <MetaRow label="Generated" value={formatISTTime(report.generatedAt)} />
            <div className="border-t border-line pt-1.5">
              <MetaRow label="Title" value={report.report.title} />
              <MetaRow
                label="Human Review"
                value={report.report.humanReviewRequired ? "REQUIRED" : "N/A"}
              />
            </div>
            <p className="text-[8px] italic text-ink-faint/60">
              AI-generated summary — human verification required.
            </p>
          </>
        ) : (
          <p className="text-[9px] text-ink-faint/60">
            Generate investigation report after drift and AIS analysis.
          </p>
        )}
      </EngineCard>
    </div>
  );
}
