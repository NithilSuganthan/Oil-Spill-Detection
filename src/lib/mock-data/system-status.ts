import type { SystemStatus } from "@/lib/types";

export const SYSTEM_STATUS: SystemStatus = {
  services: [
    { name: "Satellite Feed", status: "LIVE" },
    { name: "Processing Engine", status: "RUNNING" },
    { name: "AI Model", status: "OPERATIONAL" },
    { name: "Database", status: "CONNECTED" },
  ],
  activeScene: {
    id: "S1B_EW_GRDM_20260825T1925",
    platform: "Sentinel-1B",
    acquiredAt: "2026-08-25T19:25:00+05:30",
    processedAt: "—",
    status: "PROCESSING",
  },
};
