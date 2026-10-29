"use client";

import * as React from "react";
import { Play, Pause, Calendar, Radio } from "lucide-react";
import { cn } from "@/lib/utils";

interface TimelineBarProps {
  isPlaying: boolean;
  speed: number;
  progress: number;
  onPlay: () => void;
  onPause: () => void;
  onSpeedChange: (speed: number) => void;
  onProgressChange: (progress: number) => void;
  className?: string;
}

export function getCurrentISTProgress() {
  const now = new Date();
  const istStr = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
    hour12: false,
  }).format(now);
  const parts = istStr.split(":").map(Number);
  const h = parts[0] || 0;
  const m = parts[1] || 0;
  const s = parts[2] || 0;
  return Math.min(1, Math.max(0, (h * 3600 + m * 60 + s) / 86400));
}

export function TimelineBar({
  isPlaying,
  speed,
  progress,
  onPlay,
  onPause,
  onSpeedChange,
  onProgressChange,
  className,
}: TimelineBarProps) {
  const speeds = [0.5, 1, 2, 4];
  const nextSpeed = () => {
    const idx = speeds.indexOf(speed);
    onSpeedChange(speeds[(idx + 1) % speeds.length]);
  };

  const handleGoLive = () => {
    onProgressChange(getCurrentISTProgress());
  };

  const hours = ["00:00", "06:00", "12:00", "18:00", "NOW (23:01 IST)", "24:00"];

  return (
    <div className={cn("rounded-lg border border-line/60 bg-base-950/95 backdrop-blur-xl flex items-center gap-3 px-3 py-1.5 shadow-2xl", className)}>
      {/* Play / Speed Controls */}
      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={isPlaying ? onPause : onPlay}
          className="flex h-7 w-7 items-center justify-center rounded-full border border-cyan-400/50 bg-cyan-500/20 text-cyan-300 transition-all hover:bg-cyan-500/30 hover:scale-105 active:scale-95 shadow-[0_0_10px_rgba(34,211,238,0.3)]"
          aria-label={isPlaying ? "Pause" : "Play"}
        >
          {isPlaying ? (
            <Pause className="h-3.5 w-3.5" />
          ) : (
            <Play className="h-3.5 w-3.5 ml-0.5 fill-current text-cyan-400" />
          )}
        </button>

        <button
          onClick={nextSpeed}
          className="flex h-6 items-center gap-0.5 rounded border border-line/60 bg-base-900 px-2 font-mono text-[9px] font-bold text-ink-dim transition-all hover:border-cyan-400/50 hover:text-cyan-300"
        >
          {speed}x ▾
        </button>
      </div>

      {/* Main Timeline Scrubber Track */}
      <div className="flex-1 relative">
        <div className="flex justify-between mb-1">
          {hours.map((h) => (
            <span
              key={h}
              className={cn(
                "font-mono text-[8px] tabular-nums font-bold",
                h.includes("NOW") ? "text-cyan-300 font-extrabold" : "text-ink-faint/60"
              )}
            >
              {h}
            </span>
          ))}
        </div>

        <div
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            onProgressChange(frac);
          }}
          className="relative h-2 rounded-full bg-base-900 border border-line/40 cursor-pointer overflow-visible"
        >
          <div
            className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-cyan-500/60 to-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.6)]"
            style={{ width: `${progress * 100}%` }}
          />

          {/* Scrubber Knob */}
          <div
            className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 z-20 flex flex-col items-center"
            style={{ left: `${progress * 100}%` }}
          >
            <div className="h-4 w-1.5 bg-cyan-400 rounded-full border border-white shadow-[0_0_8px_#22d3ee]" />
          </div>
        </div>
      </div>

      {/* Right Date Picker & Live Toggle */}
      <div className="flex items-center gap-2 shrink-0 font-mono">
        <div className="flex items-center gap-1.5 rounded border border-line/60 bg-base-900 px-2 py-1 text-[9px] text-ink-dim">
          <Calendar className="h-3 w-3 text-cyan-400" />
          <span>04 Sep 2026</span>
        </div>

        <button
          onClick={handleGoLive}
          className="flex items-center gap-1.5 rounded border border-emerald-500/40 bg-emerald-500/10 px-2 py-1 text-[9px] font-extrabold text-emerald-400 hover:bg-emerald-500/20 transition-all cursor-pointer"
        >
          <Radio className="h-3 w-3 text-emerald-400 animate-pulse" />
          <span>Live</span>
        </button>
      </div>
    </div>
  );
}
