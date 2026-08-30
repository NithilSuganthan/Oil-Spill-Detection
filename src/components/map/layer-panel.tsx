"use client";

import * as React from "react";
import { MAP_LAYERS, useAppStore } from "@/lib/store/use-app-store";
import type { MapLayerId } from "@/lib/types";
import { cn } from "@/lib/utils";

const PHASE_LABELS: Record<number, string> = {
  1: "DETECTION",
  3: "AIS CORRELATION",
  4: "VESSEL ATTRIBUTION",
  5: "DRIFT / SOURCE ESTIMATE",
};

export function LayerPanel({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const activeLayers = useAppStore((s) => s.activeLayers);
  const toggleLayer = useAppStore((s) => s.toggleLayer);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open, onClose]);

  if (!open) return null;

  const phases = Array.from(new Set(MAP_LAYERS.map((l) => l.phase))).sort();

  return (
    <div
      ref={ref}
      className="panel absolute right-14 top-3 z-20 w-64 animate-fade-in p-1 shadow-panel"
    >
      <p className="px-2 py-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-ink-faint">
        Map Layers
      </p>
      {phases.map((phase) => (
        <div key={phase}>
          <p className="border-t border-line px-2 pb-1 pt-2 font-mono text-[9px] uppercase tracking-widest text-ink-faint">
            {PHASE_LABELS[phase] ?? `Phase ${phase}`}
          </p>
          {MAP_LAYERS.filter((l) => l.phase === phase).map((layer) => {
            const on = activeLayers[layer.id as MapLayerId];
            return (
              <button
                key={layer.id}
                disabled={!layer.available}
                onClick={() => toggleLayer(layer.id)}
                className={cn(
                  "flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-xs transition-colors",
                  layer.available
                    ? "text-ink-dim hover:bg-base-700/70"
                    : "cursor-not-allowed text-ink-faint/60",
                  on && layer.available && "text-signal-cyan"
                )}
              >
                <span>{layer.label}</span>
                {layer.available ? (
                  <span
                    className={cn(
                      "relative h-3.5 w-6 rounded-full border transition-colors",
                      on
                        ? "border-signal-cyan/60 bg-signal-cyan/30"
                        : "border-line-bright bg-base-700"
                    )}
                  >
                    <span
                      className={cn(
                        "absolute top-[1px] h-[10px] w-[10px] rounded-full transition-all",
                        on
                          ? "left-[12px] bg-signal-cyan"
                          : "left-[2px] bg-ink-faint"
                      )}
                    />
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );
}

const LEGEND_ITEMS = [
  { color: "#ef4444", label: "High confidence (≥80%)" },
  { color: "#ea580c", label: "Medium confidence (65–80%)" },
  { color: "#ca8a04", label: "Low confidence (<65%)" },
  { color: "#38bdf8", label: "Satellite scene coverage" },
];

export function MapLegend({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <div className="panel absolute bottom-8 left-3 z-10 animate-fade-in px-3 py-2 shadow-panel">
      <p className="mb-1.5 font-mono text-[9px] uppercase tracking-[0.2em] text-ink-faint">
        Legend
      </p>
      <ul className="space-y-1">
        {LEGEND_ITEMS.map((item) => (
          <li key={item.label} className="flex items-center gap-2">
            <span
              className="h-2.5 w-2.5 rounded-sm border border-black/30"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-[11px] text-ink-dim">{item.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
