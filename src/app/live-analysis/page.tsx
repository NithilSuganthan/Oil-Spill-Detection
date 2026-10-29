"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PageShell } from "@/components/layout/page-shell";
import { PipelineStages } from "@/components/live-analysis/pipeline-stages";
import { EngineCards } from "@/components/live-analysis/engine-cards";
import { InvestigationMap } from "@/components/live-analysis/investigation-map";
import { SlickTimeline } from "@/components/live-analysis/slick-timeline";
import { EvidenceChain } from "@/components/live-analysis/evidence-chain";
import { useSSE, mapEventToStage, type SSEEvent } from "@/lib/hooks/use-sse";
import {
  getIncidents,
  getDrift,
  getAttribution,
  getSystemStatus,
  getReport,
  getScene,
  runInvestigation,
  generateReport,
  getSatelliteProvider,
  API_MODE,
} from "@/lib/api/client";
import {
  Activity,
  Radio,
  Zap,
  Play,
  Loader2,
  Wifi,
  WifiOff,
  Satellite,
  CheckCircle2,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type StageStatus = "waiting" | "running" | "complete" | "failed" | "skipped";

export interface PipelineStage {
  id: string;
  label: string;
  sublabel: string;
  status: StageStatus;
  detail?: string;
  timestamp?: string;
  duration?: string;
}

const INITIAL_STAGES: PipelineStage[] = [
  { id: "satellite", label: "SATELLITE ACQUISITION", sublabel: "Sentinel-1 SAR", status: "waiting" },
  { id: "preprocessing", label: "SAR PREPROCESSING", sublabel: "Calibration · Georeferencing", status: "waiting" },
  { id: "segmentation", label: "AI SEGMENTATION", sublabel: "TinyUNet", status: "waiting" },
  { id: "detection", label: "DETECTION EXTRACTION", sublabel: "Polygon · Confidence", status: "waiting" },
  { id: "drift", label: "BACKWARD DRIFT", sublabel: "Source Estimation", status: "waiting" },
  { id: "attribution", label: "AIS ATTRIBUTION", sublabel: "Vessel Correlation", status: "waiting" },
  { id: "report", label: "INVESTIGATION REPORT", sublabel: "Groq / Mock", status: "waiting" },
];

function LiveAnalysisContent() {
  const searchParams = useSearchParams();
  const sceneParam = searchParams.get("scene");

  const queryClient = useQueryClient();
  const [stages, setStages] = React.useState<PipelineStage[]>(INITIAL_STAGES);
  const [selectedIncidentIdx, setSelectedIncidentIdx] = React.useState(0);
  const [pipelineStartTime, setPipelineStartTime] = React.useState<number | null>(null);
  const [, setSseEvents] = React.useState<SSEEvent[]>([]);
  const [simulationMode, setSimulationMode] = React.useState(false);

  const isReal = API_MODE === "real";

  // Data fetching
  const { data: incidents } = useQuery({
    queryKey: ["all-incidents"],
    queryFn: () => getIncidents({}),
  });

  const { data: systemStatus } = useQuery({
    queryKey: ["system-status"],
    queryFn: getSystemStatus,
  });

  const selectedIncident = incidents?.[selectedIncidentIdx] ?? incidents?.[0] ?? null;

  const { data: drift } = useQuery({
    queryKey: ["drift", selectedIncident?.id],
    queryFn: () => getDrift(selectedIncident!.id),
    enabled: !!selectedIncident?.id,
    retry: false,
  });

  const { data: attribution } = useQuery({
    queryKey: ["attribution", selectedIncident?.id],
    queryFn: () => getAttribution(selectedIncident!.id),
    enabled: !!selectedIncident?.id,
    retry: false,
  });

  const { data: scene } = useQuery({
    queryKey: ["scene", selectedIncident?.sceneId],
    queryFn: () => getScene(selectedIncident!.sceneId),
    enabled: !!selectedIncident?.sceneId,
    retry: false,
  });

  const { data: satProvider } = useQuery({
    queryKey: ["satellite-provider"],
    queryFn: getSatelliteProvider,
    retry: false,
  });

  const { data: reportData } = useQuery({
    queryKey: ["report", selectedIncident?.id],
    queryFn: () => getReport(selectedIncident!.id),
    enabled: !!selectedIncident?.id,
    retry: false,
  });

  // Investigation mutation
  const investigationMutation = useMutation({
    mutationFn: (incidentId: string) => runInvestigation(incidentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["drift", selectedIncident?.id] });
      queryClient.invalidateQueries({ queryKey: ["attribution", selectedIncident?.id] });
      queryClient.invalidateQueries({ queryKey: ["report", selectedIncident?.id] });
    },
  });

  // Report generation mutation
  const reportMutation = useMutation({
    mutationFn: (incidentId: string) => generateReport(incidentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["report", selectedIncident?.id] });
    },
  });

  // SSE for real-time events
  const { connected: sseConnected } = useSSE({
    enabled: isReal,
    onEvent: (event) => {
      setSseEvents((prev) => [...prev.slice(-49), event]);
      const mapping = mapEventToStage(event.type);
      if (mapping) {
        setStages((prev) =>
          prev.map((s) => {
            if (s.id === mapping.stageId) {
              return {
                ...s,
                status: mapping.status,
                timestamp: new Date().toISOString(),
              };
            }
            if (mapping.stageId === "investigation") {
              if (s.id === "drift" && mapping.status === "running") return { ...s, status: "running" as StageStatus };
              if (s.id === "attribution" && mapping.status === "running") return { ...s, status: "running" as StageStatus };
              if (s.id === "drift" && mapping.status === "complete") return { ...s, status: "complete" as StageStatus };
              if (s.id === "attribution" && mapping.status === "complete") return { ...s, status: "complete" as StageStatus };
            }
            return s;
          })
        );
      }
    },
  });

  // Initialize stages based on available data
  React.useEffect(() => {
    if (!selectedIncident) return;

    setStages((prev) =>
      prev.map((s) => {
        if (s.id === "drift" && drift) return { ...s, status: "complete" as StageStatus };
        if (s.id === "attribution" && attribution) return { ...s, status: "complete" as StageStatus };
        if (s.id === "report" && reportData) return { ...s, status: "complete" as StageStatus };
        if (s.id === "satellite") return { ...s, status: "complete" as StageStatus, detail: sceneParam ? `Swath: ${sceneParam}` : undefined };
        if (s.id === "preprocessing") return { ...s, status: "complete" as StageStatus };
        if (s.id === "detection") return { ...s, status: "complete" as StageStatus };
        return s;
      })
    );
  }, [selectedIncident, drift, attribution, reportData, scene, sceneParam]);

  // Run investigation
  const handleRunInvestigation = () => {
    if (!selectedIncident) return;
    setPipelineStartTime(Date.now());
    setSimulationMode(false);
    setStages((prev) =>
      prev.map((s) => ({
        ...s,
        status: s.id === "detection" ? ("complete" as StageStatus) : ("waiting" as StageStatus),
        timestamp: undefined,
      }))
    );
    investigationMutation.mutate(selectedIncident.id);
  };

  // Run simulation
  const handleRunSimulation = () => {
    if (!selectedIncident) return;
    setSimulationMode(true);
    setPipelineStartTime(Date.now());
    setStages(INITIAL_STAGES.map((s) => ({ ...s, status: "waiting" as StageStatus })));

    const sequence: { idx: number; status: StageStatus; delay: number }[] = [
      { idx: 0, status: "running", delay: 0 },
      { idx: 0, status: "complete", delay: 1200 },
      { idx: 1, status: "running", delay: 1300 },
      { idx: 1, status: "complete", delay: 3000 },
      { idx: 2, status: "running", delay: 3100 },
      { idx: 2, status: "complete", delay: 5500 },
      { idx: 3, status: "running", delay: 5600 },
      { idx: 3, status: "complete", delay: 6800 },
      { idx: 4, status: "running", delay: 8300 },
      { idx: 4, status: "complete", delay: 11000 },
      { idx: 5, status: "running", delay: 11100 },
      { idx: 5, status: "complete", delay: 13000 },
      { idx: 6, status: "running", delay: 13100 },
      { idx: 6, status: "complete", delay: 15000 },
    ];

    sequence.forEach(({ idx, status, delay }) => {
      setTimeout(() => {
        setStages((prev) => {
          const next = [...prev];
          next[idx] = { ...next[idx], status, timestamp: new Date().toISOString() };
          return next;
        });
      }, delay);
    });
  };

  // Generate report
  const handleGenerateReport = () => {
    if (!selectedIncident) return;
    setStages((prev) =>
      prev.map((s) => (s.id === "report" ? { ...s, status: "running" as StageStatus } : s))
    );
    reportMutation.mutate(selectedIncident.id, {
      onSettled: () => {
        setStages((prev) =>
          prev.map((s) =>
            s.id === "report"
              ? { ...s, status: reportMutation.isSuccess ? "complete" : "failed", timestamp: new Date().toISOString() }
              : s
          )
        );
      },
    });
  };

  const completedStages = stages.filter((s) => s.status === "complete").length;
  const overallProgress = (completedStages / stages.length) * 100;

  return (
    <PageShell maxWidth="max-w-[1400px]" viewer={false}>
      {/* Header */}
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded border border-signal-cyan/30 bg-signal-cyan/10">
              <Zap className="h-4 w-4 text-signal-cyan" />
            </div>
            <div>
              <h1 className="font-mono text-lg font-bold tracking-wider text-ink">
                LIVE INVESTIGATION PIPELINE
              </h1>
              <p className="text-[11px] uppercase tracking-[0.18em] text-ink-faint">
                Real-time backend state · {isReal ? "Connected to backend" : "Simulation available"}
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Connection status */}
          <div
            className={cn(
              "flex items-center gap-2 rounded border px-3 py-1.5 font-mono text-[10px] tracking-wider",
              isReal && sseConnected
                ? "border-signal-green/40 bg-signal-green/10 text-signal-green"
                : isReal
                  ? "border-signal-amber/40 bg-signal-amber/10 text-signal-amber"
                  : "border-line text-ink-faint"
            )}
          >
            {isReal && sseConnected ? (
              <Wifi className="h-3 w-3" />
            ) : isReal ? (
              <WifiOff className="h-3 w-3" />
            ) : (
              <Radio className="h-3 w-3" />
            )}
            <span className="font-semibold">
              {isReal && sseConnected
                ? "SSE CONNECTED"
                : isReal
                  ? "BACKEND ONLY"
                  : "SIMULATION MODE"}
            </span>
          </div>

          {/* Live investigation button */}
          {isReal && (
            <button
              onClick={handleRunInvestigation}
              disabled={investigationMutation.isPending || !selectedIncident}
              className={cn(
                "focus-ring flex items-center gap-2 rounded border px-4 py-2 font-mono text-[11px] uppercase tracking-widest transition-colors",
                investigationMutation.isPending
                  ? "border-signal-cyan/50 bg-signal-cyan/10 text-signal-cyan"
                  : "border-signal-green/50 bg-signal-green/10 text-signal-green hover:bg-signal-green/20"
              )}
            >
              {investigationMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Play className="h-3.5 w-3.5" />
              )}
              {investigationMutation.isPending ? "Running…" : "Run Live Investigation"}
            </button>
          )}

          {/* Simulation button */}
          <button
            onClick={handleRunSimulation}
            className="focus-ring flex items-center gap-2 rounded border border-signal-amber/50 bg-signal-amber/10 px-4 py-2 font-mono text-[11px] uppercase tracking-widest text-signal-amber transition-colors hover:bg-signal-amber/20"
          >
            <Activity className="h-3.5 w-3.5" />
            Run Simulation
          </button>
        </div>
      </div>

      {/* Active SAR Scene Notice */}
      {sceneParam && (
        <div className="mb-4 flex items-center gap-2.5 rounded border border-cyan-500/40 bg-cyan-500/10 px-4 py-2 font-mono text-[11px] text-cyan-300 animate-fade-in">
          <Satellite className="h-4 w-4 text-cyan-400 shrink-0" />
          <span>Active Sentinel-1 SAR Acquisition Loaded: <strong>{sceneParam}</strong> (VV+VH GRD)</span>
        </div>
      )}

      {/* Mode banner */}
      {simulationMode && (
        <div className="mb-4 rounded border border-signal-amber/40 bg-signal-amber/5 px-4 py-2 font-mono text-[10px] tracking-wider text-signal-amber animate-fade-in">
          ⚠ SIMULATION — NOT LIVE BACKEND EXECUTION. Displaying illustrative pipeline progression.
        </div>
      )}

      {/* Progress bar */}
      <div className="mb-6">
        <div className="mb-2 flex items-center justify-between">
          <span className="font-mono text-[10px] uppercase tracking-widest text-ink-faint">
            Pipeline Progress
          </span>
          <span className="font-mono text-[11px] tabular-nums text-signal-cyan">
            {completedStages}/{stages.length} STAGES
          </span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-base-800">
          <div
            className="h-full rounded-full bg-gradient-to-r from-signal-cyan to-signal-teal transition-all duration-700 ease-out"
            style={{ width: `${overallProgress}%` }}
          />
        </div>
      </div>

      {/* Incident Selector */}
      {incidents && incidents.length > 0 && (
        <div className="mb-6">
          <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-widest text-ink-faint">
            Active Investigation
          </label>
          <div className="flex flex-wrap gap-2">
            {incidents.slice(0, 6).map((inc, idx) => (
              <button
                key={inc.id}
                onClick={() => {
                  setSelectedIncidentIdx(idx);
                  setStages(INITIAL_STAGES.map((s) => ({ ...s, status: "waiting" })));
                  setSseEvents([]);
                  setSimulationMode(false);
                }}
                className={cn(
                  "focus-ring rounded border px-3 py-1.5 font-mono text-[11px] transition-colors",
                  idx === selectedIncidentIdx
                    ? "border-signal-cyan/60 bg-signal-cyan/10 text-signal-cyan"
                    : "border-line text-ink-dim hover:border-line-bright hover:text-ink"
                )}
              >
                {inc.id}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Pipeline stages */}
      <div className="mb-6">
        <PipelineStages
          stages={stages}
          simulationMode={simulationMode}
          pipelineStartTime={pipelineStartTime}
          onGenerateReport={handleGenerateReport}
        />
      </div>

      {/* Engine cards */}
      <div className="mb-6">
        <EngineCards
          drift={drift}
          attribution={attribution}
          report={reportData}
          scene={scene}
          satProvider={satProvider}
          incident={selectedIncident}
          simulationMode={simulationMode}
        />
      </div>

      {/* Investigation map + timeline */}
      <div className="mb-6 grid grid-cols-1 gap-4 xl:grid-cols-[1fr_340px]">
        <InvestigationMap
          incident={selectedIncident}
          drift={drift}
          attribution={attribution}
        />
        <SlickTimeline
          stages={stages}
          pipelineStartTime={pipelineStartTime}
          drift={drift}
          incident={selectedIncident}
          simulationMode={simulationMode}
        />
      </div>

      {/* Evidence chain */}
      <div className="mb-6">
        <EvidenceChain stages={stages} />
      </div>
    </PageShell>
  );
}

export default function LiveAnalysisPage() {
  return (
    <React.Suspense fallback={<div className="p-8 text-center font-mono text-cyan-400">Loading SAR Scene Analysis...</div>}>
      <LiveAnalysisContent />
    </React.Suspense>
  );
}
