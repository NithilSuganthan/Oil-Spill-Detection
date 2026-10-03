"use client";

import * as React from "react";
import maplibregl, { type Map as MapLibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Incident } from "@/lib/types";
import { useAppStore } from "@/lib/store/use-app-store";
import { satelliteStyle, getStyleForMode } from "@/components/map/map-config";
import { SAR_SWATHS } from "@/lib/mock-data/sar-swaths";
import { REALTIME_AIS_GEOJSON } from "@/lib/mock-data/realtime-ais";
import type { VesselData } from "@/components/globe/vessel-inspector";
import type { SarSceneData } from "@/components/globe/sar-inspector";

function getSeverityColor(confidence: number): string {
  if (confidence >= 0.8) return "#ef4444";
  if (confidence >= 0.6) return "#f59e0b";
  return "#22c55e";
}

function createIncidentMarker(
  incident: Incident,
  isSelected: boolean,
  onClick: () => void,
): maplibregl.Marker {
  const color = getSeverityColor(incident.confidence);
  const size = isSelected ? 22 : 14;
  const container = document.createElement("div");
  container.className = "incident-globe-marker-wrapper relative cursor-pointer z-20";

  const el = document.createElement("div");
  el.className = "incident-globe-marker";
  el.style.cssText = `
    width: ${size}px;
    height: ${size}px;
    border-radius: 50%;
    background: ${color};
    border: ${isSelected ? "3px" : "2px"} solid #ffffff;
    box-shadow: 0 0 ${isSelected ? "20px" : "10px"} ${color};
    transition: all 0.2s ease;
  `;

  const pulse = document.createElement("div");
  pulse.style.cssText = `
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: ${size + 14}px;
    height: ${size + 14}px;
    border-radius: 50%;
    border: 2px solid ${color};
    animation: globe-pulse-ring 2s ease-out infinite;
    pointer-events: none;
  `;
  container.appendChild(pulse);
  container.appendChild(el);

  container.addEventListener("click", (e) => {
    e.stopPropagation();
    onClick();
  });

  return new maplibregl.Marker({ element: container })
    .setLngLat([incident.centroid.lon, incident.centroid.lat])
    .setOffset([0, 0]);
}

function addMarkers(
  map: maplibregl.Map,
  incidents: Incident[],
  selectedIncidentId: string | null,
  selectIncident: (inc: Incident, opts: { flyTo: boolean }) => void,
  onIncidentSelect?: (inc: Incident) => void,
): maplibregl.Marker[] {
  const markers: maplibregl.Marker[] = [];
  for (const incident of incidents) {
    const isSelected = incident.id === selectedIncidentId;
    const marker = createIncidentMarker(incident, isSelected, () => {
      selectIncident(incident, { flyTo: true });
      onIncidentSelect?.(incident);
    });
    marker.addTo(map);
    markers.push(marker);
  }
  return markers;
}

export interface GlobeMapViewProps {
  incidents: Incident[];
  onIncidentSelect?: (incident: Incident) => void;
  onVesselSelect?: (vessel: VesselData) => void;
  onSarSelect?: (scene: SarSceneData) => void;
  vesselGeoJSON?: GeoJSON.FeatureCollection | null;
  selectedVesselMmsi?: string | null;
  activeLayers?: Record<string, boolean>;
  searchTarget?: [number, number] | null;
  className?: string;
}

export function GlobeMapView({
  incidents = [],
  onIncidentSelect,
  onVesselSelect,
  onSarSelect,
  vesselGeoJSON,
  selectedVesselMmsi,
  activeLayers = {},
  searchTarget,
  className,
}: GlobeMapViewProps) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const mapRef = React.useRef<MapLibreMap | null>(null);
  const markersRef = React.useRef<maplibregl.Marker[]>([]);
  const readyRef = React.useRef(false);
  const [ready, setReady] = React.useState(false);

  const selectedIncidentId = useAppStore((s) => s.selectedIncidentId);
  const selectIncident = useAppStore((s) => s.selectIncident);
  const mapStyle = useAppStore((s) => s.mapStyle);

  const effectiveVesselGeoJSON = React.useMemo(() => {
    if (vesselGeoJSON && vesselGeoJSON.features && vesselGeoJSON.features.length > 0) {
      return vesselGeoJSON;
    }
    return REALTIME_AIS_GEOJSON;
  }, [vesselGeoJSON]);

  /* ---------- Map Initialization ---------- */
  React.useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    let isMounted = true;

    try {
      const map = new maplibregl.Map({
        container: containerRef.current,
        style: satelliteStyle(),
        center: [78.5, 15.0],
        zoom: 0.85,
        pitch: 0,
        minZoom: 0.2,
        maxZoom: 18,
        dragRotate: true,
        pitchWithRotate: true,
        touchZoomRotate: true,
        attributionControl: { compact: true },
        projection: { type: "globe" },
      } as maplibregl.MapOptions);
      mapRef.current = map;

      map.addControl(
        new maplibregl.NavigationControl({ showCompass: true, visualizePitch: true }),
        "top-right",
      );

      const finishInit = () => {
        if (!isMounted || readyRef.current) return;
        if (!map.isStyleLoaded()) return;
        readyRef.current = true;
        setReady(true);
        try {
          addSarSwathsLayer(map, onSarSelect);
          addVesselTracksLayer(map, selectedVesselMmsi);
          addOceanCurrentFlowLayer(map);
          addWindFlowLayer(map);
          addVesselLayer(map, effectiveVesselGeoJSON, onVesselSelect);
        } catch (e) {
          console.warn("Globe layer init error caught safely:", e);
        }
      };

      map.once("load", finishInit);

      map.on("idle", () => {
        if (!readyRef.current && map.isStyleLoaded()) {
          finishInit();
        }
      });
    } catch (err) {
      console.error("Globe map init error:", err);
      setReady(true);
    }

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
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      mapRef.current?.remove();
      mapRef.current = null;
      readyRef.current = false;
    };
  }, [effectiveVesselGeoJSON, onSarSelect, onVesselSelect]);

  /* ---------- Dynamic Basemap Style Switching ---------- */
  React.useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    try {
      map.setStyle(getStyleForMode(mapStyle));
    } catch {
      return;
    }

    const onStyleLoad = () => {
      try { map.setProjection({ type: "globe" }); } catch { /* ignore */ }

      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      const mapNow = mapRef.current;
      if (!mapNow || !mapNow.isStyleLoaded()) return;

      markersRef.current = addMarkers(
        mapNow,
        incidents,
        selectedIncidentId,
        selectIncident,
        onIncidentSelect,
      );

      try {
        addSarSwathsLayer(mapNow, onSarSelect);
        addVesselTracksLayer(mapNow, selectedVesselMmsi);
        addOceanCurrentFlowLayer(mapNow);
        addWindFlowLayer(mapNow);
        addVesselLayer(mapNow, effectiveVesselGeoJSON, onVesselSelect);
      } catch (e) {
        console.warn("Globe style-switch layer re-add caught safely:", e);
      }
    };

    map.on("style.load", onStyleLoad);
    return () => {
      map.off("style.load", onStyleLoad);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapStyle]);

  /* ---------- Update Active Layers Visibility ---------- */
  React.useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    const setVis = (layerId: string, visible: boolean) => {
      if (map.getLayer(layerId)) {
        try {
          map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
        } catch { /* ignore */ }
      }
    };

    setVis("vessel-circles", activeLayers.ais !== false);
    setVis("vessel-labels", activeLayers.ais !== false);
    setVis("vessel-tracks-line", activeLayers["ais-tracks"] !== false);
    setVis("vessel-tracks-selected", activeLayers["ais-tracks"] !== false);
    setVis("vessel-tracks-pulse-dots", activeLayers["ais-tracks"] !== false);
    setVis("sar-swaths-fill", activeLayers.sar !== false);
    setVis("sar-swaths-outline", activeLayers.sar !== false);
    setVis("sar-swaths-label", activeLayers.sar !== false);

    // Ocean Currents layers
    setVis("ocean-currents-glow", activeLayers.current !== false);
    setVis("ocean-currents-lines", activeLayers.current !== false);
    setVis("ocean-currents-arrows", activeLayers.current !== false);
    setVis("ocean-currents-labels", activeLayers.current !== false);

    // Wind Streamlines layers
    setVis("wind-lines-glow", activeLayers.wind !== false);
    setVis("wind-lines", activeLayers.wind !== false);
    setVis("wind-arrows", activeLayers.wind !== false);
    setVis("wind-labels", activeLayers.wind !== false);

    setVis("carto-labels", activeLayers.labels !== false);

    markersRef.current.forEach((m) => {
      const el = m.getElement();
      el.style.display = activeLayers.oil !== false ? "block" : "none";
    });
  }, [activeLayers, ready]);

  /* ---------- Update Selected Vessel Track ---------- */
  React.useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !map.isStyleLoaded()) return;
    try {
      addVesselTracksLayer(map, selectedVesselMmsi);
    } catch { /* ignore */ }
  }, [selectedVesselMmsi, ready]);

  /* ---------- Update Incident Markers ---------- */
  React.useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    markersRef.current.forEach((m) => m.remove());
    markersRef.current = addMarkers(
      map,
      incidents,
      selectedIncidentId,
      selectIncident,
      onIncidentSelect,
    );
  }, [incidents, ready, selectedIncidentId, selectIncident, onIncidentSelect]);

  /* ---------- Update AIS Vessel Layer ---------- */
  React.useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !map.isStyleLoaded()) return;

    try {
      addVesselLayer(map, effectiveVesselGeoJSON, onVesselSelect);
    } catch { /* ignore */ }
  }, [effectiveVesselGeoJSON, ready, onVesselSelect]);

  /* ---------- Fly to Search Target ---------- */
  React.useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !searchTarget) return;

    map.flyTo({
      center: searchTarget,
      zoom: 6.8,
      pitch: 40,
      duration: 2200,
      curve: 1.6,
      essential: true,
    });
  }, [searchTarget, ready]);

  return (
    <div className={className ? `relative ${className}` : "relative h-full w-full overflow-hidden bg-[#020617]"}>
      <div
        className="pointer-events-none absolute inset-0 z-[1] flex items-center justify-center"
        style={{
          background:
            "radial-gradient(circle at 50% 50%, rgba(56,189,248,0.18) 0%, rgba(14,165,233,0.06) 42%, transparent 70%)",
        }}
      />
      <div
        ref={containerRef}
        className="h-full w-full bg-[#020617]"
        role="application"
        aria-label="3D Earth Satellite Observation Sphere"
      />

      {!ready && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-base-950/90 backdrop-blur-md">
          <div className="flex flex-col items-center gap-3">
            <div className="h-10 w-10 animate-spin rounded-full border-2 border-transparent border-t-cyan-400 border-r-cyan-400/40" />
            <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-cyan-300 font-extrabold">
              INITIALIZING 3D EARTH SATELLITE OBSERVER...
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// ── SAR Swaths Layer ──────────────────────────────────────────────────

function addSarSwathsLayer(map: maplibregl.Map, onSarSelect?: (scene: SarSceneData) => void) {
  if (map.getSource("sar-swaths")) return;

  const geojson: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: SAR_SWATHS.map((swath) => ({
      type: "Feature",
      properties: {
        id: swath.id,
        label: swath.label,
        satellite: swath.satellite,
        passTime: swath.passTime,
        polarization: "VV + VH",
        processingLevel: "GRD (Ground Range Detected)",
        timeliness: "NRT (1h)",
        productId: `S1A_IW_GRDH_1SDV_${swath.id}`,
      },
      geometry: {
        type: "Polygon",
        coordinates: [swath.coordinates],
      },
    })),
  };

  map.addSource("sar-swaths", {
    type: "geojson",
    data: geojson,
  });

  map.addLayer({
    id: "sar-swaths-fill",
    type: "fill",
    source: "sar-swaths",
    paint: {
      "fill-color": "#38bdf8",
      "fill-opacity": 0.18,
    },
  });

  map.addLayer({
    id: "sar-swaths-outline",
    type: "line",
    source: "sar-swaths",
    paint: {
      "line-color": "#38bdf8",
      "line-width": 1.5,
      "line-dasharray": [4, 3],
      "line-opacity": 0.9,
    },
  });

  map.addLayer({
    id: "sar-swaths-label",
    type: "symbol",
    source: "sar-swaths",
    layout: {
      "text-field": ["get", "label"],
      "text-size": 10,
      "text-anchor": "top-left",
      "text-offset": [1, 1],
      "text-allow-overlap": false,
    },
    paint: {
      "text-color": "#38bdf8",
      "text-halo-color": "#020617",
      "text-halo-width": 2,
    },
  });

  map.on("click", "sar-swaths-fill", (e) => {
    if (!e.features || e.features.length === 0) return;
    const feat = e.features[0];
    const props = feat.properties as any;
    if (onSarSelect && props) {
      onSarSelect({
        id: props.id,
        satellite: props.satellite,
        passTime: props.passTime ? props.passTime.replace("T", " ").replace("Z", "") : "04 Sep 18:32",
        polarization: props.polarization || "VV + VH",
        processingLevel: props.processingLevel || "GRD",
        timeliness: props.timeliness || "NRT",
        productId: props.productId || props.id,
      });
    }
  });

  map.on("mouseenter", "sar-swaths-fill", () => {
    map.getCanvas().style.cursor = "pointer";
  });
  map.on("mouseleave", "sar-swaths-fill", () => {
    map.getCanvas().style.cursor = "";
  });
}

// ── Vessel Trajectories Layer ──────────────────────────────────────────

function addVesselTracksLayer(map: maplibregl.Map, selectedMmsi?: string | null) {
  const sourceId = "vessel-tracks";
  const pulseSourceId = "vessel-tracks-pulses";

  const trackFeatures: GeoJSON.Feature[] = REALTIME_AIS_GEOJSON.features.map((feat) => {
    const coords = (feat.geometry as any).coordinates;
    const props = (feat.properties || {}) as any;
    const heading = props.heading || 0;
    const rad = (heading * Math.PI) / 180;
    
    const p1: [number, number] = [coords[0] - Math.sin(rad) * 4.8, coords[1] - Math.cos(rad) * 4.8];
    const p2: [number, number] = [coords[0] - Math.sin(rad) * 3.2 + 0.3, coords[1] - Math.cos(rad) * 3.2 - 0.2];
    const p3: [number, number] = [coords[0] - Math.sin(rad) * 1.5 - 0.1, coords[1] - Math.cos(rad) * 1.5 + 0.1];
    const p4: [number, number] = [coords[0], coords[1]];

    return {
      type: "Feature",
      properties: {
        mmsi: props.mmsi,
        name: props.name,
        isSelected: props.mmsi === selectedMmsi,
      },
      geometry: {
        type: "LineString",
        coordinates: [p1, p2, p3, p4],
      },
    };
  });

  const pulseFeatures: GeoJSON.Feature[] = REALTIME_AIS_GEOJSON.features.flatMap((feat) => {
    const coords = (feat.geometry as any).coordinates;
    const props = (feat.properties || {}) as any;
    const heading = props.heading || 0;
    const rad = (heading * Math.PI) / 180;
    
    const waypoints: [number, number][] = [
      [coords[0] - Math.sin(rad) * 3.2 + 0.3, coords[1] - Math.cos(rad) * 3.2 - 0.2],
      [coords[0] - Math.sin(rad) * 1.5 - 0.1, coords[1] - Math.cos(rad) * 1.5 + 0.1],
    ];

    return waypoints.map((pt) => ({
      type: "Feature",
      properties: { mmsi: props.mmsi, isSelected: props.mmsi === selectedMmsi },
      geometry: { type: "Point", coordinates: pt },
    }));
  });

  const geojson: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: trackFeatures,
  };

  const pulseGeojson: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: pulseFeatures,
  };

  if (map.getSource(sourceId)) {
    (map.getSource(sourceId) as maplibregl.GeoJSONSource).setData(geojson);
    if (map.getSource(pulseSourceId)) {
      (map.getSource(pulseSourceId) as maplibregl.GeoJSONSource).setData(pulseGeojson);
    }
    return;
  }

  map.addSource(sourceId, { type: "geojson", data: geojson });
  map.addSource(pulseSourceId, { type: "geojson", data: pulseGeojson });

  map.addLayer({
    id: "vessel-tracks-line",
    type: "line",
    source: sourceId,
    paint: {
      "line-color": "#38bdf8",
      "line-width": 1.8,
      "line-dasharray": [4, 3],
      "line-opacity": 0.75,
    },
  });

  map.addLayer({
    id: "vessel-tracks-selected",
    type: "line",
    source: sourceId,
    filter: ["==", ["get", "mmsi"], selectedMmsi || ""],
    paint: {
      "line-color": "#00f2fe",
      "line-width": 4.2,
      "line-opacity": 1.0,
    },
  });

  map.addLayer({
    id: "vessel-tracks-pulse-dots",
    type: "circle",
    source: pulseSourceId,
    paint: {
      "circle-radius": [
        "case",
        ["get", "isSelected"],
        5.5,
        3.0
      ],
      "circle-color": [
        "case",
        ["get", "isSelected"],
        "#00f2fe",
        "#38bdf8"
      ],
      "circle-opacity": 0.85,
      "circle-stroke-width": 1,
      "circle-stroke-color": "#ffffff",
    },
  });
}

// ── Ocean Currents Flow Layer (CMEMS - Electric Cyan Gyres + Labels) ────

function addOceanCurrentFlowLayer(map: maplibregl.Map) {
  if (map.getSource("ocean-currents-flow")) return;

  const oceanCurrentData: { label: string; speed: string; path: [number, number][] }[] = [
    {
      label: "SOMALI CURRENT (0.62 m/s)",
      speed: "0.62 m/s",
      path: [[48.0, 4.0], [54.0, 9.5], [62.0, 15.0], [70.0, 19.5], [74.0, 22.0]],
    },
    {
      label: "EQUATORIAL COUNTERCURRENT (0.45 m/s)",
      speed: "0.45 m/s",
      path: [[52.0, -2.0], [64.0, -1.5], [76.0, -1.0], [88.0, -0.5], [98.0, 0.0]],
    },
    {
      label: "SOUTH-EAST ARABIAN SEA GYRE (0.38 m/s)",
      speed: "0.38 m/s",
      path: [[68.0, 8.0], [72.0, 11.5], [75.0, 15.0], [72.0, 17.5], [67.0, 14.0]],
    },
    {
      label: "BAY OF BENGAL OCEANIC STREAM (0.42 m/s)",
      speed: "0.42 m/s",
      path: [[81.0, 6.0], [85.0, 11.0], [89.0, 15.5], [92.0, 19.0], [88.0, 21.5]],
    },
    {
      label: "ANDAMAN SEA CURRENT (0.35 m/s)",
      speed: "0.35 m/s",
      path: [[92.0, 5.0], [95.0, 8.5], [97.0, 12.0], [94.0, 15.0]],
    },
    {
      label: "MALACCA COASTAL STREAM (0.50 m/s)",
      speed: "0.50 m/s",
      path: [[98.0, 1.5], [101.0, 3.2], [104.0, 5.0]],
    },
  ];

  const flowLines: GeoJSON.Feature[] = oceanCurrentData.map((c) => ({
    type: "Feature",
    properties: { label: c.label, speed: c.speed },
    geometry: { type: "LineString", coordinates: c.path },
  }));

  const arrowPoints: GeoJSON.Feature[] = oceanCurrentData.flatMap((c) => {
    const midIdx = Math.floor(c.path.length / 2);
    return [c.path[midIdx]].map((pt) => ({
      type: "Feature",
      properties: { label: c.label },
      geometry: { type: "Point", coordinates: pt },
    }));
  });

  map.addSource("ocean-currents-flow", {
    type: "geojson",
    data: { type: "FeatureCollection", features: flowLines },
  });

  map.addSource("ocean-currents-labels-src", {
    type: "geojson",
    data: { type: "FeatureCollection", features: arrowPoints },
  });

  // Soft cyan background glow line
  map.addLayer({
    id: "ocean-currents-glow",
    type: "line",
    source: "ocean-currents-flow",
    paint: {
      "line-color": "#00f2fe",
      "line-width": 6.0,
      "line-opacity": 0.25,
      "line-blur": 3,
    },
  });

  // Main solid cyan ocean current streamline
  map.addLayer({
    id: "ocean-currents-lines",
    type: "line",
    source: "ocean-currents-flow",
    paint: {
      "line-color": "#00f2fe",
      "line-width": 2.4,
      "line-opacity": 0.85,
    },
  });

  // Arrowhead symbols along current flow
  map.addLayer({
    id: "ocean-currents-arrows",
    type: "symbol",
    source: "ocean-currents-labels-src",
    layout: {
      "text-field": "♒",
      "text-size": 13,
      "text-allow-overlap": false,
    },
    paint: {
      "text-color": "#00f2fe",
      "text-halo-color": "#020617",
      "text-halo-width": 2,
    },
  });

  // Professional oceanographic label badges
  map.addLayer({
    id: "ocean-currents-labels",
    type: "symbol",
    source: "ocean-currents-labels-src",
    layout: {
      "text-field": ["get", "label"],
      "text-size": 9.5,
      "text-offset": [0, 1.4],
      "text-anchor": "top",
      "text-allow-overlap": false,
    },
    paint: {
      "text-color": "#38bdf8",
      "text-halo-color": "#020617",
      "text-halo-width": 2.5,
    },
    minzoom: 1.5,
  });
}

// ── Wind Vectors Flow Layer (ECMWF - Warm Amber Streamlines + Labels) ────

function addWindFlowLayer(map: maplibregl.Map) {
  if (map.getSource("wind-flow")) return;

  const windData: { label: string; path: [number, number][] }[] = [
    {
      label: "ARABIAN SEA WIND FIELD (14 kn SSW)",
      path: [[50.0, 10.0], [58.0, 14.5], [66.0, 18.0], [73.0, 21.0]],
    },
    {
      label: "SW MONSOON VECTOR (16 kn SW)",
      path: [[56.0, 2.0], [64.0, 7.0], [72.0, 12.0], [80.0, 16.5]],
    },
    {
      label: "EQUATORIAL WIND FLOW (11 kn WSW)",
      path: [[65.0, -4.0], [74.0, 2.0], [82.0, 7.5], [90.0, 13.0]],
    },
    {
      label: "INDIAN OCEAN WIND FIELD (12 kn W)",
      path: [[75.0, -8.0], [84.0, -2.0], [92.0, 4.0], [99.0, 9.0]],
    },
    {
      label: "BAY OF BENGAL FLOW (15 kn SW)",
      path: [[82.0, 10.0], [88.0, 14.5], [93.0, 18.5]],
    },
  ];

  const flowLines: GeoJSON.Feature[] = windData.map((w) => ({
    type: "Feature",
    properties: { label: w.label },
    geometry: { type: "LineString", coordinates: w.path },
  }));

  const arrowPoints: GeoJSON.Feature[] = windData.flatMap((w) => {
    const midIdx = Math.floor(w.path.length / 2);
    return [w.path[midIdx]].map((pt) => ({
      type: "Feature",
      properties: { label: w.label },
      geometry: { type: "Point", coordinates: pt },
    }));
  });

  map.addSource("wind-flow", {
    type: "geojson",
    data: { type: "FeatureCollection", features: flowLines },
  });

  map.addSource("wind-labels-src", {
    type: "geojson",
    data: { type: "FeatureCollection", features: arrowPoints },
  });

  // Soft warm glow line
  map.addLayer({
    id: "wind-lines-glow",
    type: "line",
    source: "wind-flow",
    paint: {
      "line-color": "#f59e0b",
      "line-width": 5.0,
      "line-opacity": 0.22,
      "line-blur": 3,
    },
  });

  // Main amber wind vector line with dash pattern
  map.addLayer({
    id: "wind-lines",
    type: "line",
    source: "wind-flow",
    paint: {
      "line-color": "#f59e0b",
      "line-width": 2.0,
      "line-dasharray": [6, 4],
      "line-opacity": 0.9,
    },
  });

  // Directional wind vector arrows
  map.addLayer({
    id: "wind-arrows",
    type: "symbol",
    source: "wind-labels-src",
    layout: {
      "text-field": "▶",
      "text-size": 12,
      "text-allow-overlap": false,
    },
    paint: {
      "text-color": "#fbbf24",
      "text-halo-color": "#020617",
      "text-halo-width": 2,
    },
  });

  // Professional ECMWF meteorological labels
  map.addLayer({
    id: "wind-labels",
    type: "symbol",
    source: "wind-labels-src",
    layout: {
      "text-field": ["get", "label"],
      "text-size": 9.5,
      "text-offset": [0, -1.4],
      "text-anchor": "bottom",
      "text-allow-overlap": false,
    },
    paint: {
      "text-color": "#fbbf24",
      "text-halo-color": "#020617",
      "text-halo-width": 2.5,
    },
    minzoom: 1.5,
  });
}

// ── AIS Vessel Layer ──────────────────────────────────────────────────

function addVesselLayer(
  map: maplibregl.Map,
  geojson: GeoJSON.FeatureCollection,
  onVesselSelect?: (vessel: VesselData) => void
) {
  const sourceId = "ais-vessels";

  if (map.getLayer("vessel-circles")) map.removeLayer("vessel-circles");
  if (map.getLayer("vessel-labels")) map.removeLayer("vessel-labels");
  if (map.getSource(sourceId)) map.removeSource(sourceId);

  map.addSource(sourceId, {
    type: "geojson",
    data: geojson,
  });

  map.addLayer({
    id: "vessel-circles",
    type: "circle",
    source: sourceId,
    paint: {
      "circle-radius": [
        "interpolate",
        ["linear"],
        ["zoom"],
        0.5, 5.5,
        3, 7.5,
        6, 9.5
      ],
      "circle-color": [
        "case",
        ["has", "color"],
        ["get", "color"],
        "#38bdf8"
      ],
      "circle-stroke-width": 1.8,
      "circle-stroke-color": "#ffffff",
      "circle-stroke-opacity": 0.95,
      "circle-opacity": 1.0,
    },
  });

  map.addLayer({
    id: "vessel-labels",
    type: "symbol",
    source: sourceId,
    layout: {
      "text-field": ["get", "name"],
      "text-size": 9.5,
      "text-offset": [0, 1.5],
      "text-anchor": "top",
      "text-allow-overlap": false,
    },
    paint: {
      "text-color": "#ffffff",
      "text-halo-color": "#020617",
      "text-halo-width": 2,
    },
    minzoom: 1.8,
  });

  map.on("click", "vessel-circles", (e) => {
    if (!e.features || e.features.length === 0) return;
    const feat = e.features[0];
    const props = feat.properties as any;
    const coords = (feat.geometry as any).coordinates;
    if (onVesselSelect && props) {
      onVesselSelect({
        mmsi: props.mmsi || "413298410",
        name: props.name || "MV OCEAN SPIRIT",
        vesselType: props.type || "Cargo",
        lat: coords[1],
        lon: coords[0],
        sog: props.sog || 14.2,
        heading: props.heading || 112,
        lastUpdate: "23:25:43 IST",
      });
    }
  });

  map.on("mouseenter", "vessel-circles", () => {
    map.getCanvas().style.cursor = "pointer";
  });
  map.on("mouseleave", "vessel-circles", () => {
    map.getCanvas().style.cursor = "";
  });
}
