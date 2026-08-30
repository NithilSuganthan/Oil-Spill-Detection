import Link from "next/link";
import { notFound } from "next/navigation";
import {
  Anchor,
  ArrowLeft,
  Clock,
  Cpu,
  MapPin,
  Route,
  Satellite,
  Shield,
  Waves,
  Navigation,
} from "lucide-react";
import { getIncident, getScene, getAttribution, getDrift } from "@/lib/api/client";
import { PageShell } from "@/components/layout/page-shell";
import { MapView } from "@/components/map/map-view-client";
import { Badge, levelTone } from "@/components/ui/badge";
import { formatArea, formatISTDate, formatISTTime, formatPercent } from "@/lib/utils";
import type { AttributionResult, CandidateVessel, DriftResult } from "@/lib/types";

/**
 * Rendered on demand so the page works in BOTH API modes:
 *  - mock mode: data comes from local mock data at request time
 *  - real mode: data comes from FastAPI at request time
 *    (a statically prerendered page would otherwise require the backend
 *     during `next build`)
 */
export const dynamic = "force-dynamic";

function Meta({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <span className="shrink-0 font-mono text-[10px] uppercase tracking-widest text-ink-faint">
        {label}
      </span>
      <span className="text-right font-mono text-xs tabular-nums text-ink">{value}</span>
    </div>
  );
}

const TIMELINE_STEPS = [
  { title: "SAR Acquisition", desc: "Sentinel-1 pass over focus region", offsetMin: -11 },
  { title: "Preprocessing", desc: "Radiometric calibration · speckle filtering", offsetMin: -6 },
  { title: "Model Inference", desc: "OilSpillNet v1.0 segmentation", offsetMin: -4 },
  { title: "Detection Registered", desc: "Polygon extracted and stored", offsetMin: 0 },
];

export default async function IncidentDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const incident = await getIncident(decodeURIComponent(params.id));
  if (!incident) notFound();

  const scene = await getScene(incident.sceneId);
  const detected = new Date(incident.detectedAt).getTime();
  let attribution: AttributionResult | null = null;
  let drift: DriftResult | null = null;
  try {
    attribution = await getAttribution(incident.id);
  } catch {
    // Attribution may not be available yet
  }
  try {
    drift = await getDrift(incident.id);
  } catch {
    // Drift may not be available yet
  }

  return (
    <PageShell maxWidth="max-w-[1500px]">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link
            href="/incidents"
            className="focus-ring rounded border border-line p-2 text-ink-dim hover:border-line-bright hover:text-ink"
            aria-label="Back to incidents"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="font-mono text-lg font-bold tracking-wider text-ink">{incident.id}</h1>
              <Badge tone={levelTone[incident.level]}>{incident.level} CONFIDENCE</Badge>
              <Badge tone={incident.status === "completed" ? "green" : "medium"}>
                {incident.status}
              </Badge>
            </div>
            <p className="mt-0.5 text-xs text-ink-faint">{incident.locationDescription}</p>
          </div>
        </div>
        <span className="font-mono text-xs tabular-nums text-ink-dim">
          Detected {formatISTDate(incident.detectedAt)} · {formatISTTime(incident.detectedAt)}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[340px_1fr] xl:grid-cols-[340px_1fr_320px]">
        {/* LEFT — metadata */}
        <div className="space-y-4">
          <section className="panel p-4">
            <h2 className="panel-title mb-2 flex items-center gap-1.5">
              <MapPin className="h-3.5 w-3.5 text-signal-cyan/80" /> Detection Geometry
            </h2>
            <Meta label="Confidence" value={<span className="text-signal-cyan">{formatPercent(incident.confidence)}</span>} />
            <Meta label="Area" value={`${formatArea(incident.areaKm2)} km²`} />
            <Meta label="Perimeter" value={`${incident.perimeterKm2.toFixed(1)} km`} />
            <Meta label="Centroid" value={`${incident.centroid.lat.toFixed(4)}° N, ${incident.centroid.lon.toFixed(4)}° E`} />
            <Meta label="Wind" value={`${incident.windSpeedKts} kts`} />
            {incident.estimatedVolumeTons !== null && (
              <Meta label="Est. Volume" value={`~${incident.estimatedVolumeTons} t (rough)`} />
            )}
          </section>

          <section className="panel p-4">
            <h2 className="panel-title mb-2 flex items-center gap-1.5">
              <Satellite className="h-3.5 w-3.5 text-signal-cyan/80" /> Satellite Scene
            </h2>
            <Meta label="Platform" value={scene?.platform ?? incident.satellite} />
            <Meta label="Sensor" value={scene?.sensor ?? "SAR C-band"} />
            <Meta label="Mode" value={scene ? `${scene.acquisitionMode} · ${scene.polarisation}` : "—"} />
            <Meta label="Scene ID" value={<span className="break-all">{incident.sceneId}</span>} />
            <Meta
              label="Acquired"
              value={scene ? `${formatISTDate(scene.acquiredAt)} ${formatISTTime(scene.acquiredAt)}` : "—"}
            />
          </section>

          <section className="panel p-4">
            <h2 className="panel-title mb-2 flex items-center gap-1.5">
              <Cpu className="h-3.5 w-3.5 text-signal-cyan/80" /> Model Information
            </h2>
            <Meta label="Model" value={`${incident.model} ${incident.modelVersion}`} />
            <Meta label="Task" value="Slick segmentation (binary + scoring)" />
            <Meta label="Input" value="Sentinel-1 GRD · VV/VH" />
            <Meta label="Post-processing" value="Look-alike rejection · polygon extraction" />
          </section>

          {/* VESSEL CORRELATION */}
          <section className="panel p-4">
            <h2 className="panel-title mb-2 flex items-center gap-1.5">
              <Anchor className="h-3.5 w-3.5 text-signal-cyan/80" /> Vessel Correlation
            </h2>
            {attribution && attribution.candidateCount > 0 ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-[11px] text-ink-faint">
                  <span>AIS Source: <span className="text-ink">{attribution.provider === "gfw" ? "Global Fishing Watch" : "DEMO AIS"}</span></span>
                  <span>Search radius: {attribution.searchWindow.radiusKm} km</span>
                </div>
                <div className="flex items-center justify-between text-[11px] text-ink-faint">
                  <span>Time window: ±{attribution.searchWindow.timeWindowHours}h</span>
                  <span>Candidates: {attribution.candidateCount}</span>
                </div>
                <div className="border-t border-line" />
                {attribution.candidates.slice(0, 5).map((c, idx) => (
                  <CandidateCard key={c.mmsi} candidate={c} rank={idx + 1} />
                ))}
              </div>
            ) : (
              <p className="text-[11px] leading-relaxed text-ink-faint/80">
                No vessel correlation data available. Run AIS analysis from the API
                (POST /attribution/analyze) to populate this section.
              </p>
            )}
          </section>

          {/* DRIFT / SOURCE ESTIMATE */}
          <section className="panel p-4">
            <h2 className="panel-title mb-2 flex items-center gap-1.5">
              <Waves className="h-3.5 w-3.5 text-signal-cyan/80" /> Drift / Source Estimate
            </h2>
            {drift ? (
              <div className="space-y-3">
                {drift.provenance?.environmental_provider === "real" ? (
                  <div className="rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-[11px] text-emerald-300">
                    REAL ENVIRONMENTAL FORCING — CMEMS GLOBCurrents + ERA5 winds.
                  </div>
                ) : drift.qualityFlags.includes("DEMO_ENVIRONMENTAL_FORCING") ? (
                  <div className="rounded border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-300">
                    DEMO data — using simulated environmental forcing. Not for operational use.
                  </div>
                ) : null}
                <div className="flex items-center justify-between text-[11px] text-ink-faint">
                  <span>Method</span>
                  <span className="font-mono text-ink">{drift.method.replace(/_/g, " ")}</span>
                </div>
                <div className="flex items-center justify-between text-[11px] text-ink-faint">
                  <span>Estimated Source</span>
                  <span className="font-mono text-ink">
                    {drift.sourceLatitude.toFixed(4)}°N, {drift.sourceLongitude.toFixed(4)}°E
                  </span>
                </div>
                <div className="flex items-center justify-between text-[11px] text-ink-faint">
                  <span>Slick Observed At</span>
                  <span className="font-mono text-ink">
                    {formatISTDate(drift.observationTime)} {formatISTTime(drift.observationTime)}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[11px] text-ink-faint">
                  <span>Source Time Window</span>
                  <span className="font-mono text-ink">
                    {formatISTDate(drift.sourceEarliest)} {formatISTTime(drift.sourceEarliest)} — {formatISTTime(drift.sourceLatest)}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[11px] text-ink-faint">
                  <span>Uncertainty</span>
                  <span className="font-mono text-ink">
                    ±{drift.uncertaintyKm.toFixed(1)} km / ±{drift.uncertaintyHours.toFixed(1)} h
                  </span>
                </div>
                <div className="flex items-center justify-between text-[11px] text-ink-faint">
                  <span>Confidence</span>
                  <span className="font-mono text-signal-cyan">{formatPercent(drift.confidence)}</span>
                </div>
                <div className="flex items-center justify-between text-[11px] text-ink-faint">
                  <span>Ensemble Size</span>
                  <span className="font-mono text-ink">{drift.ensembleSize} particles</span>
                </div>
                {drift.qualityFlags.length > 0 && (
                  <>
                    <div className="border-t border-line" />
                    <div className="flex items-start justify-between gap-2 text-[11px]">
                      <span className="shrink-0 text-ink-faint">Quality Flags</span>
                      <div className="flex flex-wrap justify-end gap-1">
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
                    </div>
                  </>
                )}
                <p className="text-[10px] italic text-ink-faint/70">
                  Source location is an estimate based on backward drift modelling. Not a confirmed origin point.
                </p>
              </div>
            ) : (
              <p className="text-[11px] leading-relaxed text-ink-faint/80">
                Drift analysis not available. Run investigation from the API
                (POST /investigation/{incident.id}/run) to populate this section.
              </p>
            )}
          </section>

          {/* FUTURE MODULE PLACEHOLDERS */}
        </div>

        {/* CENTER — map */}
        <div className="panel min-h-[420px] overflow-hidden">
          <MapView
            incidents={[incident]}
            scenes={scene ? [scene] : []}
            drift={drift}
            className="h-full min-h-[420px]"
          />
        </div>

        {/* RIGHT — timeline */}
        <div className="space-y-4">
          <section className="panel p-4">
            <h2 className="panel-title mb-3 flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-signal-cyan/80" /> Processing Timeline
            </h2>
            <ol className="relative space-y-4 border-l border-line pl-4">
              {TIMELINE_STEPS.map((step) => {
                const at = new Date(detected + step.offsetMin * 60000);
                return (
                  <li key={step.title} className="relative">
                    <span className="absolute -left-[21px] top-1 h-2 w-2 rounded-full border border-signal-cyan/70 bg-base-950" />
                    <p className="text-xs font-medium text-ink">{step.title}</p>
                    <p className="text-[11px] text-ink-faint">{step.desc}</p>
                    <p className="font-mono text-[10px] tabular-nums text-signal-cyan/80">
                      {formatISTTime(at.toISOString())} IST
                    </p>
                  </li>
                );
              })}
            </ol>
          </section>

          <section className="panel p-4">
            <h2 className="panel-title mb-2">Prediction Visualization</h2>
            <p className="text-[11px] leading-relaxed text-ink-faint">
              The SAR / prediction / overlay comparison workspace is available on the monitor
              console. Select this incident and open{" "}
              <span className="text-signal-cyan">View Prediction Overlay</span>.
            </p>
          </section>
        </div>
      </div>
    </PageShell>
  );
}

function CandidateCard({ candidate, rank }: { candidate: CandidateVessel; rank: number }) {
  const scorePercent = Math.round(candidate.attributionScore * 100);
  const isTopCandidate = rank === 1;
  return (
    <div className={`rounded border p-3 ${isTopCandidate ? "border-signal-cyan/40 bg-signal-cyan/5" : "border-line bg-base-900/50"}`}>
      <div className="mb-1.5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] font-bold text-ink-faint">#{rank}</span>
          <span className="text-xs font-medium text-ink">
            {candidate.vesselName || `MMSI ${candidate.mmsi}`}
          </span>
          {isTopCandidate && (
            <Badge tone="cyan">POTENTIAL SOURCE</Badge>
          )}
        </div>
        <span className="font-mono text-[10px] text-ink-faint">{candidate.vesselType}</span>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
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
      <div className="mt-2 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Shield className="h-3 w-3 text-signal-cyan/60" />
          <span className="text-[10px] font-medium text-ink-faint">
            Attribution Score
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-base-950">
            <div
              className="h-full rounded-full bg-signal-cyan"
              style={{ width: `${scorePercent}%` }}
            />
          </div>
          <span className="font-mono text-xs font-bold text-signal-cyan">{scorePercent}%</span>
        </div>
      </div>
      <p className="mt-2 text-[10px] italic text-ink-faint/70">
        Human review required — AIS proximity alone does not establish causation.
      </p>
    </div>
  );
}
