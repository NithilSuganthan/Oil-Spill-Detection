"use client";

import * as React from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { DriftResult, AttributionResult, CandidateVessel } from "@/lib/types";
import { getMapStyleUrl, getStyleForMode, COASTAL_CITIES, SEA_LABELS } from "@/components/map/map-config";
import { useAppStore } from "@/lib/store/use-app-store";

export interface DriftMapViewHandle {
  flyTo: (lng: number, lat: number, zoom?: number) => void;
  fitInvestigation: () => void;
  replayInvestigation: (onStep?: (progress: number) => void) => void;
  cancelReplay: () => void;
  getMap: () => maplibregl.Map | null;
}

interface DriftMapViewProps {
  sourcePoints: [number, number][];
  slickPoints?: [number, number][];
  drift: DriftResult | null;
  attribution: AttributionResult | null;
  activeLayers: Record<string, boolean>;
  evolutionMode?: "SOURCE" | "DRIFT" | "DETECTION" | "FULL";
  animationProgress?: number; // 0 (Source T-8h) -> 1 (Slick T-0)
  animationSpeed?: number;
  onSelectSource?: () => void;
  onSelectSlick?: () => void;
  onSelectVessel?: (vessel: CandidateVessel) => void;
  envGrid?: import("@/lib/types").EnvironmentalGrid | null;
}

// Particle color interpolation helper along time flow
function getParticleColorRGB(t: number): { r: number; g: number; b: number; hex: string } {
  const clampT = Math.max(0, Math.min(1, t));
  let r: number, g: number, b: number;

  if (clampT < 0.35) {
    // Emerald (16, 185, 129) -> Cyan (6, 182, 212)
    const factor = clampT / 0.35;
    r = Math.round(16 + (6 - 16) * factor);
    g = Math.round(185 + (182 - 185) * factor);
    b = Math.round(129 + (212 - 129) * factor);
  } else if (clampT < 0.7) {
    // Cyan (6, 182, 212) -> Yellow/Amber (245, 158, 11)
    const factor = (clampT - 0.35) / 0.35;
    r = Math.round(6 + (245 - 6) * factor);
    g = Math.round(182 + (158 - 182) * factor);
    b = Math.round(212 + (11 - 212) * factor);
  } else {
    // Amber (245, 158, 11) -> Crimson Red (239, 68, 68)
    const factor = (clampT - 0.7) / 0.3;
    r = Math.round(245 + (239 - 245) * factor);
    g = Math.round(158 + (68 - 158) * factor);
    b = Math.round(11 + (68 - 11) * factor);
  }

  const hex = `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
  return { r, g, b, hex };
}

// Build deterministic track coordinates for candidate vessels across 8-hour timeline
function getVesselPositionAtTime(
  vessel: CandidateVessel,
  idx: number,
  tProgress: number, // 0..1
  centerLat: number,
  centerLon: number,
  sourceLat: number,
  sourceLon: number
): { lat: number; lon: number; headingDeg: number; speedKts: number } {
  // Candidate #1 (Tanker / Top Candidate): Starts near source at T-8h, moves SE
  if (idx === 0 || vessel.vesselType === "Tanker") {
    const startLat = sourceLat + 0.005;
    const startLon = sourceLon + 0.005;
    const endLat = centerLat - 0.04;
    const endLon = centerLon + 0.12;

    const lat = startLat + (endLat - startLat) * tProgress;
    const lon = startLon + (endLon - startLon) * tProgress;
    const dLat = endLat - startLat;
    const dLon = endLon - startLon;
    const headingDeg = (Math.atan2(dLon, dLat) * 180) / Math.PI;

    return { lat, lon, headingDeg: (headingDeg + 360) % 360, speedKts: 13.8 };
  }

  // Candidate #2 (Cargo Ship): Moves NE across search area
  if (idx === 1 || vessel.vesselType === "Cargo") {
    const startLat = centerLat - 0.10;
    const startLon = centerLon - 0.08;
    const endLat = centerLat + 0.08;
    const endLon = centerLon + 0.06;

    const lat = startLat + (endLat - startLat) * tProgress;
    const lon = startLon + (endLon - startLon) * tProgress;
    const dLat = endLat - startLat;
    const dLon = endLon - startLon;
    const headingDeg = (Math.atan2(dLon, dLat) * 180) / Math.PI;

    return { lat, lon, headingDeg: (headingDeg + 360) % 360, speedKts: 16.2 };
  }

  // Candidate #3 (Fishing Vessel / Other): Slow coaster
  const startLat = centerLat + 0.05;
  const startLon = centerLon + 0.08;
  const endLat = centerLat - 0.02;
  const endLon = centerLon - 0.04;

  const lat = startLat + (endLat - startLat) * tProgress;
  const lon = startLon + (endLon - startLon) * tProgress;
  const dLat = endLat - startLat;
  const dLon = endLon - startLon;
  const headingDeg = (Math.atan2(dLon, dLat) * 180) / Math.PI;

  return { lat, lon, headingDeg: (headingDeg + 360) % 360, speedKts: 8.4 };
}

/** Bilinear interpolation on a grid. Returns null if outside grid or no data. */
function bilinearGridValue(
  grid: (number | null)[][],
  lats: number[],
  lons: number[],
  lat: number,
  lon: number,
): number | null {
  if (lats.length < 2 || lons.length < 2) return null;

  let latIdx = lats.findIndex((v) => v >= lat);
  let lonIdx = lons.findIndex((v) => v >= lon);
  if (latIdx === -1) latIdx = lats.length - 1;
  if (lonIdx === -1) lonIdx = lons.length - 1;
  if (latIdx === 0) latIdx = 1;
  if (lonIdx === 0) lonIdx = 1;

  const i0 = latIdx - 1;
  const i1 = latIdx;
  const j0 = lonIdx - 1;
  const j1 = lonIdx;

  const lat0 = lats[i0];
  const lat1 = lats[i1];
  const lon0 = lons[j0];
  const lon1 = lons[j1];
  if (lat1 === lat0 || lon1 === lon0) return null;

  const dlat = (lat - lat0) / (lat1 - lat0);
  const dlon = (lon - lon0) / (lon1 - lon0);

  const v00 = grid[i0]?.[j0];
  const v01 = grid[i0]?.[j1];
  const v10 = grid[i1]?.[j0];
  const v11 = grid[i1]?.[j1];
  if (v00 == null || v01 == null || v10 == null || v11 == null) return null;

  return v00 * (1 - dlat) * (1 - dlon) + v01 * (1 - dlat) * dlon +
    v10 * dlat * (1 - dlon) + v11 * dlat * dlon;
}

const DriftMapView = React.forwardRef<DriftMapViewHandle, DriftMapViewProps>(
  function DriftMapView(
    {
      sourcePoints,
      slickPoints,
      drift,
      attribution,
      activeLayers,
      evolutionMode = "FULL",
      animationProgress = 1,
      animationSpeed = 1,
      onSelectSource,
      onSelectSlick,
      onSelectVessel,
      envGrid = null,
    },
    ref
  ) {
    const mapContainerRef = React.useRef<HTMLDivElement>(null);
    const mapRef = React.useRef<maplibregl.Map | null>(null);
    const readyRef = React.useRef(false);

    const particleCanvasRef = React.useRef<HTMLCanvasElement>(null);
    const windCanvasRef = React.useRef<HTMLCanvasElement>(null);
    const currentCanvasRef = React.useRef<HTMLCanvasElement>(null);

    const vesselMarkersRef = React.useRef<maplibregl.Marker[]>([]);
    const sourceMarkerRef = React.useRef<maplibregl.Marker | null>(null);
    const slickMarkerRef = React.useRef<maplibregl.Marker | null>(null);
    const trajectoryMarkersRef = React.useRef<maplibregl.Marker[]>([]);

    const isReplayingRef = React.useRef(false);
    const replayAnimFrameRef = React.useRef<number | null>(null);
    const initDataLayersRef = React.useRef<(() => void) | null>(null);
    const mapStyle = useAppStore((s) => s.mapStyle);

    // Cancel replay animation if user interacts
    const cancelReplay = React.useCallback(() => {
      isReplayingRef.current = false;
      if (replayAnimFrameRef.current !== null) {
        cancelAnimationFrame(replayAnimFrameRef.current);
        replayAnimFrameRef.current = null;
      }
    }, []);

    // Fit camera to full investigation bounds
    const fitInvestigation = React.useCallback(() => {
      cancelReplay();
      const map = mapRef.current;
      if (!map) return;

      const points: [number, number][] = [];
      if (sourcePoints && sourcePoints.length > 0) points.push(...sourcePoints);
      if (slickPoints && slickPoints.length > 0) points.push(...slickPoints);
      if (drift?.sourceLatitude != null && drift?.sourceLongitude != null) {
        points.push([drift.sourceLatitude, drift.sourceLongitude]);
      }
      if (drift?.slickLatitude != null && drift?.slickLongitude != null) {
        points.push([drift.slickLatitude, drift.slickLongitude]);
      }

      if (points.length > 0) {
        const bounds = new maplibregl.LngLatBounds();
        points.forEach((pt) => bounds.extend([pt[1], pt[0]]));
        map.fitBounds(bounds, { padding: 80, maxZoom: 13, duration: 1500 });
      }
    }, [sourcePoints, slickPoints, drift, cancelReplay]);

    // Cinematic Replay Investigation Mode
    const replayInvestigation = React.useCallback(
      (onStep?: (progress: number) => void) => {
        const map = mapRef.current;
        if (!map || !drift) return;

        cancelReplay();
        isReplayingRef.current = true;

        const slickLat = drift.slickLatitude;
        const slickLon = drift.slickLongitude;
        const sourceLat = drift.sourceLatitude;
        const sourceLon = drift.sourceLongitude;

        map.flyTo({ center: [slickLon, slickLat], zoom: 11, duration: 1500 });

        let startTime: number | null = null;
        const duration = 10000;

        const animateCamera = (time: number) => {
          if (!isReplayingRef.current) return;
          if (!startTime) startTime = time;
          const elapsed = time - startTime;
          const progress = Math.min(1, elapsed / duration);

          if (onStep) onStep(progress);

          const curLat = slickLat + (sourceLat - slickLat) * progress;
          const curLon = slickLon + (sourceLon - slickLon) * progress;

          map.easeTo({
            center: [curLon, curLat],
            zoom: 10.5 + Math.sin(progress * Math.PI) * 0.5,
            duration: 50,
          });

          if (progress < 1) {
            replayAnimFrameRef.current = requestAnimationFrame(animateCamera);
          } else {
            setTimeout(() => {
              if (isReplayingRef.current) {
                fitInvestigation();
                isReplayingRef.current = false;
              }
            }, 1000);
          }
        };

        setTimeout(() => {
          if (isReplayingRef.current) {
            replayAnimFrameRef.current = requestAnimationFrame(animateCamera);
          }
        }, 1600);
      },
      [drift, cancelReplay, fitInvestigation]
    );

    // Expose handle methods
    React.useImperativeHandle(ref, () => ({
      flyTo: (lng: number, lat: number, zoom = 12) => {
        cancelReplay();
        mapRef.current?.flyTo({ center: [lng, lat], zoom, essential: true });
      },
      fitInvestigation,
      replayInvestigation,
      cancelReplay,
      getMap: () => mapRef.current,
    }));

    // Initialize MapLibre GL with robust lifecycle
    React.useEffect(() => {
      if (!mapContainerRef.current || mapRef.current) return;

      let isMounted = true;
      let styleLoadAttempted = false;

      const map = new maplibregl.Map({
        container: mapContainerRef.current,
        style: getMapStyleUrl(),
        center: [72.8456, 15.2965],
        zoom: 7.5,
        pitch: 0,
        attributionControl: { compact: true },
      });
      mapRef.current = map;

      map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");

      const addSourceIfMissing = (id: string, spec: maplibregl.SourceSpecification) => {
        if (!map.getSource(id)) {
          map.addSource(id, spec);
        }
      };

      const addLayerIfMissing = (layer: maplibregl.LayerSpecification) => {
        if (!map.getLayer(layer.id)) {
          map.addLayer(layer);
        }
      };

      const initDataLayers = () => {
        if (!isMounted) return;
        readyRef.current = true;
        initDataLayersRef.current = initDataLayers;

        addSourceIfMissing("poi", {
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

        addLayerIfMissing({
          id: "sea-labels",
          type: "symbol",
          source: "poi",
          filter: ["==", ["get", "kind"], "sea"],
          layout: {
            "text-field": ["get", "name"],
            "text-size": 13,
            "text-letter-spacing": 0.3,
          },
          paint: { "text-color": "#4a6076", "text-halo-color": "#070c16", "text-halo-width": 1.5 },
        });

        addLayerIfMissing({
          id: "city-dot",
          type: "circle",
          source: "poi",
          filter: ["==", ["get", "kind"], "city"],
          paint: {
            "circle-radius": 3,
            "circle-color": "#38bdf8",
            "circle-stroke-width": 1,
            "circle-stroke-color": "#0a1120",
          },
        });

        addLayerIfMissing({
          id: "city-labels",
          type: "symbol",
          source: "poi",
          filter: ["==", ["get", "kind"], "city"],
          layout: {
            "text-field": ["get", "name"],
            "text-size": 11,
            "text-offset": [0, 1.2],
            "text-anchor": "top",
          },
          paint: { "text-color": "#93a4bd", "text-halo-color": "#070c16", "text-halo-width": 1.5 },
        });

        addSourceIfMissing("slick-polygon", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });

        addLayerIfMissing({
          id: "slick-polygon-fill",
          type: "fill",
          source: "slick-polygon",
          paint: {
            "fill-color": "#ef4444",
            "fill-opacity": 0.28,
          },
        });

        addLayerIfMissing({
          id: "slick-polygon-line",
          type: "line",
          source: "slick-polygon",
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": "#ef4444",
            "line-width": 3,
            "line-opacity": 0.95,
          },
        });

        addSourceIfMissing("trajectory-line", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });

        addLayerIfMissing({
          id: "trajectory-glow",
          type: "line",
          source: "trajectory-line",
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": "#06b6d4",
            "line-width": 9,
            "line-opacity": 0.4,
            "line-blur": 5,
          },
        });

        addLayerIfMissing({
          id: "trajectory-core",
          type: "line",
          source: "trajectory-line",
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": "#22d3ee",
            "line-width": 3.5,
            "line-opacity": 0.95,
            "line-dasharray": [4, 2],
          },
        });

        addSourceIfMissing("uncertainty-circle", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });

        addLayerIfMissing({
          id: "uncertainty-fill",
          type: "fill",
          source: "uncertainty-circle",
          paint: {
            "fill-color": "#a855f7",
            "fill-opacity": 0.16,
          },
        });

        addLayerIfMissing({
          id: "uncertainty-outline",
          type: "line",
          source: "uncertainty-circle",
          paint: {
            "line-color": "#c084fc",
            "line-width": 1.8,
            "line-opacity": 0.85,
            "line-dasharray": [4, 3],
          },
        });

        addSourceIfMissing("vessel-tracks", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });

        addLayerIfMissing({
          id: "vessel-tracks-line",
          type: "line",
          source: "vessel-tracks",
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": [
              "case",
              ["==", ["get", "isTop"], true],
              "#f59e0b",
              "#3b82f6"
            ],
            "line-width": 2,
            "line-dasharray": [3, 2],
            "line-opacity": 0.65,
          },
        });

        updateGeoJSONData(map);
      };

      const finishInit = () => {
        if (!isMounted || readyRef.current) return;
        readyRef.current = true;
        try {
          initDataLayers();
        } catch (err) {
          console.warn("Error initializing drift map layers:", err);
        }
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

      map.on("mousedown", cancelReplay);
      map.on("wheel", cancelReplay);
      map.on("touchstart", cancelReplay);

      const resizeObserver = new ResizeObserver(() => {
        if (mapRef.current) {
          try { mapRef.current.resize(); } catch { /* ignore */ }
        }
      });
      if (mapContainerRef.current) {
        resizeObserver.observe(mapContainerRef.current);
      }

      return () => {
        isMounted = false;
        resizeObserver.disconnect();
        map.remove();
        mapRef.current = null;
        readyRef.current = false;
      };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Dynamic basemap style switching
    React.useEffect(() => {
      const map = mapRef.current;
      if (!map || !readyRef.current) return;

      const newStyle = getStyleForMode(mapStyle);
      map.setStyle(newStyle);

      const onStyleLoad = () => {
        // Re-add all data layers after style change
        initDataLayersRef.current?.();
        // Re-apply current data to restored sources
        const mapNow = mapRef.current;
        if (mapNow) updateGeoJSONData(mapNow);
      };

      map.on("style.load", onStyleLoad);
      return () => {
        map.off("style.load", onStyleLoad);
      };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [mapStyle]);

    // Update GeoJSON layers data
    const updateGeoJSONData = React.useCallback(
      (map: maplibregl.Map) => {
        if (!readyRef.current || !map.isStyleLoaded()) return;
        try {

        // Trajectory line: sourcePoints array of [lat, lon]
        if (sourcePoints && sourcePoints.length > 1) {
          const coords = sourcePoints.map((pt) => [pt[1], pt[0]]);
          const src = map.getSource("trajectory-line") as maplibregl.GeoJSONSource;
          if (src) {
            src.setData({
              type: "FeatureCollection",
              features: [
                {
                  type: "Feature",
                  geometry: { type: "LineString", coordinates: coords },
                  properties: {},
                },
              ],
            });
          }
        }

        // Slick Polygon
        if (slickPoints && slickPoints.length > 2) {
          const coords = slickPoints.map((pt) => [pt[1], pt[0]]);
          if (
            coords[0][0] !== coords[coords.length - 1][0] ||
            coords[0][1] !== coords[coords.length - 1][1]
          ) {
            coords.push(coords[0]);
          }
          const src = map.getSource("slick-polygon") as maplibregl.GeoJSONSource;
          if (src) {
            src.setData({
              type: "FeatureCollection",
              features: [
                {
                  type: "Feature",
                  geometry: { type: "Polygon", coordinates: [coords] },
                  properties: {},
                },
              ],
            });
          }
        }

        // Source Uncertainty Circle
        if (
          drift?.sourceLatitude != null &&
          drift?.sourceLongitude != null &&
          drift?.uncertaintyKm != null
        ) {
          const radiusDeg = drift.uncertaintyKm / 111.32;
          const center: [number, number] = [drift.sourceLongitude, drift.sourceLatitude];
          const circlePts: [number, number][] = [];
          for (let i = 0; i <= 64; i++) {
            const angle = (i / 64) * 2 * Math.PI;
            circlePts.push([
              center[0] + radiusDeg * Math.cos(angle),
              center[1] + (radiusDeg / Math.cos((center[1] * Math.PI) / 180)) * Math.sin(angle),
            ]);
          }
          const src = map.getSource("uncertainty-circle") as maplibregl.GeoJSONSource;
          if (src) {
            src.setData({
              type: "FeatureCollection",
              features: [
                {
                  type: "Feature",
                  geometry: { type: "Polygon", coordinates: [circlePts] },
                  properties: {},
                },
              ],
            });
          }
        }

        // AIS Vessel Track Lines
        if (attribution && attribution.candidates.length > 0 && drift) {
          const centerLat = attribution.searchWindow?.centerLat ?? drift.slickLatitude;
          const centerLon = attribution.searchWindow?.centerLon ?? drift.slickLongitude;
          const sourceLat = drift.sourceLatitude;
          const sourceLon = drift.sourceLongitude;

          const trackFeatures: GeoJSON.Feature[] = attribution.candidates.map((vessel, idx) => {
            const steps = 30;
            const pts: [number, number][] = [];
            for (let step = 0; step <= steps; step++) {
              const pos = getVesselPositionAtTime(
                vessel,
                idx,
                step / steps,
                centerLat,
                centerLon,
                sourceLat,
                sourceLon
              );
              pts.push([pos.lon, pos.lat]);
            }
            return {
              type: "Feature",
              properties: { mmsi: vessel.mmsi, isTop: idx === 0 },
              geometry: { type: "LineString", coordinates: pts },
            };
          });

          const src = map.getSource("vessel-tracks") as maplibregl.GeoJSONSource;
          if (src) {
            src.setData({ type: "FeatureCollection", features: trackFeatures });
          }
        }
        } catch {
          /* ignore style loading transition */
        }
      },
      [sourcePoints, slickPoints, drift, attribution]
    );

    React.useEffect(() => {
      const map = mapRef.current;
      if (map) updateGeoJSONData(map);
    }, [updateGeoJSONData]);

    // Layer Visibility Control
    React.useEffect(() => {
      const map = mapRef.current;
      if (!map || !readyRef.current || !map.isStyleLoaded()) return;

      const setVis = (id: string, vis: boolean) => {
        if (map.getLayer(id)) {
          try {
            map.setLayoutProperty(id, "visibility", vis ? "visible" : "none");
          } catch {
            /* ignore */
          }
        }
      };

      setVis("slick-polygon-fill", activeLayers["slick"] ?? true);
      setVis("slick-polygon-line", activeLayers["slick"] ?? true);
      setVis("trajectory-glow", activeLayers["trajectory"] ?? true);
      setVis("trajectory-core", activeLayers["trajectory"] ?? true);
      setVis("uncertainty-fill", activeLayers["uncertainty"] ?? true);
      setVis("uncertainty-outline", activeLayers["uncertainty"] ?? true);
      setVis("vessel-tracks-line", activeLayers["ais-tracks"] ?? true);
    }, [activeLayers]);

    // ── ESTIMATED SOURCE MARKER (CONCENTRIC RINGS) ──
    React.useEffect(() => {
      sourceMarkerRef.current?.remove();
      sourceMarkerRef.current = null;

      const map = mapRef.current;
      if (!map || !drift || drift.sourceLatitude == null || drift.sourceLongitude == null) return;
      if (!activeLayers["source"]) return;

      const el = document.createElement("div");
      el.className = "relative flex items-center justify-center cursor-pointer group";
      el.innerHTML = `
        <div class="absolute h-16 w-16 rounded-full border border-emerald-400/60 bg-emerald-500/10 animate-source-ring-1 pointer-events-none"></div>
        <div class="absolute h-16 w-16 rounded-full border border-emerald-400/40 bg-emerald-500/10 animate-source-ring-2 pointer-events-none"></div>
        <div class="absolute h-16 w-16 rounded-full border border-emerald-400/20 bg-emerald-500/10 animate-source-ring-3 pointer-events-none"></div>
        <div class="relative h-6 w-6 rounded-full bg-emerald-500/20 border-2 border-emerald-400 shadow-[0_0_16px_rgba(52,211,153,0.9)] flex items-center justify-center">
          <div class="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse"></div>
        </div>
        <div class="absolute top-7 left-1/2 -translate-x-1/2 whitespace-nowrap panel border-emerald-500/40 bg-base-950/90 px-2 py-1 font-mono text-[9px] text-emerald-300 shadow-xl backdrop-blur-md flex flex-col items-center pointer-events-auto">
          <span class="font-bold tracking-wider uppercase text-[8px] text-emerald-400">ESTIMATED SOURCE</span>
          <span class="text-[10px] text-ink font-semibold">${drift.sourceLatitude.toFixed(4)}° N, ${drift.sourceLongitude.toFixed(4)}° E</span>
          <span class="text-[7.5px] text-ink-faint">~8h before detection (10:31 IST)</span>
        </div>
      `;

      el.addEventListener("click", () => {
        if (onSelectSource) onSelectSource();
      });

      sourceMarkerRef.current = new maplibregl.Marker({ element: el })
        .setLngLat([drift.sourceLongitude, drift.sourceLatitude])
        .addTo(map);

      return () => {
        sourceMarkerRef.current?.remove();
        sourceMarkerRef.current = null;
      };
    }, [drift, activeLayers["source"], onSelectSource]);

    // ── DETECTED SLICK MARKER ──
    React.useEffect(() => {
      slickMarkerRef.current?.remove();
      slickMarkerRef.current = null;

      const map = mapRef.current;
      if (!map || !drift || drift.slickLatitude == null || drift.slickLongitude == null) return;
      if (!activeLayers["slick"]) return;

      const el = document.createElement("div");
      el.className = "relative flex items-center justify-center cursor-pointer group";
      el.innerHTML = `
        <div class="relative h-7 w-7 rounded-full bg-red-500/20 border-2 border-red-500 animate-slick-glow flex items-center justify-center">
          <div class="h-3 w-3 rounded-full bg-red-500 animate-ping opacity-75"></div>
          <div class="absolute h-2 w-2 rounded-full bg-red-400"></div>
        </div>
        <div class="absolute top-8 left-1/2 -translate-x-1/2 whitespace-nowrap panel border-red-500/50 bg-base-950/95 px-2.5 py-1.5 font-mono text-[9px] text-ink shadow-2xl backdrop-blur-md flex flex-col items-center border-l-2 border-l-red-500 pointer-events-auto">
          <span class="font-bold tracking-wider uppercase text-[8px] text-red-400">DETECTED POTENTIAL SLICK</span>
          <span class="text-[11px] text-red-300 font-extrabold">18.4 km² · 91.4% confidence</span>
          <span class="text-[7.5px] text-amber-400 font-semibold tracking-tight uppercase">MODEL PREDICTION — HUMAN VERIFICATION REQUIRED</span>
        </div>
      `;

      el.addEventListener("click", () => {
        if (onSelectSlick) onSelectSlick();
      });

      slickMarkerRef.current = new maplibregl.Marker({ element: el })
        .setLngLat([drift.slickLongitude, drift.slickLatitude])
        .addTo(map);

      return () => {
        slickMarkerRef.current?.remove();
        slickMarkerRef.current = null;
      };
    }, [drift, activeLayers["slick"], onSelectSlick]);

    // ── TRAJECTORY TIME MARKERS (T-8h..T-0) ──
    React.useEffect(() => {
      trajectoryMarkersRef.current.forEach((m) => m.remove());
      trajectoryMarkersRef.current = [];

      const map = mapRef.current;
      if (!map || !sourcePoints || sourcePoints.length < 4 || !activeLayers["trajectory"]) return;

      const timeSteps = [
        { label: "T-8h", sub: "10:31 IST", index: 0 },
        { label: "T-6h", sub: "12:31 IST", index: Math.floor(sourcePoints.length * 0.25) },
        { label: "T-4h", sub: "14:31 IST", index: Math.floor(sourcePoints.length * 0.5) },
        { label: "T-2h", sub: "16:31 IST", index: Math.floor(sourcePoints.length * 0.75) },
        { label: "T+0h", sub: "18:31 IST", index: sourcePoints.length - 1 },
      ];

      timeSteps.forEach(({ label, sub, index }) => {
        const pt = sourcePoints[index];
        if (!pt) return;

        const el = document.createElement("div");
        el.className = "flex flex-col items-center font-mono pointer-events-none";
        el.innerHTML = `
          <div class="h-2 w-2 rounded-full bg-cyan-400 border border-base-950 shadow-[0_0_6px_rgba(34,211,238,0.8)]"></div>
          <div class="mt-0.5 rounded border border-line bg-base-950/80 px-1 py-0.5 text-[8px] font-bold text-cyan-300 backdrop-blur-sm">
            ${label} <span class="text-ink-faint font-normal text-[7px]">${sub}</span>
          </div>
        `;

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([pt[1], pt[0]])
          .addTo(map);

        trajectoryMarkersRef.current.push(marker);
      });

      return () => {
        trajectoryMarkersRef.current.forEach((m) => m.remove());
        trajectoryMarkersRef.current = [];
      };
    }, [sourcePoints, activeLayers["trajectory"]]);

    // ── SYNCHRONIZED DYNAMIC AIS OIL TANKER & VESSEL MOVEMENTS ALONG TIMELINE ──
    React.useEffect(() => {
      vesselMarkersRef.current.forEach((m) => m.remove());
      vesselMarkersRef.current = [];

      const map = mapRef.current;
      if (!map || !attribution || !drift) return;
      if (!activeLayers["ais-vessels"] && !activeLayers["candidates"]) return;

      const candidates = attribution.candidates ?? [];
      const centerLat = attribution.searchWindow?.centerLat ?? drift.slickLatitude;
      const centerLon = attribution.searchWindow?.centerLon ?? drift.slickLongitude;
      const sourceLat = drift.sourceLatitude;
      const sourceLon = drift.sourceLongitude;

      candidates.forEach((vessel, idx) => {
        const isTop = idx === 0;
        const scorePct = Math.round(vessel.attributionScore * 100);

        // Interpolate vessel exact position at current timeline progress
        const pos = getVesselPositionAtTime(
          vessel,
          idx,
          animationProgress,
          centerLat,
          centerLon,
          sourceLat,
          sourceLon
        );

        // Distance from current vessel position to oil spill centroid at current timeline
        const dLat = (pos.lat - (sourceLat + (centerLat - sourceLat) * animationProgress)) * 111.32;
        const dLon = (pos.lon - (sourceLon + (centerLon - sourceLon) * animationProgress)) * 111.32 * Math.cos((pos.lat * Math.PI) / 180);
        const distKm = Math.sqrt(dLat * dLat + dLon * dLon).toFixed(2);

        const el = document.createElement("div");
        el.className = "relative flex items-center justify-center cursor-pointer group";
        el.innerHTML = `
          ${
            isTop
              ? `<div class="absolute h-9 w-9 rounded-full border border-amber-400/80 bg-amber-500/20 animate-ping"></div>`
              : ""
          }
          <div class="relative flex items-center justify-center transition-transform duration-100" style="transform: rotate(${pos.headingDeg}deg);">
            <div class="${
              isTop
                ? "h-7 w-7 rounded-full bg-amber-500/30 border-2 border-amber-400 shadow-[0_0_16px_rgba(245,158,11,0.9)]"
                : "h-6 w-6 rounded-full bg-blue-500/30 border border-blue-400"
            } flex items-center justify-center">
              <svg class="h-4 w-4 ${isTop ? "text-amber-300" : "text-blue-300"}" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"/>
              </svg>
            </div>
          </div>
          <!-- Live Vessel Data Badge on Map -->
          <div class="absolute top-8 left-1/2 -translate-x-1/2 whitespace-nowrap panel border-line bg-base-950/95 px-2 py-1 font-mono text-[9px] text-ink shadow-2xl backdrop-blur-md flex flex-col items-center border-t-2 ${
            isTop ? "border-t-amber-400" : "border-t-blue-400"
          } pointer-events-auto">
            <div class="flex items-center gap-1">
              <span class="font-bold text-ink">${vessel.vesselName || `MMSI ${vessel.mmsi}`}</span>
              ${isTop ? `<span class="rounded bg-amber-500/30 text-amber-300 font-extrabold px-1 text-[7px]">TOP</span>` : ""}
              <span class="text-amber-400 font-bold">${scorePct}%</span>
            </div>
            <div class="flex items-center gap-2 text-[7.5px] text-ink-faint mt-0.5">
              <span>${vessel.vesselType || "Tanker"}</span>
              <span class="text-cyan-400 font-semibold">${pos.speedKts} kts</span>
              <span class="text-emerald-400 font-semibold">${distKm} km to spill</span>
            </div>
          </div>
        `;

        el.addEventListener("click", () => {
          if (onSelectVessel) onSelectVessel(vessel);
        });

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([pos.lon, pos.lat])
          .addTo(map);

        vesselMarkersRef.current.push(marker);
      });

      return () => {
        vesselMarkersRef.current.forEach((m) => m.remove());
        vesselMarkersRef.current = [];
      };
    }, [attribution, drift, activeLayers["ais-vessels"], activeLayers["candidates"], animationProgress, onSelectVessel]);

    // ── ADVANCED DYNAMIC OIL SPILL CANVASES ──
    React.useEffect(() => {
      const canvas = particleCanvasRef.current;
      const map = mapRef.current;
      if (!canvas || !map || !activeLayers["trajectory"]) {
        if (canvas) {
          const ctx = canvas.getContext("2d");
          if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
        return;
      }

      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const trajectory = (sourcePoints ?? []).map((pt) => ({ lat: pt[0], lng: pt[1] }));
      if (trajectory.length < 2) return;

      const particleCount = 420;
      const particles = Array.from({ length: particleCount }, () => {
        return {
          progress: Math.random(),
          speed: 0.04 + Math.random() * 0.08,
          size: 1.5 + Math.random() * 2.5,
          opacity: 0.4 + Math.random() * 0.6,
          offsetAngle: Math.random() * Math.PI * 2,
          offsetRadius: Math.random(),
        };
      });

      let animFrame: number;
      let lastTime = 0;

      const interpolatePath = (pFrac: number) => {
        const segCount = trajectory.length - 1;
        const seg = Math.min(Math.floor(pFrac * segCount), segCount - 1);
        const t = pFrac * segCount - seg;
        const a = trajectory[seg];
        const b = trajectory[Math.min(seg + 1, trajectory.length - 1)];
        return {
          lat: a.lat + (b.lat - a.lat) * t,
          lng: a.lng + (b.lng - a.lng) * t,
          headingRad: Math.atan2(b.lat - a.lat, b.lng - a.lng),
        };
      };

      const render = (time: number) => {
        const dt = lastTime ? Math.min((time - lastTime) / 1000, 0.05) : 0.016;
        lastTime = time;

        const parent = canvas.parentElement;
        if (parent) {
          const dpr = window.devicePixelRatio || 1;
          const w = parent.clientWidth;
          const h = parent.clientHeight;
          if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
            canvas.width = w * dpr;
            canvas.height = h * dpr;
            canvas.style.width = `${w}px`;
            canvas.style.height = `${h}px`;
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
          }
        }

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        for (const p of particles) {
          p.progress += dt * animationSpeed * p.speed;
          if (p.progress > 1) p.progress -= 1;

          // Unified timeline cutoff
          const effectiveProgress = p.progress * animationProgress;

          const pathInfo = interpolatePath(effectiveProgress);

          const dispersionScale = (1 - effectiveProgress * 0.75) * 0.018;
          const perpLat = Math.cos(p.offsetAngle) * p.offsetRadius * dispersionScale;
          const perpLng = Math.sin(p.offsetAngle) * p.offsetRadius * dispersionScale;

          const finalLat = pathInfo.lat + perpLat;
          const finalLng = pathInfo.lng + perpLng;

          let pt: maplibregl.Point;
          try {
            pt = map.project([finalLng, finalLat]);
          } catch {
            continue;
          }

          let fade = 1;
          if (effectiveProgress < 0.05) fade = effectiveProgress / 0.05;
          else if (effectiveProgress > 0.95) fade = (1 - effectiveProgress) / 0.05;

          const alpha = p.opacity * fade * 0.88;
          const colorObj = getParticleColorRGB(effectiveProgress);

          const trailLength = 7 * p.size;
          const dx = Math.cos(pathInfo.headingRad) * trailLength;
          const dy = Math.sin(pathInfo.headingRad) * trailLength;

          // Motion tail
          ctx.beginPath();
          ctx.moveTo(pt.x - dx, pt.y + dy);
          ctx.lineTo(pt.x, pt.y);
          ctx.strokeStyle = `rgba(${colorObj.r}, ${colorObj.g}, ${colorObj.b}, ${alpha * 0.5})`;
          ctx.lineWidth = p.size * 0.9;
          ctx.stroke();

          // Particle outer bloom
          ctx.beginPath();
          ctx.arc(pt.x, pt.y, p.size + 2, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${colorObj.r}, ${colorObj.g}, ${colorObj.b}, ${alpha * 0.4})`;
          ctx.fill();

          // Particle core
          ctx.beginPath();
          ctx.arc(pt.x, pt.y, p.size, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${colorObj.r}, ${colorObj.g}, ${colorObj.b}, ${alpha})`;
          ctx.fill();
        }

        animFrame = requestAnimationFrame(render);
      };

      animFrame = requestAnimationFrame(render);
      return () => cancelAnimationFrame(animFrame);
    }, [sourcePoints, activeLayers["trajectory"], animationProgress, animationSpeed]);

    // ── WIND STREAMLINES ──
    React.useEffect(() => {
      const canvas = windCanvasRef.current;
      if (!canvas || !activeLayers["wind"]) {
        if (canvas) {
          const ctx = canvas.getContext("2d");
          if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
        return;
      }

      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const parent = canvas.parentElement;
      const width = parent?.clientWidth ?? 800;
      const height = parent?.clientHeight ?? 600;

      // Use grid data for per-particle vectors if available, else fallback to fixed angle
      const hasGrid = envGrid?.windU && envGrid?.windV && envGrid?.lats && envGrid?.lons;
      const fallbackAngleRad = (242 * Math.PI) / 180;
      const fallbackVx = Math.cos(fallbackAngleRad) * 45;
      const fallbackVy = Math.sin(fallbackAngleRad) * 45;

      const windParticles = Array.from({ length: 180 }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        life: Math.random() * 70,
        maxLife: 50 + Math.random() * 40,
        speed: 0.6 + Math.random() * 0.6,
      }));

      let animFrame: number;
      let lastTime = 0;

      const render = (time: number) => {
        const dt = lastTime ? Math.min((time - lastTime) / 1000, 0.05) : 0.016;
        lastTime = time;

        const dpr = window.devicePixelRatio || 1;
        if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
          canvas.width = width * dpr;
          canvas.height = height * dpr;
          canvas.style.width = `${width}px`;
          canvas.style.height = `${height}px`;
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }

        ctx.globalCompositeOperation = "destination-out";
        ctx.fillStyle = "rgba(0, 0, 0, 0.07)";
        ctx.fillRect(0, 0, width, height);
        ctx.globalCompositeOperation = "source-over";

        const bounds = mapRef.current?.getBounds();

        for (const p of windParticles) {
          let vx = fallbackVx;
          let vy = fallbackVy;

          if (hasGrid && bounds) {
            const lon = bounds.getWest() + (p.x / width) * (bounds.getEast() - bounds.getWest());
            const lat = bounds.getNorth() - (p.y / height) * (bounds.getNorth() - bounds.getSouth());
            const u = bilinearGridValue(envGrid!.windU!, envGrid!.lats!, envGrid!.lons!, lat, lon);
            const v = bilinearGridValue(envGrid!.windV!, envGrid!.lats!, envGrid!.lons!, lat, lon);
            if (u !== null && v !== null) {
              vx = u * 8.0;
              vy = -v * 8.0; // screen y is flipped
            }
          }

          const prevX = p.x;
          const prevY = p.y;
          p.x += vx * dt * animationSpeed * p.speed;
          p.y += vy * dt * animationSpeed * p.speed;
          p.life += dt * animationSpeed * 30;

          if (p.x < -20 || p.x > width + 20 || p.y < -20 || p.y > height + 20 || p.life > p.maxLife) {
            p.x = Math.random() * width;
            p.y = Math.random() * height;
            p.life = 0;
            p.maxLife = 50 + Math.random() * 40;
            continue;
          }

          const lifeFrac = p.life / p.maxLife;
          const alpha = Math.sin(lifeFrac * Math.PI) * 0.45;

          ctx.beginPath();
          ctx.moveTo(prevX, prevY);
          ctx.lineTo(p.x, p.y);
          ctx.strokeStyle = `rgba(148, 163, 184, ${alpha})`;
          ctx.lineWidth = 1;
          ctx.stroke();
        }

        animFrame = requestAnimationFrame(render);
      };

      animFrame = requestAnimationFrame(render);
      return () => cancelAnimationFrame(animFrame);
    }, [activeLayers["wind"], animationSpeed, envGrid]);

    // ── OCEAN CURRENT STREAMLINES ──
    React.useEffect(() => {
      const canvas = currentCanvasRef.current;
      if (!canvas || !activeLayers["current"]) {
        if (canvas) {
          const ctx = canvas.getContext("2d");
          if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
        return;
      }

      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const parent = canvas.parentElement;
      const width = parent?.clientWidth ?? 800;
      const height = parent?.clientHeight ?? 600;

      // Use grid data for per-particle vectors if available, else fallback to fixed angle
      const hasGrid = envGrid?.currentU && envGrid?.currentV && envGrid?.lats && envGrid?.lons;
      const fallbackAngleRad = (1.2 * Math.PI) / 180;
      const fallbackVx = Math.cos(fallbackAngleRad) * 25;
      const fallbackVy = Math.sin(fallbackAngleRad) * 25;

      const currentParticles = Array.from({ length: 120 }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        life: Math.random() * 80,
        maxLife: 60 + Math.random() * 40,
        speed: 0.5 + Math.random() * 0.5,
      }));

      let animFrame: number;
      let lastTime = 0;

      const render = (time: number) => {
        const dt = lastTime ? Math.min((time - lastTime) / 1000, 0.05) : 0.016;
        lastTime = time;

        const dpr = window.devicePixelRatio || 1;
        if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
          canvas.width = width * dpr;
          canvas.height = height * dpr;
          canvas.style.width = `${width}px`;
          canvas.style.height = `${height}px`;
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }

        ctx.globalCompositeOperation = "destination-out";
        ctx.fillStyle = "rgba(0, 0, 0, 0.06)";
        ctx.fillRect(0, 0, width, height);
        ctx.globalCompositeOperation = "source-over";

        const bounds = mapRef.current?.getBounds();

        for (const p of currentParticles) {
          let vx = fallbackVx;
          let vy = fallbackVy;

          if (hasGrid && bounds) {
            const lon = bounds.getWest() + (p.x / width) * (bounds.getEast() - bounds.getWest());
            const lat = bounds.getNorth() - (p.y / height) * (bounds.getNorth() - bounds.getSouth());
            const u = bilinearGridValue(envGrid!.currentU!, envGrid!.lats!, envGrid!.lons!, lat, lon);
            const v = bilinearGridValue(envGrid!.currentV!, envGrid!.lats!, envGrid!.lons!, lat, lon);
            if (u !== null && v !== null) {
              vx = u * 15.0;
              vy = -v * 15.0; // screen y is flipped
            }
          }

          const prevX = p.x;
          const prevY = p.y;
          p.x += vx * dt * animationSpeed * p.speed;
          p.y += vy * dt * animationSpeed * p.speed;
          p.life += dt * animationSpeed * 25;

          if (p.x < -20 || p.x > width + 20 || p.y < -20 || p.y > height + 20 || p.life > p.maxLife) {
            p.x = Math.random() * width;
            p.y = Math.random() * height;
            p.life = 0;
            p.maxLife = 60 + Math.random() * 40;
            continue;
          }

          const lifeFrac = p.life / p.maxLife;
          const alpha = Math.sin(lifeFrac * Math.PI) * 0.5;

          ctx.beginPath();
          ctx.moveTo(prevX, prevY);
          ctx.lineTo(p.x, p.y);
          ctx.strokeStyle = `rgba(34, 211, 238, ${alpha * 0.6})`;
          ctx.lineWidth = 1.2;
          ctx.stroke();
        }

        animFrame = requestAnimationFrame(render);
      };

      animFrame = requestAnimationFrame(render);
      return () => cancelAnimationFrame(animFrame);
    }, [activeLayers["current"], animationSpeed, envGrid]);

    return (
      <div className="relative h-full w-full overflow-hidden bg-base-950">
        <div ref={mapContainerRef} className="h-full w-full" />

        <div className="pointer-events-none absolute inset-0 z-[5]">
          <canvas ref={particleCanvasRef} className="h-full w-full" />
        </div>
        <div className="pointer-events-none absolute inset-0 z-[4]">
          <canvas ref={windCanvasRef} className="h-full w-full" />
        </div>
        <div className="pointer-events-none absolute inset-0 z-[4]">
          <canvas ref={currentCanvasRef} className="h-full w-full" />
        </div>
      </div>
    );
  }
);

export default DriftMapView;
