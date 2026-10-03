"use client";

import * as React from "react";
import {
  ChevronDown,
  ChevronRight,
  Radio,
  Eye,
  EyeOff,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface LayerDef {
  id: string;
  label: string;
  category: string;
  defaultOn: boolean;
}

const LAYERS: LayerDef[] = [
  { id: "slick", label: "Potential Slick", category: "DETECTION", defaultOn: true },
  { id: "coverage", label: "Satellite Coverage", category: "DETECTION", defaultOn: false },
  { id: "wind", label: "Wind Flow", category: "ENVIRONMENT", defaultOn: true },
  { id: "current", label: "Ocean Current", category: "ENVIRONMENT", defaultOn: true },
  { id: "trajectory", label: "Backward Trajectory", category: "DRIFT", defaultOn: true },
  { id: "source", label: "Source Estimate", category: "DRIFT", defaultOn: true },
  { id: "uncertainty", label: "Uncertainty Region", category: "DRIFT", defaultOn: true },
  { id: "ais-vessels", label: "AIS Vessels", category: "AIS", defaultOn: false },
  { id: "ais-tracks", label: "AIS Tracks", category: "AIS", defaultOn: false },
  { id: "candidates", label: "Candidate Vessels", category: "AIS", defaultOn: false },
];

export function DriftLayerControl({
  activeLayers,
  onToggle,
}: {
  activeLayers: Record<string, boolean>;
  onToggle: (id: string) => void;
}) {
  const [collapsed, setCollapsed] = React.useState(false);
  const [openCategories, setOpenCategories] = React.useState<Record<string, boolean>>({
    DETECTION: true,
    ENVIRONMENT: true,
    DRIFT: true,
    AIS: false,
  });

  const categories = Array.from(new Set(LAYERS.map((l) => l.category)));

  const toggleCategory = (cat: string) => {
    setOpenCategories((prev) => ({ ...prev, [cat]: !prev[cat] }));
  };

  return (
    <div className="panel w-56 shadow-panel">
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="flex w-full items-center justify-between px-3 py-2"
      >
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-ink-dim">
          Layers
        </span>
        {collapsed ? (
          <ChevronRight className="h-3 w-3 text-ink-faint" />
        ) : (
          <ChevronDown className="h-3 w-3 text-ink-faint" />
        )}
      </button>

      {!collapsed && (
        <div className="border-t border-line px-2 py-1.5">
          {categories.map((cat) => (
            <div key={cat}>
              <button
                onClick={() => toggleCategory(cat)}
                className="flex w-full items-center justify-between py-1 text-left"
              >
                <span className="font-mono text-[8px] uppercase tracking-widest text-ink-faint">
                  {cat}
                </span>
                {openCategories[cat] ? (
                  <ChevronDown className="h-2.5 w-2.5 text-ink-faint" />
                ) : (
                  <ChevronRight className="h-2.5 w-2.5 text-ink-faint" />
                )}
              </button>
              {openCategories[cat] &&
                LAYERS.filter((l) => l.category === cat).map((layer) => {
                  const on = activeLayers[layer.id] ?? layer.defaultOn;
                  return (
                    <button
                      key={layer.id}
                      onClick={() => onToggle(layer.id)}
                      className="flex w-full items-center gap-2 rounded px-2 py-1 text-left transition-colors hover:bg-base-700/50"
                    >
                      {on ? (
                        <Eye className="h-3 w-3 shrink-0 text-signal-cyan" />
                      ) : (
                        <EyeOff className="h-3 w-3 shrink-0 text-ink-faint/50" />
                      )}
                      <span
                        className={cn(
                          "text-[10px]",
                          on ? "text-ink" : "text-ink-faint/60"
                        )}
                      >
                        {layer.label}
                      </span>
                    </button>
                  );
                })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
