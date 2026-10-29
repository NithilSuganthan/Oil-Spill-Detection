export interface RealtimeVesselFeature {
  type: "Feature";
  properties: {
    mmsi: string;
    name: string;
    type: "Tanker" | "Cargo" | "Passenger" | "Fishing";
    sog: number;
    heading: number;
    flag: string;
    color: string;
  };
  geometry: {
    type: "Point";
    coordinates: [number, number];
  };
}

export const REALTIME_AIS_GEOJSON: GeoJSON.FeatureCollection = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { mmsi: "413298410", name: "MV OCEAN SPIRIT", type: "Cargo", sog: 14.2, heading: 112, flag: "PA", color: "#38bdf8" },
      geometry: { type: "Point", coordinates: [68.4, 15.2] },
    },
    {
      type: "Feature",
      properties: { mmsi: "563048200", name: "SEA HARMONY", type: "Tanker", sog: 11.8, heading: 88, flag: "SG", color: "#f97316" },
      geometry: { type: "Point", coordinates: [72.1, 18.5] },
    },
    {
      type: "Feature",
      properties: { mmsi: "352981000", name: "GLOBAL TRADER", type: "Cargo", sog: 15.6, heading: 145, flag: "LR", color: "#38bdf8" },
      geometry: { type: "Point", coordinates: [75.8, 11.4] },
    },
    {
      type: "Feature",
      properties: { mmsi: "636019482", name: "INDUS PRIDE", type: "Tanker", sog: 10.4, heading: 275, flag: "IN", color: "#f97316" },
      geometry: { type: "Point", coordinates: [64.2, 22.8] },
    },
    {
      type: "Feature",
      properties: { mmsi: "419001284", name: "COROMANDEL STAR", type: "Passenger", sog: 18.1, heading: 42, flag: "IN", color: "#34d399" },
      geometry: { type: "Point", coordinates: [80.5, 12.8] },
    },
    {
      type: "Feature",
      properties: { mmsi: "412891024", name: "BENGAL EXPRESS", type: "Cargo", sog: 13.9, heading: 60, flag: "BD", color: "#38bdf8" },
      geometry: { type: "Point", coordinates: [88.2, 19.4] },
    },
    {
      type: "Feature",
      properties: { mmsi: "538004921", name: "PACIFIC VOYAGER", type: "Tanker", sog: 12.5, heading: 120, flag: "MH", color: "#f97316" },
      geometry: { type: "Point", coordinates: [60.1, 13.2] },
    },
    {
      type: "Feature",
      properties: { mmsi: "413982001", name: "MALABAR FISHER 04", type: "Fishing", sog: 6.8, heading: 190, flag: "IN", color: "#fbbf24" },
      geometry: { type: "Point", coordinates: [76.0, 9.8] },
    },
    {
      type: "Feature",
      properties: { mmsi: "413982002", name: "ARABIAN SEA HAWK", type: "Fishing", sog: 5.4, heading: 210, flag: "IN", color: "#fbbf24" },
      geometry: { type: "Point", coordinates: [71.5, 20.2] },
    },
    {
      type: "Feature",
      properties: { mmsi: "636098231", name: "RED SEA MONARCH", type: "Tanker", sog: 14.8, heading: 305, flag: "LR", color: "#f97316" },
      geometry: { type: "Point", coordinates: [54.8, 12.1] },
    },
    {
      type: "Feature",
      properties: { mmsi: "563098210", name: "STRAITS CHIEF", type: "Cargo", sog: 16.2, heading: 95, flag: "SG", color: "#38bdf8" },
      geometry: { type: "Point", coordinates: [95.2, 5.8] },
    },
    {
      type: "Feature",
      properties: { mmsi: "419082341", name: "LAKSHADWEEP FERRY", type: "Passenger", sog: 16.5, heading: 250, flag: "IN", color: "#34d399" },
      geometry: { type: "Point", coordinates: [73.2, 10.5] },
    },
    {
      type: "Feature",
      properties: { mmsi: "374098124", name: "OCEAN MAJESTY", type: "Tanker", sog: 12.1, heading: 135, flag: "PA", color: "#f97316" },
      geometry: { type: "Point", coordinates: [83.4, 7.8] },
    },
    {
      type: "Feature",
      properties: { mmsi: "413009821", name: "GUJARAT NAVIGATOR", type: "Cargo", sog: 13.1, heading: 180, flag: "IN", color: "#38bdf8" },
      geometry: { type: "Point", coordinates: [69.8, 21.4] },
    },
    {
      type: "Feature",
      properties: { mmsi: "563098412", name: "CEYLON PHOENIX", type: "Tanker", sog: 11.2, heading: 80, flag: "LK", color: "#f97316" },
      geometry: { type: "Point", coordinates: [81.8, 6.2] },
    },
    {
      type: "Feature",
      properties: { mmsi: "636098712", name: "GULF PIONEER", type: "Cargo", sog: 15.0, heading: 290, flag: "LR", color: "#38bdf8" },
      geometry: { type: "Point", coordinates: [58.2, 23.5] },
    },
    {
      type: "Feature",
      properties: { mmsi: "413982009", name: "KONKAN QUEEN", type: "Passenger", sog: 17.4, heading: 165, flag: "IN", color: "#34d399" },
      geometry: { type: "Point", coordinates: [73.5, 16.2] },
    },
    {
      type: "Feature",
      properties: { mmsi: "413982015", name: "ANDAMAN HORIZON", type: "Passenger", sog: 15.8, heading: 75, flag: "IN", color: "#34d399" },
      geometry: { type: "Point", coordinates: [92.8, 11.7] },
    },
    {
      type: "Feature",
      properties: { mmsi: "538098214", name: "ATLANTIC FORTUNE", type: "Cargo", sog: 14.5, heading: 220, flag: "MH", color: "#38bdf8" },
      geometry: { type: "Point", coordinates: [77.2, 4.2] },
    },
    {
      type: "Feature",
      properties: { mmsi: "413982030", name: "VIZAG STAR", type: "Cargo", sog: 12.8, heading: 30, flag: "IN", color: "#38bdf8" },
      geometry: { type: "Point", coordinates: [84.1, 16.8] },
    },
  ],
};
