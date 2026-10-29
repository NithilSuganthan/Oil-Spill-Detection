"use client";

import * as React from "react";
import maplibregl, { type Map as MapLibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { OperationalAlert } from "@/lib/types";

interface AlertMapProps {
  alerts: OperationalAlert[];
  selectedAlert: OperationalAlert | null;
  onSelectAlert: (alert: OperationalAlert) => void;
  className?: string;
}

export function AlertMap({
  alerts,
  selectedAlert,
  onSelectAlert,
  className = "",
}: AlertMapProps) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const mapRef = React.useRef<MapLibreMap | null>(null);
  const markersRef = React.useRef<maplibregl.Marker[]>([]);

  // Initialize map
  React.useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          basemap: {
            type: "raster",
            tiles: [
              "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            ],
            tileSize: 256,
            maxzoom: 19,
          },
        },
        layers: [{ id: "basemap", type: "raster", source: "basemap" }],
      },
      center: [78.9629, 15.5],
      zoom: 4.5,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Update markers and polygon layers when alerts or selectedAlert changes
  React.useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Clear previous markers
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    // Create markers for each alert
    alerts.forEach((alert) => {
      const isSelected = selectedAlert?.alertId === alert.alertId;
      const isCritical = alert.severity === "CRITICAL";

      const el = document.createElement("div");
      el.className = "relative flex items-center justify-center cursor-pointer group";

      // Outer pulse ring
      const pulse = document.createElement("span");
      pulse.className = `absolute w-8 h-8 rounded-full opacity-60 animate-ping ${
        isCritical ? "bg-red-500/40" : "bg-orange-500/40"
      }`;

      // Core badge
      const core = document.createElement("div");
      core.className = `relative flex items-center justify-center w-5 h-5 rounded-full border text-[9px] font-mono font-bold shadow-lg transition-transform transform ${
        isSelected ? "scale-125 ring-2 ring-signal-cyan" : "hover:scale-110"
      } ${
        isCritical
          ? "bg-red-950 border-red-500 text-red-300"
          : "bg-orange-950 border-orange-500 text-orange-300"
      }`;
      core.innerText = isCritical ? "!" : "▲";

      el.appendChild(pulse);
      el.appendChild(core);

      el.addEventListener("click", () => {
        onSelectAlert(alert);
      });

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([alert.longitude, alert.latitude])
        .addTo(map);

      markersRef.current.push(marker);
    });

    // Update polygons if available
    const polygonFeatures = alerts
      .filter((a) => a.geometry && a.geometry.type === "Polygon")
      .map((a) => ({
        type: "Feature" as const,
        geometry: a.geometry as GeoJSON.Polygon,
        properties: {
          alertId: a.alertId,
          severity: a.severity,
          isSelected: selectedAlert?.alertId === a.alertId,
        },
      }));

    const updateLayers = () => {
      const source = map.getSource("alert-polygons") as maplibregl.GeoJSONSource | undefined;
      const geojson: GeoJSON.FeatureCollection = {
        type: "FeatureCollection",
        features: polygonFeatures,
      };

      if (source) {
        source.setData(geojson);
      } else if (map.isStyleLoaded()) {
        map.addSource("alert-polygons", {
          type: "geojson",
          data: geojson,
        });

        map.addLayer({
          id: "alert-polygons-fill",
          type: "fill",
          source: "alert-polygons",
          paint: {
            "fill-color": [
              "case",
              ["==", ["get", "severity"], "CRITICAL"],
              "#ef4444",
              "#f97316",
            ],
            "fill-opacity": [
              "case",
              ["==", ["get", "isSelected"], true],
              0.55,
              0.25,
            ],
          },
        });

        map.addLayer({
          id: "alert-polygons-stroke",
          type: "line",
          source: "alert-polygons",
          paint: {
            "line-color": [
              "case",
              ["==", ["get", "severity"], "CRITICAL"],
              "#f87171",
              "#fb923c",
            ],
            "line-width": ["case", ["==", ["get", "isSelected"], true], 2.5, 1.5],
            "line-dasharray": [2, 1],
          },
        });
      }
    };

    if (map.isStyleLoaded()) {
      updateLayers();
    } else {
      map.once("load", updateLayers);
    }
  }, [alerts, selectedAlert, onSelectAlert]);

  // Fly to selected alert
  React.useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedAlert) return;

    map.flyTo({
      center: [selectedAlert.longitude, selectedAlert.latitude],
      zoom: 7.5,
      speed: 1.4,
      curve: 1.2,
      essential: true,
    });
  }, [selectedAlert]);

  return (
    <div className={`relative overflow-hidden rounded-lg border border-line/70 bg-base-950 ${className}`}>
      <div ref={containerRef} className="h-full w-full" />
      <div className="absolute top-2 left-2 z-10 flex items-center gap-2 rounded border border-line/60 bg-base-900/80 px-2.5 py-1 text-[10px] font-mono text-ink-dim backdrop-blur-sm">
        <span className="h-2 w-2 rounded-full bg-signal-cyan animate-pulse" />
        <span>SATELLITE IMAGERY · OPERATIONAL EEZ</span>
      </div>
      {selectedAlert && (
        <div className="absolute bottom-2 left-2 z-10 rounded border border-line/60 bg-base-900/90 px-3 py-1.5 text-[10px] font-mono text-ink backdrop-blur-sm">
          <span className="text-ink-faint">FOCUSED: </span>
          <span className="font-semibold text-signal-cyan">{selectedAlert.incidentId}</span>
          <span className="mx-2 text-line">|</span>
          <span className="text-ink-faint">POS: </span>
          <span>
            {selectedAlert.latitude.toFixed(3)}°N, {selectedAlert.longitude.toFixed(3)}°E
          </span>
        </div>
      )}
    </div>
  );
}
