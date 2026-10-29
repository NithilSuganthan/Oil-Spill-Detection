"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Target,
  RefreshCw,
  Loader2,
  Radio,
  Play,
  Maximize2,
  FileText,
  ChevronDown,
  AlertTriangle,
  Layers,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import {
  getDrift,
  getAttribution,
  getIncident,
  getEnvironmentalGrid,
  runInvestigation,
  getIncidents,
} from "@/lib/api/client";
import { generateInvestigationPDF } from "@/lib/pdf/generate-report-pdf";
import type { CandidateVessel } from "@/lib/types";
import { useAppStore } from "@/lib/store/use-app-store";
import { TopNav, MobileNav } from "@/components/layout/top-nav";
import DriftMapView, { type DriftMapViewHandle } from "@/components/drift-map/drift-map-view";
import { DriftTimeline } from "@/components/drift-map/drift-timeline";
import { DriftLayerControl } from "@/components/drift-map/drift-layer-control";
import { DriftLegend } from "@/components/drift-map/drift-legend";
import { DriftStatusCard } from "@/components/drift-map/drift-status-card";
import { SourceEstimateCard } from "@/components/drift-map/source-estimate-card";
import { AisVesselCard } from "@/components/drift-map/ais-vessel-card";
import {
  InvestigationPipeline,
  computePipelineStages,
} from "@/components/investigation/investigation-pipeline";
import { ContextualPanel, type PanelContext } from "@/components/investigation/contextual-panel";
import { MapStyleSwitcher } from "@/components/map/map-style-switcher";

export default function InvestigatePage() {
  const params = useParams();
  const router = useRouter();
  const incidentId = (params?.id as string) || "IN-250825-001";

  const mapViewRef = React.useRef<DriftMapViewHandle>(null);
  const [mobileNav, setMobileNav] = React.useState(false);
  const [selectorOpen, setSelectorOpen] = React.useState(false);

  // ── Selection & Context state ──
  const [panelContext, setPanelContext] = React.useState<PanelContext>({ type: "incident" });
  const [showSourceCard, setShowSourceCard] = React.useState(false);
  const [selectedVessel, setSelectedVessel] = React.useState<CandidateVessel | null>(null);
  const [isRightPanelOpen, setIsRightPanelOpen] = React.useState(true);
  const [activeStageId, setActiveStageId] = React.useState<string | null>("detection");

  // ── Layer state ──
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

  // ── Timeline state from Zustand ──
  const isPlaying = useAppStore((s) => s.isPlaying);
  const speed = useAppStore((s) => s.speed);
  const animationProgress = useAppStore((s) => s.animationProgress);
  const setAnimationProgress = useAppStore((s) => s.setAnimationProgress);
  const play = useAppStore((s) => s.play);
  const pause = useAppStore((s) => s.pause);
  const setSpeed = useAppStore((s) => s.setSpeed);
  const resetTimeline = useAppStore((s) => s.resetTimeline);
  const setMapStyle = useAppStore((s) => s.setMapStyle);

  // Default basemap for investigation is satellite
  React.useEffect(() => {
    setMapStyle("satellite");
  }, [setMapStyle]);

  // ── Evolution mode ──
  const [evolutionMode, setEvolutionMode] = React.useState<"SOURCE" | "DRIFT" | "DETECTION" | "FULL">("FULL");

  // ── Fetch all incidents for target selector ──
  const { data: allIncidents } = useQuery({
    queryKey: ["incidents-all"],
    queryFn: () => getIncidents(),
  });

  // ── Fetch current incident ──
  const {
    data: incident,
    isLoading: incidentLoading,
    isError: incidentError,
  } = useQuery({
    queryKey: ["incident", incidentId],
    queryFn: () => getIncident(incidentId),
    enabled: !!incidentId,
  });

  // ── Fetch drift ──
  const {
    data: drift,
    isLoading: driftLoading,
    refetch: refetchDrift,
  } = useQuery({
    queryKey: ["drift", incidentId],
    queryFn: () => getDrift(incidentId),
    enabled: !!incidentId,
  });

  // ── Fetch attribution ──
  const {
    data: attribution,
    isLoading: attributionLoading,
    refetch: refetchAttribution,
  } = useQuery({
    queryKey: ["attribution", incidentId],
    queryFn: () => getAttribution(incidentId),
    enabled: !!incidentId,
  });

  // ── Fetch investigation (includes criticality) ──
  const { data: investigation, isLoading: investigationLoading } = useQuery({
    queryKey: ["investigation", incidentId],
    queryFn: () => runInvestigation(incidentId),
    enabled: !!incidentId,
  });

  // ── Fetch environmental grid ──
  const { data: envGrid } = useQuery({
    queryKey: ["environmental-grid", incidentId],
    queryFn: () => {
      if (!incident) return null;
      return getEnvironmentalGrid(
        incident.centroid.lat,
        incident.centroid.lon,
        incident.detectedAt,
      );
    },
    enabled: !!incident && !!drift,
    staleTime: 5 * 60 * 1000,
  });

  // ── Derived data ──
  const isRealData = React.useMemo(() => {
    if (envGrid?.metadata?.status === "REAL") return true;
    const prov = (drift?.provenance ?? {}) as Record<string, unknown>;
    return prov.environmentalProvider === "real" || prov.environmental_provider === "real";
  }, [drift, envGrid]);

  const sourcePoints = React.useMemo(() => (drift?.sourcePoints ?? []) as [number, number][], [drift]);

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

  // ── Pipeline stages ──
  const stages = React.useMemo(
    () =>
      computePipelineStages({
        hasIncident: !!incident,
        hasDrift: !!drift,
        hasAttribution: !!attribution,
        hasEnvGrid: !!envGrid,
        hasCriticality: !!investigation?.criticality,
        hasReport: false,
        isDriftLoading: driftLoading,
        isAttributionLoading: attributionLoading,
        isInvestigationLoading: investigationLoading,
      }),
    [incident, drift, attribution, envGrid, investigation, driftLoading, attributionLoading, investigationLoading]
  );

  // ── Timeline playback loop ──
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

  // ── Layer toggle ──
  const toggleLayer = React.useCallback((id: string) => {
    setActiveLayers((prev) => ({ ...prev, [id]: !prev[id] }));
  }, []);

  // ── Replay drift ──
  const handleReplayDrift = React.useCallback(() => {
    pause();
    setAnimationProgress(0);
    mapViewRef.current?.replayInvestigation((progress) => {
      setAnimationProgress(progress);
    });
  }, [pause, setAnimationProgress]);

  // ── Evolution mode change ──
  const handleEvolutionMode = React.useCallback(
    (mode: "SOURCE" | "DRIFT" | "DETECTION" | "FULL") => {
      setEvolutionMode(mode);
      if (!drift) return;

      if (mode === "SOURCE") {
        setAnimationProgress(0);
        mapViewRef.current?.flyTo(drift.sourceLongitude, drift.sourceLatitude, 12);
        setShowSourceCard(true);
        setPanelContext({ type: "source" });
        setActiveStageId("drift");
      } else if (mode === "DRIFT") {
        setAnimationProgress(0.5);
        mapViewRef.current?.fitInvestigation();
        setActiveLayers((prev) => ({ ...prev, trajectory: true }));
        setPanelContext({ type: "incident" });
        setActiveStageId("drift");
      } else if (mode === "DETECTION") {
        setAnimationProgress(1);
        mapViewRef.current?.flyTo(drift.slickLongitude, drift.slickLatitude, 12);
        setPanelContext({ type: "incident" });
        setActiveStageId("detection");
      } else if (mode === "FULL") {
        handleReplayDrift();
        setPanelContext({ type: "incident" });
        setActiveStageId("detection");
      }
    },
    [drift, handleReplayDrift, setAnimationProgress]
  );

  // ── Auto-fly cinematic camera on incident change ──
  const prevDriftIdRef = React.useRef<string | null>(null);
  React.useEffect(() => {
    if (!drift) return;
    if (prevDriftIdRef.current !== drift.incidentId) {
      prevDriftIdRef.current = drift.incidentId;
      const timer = setTimeout(() => {
        mapViewRef.current?.flyTo(drift.slickLongitude, drift.slickLatitude, 11.5);
        setAnimationProgress(0);
        setEvolutionMode("FULL");
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [drift, setAnimationProgress]);

  // ── Pipeline stage click handler ──
  const handleStageClick = React.useCallback(
    (stageId: string) => {
      setActiveStageId(stageId);
      if (!drift) return;

      switch (stageId) {
        case "detection":
          mapViewRef.current?.flyTo(drift.slickLongitude, drift.slickLatitude, 12);
          setPanelContext({ type: "incident" });
          break;
        case "environment":
          setPanelContext({ type: "environment" });
          break;
        case "drift":
          handleEvolutionMode("DRIFT");
          break;
        case "ais":
        case "attribution":
          if (attribution?.candidates && attribution.candidates.length > 0) {
            const firstCandidate = attribution.candidates[0];
            setSelectedVessel(firstCandidate);
            setPanelContext({ type: "vessel", vessel: firstCandidate });
            handleEvolutionMode("DRIFT");
          }
          break;
        case "source":
        case "assessment":
        case "report":
          setPanelContext({ type: "incident" });
          break;
        default:
          setPanelContext({ type: "incident" });
          break;
      }
    },
    [drift, attribution, handleEvolutionMode]
  );

  // ── Refresh handler ──
  const handleRefreshAll = () => {
    refetchDrift();
    refetchAttribution();
  };

  // ── Loading state ──
  if (incidentLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-base-950">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-cyan-400" />
          <span className="font-mono text-[11px] text-ink-faint uppercase tracking-wider">
            Loading investigation {incidentId}...
          </span>
        </div>
      </div>
    );
  }

  // ── Error state ──
  if (incidentError || !incident) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-base-950 gap-4">
        <AlertTriangle className="h-12 w-12 text-amber-400" />
        <div className="text-center">
          <h2 className="font-mono text-[14px] font-bold text-ink uppercase">
            Model Detection Not Found
          </h2>
          <p className="mt-1 text-[11px] text-ink-faint font-mono">
            Could not load incident target {incidentId}
          </p>
        </div>
        <button
          onClick={() => router.push("/investigate/IN-250825-001")}
          className="rounded-md bg-cyan-500/20 border border-cyan-400/40 px-4 py-2 font-mono text-[11px] font-bold text-cyan-300 transition-colors hover:bg-cyan-500/30"
        >
          OPEN DEFAULT DETECTION (IN-250825-001)
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-base-950 text-ink select-none">
      {/* Global Nav Bar */}
      <TopNav onOpenMobileNav={() => setMobileNav(true)} />
      <MobileNav open={mobileNav} onClose={() => setMobileNav(false)} />

      {/* Command Center Sub-Header */}
      <header className="flex h-11 items-center justify-between border-b border-line/60 bg-base-950/95 px-4 shrink-0 shadow-xl z-20">
        <div className="flex items-center gap-3">
          {/* Target Icon */}
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-cyan-400/15 border border-cyan-400/40 shadow-[0_0_10px_rgba(34,211,238,0.2)]">
            <Target className="h-4 w-4 text-cyan-400 animate-pulse" />
          </div>

          <div className="flex items-center gap-2">
            <h1 className="font-mono text-[11.5px] font-extrabold text-ink tracking-wider uppercase">
              SAGAR WATCH <span className="text-cyan-400">|</span> INVESTIGATION WORKSTATION
            </h1>

            {/* Model Detection Target Selector Dropdown */}
            <div className="relative">
              <button
                onClick={() => setSelectorOpen((o) => !o)}
                className="flex items-center gap-1.5 rounded-md border border-cyan-400/40 bg-cyan-500/10 px-2.5 py-1 font-mono text-[11px] font-extrabold text-cyan-300 hover:bg-cyan-500/20 transition-all shadow-[0_0_8px_rgba(34,211,238,0.15)]"
              >
                <span>{incident.id}</span>
                <ChevronDown className="h-3 w-3 text-cyan-400" />
              </button>

              {selectorOpen && (
                <div className="absolute top-full left-0 mt-1.5 w-72 rounded-md border border-line/80 bg-base-950/95 p-1.5 shadow-2xl backdrop-blur-xl z-50">
                  <div className="px-2 py-1 border-b border-line/40 mb-1 font-mono text-[8px] font-bold text-ink-faint uppercase">
                    SELECT MODEL DETECTION TARGET (9 AVAILABLE)
                  </div>
                  <div className="max-h-60 overflow-y-auto space-y-0.5 scrollbar-thin">
                    {(allIncidents ?? [incident]).map((inc) => (
                      <button
                        key={inc.id}
                        onClick={() => {
                          setSelectorOpen(false);
                          router.push(`/investigate/${inc.id}`);
                        }}
                        className={cn(
                          "w-full flex items-center justify-between px-2.5 py-1.5 rounded text-left font-mono text-[10px] transition-all",
                          inc.id === incident.id
                            ? "bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-400/40"
                            : "text-ink-dim hover:bg-base-800/60 hover:text-ink"
                        )}
                      >
                        <span className="font-extrabold">{inc.id}</span>
                        <span className="text-[8.5px] text-ink-faint">{inc.region} ({inc.areaKm2.toFixed(1)} km²)</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <span className="font-mono text-[9px] text-ink-faint hidden lg:inline border-l border-line/60 pl-2">
              {incident.locationDescription}
            </span>
          </div>
        </div>

        {/* Header Action Controls */}
        <div className="flex items-center gap-2">
          {/* NRT Live Status */}
          <div className="hidden sm:flex items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1">
            <Radio className="h-2.5 w-2.5 animate-pulse text-emerald-400" />
            <span className="font-mono text-[8.5px] font-bold text-emerald-300">NRT LIVE STREAM</span>
          </div>

          {/* Evolution Modes */}
          <div className="hidden md:flex items-center gap-0.5 rounded-md border border-line/60 bg-base-900/80 p-0.5">
            {(["SOURCE", "DRIFT", "DETECTION", "FULL"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => handleEvolutionMode(mode)}
                className={cn(
                  "font-mono text-[8.5px] font-extrabold px-2 py-0.5 rounded transition-all",
                  evolutionMode === mode
                    ? mode === "SOURCE" ? "bg-purple-500/20 text-purple-300 border border-purple-500/40" :
                      mode === "DRIFT" ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40" :
                      mode === "DETECTION" ? "bg-red-500/20 text-red-300 border border-red-500/40" :
                      "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                    : "text-ink-faint hover:text-ink hover:bg-base-800"
                )}
              >
                [{mode}]
              </button>
            ))}
          </div>

          {/* Replay Button */}
          <button
            onClick={handleReplayDrift}
            className="flex h-7 items-center gap-1 rounded-md border border-cyan-400/60 bg-gradient-to-r from-cyan-500/20 via-cyan-400/30 to-emerald-500/20 px-2.5 font-mono text-[10px] font-extrabold text-cyan-300 shadow-[0_0_14px_rgba(34,211,238,0.25)] transition-all hover:scale-[1.02] hover:bg-cyan-400/30 active:scale-95"
          >
            <Play className="h-3 w-3 fill-current text-cyan-400" />
            REPLAY
          </button>

          {/* Fit Boundary */}
          <button
            onClick={() => mapViewRef.current?.fitInvestigation()}
            className="flex h-7 items-center gap-1 rounded-md border border-line/60 bg-base-900 px-2.5 font-mono text-[9px] font-bold text-ink-dim transition-colors hover:border-cyan-400/50 hover:text-cyan-300"
          >
            <Maximize2 className="h-3 w-3" />
            FIT
          </button>

          {/* Refresh */}
          <button
            onClick={handleRefreshAll}
            className="flex h-7 w-7 items-center justify-center rounded-md border border-line/60 bg-base-900 text-ink-dim transition-colors hover:border-cyan-400/50 hover:text-ink"
            title="Refresh Data"
          >
            <RefreshCw className="h-3 w-3" />
          </button>
        </div>
      </header>

      {/* Main Command Center Workspace */}
      <div className="relative flex flex-1 overflow-hidden">
        {/* LEFT PANEL: 01-07 Investigation Pipeline (~15-18% width) */}
        <div className="hidden lg:flex w-56 shrink-0 z-10">
          <InvestigationPipeline
            stages={stages}
            activeStageId={activeStageId}
            onStageClick={handleStageClick}
          />
        </div>

        {/* CENTER PANEL: Map Workspace (Dominating ~65%) */}
        <div className="relative flex-1 overflow-hidden">
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
            onSelectSource={() => {
              setShowSourceCard(true);
              setPanelContext({ type: "source" });
              setActiveStageId("drift");
            }}
            onSelectSlick={() => {
              mapViewRef.current?.flyTo(drift?.slickLongitude ?? 72.84, drift?.slickLatitude ?? 15.29, 13);
              setPanelContext({ type: "incident" });
              setActiveStageId("detection");
            }}
            onSelectVessel={(v) => {
              setSelectedVessel(v);
              setPanelContext({ type: "vessel", vessel: v });
              setActiveStageId("ais");
            }}
            envGrid={envGrid ?? null}
          />

          {/* Basemap switcher */}
          <MapStyleSwitcher />

          {/* Top Left Floating status card */}
          <div className="absolute top-3 left-3 z-10">
            <DriftStatusCard
              drift={drift ?? null}
              attribution={attribution ?? null}
              isRealData={isRealData}
              isConnected={true}
            />
          </div>

          {/* Top Right Layer control toggles */}
          <div className="absolute top-3 right-3 z-10">
            <DriftLayerControl activeLayers={activeLayers} onToggle={toggleLayer} />
          </div>

          {/* Bottom Left Map Legend */}
          <div className="absolute bottom-24 left-3 z-10">
            <DriftLegend />
          </div>

          {/* Source Estimate Card overlay */}
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

          {/* Candidate Vessel Detail Overlay Card */}
          {selectedVessel && (
            <div className="absolute top-16 left-3 z-20 animate-feed-item-in">
              <AisVesselCard vessel={selectedVessel} onClose={() => setSelectedVessel(null)} />
            </div>
          )}

          {/* Computing Loading overlay */}
          {(driftLoading || attributionLoading) && (
            <div className="absolute inset-0 z-30 flex items-center justify-center bg-base-950/70 backdrop-blur-md">
              <div className="panel flex items-center gap-3 px-6 py-4 border-cyan-400/50 shadow-2xl">
                <Loader2 className="h-6 w-6 animate-spin text-cyan-400" />
                <div>
                  <span className="font-mono text-[12px] font-bold text-ink block">
                    Executing Maritime Intelligence Pipeline...
                  </span>
                  <span className="font-mono text-[9.5px] text-ink-faint">
                    Computing backward hindcast trajectory &amp; AIS candidate vessel correlation
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* RIGHT PANEL: Analyst Console (~20-25% width) */}
        {isRightPanelOpen && (
          <div className="hidden md:flex w-84 lg:w-96 shrink-0 z-10">
            <ContextualPanel
              context={panelContext}
              incident={incident}
              drift={drift ?? null}
              attribution={attribution ?? null}
              criticality={investigation?.criticality ?? null}
              envGrid={envGrid ?? null}
              isRealData={isRealData}
              onClearContext={() => setPanelContext({ type: "incident" })}
              onSelectVessel={(v) => {
                setSelectedVessel(v);
                setPanelContext({ type: "vessel", vessel: v });
                mapViewRef.current?.flyTo(drift?.sourceLongitude ?? 72.5, drift?.sourceLatitude ?? 15.0, 11);
              }}
              activeStageId={activeStageId}
            />
          </div>
        )}

        {/* Right Panel Collapse / Expand Button */}
        <button
          onClick={() => setIsRightPanelOpen((o) => !o)}
          className="absolute right-0 top-1/2 -translate-y-1/2 z-20 flex h-12 w-5 items-center justify-center rounded-l border border-r-0 border-line/60 bg-base-950/90 text-cyan-400 hover:bg-base-900 transition-colors shadow-lg"
          title={isRightPanelOpen ? "Collapse Analyst Console" : "Expand Analyst Console"}
        >
          <span className="text-[11px] font-mono font-bold">{isRightPanelOpen ? "›" : "‹"}</span>
        </button>
      </div>

      {/* BOTTOM PANEL: Master Investigation Timeline */}
      <div className="shrink-0 border-t border-line/60 bg-base-950 p-2 z-20 shadow-2xl">
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
