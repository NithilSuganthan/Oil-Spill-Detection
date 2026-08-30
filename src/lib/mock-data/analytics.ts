import type {
  AnalyticsSummary,
  ConfidenceBucket,
  DailyStat,
  HourlyPoint,
  RegionStat,
} from "@/lib/types";

const DAILY: DailyStat[] = [
  { date: "19 Aug", detections: 6, highConfidence: 3, areaKm2: 41.2, scenesProcessed: 31 },
  { date: "20 Aug", detections: 9, highConfidence: 4, areaKm2: 63.8, scenesProcessed: 35 },
  { date: "21 Aug", detections: 7, highConfidence: 3, areaKm2: 48.1, scenesProcessed: 33 },
  { date: "22 Aug", detections: 12, highConfidence: 7, areaKm2: 96.5, scenesProcessed: 40 },
  { date: "23 Aug", detections: 8, highConfidence: 4, areaKm2: 57.3, scenesProcessed: 36 },
  { date: "24 Aug", detections: 11, highConfidence: 6, areaKm2: 84.9, scenesProcessed: 39 },
  { date: "25 Aug", detections: 14, highConfidence: 9, areaKm2: 127.4, scenesProcessed: 38 },
];

const HOURLY: HourlyPoint[] = [
  { hour: "00", detections: 0 },
  { hour: "02", detections: 0 },
  { hour: "04", detections: 1 },
  { hour: "06", detections: 1 },
  { hour: "08", detections: 2 },
  { hour: "10", detections: 2 },
  { hour: "12", detections: 3 },
  { hour: "14", detections: 2 },
  { hour: "16", detections: 2 },
  { hour: "18", detections: 1 },
];

const BY_REGION: RegionStat[] = [
  { region: "Gulf of Kutch", detections: 14, areaKm2: 118.6 },
  { region: "Gulf of Khambhat", detections: 11, areaKm2: 74.2 },
  { region: "Arabian Sea", detections: 9, areaKm2: 92.4 },
  { region: "Coromandel Coast", detections: 7, areaKm2: 41.8 },
  { region: "Northern Bay of Bengal", detections: 6, areaKm2: 38.5 },
  { region: "Malabar Coast", detections: 5, areaKm2: 22.1 },
  { region: "Andaman Sea", detections: 4, areaKm2: 19.7 },
  { region: "Lakshadweep Sea", detections: 2, areaKm2: 6.3 },
];

const CONFIDENCE_BUCKETS: ConfidenceBucket[] = [
  { bucket: "50–60%", count: 9 },
  { bucket: "60–70%", count: 12 },
  { bucket: "70–80%", count: 15 },
  { bucket: "80–90%", count: 18 },
  { bucket: "90–100%", count: 4 },
];

export const ANALYTICS_SUMMARY: AnalyticsSummary = {
  totals: {
    detections: 14,
    highConfidence: 9,
    totalAreaKm2: 127.4,
    scenesProcessed: 38,
  },
  daily: DAILY,
  hourly: HOURLY,
  byRegion: BY_REGION,
  confidenceBuckets: CONFIDENCE_BUCKETS,
};
