import type { Incident } from "@/lib/types";

/** Shared confidence → visual treatment mapping used across the app. */
export const LEVEL_META = {
  HIGH: { label: "High", color: "#f87171" },
  MEDIUM: { label: "Medium", color: "#fb923c" },
  LOW: { label: "Low", color: "#facc15" },
} as const;

export function incidentToGeoJSON(incidents: Incident[]) {
  return {
    type: "FeatureCollection" as const,
    features: incidents.map((inc) => ({
      type: "Feature" as const,
      properties: { id: inc.id, level: inc.level },
      geometry: inc.geometry,
    })),
  };
}
