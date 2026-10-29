"use client";

import * as React from "react";
import { Ship, Navigation, Compass, Clock, Radio, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { VesselData } from "@/components/globe/vessel-inspector";

interface VesselListPanelProps {
  vesselGeoJSON: GeoJSON.FeatureCollection | null;
  aisSource: "realtime" | "demo";
  isConnected: boolean;
  selectedVesselMmsi: string | null | undefined;
  onVesselSelect: (vessel: VesselData) => void;
  className?: string;
}

interface VesselRow {
  mmsi: string;
  name: string;
  vesselType: string;
  lat: number;
  lon: number;
  sog: number | null;
  heading: number | null;
  lastUpdate: string | null;
  color: string;
  messageCount: number;
}

function parseVessels(geojson: GeoJSON.FeatureCollection | null): VesselRow[] {
  if (!geojson?.features) return [];
  return geojson.features
    .map((f) => {
      const props = f.properties as Record<string, unknown> | undefined;
      const coords = (f.geometry as GeoJSON.Point)?.coordinates;
      if (!props || !coords) return null;
      return {
        mmsi: String(props.mmsi ?? ""),
        name: String(props.name ?? `MMSI-${props.mmsi}`),
        vesselType: String(props.type ?? "unknown"),
        lat: coords[1],
        lon: coords[0],
        sog: props.sog != null ? Number(props.sog) : null,
        heading: props.heading != null ? Number(props.heading) : null,
        lastUpdate: props.last_update as string | null,
        color: String(props.color ?? "#94a3b8"),
        messageCount: Number(props.message_count ?? 0),
      };
    })
    .filter(Boolean) as VesselRow[];
}

function formatTimeAgo(iso: string | null): string {
  if (!iso) return "UNAVAILABLE";
  try {
    const then = new Date(iso).getTime();
    const now = Date.now();
    const diff = Math.floor((now - then) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  } catch {
    return "UNAVAILABLE";
  }
}

function formatTimeUTC(iso: string | null): string {
  if (!iso) return "UNAVAILABLE";
  try {
    const d = new Date(iso);
    return d.toISOString().slice(11, 19) + " UTC";
  } catch {
    return "UNAVAILABLE";
  }
}

export function VesselListPanel({
  vesselGeoJSON,
  aisSource,
  isConnected,
  selectedVesselMmsi,
  onVesselSelect,
  className,
}: VesselListPanelProps) {
  const vessels = React.useMemo(() => parseVessels(vesselGeoJSON), [vesselGeoJSON]);
  const [expanded, setExpanded] = React.useState(true);
  const listRef = React.useRef<HTMLDivElement>(null);

  const isRealtime = aisSource === "realtime";
  const statusLabel = isRealtime
    ? isConnected
      ? "LIVE"
      : "UNAVAILABLE"
    : "DEMO / SIMULATED";
  const statusColor = isRealtime
    ? isConnected
      ? "text-emerald-400"
      : "text-red-400"
    : "text-amber-400";

  // Scroll selected vessel into view
  React.useEffect(() => {
    if (!selectedVesselMmsi || !listRef.current) return;
    const el = listRef.current.querySelector(`[data-mmsi="${selectedVesselMmsi}"]`);
    if (el) el.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedVesselMmsi]);

  return (
    <div
      className={cn(
        "glass-panel w-56 overflow-hidden font-mono",
        className,
      )}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded((e) => !e)}
        className="flex w-full items-center justify-between border-b border-line/50 px-3 py-2 hover:bg-base-800/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Ship className="h-3.5 w-3.5 text-ink-dim" />
          <span className="text-[10px] font-bold uppercase tracking-wider text-ink-dim">
            AIS Vessels
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn("text-[10px] font-bold", statusColor)}>
            {vessels.length} {statusLabel}
          </span>
          {isRealtime && (
            <Radio
              className={cn(
                "h-2.5 w-2.5",
                isConnected ? "text-emerald-400 animate-pulse" : "text-red-400",
              )}
            />
          )}
        </div>
      </button>

      {/* Vessel list */}
      {expanded && (
        <div ref={listRef} className="max-h-64 overflow-y-auto scrollbar-thin">
          {vessels.length === 0 ? (
            <div className="px-3 py-4 text-center">
              <span className="text-[10px] text-ink-faint">
                {isRealtime && !isConnected
                  ? "Waiting for AISStream..."
                  : "No vessels"}
              </span>
            </div>
          ) : (
            vessels.map((v) => {
              const isSelected = v.mmsi === selectedVesselMmsi;
              return (
                <button
                  key={v.mmsi}
                  data-mmsi={v.mmsi}
                  onClick={() =>
                    onVesselSelect({
                      mmsi: v.mmsi,
                      name: v.name,
                      vesselType: v.vesselType,
                      lat: v.lat,
                      lon: v.lon,
                      sog: v.sog ?? undefined,
                      heading: v.heading ?? undefined,
                      lastUpdate: v.lastUpdate ?? undefined,
                    })
                  }
                  className={cn(
                    "w-full border-b border-line/20 px-3 py-2 text-left transition-colors",
                    isSelected
                      ? "bg-cyan-500/10 border-l-2 border-l-cyan-400"
                      : "hover:bg-base-800/40 border-l-2 border-l-transparent",
                  )}
                >
                  {/* Vessel name + type dot */}
                  <div className="flex items-center gap-1.5">
                    <span
                      className="inline-block h-2 w-2 rounded-full flex-shrink-0"
                      style={{ backgroundColor: v.color }}
                    />
                    <span className="text-[11px] font-bold text-ink truncate">
                      {v.name}
                    </span>
                    {isRealtime && (
                      <span className="ml-auto flex-shrink-0 text-[8px] text-emerald-400/70">
                        LIVE
                      </span>
                    )}
                  </div>

                  {/* MMSI */}
                  <div className="mt-0.5 pl-3.5 text-[9px] text-ink-faint">
                    MMSI {v.mmsi}
                  </div>

                  {/* Speed + Heading */}
                  <div className="mt-0.5 flex items-center gap-2 pl-3.5 text-[9px] text-ink-dim">
                    {v.sog != null ? (
                      <span className="flex items-center gap-0.5">
                        <Navigation className="h-2 w-2" />
                        {v.sog.toFixed(1)} kn
                      </span>
                    ) : (
                      <span className="text-ink-faint">SOG —</span>
                    )}
                    {v.heading != null ? (
                      <span className="flex items-center gap-0.5">
                        <Compass className="h-2 w-2" />
                        {Math.round(v.heading)}°
                      </span>
                    ) : (
                      <span className="text-ink-faint">HDG —</span>
                    )}
                  </div>

                  {/* Last update */}
                  <div className="mt-0.5 flex items-center gap-1 pl-3.5 text-[8px] text-ink-faint">
                    <Clock className="h-1.5 w-1.5" />
                    {isRealtime
                      ? `Updated ${formatTimeAgo(v.lastUpdate)}`
                      : "Simulated"}
                  </div>
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
