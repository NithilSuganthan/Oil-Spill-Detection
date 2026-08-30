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
} from "lucide-react";
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

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="mb-1.5 flex items-center gap-1.5 border-t border-line pt-3">
        {icon}
        <h4 className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-signal-cyan/90">
          {title}
        </h4>
      </div>
      {children}
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

export function IncidentDetailsPanel({
  incident,
  onClose,
  compact = false,
}: {
  incident: Incident | null;
  onClose?: () => void;
  compact?: boolean;
}) {
  const openViewer = useAppStore((s) => s.openViewer);
  const requestFlyTo = useAppStore((s) => s.requestFlyTo);
  const queryClient = useQueryClient();
  const [selectedCandidateIdx, setSelectedCandidateIdx] = React.useState<number | null>(null);

  // Fetch AIS attribution when incident changes
  const {
    data: attribution,
    isLoading: attributionLoading,
    isError: attributionError,
  } = useQuery({
    queryKey: ["attribution", incident?.id],
    queryFn: () => getAttribution(incident!.id),
    enabled: !!incident?.id,
    retry: false,
    staleTime: 60_000,
  });

  // Fetch drift analysis when incident changes
  const {
    data: drift,
    isLoading: driftLoading,
    isError: driftError,
  } = useQuery({
    queryKey: ["drift", incident?.id],
    queryFn: () => getDrift(incident!.id),
    enabled: !!incident?.id,
    retry: false,
    staleTime: 60_000,
  });

  // Intelligence is embedded in attribution response
  const intelligence = attribution?.intelligence as DetectionIntelligence | undefined;

  // Run investigation mutation
  const runInvestigationMutation = useMutation({
    mutationFn: () => runInvestigation(incident!.id),
    onSuccess: (result) => {
      // Refetch attribution to update the panel
      queryClient.invalidateQueries({ queryKey: ["attribution", incident?.id] });
    },
  });

  // Reset selection when incident changes
  React.useEffect(() => {
    setSelectedCandidateIdx(null);
  }, [incident?.id]);

  if (!incident) return null;

  return (
    <div className={cn("flex h-full min-h-0 flex-col animate-slide-in-right")}>
      <div className="panel-header shrink-0">
        <span className="panel-title">Incident Details</span>
        {onClose && (
          <button
            aria-label="Close details panel"
            onClick={onClose}
            className="focus-ring rounded p-1 text-ink-faint hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="min-h-0 flex-1 space-y-1 overflow-y-auto px-3 py-2.5">
        <div className="flex items-center justify-between pb-1">
          <h3 className="font-mono text-base font-bold tracking-wide text-ink">{incident.id}</h3>
          <Badge tone={levelTone[incident.level]}>{incident.level} CONFIDENCE</Badge>
        </div>

        <Section icon={<MapPin className="h-3 w-3 text-signal-cyan/80" />} title="Detection">
          <MetaRow label="Confidence" value={<span className="text-signal-cyan">{formatPercent(incident.confidence)}</span>} />
          <MetaRow label="Area" value={`${formatArea(incident.areaKm2)} km²`} />
          <MetaRow label="Perimeter" value={`${incident.perimeterKm2.toFixed(1)} km`} />
          <MetaRow
            label="Centroid"
            value={
              <>
                {incident.centroid.lat.toFixed(4)}° N<br />
                {incident.centroid.lon.toFixed(4)}° E
              </>
            }
          />
          <MetaRow label="Location" value={incident.locationDescription} mono={false} />
          <MetaRow label="Detected" value={formatISTTime(incident.detectedAt)} />
          {incident.estimatedVolumeTons !== null && (
            <MetaRow label="Est. Volume" value={`~${incident.estimatedVolumeTons} t (rough)`} />
          )}
        </Section>

        <Section icon={<Satellite className="h-3 w-3 text-signal-cyan/80" />} title="Acquisition">
          <MetaRow label="Satellite" value={incident.satellite} />
          <MetaRow label="Scene ID" value={<span className="break-all">{incident.sceneId}</span>} />
          <MetaRow label="Acquired" value={`${formatISTDate(incident.detectedAt)} ${formatISTTimeShort(incident.detectedAt)} IST`} />
        </Section>

        <Section icon={<Cpu className="h-3 w-3 text-signal-cyan/80" />} title="Processing">
          <MetaRow label="Processed" value={`${formatISTDate(incident.detectedAt)} · +6 min`} />
          <MetaRow label="Model" value={`${incident.model} ${incident.modelVersion}`} />
          <MetaRow
            label="Status"
            value={
              <span
                className={cn(
                  incident.status === "completed"
                    ? "text-signal-green"
                    : incident.status === "processing"
                      ? "text-signal-amber"
                      : "text-signal-orange"
                )}
              >
                {incident.status === "completed"
                  ? "Completed"
                  : incident.status === "processing"
                    ? "Processing"
                    : "Under Review"}
              </span>
            }
          />
        </Section>

        {/* DETECTION INTELLIGENCE */}
        {intelligence && (
          <Section icon={<Brain className="h-3 w-3 text-signal-cyan/80" />} title="Detection Intelligence">
            {/* Confidence Breakdown */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-ink-faint">Raw Model Confidence</span>
                <span className="font-mono text-ink">{formatPercent(intelligence.confidenceBreakdown.rawModelConfidence)}</span>
              </div>
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-ink-faint">Adjusted Confidence</span>
                <span className={cn(
                  "font-mono font-bold",
                  intelligence.confidenceBreakdown.confidenceBand === "HIGH" ? "text-signal-green" :
                  intelligence.confidenceBreakdown.confidenceBand === "MEDIUM" ? "text-signal-cyan" :
                  "text-signal-amber"
                )}>
                  {formatPercent(intelligence.confidenceBreakdown.adjustedConfidence)}
                  <span className="ml-1 text-[8px] font-normal text-ink-faint">
                    ({intelligence.confidenceBreakdown.confidenceBand})
                  </span>
                </span>
              </div>
              <div className="border-t border-line" />

              {/* Look-Alike Screening */}
              <div className="flex items-center justify-between text-[10px]">
                <span className="flex items-center gap-1 text-ink-faint">
                  <Eye className="h-2.5 w-2.5" />
                  Look-Alike Screening
                  <Badge tone="neutral">{intelligence.lookAlikeScreening.status}</Badge>
                </span>
                <span className="font-mono text-ink">
                  P={formatPercent(intelligence.lookAlikeScreening.pLookLike)}
                  {intelligence.lookAlikeScreening.penalty > 0 && (
                    <span className="text-signal-amber"> (-{formatPercent(intelligence.lookAlikeScreening.penalty)})</span>
                  )}
                </span>
              </div>
              {intelligence.lookAlikeScreening.textureStatus === "UNAVAILABLE" && (
                <div className="text-[9px] text-ink-faint/60 pl-4">
                  Texture features: UNAVAILABLE (not extracted from SAR patch)
                </div>
              )}

              {/* Environmental Reliability */}
              <div className="flex items-center justify-between text-[10px]">
                <span className="flex items-center gap-1 text-ink-faint">
                  <Wind className="h-2.5 w-2.5" />
                  Environmental
                  <Badge tone={
                    intelligence.environmentalReliability.band === "IDEAL" ? "cyan" :
                    intelligence.environmentalReliability.band === "GOOD" ? "neutral" :
                    "low"
                  }>
                    {intelligence.environmentalReliability.band}
                  </Badge>
                </span>
                <span className="font-mono text-ink">
                  {intelligence.environmentalReliability.windSpeedKnots.toFixed(0)} kts
                  {intelligence.environmentalReliability.penalty > 0 && (
                    <span className="text-signal-amber"> (-{formatPercent(intelligence.environmentalReliability.penalty)})</span>
                  )}
                </span>
              </div>

              {/* Calibration Status */}
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-ink-faint">Calibration</span>
                <Badge tone="low">{intelligence.calibration.status}</Badge>
              </div>

              {/* Seasonal Prior */}
              <div className="flex items-center justify-between text-[10px]">
                <span className="flex items-center gap-1 text-ink-faint">
                  <Calendar className="h-2.5 w-2.5" />
                  Seasonal Prior
                  <Badge tone="neutral">{intelligence.seasonalPrior.status}</Badge>
                </span>
                <span className="font-mono text-ink">
                  {intelligence.seasonalPrior.adjustment > 0 ? "+" : ""}
                  {formatPercent(intelligence.seasonalPrior.adjustment)}
                </span>
              </div>

              {/* AIS Gap Status */}
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-ink-faint">AIS Gap Analysis</span>
                <Badge tone="low">{intelligence.aisGap.status}</Badge>
              </div>

              <p className="text-[9px] italic text-ink-faint/70 pt-1">
                Detection intelligence is heuristic evidence, not a definitive classification.
                Adjusted confidence = raw confidence minus heuristic penalties.
              </p>
            </div>
          </Section>
        )}

        {/* AIS VESSEL CORRELATION */}
        <Section icon={<Anchor className="h-3 w-3 text-signal-cyan/80" />} title="AIS / Vessel Correlation">
          {attributionLoading ? (
            <div className="flex items-center gap-2 py-2 text-[11px] text-ink-faint">
              <Loader2 className="h-3 w-3 animate-spin text-signal-cyan/60" />
              Loading AIS data…
            </div>
          ) : attributionError ? (
            <div className="flex items-start gap-2 rounded border border-signal-amber/30 bg-signal-amber/5 px-2.5 py-2 text-[11px] text-signal-amber">
              <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
              AIS data unavailable for this time window.
            </div>
          ) : attribution && attribution.candidateCount > 0 ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-[10px] text-ink-faint">
                <span>
                  Provider:{" "}
                  <span className="text-ink">
                    {attribution.provider === "gfw" ? "Global Fishing Watch" : "DEMO AIS"}
                  </span>
                </span>
                <span>{attribution.candidateCount} vessels</span>
              </div>
              <div className="flex items-center justify-between text-[10px] text-ink-faint">
                <span>
                  Observed:{" "}
                  <span className="font-mono text-ink">{attribution.totalObservations}</span>
                </span>
                {attribution.candidates.length > 0 && (
                  <span>
                    Top score:{" "}
                    <span className="font-mono text-signal-cyan">
                      {Math.round(attribution.candidates[0].attributionScore * 100)}%
                    </span>
                  </span>
                )}
              </div>
              <div className="border-t border-line" />
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
                        // Fly to vessel observation area (offset from incident centroid)
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
              <p className="text-[9px] italic text-ink-faint/70">
                Potential Source Vessel — Human review required. AIS proximity alone does not establish causation.
              </p>
            </div>
          ) : attribution && attribution.candidateCount === 0 ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-[10px] text-ink-faint">
                <span>
                  Provider:{" "}
                  <span className="text-ink">
                    {attribution.provider === "gfw" ? "Global Fishing Watch" : "DEMO AIS"}
                  </span>
                </span>
                <span>0 candidates</span>
              </div>
              <p className="text-[11px] text-ink-faint/80">
                AIS data was available but no vessels were observed in the search window.
              </p>
            </div>
          ) : (
            <div className="space-y-2.5">
              <p className="text-[11px] text-ink-faint">
                AIS Correlation — Not analyzed
              </p>
              <Button
                variant="default"
                size="sm"
                className="w-full justify-start"
                disabled={runInvestigationMutation.isPending}
                onClick={() => runInvestigationMutation.mutate()}
              >
                {runInvestigationMutation.isPending ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" /> Running Investigation…
                  </>
                ) : (
                  <>
                    <Play className="h-3.5 w-3.5" /> Run Investigation
                  </>
                )}
              </Button>
              {runInvestigationMutation.isError && (
                <p className="text-[10px] text-signal-red">
                  Investigation failed. Backend may not be running.
                </p>
              )}
            </div>
          )}
        </Section>

        {/* DRIFT / SOURCE ESTIMATE */}
        <Section icon={<Waves className="h-3 w-3 text-signal-cyan/80" />} title="Drift / Source Estimate">
          {driftLoading ? (
            <div className="flex items-center gap-2 py-2 text-[11px] text-ink-faint">
              <Loader2 className="h-3 w-3 animate-spin text-signal-cyan/60" />
              Loading drift data…
            </div>
          ) : driftError ? (
            <div className="flex items-start gap-2 rounded border border-signal-amber/30 bg-signal-amber/5 px-2.5 py-2 text-[11px] text-signal-amber">
              <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
              Drift analysis unavailable.
            </div>
          ) : drift ? (
            <div className="space-y-2">
              {drift.provenance?.environmental_provider === "real" ? (
                <div className="rounded border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1.5 text-[10px] text-emerald-300">
                  REAL ENVIRONMENTAL FORCING — CMEMS + ERA5
                </div>
              ) : drift.qualityFlags.includes("DEMO_ENVIRONMENTAL_FORCING") ? (
                <div className="rounded border border-amber-500/40 bg-amber-500/10 px-2.5 py-1.5 text-[10px] text-amber-300">
                  DEMO — simulated environmental forcing
                </div>
              ) : null}
              <div className="flex items-center justify-between text-[10px] text-ink-faint">
                <span>Method</span>
                <span className="font-mono text-ink">{drift.method.replace(/_/g, " ")}</span>
              </div>
              <div className="flex items-center justify-between text-[10px] text-ink-faint">
                <span>Source</span>
                <span className="font-mono text-ink">
                  {drift.sourceLatitude.toFixed(4)}°N, {drift.sourceLongitude.toFixed(4)}°E
                </span>
              </div>
              <div className="flex items-center justify-between text-[10px] text-ink-faint">
                <span>Uncertainty</span>
                <span className="font-mono text-ink">
                  ±{drift.uncertaintyKm.toFixed(1)} km / ±{drift.uncertaintyHours.toFixed(1)} h
                </span>
              </div>
              <div className="flex items-center justify-between text-[10px] text-ink-faint">
                <span>Confidence</span>
                <span className="font-mono text-signal-cyan">{formatPercent(drift.confidence)}</span>
              </div>
              <div className="flex items-center justify-between text-[10px] text-ink-faint">
                <span>Ensemble</span>
                <span className="font-mono text-ink">{drift.ensembleSize} particles</span>
              </div>
              {drift.qualityFlags.length > 0 && (
                <div className="flex flex-wrap gap-1 pt-0.5">
                  {drift.qualityFlags.map((flag) => (
                    <Badge
                      key={flag}
                      tone={
                        flag === "DEMO_ENVIRONMENTAL_FORCING"
                          ? "low"
                          : flag === "REAL_ENVIRONMENTAL_FORCING"
                            ? "cyan"
                            : "neutral"
                      }
                    >
                      {flag}
                    </Badge>
                  ))}
                </div>
              )}
              <p className="text-[9px] italic text-ink-faint/70">
                Source location is an estimate. Not a confirmed origin point.
              </p>
            </div>
          ) : (
            <p className="text-[11px] text-ink-faint/80">
              Drift analysis not available for this incident.
            </p>
          )}
        </Section>
      </div>

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
