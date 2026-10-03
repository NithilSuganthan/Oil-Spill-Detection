import type {
  AnalyticsSummary,
  AttributionResult,
  DriftResult,
  EnvironmentalGrid,
  Incident,
  IncidentFilters,
  InvestigationResult,
  SatelliteScene,
  StoredReport,
  SystemStatus,
  TimeRange,
} from "@/lib/types";

/**
 * HTTP implementation of the platform API — talks to the FastAPI backend
 * (see backend/). Wire format is camelCase and mirrors src/lib/types.ts,
 * so responses map 1:1 onto the frontend types.
 *
 * Enabled with NEXT_PUBLIC_API_MODE=real (mock mode never imports this file's
 * functions at runtime).
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

const RANGE_HOURS: Record<TimeRange, number | null> = {
  "6h": 6,
  "24h": 24,
  "7d": null,
};

async function getJSON<T>(path: string, params?: URLSearchParams): Promise<T> {
  const url = `${API_BASE_URL}${path}${params?.size ? `?${params}` : ""}`;
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    throw new Error(`API ${res.status} ${res.statusText}: ${url}`);
  }
  return (await res.json()) as T;
}

function istNow(): number {
  // The demo dataset is anchored around Aug 2026; in real operation the
  // backend applies its own windowing and this only bounds nothing.
  return Date.now();
}

export async function getIncidents(
  filters: Partial<IncidentFilters> = {}
): Promise<Incident[]> {
  const { search = "", levels = [], timeRange = "24h", region = "All India Region" } = filters;

  const params = new URLSearchParams();
  const cutoff = RANGE_HOURS[timeRange];
  if (cutoff !== null) {
    const start = new Date(istNow() - cutoff * 3_600_000);
    params.set("start", start.toISOString());
  }
  if (levels.length > 0) {
    // lowest bound of the selected confidence bands; exact band filtering below
    params.set("min_confidence", String(Math.min(...bandsOf(levels))));
  }

  const incidents = await getJSON<Incident[]>("/spills", params);

  const q = search.trim().toLowerCase();
  return incidents.filter((inc) => {
    if (q && !`${inc.id} ${inc.locationDescription}`.toLowerCase().includes(q)) return false;
    if (levels.length > 0 && !levels.includes(inc.level)) return false;
    if (region !== "All India Region" && inc.region !== region) return false;
    return true;
  });
}

function bandsOf(levels: Incident["level"][]): number[] {
  const bands: Record<Incident["level"], number> = { HIGH: 0.8, MEDIUM: 0.65, LOW: 0.0 };
  return levels.map((l) => bands[l]);
}

export async function getAllIncidents(): Promise<Incident[]> {
  return getJSON<Incident[]>("/spills");
}

export async function getIncident(id: string): Promise<Incident | null> {
  try {
    return await getJSON<Incident>(`/spills/${encodeURIComponent(id)}`);
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) return null;
    throw err;
  }
}

export async function getSatelliteScenes(): Promise<SatelliteScene[]> {
  return getJSON<SatelliteScene[]>("/satellite/scenes");
}

export async function getScene(id: string): Promise<SatelliteScene | null> {
  try {
    return await getJSON<SatelliteScene>(`/satellite/scenes/${encodeURIComponent(id)}`);
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) return null;
    throw err;
  }
}

export async function getAnalytics(): Promise<AnalyticsSummary> {
  return getJSON<AnalyticsSummary>("/analytics/summary");
}

export async function getSystemStatus(): Promise<SystemStatus> {
  return getJSON<SystemStatus>("/system/status");
}

export async function getAttribution(
  incidentId: string
): Promise<AttributionResult | null> {
  try {
    return await getJSON<AttributionResult>(
      `/attribution/${encodeURIComponent(incidentId)}`
    );
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) return null;
    throw err;
  }
}

export async function analyzeAttribution(
  incidentId: string
): Promise<AttributionResult> {
  const res = await fetch(`${API_BASE_URL}/attribution/analyze`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ incidentId }),
  });
  if (!res.ok) {
    throw new Error(`API ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as AttributionResult;
}

export async function getDrift(
  incidentId: string
): Promise<DriftResult | null> {
  try {
    return await getJSON<DriftResult>(
      `/drift/${encodeURIComponent(incidentId)}`
    );
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) return null;
    throw err;
  }
}

export async function runInvestigation(
  incidentId: string
): Promise<InvestigationResult> {
  const res = await fetch(`${API_BASE_URL}/investigation/${encodeURIComponent(incidentId)}/run`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) {
    throw new Error(`API ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as InvestigationResult;
}

export async function generateReport(
  incidentId: string
): Promise<StoredReport> {
  const res = await fetch(`${API_BASE_URL}/reports/investigation/${encodeURIComponent(incidentId)}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) {
    throw new Error(`API ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as StoredReport;
}

export async function getReport(
  incidentId: string
): Promise<StoredReport | null> {
  try {
    return await getJSON<StoredReport>(
      `/reports/investigation/${encodeURIComponent(incidentId)}`
    );
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) return null;
    throw err;
  }
}

export async function listReports(): Promise<StoredReport[]> {
  return getJSON<StoredReport[]>("/reports");
}

export interface PipelineJob {
  id: string;
  sceneId: string;
  state: string;
  error: string | null;
  createdAt: string;
  updatedAt: string;
  history: Array<{ state: string; at: string }>;
}

export async function getPipelineJobs(sceneId?: string): Promise<PipelineJob[]> {
  const params = sceneId ? new URLSearchParams({ scene_id: sceneId }) : undefined;
  return getJSON<PipelineJob[]>("/pipeline/jobs", params);
}

export interface SceneProcessingState {
  sceneId: string;
  state: string;
  isRealData: boolean;
  note: string | null;
  availableProducts: string[];
  previewAvailable: boolean;
  preprocessing?: {
    status: string;
    calibrationMethod: string;
    calibrationUnits: string;
    outputCrs: string;
    outputs: string[];
    previews: string[];
    gcps: number;
    qualityFailures: string[];
    elapsedS: number;
  };
}

export async function getSceneProcessing(sceneId: string): Promise<SceneProcessingState | null> {
  try {
    return await getJSON<SceneProcessingState>(
      `/satellite/scenes/${encodeURIComponent(sceneId)}/processing`
    );
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) return null;
    throw err;
  }
}

export interface SatelliteProviderInfo {
  name: string;
  isReal: boolean;
  description: string;
  note: string | null;
}

export async function getSatelliteProvider(): Promise<SatelliteProviderInfo> {
  return getJSON<SatelliteProviderInfo>("/satellite/scenes/provider");
}

export async function getEnvironmentalGrid(
  lat: number,
  lon: number,
  timestamp: string,
): Promise<EnvironmentalGrid> {
  const res = await fetch(`${API_BASE_URL}/environmental/grid`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ lat, lon, timestamp }),
  });
  if (!res.ok) {
    throw new Error(`API ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as EnvironmentalGrid;
}

// ── Real-time AIS Stream ───────────────────────────────────────────────

export interface AISStreamStatus {
  connected: boolean;
  freshness: string;
  total_vessels: number;
  recent_vessels: number;
  total_messages: number;
  last_message_time: string | null;
  reconnect_count: number;
}

export async function getAISStatus(): Promise<AISStreamStatus> {
  return getJSON<AISStreamStatus>("/ais/status");
}

export async function getAISVessels(): Promise<GeoJSON.FeatureCollection> {
  return getJSON<GeoJSON.FeatureCollection>("/ais/vessels");
}

export async function getAISVesselsNearby(
  west: number,
  south: number,
  east: number,
  north: number,
): Promise<GeoJSON.FeatureCollection> {
  const params = new URLSearchParams({
    west: String(west),
    south: String(south),
    east: String(east),
    north: String(north),
  });
  return getJSON<GeoJSON.FeatureCollection>("/ais/vessels/nearby", params);
}

// ── SSE: Real-time AIS stream ─────────────────────────────────────────

export type AISStreamEventType = "ais.status" | "ais.vessels.update";

export interface AISStreamEvent {
  type: AISStreamEventType;
  payload: Record<string, unknown>;
}

export function connectAISStream(
  onEvent: (event: AISStreamEvent) => void,
  onError?: (error: Event) => void,
): () => void {
  const eventSource = new EventSource(`${API_BASE_URL}/ais/stream`);

  eventSource.addEventListener("ais.status", ((e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data);
      onEvent({ type: "ais.status", payload: data.payload ?? data });
    } catch { /* ignore parse errors */ }
  }) as EventListener);

  eventSource.addEventListener("ais.vessels.update", ((e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data);
      onEvent({ type: "ais.vessels.update", payload: data.payload ?? data });
    } catch { /* ignore parse errors */ }
  }) as EventListener);

  eventSource.onerror = onError ?? (() => {});

  return () => {
    eventSource.close();
  };
}
