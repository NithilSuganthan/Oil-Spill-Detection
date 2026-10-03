"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Target,
  RefreshCw,
  Loader2,
  Radio,
  Play,
  Maximize2,
  Layers,
  Compass,
  Ship,
  Info,
  Sliders,
  ChevronLeft,
  ChevronRight,
  FileDown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { getDrift, getAttribution, getIncidents, getIncident, getReport, generateReport, runInvestigation, getEnvironmentalGrid } from "@/lib/api/client";
import { generateInvestigationPDF } from "@/lib/pdf/generate-report-pdf";
import type { Incident, DriftResult, AttributionResult, CandidateVessel, EnvironmentalGrid } from "@/lib/types";
import { useSSE } from "@/lib/hooks/use-sse";
import { useAppStore } from "@/lib/store/use-app-store";
import { TopNav, MobileNav } from "@/components/layout/top-nav";
import DriftMapView, { type DriftMapViewHandle } from "@/components/drift-map/drift-map-view";
import { DriftTimeline } from "@/components/drift-map/drift-timeline";
import { DriftSummaryPanel } from "@/components/drift-map/drift-summary-panel";
import { DriftLayerControl } from "@/components/drift-map/drift-layer-control";
import { EnvironmentPanel } from "@/components/drift-map/environment-panel";
import { DriftLegend } from "@/components/drift-map/drift-legend";
import { DriftStatusCard } from "@/components/drift-map/drift-status-card";
import { SourceEstimateCard } from "@/components/drift-map/source-estimate-card";
import { AisVesselCard } from "@/components/drift-map/ais-vessel-card";
import { MapStyleSwitcher } from "@/components/map/map-style-switcher";
import { Suspense } from "react";

export default function DriftMapPage() {
  return (
    <Suspense fallback={
      <div className="flex h-screen items-center justify-center bg-base-950">
        <div className="h-9 w-9 animate-spin rounded-full border border-transparent border-t-signal-cyan border-r-signal-cyan/30" />
      </div>
    }>
      <DriftMapContent />
    </Suspense>
  );
}

function DriftMapContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialIncidentId = searchParams.get("incident");
  const mapViewRef = React.useRef<DriftMapViewHandle>(null);

  // Top Nav Mobile state
  const [mobileNavOpen, setMobileNavOpen] = React.useState(false);

  // SSE Real-time events
  const { events, connected: isConnected } = useSSE();

  // Incident & Selection state
  const [selectedIncidentId, setSelectedIncidentId] = React.useState<string | null>(null);
  const [selectedVessel, setSelectedVessel] = React.useState<CandidateVessel | null>(null);
  const [showSourceCard, setShowSourceCard] = React.useState(false);
  const [isRightPanelOpen, setIsRightPanelOpen] = React.useState(true);

  // Unified Timeline & Playback state (from Zustand store)
  const isPlaying = useAppStore((s) => s.isPlaying);
  const speed = useAppStore((s) => s.speed);
  const animationProgress = useAppStore((s) => s.animationProgress);
  const setAnimationProgress = useAppStore((s) => s.setAnimationProgress);
  const play = useAppStore((s) => s.play);
  const pause = useAppStore((s) => s.pause);
  const setSpeed = useAppStore((s) => s.setSpeed);
  const resetTimeline = useAppStore((s) => s.resetTimeline);

  // Evolution Mode state
  const [evolutionMode, setEvolutionMode] = React.useState<"SOURCE" | "DRIFT" | "DETECTION" | "FULL">("FULL");

  // Active Layers state
  const [activeLayers, setActiveLayers] = React.useState<Record<string, boolean>>({
    slick: true,
    coverage: false,
    wind: true,
    current: true,
    trajectory: true,
    source: true,
    uncertainty: true,
    "ais-vessels": true,
    "ais-tracks": true,
    candidates: true,
  });

  // Fetch Incidents
  const { data: incidents = [], isLoading: incidentsLoading, refetch: refetchIncidents } = useQuery({
    queryKey: ["incidents"],
    queryFn: () => getIncidents(),
  });

  // Auto-select incident: prefer ?incident= query param, otherwise first incident
  React.useEffect(() => {
    if (initialIncidentId) {
      setSelectedIncidentId(initialIncidentId);
    } else if (!selectedIncidentId && incidents.length > 0) {
      setSelectedIncidentId(incidents[0].id);
    }
  }, [incidents, selectedIncidentId, initialIncidentId]);

  // Fetch Drift Data
  const {
    data: drift,
    isLoading: driftLoading,
    refetch: refetchDrift,
  } = useQuery({
    queryKey: ["drift", selectedIncidentId],
    queryFn: () => getDrift(selectedIncidentId!),
    enabled: !!selectedIncidentId,
  });

  // Fetch Attribution Data
  const {
    data: attribution,
    isLoading: attributionLoading,
    refetch: refetchAttribution,
  } = useQuery({
    queryKey: ["attribution", selectedIncidentId],
    queryFn: () => getAttribution(selectedIncidentId!),
    enabled: !!selectedIncidentId,
  });

  // Fetch Investigation Data (includes criticality)
  const {
    data: investigation,
  } = useQuery({
    queryKey: ["investigation", selectedIncidentId],
    queryFn: () => runInvestigation(selectedIncidentId!),
    enabled: !!selectedIncidentId,
  });

  // Fetch Environmental Grid (wind + current vectors for particle visualization)
  const {
    data: envGrid,
  } = useQuery({
    queryKey: ["environmental-grid", selectedIncidentId],
    queryFn: () => {
      if (!drift) return null;
      const incident = incidents.find((i) => i.id === selectedIncidentId);
      if (!incident) return null;
      return getEnvironmentalGrid(
        incident.centroid.lat,
        incident.centroid.lon,
        incident.detectedAt,
      );
    },
    enabled: !!selectedIncidentId && !!drift,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });

  // Check if environmental provider is real
  const isRealData = React.useMemo(() => {
    if (envGrid?.metadata?.status === "REAL") return true;
    const prov = (drift?.provenance ?? {}) as Record<string, unknown>;
    return prov.environmentalProvider === "real" || prov.environmental_provider === "real";
  }, [drift, envGrid]);

  // Source Points from Drift Result
  const sourcePoints = React.useMemo(() => {
    return (drift?.sourcePoints ?? []) as [number, number][];
  }, [drift]);

  // Slick Points from Drift Result / Incident
  const slickPoints = React.useMemo(() => {
    if (!drift) return [];
    const lat = drift.slickLatitude;
    const lon = drift.slickLongitude;
    const ring: [number, number][] = [];
    const n = 16;
    const rKm = 1.8;
    for (let i = 0; i < n; i++) {
      const theta = (i / n) * Math.PI * 2;
      const dLat = (rKm / 111.32) * Math.sin(theta);
      const dLon = (rKm / (111.32 * Math.cos((lat * Math.PI) / 180))) * Math.cos(theta);
      ring.push([lat + dLat, lon + dLon]);
    }
    return ring;
  }, [drift]);

  // Unified Timeline playback loop (Drives BOTH Oil Spill Particles and Oil Tanker Ship Movements!)
  React.useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setAnimationProgress(animationProgress + 0.006 * speed);
      if (animationProgress + 0.006 * speed >= 1) {
        pause();
        setAnimationProgress(1);
      }
    }, 40);
    return () => clearInterval(interval);
  }, [isPlaying, speed, animationProgress, setAnimationProgress, pause]);

  // Layer toggle handler
  const toggleLayer = React.useCallback((id: string) => {
    setActiveLayers((prev) => ({ ...prev, [id]: !prev[id] }));
  }, []);

  // Replay Drift Handler (Prominent Demo Action)
  const handleReplayDrift = React.useCallback(() => {
    pause();
    setAnimationProgress(0);
    mapViewRef.current?.replayInvestigation((progress) => {
      setAnimationProgress(progress);
    });
  }, [pause, setAnimationProgress]);

  // Evolution Mode Change Handler
  const handleEvolutionMode = React.useCallback(
    (mode: "SOURCE" | "DRIFT" | "DETECTION" | "FULL") => {
      setEvolutionMode(mode);
      if (!drift) return;

      if (mode === "SOURCE") {
        setAnimationProgress(0);
        mapViewRef.current?.flyTo(drift.sourceLongitude, drift.sourceLatitude, 12);
        setShowSourceCard(true);
      } else if (mode === "DRIFT") {
        setAnimationProgress(0.5);
        mapViewRef.current?.fitInvestigation();
        setActiveLayers((prev) => ({ ...prev, trajectory: true }));
      } else if (mode === "DETECTION") {
        setAnimationProgress(1);
        mapViewRef.current?.flyTo(drift.slickLongitude, drift.slickLatitude, 12);
      } else if (mode === "FULL") {
        handleReplayDrift();
      }
    },
    [drift, handleReplayDrift, setAnimationProgress]
  );

  const handleRefreshAll = () => {
    refetchIncidents();
    refetchDrift();
    refetchAttribution();
  };

  // ── AUTO-FLY TO NEW INCIDENT when drift data loads ──
  // This ensures the simulation is visible for EVERY incident, not just the first one
  const prevDriftIdRef = React.useRef<string | null>(null);
  React.useEffect(() => {
    if (!drift) return;
    // Only fly when we switch to a different incident's drift
    if (prevDriftIdRef.current !== drift.incidentId) {
      prevDriftIdRef.current = drift.incidentId;
      // Small delay to let the map update its GeoJSON data first
      const timer = setTimeout(() => {
        mapViewRef.current?.fitInvestigation();
        setAnimationProgress(0);
        setEvolutionMode("FULL");
      }, 400);
      return () => clearTimeout(timer);
    }
  }, [drift, setAnimationProgress]);

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-base-950 text-ink">
      {/* 1. MAIN GLOBAL NAVBAR (MONITOR, INCIDENTS, ANALYTICS, LIVE ANALYSIS, DRIFT MAP, REPORTS, ABOUT) */}
      <TopNav onOpenMobileNav={() => setMobileNavOpen(true)} />
      <MobileNav open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />

      {/* 2. PAGE SUB-HEADER TOOLBAR */}
      <header className="flex h-11 items-center justify-between border-b border-line bg-base-900/90 px-4 shrink-0 shadow-md">
        <div className="flex items-center gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-cyan-400/15 border border-cyan-400/30">
            <Target className="h-3.5 w-3.5 text-cyan-400" />
          </div>
          <div>
            <h1 className="font-mono text-[12px] font-bold text-ink tracking-wider uppercase">
              SAGAR WATCH DRIFT &amp; SOURCE ESTIMATION
            </h1>
            <p className="text-[8.5px] text-ink-faint font-mono hidden sm:block">
              Synchronized Hindcast Trajectory &amp; AIS Tanker Ship Movement
            </p>
          </div>
        </div>

        {/* Action Controls & Incident Selector */}
        <div className="flex items-center gap-2.5">
          {/* SSE Connection Status */}
          <div className="hidden sm:flex items-center gap-1.5 rounded-md border border-line bg-base-950/60 px-2 py-0.5">
            <Radio
              className={cn(
                "h-2.5 w-2.5 animate-pulse",
                isConnected ? "text-emerald-400" : "text-amber-400"
              )}
            />
            <span className="font-mono text-[8.5px] font-bold text-ink-dim">
              {isConnected ? "SSE LIVE" : "OFFLINE"}
            </span>
          </div>

          {/* Incident Selector */}
          <select
            value={selectedIncidentId ?? ""}
            onChange={(e) => {
              setSelectedIncidentId(e.target.value);
              setSelectedVessel(null);
              setShowSourceCard(false);
            }}
            className="rounded-md border border-line bg-base-800 px-2.5 py-1 font-mono text-[10.5px] font-semibold text-ink focus:border-cyan-400 focus:outline-none"
          >
            <option value="">Select Target Detection</option>
            {incidents.map((inc) => (
              <option key={inc.id} value={inc.id}>
                {inc.id} — {inc.region} ({inc.confidence ? (inc.confidence * 100).toFixed(0) : "90"}%)
              </option>
            ))}
          </select>

          {/* Fit Investigation Button */}
          <button
            onClick={() => mapViewRef.current?.fitInvestigation()}
            className="flex h-7 items-center gap-1 rounded-md border border-line bg-base-800 px-2.5 font-mono text-[9.5px] font-bold text-ink transition-colors hover:border-cyan-400 hover:text-cyan-400"
          >
            <Maximize2 className="h-3 w-3" />
            FIT INVESTIGATION
          </button>

          {/* Primary Action Button: REPLAY DRIFT */}
          <button
            onClick={handleReplayDrift}
            className="flex h-7 items-center gap-1 rounded-md border border-cyan-400/60 bg-gradient-to-r from-cyan-500/20 via-cyan-400/30 to-emerald-500/20 px-3 font-mono text-[10.5px] font-extrabold text-cyan-300 shadow-[0_0_14px_rgba(34,211,238,0.3)] transition-all hover:scale-[1.02] hover:bg-cyan-400/30 active:scale-95"
          >
            <Play className="h-3.5 w-3.5 fill-current text-cyan-400" />
            ▶ REPLAY DRIFT
          </button>

          {/* PDF Report Download Button */}
          <button
            onClick={async () => {
              if (!selectedIncidentId) return;
              const [inc, rep] = await Promise.all([
                getIncident(selectedIncidentId),
                generateReport(selectedIncidentId),
              ]);
              generateInvestigationPDF({
                incident: inc,
                drift: drift ?? null,
                attribution: attribution ?? null,
                report: rep,
              });
            }}
            disabled={!drift}
            className="flex h-7 items-center gap-1 rounded-md border border-amber-400/50 bg-gradient-to-r from-amber-500/15 to-amber-600/15 px-2.5 font-mono text-[10px] font-bold text-amber-300 transition-all hover:bg-amber-500/25 active:scale-95 disabled:opacity-40"
            title="Download Investigation Report as PDF"
          >
            <FileDown className="h-3.5 w-3.5" />
            PDF REPORT
          </button>

          {/* Refresh Button */}
          <button
            onClick={handleRefreshAll}
            className="flex h-7 w-7 items-center justify-center rounded-md border border-line bg-base-800 text-ink-dim transition-colors hover:border-line-bright hover:text-ink"
            title="Refresh Analysis Data"
          >
            <RefreshCw className="h-3 w-3" />
          </button>
        </div>
      </header>

      {/* Main Workspace Area (Map + Side Panel) */}
      <div className="relative flex flex-1 overflow-hidden">
        {/* Map Container */}
        <div className="relative flex-1 overflow-hidden">
          {/* Interactive MapLibre Map View */}
          <DriftMapView
            ref={mapViewRef}
            sourcePoints={sourcePoints}
            slickPoints={slickPoints}
            drift={drift ?? null}
            attribution={attribution ?? null}
            activeLayers={activeLayers}
            evolutionMode={evolutionMode}
            animationProgress={animationProgress}
            animationSpeed={speed}
            onSelectSource={() => setShowSourceCard(true)}
            onSelectSlick={() => {
              mapViewRef.current?.flyTo(drift?.slickLongitude ?? 72.84, drift?.slickLatitude ?? 15.29, 13);
            }}
            onSelectVessel={(v) => setSelectedVessel(v)}
            envGrid={envGrid ?? null}
          />

          {/* Basemap style switcher */}
          <MapStyleSwitcher />

          {/* TOP-LEFT FLOATING STATUS CARD */}
          <div className="absolute top-3 left-3 z-10">
            <DriftStatusCard
              drift={drift ?? null}
              attribution={attribution ?? null}
              isRealData={isRealData}
              isConnected={isConnected}
            />
          </div>

          {/* EVOLUTION CONTROL TOOLBAR (Top Center) */}
          <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10">
            <div className="panel border-line bg-base-900/90 p-1 shadow-2xl backdrop-blur-md flex items-center gap-1">
              <span className="font-mono text-[8px] uppercase tracking-widest text-ink-faint px-2 font-bold hidden sm:inline">
                EVOLUTION VIEW:
              </span>
              <button
                onClick={() => handleEvolutionMode("SOURCE")}
                className={cn(
                  "font-mono text-[9px] font-bold px-2.5 py-1 rounded transition-all",
                  evolutionMode === "SOURCE"
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-[0_0_8px_rgba(52,211,153,0.3)]"
                    : "text-ink-faint hover:text-ink hover:bg-base-800"
                )}
              >
                [ SOURCE ]
              </button>
              <button
                onClick={() => handleEvolutionMode("DRIFT")}
                className={cn(
                  "font-mono text-[9px] font-bold px-2.5 py-1 rounded transition-all",
                  evolutionMode === "DRIFT"
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-[0_0_8px_rgba(34,211,238,0.3)]"
                    : "text-ink-faint hover:text-ink hover:bg-base-800"
                )}
              >
                [ DRIFT ]
              </button>
              <button
                onClick={() => handleEvolutionMode("DETECTION")}
                className={cn(
                  "font-mono text-[9px] font-bold px-2.5 py-1 rounded transition-all",
                  evolutionMode === "DETECTION"
                    ? "bg-red-500/20 text-red-300 border border-red-500/40 shadow-[0_0_8px_rgba(239,68,68,0.3)]"
                    : "text-ink-faint hover:text-ink hover:bg-base-800"
                )}
              >
                [ DETECTION ]
              </button>
              <button
                onClick={() => handleEvolutionMode("FULL")}
                className={cn(
                  "font-mono text-[9px] font-bold px-2.5 py-1 rounded transition-all",
                  evolutionMode === "FULL"
                    ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-[0_0_8px_rgba(245,158,11,0.3)]"
                    : "text-ink-faint hover:text-ink hover:bg-base-800"
                )}
              >
                [ FULL EVOLUTION ]
              </button>
            </div>
          </div>

          {/* MAP LAYER CONTROLS (Top Right) */}
          <div className="absolute top-3 right-3 z-10">
            <DriftLayerControl activeLayers={activeLayers} onToggle={toggleLayer} />
          </div>

          {/* ENVIRONMENT PANEL (Bottom Left) */}
          <div className="absolute bottom-24 left-3 z-10 max-w-xs">
            <EnvironmentPanel drift={drift ?? null} grid={envGrid ?? null} />
          </div>

          {/* DRIFT LEGEND (Bottom Left) */}
          <div className="absolute bottom-3 left-3 z-10">
            <DriftLegend />
          </div>

          {/* SOURCE ESTIMATE MODAL CARD */}
          {showSourceCard && (
            <div className="absolute top-16 left-3 z-20 animate-feed-item-in">
              <SourceEstimateCard
                drift={drift ?? null}
                onClose={() => setShowSourceCard(false)}
                onLocate={() => {
                  if (drift?.sourceLongitude && drift?.sourceLatitude) {
                    mapViewRef.current?.flyTo(drift.sourceLongitude, drift.sourceLatitude, 13);
                  }
                }}
              />
            </div>
          )}

          {/* CANDIDATE VESSEL MODAL CARD */}
          {selectedVessel && (
            <div className="absolute top-16 left-3 z-20 animate-feed-item-in">
              <AisVesselCard vessel={selectedVessel} onClose={() => setSelectedVessel(null)} />
            </div>
          )}

          {/* Loading Overlay */}
          {(driftLoading || attributionLoading) && (
            <div className="absolute inset-0 z-30 flex items-center justify-center bg-base-950/60 backdrop-blur-md">
              <div className="panel flex items-center gap-3 px-6 py-4 border-cyan-400/40 shadow-2xl">
                <Loader2 className="h-5 w-5 animate-spin text-cyan-400" />
                <div>
                  <span className="font-mono text-[12px] font-bold text-ink block">
                    Computing Backward Hindcast...
                  </span>
                  <span className="font-mono text-[9.5px] text-ink-faint">
                    Simulating 50 ensemble particles &amp; correlating AIS vessel trajectories
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* DRIFT NOT YET COMPUTED State */}
          {!driftLoading && !drift && selectedIncidentId && (
            <div className="absolute inset-0 z-30 flex items-center justify-center bg-base-950/80 backdrop-blur-md">
              <div className="panel flex flex-col items-center gap-3 px-8 py-6 text-center border-amber-500/40 max-w-md">
                <Target className="h-10 w-10 text-amber-400 animate-pulse" />
                <div>
                  <h3 className="font-mono text-[14px] font-bold text-ink uppercase">
                    DRIFT NOT YET COMPUTED
                  </h3>
                  <p className="mt-1 text-[11px] text-ink-faint font-mono">
                    No backward drift trajectory has been calculated for this incident target.
                  </p>
                </div>
                <button
                  onClick={() => router.push("/live-analysis")}
                  className="rounded-md bg-cyan-500/20 border border-cyan-400/40 px-4 py-2 font-mono text-[11px] font-bold text-cyan-300 transition-colors hover:bg-cyan-500/30"
                >
                  RUN HINDCAST INVESTIGATION
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right Collapsible Investigation Panel (~25% width on desktop) */}
        {isRightPanelOpen && (
          <div className="w-80 shrink-0 border-l border-line bg-base-900/90 shadow-2xl z-10 transition-all">
            <DriftSummaryPanel
              drift={drift ?? null}
              attribution={attribution ?? null}
              isRealData={isRealData}
              criticality={investigation?.criticality ?? null}
            />
          </div>
        )}

        {/* Toggle Right Panel Button */}
        <button
          onClick={() => setIsRightPanelOpen((o) => !o)}
          className="absolute right-0 top-1/2 -translate-y-1/2 z-20 flex h-10 w-5 items-center justify-center rounded-l border border-r-0 border-line bg-base-900 text-ink-faint hover:text-ink hover:bg-base-800"
          title={isRightPanelOpen ? "Collapse Details" : "Expand Details"}
        >
          {isRightPanelOpen ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* 3. UNIFIED TIMELINE PLAYBACK BAR (DRIVES BOTH DRIFT PARTICLES & OIL TANKER SHIP MOVEMENTS) */}
      <div className="shrink-0 border-t border-line bg-base-950 p-2 z-20">
        <DriftTimeline
          durationHours={8}
          currentTime={animationProgress}
          isPlaying={isPlaying}
          speed={speed}
          onSeek={(frac) => setAnimationProgress(frac)}
          onPlay={() => {
            if (animationProgress >= 1) setAnimationProgress(0);
            play();
          }}
          onPause={() => pause()}
          onSpeedChange={setSpeed}
          onReset={() => {
            resetTimeline();
            setAnimationProgress(0);
          }}
        />
      </div>
    </div>
  );
}

