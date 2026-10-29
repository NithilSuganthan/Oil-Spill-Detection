"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  X,
  ArrowRight,
  ExternalLink,
  Ship,
  Droplets,
  Calendar,
  MapPin,
  Radar,
  TrendingUp,
  Clock,
  CheckCircle2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatISTTime, formatArea } from "@/lib/utils";
import type { Incident } from "@/lib/types";

interface OilInspectorProps {
  incident: Incident;
  onClose: () => void;
  className?: string;
}

const NEARBY_VESSELS = [
  { name: "MV OCEAN SPIRIT", type: "Cargo", distance: "8.4 km", icon: Ship },
  { name: "SEA HARMONY", type: "Tanker", distance: "12.1 km", icon: Ship },
  { name: "GLOBAL TRADER", type: "Cargo", distance: "18.7 km", icon: Ship },
];

export function OilInspector({ incident, onClose, className }: OilInspectorProps) {
  const router = useRouter();
  const confidence = Math.round(incident.confidence * 100);
  const [sarMode, setSarMode] = React.useState<"VV" | "VH" | "Detection">("Detection");

  return (
    <div
      className={cn(
        "glass-panel w-80 animate-slide-in-right overflow-hidden shadow-2xl border border-line/80 bg-base-950/95 backdrop-blur-xl rounded-lg",
        className
      )}
    >
      {/* Top Header */}
      <div className="flex items-center justify-between border-b border-line/60 px-3.5 py-2.5 bg-base-900/80">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] font-extrabold uppercase tracking-wider text-red-400">
            SELECTED: <span className="text-ink">OIL DETECTION</span>
          </span>
        </div>
        <button
          onClick={onClose}
          className="rounded p-1 text-ink-faint hover:text-ink hover:bg-base-800 transition-colors"
          aria-label="Close inspector"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* SAR Image Thumbnail Viewer with Mode Tabs */}
      <div className="relative border-b border-line/60 bg-base-950 p-2">
        <div className="relative h-36 w-full overflow-hidden rounded border border-line/40 bg-black">
          {/* Simulated SAR Speckle Background Canvas */}
          <div
            className="absolute inset-0 opacity-80"
            style={{
              backgroundImage: `radial-gradient(circle at 45% 55%, rgba(239, 68, 68, 0.4) 0%, rgba(239, 68, 68, 0.15) 25%, transparent 60%), radial-gradient(circle, #1e293b 1px, transparent 1px)`,
              backgroundSize: "100% 100%, 4px 4px",
            }}
          />

          {/* Oil Slick Polygon Visual Representation */}
          <svg className="absolute inset-0 h-full w-full" viewBox="0 0 200 120">
            <path
              d="M 60,45 Q 85,30 120,40 Q 155,50 140,75 Q 115,95 80,85 Q 45,75 60,45 Z"
              fill="rgba(239, 68, 68, 0.45)"
              stroke="#ef4444"
              strokeWidth="2"
              strokeDasharray={sarMode === "Detection" ? "none" : "3,3"}
            />
            <path
              d="M 85,52 Q 105,42 125,55 Q 115,72 90,70 Z"
              fill="rgba(239, 68, 68, 0.7)"
            />
          </svg>

          {/* SAR Overlay Tag */}
          <div className="absolute top-2 left-2 rounded bg-base-950/80 px-1.5 py-0.5 font-mono text-[8px] font-bold text-cyan-400 border border-cyan-400/30">
            Sentinel-1 SAR ({sarMode})
          </div>
        </div>

        {/* Mode Selector Tabs */}
        <div className="mt-1.5 flex gap-1">
          {(["VV", "VH", "Detection"] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setSarMode(mode)}
              className={cn(
                "flex-1 py-1 font-mono text-[8.5px] font-bold rounded transition-all",
                sarMode === mode
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-400/40"
                  : "bg-base-900/60 text-ink-faint hover:text-ink"
              )}
            >
              SAR ({mode})
            </button>
          ))}
        </div>
      </div>

      {/* Incident Details Container */}
      <div className="p-3.5 space-y-3">
        {/* ID Title & High Level Badge */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <Droplets className="h-4 w-4 text-red-400 shrink-0" />
            <div>
              <div className="font-mono text-sm font-extrabold text-ink tracking-wider">
                {incident.id}
              </div>
              <div className="font-mono text-[9px] text-ink-faint">
                Potential Oil Spill
              </div>
            </div>
          </div>
          <span className="rounded bg-red-500/20 border border-red-500/40 px-2 py-0.5 font-mono text-[9px] font-extrabold text-red-400">
            HIGH
          </span>
        </div>

        {/* Key Attributes Grid */}
        <div className="space-y-1.5 font-mono text-[9.5px]">
          <div className="flex items-center justify-between rounded bg-base-900/60 p-1.5 border border-line/40">
            <span className="text-ink-faint">Detected</span>
            <span className="font-bold text-ink">{formatISTTime(incident.detectedAt)} UTC</span>
          </div>

          <div className="flex items-center justify-between rounded bg-base-900/60 p-1.5 border border-line/40">
            <span className="text-ink-faint">Area</span>
            <span className="font-bold text-red-400">{formatArea(incident.areaKm2)} km²</span>
          </div>

          <div className="flex items-center justify-between rounded bg-base-900/60 p-1.5 border border-line/40">
            <span className="text-ink-faint">Model Confidence</span>
            <span className="font-bold text-cyan-400">{confidence}%</span>
          </div>

          <div className="flex items-center justify-between rounded bg-base-900/60 p-1.5 border border-line/40">
            <span className="text-ink-faint">Estimated Age</span>
            <span className="font-bold text-amber-400">~6 – 12 hours</span>
          </div>

          <div className="flex items-center justify-between rounded bg-base-900/60 p-1.5 border border-line/40">
            <span className="text-ink-faint">Source</span>
            <span className="font-bold text-ink">{incident.satellite} (S1A)</span>
          </div>

          <div className="flex items-center justify-between rounded bg-base-900/60 p-1.5 border border-line/40">
            <span className="text-ink-faint">Processing</span>
            <span className="font-bold text-emerald-400 flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3" /> Completed
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="space-y-1.5 pt-1">
          <button
            onClick={() => router.push(`/investigate/${incident.id}`)}
            className="flex w-full items-center justify-center gap-2 rounded-md bg-cyan-500 border border-cyan-400 px-3 py-2 font-mono text-[11px] font-extrabold text-base-950 shadow-[0_0_14px_rgba(34,211,238,0.4)] transition-all hover:bg-cyan-400 active:scale-95"
          >
            Investigate Incident
            <ArrowRight className="h-3.5 w-3.5" />
          </button>

          <button
            onClick={() => router.push(`/live-analysis?incident=${incident.id}`)}
            className="flex w-full items-center justify-center gap-1.5 rounded-md border border-line/80 bg-base-900 px-3 py-1.5 font-mono text-[10px] font-bold text-ink-dim hover:text-ink hover:border-cyan-400/50 transition-all"
          >
            <ExternalLink className="h-3 w-3" /> View SAR Scene
          </button>
        </div>

        {/* Nearby Vessels Candidate Section */}
        <div className="pt-2 border-t border-line/60 space-y-1.5">
          <div className="flex items-center justify-between font-mono text-[8.5px] font-bold text-ink-faint uppercase">
            <span>NEARBY VESSELS (5)</span>
            <span className="text-cyan-400 hover:underline cursor-pointer">View All</span>
          </div>

          <div className="space-y-1">
            {NEARBY_VESSELS.map((vessel) => (
              <div
                key={vessel.name}
                className="flex items-center justify-between rounded bg-base-900/50 px-2 py-1 border border-line/30 font-mono text-[8.5px]"
              >
                <div className="flex items-center gap-1.5">
                  <Ship className="h-3 w-3 text-red-400 shrink-0" />
                  <div>
                    <span className="font-bold text-ink">{vessel.name}</span>
                    <span className="text-ink-faint ml-1 font-normal">({vessel.type})</span>
                  </div>
                </div>
                <span className="font-bold text-amber-400">{vessel.distance}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
