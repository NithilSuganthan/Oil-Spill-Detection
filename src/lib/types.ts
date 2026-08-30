export type ConfidenceLevel = "HIGH" | "MEDIUM" | "LOW";

export interface Centroid {
  lat: number;
  lon: number;
}

export interface BoundingBox {
  west: number;
  south: number;
  east: number;
  north: number;
}

/** GeoJSON Polygon ring: [lon, lat] pairs. Mirrors what the backend will emit. */
export type Ring = [number, number][];

export interface SpillGeometry {
  type: "Polygon";
  coordinates: Ring[];
}

export interface SatelliteScene {
  id: string;
  platform: "Sentinel-1A" | "Sentinel-1B";
  sensor: "SAR C-band";
  acquisitionMode: "IW" | "EW";
  polarisation: string;
  acquiredAt: string; // ISO 8601 (IST offset implied by formatter)
  processedAt: string;
  footprint: BoundingBox;
  status: "processed" | "processing" | "queued";
}

export type IncidentStatus = "completed" | "processing" | "review";

export interface Incident {
  id: string;
  confidence: number; // 0..1
  areaKm2: number;
  perimeterKm2: number;
  centroid: Centroid;
  geometry: SpillGeometry;
  detectedAt: string; // ISO 8601
  region: IndianRegion;
  locationDescription: string;
  satellite: SatelliteScene["platform"];
  sceneId: string;
  model: string;
  modelVersion: string;
  status: IncidentStatus;
  level: ConfidenceLevel;
  windSpeedKts: number;
  estimatedVolumeTons: number | null;
}

export const INDIAN_REGIONS = [
  "All India Region",
  "Arabian Sea",
  "Bay of Bengal",
  "Gulf of Kutch",
  "Gulf of Khambhat",
  "Konkan Coast",
  "Malabar Coast",
  "Coromandel Coast",
  "Northern Bay of Bengal",
  "Andaman Sea",
  "Lakshadweep Sea",
] as const;

export type IndianRegion = Exclude<(typeof INDIAN_REGIONS)[number], "All India Region">;

export type TimeRange = "6h" | "24h" | "7d";

export interface IncidentFilters {
  search: string;
  levels: ConfidenceLevel[];
  timeRange: TimeRange;
  region: string;
}

export type MapLayerId =
  | "detections"
  | "scene-coverage"
  | "ais-vessels"
  | "ais-tracks"
  | "drift-trajectories"
  | "source-probability"
  | "candidate-vessels";

export interface MapLayerDef {
  id: MapLayerId;
  label: string;
  available: boolean;
  phase: number;
  defaultOn: boolean;
}

export interface SystemService {
  name: string;
  status: "LIVE" | "RUNNING" | "OPERATIONAL" | "CONNECTED";
}

export interface SystemStatus {
  services: SystemService[];
  activeScene: {
    id: string;
    platform: string;
    acquiredAt: string;
    processedAt: string;
    status: string;
  };
}

export interface DailyStat {
  date: string;
  detections: number;
  highConfidence: number;
  areaKm2: number;
  scenesProcessed: number;
}

export interface RegionStat {
  region: string;
  detections: number;
  areaKm2: number;
}

export interface ConfidenceBucket {
  bucket: string;
  count: number;
}

export interface HourlyPoint {
  hour: string;
  detections: number;
}

export interface AnalyticsSummary {
  totals: {
    detections: number;
    highConfidence: number;
    totalAreaKm2: number;
    scenesProcessed: number;
  };
  daily: DailyStat[];
  hourly: HourlyPoint[];
  byRegion: RegionStat[];
  confidenceBuckets: ConfidenceBucket[];
}

// ── AIS Vessel Correlation (Phase 4) ─────────────────────────────────

export interface ScoreComponents {
  distance: number;
  time: number;
  trackConsistency: number;
}

export interface CandidateVessel {
  mmsi: string;
  vesselName: string | null;
  imo: string | null;
  vesselType: string | null;
  flag: string | null;
  numberOfObservations: number;
  closestDistanceKm: number;
  closestTimestamp: string | null;
  closestTimeDifferenceMinutes: number | null;
  meanDistanceKm: number;
  firstObservation: string | null;
  lastObservation: string | null;
  attributionScore: number;
  scoreComponents: ScoreComponents | null;
  qualityFlags: string[];
  humanReviewRequired: boolean;
  // Phase 8: Intelligence signals
  gapSignals?: Array<{
    mmsi: string;
    gapStart: string | null;
    gapEnd: string | null;
    gapDurationHours: number;
    distanceToDetectionKm: number;
    gapScore: number;
    explanation: string;
  }>;
  staticSpacing?: {
    mmsi: string;
    isStaticSpaced: boolean;
    spacingIntervalMinutes: number;
    distanceKm: number;
    confidence: number;
    explanation: string;
  } | null;
}

export interface SearchWindow {
  start: string;
  end: string;
  centerLat: number;
  centerLon: number;
  radiusKm: number;
  timeWindowHours: number;
}

export interface AttributionResult {
  incidentId: string;
  searchWindow: SearchWindow;
  coverageKnown: boolean;
  provider: string;
  dataset: string;
  candidateCount: number;
  candidates: CandidateVessel[];
  totalObservations: number;
  analyzedAt: string | null;
  provenance: Record<string, unknown>;
  // Phase 8: Intelligence (embedded from attribution endpoint)
  intelligence?: DetectionIntelligence | null;
}

// ── Drift / Source Estimate (Phase 5) ─────────────────────────────────

export interface DriftTrajectory {
  points: Array<[number, number, string]>; // [lat, lon, timestamp]
}

export interface DriftResult {
  incidentId: string;
  method: string;
  slickLatitude: number;
  slickLongitude: number;
  observationTime: string;
  integrationHours: number;
  timestepMinutes: number;
  ensembleSize: number;
  sourceLatitude: number;
  sourceLongitude: number;
  sourceEarliest: string;
  sourceLatest: string;
  uncertaintyKm: number;
  uncertaintyHours: number;
  confidence: number;
  qualityFlags: string[];
  sourcePoints: Array<[number, number]>; // [lat, lon]
  provenance: Record<string, unknown>;
  analyzedAt: string | null;
}

export interface InvestigationResult {
  incidentId: string;
  drift: DriftResult | null;
  attribution: AttributionResult | null;
  intelligence?: DetectionIntelligence | null;
  environment: "DEMO" | "MIXED" | "REAL";
  status: "completed" | "failed";
}

// ── Phase 8: Detection Intelligence ────────────────────────────────────

export interface DetectionIntelligence {
  confidenceBreakdown: ConfidenceBreakdownResponse;
  lookAlikeScreening: LookAlikeScreening;
  environmentalReliability: EnvironmentalReliabilityInfo;
  smallDetection: SmallDetectionInfo;
  seasonalPrior: SeasonalPriorInfo;
  calibration: CalibrationInfo;
  aisGap: AISGapInfo;
  staticSpacing: StaticSpacingInfo;
  vesselEvidence: VesselEvidence[];
  provenance: Record<string, unknown>;
}

export interface ConfidenceBreakdownResponse {
  rawModelConfidence: number;
  adjustedConfidence: number;
  confidenceBand: "HIGH" | "MEDIUM" | "LOW";
  lookLikePenalty: number;
  environmentalPenalty: number;
  smallDetectionPenalty: number;
  calibrationShift: number;
  seasonalPriorAdjustment: number;
  lookLikeStatus: string;
  environmentalStatus: string;
  calibrationStatus: string;
  smallDetectionStatus: string;
  seasonalPriorStatus: string;
  lookLikeExplanation: string;
  environmentalExplanation: string;
  smallDetectionExplanation: string;
}

export interface LookAlikeScreening {
  status: string;
  pLookLike: number;
  penalty: number;
  textureStatus: string;
  explanation: string;
}

export interface EnvironmentalReliabilityInfo {
  status: string;
  band: string;
  windSpeedKnots: number;
  waveHeightM: number | null;
  currentSpeedMs: number;
  penalty: number;
  explanation: string;
}

export interface SmallDetectionInfo {
  status: string;
  areaKm2: number;
  pixelCount: number;
  isSubThreshold: boolean;
  risk: string;
  explanation: string;
  recommendedAction: string;
}

export interface SeasonalPriorInfo {
  status: string;
  month: number;
  factor: number;
  adjustment: number;
  explanation: string;
}

export interface CalibrationInfo {
  status: string;
  calibratedConfidence: number | null;
  calibrationShift: number;
  explanation: string;
}

export interface AISGapInfo {
  status: string;
  explanation: string;
}

export interface StaticSpacingInfo {
  status: string;
  explanation: string;
}

export interface VesselEvidence {
  mmsi: string;
  attributionScore: number;
  distanceScore: number | null;
  timeScore: number | null;
  trackConsistencyScore: number | null;
  aisGapStatus: string;
  aisGapScore: number | null;
  staticSpacingStatus: string;
  staticSpacingScore: number | null;
  vesselTypePrior: number | null;
  evidenceAvailability: string;
}

// ── Phase 9: Investigation Reports ─────────────────────────────────────

export interface CandidateAssessment {
  mmsi: string;
  vesselName: string;
  attributionScore: number;
  explanation: string;
}

export interface InvestigationReport {
  title: string;
  executiveSummary: string;
  detectionAssessment: string;
  environmentAssessment: string;
  driftAssessment: string;
  aisAssessment: string;
  candidateAssessments: CandidateAssessment[];
  uncertainty: string;
  recommendedActions: string[];
  limitations: string[];
  humanReviewRequired: boolean;
}

export interface StoredReport {
  reportId: string;
  incidentId: string;
  generatedAt: string;
  provider: string;
  model: string;
  evidenceVersion: string;
  promptVersion: string;
  report: InvestigationReport;
}
