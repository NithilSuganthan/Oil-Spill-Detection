"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { X, Satellite, Cpu, Layers } from "lucide-react";
import { getIncident, getScene } from "@/lib/api/client";
import { useAppStore, type ViewerTab } from "@/lib/store/use-app-store";
import { formatISTDate, formatISTTime } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { SarCanvas, type ViewerMode } from "./sar-canvas";
import { LoadingBlock } from "@/components/ui/states";

const TABS: { id: ViewerTab; label: string; hint: string }[] = [
  { id: "sar", label: "ORIGINAL", hint: "Level-1 GRD magnitude" },
  { id: "prediction", label: "PREDICTION", hint: "OilSpillNet v1.0 segmentation" },
  { id: "overlay", label: "OVERLAY", hint: "SAR + predicted slick mask" },
];

export function SatelliteViewerModal() {
  const viewerIncidentId = useAppStore((s) => s.viewerIncidentId);
  const viewerTab = useAppStore((s) => s.viewerTab);
  const setViewerTab = useAppStore((s) => s.setViewerTab);
  const closeViewer = useAppStore((s) => s.closeViewer);
  const [maskOpacity, setMaskOpacity] = React.useState(0.65);

  const {
    data: incident,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["incident", viewerIncidentId],
    queryFn: () => getIncident(viewerIncidentId!),
    enabled: Boolean(viewerIncidentId),
  });

  const { data: scene } = useQuery({
    queryKey: ["scene", incident?.sceneId],
    queryFn: () => getScene(incident!.sceneId),
    enabled: Boolean(incident?.sceneId),
  });

  React.useEffect(() => {
    if (!viewerIncidentId) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeViewer();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [viewerIncidentId, closeViewer]);

  if (!viewerIncidentId) return null;

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-3 md:p-6 animate-fade-in">
      <button
        aria-label="Close viewer"
        className="absolute inset-0 bg-base-950/85 backdrop-blur-sm"
        onClick={closeViewer}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Satellite scene analysis"
        className="panel relative flex h-full max-h-full w-full max-w-6xl flex-col overflow-hidden shadow-panel"
      >
        {/* header */}
        <div className="flex h-12 shrink-0 items-center justify-between border-b border-line px-4">
          <div className="flex min-w-0 items-center gap-3">
            <Satellite className="h-4 w-4 shrink-0 text-signal-cyan" />
            <div className="min-w-0 leading-tight">
              <p className="font-mono text-xs font-bold tracking-wider text-ink">
                SCENE INVESTIGATION · {incident?.id ?? viewerIncidentId}
              </p>
              <p className="truncate font-mono text-[10px] text-ink-faint">
                {scene ? `${scene.platform} · ${scene.sensor} · ${scene.polarisation}` : "Loading scene metadata…"}
              </p>
            </div>
          </div>
          <button
            aria-label="Close"
            onClick={closeViewer}
            className="focus-ring rounded p-1.5 text-ink-faint hover:bg-base-700/60 hover:text-ink"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* mode tabs */}
        <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-line bg-base-900/60 px-4 py-2">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setViewerTab(tab.id)}
              aria-pressed={viewerTab === tab.id}
              title={tab.hint}
              className={cn(
                "focus-ring rounded border px-3 py-1 font-mono text-[10px] tracking-[0.18em] transition-colors",
                viewerTab === tab.id
                  ? "border-signal-cyan/60 bg-signal-cyan/10 text-signal-cyan"
                  : "border-line text-ink-faint hover:border-line-bright hover:text-ink-dim"
              )}
            >
              {tab.label}
            </button>
          ))}

          {viewerTab === "overlay" && (
            <label className="ml-auto flex items-center gap-2">
              <span className="font-mono text-[10px] uppercase tracking-widest text-ink-faint">
                Mask Opacity
              </span>
              <input
                type="range"
                min={0}
                max={100}
                value={Math.round(maskOpacity * 100)}
                onChange={(e) => setMaskOpacity(Number(e.target.value) / 100)}
                className="h-1 w-40 cursor-pointer accent-cyan-400"
                aria-label="Prediction mask opacity"
              />
              <span className="w-9 font-mono text-[11px] tabular-nums text-ink-dim">
                {Math.round(maskOpacity * 100)}%
              </span>
            </label>
          )}
        </div>

        {/* body */}
        <div className="min-h-0 flex-1 p-3">
          {isError ? (
            <LoadingBlock label="Scene unavailable" />
          ) : isLoading || !incident ? (
            <LoadingBlock label="Loading scene…" />
          ) : (
            <div className="grid h-full min-h-0 grid-cols-1 gap-3 lg:grid-cols-[1fr_280px]">
              <div className="relative min-h-[320px]">
                <SarCanvas
                  key={viewerTab}
                  incident={incident}
                  mode={viewerTab as ViewerMode}
                  maskOpacity={maskOpacity}
                />
              </div>

              {/* side metadata */}
              <aside className="hidden min-h-0 flex-col gap-3 overflow-y-auto lg:flex">
                <section className="panel p-3">
                  <div className="mb-2 flex items-center gap-1.5">
                    <Satellite className="h-3 w-3 text-signal-cyan/80" />
                    <h4 className="panel-title">Acquisition</h4>
                  </div>
                  <dl className="space-y-1.5 font-mono text-[11px]">
                    {[
                      ["Platform", scene?.platform ?? incident.satellite],
                      ["Sensor", scene?.sensor ?? "SAR C-band"],
                      ["Mode", scene ? `IW / ${scene.acquisitionMode}` : "—"],
                      ["Polarisation", scene?.polarisation ?? "VV + VH"],
                      ["Acquired", `${formatISTDate(incident.detectedAt)} ${formatISTTime(incident.detectedAt).replace(" IST", "")} IST`],
                      ["Scene ID", incident.sceneId],
                    ].map(([k, v]) => (
                      <div key={k} className="flex justify-between gap-3">
                        <dt className="text-ink-faint">{k}</dt>
                        <dd className="truncate text-right text-ink-dim">{v}</dd>
                      </div>
                    ))}
                  </dl>
                </section>

                <section className="panel p-3">
                  <div className="mb-2 flex items-center gap-1.5">
                    <Cpu className="h-3 w-3 text-signal-cyan/80" />
                    <h4 className="panel-title">Inference</h4>
                  </div>
                  <dl className="space-y-1.5 font-mono text-[11px]">
                    {[
                      ["Model", `${incident.model} ${incident.modelVersion}`],
                      ["Confidence", `${(incident.confidence * 100).toFixed(1)}%`],
                      ["Slick Area", `${incident.areaKm2.toFixed(1)} km²`],
                      ["Look-alike Filter", "Passed"],
                      ["Wind Field", `${incident.windSpeedKts} kts`],
                    ].map(([k, v]) => (
                      <div key={k} className="flex justify-between gap-3">
                        <dt className="text-ink-faint">{k}</dt>
                        <dd className="text-right text-ink-dim">{v}</dd>
                      </div>
                    ))}
                  </dl>
                  <p className="mt-2 flex items-start gap-1.5 border-t border-line pt-2 text-[10px] leading-relaxed text-ink-faint">
                    <Layers className="mt-0.5 h-3 w-3 shrink-0" />
                    Imagery shown is a synthetic prototype visualization of the planned ML output — not real satellite data.
                  </p>
                </section>

                <section className="panel p-3">
                  <h4 className="panel-title mb-2">Pipeline</h4>
                  <ol className="space-y-1.5 text-[11px] text-ink-dim">
                    <li>① SAR preprocessing (calibration · speckle)</li>
                    <li>② Dark-spot candidate detection</li>
                    <li>③ OilSpillNet segmentation</li>
                    <li>④ Look-alike rejection &amp; scoring</li>
                    <li>⑤ Polygon extraction → database</li>
                  </ol>
                </section>
              </aside>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
