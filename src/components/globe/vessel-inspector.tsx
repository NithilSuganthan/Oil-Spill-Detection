"use client";

import * as React from "react";
import { Ship, X, Navigation, Compass, Clock, Route, MapPin } from "lucide-react";
import { cn } from "@/lib/utils";

export interface VesselData {
  mmsi: string;
  name?: string;
  vesselType?: string;
  lat: number;
  lon: number;
  sog?: number;
  cog?: number;
  heading?: number;
  flag?: string;
  navigationStatus?: string;
  lastUpdate?: string;
}

interface VesselInspectorProps {
  vessel: VesselData;
  aisSource?: "realtime" | "demo";
  onClose: () => void;
  onViewTrack?: () => void;
  className?: string;
}

const VESSEL_TYPE_COLORS: Record<string, string> = {
  Tanker: "text-signal-orange",
  Cargo: "text-signal-cyan",
  Passenger: "text-signal-green",
  Fishing: "text-signal-amber",
  Tug: "text-ink-dim",
  default: "text-ink",
};

function getVesselColor(type?: string) {
  if (!type) return VESSEL_TYPE_COLORS.default;
  for (const [key, color] of Object.entries(VESSEL_TYPE_COLORS)) {
    if (type.toLowerCase().includes(key.toLowerCase())) return color;
  }
  return VESSEL_TYPE_COLORS.default;
}

function formatCoord(val: number, isLat: boolean): string {
  const dir = isLat ? (val >= 0 ? "N" : "S") : val >= 0 ? "E" : "W";
  return `${Math.abs(val).toFixed(4)}° ${dir}`;
}

function formatTimeUTC(iso: string | undefined): string {
  if (!iso) return "UNAVAILABLE";
  try {
    const d = new Date(iso);
    return d.toISOString().slice(0, 19).replace("T", " ") + " UTC";
  } catch {
    return "UNAVAILABLE";
  }
}

export function VesselInspector({
  vessel,
  aisSource = "demo",
  onClose,
  onViewTrack,
  className,
}: VesselInspectorProps) {
  const vesselColor = getVesselColor(vessel.vesselType);
  const isRealtime = aisSource === "realtime";

  return (
    <div
      className={cn(
        "glass-panel w-60 animate-slide-in-right overflow-hidden",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-line/50 px-3 py-2">
        <div className="flex items-center gap-2">
          <Ship className={cn("h-3.5 w-3.5", vesselColor)} />
          <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-ink-dim">
            Vessel
          </span>
        </div>
        <button
          onClick={onClose}
          className="rounded p-0.5 text-ink-faint hover:text-ink transition-colors"
          aria-label="Close vessel inspector"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="px-3 py-3 space-y-2.5">
        {/* Vessel name */}
        <div>
          <div className="font-mono text-[8px] text-ink-faint uppercase">Vessel</div>
          <div className="font-mono text-sm font-bold text-ink">
            {vessel.name || "UNAVAILABLE"}
          </div>
        </div>

        {/* MMSI */}
        <div>
          <div className="font-mono text-[8px] text-ink-faint uppercase">MMSI</div>
          <div className="font-mono text-xs font-medium text-ink">{vessel.mmsi}</div>
        </div>

        {/* Position */}
        <div className="pt-1 border-t border-line/30">
          <div className="font-mono text-[8px] text-ink-faint uppercase">Position</div>
          <div className="font-mono text-[11px] text-ink tabular-nums">
            {formatCoord(vessel.lat, true)}, {formatCoord(vessel.lon, false)}
          </div>
        </div>

        {/* Speed + Heading */}
        <div className="grid grid-cols-2 gap-2 pt-1 border-t border-line/30">
          <div>
            <div className="flex items-center gap-1">
              <Navigation className="h-2.5 w-2.5 text-ink-faint" />
              <span className="font-mono text-[8px] text-ink-faint">SPEED</span>
            </div>
            <div className="font-mono text-[11px] font-bold text-ink tabular-nums">
              {vessel.sog != null ? `${vessel.sog.toFixed(1)} kn` : "UNAVAILABLE"}
            </div>
          </div>
          <div>
            <div className="flex items-center gap-1">
              <Compass className="h-2.5 w-2.5 text-ink-faint" />
              <span className="font-mono text-[8px] text-ink-faint">HEADING</span>
            </div>
            <div className="font-mono text-[11px] font-bold text-ink tabular-nums">
              {vessel.heading != null ? `${Math.round(vessel.heading)}°` : "UNAVAILABLE"}
            </div>
          </div>
        </div>

        {/* Last Update */}
        <div className="flex items-center gap-1.5 pt-1 border-t border-line/30">
          <Clock className="h-2.5 w-2.5 text-ink-faint" />
          <div>
            <div className="font-mono text-[8px] text-ink-faint uppercase">Last AIS Update</div>
            <div className="font-mono text-[10px] text-ink tabular-nums">
              {isRealtime ? formatTimeUTC(vessel.lastUpdate) : "Simulated"}
            </div>
          </div>
        </div>

        {/* Source */}
        <div className="flex items-center gap-1.5 pt-1 border-t border-line/30">
          <MapPin className="h-2.5 w-2.5 text-ink-faint" />
          <div>
            <div className="font-mono text-[8px] text-ink-faint uppercase">Source</div>
            <div className={cn(
              "font-mono text-[10px] font-bold",
              isRealtime ? "text-emerald-400" : "text-amber-400",
            )}>
              {isRealtime ? "AISSTREAM • REAL-TIME" : "DEMO • SIMULATED"}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-1.5 pt-1">
          {onViewTrack && (
            <button
              onClick={onViewTrack}
              className="flex flex-1 items-center justify-center gap-1 rounded border border-line/50 bg-base-800/50 px-2 py-1.5 font-mono text-[9px] text-ink-dim transition-colors hover:border-line hover:text-ink"
            >
              <Route className="h-2.5 w-2.5" />
              VIEW TRACK
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
