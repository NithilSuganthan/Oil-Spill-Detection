"use client";

import * as React from "react";
import { Palette, Globe, Mountain, Sun } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store/use-app-store";
import { BASEMAP_OPTIONS } from "@/components/map/map-config";
import type { MapStyle } from "@/lib/types";

/** Icons for each basemap mode */
const STYLE_ICONS: Record<MapStyle, React.ElementType> = {
  dark: Palette,
  satellite: Globe,
  ocean: Sun,
  terrain: Mountain,
};

/** Color swatches to visually represent each basemap */
const STYLE_SWATCHES: Record<MapStyle, string> = {
  dark: "bg-zinc-800",
  satellite: "bg-emerald-700",
  ocean: "bg-sky-600",
  terrain: "bg-stone-400",
};

export interface MapStyleSwitcherProps {
  /** Override the current map style (if not using the global store). */
  activeStyle?: MapStyle;
  /** Callback when the user selects a new style. */
  onStyleChange?: (style: MapStyle) => void;
  /** Position class override. Defaults to bottom-right. */
  className?: string;
}

/**
 * Compact floating basemap switcher.
 *
 * Renders a horizontal pill-shaped control with 4 style options.
 * Reads from / writes to the global Zustand store by default,
 * but can be driven by props for isolated map instances.
 */
export function MapStyleSwitcher({
  activeStyle: activeProp,
  onStyleChange,
  className,
}: MapStyleSwitcherProps) {
  const storeStyle = useAppStore((s) => s.mapStyle);
  const storeSetStyle = useAppStore((s) => s.setMapStyle);

  const activeStyle = activeProp ?? storeStyle;
  const handleChange = onStyleChange ?? storeSetStyle;

  const [expanded, setExpanded] = React.useState(false);

  return (
    <div
      className={cn(
        "absolute bottom-4 right-4 z-10 flex flex-col items-end gap-1.5",
        className
      )}
    >
      {/* Expanded panel */}
      {expanded && (
        <div className="glass-panel flex flex-col gap-0.5 p-1.5">
          <div className="mb-0.5 px-1.5 font-mono text-[8px] uppercase tracking-widest text-ink-faint">
            Basemap
          </div>
          {BASEMAP_OPTIONS.map((opt) => {
            const Icon = STYLE_ICONS[opt.mode];
            const isActive = activeStyle === opt.mode;
            return (
              <button
                key={opt.mode}
                type="button"
                title={opt.description}
                onClick={() => {
                  handleChange(opt.mode);
                  setExpanded(false);
                }}
                className={cn(
                  "flex items-center gap-2 rounded px-2 py-1 font-mono text-[9px] transition-colors",
                  isActive
                    ? "bg-signal-cyan/15 text-signal-cyan"
                    : "text-ink-dim hover:bg-base-800 hover:text-ink"
                )}
              >
                <Icon className="h-2.5 w-2.5" />
                <span className="w-12 text-left">{opt.label}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* Toggle button */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        title="Change basemap style"
        className={cn(
          "focus-ring flex h-7 w-7 items-center justify-center rounded border bg-base-900/90 backdrop-blur transition-colors",
          expanded
            ? "border-signal-cyan/50 text-signal-cyan"
            : "border-line/50 text-ink-dim hover:border-line hover:text-ink"
        )}
      >
        <Palette className="h-3 w-3" />
      </button>
    </div>
  );
}
