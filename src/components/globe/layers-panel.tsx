"use client";

import * as React from "react";
import {
  Ship,
  Route,
  Radar,
  Droplets,
  Wind,
  Waves,
  Globe2,
  Tag,
  RotateCcw,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface LayerDef {
  id: string;
  label: string;
  icon: React.ElementType;
  color: string;
  available: boolean;
}

const DEFAULT_LAYERS: LayerDef[] = [
  { id: "ais", label: "AIS Vessels", icon: Ship, color: "#e2e8f0", available: true },
  { id: "ais-tracks", label: "Vessel Tracks", icon: Route, color: "#94a3b8", available: true },
  { id: "sar", label: "SAR Coverage", icon: Radar, color: "#38bdf8", available: true },
  { id: "oil", label: "Oil Detections", icon: Droplets, color: "#f87171", available: true },
  { id: "wind", label: "Wind (ECMWF)", icon: Wind, color: "#34d399", available: true },
  { id: "current", label: "Ocean Current (CMEMS)", icon: Waves, color: "#2dd4bf", available: true },
  { id: "coastline", label: "Coastline & Borders", icon: Globe2, color: "#64748b", available: true },
  { id: "labels", label: "Place Labels", icon: Tag, color: "#94a3b8", available: true },
];

interface LayersPanelProps {
  activeLayers: Record<string, boolean>;
  onToggle: (id: string) => void;
  onReset?: () => void;
  className?: string;
}

export function LayersPanel({
  activeLayers,
  onToggle,
  onReset,
  className,
}: LayersPanelProps) {
  return (
    <div className={cn("glass-panel p-3 w-56", className)}>
      <div className="flex items-center justify-between mb-2.5">
        <h3 className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-ink-dim">
          Layers
        </h3>
        {onReset && (
          <button
            onClick={onReset}
            className="flex items-center gap-1 font-mono text-[9px] text-signal-cyan hover:text-signal-cyan/80 transition-colors"
            aria-label="Reset layers"
          >
            <RotateCcw className="h-2.5 w-2.5" />
            Reset
          </button>
        )}
      </div>
      <div className="space-y-0.5">
        {DEFAULT_LAYERS.map((layer) => {
          const active = activeLayers[layer.id] !== false;
          const Icon = layer.icon;
          return (
            <button
              key={layer.id}
              onClick={() => onToggle(layer.id)}
              className={cn(
                "flex w-full items-center gap-2 rounded px-2 py-1.5 text-left transition-all",
                active
                  ? "bg-base-800/60"
                  : "bg-transparent hover:bg-base-800/30"
              )}
            >
              <div
                className={cn(
                  "flex h-4 w-4 items-center justify-center rounded border transition-all",
                  active
                    ? "border-signal-cyan/60 bg-signal-cyan/15"
                    : "border-line bg-transparent"
                )}
              >
                {active && (
                  <svg className="h-2.5 w-2.5 text-signal-cyan" viewBox="0 0 12 12" fill="none">
                    <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </div>
              <Icon
                className="h-3 w-3 shrink-0"
                style={{ color: active ? layer.color : "#5c718f" }}
              />
              <span
                className={cn(
                  "font-mono text-[10px] tracking-wide",
                  active ? "text-ink" : "text-ink-faint"
                )}
              >
                {layer.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
