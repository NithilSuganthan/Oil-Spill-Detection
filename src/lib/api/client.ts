import type {
  AnalyticsSummary,
  AttributionResult,
  DriftResult,
  Incident,
  IncidentFilters,
  InvestigationResult,
  SatelliteScene,
  StoredReport,
  SystemStatus,
  TimeRange,
} from "@/lib/types";
import { INCIDENTS } from "@/lib/mock-data/incidents";
import { SCENES } from "@/lib/mock-data/scenes";
import { ANALYTICS_SUMMARY } from "@/lib/mock-data/analytics";
import { SYSTEM_STATUS } from "@/lib/mock-data/system-status";

/**
 * API abstraction layer — the ONLY module the frontend uses for data.
 *
 * NEXT_PUBLIC_API_MODE:
 *   "mock" (default) -> resolve against local mock data; no backend needed.
 *   "real"           -> call the FastAPI backend at NEXT_PUBLIC_API_BASE_URL
 *                       (see src/lib/api/http-client.ts and backend/README.md).
 *
 * Both implementations satisfy identical signatures, so components never
 * change when switching modes. In real mode the backend serves demo/seed
 * records flagged `isDemo` until real satellite ingestion is connected.
 */

export const API_MODE: "mock" | "real" =
  process.env.NEXT_PUBLIC_API_MODE === "real" ? "real" : "mock";

const LATENCY_MS = 220;

function delay<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), LATENCY_MS));
}

const RANGE_HOURS: Record<TimeRange, number | null> = {
  "6h": 6,
  "24h": 24,
  "7d": null,
};

function filterMock(
  filters: Partial<IncidentFilters> = {}
): Incident[] {
  const { search = "", levels = [], timeRange = "24h", region = "All India Region" } =
    filters;
  const cutoffHours = RANGE_HOURS[timeRange];
  // Demo dataset anchor (matches src/lib/mock-data timestamps).
  const now = new Date("2026-08-25T19:40:00+05:30").getTime();
  const q = search.trim().toLowerCase();

  return INCIDENTS.filter((inc) => {
    if (q && !`${inc.id} ${inc.locationDescription}`.toLowerCase().includes(q))
      return false;
    if (levels.length > 0 && !levels.includes(inc.level)) return false;
    if (cutoffHours !== null) {
      const ageH = (now - new Date(inc.detectedAt).getTime()) / 3_600_000;
      if (ageH > cutoffHours) return false;
    }
    if (region !== "All India Region" && inc.region !== region) return false;
    return true;
  });
}

/* ------------------------------------------------------------------ */
/* Mock implementation                                                 */
/* ------------------------------------------------------------------ */

const mockApi = {
  async getIncidents(filters?: Partial<IncidentFilters>): Promise<Incident[]> {
    return delay(filterMock(filters));
  },
  async getAllIncidents(): Promise<Incident[]> {
    return delay(INCIDENTS);
  },
  async getIncident(id: string): Promise<Incident | null> {
    return delay(INCIDENTS.find((i) => i.id === id) ?? null);
  },
  async getSatelliteScenes(): Promise<SatelliteScene[]> {
    return delay(SCENES);
  },
  async getScene(id: string): Promise<SatelliteScene | null> {
    return delay(SCENES.find((s) => s.id === id) ?? null);
  },
  async getAnalytics(): Promise<AnalyticsSummary> {
    return delay(ANALYTICS_SUMMARY);
  },
  async getSystemStatus(): Promise<SystemStatus> {
    return Promise.resolve(SYSTEM_STATUS);
  },
  async getAttribution(incidentId: string): Promise<AttributionResult | null> {
    return delay(mockAttribution(incidentId));
  },
  async analyzeAttribution(incidentId: string): Promise<AttributionResult> {
    return delay(mockAttribution(incidentId));
  },
  async getDrift(incidentId: string): Promise<DriftResult | null> {
    return delay(mockDrift(incidentId));
  },
  async runInvestigation(incidentId: string): Promise<InvestigationResult> {
    return delay(mockInvestigation(incidentId));
  },
  async generateReport(incidentId: string): Promise<StoredReport> {
    return delay(mockReport(incidentId));
  },
  async getReport(incidentId: string): Promise<StoredReport | null> {
    return delay(mockReport(incidentId));
  },
  async listReports(): Promise<StoredReport[]> {
    return delay([mockReport("IN-250825-001")]);
  },
};

/* ------------------------------------------------------------------ */
/* Real implementation (FastAPI)                                       */
/* ------------------------------------------------------------------ */

import * as httpApi from "./http-client";

/* ------------------------------------------------------------------ */
/* Active implementation selected by configuration                     */
/* ------------------------------------------------------------------ */

const impl = API_MODE === "real" ? httpApi : mockApi;

/** Mock attribution data for demo incidents. */
function mockAttribution(incidentId: string): AttributionResult {
  const incident = INCIDENTS.find((i) => i.id === incidentId);
  const lat = incident?.centroid?.lat ?? 10.0;
  const lon = incident?.centroid?.lon ?? 72.0;
  return {
    incidentId,
    searchWindow: {
      start: "2026-08-25T19:00:00+05:30",
      end: "2026-08-26T07:00:00+05:30",
      centerLat: lat,
      centerLon: lon,
      radiusKm: 50,
      timeWindowHours: 6,
    },
    coverageKnown: true,
    provider: "mock",
    dataset: "DEMO AIS \u2014 not real data",
    candidateCount: 3,
    candidates: [
      {
        mmsi: "987654321",
        vesselName: "PACIFIC CARRIER",
        imo: "9876543",
        vesselType: "Cargo",
        flag: "IND",
        numberOfObservations: 5,
        closestDistanceKm: 0.33,
        closestTimestamp: "2026-08-26T01:00:00+05:30",
        closestTimeDifferenceMinutes: 0,
        meanDistanceKm: 3.21,
        firstObservation: "2026-08-25T21:00:00+05:30",
        lastObservation: "2026-08-26T05:00:00+05:30",
        attributionScore: 0.87,
        scoreComponents: { distance: 0.99, time: 1.0, trackConsistency: 0.65 },
        qualityFlags: [],
        humanReviewRequired: true,
      },
      {
        mmsi: "987654323",
        vesselName: "COASTAL FISHER",
        imo: null,
        vesselType: "Fishing",
        flag: "IND",
        numberOfObservations: 6,
        closestDistanceKm: 2.01,
        closestTimestamp: "2026-08-26T01:00:00+05:30",
        closestTimeDifferenceMinutes: 0,
        meanDistanceKm: 2.54,
        firstObservation: "2026-08-25T15:00:00+05:30",
        lastObservation: "2026-08-26T01:00:00+05:30",
        attributionScore: 0.79,
        scoreComponents: { distance: 0.96, time: 1.0, trackConsistency: 0.80 },
        qualityFlags: [],
        humanReviewRequired: true,
      },
      {
        mmsi: "987654322",
        vesselName: "ARABIAN TRADER",
        imo: "9876544",
        vesselType: "Tanker",
        flag: "LKA",
        numberOfObservations: 4,
        closestDistanceKm: 4.48,
        closestTimestamp: "2026-08-25T23:00:00+05:30",
        closestTimeDifferenceMinutes: -120,
        meanDistanceKm: 9.87,
        firstObservation: "2026-08-25T20:00:00+05:30",
        lastObservation: "2026-08-26T02:00:00+05:30",
        attributionScore: 0.61,
        scoreComponents: { distance: 0.91, time: 0.67, trackConsistency: 0.50 },
        qualityFlags: [],
        humanReviewRequired: true,
      },
    ],
    totalObservations: 24,
    analyzedAt: "2026-08-26T20:00:00+05:30",
    provenance: { provider: "mock", dataset: "DEMO AIS \u2014 not real data" },
  };
}

/** Mock drift data for demo incidents. */
function mockDrift(incidentId: string): DriftResult {
  const incident = INCIDENTS.find((i) => i.id === incidentId);
  const lat = incident?.centroid?.lat ?? 10.0;
  const lon = incident?.centroid?.lon ?? 72.0;
  return {
    incidentId,
    method: "first_order_backward_hindcast",
    slickLatitude: lat,
    slickLongitude: lon,
    observationTime: "2026-08-26T01:00:00Z",
    integrationHours: 24,
    timestepMinutes: 15,
    ensembleSize: 50,
    sourceLatitude: lat - 0.08,
    sourceLongitude: lon - 0.12,
    sourceEarliest: "2026-08-25T01:00:00Z",
    sourceLatest: "2026-08-25T05:00:00Z",
    uncertaintyKm: 12.5,
    uncertaintyHours: 4.0,
    confidence: 0.62,
    qualityFlags: ["DEMO_ENVIRONMENTAL_FORCING"],
    sourcePoints: Array.from({ length: 50 }, (_, i) => [
      lat - 0.08 + (Math.sin(i * 0.5) * 0.02),
      lon - 0.12 + (Math.cos(i * 0.5) * 0.02),
    ]),
    provenance: {
      provider: "first_order",
      environmentalProvider: "mock",
      windageCoefficient: 0.03,
      nParticles: 50,
    },
    analyzedAt: "2026-08-26T20:00:00Z",
  };
}

/** Mock investigation combining drift + attribution. */
function mockInvestigation(incidentId: string): InvestigationResult {
  return {
    incidentId,
    drift: mockDrift(incidentId),
    attribution: mockAttribution(incidentId),
    environment: "DEMO",
    status: "completed",
  };
}

/** Mock investigation report for demo. */
function mockReport(incidentId: string): StoredReport {
  return {
    reportId: `RPT-${incidentId}-mock`,
    incidentId,
    generatedAt: new Date().toISOString(),
    provider: "mock",
    model: "mock",
    evidenceVersion: "1.0",
    promptVersion: "1.0",
    report: {
      title: `Investigation Report — ${incidentId}`,
      executiveSummary: `This investigation of incident ${incidentId} identified a detection with raw model confidence 85.0% (adjusted: 78.0%). The detected area covers 10.00 km². The highest-ranked potential source vessel is PACIFIC CARRIER (MMSI 987654321) with an attribution score of 0.870.`,
      detectionAssessment: "The SAR detection was made by TinyUNet (version 1.0-dev). Raw confidence: 85.0%. Adjusted confidence: 78.0%. Calibration status: NOT_CALIBRATED. This is a model prediction requiring human verification.",
      environmentAssessment: "Environmental data provider: mock. Status: DEMO. Reliability band: GOOD. WARNING: Environmental data is synthetic (DEMO mode).",
      driftAssessment: "Drift hindcast method: first_order_backward_hindcast. Estimated source: (14.9200, 72.8800). Uncertainty: 12.5 km. Ensemble size: 50.",
      aisAssessment: "AIS provider: gfw. Data availability: AVAILABLE. Vessels found: 3. Observations: 24.",
      candidateAssessments: [
        { mmsi: "987654321", vesselName: "PACIFIC CARRIER", attributionScore: 0.87, explanation: "Vessel ranked highly because it was 0.33 km from the estimated source region and its observation time was 0 minutes from the estimated release window." },
      ],
      uncertainty: "Source uncertainty: 12.5 km spatial, 4.0 hours temporal. Confidence: 62.0%. Environmental forcing: DEMO.",
      recommendedActions: ["Human verification of SAR detection required", "Review additional satellite imagery if available", "Verify vessel identification against AIS records", "Obtain real environmental data for production use"],
      limitations: ["This is an AI-generated summary based on system evidence", "All vessel associations are potential — human review required", "Confidence calibration is NOT_CALIBRATED", "Environmental data is synthetic (DEMO mode)", "AIS gap analysis requires raw transmission-level data"],
      humanReviewRequired: true,
    },
  };
}

export function getIncidents(
  filters: Partial<IncidentFilters> = {}
): Promise<Incident[]> {
  return impl.getIncidents(filters);
}

export function getAllIncidents(): Promise<Incident[]> {
  return impl.getAllIncidents();
}

export function getIncident(id: string): Promise<Incident | null> {
  return impl.getIncident(id);
}

export function getSatelliteScenes(): Promise<SatelliteScene[]> {
  return impl.getSatelliteScenes();
}

export function getScene(id: string): Promise<SatelliteScene | null> {
  return impl.getScene(id);
}

export function getAnalytics(): Promise<AnalyticsSummary> {
  return impl.getAnalytics();
}

export function getSystemStatus(): Promise<SystemStatus> {
  return impl.getSystemStatus();
}

export function getAttribution(incidentId: string): Promise<AttributionResult | null> {
  return impl.getAttribution(incidentId);
}

export function analyzeAttribution(incidentId: string): Promise<AttributionResult> {
  return impl.analyzeAttribution(incidentId);
}

export function getDrift(incidentId: string): Promise<DriftResult | null> {
  return impl.getDrift(incidentId);
}

export function runInvestigation(incidentId: string): Promise<InvestigationResult> {
  return impl.runInvestigation(incidentId);
}

export function generateReport(incidentId: string): Promise<StoredReport> {
  return impl.generateReport(incidentId);
}

export function getReport(incidentId: string): Promise<StoredReport | null> {
  return impl.getReport(incidentId);
}

export function listReports(): Promise<StoredReport[]> {
  return impl.listReports();
}
