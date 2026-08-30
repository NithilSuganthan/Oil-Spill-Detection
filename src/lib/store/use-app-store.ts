"use client";

import { create } from "zustand";
import type {
  ConfidenceLevel,
  Incident,
  MapLayerDef,
  MapLayerId,
  TimeRange,
} from "@/lib/types";

export const MAP_LAYERS: MapLayerDef[] = [
  { id: "detections", label: "Oil Spill Detections", available: true, phase: 1, defaultOn: true },
  { id: "scene-coverage", label: "Satellite Scene Coverage", available: true, phase: 1, defaultOn: false },
  { id: "ais-vessels", label: "AIS Vessels", available: true, phase: 3, defaultOn: false },
  { id: "ais-tracks", label: "AIS Tracks", available: true, phase: 3, defaultOn: false },
  { id: "drift-trajectories", label: "Drift Trajectories", available: true, phase: 5, defaultOn: false },
  { id: "source-probability", label: "Source Uncertainty", available: true, phase: 5, defaultOn: false },
  { id: "candidate-vessels", label: "Candidate Vessels", available: true, phase: 4, defaultOn: false },
];

export interface FlyToTarget {
  lon: number;
  lat: number;
  zoom?: number;
  nonce: number;
}

export type ViewerTab = "sar" | "prediction" | "overlay";

interface AppState {
  selectedIncidentId: string | null;
  selectedIncident: Incident | null;
  detailsOpen: boolean;
  viewerIncidentId: string | null;
  viewerTab: ViewerTab;

  filters: {
    search: string;
    levels: ConfidenceLevel[];
    timeRange: TimeRange;
    region: string;
  };

  activeLayers: Record<MapLayerId, boolean>;
  flyTo: FlyToTarget | null;
  sidebarOpenMobile: boolean;
  detailsOpenMobile: boolean;

  selectIncident: (incident: Incident, opts?: { flyTo?: boolean }) => void;
  clearSelection: () => void;
  openViewer: (id: string, tab?: ViewerTab) => void;
  closeViewer: () => void;
  setViewerTab: (tab: ViewerTab) => void;
  setSearch: (q: string) => void;
  toggleLevel: (l: ConfidenceLevel) => void;
  setTimeRange: (t: TimeRange) => void;
  setRegion: (r: string) => void;
  resetFilters: () => void;
  toggleLayer: (id: MapLayerId) => void;
  requestFlyTo: (lon: number, lat: number, zoom?: number) => void;
  setSidebarOpenMobile: (v: boolean) => void;
  setDetailsOpenMobile: (v: boolean) => void;
}

const defaultLayers = Object.fromEntries(
  MAP_LAYERS.map((l) => [l.id, l.defaultOn])
) as Record<MapLayerId, boolean>;

const defaultFilters = {
  search: "",
  levels: [] as ConfidenceLevel[],
  timeRange: "24h" as TimeRange,
  region: "All India Region",
};

export const useAppStore = create<AppState>((set) => ({
  selectedIncidentId: null,
  selectedIncident: null,
  detailsOpen: false,
  viewerIncidentId: null,
  viewerTab: "overlay",

  filters: defaultFilters,
  activeLayers: defaultLayers,
  flyTo: null,
  sidebarOpenMobile: false,
  detailsOpenMobile: false,

  selectIncident: (incident, opts) =>
    set((s) => ({
      selectedIncidentId: incident.id,
      selectedIncident: incident,
      detailsOpen: true,
      detailsOpenMobile: true,
      flyTo:
        opts?.flyTo === false
          ? s.flyTo
          : { lon: incident.centroid.lon, lat: incident.centroid.lat, zoom: 8.5, nonce: Date.now() },
    })),

  clearSelection: () =>
    set({ selectedIncidentId: null, selectedIncident: null, detailsOpen: false }),

  openViewer: (id, tab) =>
    set((s) => ({ viewerIncidentId: id, viewerTab: tab ?? s.viewerTab })),
  closeViewer: () => set({ viewerIncidentId: null }),
  setViewerTab: (viewerTab) => set({ viewerTab }),

  setSearch: (search) => set((s) => ({ filters: { ...s.filters, search } })),
  toggleLevel: (level) =>
    set((s) => {
      const has = s.filters.levels.includes(level);
      return {
        filters: {
          ...s.filters,
          levels: has
            ? s.filters.levels.filter((l) => l !== level)
            : [...s.filters.levels, level],
        },
      };
    }),
  setTimeRange: (timeRange) => set((s) => ({ filters: { ...s.filters, timeRange } })),
  setRegion: (region) => set((s) => ({ filters: { ...s.filters, region } })),
  resetFilters: () => set({ filters: defaultFilters }),

  toggleLayer: (id) =>
    set((s) => ({ activeLayers: { ...s.activeLayers, [id]: !s.activeLayers[id] } })),

  requestFlyTo: (lon, lat, zoom = 6) =>
    set({ flyTo: { lon, lat, zoom, nonce: Date.now() } }),

  setSidebarOpenMobile: (v) => set({ sidebarOpenMobile: v }),
  setDetailsOpenMobile: (v) => set({ detailsOpenMobile: v }),
}));
