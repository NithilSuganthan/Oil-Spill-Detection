"use client";

import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  X,
  Satellite,
  Cpu,
  MapPin,
  Download,
  Image as ImageIcon,
  Anchor,
  Shield,
  AlertTriangle,
  Play,
  Loader2,
  Waves,
  Brain,
  Wind,
  Eye,
  Calendar,
  Clock,
  ChevronDown,
  ChevronRight,
  Zap,
} from "lucide-react";
import Link from "next/link";
import type { CandidateVessel, DetectionIntelligence, Incident } from "@/lib/types";
import { useAppStore } from "@/lib/store/use-app-store";
import {
  cn,
  formatArea,
  formatISTDate,
  formatISTTime,
  formatISTTimeShort,
  formatPercent,
} from "@/lib/utils";
import { Badge, levelTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getAttribution, getDrift, runInvestigation } from "@/lib/api/client";

function MetaRow({ label, value, mono = true }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <span className="shrink-0 font-mono text-[10px] uppercase tracking-widest text-ink-faint">
        {label}
      </span>
      <span className={cn("text-right text-xs text-ink", mono && "font-mono tabular-nums")}>
        {value}
      </span>
    </div>
  );
}

function ExpandableSection({
  icon,
  title,
  status,
  statusLabel,
  defaultOpen = false,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  status?: "complete" | "running" | "available" | "unavailable";
  statusLabel?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(defaultOpen);

  const statusDot = status ? (
    <span className="flex items-center gap-1">
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          status === "complete"
            ? "bg-signal-green"
            : status === "running"
              ? "bg-signal-cyan animate-status-blink"
              : status === "available"
                ? "bg-signal-amber"
                : "bg-line-bright"
        )}
      />
      <span
        className={cn(
          "font-mono text-[8px] uppercase tracking-wider",
          status === "complete"
            ? "text-signal-green"
            : status === "running"
              ? "text-signal-cyan"
              : status === "available"
                ? "text-signal-amber"
                : "text-ink-faint"
        )}
      >
        {statusLabel ?? status}
      </span>
    </span>
  ) : null;

  return (
    <section>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between border-t border-line py-2 text-left transition-colors hover:bg-base-800/30"
      >
        <div className="flex items-center gap-1.5">
          {icon}
          <h4 className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-signal-cyan/90">
            {title}
          </h4>
        </div>
        <div className="flex items-center gap-2">
          {statusDot}
          {open ? (
            <ChevronDown className="h-3 w-3 text-ink-faint" />
          ) : (
            <ChevronRight className="h-3 w-3 text-ink-faint" />
          )}
        </div>
      </button>
      {open && <div className="section-expand pb-2">{children}</div>}
    </section>
  );
}

function exportGeoJSON(incident: Incident) {
  const fc = {
    type: "FeatureCollection" as const,
    metadata: {
      incidentId: incident.id,
      source: "SAGAR WATCH (prototype mock export)",
      model: `${incident.model} ${incident.modelVersion}`,
      confidence: incident.confidence,
      detectedAt: incident.detectedAt,
    },
    features: [
      {
        type: "Feature" as const,
        properties: {
          id: incident.id,
          confidence: incident.confidence,
          areaKm2: incident.areaKm2,
          centroid: incident.centroid,
        },
        geometry: incident.geometry,
      },
    ],
  };
  const blob = new Blob([JSON.stringify(fc, null, 2)], { type: "application/geo+json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${incident.id}.geojson`;
  a.click();
  URL.revokeObjectURL(url);
}

function CandidateCardCompact({
  candidate,
  rank,
  isSelected,
  onSelect,
}: {
  candidate: CandidateVessel;
  rank: number;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const scorePercent = Math.round(candidate.attributionScore * 100);
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full rounded border p-2.5 text-left transition-colors",
        isSelected
          ? "border-signal-cyan/60 bg-signal-cyan/10"
          : rank === 1
            ? "border-signal-cyan/30 bg-signal-cyan/5 hover:bg-signal-cyan/10"
            : "border-line bg-base-900/50 hover:bg-base-800/60"
      )}
    >
      <div className="mb-1 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-[10px] font-bold text-ink-faint">#{rank}</span>
          <span className="text-[11px] font-medium text-ink">
            {candidate.vesselName || `MMSI ${candidate.mmsi}`}
          </span>
          {rank === 1 && <Badge tone="cyan">POTENTIAL SOURCE</Badge>}
        </div>
        <span className="font-mono text-[10px] text-ink-faint">{candidate.vesselType}</span>
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px]">
        <div className="flex justify-between">
          <span className="text-ink-faint">Distance</span>
          <span className="font-mono tabular-nums text-ink">{candidate.closestDistanceKm.toFixed(1)} km</span>
        </div>
        <div className="flex justify-between">
          <span className="text-ink-faint">Time diff</span>
          <span className="font-mono tabular-nums text-ink">
            {candidate.closestTimeDifferenceMinutes !== null
              ? `${candidate.closestTimeDifferenceMinutes > 0 ? "+" : ""}${Math.round(candidate.closestTimeDifferenceMinutes)} min`
              : "—"}
          </span>
        </div>
      </div>
      <div className="mt-1.5 flex items-center justify-between">
        <div className="flex items-center gap-1">
          <Shield className="h-2.5 w-2.5 text-signal-cyan/60" />
          <span className="text-[9px] text-ink-faint">Score</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-1 w-12 overflow-hidden rounded-full bg-base-950">
            <div
              className="h-full rounded-full bg-signal-cyan"
              style={{ width: `${scorePercent}%` }}
            />
          </div>
          <span className="font-mono text-[10px] font-bold text-signal-cyan">{scorePercent}%</span>
        </div>
      </div>
    </button>
  );
}

function SpillAgeTimeline({
  sourceEarliest,
  sourceLatest,
  uncertaintyHours,
}: {
  sourceEarliest: string;
  sourceLatest: string;
  uncertaintyHours: number;
}) {
  const earliest = new Date(sourceEarliest);
  const latest = new Date(sourceLatest);
  const detectionTime = new Date(latest.getTime() + uncertaintyHours * 3600000);

  const totalSpan = detectionTime.getTime() - earliest.getTime();
  const earliestPos = 0;
  const latestPos = totalSpan > 0 ? ((latest.getTime() - earliest.getTime()) / totalSpan) * 100 : 50;

  return (
    <div className="mt-3 rounded border border-line bg-base-850 px-3 py-2.5">
      <div className="flex items-center justify-between text-[9px] text-ink-faint">
        <span>SOURCE</span>
        <span>DETECTION</span>
      </div>
      <div className="relative mt-1 h-2 rounded-full bg-base-700">
        <div
          className="absolute h-full rounded-full bg-signal-amber/30"
          style={{ left: `${earliestPos}%`, width: `${latestPos - earliestPos}%` }}
        />
        <div className="absolute -top-0.5 h-3 w-0.5 bg-signal-amber" style={{ left: `${earliestPos}%` }} />
        <div className="absolute -top-0.5 h-3 w-0.5 bg-signal-amber" style={{ left: `${latestPos}%` }} />
      </div>
      <div className="mt-1 flex items-center justify-between text-[8px] text-ink-faint">
        <span>EARLIER</span>
        <span className="text-signal-amber">RELEASE WINDOW</span>
        <span>NOW</span>
      </div>
    </div>
  );
}

export function IncidentDetailsPanel({
  incident,
  onClose,
  compact = false,
}: {
  incident: Incident;
  onClose: () => void;
  compact?: boolean;
}) {
  const queryClient = useQueryClient();
  const { requestFlyTo, openViewer } = useAppStore();

  const [selectedCandidateIdx, setSelectedCandidateIdx] = React.useState<number | null>(null);

  const { data: drift, isLoading: driftLoading, error: driftError } = useQuery({
    queryKey: ["drift", incident.id],
    queryFn: () => getDrift(incident.id),
    staleTime: 5 * 60 * 1000,
  });

  const { data: attribution, isLoading: attributionLoading, error: attributionError } = useQuery({
    queryKey: ["attribution", incident.id],
    queryFn: () => getAttribution(incident.id),
    staleTime: 5 * 60 * 1000,
  });

  const intelligence: DetectionIntelligence | null | undefined = attribution?.intelligence;

  const investigationMutation = useMutation({
    mutationFn: () => runInvestigation(incident.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["drift", incident.id] });
      queryClient.invalidateQueries({ queryKey: ["attribution", incident.id] });
    },
  });

  return (
    <div className="flex h-full flex-col bg-base-900">
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between border-b border-line px-3 py-2.5">
        <div className="flex items-center gap-2">
          <Badge tone={levelTone[incident.level]}>{incident.level}</Badge>
          <span className="font-mono text-xs font-semibold text-ink">{incident.id}</span>
        </div>
        <button
          onClick={onClose}
          className="rounded p-1 text-ink-faint transition-colors hover:bg-base-800 hover:text-ink"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Semantic label */}
      <div className="shrink-0 border-b border-line px-3 py-1.5">
        <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-signal-amber">
          MODEL-DETECTED OIL SPILL — Requires Human Review
        </p>
      </div>

      {/* Quick actions toolbar */}
      <div className="flex shrink-0 items-center gap-1 border-b border-line px-3 py-1.5">
        <Button
          variant="ghost"
          size="sm"
          className="h-6 gap-1 px-2 text-[10px]"
          onClick={() => openViewer(incident.id, "sar")}
        >
          <Satellite className="h-3 w-3" /> View SAR
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 gap-1 px-2 text-[10px]"
          onClick={() => openViewer(incident.id, "overlay")}
        >
          <ImageIcon className="h-3 w-3" /> Prediction
        </Button>
        <Link
          href={`/live?incident=${incident.id}`}
          className="flex h-6 items-center gap-1 rounded px-2 text-[10px] text-ink-faint transition-colors hover:bg-base-800 hover:text-ink"
        >
          <Zap className="h-3 w-3" /> Live Analysis
        </Link>
        <div className="flex-1" />
        <Button
          variant="ghost"
          size="sm"
          className="h-6 gap-1 px-2 text-[10px]"
          onClick={() => exportGeoJSON(incident)}
        >
          <Download className="h-3 w-3" /> GeoJSON
        </Button>
      </div>

      {/* Scrollable sections */}
      <div className="flex-1 overflow-y-auto px-3">
        {/* 01 Detection */}
        <ExpandableSection
          icon={<AlertTriangle className="h-3 w-3 text-signal-cyan/80" />}
          title="01 Detection"
          status="complete"
          statusLabel="MODEL DETECTION"
          defaultOpen
        >
          <div className="space-y-0.5">
            <MetaRow label="Confidence" value={formatPercent(incident.confidence)} />
            <MetaRow label="Area" value={formatArea(incident.areaKm2)} />
            <MetaRow label="Perimeter" value={`${incident.perimeterKm2.toFixed(1)} km`} />
            <MetaRow
              label="Centroid"
              value={`${incident.centroid.lat.toFixed(4)}N, ${incident.centroid.lon.toFixed(4)}E`}
            />
            <MetaRow label="Location" value={incident.locationDescription} mono={false} />
            <MetaRow label="Detected" value={formatISTTime(incident.detectedAt)} />
            {incident.estimatedVolumeTons !== null && (
              <MetaRow label="Est. Volume" value={`${incident.estimatedVolumeTons} tons (approx.)`} />
            )}
            <p className="pt-1 text-[9px] italic text-ink-faint/70">
              Model-generated detection — requires human review before any enforcement action.
            </p>
          </div>
        </ExpandableSection>

        {/* 02 Acquisition */}
        <ExpandableSection
          icon={<Satellite className="h-3 w-3 text-signal-cyan/80" />}
          title="02 Acquisition"
          status="complete"
          statusLabel="ACQUIRED"
        >
          <div className="space-y-0.5">
            <MetaRow label="Satellite" value={incident.satellite} />
            <MetaRow label="Scene ID" value={incident.sceneId} />
            <MetaRow label="Acquired" value={formatISTTime(incident.detectedAt)} />
          </div>
        </ExpandableSection>

        {/* 03 Processing */}
        <ExpandableSection
          icon={<Cpu className="h-3 w-3 text-signal-cyan/80" />}
          title="03 Processing"
          status="complete"
          statusLabel="PROCESSED"
        >
          <div className="space-y-0.5">
            <MetaRow label="Model" value={`${incident.model} ${incident.modelVersion}`} />
            <MetaRow label="Status" value={<Badge tone="green">{incident.status.toUpperCase()}</Badge>} />
          </div>
        </ExpandableSection>

        {/* 04 Estimated Spill Age */}
        <ExpandableSection
          icon={<Clock className="h-3 w-3 text-signal-cyan/80" />}
          title="04 Estimated Spill Age"
          status={drift ? "complete" : driftLoading ? "running" : "unavailable"}
          statusLabel={drift ? "ESTIMATED" : driftLoading ? "COMPUTING" : "UNAVAILABLE"}
        >
          {driftLoading ? (
            <div className="flex items-center gap-2 py-2 text-[11px] text-ink-faint">
              <Loader2 className="h-3 w-3 animate-spin text-signal-cyan" />
              Running drift model…
            </div>
          ) : drift ? (
            <div>
              <MetaRow
                label="Release Age"
                value={`${drift.uncertaintyHours.toFixed(1)}h ± ${drift.uncertaintyHours.toFixed(1)}h`}
              />
              <SpillAgeTimeline
                sourceEarliest={drift.sourceEarliest}
                sourceLatest={drift.sourceLatest}
                uncertaintyHours={drift.uncertaintyHours}
              />
              <MetaRow
                label="Release Window"
                value={`${formatISTTimeShort(drift.sourceEarliest)} — ${formatISTTimeShort(drift.sourceLatest)}`}
              />
              <MetaRow label="Basis" value="Drift back-projection model" />
              <p className="pt-1 text-[9px] italic text-ink-faint/70">
                Approximate estimate — not a direct measurement of oil weathering or drift.
              </p>
            </div>
          ) : (
            <p className="text-[11px] text-ink-faint/80">Drift data unavailable for this detection.</p>
          )}
        </ExpandableSection>

        {/* 05 Environment */}
        <ExpandableSection
          icon={<Waves className="h-3 w-3 text-signal-cyan/80" />}
          title="05 Environment"
          status="available"
          statusLabel="DEMO"
        >
          <div className="space-y-0.5">
            <MetaRow label="Wind" value={`${incident.windSpeedKts} kts`} />
            <MetaRow label="Region" value={incident.region} />
            <p className="pt-1 text-[9px] italic text-ink-faint/70">
              DEMO — environmental data is simulated for prototype demonstration.
            </p>
          </div>
        </ExpandableSection>

        {/* 06 Drift / Source */}
        <ExpandableSection
          icon={<Wind className="h-3 w-3 text-signal-cyan/80" />}
          title="06 Drift / Source"
          status={drift ? "complete" : driftLoading ? "running" : "unavailable"}
          statusLabel={drift ? "COMPLETE" : driftLoading ? "RUNNING" : "UNAVAILABLE"}
        >
          {driftLoading ? (
            <div className="flex items-center gap-2 py-2 text-[11px] text-ink-faint">
              <Loader2 className="h-3 w-3 animate-spin text-signal-cyan" />
              Computing drift trajectory…
            </div>
          ) : driftError ? (
            <p className="text-[11px] text-signal-red">Failed to load drift data.</p>
          ) : drift ? (
            <div className="space-y-0.5">
              <MetaRow label="Method" value={drift.method} />
              <MetaRow
                label="Source Coords"
                value={`${drift.sourceLatitude.toFixed(4)}N, ${drift.sourceLongitude.toFixed(4)}E`}
              />
              <MetaRow label="Uncertainty" value={`${drift.uncertaintyKm.toFixed(1)} km`} />
              <MetaRow label="Confidence" value={formatPercent(drift.confidence)} />
              <MetaRow label="Ensemble" value={`${drift.ensembleSize} runs`} />
              {drift.qualityFlags.length > 0 && (
                <MetaRow
                  label="Quality Flags"
                  value={drift.qualityFlags.join(", ")}
                  mono={false}
                />
              )}
              <p className="pt-1 text-[9px] italic text-ink-faint/70">
                Not a confirmed origin point — requires field verification.
              </p>
            </div>
          ) : (
            <p className="text-[11px] text-ink-faint/80">No drift analysis available.</p>
          )}
        </ExpandableSection>

        {/* 07 AIS Correlation */}
        <ExpandableSection
          icon={<Anchor className="h-3 w-3 text-signal-cyan/80" />}
          title="07 AIS Correlation"
          status={attribution ? "complete" : attributionLoading ? "running" : "unavailable"}
          statusLabel={attribution ? "COMPLETE" : attributionLoading ? "RUNNING" : "UNAVAILABLE"}
        >
          {attributionLoading ? (
            <div className="flex items-center gap-2 py-2 text-[11px] text-ink-faint">
              <Loader2 className="h-3 w-3 animate-spin text-signal-cyan" />
              Correlating AIS tracks…
            </div>
          ) : attributionError ? (
            <p className="text-[11px] text-signal-red">Failed to load AIS data.</p>
          ) : attribution ? (
            <div className="space-y-1.5">
              <MetaRow label="Provider" value={attribution.provider} />
              <MetaRow label="Candidates Found" value={attribution.candidateCount} />
              <MetaRow label="Coverage" value={attribution.coverageKnown ? "Known" : "Partial"} />
              <Button
                variant="outline"
                size="sm"
                className="mt-1 w-full gap-1 text-[10px]"
                disabled={investigationMutation.isPending}
                onClick={() => investigationMutation.mutate()}
              >
                {investigationMutation.isPending ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Play className="h-3 w-3" />
                )}
                {investigationMutation.isPending ? "Running…" : "Run Investigation"}
              </Button>
            </div>
          ) : (
            <p className="text-[11px] text-ink-faint/80">No AIS correlation data available.</p>
          )}
        </ExpandableSection>

        {/* 08 Candidate Vessels */}
        <ExpandableSection
          icon={<Anchor className="h-3 w-3 text-signal-cyan/80" />}
          title="08 Candidate Vessels"
          status={attribution && attribution.candidates.length > 0 ? "complete" : "unavailable"}
          statusLabel={attribution && attribution.candidates.length > 0 ? `${attribution.candidates.length} FOUND` : "UNAVAILABLE"}
        >
          {attribution && attribution.candidates.length > 0 ? (
            <div className="max-h-[180px] space-y-1.5 overflow-y-auto">
              {attribution.candidates.slice(0, 5).map((c, idx) => (
                <CandidateCardCompact
                  key={c.mmsi}
                  candidate={c}
                  rank={idx + 1}
                  isSelected={selectedCandidateIdx === idx}
                  onSelect={() => {
                    setSelectedCandidateIdx(idx === selectedCandidateIdx ? null : idx);
                    if (c.closestTimestamp) {
                      const offsetLat = (idx + 1) * 0.01;
                      const offsetLon = (idx + 1) * 0.015;
                      requestFlyTo(
                        incident.centroid.lon + offsetLon,
                        incident.centroid.lat + offsetLat,
                        8
                      );
                    }
                  }}
                />
              ))}
            </div>
          ) : (
            <p className="text-[11px] text-ink-faint/80">No candidate vessels identified.</p>
          )}
        </ExpandableSection>

        {/* 09 Uncertainty / Intelligence */}
        {intelligence && (
          <ExpandableSection
            icon={<Brain className="h-3 w-3 text-signal-cyan/80" />}
            title="09 Uncertainty / Intelligence"
            status="available"
            statusLabel="AVAILABLE"
          >
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-ink-faint">Raw Model Confidence</span>
                <span className="font-mono text-ink">{formatPercent(intelligence.confidenceBreakdown.rawModelConfidence)}</span>
              </div>
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-ink-faint">Adjusted Confidence</span>
                <span className={cn("font-mono font-bold",
                  intelligence.confidenceBreakdown.confidenceBand === "HIGH" ? "text-signal-green" :
                  intelligence.confidenceBreakdown.confidenceBand === "MEDIUM" ? "text-signal-cyan" : "text-signal-amber"
                )}>
                  {formatPercent(intelligence.confidenceBreakdown.adjustedConfidence)}
                </span>
              </div>
              <div className="flex items-center justify-between text-[10px]">
                <span className="flex items-center gap-1 text-ink-faint"><Eye className="h-2.5 w-2.5" /> Look-Alike</span>
                <Badge tone="neutral">{intelligence.lookAlikeScreening.status}</Badge>
              </div>
              <div className="flex items-center justify-between text-[10px]">
                <span className="flex items-center gap-1 text-ink-faint"><Wind className="h-2.5 w-2.5" /> Environmental</span>
                <Badge tone={intelligence.environmentalReliability.band === "IDEAL" ? "cyan" : "neutral"}>{intelligence.environmentalReliability.band}</Badge>
              </div>
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-ink-faint">Calibration</span>
                <Badge tone="low">{intelligence.calibration.status}</Badge>
              </div>
              <div className="flex items-center justify-between text-[10px]">
                <span className="flex items-center gap-1 text-ink-faint"><Calendar className="h-2.5 w-2.5" /> Seasonal Prior</span>
                <Badge tone="neutral">{intelligence.seasonalPrior.status}</Badge>
              </div>
              <p className="pt-1 text-[9px] italic text-ink-faint/70">
                Heuristic evidence, not a definitive classification.
              </p>
            </div>
          </ExpandableSection>
        )}

        {/* 10 Recommended Actions */}
        <ExpandableSection
          icon={<AlertTriangle className="h-3 w-3 text-signal-cyan/80" />}
          title="10 Recommended Actions"
          status="available"
          statusLabel="REVIEW"
        >
          <div className="space-y-1.5 text-[10px] text-ink-dim">
            <p>• Verify SAR detection against optical imagery if available</p>
            <p>• Review candidate vessel tracks manually</p>
            <p>• Check drift model against real environmental data</p>
            <p>• Cross-reference with regional shipping lanes</p>
            <p className="pt-1 text-[9px] italic text-ink-faint/70">
              Human review required before any enforcement action.
            </p>
          </div>
        </ExpandableSection>
      </div>

      {/* Bottom action buttons */}
      {!compact && (
        <div className="shrink-0 space-y-1.5 border-t border-line p-3">
          <Button
            variant="default"
            className="w-full justify-start"
            onClick={() => openViewer(incident.id, "sar")}
          >
            <Satellite className="h-3.5 w-3.5" /> View Satellite Scene
          </Button>
          <Button
            variant="outline"
            className="w-full justify-start"
            onClick={() => openViewer(incident.id, "overlay")}
          >
            <ImageIcon className="h-3.5 w-3.5" /> View Prediction Overlay
          </Button>
          <Button
            variant="ghost"
            className="w-full justify-start"
            onClick={() => exportGeoJSON(incident)}
          >
            <Download className="h-3.5 w-3.5" /> Export GeoJSON
          </Button>
        </div>
      )}
    </div>
  );
}

export function EmptyDetailsPanel() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
      <Satellite className="h-6 w-6 text-line-bright" />
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-faint">
        No Incident Selected
      </p>
      <p className="max-w-[220px] text-xs leading-relaxed text-ink-faint/80">
        Select a detection from the feed or click a spill polygon on the map to investigate.
      </p>
    </div>
  );
}
