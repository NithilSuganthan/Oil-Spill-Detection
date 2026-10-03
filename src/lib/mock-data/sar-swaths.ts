export interface SarSwath {
  id: string;
  satellite: "Sentinel-1A" | "Sentinel-1B";
  passTime: string;
  label: string;
  coordinates: [number, number][]; // Polygon ring [lon, lat]
}

export const SAR_SWATHS: SarSwath[] = [
  {
    id: "S1A-20260904-1832",
    satellite: "Sentinel-1A",
    passTime: "2026-09-04T18:32:00Z",
    label: "S1A · 04 Sep 18:32 UTC",
    coordinates: [
      [64.5, 23.5],
      [72.2, 21.0],
      [69.8, 12.5],
      [62.1, 15.0],
      [64.5, 23.5],
    ],
  },
  {
    id: "S1B-20260904-1721",
    satellite: "Sentinel-1B",
    passTime: "2026-09-04T17:21:00Z",
    label: "S1B · 04 Sep 17:21 UTC",
    coordinates: [
      [90.2, 19.8],
      [97.5, 17.4],
      [94.8, 8.2],
      [87.5, 10.6],
      [90.2, 19.8],
    ],
  },
  {
    id: "S1A-20260904-1645",
    satellite: "Sentinel-1A",
    passTime: "2026-09-04T16:45:00Z",
    label: "S1A · 04 Sep 16:45 UTC",
    coordinates: [
      [73.5, 2.5],
      [80.8, 0.1],
      [77.2, -10.5],
      [69.9, -8.1],
      [73.5, 2.5],
    ],
  },
];
