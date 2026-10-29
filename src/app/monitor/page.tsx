"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { PanelLeftOpen, X } from "lucide-react";
import { TopNav, MobileNav } from "@/components/layout/top-nav";
import { MapView } from "@/components/map/map-view-client";
import { DetectionsSidebar } from "@/components/monitor/detections-sidebar";
import {
  IncidentDetailsPanel,
  EmptyDetailsPanel,
} from "@/components/monitor/incident-details-panel";
import { SummaryCards } from "@/components/monitor/summary-cards";
import { SystemStatusBar } from "@/components/monitor/system-status-bar";
import { SatelliteViewerModal } from "@/components/viewer/satellite-viewer-modal";
import { ActivityFeed } from "@/components/monitor/activity-feed";
import { InvestigationProgress } from "@/components/monitor/investigation-progress";
import { getAnalytics, getIncidents, getSatelliteScenes, getAttribution } from "@/lib/api/client";
import { useAppStore } from "@/lib/store/use-app-store";
import { useSSE } from "@/lib/hooks/use-sse";

export default function MonitorPage() {
  const filters = useAppStore((s) => s.filters);
  const selectedIncident = useAppStore((s) => s.selectedIncident);
  const clearSelection = useAppStore((s) => s.clearSelection);
  const sidebarOpenMobile = useAppStore((s) => s.sidebarOpenMobile);
  const setSidebarOpenMobile = useAppStore((s) => s.setSidebarOpenMobile);
  const detailsOpenMobile = useAppStore((s) => s.detailsOpenMobile);
  const setDetailsOpenMobile = useAppStore((s) => s.setDetailsOpenMobile);

  const [mobileNav, setMobileNav] = React.useState(false);

  const {
    data: incidents,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["incidents", filters],
    queryFn: () => getIncidents(filters),
  });

  const { data: scenes } = useQuery({
    queryKey: ["scenes"],
    queryFn: getSatelliteScenes,
  });

  const { data: analytics } = useQuery({
    queryKey: ["analytics"],
    queryFn: getAnalytics,
  });

  // Fetch AIS attribution when an incident is selected
  const { data: attribution } = useQuery({
    queryKey: ["attribution", selectedIncident?.id],
    queryFn: () => getAttribution(selectedIncident!.id),
    enabled: !!selectedIncident?.id,
    retry: false,
    staleTime: 60_000,
  });

  // SSE for real-time backend events
  const { events: sseEvents, connected: sseConnected } = useSSE({
    enabled: true,
    onEvent: React.useCallback((event: { type: string; payload: Record<string, unknown> }) => {
      // Invalidate queries on relevant events
      if (event.type === "detection.created") {
        refetch();
      }
      if (event.type === "attribution.completed" || event.type === "drift.completed") {
        // Will auto-refresh via staleTime
      }
    }, [refetch]),
  });

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TopNav onOpenMobileNav={() => setMobileNav(true)} />
      <MobileNav open={mobileNav} onClose={() => setMobileNav(false)} />

      <div className="flex min-h-0 flex-1">
        {/* LEFT — detections feed */}
        <aside className="hidden w-[320px] shrink-0 border-r border-line bg-base-900/70 lg:flex lg:flex-col">
          <DetectionsSidebar
            incidents={incidents ?? []}
            isLoading={isLoading}
            isError={isError}
            refetch={refetch}
          />
        </aside>

        {/* CENTER — summary + map + activity */}
        <main className="relative flex min-w-0 flex-1 flex-col">
          <div className="shrink-0 border-b border-line bg-base-900/40 px-3 py-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h1 className="font-mono text-xs font-bold uppercase tracking-[0.2em] text-ink">
                  Detection Monitor
                </h1>
                <span className="rounded border border-signal-red/30 bg-signal-red/10 px-2 py-0.5 font-mono text-[10px] font-bold text-signal-red">
                  {analytics?.totals.detections ?? incidents?.length ?? 0} MODEL DETECTIONS
                </span>
              </div>
              <p className="hidden font-mono text-[9px] text-ink-faint sm:block">
                Model-generated oil-spill candidates for analysis
              </p>
            </div>
            <SummaryCards
              totals={
                analytics?.totals ?? {
                  detections: 0,
                  highConfidence: 0,
                  totalAreaKm2: 0,
                  scenesProcessed: 0,
                }
              }
            />
          </div>

          <div className="relative min-h-0 flex-1">
            <MapView incidents={incidents ?? []} scenes={scenes ?? []} attribution={attribution ?? null} />

            {/* Investigation progress overlay - below mobile button */}
            {selectedIncident && (
              <div className="absolute bottom-2 left-3 right-3 z-10 sm:left-3 sm:right-auto sm:max-w-[320px]">
                <InvestigationProgress incident={selectedIncident} />
              </div>
            )}

            {/* Activity feed overlay - bottom right */}
            <div className="absolute bottom-2 right-3 z-10 hidden max-h-[240px] w-[260px] overflow-y-auto sm:block">
              <ActivityFeed sseConnected={sseConnected} events={sseEvents} />
            </div>

            {/* mobile open-feed button */}
            <button
              onClick={() => setSidebarOpenMobile(true)}
              className="focus-ring absolute left-3 top-3 z-10 flex h-8 items-center gap-2 rounded border border-line bg-base-900/90 px-3 font-mono text-[11px] uppercase tracking-widest text-ink-dim backdrop-blur hover:text-ink lg:hidden"
            >
              <PanelLeftOpen className="h-4 w-4" /> Detections
              <span className="rounded bg-signal-red/15 px-1 text-signal-red">
                {incidents?.length ?? 0}
              </span>
            </button>

            {(incidents?.length ?? 0) === 0 && !isLoading && (
              <div className="pointer-events-none absolute left-1/2 top-4 z-10 -translate-x-1/2 rounded border border-line bg-base-900/90 px-4 py-2 font-mono text-[11px] tracking-wider text-ink-dim backdrop-blur animate-fade-in">
                NO MODEL DETECTIONS AVAILABLE
              </div>
            )}
          </div>
        </main>

        {/* RIGHT — incident details */}
        <aside className="hidden w-[340px] shrink-0 border-l border-line bg-base-900/70 xl:block">
          {selectedIncident ? (
            <IncidentDetailsPanel incident={selectedIncident} onClose={clearSelection} />
          ) : (
            <EmptyDetailsPanel />
          )}
        </aside>
      </div>

      <SystemStatusBar selectedIncident={selectedIncident} />

      {/* Mobile drawers */}
      {sidebarOpenMobile && (
        <div className="fixed inset-0 z-50 xl:hidden">
          <button
            aria-label="Close detections"
            className="absolute inset-0 bg-black/60"
            onClick={() => setSidebarOpenMobile(false)}
          />
          <div className="panel absolute bottom-0 left-0 top-14 flex w-[320px] max-w-[85vw] animate-fade-in flex-col rounded-none border-y-0 border-l-0">
            <DetectionsSidebar
              incidents={incidents ?? []}
              isLoading={isLoading}
              isError={isError}
              refetch={refetch}
            />
          </div>
        </div>
      )}

      {detailsOpenMobile && selectedIncident && (
        <div className="fixed inset-0 z-50 xl:hidden">
          <button
            aria-label="Close incident details"
            className="absolute inset-0 bg-black/60"
            onClick={() => setDetailsOpenMobile(false)}
          />
          <div className="panel absolute bottom-0 right-0 top-14 flex w-[340px] max-w-[92vw] animate-slide-in-right flex-col rounded-none border-y-0 border-r-0">
            <div className="flex items-center justify-end px-2 pt-1">
              <button
                aria-label="Close"
                onClick={() => setDetailsOpenMobile(false)}
                className="focus-ring rounded p-1.5 text-ink-faint hover:text-ink"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="min-h-0 flex-1 pb-2">
              <IncidentDetailsPanel incident={selectedIncident} compact onClose={() => setDetailsOpenMobile(false)} />
              <Link
                href={`/investigate/${selectedIncident.id}`}
                className="focus-ring mx-3 mt-2 block rounded-md border border-signal-cyan/50 bg-signal-cyan/10 px-3 py-2 text-center font-mono text-[11px] uppercase tracking-widest text-signal-cyan hover:bg-signal-cyan/20"
              >
                VIEW INVESTIGATION →
              </Link>
            </div>
          </div>
        </div>
      )}

      <SatelliteViewerModal />
    </div>
  );
}
