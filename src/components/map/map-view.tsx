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
  /** Globe or mercator projection. Defaults to store projectionMode. */
  projectionMode?: "globe" | "mercator";
  /** Center for initial view [lon, lat]. Defaults to India center. */
  initialCenter?: [number, number];
  /** Initial zoom level. Defaults to 4.55. */
  initialZoom?: number;
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

export function MapView({
  incidents = [],
  scenes = [],
  drift = null,
  attribution = null,
  className,
  projectionMode: projectionModeProp,
  initialCenter,
  initialZoom,
}: MapViewProps) {
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
  const storeProjectionMode = useAppStore((s) => s.projectionMode);

  const projectionMode = projectionModeProp ?? storeProjectionMode;
  const center = initialCenter ?? DEFAULT_CENTER;
  const zoom = initialZoom ?? DEFAULT_ZOOM;

  const dataRef = React.useRef({ incidents, scenes, drift, attribution });
  dataRef.current = { incidents, scenes, drift, attribution };

  /* ---------- init ---------- */
  React.useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    let isMounted = true;
    let styleLoadAttempted = false;

    try {
      const mapConfig: maplibregl.MapOptions = {
        container: containerRef.current,
        style: getMapStyleUrl(),
        center,
        zoom,
        minZoom: projectionMode === "globe" ? 0.5 : 3,
        maxZoom: 18,
        attributionControl: { compact: true },
        dragRotate: false,
        pitchWithRotate: false,
      };

      // Set projection mode
      if (projectionMode === "globe") {
        (mapConfig as Record<string, unknown>).projection = "globe";
      }

      const map = new maplibregl.Map(mapConfig);
      mapRef.current = map;

      const finishInit = () => {
        if (!isMounted || readyRef.current) return;
        readyRef.current = true;
        try {
          addDataLayers(map);
          applyVisibility(map, useAppStore.getState().activeLayers);
        } catch (err) {
          console.warn("Error adding data layers to map:", err);
        }
        setReady(true);
      };

      if (map.isStyleLoaded()) {
        finishInit();
      } else {
        map.on("load", finishInit);
        map.on("styledata", finishInit);
      }

      map.on("error", () => {
        finishInit();
      });

      // Safety timer (200ms): guarantee map ready state is set
      const timer = setTimeout(finishInit, 200);
    } catch (err) {
      console.error("MapLibre init error:", err);
      setReady(true);
    }

    const onFsChange = () => setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onFsChange);

    const resizeObserver = new ResizeObserver(() => {
      if (mapRef.current) {
        try { mapRef.current.resize(); } catch { /* ignore */ }
      }
    });
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      isMounted = false;
      resizeObserver.disconnect();
      document.removeEventListener("fullscreenchange", onFsChange);
      mapRef.current?.remove();
      mapRef.current = null;
      readyRef.current = false;
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
      id: "detection-glow",
      type: "line",
      source: "detections",
      paint: {
        "line-color": [
          "match",
          ["get", "level"],
          "HIGH",
          "#ef4444",
          "MEDIUM",
          "#f97316",
          "#eab308",
        ] as never,
        "line-width": [
          "case",
          ["==", ["get", "id"], useAppStore.getState().selectedIncidentId ?? "__none__"],
          10,
          5,
        ],
        "line-blur": 6,
        "line-opacity": 0.9,
      },
    });

    map.addLayer({
      id: "detection-fill",
      type: "fill",
      source: "detections",
      paint: {
        "fill-color": [
          "match",
          ["get", "level"],
          "HIGH",
          "#ef4444",
          "MEDIUM",
          "#f97316",
          "#eab308",
        ] as never,
        "fill-opacity": [
          "case",
          ["==", ["get", "id"], useAppStore.getState().selectedIncidentId ?? "__none__"],
          0.65,
          0.35,
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
          "#fca5a5",
          "MEDIUM",
          "#fdba74",
          "#fde047",
        ] as never,
        "line-width": [
          "case",
          ["==", ["get", "id"], useAppStore.getState().selectedIncidentId ?? "__none__"],
          3,
          1.8,
        ],
        "line-opacity": 1.0,
      },
    });

    // Centroid markers for each detection
    map.addSource("detection-centroids", {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });

    // Outer pulse ring (animated on selection)
    map.addLayer({
      id: "centroid-pulse-ring",
      type: "circle",
      source: "detection-centroids",
      filter: ["==", ["get", "selected"], true],
      paint: {
        "circle-radius": 12,
        "circle-color": "#ef4444",
        "circle-opacity": 0.0,
        "circle-stroke-color": "#ef4444",
        "circle-stroke-width": 1.5,
        "circle-stroke-opacity": 0.0,
      },
    });

    // Centroid dots
    map.addLayer({
      id: "centroid-dot",
      type: "circle",
      source: "detection-centroids",
      paint: {
        "circle-radius": [
          "case",
          ["==", ["get", "selected"], true],
          5,
          3.5,
        ],
        "circle-color": [
          "match",
          ["get", "level"],
          "HIGH",
          "#ef4444",
          "MEDIUM",
          "#f97316",
          "#eab308",
        ] as never,
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": [
          "case",
          ["==", ["get", "selected"], true],
          2,
          1,
        ],
        "circle-opacity": 1,
      },
    });

    // Centroid labels (show on hover or selected)
    map.addLayer({
      id: "centroid-label",
      type: "symbol",
      source: "detection-centroids",
      layout: {
        "text-field": ["get", "id"],
        "text-size": 10,
        "text-offset": [0, 1.8],
        "text-anchor": "top",
        "text-allow-overlap": false,
      },
      paint: {
        "text-color": "#e6edf5",
        "text-halo-color": "#070c16",
        "text-halo-width": 1.5,
      },
    });

    map.addLayer({
      id: "sea-labels",
      type: "symbol",
      source: "poi",
      filter: ["==", ["get", "kind"], "sea"],
      layout: {
        "text-field": ["get", "name"],
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

    // Source estimate popup
    map.on("click", "drift-source-point", (e) => {
      const f = e.features?.[0];
      if (!f) return;
      const props = f.properties;
      const coords = (f.geometry as GeoJSON.Point).coordinates as [number, number];
      
      new maplibregl.Popup({ closeButton: true, maxWidth: '260px' })
        .setHTML(`
          <div style="font-family: var(--font-inter), system-ui, sans-serif;">
            <div style="font-size:10px;color:#fbbf24;margin-bottom:4px;">ESTIMATED SOURCE</div>
            <div style="font-size:11px;color:#e6edf5;font-family:monospace;">${coords[1].toFixed(4)}°N, ${coords[0].toFixed(4)}°E</div>
            <div style="margin-top:4px;font-size:9px;color:#5c718f;font-style:italic;">
              ${props.label || 'Source location is an estimate. Not a confirmed origin point.'}
            </div>
          </div>
        `)
        .setLngLat(coords)
        .addTo(map);
    });

    // Uncertainty circle popup
    map.on("click", "drift-uncertainty", (e) => {
      const f = e.features?.[0];
      if (!f) return;
      const coords = (f.geometry as GeoJSON.Point).coordinates as [number, number];
      
      new maplibregl.Popup({ closeButton: true, maxWidth: '240px' })
        .setHTML(`
          <div style="font-family: var(--font-inter), system-ui, sans-serif;">
            <div style="font-size:10px;color:#22d3ee;margin-bottom:4px;">UNCERTAINTY REGION</div>
            <div style="font-size:10px;color:#93a4bd;">
              The estimated source region accounts for drift model uncertainty. The actual release point may be anywhere within this area.
            </div>
          </div>
        `)
        .setLngLat(coords)
        .addTo(map);
    });

    // Cursor for source/uncertainty points
    map.on("mouseenter", "drift-source-point", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "drift-source-point", () => { map.getCanvas().style.cursor = ""; });
    map.on("mouseenter", "drift-uncertainty", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "drift-uncertainty", () => { map.getCanvas().style.cursor = ""; });

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

    // Centroid click also selects
    map.on("click", "centroid-dot", (e) => {
      const f = e.features?.[0];
      const id = f?.properties?.id as string | undefined;
      if (!id) return;
      const inc = dataRef.current.incidents.find((i) => i.id === id);
      if (inc) selectIncident(inc);
    });

    // Hover cursors for detection layers
    map.on("mouseenter", "detection-fill", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "detection-fill", () => { map.getCanvas().style.cursor = ""; });
    map.on("mouseenter", "centroid-dot", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "centroid-dot", () => { map.getCanvas().style.cursor = ""; });

    // Candidate vessel click popup
    map.on("click", "candidate-vessel-points", (e) => {
      const f = e.features?.[0];
      if (!f) return;
      const props = f.properties;
      const coords = (f.geometry as GeoJSON.Point).coordinates as [number, number];
      
      const score = props.score ? Math.round(Number(props.score) * 100) : 0;
      const isTop = props.rank === 1;
      
      new maplibregl.Popup({ closeButton: true, maxWidth: '280px', className: 'map-popup-vessel' })
        .setHTML(`
          <div style="font-family: var(--font-inter), system-ui, sans-serif;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
              <span style="font-size:12px;font-weight:600;color:#e6edf5;">${props.name || `MMSI ${props.mmsi}`}</span>
              ${isTop ? '<span style="font-size:9px;padding:1px 6px;border:1px solid rgba(56,189,248,0.4);border-radius:3px;background:rgba(56,189,248,0.1);color:#38bdf8;font-family:monospace;">POTENTIAL SOURCE</span>' : ''}
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:3px;font-size:10px;">
              <div style="color:#5c718f;">VESSEL</div><div style="color:#e6edf5;font-family:monospace;">${props.name || '—'}</div>
              <div style="color:#5c718f;">MMSI</div><div style="color:#e6edf5;font-family:monospace;">${props.mmsi}</div>
              <div style="color:#5c718f;">TYPE</div><div style="color:#e6edf5;font-family:monospace;">${props.type || '—'}</div>
              <div style="color:#5c718f;">RANK</div><div style="color:#e6edf5;font-family:monospace;">#${props.rank || '—'}</div>
            </div>
            <div style="margin-top:6px;padding-top:6px;border-top:1px solid #1b2a44;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:9px;color:#5c718f;">ATTRIBUTION SCORE</span>
                <span style="font-size:11px;font-weight:bold;color:#38bdf8;font-family:monospace;">${score}%</span>
              </div>
              <div style="margin-top:3px;height:3px;border-radius:2px;background:#0d1626;overflow:hidden;">
                <div style="height:100%;width:${score}%;background:#38bdf8;border-radius:2px;"></div>
              </div>
            </div>
            <div style="margin-top:6px;font-size:9px;color:#5c718f;font-style:italic;">
              Human review required — AIS proximity does not establish causation.
            </div>
          </div>
        `)
        .setLngLat(coords)
        .addTo(map);
    });

    // Hover cursor for vessel points
    map.on("mouseenter", "candidate-vessel-points", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "candidate-vessel-points", () => {
      map.getCanvas().style.cursor = "";
    });

    // Detection hover popup
    let detectionPopup: maplibregl.Popup | null = null;
    map.on("mouseenter", "detection-fill", (e) => {
      const f = e.features?.[0];
      if (!f) return;
      const props = f.properties;
      const coords = (f.geometry as GeoJSON.Polygon).coordinates[0][0] as [number, number];
      const confidence = props.confidence ? Math.round(Number(props.confidence) * 100) : 0;
      
      if (detectionPopup) detectionPopup.remove();
      detectionPopup = new maplibregl.Popup({ closeButton: false, maxWidth: '220px', className: 'map-popup-detection' })
        .setHTML(`
          <div style="font-family: var(--font-inter), system-ui, sans-serif;">
            <div style="font-size:10px;color:#f97316;margin-bottom:4px;font-weight:600;letter-spacing:0.1em;">MODEL DETECTION</div>
            <div style="font-size:11px;font-weight:600;color:#e6edf5;">${props.id || '—'}</div>
            <div style="display:grid;grid-template-columns:auto 1fr;gap:2px 8px;margin-top:4px;font-size:10px;">
              <span style="color:#5c718f;">Confidence</span><span style="color:#38bdf8;font-family:monospace;">${confidence}%</span>
              <span style="color:#5c718f;">Level</span><span style="color:#e6edf5;font-family:monospace;">${props.level || '—'}</span>
            </div>
            <div style="margin-top:4px;font-size:9px;color:#5c718f;font-style:italic;">
              Model-generated candidate — requires human review.
            </div>
          </div>
        `)
        .setLngLat(coords)
        .addTo(map);
    });
    map.on("mouseleave", "detection-fill", () => {
      map.getCanvas().style.cursor = "";
      if (detectionPopup) { detectionPopup.remove(); detectionPopup = null; }
    });
  }

  /* ---------- sync detection data ---------- */
  React.useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !map.isStyleLoaded()) return;
    try {
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

      // Update centroid markers
      const centroidSrc = map.getSource("detection-centroids") as maplibregl.GeoJSONSource | undefined;
      centroidSrc?.setData({
        type: "FeatureCollection",
        features: incidents.map((inc) => ({
          type: "Feature" as const,
          properties: {
            id: inc.id,
            level: inc.level,
            confidence: inc.confidence,
            selected: inc.id === selectedId,
          },
          geometry: {
            type: "Point" as const,
            coordinates: [inc.centroid.lon, inc.centroid.lat],
          },
        })),
      });
    } catch {
      /* ignore style loading transition */
    }
  }, [incidents, ready, selectedId]);

  React.useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !map.isStyleLoaded()) return;
    try {
      const src = map.getSource("coverage") as maplibregl.GeoJSONSource | undefined;
      src?.setData({
        type: "FeatureCollection",
        features: scenes.map(bboxPolygon),
      });
    } catch {
      /* ignore style loading transition */
    }
  }, [scenes, ready]);

  // Sync drift data
  React.useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !map.isStyleLoaded()) return;

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
    if (!map || !ready || !map.isStyleLoaded()) return;

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
    if (!map || !ready || !map.isStyleLoaded()) return;

    try {
      map.setPaintProperty("detection-glow", "line-width", [
        "case",
        ["==", ["get", "id"], selectedId ?? "__none__"],
        10,
        5,
      ] as never);
      map.setPaintProperty("detection-fill", "fill-opacity", [
        "case",
        ["==", ["get", "id"], selectedId ?? "__none__"],
        0.65,
        0.35,
      ] as never);
      map.setPaintProperty("detection-outline", "line-width", [
        "case",
        ["==", ["get", "id"], selectedId ?? "__none__"],
        3,
        1.8,
      ] as never);

      // Update centroid selection state
      const centroidSrc = map.getSource("detection-centroids") as maplibregl.GeoJSONSource | undefined;
      if (centroidSrc) {
        centroidSrc.setData({
          type: "FeatureCollection",
          features: incidents.map((inc) => ({
            type: "Feature" as const,
            properties: {
              id: inc.id,
              level: inc.level,
              confidence: inc.confidence,
              selected: inc.id === selectedId,
            },
            geometry: {
              type: "Point" as const,
              coordinates: [inc.centroid.lon, inc.centroid.lat],
            },
          })),
        });
      }

      if (selectedId) {
        const targetInc = incidents.find((i) => i.id === selectedId);
        if (targetInc && targetInc.centroid) {
          map.flyTo({
            center: [targetInc.centroid.lon, targetInc.centroid.lat],
            zoom: 11.2,
            pitch: 25,
            duration: 1800,
            essential: true,
          });
        }
      }
    } catch {
      /* ignore style loading transitions */
    }
  }, [selectedId, incidents, ready]);

  // Pulse animation for selected detection
  React.useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !map.isStyleLoaded()) return;
    let raf = 0;
    const t0 = performance.now();
    const animate = (t: number) => {
      if (!selectedId) {
        try {
          map.setPaintProperty("centroid-pulse-ring", "circle-stroke-opacity", 0);
          map.setPaintProperty("centroid-pulse-ring", "circle-opacity", 0);
        } catch { /* ignore */ }
        return;
      }
      const phase = ((t - t0) / 2000) % 1;
      const opacity = 0.6 * (1 - phase);
      const radius = 8 + phase * 10;
      try {
        map.setPaintProperty("centroid-pulse-ring", "circle-radius", radius);
        map.setPaintProperty("centroid-pulse-ring", "circle-stroke-opacity", opacity);
        map.setPaintProperty("centroid-pulse-ring", "circle-opacity", opacity * 0.15);
      } catch { /* ignore */ }
      raf = requestAnimationFrame(animate);
    };
    raf = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf);
  }, [selectedId, ready]);

  /* ---------- layer visibility ---------- */
  React.useEffect(() => {
    if (!ready) return;
    const map = mapRef.current;
    if (map && map.isStyleLoaded()) applyVisibility(map, activeLayers);
  }, [activeLayers, ready]);

  function applyVisibility(map: MapLibreMap, layers: Record<string, boolean>) {
    if (!map || !map.isStyleLoaded()) return;
    const visibility = (on: boolean) => (on ? "visible" : "none");
    const safeSetLayout = (id: string, vis: boolean) => {
      if (map.getLayer(id)) {
        try {
          map.setLayoutProperty(id, "visibility", visibility(vis));
        } catch {
          /* ignore */
        }
      }
    };
    safeSetLayout("detection-glow", layers["detections"]);
    safeSetLayout("detection-fill", layers["detections"]);
    safeSetLayout("detection-outline", layers["detections"]);
    safeSetLayout("centroid-pulse-ring", layers["detections"]);
    safeSetLayout("centroid-dot", layers["detections"]);
    safeSetLayout("centroid-label", layers["detections"]);
    safeSetLayout("coverage-fill", layers["scene-coverage"]);
    safeSetLayout("coverage-line", layers["scene-coverage"]);
    safeSetLayout("drift-trajectory-lines", layers["drift-trajectories"]);
    safeSetLayout("drift-uncertainty", layers["source-probability"]);
    safeSetLayout("drift-source-point", layers["source-probability"]);
    safeSetLayout("drift-slick-point", layers["source-probability"]);
    safeSetLayout("ais-vessel-points", layers["ais-vessels"]);
    safeSetLayout("ais-track-lines", layers["ais-tracks"]);
    safeSetLayout("candidate-vessel-points", layers["candidate-vessels"]);
    safeSetLayout("candidate-vessel-labels", layers["candidate-vessels"]);
  }

  /* ---------- external fly-to requests ---------- */
  React.useEffect(() => {
    if (!flyTo || !ready) return;

    const map = mapRef.current;
    if (!map) return;

    // Determine appropriate zoom - use deeper zoom for investigation
    const targetZoom = flyTo.zoom ?? 8;

    // Smooth cinematic fly-to with appropriate duration based on distance
    const currentCenter = map.getCenter();
    const dx = flyTo.lon - currentCenter.lng;
    const dy = flyTo.lat - currentCenter.lat;
    const distance = Math.sqrt(dx * dx + dy * dy);

    // Longer duration for longer distances (globe → incident)
    const duration = Math.min(3000, Math.max(1200, distance * 40));

    map.flyTo({
      center: [flyTo.lon, flyTo.lat],
      zoom: targetZoom,
      duration,
      curve: 1.8,
      essential: true,
    });
  }, [flyTo, ready]);

  /* ---------- control actions ---------- */
  const zoomBy = (delta: number) =>
    mapRef.current?.easeTo({ zoom: (mapRef.current?.getZoom() ?? 4) + delta, duration: 250 });

  const resetView = () => {
    if (projectionMode === "globe") {
      // Reset to global view
      mapRef.current?.flyTo({
        center: [78, 15],
        zoom: 1.5,
        duration: 700,
      });
    } else {
      mapRef.current?.fitBounds(INDIA_BOUNDS, { padding: 48, duration: 700 });
    }
  };

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
