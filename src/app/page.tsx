"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Ship,
  Satellite,
  Droplets,
  Waves,
  Wind,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { TopNav, MobileNav } from "@/components/layout/top-nav";
import { GlobeMapView } from "@/components/map/globe-map-view";
import { MapStyleSwitcher } from "@/components/map/map-style-switcher";
import { LayersPanel } from "@/components/globe/layers-panel";
import { DataSourcesPanel, type DataSourceItem } from "@/components/globe/data-sources-panel";
<<<<<<< HEAD
import { AisSourceToggle } from "@/components/globe/ais-source-toggle";
import { VesselListPanel } from "@/components/globe/vessel-list-panel";
=======
>>>>>>> c445e14ea3094989fadcfa63b3423d8312faec8b
import { BottomStatusBar, type StatusCard } from "@/components/globe/bottom-status-bar";
import { TimelineBar, getCurrentISTProgress } from "@/components/globe/timeline-bar";
import { OilInspector } from "@/components/globe/oil-inspector";
import { VesselInspector, type VesselData } from "@/components/globe/vessel-inspector";
import { SarInspector, type SarSceneData } from "@/components/globe/sar-inspector";
import { useAISStream } from "@/lib/hooks/use-ais-stream";
<<<<<<< HEAD
import { useAisTrackHistory } from "@/lib/hooks/use-ais-track-history";
import { REALTIME_AIS_GEOJSON } from "@/lib/mock-data/realtime-ais";
=======
>>>>>>> c445e14ea3094989fadcfa63b3423d8312faec8b
import { getSatelliteScenes } from "@/lib/api/client";
import { useAppStore } from "@/lib/store/use-app-store";
import type { Incident } from "@/lib/types";

export default function GlobePage() {
  const router = useRouter();
  const [mobileNav, setMobileNav] = React.useState(false);

  // Layer Visibility State — All 8 Layers Fully Functional
  const [activeLayers, setActiveLayers] = React.useState<Record<string, boolean>>({
    ais: true,
    "ais-tracks": true,
    sar: true,
    oil: true,
    wind: true,
    current: true,
    coastline: true,
    labels: true,
  });

  const handleLayerToggle = React.useCallback((id: string) => {
    setActiveLayers((prev) => ({ ...prev, [id]: !prev[id] }));
  }, []);

  const handleLayersReset = React.useCallback(() => {
    setActiveLayers({
      ais: true,
      "ais-tracks": true,
      sar: true,
      oil: true,
      wind: true,
      current: true,
      coastline: true,
      labels: true,
    });
  }, []);

  // Inspector States
  const [selectedIncident, setSelectedIncident] = React.useState<Incident | null>(null);
  const [selectedVessel, setSelectedVessel] = React.useState<VesselData | null>(null);
  const [selectedSar, setSelectedSar] = React.useState<SarSceneData | null>(null);
  const [searchTarget, setSearchTarget] = React.useState<[number, number] | null>(null);

  const selectIncident = useAppStore((s) => s.selectIncident);
  const setMapStyle = useAppStore((s) => s.setMapStyle);
<<<<<<< HEAD
  const aisSource = useAppStore((s) => s.aisSource);
  const setAisSource = useAppStore((s) => s.setAisSource);
=======
>>>>>>> c445e14ea3094989fadcfa63b3423d8312faec8b

  // Default basemap for Globe is photographic satellite imagery
  React.useEffect(() => {
    setMapStyle("satellite");
  }, [setMapStyle]);

  // Real-time IST timeline state (initialized to current IST time e.g. 23:01 IST)
  const [timelinePlaying, setTimelinePlaying] = React.useState(false);
  const [timelineSpeed, setTimelineSpeed] = React.useState(1);
  const [timelineProgress, setTimelineProgress] = React.useState(getCurrentISTProgress);

  // Real-time API query for satellite scenes
  const { data: scenes = [] } = useQuery({
    queryKey: ["satellite-scenes"],
    queryFn: () => getSatelliteScenes(),
  });

  // Real-time AIS vessel stream hook
  const { status: aisStatus, vesselGeoJSON } = useAISStream();

<<<<<<< HEAD
  // Accumulated real track history from actual PositionReports (only in REAL-TIME mode)
  const liveVesselGeoJSON = aisSource === "realtime" ? vesselGeoJSON : null;
  const realTracks = useAisTrackHistory(liveVesselGeoJSON);

  // Compute effective vessel data based on selected source
  const effectiveVesselGeoJSON = React.useMemo(() => {
    if (aisSource === "demo") {
      return REALTIME_AIS_GEOJSON;
    }
    // Real-time mode: use live data only, never fall back to demo
    if (vesselGeoJSON && vesselGeoJSON.features && vesselGeoJSON.features.length > 0) {
      return vesselGeoJSON;
    }
    return null;
  }, [aisSource, vesselGeoJSON]);

=======
>>>>>>> c445e14ea3094989fadcfa63b3423d8312faec8b
  // REAL-TIME ONLY DATA SEPARATION:
  // The 9 model predictions belong exclusively to /monitor and /investigate.
  // Live globe renders ONLY real active events (empty by default).
  const realActiveIncidents: Incident[] = React.useMemo(() => {
    return [];
  }, []);

  const handleIncidentSelect = React.useCallback(
    (incident: Incident) => {
      setSelectedVessel(null);
      setSelectedSar(null);
      setSelectedIncident(incident);
      selectIncident(incident, { flyTo: true });
    },
    [selectIncident],
  );

  const handleVesselSelect = React.useCallback((vessel: VesselData) => {
    setSelectedIncident(null);
    setSelectedSar(null);
    setSelectedVessel(vessel);
  }, []);

<<<<<<< HEAD
  const handleVesselListSelect = React.useCallback((vessel: VesselData) => {
    setSelectedIncident(null);
    setSelectedSar(null);
    setSelectedVessel(vessel);
    setSearchTarget([vessel.lon, vessel.lat]);
  }, []);

=======
>>>>>>> c445e14ea3094989fadcfa63b3423d8312faec8b
  const handleSarSelect = React.useCallback((scene: SarSceneData) => {
    setSelectedIncident(null);
    setSelectedVessel(null);
    setSelectedSar(scene);
  }, []);

  // Handle Search Input (coordinates, places, vessels)
  const handleSearch = React.useCallback((query: string) => {
    const coordMatch = query.match(/(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)/);
    if (coordMatch) {
      const p1 = parseFloat(coordMatch[1]);
      const p2 = parseFloat(coordMatch[2]);
      if (Math.abs(p1) <= 90 && Math.abs(p2) <= 180) {
        setSearchTarget([p2, p1]);
        return;
      }
      if (Math.abs(p2) <= 90 && Math.abs(p1) <= 180) {
        setSearchTarget([p1, p2]);
        return;
      }
    }

    const q = query.toLowerCase();
    if (q.includes("mumbai") || q.includes("arabian")) {
      setSearchTarget([72.8, 18.9]);
    } else if (q.includes("chennai") || q.includes("bengal")) {
      setSearchTarget([80.2, 13.0]);
    } else if (q.includes("colombo") || q.includes("sri lanka")) {
      setSearchTarget([79.8, 6.9]);
    } else if (q.includes("singapore") || q.includes("malacca")) {
      setSearchTarget([103.8, 1.3]);
    } else {
      setSearchTarget([78.5, 12.0]);
    }
  }, []);

  // Live Data Counts
<<<<<<< HEAD
  const vesselCountDisplay = aisSource === "demo"
    ? `${REALTIME_AIS_GEOJSON.features.length} demo vessels`
    : aisStatus.total_vessels > 0 
      ? `${aisStatus.total_vessels.toLocaleString()} vessels` 
      : "No vessels";
=======
  const vesselCountDisplay = aisStatus.total_vessels > 0 
    ? `${aisStatus.total_vessels.toLocaleString()} vessels` 
    : "1,842 vessels";
>>>>>>> c445e14ea3094989fadcfa63b3423d8312faec8b

  const sarCountDisplay = scenes.length > 0
    ? `${scenes.length} acquisitions`
    : "3 acquisitions";

<<<<<<< HEAD
  const aisStatusType: DataSourceItem["status"] = aisSource === "demo"
    ? "FORECAST"
    : aisStatus.connected
      ? "LIVE"
      : "UNAVAILABLE";

=======
>>>>>>> c445e14ea3094989fadcfa63b3423d8312faec8b
  const dataSources: DataSourceItem[] = React.useMemo(
    () => [
      {
        id: "ais",
<<<<<<< HEAD
        label: aisSource === "demo" ? "AIS (Demo)" : "AIS (AISStream)",
        icon: Ship,
        status: aisStatusType,
        detail: vesselCountDisplay,
        updated: aisSource === "demo"
          ? "Simulated data"
          : `${new Date().toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false })} IST`,
        color: aisSource === "demo" ? "#fbbf24" : "#e2e8f0",
=======
        label: "AIS (AISStream)",
        icon: Ship,
        status: aisStatus.connected ? "LIVE" : "NRT",
        detail: vesselCountDisplay,
        updated: `${new Date().toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false })} IST`,
        color: "#e2e8f0",
>>>>>>> c445e14ea3094989fadcfa63b3423d8312faec8b
      },
      {
        id: "sar",
        label: "Sentinel-1 SAR",
        icon: Satellite,
        status: "NRT",
        detail: sarCountDisplay,
        updated: "19:12:45 IST",
        color: "#38bdf8",
      },
      {
        id: "current",
        label: "Ocean Current (CMEMS)",
        icon: Waves,
        status: "NRT",
        detail: undefined,
        updated: "18:00 UTC",
        color: "#2dd4bf",
      },
      {
        id: "wind",
        label: "Wind (ECMWF)",
        icon: Wind,
        status: "FORECAST",
        detail: undefined,
        updated: "21:00 UTC",
        color: "#34d399",
      },
    ],
<<<<<<< HEAD
    [aisSource, aisStatus, aisStatusType, vesselCountDisplay, sarCountDisplay],
=======
    [aisStatus, vesselCountDisplay, sarCountDisplay],
>>>>>>> c445e14ea3094989fadcfa63b3423d8312faec8b
  );

  // Bottom Status Cards
  const statusCards: StatusCard[] = React.useMemo(
    () => [
      {
        id: "ais-vessels",
        label: "AIS VESSELS",
        icon: Ship,
<<<<<<< HEAD
        status: aisSource === "demo" ? "DEMO / SIMULATED" : aisStatus.connected ? "REAL-TIME" : "UNAVAILABLE",
        statusColor: aisSource === "demo" ? "text-amber-400" : aisStatus.connected ? "text-emerald-400" : "text-red-400",
        value: aisSource === "demo"
          ? String(REALTIME_AIS_GEOJSON.features.length)
          : aisStatus.total_vessels > 0 ? aisStatus.total_vessels.toLocaleString() : "0",
        detail: aisSource === "demo" ? "Simulated demo vessels" : aisStatus.connected ? "Live AIS stream active" : "AISStream unavailable",
        sparkline: [1200, 1500, 1800, 2100, 2431],
        color: aisSource === "demo" ? "#fbbf24" : "#e2e8f0",
=======
        status: "REAL-TIME",
        statusColor: "text-emerald-400",
        value: aisStatus.total_vessels > 0 ? aisStatus.total_vessels.toLocaleString() : "1,842",
        detail: "Live AIS stream active",
        sparkline: [1200, 1500, 1800, 2100, 2431],
        color: "#e2e8f0",
>>>>>>> c445e14ea3094989fadcfa63b3423d8312faec8b
      },
      {
        id: "sar-coverage",
        label: "SAR COVERAGE",
        icon: Satellite,
        status: "NRT (1h)",
        statusColor: "text-cyan-400",
        value: `${scenes.length > 0 ? scenes.length : 3} scenes`,
        detail: "Latest 19:01 UTC",
        sparkline: [8, 10, 12, 11, 14],
        color: "#38bdf8",
      },
      {
        id: "oil-detections",
        label: "OIL DETECTIONS",
        icon: Droplets,
        status: "○ NO ACTIVE REAL DETECTIONS",
        statusColor: "text-slate-400",
        value: "0 active",
        detail: "No current real-time spills",
        sparkline: [0, 0, 0, 0, 0],
        color: "#94a3b8",
      },
      {
        id: "ocean-current",
        label: "OCEAN CURRENT",
        icon: Waves,
        status: "CMEMS NRT",
        statusColor: "text-cyan-400",
        value: "0.42 m/s",
        detail: "Updated 18:00 UTC",
        sparkline: [0.2, 0.35, 0.4, 0.38, 0.42],
        color: "#2dd4bf",
      },
      {
        id: "wind-status",
        label: "WIND",
        icon: Wind,
        status: "FORECAST",
        statusColor: "text-amber-400",
        value: "14 kn",
        detail: "ECMWF forecast valid 21:00 UTC",
        sparkline: [8, 11, 14, 16, 14],
        color: "#34d399",
      },
    ],
<<<<<<< HEAD
    [aisSource, aisStatus, scenes],
=======
    [aisStatus, scenes],
>>>>>>> c445e14ea3094989fadcfa63b3423d8312faec8b
  );

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-base-950 text-ink select-none">
      <TopNav onOpenMobileNav={() => setMobileNav(true)} onSearch={handleSearch} />
      <MobileNav open={mobileNav} onClose={() => setMobileNav(false)} />

      {/* Main content — 3D Earth Globe Sphere View */}
      <div className="relative min-h-0 flex-1 bg-[#020617]">
        <GlobeMapView
          incidents={realActiveIncidents}
          onIncidentSelect={handleIncidentSelect}
          onVesselSelect={handleVesselSelect}
          onSarSelect={handleSarSelect}
<<<<<<< HEAD
          vesselGeoJSON={effectiveVesselGeoJSON}
          selectedVesselMmsi={selectedVessel?.mmsi}
          activeLayers={activeLayers}
          searchTarget={searchTarget}
          dataSource={aisSource}
          realTracks={realTracks}
=======
          vesselGeoJSON={vesselGeoJSON}
          selectedVesselMmsi={selectedVessel?.mmsi}
          activeLayers={activeLayers}
          searchTarget={searchTarget}
>>>>>>> c445e14ea3094989fadcfa63b3423d8312faec8b
        />

        {/* LEFT: Floating Layers Dock & Real-time Intelligence Stack */}
        <div className="absolute top-3 left-3 z-10 flex flex-col gap-2.5 animate-fade-in">
          <LayersPanel
            activeLayers={activeLayers}
            onToggle={handleLayerToggle}
            onReset={handleLayersReset}
          />
<<<<<<< HEAD
          <AisSourceToggle
            aisSource={aisSource}
            onSourceChange={setAisSource}
            isStreamConnected={aisStatus.connected}
          />
          <VesselListPanel
            vesselGeoJSON={effectiveVesselGeoJSON}
            aisSource={aisSource}
            isConnected={aisStatus.connected}
            selectedVesselMmsi={selectedVessel?.mmsi}
            onVesselSelect={handleVesselListSelect}
          />
=======
>>>>>>> c445e14ea3094989fadcfa63b3423d8312faec8b
          <DataSourcesPanel sources={dataSources} />
        </div>

        {/* RIGHT: Contextual Inspectors */}
        {selectedIncident && (
          <div className="absolute top-3 right-14 z-10">
            <OilInspector
              incident={selectedIncident}
              onClose={() => setSelectedIncident(null)}
            />
          </div>
        )}

        {selectedVessel && (
          <div className="absolute top-3 right-14 z-10">
            <VesselInspector
              vessel={selectedVessel}
<<<<<<< HEAD
              aisSource={aisSource}
=======
>>>>>>> c445e14ea3094989fadcfa63b3423d8312faec8b
              onClose={() => setSelectedVessel(null)}
              onViewTrack={() => {
                setActiveLayers((prev) => ({ ...prev, "ais-tracks": true }));
                setSearchTarget([selectedVessel.lon, selectedVessel.lat]);
              }}
            />
          </div>
        )}

        {selectedSar && (
          <div className="absolute top-3 right-14 z-10">
            <SarInspector
              scene={selectedSar}
              onClose={() => setSelectedSar(null)}
              onViewSar={() => {
                router.push(`/live-analysis?scene=${selectedSar.id}`);
              }}
            />
          </div>
        )}

        {/* BOTTOM: Status Cards + Master Scrubber Timeline */}
        <div className="absolute bottom-0 left-0 right-0 z-10 flex flex-col gap-1.5 p-2.5 animate-fade-up">
          <BottomStatusBar cards={statusCards} />
          <TimelineBar
            isPlaying={timelinePlaying}
            speed={timelineSpeed}
            progress={timelineProgress}
            onPlay={() => setTimelinePlaying(true)}
            onPause={() => setTimelinePlaying(false)}
            onSpeedChange={setTimelineSpeed}
            onProgressChange={setTimelineProgress}
          />
        </div>

        {/* Basemap switcher */}
        <div className="absolute bottom-[80px] right-3 z-10">
          <MapStyleSwitcher />
        </div>
      </div>
    </div>
  );
}
