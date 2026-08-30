import type {
  ConfidenceLevel,
  Incident,
  IndianRegion,
  Ring,
} from "@/lib/types";

/**
 * Deterministic PRNG so mock geometry is stable across reloads,
 * mimicking stored GeoJSON from the future backend.
 */
function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Builds an irregular elongated slick polygon around a centroid. */
export function makeSlickRing(
  lon: number,
  lat: number,
  headingDeg: number,
  lengthKm: number,
  widthKm: number,
  seed: number
): Ring {
  const rand = mulberry32(seed);
  const pts: Ring = [];
  const n = 16;
  const rad = (headingDeg * Math.PI) / 180;
  const ux = Math.cos(rad);
  const uy = Math.sin(rad); // local frame: x along-track, y cross-track
  const degPerKmLat = 1 / 111;
  const degPerKmLon = 1 / (111 * Math.cos((lat * Math.PI) / 180));

  for (let i = 0; i < n; i++) {
    const theta = (i / n) * Math.PI * 2;
    // elongated blob: longer axis along heading
    const rAlong = (lengthKm / 2) * Math.cos(theta);
    const rCross = (widthKm / 2) * Math.sin(theta);
    // organic jitter
    const j = 0.78 + rand() * 0.44;
    const ax = rAlong * ux - rCross * uy;
    const ay = rAlong * uy + rCross * ux;
    pts.push([
      +(lon + ax * degPerKmLon * j).toFixed(5),
      +(lat + ay * degPerKmLat * j).toFixed(5),
    ]);
  }
  pts.push(pts[0]); // close ring
  return pts;
}

interface SeedIncident {
  id: string;
  confidence: number;
  areaKm2: number;
  perimeterKm: number;
  lat: number;
  lon: number;
  heading: number;
  lengthKm: number;
  widthKm: number;
  detectedAt: string;
  region: IndianRegion;
  locationDescription: string;
  satellite: "Sentinel-1A" | "Sentinel-1B";
  sceneId: string;
  status: Incident["status"];
  windSpeedKts: number;
  estimatedVolumeTons: number | null;
}

const SEED_INCIDENTS: SeedIncident[] = [
  {
    id: "IN-250825-001",
    confidence: 0.914,
    areaKm2: 18.4,
    perimeterKm: 21.6,
    lat: 15.2965,
    lon: 72.8456,
    heading: 62,
    lengthKm: 8.2,
    widthKm: 3.1,
    detectedAt: "2026-08-25T18:31:00+05:30",
    region: "Arabian Sea",
    locationDescription: "Arabian Sea · Off Maharashtra Coast",
    satellite: "Sentinel-1A",
    sceneId: "S1A_IW_GRDH_20260825T1820",
    status: "completed",
    windSpeedKts: 9,
    estimatedVolumeTons: 42,
  },
  {
    id: "IN-250825-002",
    confidence: 0.847,
    areaKm2: 7.2,
    perimeterKm: 13.9,
    lat: 20.108,
    lon: 72.391,
    heading: 118,
    lengthKm: 4.9,
    widthKm: 2.0,
    detectedAt: "2026-08-25T17:52:00+05:30",
    region: "Gulf of Khambhat",
    locationDescription: "Gulf of Khambhat · Off Gujarat Coast",
    satellite: "Sentinel-1A",
    sceneId: "S1A_IW_GRDH_20260825T1745",
    status: "completed",
    windSpeedKts: 12,
    estimatedVolumeTons: 18,
  },
  {
    id: "IN-250825-003",
    confidence: 0.713,
    areaKm2: 3.8,
    perimeterKm: 9.4,
    lat: 13.204,
    lon: 80.612,
    heading: 205,
    lengthKm: 3.6,
    widthKm: 1.5,
    detectedAt: "2026-08-25T16:44:00+05:30",
    region: "Coromandel Coast",
    locationDescription: "Bay of Bengal · Off Tamil Nadu Coast",
    satellite: "Sentinel-1B",
    sceneId: "S1B_IW_GRDH_20260825T1638",
    status: "completed",
    windSpeedKts: 11,
    estimatedVolumeTons: null,
  },
  {
    id: "IN-250825-004",
    confidence: 0.689,
    areaKm2: 2.1,
    perimeterKm: 6.7,
    lat: 9.618,
    lon: 75.824,
    heading: 340,
    lengthKm: 2.8,
    widthKm: 1.1,
    detectedAt: "2026-08-25T15:36:00+05:30",
    region: "Malabar Coast",
    locationDescription: "Arabian Sea · Off Kerala Coast",
    satellite: "Sentinel-1B",
    sceneId: "S1B_IW_GRDH_20260825T1530",
    status: "review",
    windSpeedKts: 14,
    estimatedVolumeTons: null,
  },
  {
    id: "IN-250825-005",
    confidence: 0.552,
    areaKm2: 1.0,
    perimeterKm: 4.1,
    lat: 19.342,
    lon: 86.418,
    heading: 95,
    lengthKm: 1.9,
    widthKm: 0.8,
    detectedAt: "2026-08-25T14:28:00+05:30",
    region: "Northern Bay of Bengal",
    locationDescription: "Bay of Bengal · Off Odisha Coast",
    satellite: "Sentinel-1A",
    sceneId: "S1A_IW_GRDH_20260825T1422",
    status: "review",
    windSpeedKts: 16,
    estimatedVolumeTons: null,
  },
  {
    id: "IN-250825-006",
    confidence: 0.882,
    areaKm2: 11.6,
    perimeterKm: 16.8,
    lat: 22.574,
    lon: 69.318,
    heading: 45,
    lengthKm: 6.4,
    widthKm: 2.6,
    detectedAt: "2026-08-25T12:14:00+05:30",
    region: "Gulf of Kutch",
    locationDescription: "Gulf of Kutch · Off Gujarat Coast",
    satellite: "Sentinel-1A",
    sceneId: "S1A_IW_GRDH_20260825T1205",
    status: "completed",
    windSpeedKts: 8,
    estimatedVolumeTons: 31,
  },
  {
    id: "IN-250824-011",
    confidence: 0.765,
    areaKm2: 5.4,
    perimeterKm: 11.2,
    lat: 11.632,
    lon: 93.214,
    heading: 150,
    lengthKm: 4.2,
    widthKm: 1.8,
    detectedAt: "2026-08-24T21:05:00+05:30",
    region: "Andaman Sea",
    locationDescription: "Andaman Sea · Off Port Blair Approach",
    satellite: "Sentinel-1B",
    sceneId: "S1B_IW_GRDH_20260824T2058",
    status: "completed",
    windSpeedKts: 10,
    estimatedVolumeTons: null,
  },
  {
    id: "IN-250824-007",
    confidence: 0.583,
    areaKm2: 1.7,
    perimeterKm: 5.6,
    lat: 10.512,
    lon: 71.806,
    heading: 280,
    lengthKm: 2.4,
    widthKm: 1.0,
    detectedAt: "2026-08-24T18:47:00+05:30",
    region: "Lakshadweep Sea",
    locationDescription: "Lakshadweep Sea · East of Kavaratti",
    satellite: "Sentinel-1A",
    sceneId: "S1A_EW_GRDM_20260824T1840",
    status: "review",
    windSpeedKts: 13,
    estimatedVolumeTons: null,
  },
  {
    id: "IN-250824-003",
    confidence: 0.821,
    areaKm2: 6.9,
    perimeterKm: 12.4,
    lat: 17.894,
    lon: 85.562,
    heading: 75,
    lengthKm: 4.7,
    widthKm: 2.1,
    detectedAt: "2026-08-24T15:12:00+05:30",
    region: "Northern Bay of Bengal",
    locationDescription: "Bay of Bengal · Off Visakhapatnam",
    satellite: "Sentinel-1A",
    sceneId: "S1A_IW_GRDH_20260824T1506",
    status: "completed",
    windSpeedKts: 11,
    estimatedVolumeTons: null,
  },
];

export function confidenceLevel(confidence: number): ConfidenceLevel {
  if (confidence >= 0.8) return "HIGH";
  if (confidence >= 0.65) return "MEDIUM";
  return "LOW";
}

export const INCIDENTS: Incident[] = SEED_INCIDENTS.map((s, i) => ({
  id: s.id,
  confidence: s.confidence,
  areaKm2: s.areaKm2,
  perimeterKm2: s.perimeterKm,
  centroid: { lat: s.lat, lon: s.lon },
  geometry: {
    type: "Polygon",
    coordinates: [makeSlickRing(s.lon, s.lat, s.heading, s.lengthKm, s.widthKm, 1000 + i * 37)],
  },
  detectedAt: s.detectedAt,
  region: s.region,
  locationDescription: s.locationDescription,
  satellite: s.satellite,
  sceneId: s.sceneId,
  model: "OilSpillNet",
  modelVersion: "v1.0",
  status: s.status,
  level: confidenceLevel(s.confidence),
  windSpeedKts: s.windSpeedKts,
  estimatedVolumeTons: s.estimatedVolumeTons,
}));
