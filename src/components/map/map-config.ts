import type { StyleSpecification } from "maplibre-gl";
import type { MapStyle } from "@/lib/types";

export const DEFAULT_CENTER: [number, number] = [81.5, 14.8];
export const DEFAULT_ZOOM = 0.8;
export const INDIA_BOUNDS: [[number, number], [number, number]] = [
  [65.0, 4.0],
  [95.5, 25.5],
];

/** Attribution strings for each provider */
const ESRI_ATTRIBUTION =
  '© <a href="https://www.esri.com/en-us/arcgis/products/data">Esri</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
const ESRI_OCEAN_ATTRIBUTION =
  '© <a href="https://www.esri.com/en-us/arcgis/products/data">Esri</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> © <a href="https://www.naturalearthdata.com/">Natural Earth</a>';
const CARTO_ATTRIBUTION =
  '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> © <a href="https://carto.com/attributions">CARTO</a>';

/**
 * Satellite basemap — ESRI WorldImagery (global photographic satellite imagery)
 * Colorful land (green forests, brown terrain) and realistic blue ocean water.
 */
export function satelliteStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {
      basemap: {
        type: "raster",
        tiles: [
          "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        ],
        tileSize: 256,
        maxzoom: 19,
        attribution: ESRI_ATTRIBUTION,
      },
      "carto-labels": {
        type: "raster",
        tiles: [
          "https://a.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}@2x.png",
          "https://b.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}@2x.png",
        ],
        tileSize: 256,
        attribution: "",
      },
    },
    layers: [
      { id: "basemap", type: "raster", source: "basemap" },
      { id: "carto-labels", type: "raster", source: "carto-labels" },
    ],
  };
}

/** Dark basemap — CARTO dark_all */
function darkStyle(): StyleSpecification {
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
        attribution: CARTO_ATTRIBUTION,
      },
    },
    layers: [{ id: "basemap", type: "raster", source: "basemap" }],
  };
}

/** Ocean basemap — ESRI Ocean Basemap */
function oceanStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {
      "esri-ocean": {
        type: "raster",
        tiles: [
          "https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}",
        ],
        tileSize: 256,
        attribution: ESRI_OCEAN_ATTRIBUTION,
      },
      "carto-labels": {
        type: "raster",
        tiles: [
          "https://a.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}@2x.png",
          "https://b.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}@2x.png",
        ],
        tileSize: 256,
        attribution: "",
      },
    },
    layers: [
      { id: "esri-ocean", type: "raster", source: "esri-ocean" },
      { id: "carto-labels", type: "raster", source: "carto-labels" },
    ],
  };
}

/** Terrain basemap — ESRI WorldTerrain */
function terrainStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {
      "esri-terrain": {
        type: "raster",
        tiles: [
          "https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}",
        ],
        tileSize: 256,
        attribution: ESRI_ATTRIBUTION,
      },
      "carto-labels": {
        type: "raster",
        tiles: [
          "https://a.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}@2x.png",
          "https://b.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}@2x.png",
        ],
        tileSize: 256,
        attribution: "",
      },
    },
    layers: [
      { id: "esri-terrain", type: "raster", source: "esri-terrain" },
      { id: "carto-labels", type: "raster", source: "carto-labels" },
    ],
  };
}

export function getMapStyleUrl(): StyleSpecification {
  return satelliteStyle();
}

/** Get full MapLibre StyleSpecification for a given mode */
export function getStyleForMode(mode: MapStyle): StyleSpecification {
  switch (mode) {
    case "dark":
      return darkStyle();
    case "ocean":
      return oceanStyle();
    case "terrain":
      return terrainStyle();
    case "satellite":
    default:
      return satelliteStyle();
  }
}

export const BASEMAP_OPTIONS: {
  mode: MapStyle;
  label: string;
  shortLabel: string;
  description: string;
}[] = [
  { mode: "satellite", label: "Satellite", shortLabel: "SAT", description: "High-resolution photographic satellite imagery" },
  { mode: "dark", label: "Dark", shortLabel: "DK", description: "Low-light operational basemap" },
  { mode: "ocean", label: "Ocean", shortLabel: "OCN", description: "Blue maritime basemap with bathymetry" },
  { mode: "terrain", label: "Terrain", shortLabel: "TRN", description: "Topographic relief with elevation tinting" },
];

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
