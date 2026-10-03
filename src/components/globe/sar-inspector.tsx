"use client";

import * as React from "react";
import { Satellite, X, ExternalLink, Calendar, ShieldCheck, Layers } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SarSceneData {
  id: string;
  satellite: string;
  passTime: string;
  polarization: string;
  processingLevel: string;
  timeliness: string;
  productId: string;
}

interface SarInspectorProps {
  scene: SarSceneData;
  onClose: () => void;
  onViewSar?: () => void;
  className?: string;
}

export function SarInspector({
  scene,
  onClose,
  onViewSar,
  className,
}: SarInspectorProps) {
  return (
    <div
      className={cn(
        "glass-panel w-72 animate-slide-in-right overflow-hidden shadow-2xl border border-line/80 bg-base-950/95 backdrop-blur-xl rounded-lg font-mono",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-line/60 px-3.5 py-2.5 bg-base-900/80">
        <div className="flex items-center gap-2">
          <Satellite className="h-4 w-4 text-cyan-400" />
          <span className="text-[10px] font-extrabold uppercase tracking-wider text-cyan-300">
            SENTINEL-1 SAR ACQUISITION
          </span>
        </div>
        <button
          onClick={onClose}
          className="rounded p-1 text-ink-faint hover:text-ink hover:bg-base-800 transition-colors"
          aria-label="Close SAR inspector"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="p-3.5 space-y-3">
        {/* Main Satellite Title */}
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-extrabold text-ink">{scene.satellite}</div>
            <div className="text-[9px] text-ink-faint">Sentinel-1 Synthetic Aperture Radar</div>
          </div>
          <span className="rounded bg-cyan-500/20 border border-cyan-400/40 px-2 py-0.5 text-[9px] font-extrabold text-cyan-400">
            {scene.timeliness}
          </span>
        </div>

        {/* Technical Data Grid */}
        <div className="space-y-1.5 text-[9.5px]">
          <div className="flex items-center justify-between rounded bg-base-900/60 p-1.5 border border-line/40">
            <span className="text-ink-faint">Acquisition Time</span>
            <span className="font-bold text-ink">{scene.passTime} UTC</span>
          </div>

          <div className="flex items-center justify-between rounded bg-base-900/60 p-1.5 border border-line/40">
            <span className="text-ink-faint">Polarization</span>
            <span className="font-bold text-cyan-400">{scene.polarization}</span>
          </div>

          <div className="flex items-center justify-between rounded bg-base-900/60 p-1.5 border border-line/40">
            <span className="text-ink-faint">Processing Level</span>
            <span className="font-bold text-ink">{scene.processingLevel}</span>
          </div>

          <div className="flex items-center justify-between rounded bg-base-900/60 p-1.5 border border-line/40">
            <span className="text-ink-faint">Product ID</span>
            <span className="font-mono text-[8.5px] text-ink-dim truncate max-w-[120px]" title={scene.productId}>
              {scene.productId}
            </span>
          </div>
        </div>

        {/* View SAR Action Button */}
        <button
          onClick={onViewSar}
          className="flex w-full items-center justify-center gap-1.5 rounded-md bg-cyan-500 border border-cyan-400 px-3 py-2 text-[10px] font-extrabold text-base-950 shadow-[0_0_12px_rgba(34,211,238,0.4)] transition-all hover:bg-cyan-400 active:scale-95"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          VIEW SAR SCENE
        </button>
      </div>
    </div>
  );
}
