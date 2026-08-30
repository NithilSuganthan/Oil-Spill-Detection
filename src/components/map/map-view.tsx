"use client";

import * as React from "react";
import maplibregl, {
  type Map as MapLibreMap,
  type StyleSpecification,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { AttributionResult, Incident, SatelliteScene, DriftResult } from "@/lib/types";
import { useAppStore } from "@/lib/store/use-app-store";
import {
  COASTAL_CITIES,
  DEFAULT_CENTER,
  DEFAULT_ZOOM,
  INDIA_BOUNDS,
  SEA_LABELS,
  buildFallbackStyle,
  getMapStyleUrl,
} from "./map-config";
import { LEVEL_COLORS, detectionFillExpression } from "./spill-style";
import { MapControls, LayerToggleButton } from "./map-controls";
import { LayerPanel, MapLegend } from "./layer-panel";

export interface MapViewProps {
  incidents?: Incident[];
  scenes?: SatelliteScene[];
  drift?: DriftResult | null;
  attribution?: AttributionResult | null;
  className?: string;
}

function bboxPolygon(scene: SatelliteScene): GeoJSON.Feature<GeoJSON.Polygon> {
  const b = scene.footprint;
  return {
    type: "Feature",
    properties: { id: scene.id },
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [b.west, b.south],
          [b.east, b.south],
          [b.east, b.north],
          [b.west, b.north],
          [b.west, b.south],
        ],
      ],
    },
  };
}

export function MapView({ incidents = [], scenes = [], drift = null, attribution = null, className }: MapViewProps) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const mapRef = React.useRef<MapLibreMap | null>(null);
  const readyRef = React.useRef(false);
  const [ready, setReady] = React.useState(false);
  const [fullscreen, setFullscreen] = React.useState(false);
  const [layersOpen, setLayersOpen] = React.useState(false);
  const [legendVisible, setLegendVisible] = React.useState(true);

  const selectedId = useAppStore((s) => s.selectedIncidentId);
  const selectIncident = useAppStore((s) => s.selectIncident);
  const activeLayers = useAppStore((s) => s.activeLayers);
  const flyTo = useAppStore((s) => s.flyTo);

  const dataRef = React.useRef({ incidents, scenes, drift, attribution });
  dataRef.current = { incidents, scenes, drift, attribution };

  /* ---------- init ---------- */
  React.useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: getMapStyleUrl(),
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
      minZoom: 3,
      maxZoom: 12,
      attributionControl: { compact: true },
      dragRotate: false,
      pitchWithRotate: false,
    });
    mapRef.current = map;

    map.on("error", (e) => {
      // Basemap failure fallback (keeps the ops UI usable offline / blocked tiles)
      const sourceId = (e as unknown as { sourceId?: string }).sourceId;
      if (!readyRef.current && sourceId === undefined && e.error) {
        try {
          map.setStyle(buildFallbackStyle());
          map.once("style.load", () => {
            addDataLayers(map);
            applyVisibility(map, useAppStore.getState().activeLayers);
            readyRef.current = true;
            setReady(true);
          });
        } catch {
          /* ignore */
        }
      }
    });

    map.on("load", () => {
      addDataLayers(map);
      applyVisibility(
        map,
        useAppStore.getState().activeLayers
      );
      readyRef.current = true;
      setReady(true);
    });

    const onFsChange = () => setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onFsChange);

    return () => {
      document.removeEventListener("fullscreenchange", onFsChange);
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function addDataLayers(map: MapLibreMap) {
    if (map.getSource("detections")) return;

    map.addSource("detections", {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });
    map.addSource("coverage", {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });
    map.addSource("poi", {
      type: "geojson",
      data: {
        type: "FeatureCollection",
        features: [
          ...COASTAL_CITIES.map((c) => ({
            type: "Feature" as const,
            properties: { name: c.name, kind: "city" },
            geometry: { type: "Point" as const, coordinates: [c.lon, c.lat] },
          })),
          ...SEA_LABELS.map((c) => ({
            type: "Feature" as const,
            properties: { name: c.name, kind: "sea" },
            geometry: { type: "Point" as const, coordinates: [c.lon, c.lat] },
          })),
        ],
      },
    });

    // Drift sources
    map.addSource("drift-trajectories", {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });
    map.addSource("drift-source-points", {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });

    // AIS sources
    map.addSource("ais-vessels", {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });
    map.addSource("ais-tracks", {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });
    map.addSource("candidate-vessels", {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });

    map.addLayer({
      id: "coverage-fill",
      type: "fill",
      source: "coverage",
      paint: {
        "fill-color": "#38bdf8",
        "fill-opacity": 0.04,
      },
    });
    map.addLayer({
      id: "coverage-line",
      type: "line",
      source: "coverage",
      paint: {
        "line-color": "#38bdf8",
        "line-width": 1,
        "line-dasharray": [4, 3],
        "line-opacity": 0.5,
      },
    });

    map.addLayer({
      id: "detection-pulse",
      type: "fill",
      source: "detections",
      filter: ["==", ["get", "id"], "__none__"],
      paint: {
        "fill-color": detectionFillExpression(null) as never,
        "fill-opacity": 0.35,
      },
    });
    map.addLayer({
      id: "detection-fill",
      type: "fill",
      source: "detections",
      paint: {
        "fill-color": detectionFillExpression(null) as never,
        "fill-opacity": [
          "case",
          ["==", ["get", "id"], useAppStore.getState().selectedIncidentId ?? "__none__"],
          0.5,
          0.26,
        ],
      },
    });
    map.addLayer({
      id: "detection-outline",
      type: "line",
      source: "detections",
      paint: {
        "line-color": [
          "match",
          ["get", "level"],
          "HIGH",
          LEVEL_COLORS.HIGH.line,
          "MEDIUM",
          LEVEL_COLORS.MEDIUM.line,
          LEVEL_COLORS.LOW.line,
        ] as never,
        "line-width": [
          "case",
          ["==", ["get", "id"], useAppStore.getState().selectedIncidentId ?? "__none__"],
          3,
          1.4,
        ],
        "line-opacity": 0.95,
      },
    });

    map.addLayer({
      id: "sea-labels",
      type: "symbol",
      source: "poi",
      filter: ["==", ["get", "kind"], "sea"],
      layout: {
        "text-field": ["get", "name"],
        "text-font": ["Open Sans Regular"],
        "text-size": 11,
        "text-letter-spacing": 0.28,
      },
      paint: { "text-color": "#4a6076" },
    });
    map.addLayer({
      id: "city-dot",
      type: "circle",
      source: "poi",
      filter: ["==", ["get", "kind"], "city"],
      paint: {
        "circle-radius": 2.5,
        "circle-color": "#93a4bd",
        "circle-stroke-width": 1,
        "circle-stroke-color": "#0a1120",
      },
    });
    map.addLayer({
      id: "city-labels",
      type: "symbol",
      source: "poi",
      minzoom: 4.4,
      filter: ["==", ["get", "kind"], "city"],
      layout: {
        "text-field": ["get", "name"],
        "text-font": ["Open Sans Regular"],
        "text-size": 10,
        "text-offset": [0, 1.1],
        "text-anchor": "top",
      },
      paint: { "text-color": "#7c8fa8", "text-halo-color": "#070c16", "text-halo-width": 1.2 },
    });

    // Drift trajectory lines
    map.addLayer({
      id: "drift-trajectory-lines",
      type: "line",
      source: "drift-trajectories",
      layout: {
        "line-cap": "round",
        "line-join": "round",
      },
      paint: {
        "line-color": "#22d3ee",
        "line-width": 1.5,
        "line-opacity": 0.5,
      },
    });

    // Source estimate uncertainty circle
    map.addLayer({
      id: "drift-uncertainty",
      type: "circle",
      source: "drift-source-points",
      filter: ["==", ["get", "kind"], "uncertainty"],
      paint: {
        "circle-radius": 8,
        "circle-color": "#22d3ee",
        "circle-opacity": 0.15,
        "circle-stroke-color": "#22d3ee",
        "circle-stroke-width": 1,
        "circle-stroke-opacity": 0.3,
      },
    });

    // Source estimate point
    map.addLayer({
      id: "drift-source-point",
      type: "circle",
      source: "drift-source-points",
      filter: ["==", ["get", "kind"], "source"],
      paint: {
        "circle-radius": 5,
        "circle-color": "#f59e0b",
        "circle-stroke-color": "#fff",
        "circle-stroke-width": 1.5,
      },
    });

    // Slick observation point
    map.addLayer({
      id: "drift-slick-point",
      type: "circle",
      source: "drift-source-points",
      filter: ["==", ["get", "kind"], "slick"],
      paint: {
        "circle-radius": 5,
        "circle-color": "#ef4444",
        "circle-stroke-color": "#fff",
        "circle-stroke-width": 1.5,
      },
    });

    // AIS vessel track lines
    map.addLayer({
      id: "ais-track-lines",
      type: "line",
      source: "ais-tracks",
      layout: {
        "line-cap": "round",
        "line-join": "round",
      },
      paint: {
        "line-color": "#60a5fa",
        "line-width": 1,
        "line-opacity": 0.4,
      },
    });

    // AIS vessel points (all vessels in search window)
    map.addLayer({
      id: "ais-vessel-points",
      type: "circle",
      source: "ais-vessels",
      paint: {
        "circle-radius": 4,
        "circle-color": "#3b82f6",
        "circle-stroke-color": "#1e3a5f",
        "circle-stroke-width": 1,
        "circle-opacity": 0.7,
      },
    });

    // Candidate vessel points (highlighted, larger)
    map.addLayer({
      id: "candidate-vessel-points",
      type: "circle",
      source: "candidate-vessels",
      paint: {
        "circle-radius": [
          "case",
          ["==", ["get", "rank"], 1],
          7,
          5,
        ],
        "circle-color": [
          "case",
          ["==", ["get", "rank"], 1],
          "#f59e0b",
          "#fb923c",
        ],
        "circle-stroke-color": "#fff",
        "circle-stroke-width": [
          "case",
          ["==", ["get", "rank"], 1],
          2,
          1,
        ],
      },
    });

    // Candidate vessel labels (name for top candidates)
    map.addLayer({
      id: "candidate-vessel-labels",
      type: "symbol",
      source: "candidate-vessels",
      filter: ["==", ["get", "rank"], 1],
      layout: {
        "text-field": ["get", "name"],
        "text-font": ["Open Sans Regular"],
        "text-size": 10,
        "text-offset": [0, 1.3],
        "text-anchor": "top",
      },
      paint: {
        "text-color": "#fbbf24",
        "text-halo-color": "#070c16",
        "text-halo-width": 1.2,
      },
    });

    map.on("click", "detection-fill", (e) => {
      const f = e.features?.[0];
      const id = f?.properties?.id as string | undefined;
      if (!id) return;
      const inc = dataRef.current.incidents.find((i) => i.id === id);
      if (inc) selectIncident(inc);
    });
    map.on("mouseenter", "detection-fill", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "detection-fill", () => {
      map.getCanvas().style.cursor = "";
    });
  }

  /* ---------- sync detection data ---------- */
  React.useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const src = map.getSource("detections") as maplibregl.GeoJSONSource | undefined;
    src?.setData({
      type: "FeatureCollection",
      features: incidents.map((inc) => ({
        type: "Feature" as const,
        id: undefined,
        properties: {
          id: inc.id,
          level: inc.level,
          confidence: inc.confidence,
        },
        geometry: inc.geometry,
      })),
    });
  }, [incidents, ready]);

  React.useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const src = map.getSource("coverage") as maplibregl.GeoJSONSource | undefined;
    src?.setData({
      type: "FeatureCollection",
      features: scenes.map(bboxPolygon),
    });
  }, [scenes, ready]);

  // Sync drift data
  React.useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    // Trajectory lines
    const trajSrc = map.getSource("drift-trajectories") as maplibregl.GeoJSONSource | undefined;
    if (drift) {
      const trajFeatures: GeoJSON.Feature[] = [];
      for (let i = 0; i < Math.min(10, drift.sourcePoints.length); i++) {
        const pts = drift.sourcePoints;
        // Create trajectory lines from source to slick
        if (pts[i]) {
          trajFeatures.push({
            type: "Feature",
            properties: { index: i },
            geometry: {
              type: "LineString",
              coordinates: [
                [drift.sourceLongitude, drift.sourceLatitude],
                [drift.slickLongitude, drift.slickLatitude],
              ],
            },
          });
        }
      }
      trajSrc?.setData({ type: "FeatureCollection", features: trajFeatures });
    } else {
      trajSrc?.setData({ type: "FeatureCollection", features: [] });
    }

    // Source points (source, slick, uncertainty)
    const ptsSrc = map.getSource("drift-source-points") as maplibregl.GeoJSONSource | undefined;
    if (drift) {
      const uncertaintyKm = drift.uncertaintyKm;
      const approxRadiusPx = Math.min(20, Math.max(6, uncertaintyKm / 2));
      ptsSrc?.setData({
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            properties: { kind: "slick", label: "Observed slick" },
            geometry: { type: "Point", coordinates: [drift.slickLongitude, drift.slickLatitude] },
          },
          {
            type: "Feature",
            properties: { kind: "source", label: `Estimated source (±${uncertaintyKm.toFixed(1)} km)` },
            geometry: { type: "Point", coordinates: [drift.sourceLongitude, drift.sourceLatitude] },
          },
          {
            type: "Feature",
            properties: { kind: "uncertainty", radius: approxRadiusPx },
            geometry: { type: "Point", coordinates: [drift.sourceLongitude, drift.sourceLatitude] },
          },
        ],
      });
    } else {
      ptsSrc?.setData({ type: "FeatureCollection", features: [] });
    }
  }, [drift, ready]);

  // Sync AIS data to map
  React.useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    // AIS vessel points (all vessels from attribution)
    const aisSrc = map.getSource("ais-vessels") as maplibregl.GeoJSONSource | undefined;
    const trackSrc = map.getSource("ais-tracks") as maplibregl.GeoJSONSource | undefined;
    const candidateSrc = map.getSource("candidate-vessels") as maplibregl.GeoJSONSource | undefined;

    if (attribution && attribution.candidates.length > 0) {
      // All AIS vessels as points (offset from centroid for visibility)
      const aisFeatures: GeoJSON.Feature[] = attribution.candidates.map((c, idx) => {
        const offsetLat = (idx + 1) * 0.008;
        const offsetLon = (idx + 1) * 0.012;
        return {
          type: "Feature" as const,
          properties: {
            mmsi: c.mmsi,
            name: c.vesselName || `MMSI ${c.mmsi}`,
            type: c.vesselType,
            score: c.attributionScore,
          },
          geometry: {
            type: "Point" as const,
            coordinates: [
              (attribution.searchWindow?.centerLon ?? 0) + offsetLon,
              (attribution.searchWindow?.centerLat ?? 0) + offsetLat,
            ],
          },
        };
      });
      aisSrc?.setData({ type: "FeatureCollection", features: aisFeatures });

      // Track lines from each vessel to incident centroid
      const trackFeatures: GeoJSON.Feature[] = attribution.candidates.map((c, idx) => {
        const offsetLat = (idx + 1) * 0.008;
        const offsetLon = (idx + 1) * 0.012;
        return {
          type: "Feature" as const,
          properties: { mmsi: c.mmsi },
          geometry: {
            type: "LineString" as const,
            coordinates: [
              [
                (attribution.searchWindow?.centerLon ?? 0) + offsetLon,
                (attribution.searchWindow?.centerLat ?? 0) + offsetLat,
              ],
              [
                attribution.searchWindow?.centerLon ?? 0,
                attribution.searchWindow?.centerLat ?? 0,
              ],
            ],
          },
        };
      });
      trackSrc?.setData({ type: "FeatureCollection", features: trackFeatures });

      // Candidate vessels (top 5, highlighted)
      const candidateFeatures: GeoJSON.Feature[] = attribution.candidates.slice(0, 5).map((c, idx) => {
        const offsetLat = (idx + 1) * 0.008;
        const offsetLon = (idx + 1) * 0.012;
        return {
          type: "Feature" as const,
          properties: {
            mmsi: c.mmsi,
            name: c.vesselName || `MMSI ${c.mmsi}`,
            type: c.vesselType,
            score: c.attributionScore,
            rank: idx + 1,
          },
          geometry: {
            type: "Point" as const,
            coordinates: [
              (attribution.searchWindow?.centerLon ?? 0) + offsetLon,
              (attribution.searchWindow?.centerLat ?? 0) + offsetLat,
            ],
          },
        };
      });
      candidateSrc?.setData({ type: "FeatureCollection", features: candidateFeatures });
    } else {
      aisSrc?.setData({ type: "FeatureCollection", features: [] });
      trackSrc?.setData({ type: "FeatureCollection", features: [] });
      candidateSrc?.setData({ type: "FeatureCollection", features: [] });
    }
  }, [attribution, ready]);

  /* ---------- selection highlight + pulse ---------- */
  React.useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    map.setFilter(
      "detection-pulse",
      ["==", ["get", "id"], selectedId ?? "__none__"] as never
    );
    map.setPaintProperty(
      "detection-fill",
      "fill-color",
      detectionFillExpression(selectedId) as never
    );
    map.setPaintProperty("detection-fill", "fill-opacity", [
      "case",
      ["==", ["get", "id"], selectedId ?? "__none__"],
      0.5,
      0.26,
    ] as never);
    map.setPaintProperty("detection-outline", "line-width", [
      "case",
      ["==", ["get", "id"], selectedId ?? "__none__"],
      3,
      1.4,
    ] as never);
  }, [selectedId, ready]);

  React.useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !selectedId) return;
    let raf = 0;
    const t0 = performance.now();
    const animate = (t: number) => {
      const phase = ((t - t0) / 1400) % 1;
      const opacity = 0.32 * (1 - phase);
      map.setPaintProperty("detection-pulse", "fill-opacity", opacity);
      raf = requestAnimationFrame(animate);
    };
    raf = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf);
  }, [selectedId, ready]);

  /* ---------- layer visibility ---------- */
  React.useEffect(() => {
    if (!ready) return;
    const map = mapRef.current;
    if (map) applyVisibility(map, activeLayers);
  }, [activeLayers, ready]);

  function applyVisibility(map: MapLibreMap, layers: Record<string, boolean>) {
    const visibility = (on: boolean) => (on ? "visible" : "none");
    map.setLayoutProperty("detection-pulse", "visibility", visibility(layers["detections"]));
    map.setLayoutProperty("detection-fill", "visibility", visibility(layers["detections"]));
    map.setLayoutProperty("detection-outline", "visibility", visibility(layers["detections"]));
    map.setLayoutProperty("coverage-fill", "visibility", visibility(layers["scene-coverage"]));
    map.setLayoutProperty("coverage-line", "visibility", visibility(layers["scene-coverage"]));
    map.setLayoutProperty("drift-trajectory-lines", "visibility", visibility(layers["drift-trajectories"]));
    map.setLayoutProperty("drift-uncertainty", "visibility", visibility(layers["source-probability"]));
    map.setLayoutProperty("drift-source-point", "visibility", visibility(layers["source-probability"]));
    map.setLayoutProperty("drift-slick-point", "visibility", visibility(layers["source-probability"]));
    map.setLayoutProperty("ais-vessel-points", "visibility", visibility(layers["ais-vessels"]));
    map.setLayoutProperty("ais-track-lines", "visibility", visibility(layers["ais-tracks"]));
    map.setLayoutProperty("candidate-vessel-points", "visibility", visibility(layers["candidate-vessels"]));
    map.setLayoutProperty("candidate-vessel-labels", "visibility", visibility(layers["candidate-vessels"]));
  }

  /* ---------- external fly-to requests ---------- */
  React.useEffect(() => {
    if (!flyTo || !ready) return;
    mapRef.current?.flyTo({
      center: [flyTo.lon, flyTo.lat],
      zoom: flyTo.zoom ?? DEFAULT_ZOOM + 3.5,
      speed: 1.1,
      curve: 1.6,
      essential: true,
    });
  }, [flyTo, ready]);

  /* ---------- control actions ---------- */
  const zoomBy = (delta: number) =>
    mapRef.current?.easeTo({ zoom: (mapRef.current?.getZoom() ?? 4) + delta, duration: 250 });

  const resetView = () =>
    mapRef.current?.fitBounds(INDIA_BOUNDS, { padding: 48, duration: 700 });

  const locateCamera = () => {
    const sel = dataRef.current.incidents.find((i) => i.id === selectedId);
    if (sel) {
      mapRef.current?.flyTo({
        center: [sel.centroid.lon, sel.centroid.lat],
        zoom: 9,
        duration: 800,
      });
    } else {
      resetView();
    }
  };

  const toggleFullscreen = () => {
    const el = containerRef.current?.parentElement;
    if (!document.fullscreenElement) el?.requestFullscreen?.();
    else document.exitFullscreen();
  };

  return (
    <div className={className ? `relative ${className}` : "relative h-full w-full"}>
      <div ref={containerRef} className="h-full w-full" role="application" aria-label="Oil spill detection map of Indian waters" />

      <MapControls
        onZoomIn={() => zoomBy(0.8)}
        onZoomOut={() => zoomBy(-0.8)}
        onResetView={resetView}
        onLocate={locateCamera}
        onToggleFullscreen={toggleFullscreen}
        isFullscreen={fullscreen}
      />
      <LayerToggleButton active={layersOpen} onClick={() => setLayersOpen((o) => !o)} />
      <LayerPanel open={layersOpen} onClose={() => setLayersOpen(false)} />
      <MapLegend visible={legendVisible && ready} />

      <button
        onClick={() => setLegendVisible((v) => !v)}
        aria-label={legendVisible ? "Hide legend" : "Show legend"}
        className="focus-ring absolute bottom-8 right-[52px] z-10 rounded border border-line bg-base-900/90 px-2 py-1 font-mono text-[9px] uppercase tracking-widest text-ink-faint backdrop-blur hover:text-ink"
      >
        {legendVisible ? "Hide" : "Legend"}
      </button>

      {!ready && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-base-950/80">
          <div className="flex flex-col items-center gap-3">
            <div className="h-9 w-9 animate-spin rounded-full border border-transparent border-t-signal-cyan border-r-signal-cyan/30" />
            <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-ink-faint">
              Initializing tactical map…
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
