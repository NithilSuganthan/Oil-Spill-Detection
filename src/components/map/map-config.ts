import type { StyleSpecification } from "maplibre-gl";

/**
 * Map style resolution.
 *
 * Priority:
 *   1. NEXT_PUBLIC_MAP_STYLE_URL env var (any MapLibre-compatible style,
 *      e.g. a commercial satellite/dark style that needs its own key server-side)
 *   2. Free CARTO dark-matter vector basemap (no API key required)
 *
 * This keeps the visual identity stable while allowing the basemap provider
 * to be swapped without touching component code.
 */
const ENV_STYLE_URL = process.env.NEXT_PUBLIC_MAP_STYLE_URL;

export const DEFAULT_CENTER: [number, number] = [81.5, 14.8];
export const DEFAULT_ZOOM = 4.55;
export const INDIA_BOUNDS: [[number, number], [number, number]] = [
  [65.0, 4.0],
  [95.5, 25.5],
];

export function getMapStyleUrl(): string {
  return (
    ENV_STYLE_URL ||
    "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
  );
}

/** Raster fallback style (used if the primary style fails to load). */
export function buildFallbackStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {
      basemap: {
        type: "raster",
        tiles: [
          "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
          "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        ],
        tileSize: 256,
        attribution:
          '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> © <a href="https://carto.com/attributions">CARTO</a>',
      },
    },
    layers: [{ id: "basemap", type: "raster", source: "basemap" }],
  };
}

export interface CoastalCity {
  name: string;
  lon: number;
  lat: number;
}

export const COASTAL_CITIES: CoastalCity[] = [
  { name: "Mumbai", lon: 72.8777, lat: 19.076 },
  { name: "Kandla", lon: 70.2167, lat: 23.0333 },
  { name: "Goa", lon: 73.8278, lat: 15.4909 },
  { name: "Kochi", lon: 76.2673, lat: 9.9312 },
  { name: "Chennai", lon: 80.2707, lat: 13.0827 },
  { name: "Visakhapatnam", lon: 83.2186, lat: 17.7231 },
  { name: "Kolkata", lon: 88.3639, lat: 22.5726 },
  { name: "Port Blair", lon: 92.7265, lat: 11.6743 },
];

export const SEA_LABELS: CoastalCity[] = [
  { name: "ARABIAN SEA", lon: 70.5, lat: 12.5 },
  { name: "BAY OF BENGAL", lon: 88.0, lat: 13.5 },
  { name: "INDIAN OCEAN", lon: 78.0, lat: 4.5 },
];
