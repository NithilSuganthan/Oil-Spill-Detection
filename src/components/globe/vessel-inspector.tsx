"use client";

import * as React from "react";
import { Ship, X, Navigation, Compass, Clock, Route } from "lucide-react";
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

export function VesselInspector({
  vessel,
  onClose,
  onViewTrack,
  className,
}: VesselInspectorProps) {
  const vesselColor = getVesselColor(vessel.vesselType);

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
        {/* Vessel identity */}
        <div>
          <div className="font-mono text-[10px] text-ink-faint">MMSI</div>
          <div className="font-mono text-sm font-bold text-ink">{vessel.mmsi}</div>
        </div>

        {vessel.name && (
          <div>
            <div className="font-mono text-[10px] text-ink-faint">Name</div>
            <div className="font-mono text-xs font-medium text-ink">{vessel.name}</div>
          </div>
        )}

        {vessel.vesselType && (
          <div className="flex items-center gap-1.5">
            <span className={cn("font-mono text-[10px] font-bold", vesselColor)}>
              {vessel.vesselType}
            </span>
          </div>
        )}

        {/* Telemetry */}
        <div className="grid grid-cols-2 gap-2 pt-1 border-t border-line/30">
          {vessel.sog != null && (
            <TelemetryItem
              icon={Navigation}
              label="SOG"
              value={`${vessel.sog.toFixed(1)} kn`}
            />
          )}
          {vessel.heading != null && (
            <TelemetryItem
              icon={Compass}
              label="HDG"
              value={`${Math.round(vessel.heading)}°`}
            />
          )}
        </div>

        {vessel.lastUpdate && (
          <div className="flex items-center gap-1.5 pt-1 border-t border-line/30">
            <Clock className="h-2.5 w-2.5 text-ink-faint" />
            <span className="font-mono text-[8px] text-ink-faint">
              UPDATED {vessel.lastUpdate}
            </span>
          </div>
        )}

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

function TelemetryItem({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
}) {
  return (
    <div>
      <div className="flex items-center gap-1">
        <Icon className="h-2.5 w-2.5 text-ink-faint" />
        <span className="font-mono text-[8px] text-ink-faint">{label}</span>
      </div>
      <div className="font-mono text-[11px] font-bold text-ink tabular-nums">{value}</div>
    </div>
  );
}
