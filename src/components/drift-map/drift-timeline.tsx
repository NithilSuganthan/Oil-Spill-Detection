"use client";

import * as React from "react";
import {
  Play,
  Pause,
  RotateCcw,
  FastForward,
  Rewind,
  Clock,
  Calendar,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface TimelineProps {
  durationHours?: number;
  currentTime: number; // 0..1 fraction (0 = estimated source T-8h, 1 = detected slick T-0)
  isPlaying: boolean;
  speed: number;
  onSeek: (fraction: number) => void;
  onPlay: () => void;
  onPause: () => void;
  onSpeedChange: (speed: number) => void;
  onReset: () => void;
  onJumpToOffset?: (hoursAgo: number) => void;
}

const SPEEDS = [0.5, 1, 2, 4];
const JUMP_OFFSETS = [8, 6, 4, 2, 0]; // Hours ago

export function DriftTimeline({
  durationHours = 8,
  currentTime,
  isPlaying,
  speed,
  onSeek,
  onPlay,
  onPause,
  onSpeedChange,
  onReset,
  onJumpToOffset,
}: TimelineProps) {
  const trackRef = React.useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = React.useState(false);

  const handleTrackInteraction = React.useCallback(
    (clientX: number) => {
      if (!trackRef.current) return;
      const rect = trackRef.current.getBoundingClientRect();
      const fraction = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      onSeek(fraction);
    },
    [onSeek]
  );

  const handlePointerDown = (e: React.PointerEvent) => {
    setDragging(true);
    handleTrackInteraction(e.clientX);
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (dragging) handleTrackInteraction(e.clientX);
  };

  const handlePointerUp = () => setDragging(false);

  // Math: currentTime = 0 is T-8h, currentTime = 1 is T-0
  const hoursAgo = (1 - currentTime) * durationHours;
  
  // Format IST clock time (Anchor: T-0 = 18:31 IST)
  const getFormattedClock = (hAgo: number) => {
    const baseHour = 18;
    const baseMin = 31;
    let targetTotalMins = baseHour * 60 + baseMin - Math.round(hAgo * 60);
    if (targetTotalMins < 0) targetTotalMins += 24 * 60;
    const targetH = Math.floor(targetTotalMins / 60) % 24;
    const targetM = targetTotalMins % 60;
    return `${targetH.toString().padStart(2, "0")}:${targetM.toString().padStart(2, "0")} IST`;
  };

  return (
    <div className="panel border-line bg-base-900/95 px-4 py-3 shadow-2xl backdrop-blur-xl">
      {/* Top Controls Row */}
      <div className="mb-2.5 flex flex-wrap items-center justify-between gap-3">
        {/* Playback Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={onReset}
            className="focus-ring flex h-8 w-8 items-center justify-center rounded-md border border-line bg-base-800 text-ink-dim transition-colors hover:border-line-bright hover:text-ink"
            title="Reset to Estimated Source (T-8h)"
            aria-label="Reset to start"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>

          <button
            onClick={isPlaying ? onPause : onPlay}
            className={cn(
              "focus-ring flex h-8 px-3 items-center gap-1.5 rounded-md border font-mono text-[10px] font-bold tracking-wider transition-colors",
              isPlaying
                ? "border-cyan-400/60 bg-cyan-400/20 text-cyan-300 shadow-[0_0_12px_rgba(34,211,238,0.3)]"
                : "border-cyan-400/40 bg-cyan-400/10 text-cyan-400 hover:bg-cyan-400/20"
            )}
            aria-label={isPlaying ? "Pause" : "Play Hindcast"}
          >
            {isPlaying ? (
              <>
                <Pause className="h-3.5 w-3.5" /> PAUSE
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5 fill-current" /> PLAY DRIFT
              </>
            )}
          </button>

          {/* Speed Selector */}
          <div className="flex items-center gap-1 bg-base-950/60 border border-line/60 rounded-md p-0.5">
            {SPEEDS.map((s) => (
              <button
                key={s}
                onClick={() => onSpeedChange(s)}
                className={cn(
                  "focus-ring rounded px-2 py-0.5 font-mono text-[9px] font-bold transition-colors",
                  speed === s
                    ? "bg-cyan-400/20 text-cyan-400 border border-cyan-400/40"
                    : "text-ink-faint hover:text-ink-dim"
                )}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>

        {/* Quick Jump Timeline Markers */}
        <div className="flex items-center gap-1">
          <span className="font-mono text-[8px] uppercase tracking-widest text-ink-faint mr-1 hidden sm:inline">
            JUMP:
          </span>
          {JUMP_OFFSETS.map((h) => {
            const frac = 1 - h / durationHours;
            const isActive = Math.abs(currentTime - frac) < 0.05;
            return (
              <button
                key={h}
                onClick={() => onSeek(frac)}
                className={cn(
                  "font-mono text-[9px] px-2 py-1 rounded border transition-all",
                  isActive
                    ? "border-emerald-400 bg-emerald-400/20 text-emerald-300 font-bold shadow-[0_0_8px_rgba(52,211,153,0.4)]"
                    : "border-line/60 bg-base-950/40 text-ink-faint hover:border-line hover:text-ink"
                )}
              >
                {h === 0 ? "T-0" : `T-${h}h`}
              </button>
            );
          })}
        </div>

        {/* Live Offset & IST Timestamp */}
        <div className="flex items-center gap-2 font-mono text-[11px]">
          <div className="flex items-center gap-1.5 rounded-md bg-base-950/80 border border-line/80 px-2.5 py-1 text-cyan-400 font-bold">
            <Clock className="h-3 w-3 text-cyan-400" />
            <span>
              {hoursAgo === 0 ? "T+00:00" : `T-${hoursAgo.toFixed(1).padStart(4, "0")}h`}
            </span>
          </div>
          <div className="rounded-md bg-base-950/80 border border-line/80 px-2.5 py-1 text-ink font-semibold">
            {getFormattedClock(hoursAgo)}
          </div>
        </div>
      </div>

      {/* Scrubber Track */}
      <div
        ref={trackRef}
        className="relative h-7 cursor-pointer select-none py-1"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        role="slider"
        aria-label="Drift timeline scrubber"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(currentTime * 100)}
      >
        {/* Background track gradient (Estimated Source -> Slick) */}
        <div className="absolute left-0 right-0 top-1/2 h-2 -translate-y-1/2 rounded-full bg-gradient-to-r from-emerald-500/30 via-amber-500/30 to-red-500/30 border border-line/50" />

        {/* Progress fill */}
        <div
          className="absolute left-0 top-1/2 h-2 -translate-y-1/2 rounded-full bg-gradient-to-r from-emerald-400 via-yellow-400 to-red-500 shadow-[0_0_8px_rgba(52,211,153,0.5)]"
          style={{ width: `${currentTime * 100}%` }}
        />

        {/* Time Step Dots & Labels */}
        {JUMP_OFFSETS.map((h) => {
          const frac = 1 - h / durationHours;
          return (
            <div
              key={h}
              className="absolute top-1/2 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center pointer-events-none"
              style={{ left: `${frac * 100}%` }}
            >
              <div className="h-3 w-1 rounded-full bg-line-bright border border-base-950" />
              <span className="mt-1.5 font-mono text-[7px] font-semibold text-ink-faint">
                {h === 0 ? "DETECTED" : h === 8 ? "SOURCE" : `T-${h}h`}
              </span>
            </div>
          );
        })}

        {/* Moving Playhead */}
        <div
          className="absolute top-1/2 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center pointer-events-none transition-transform duration-75"
          style={{ left: `${currentTime * 100}%` }}
        >
          <div className="h-5 w-1.5 rounded-full bg-cyan-300 shadow-[0_0_12px_rgba(34,211,238,1)] border border-white" />
        </div>
      </div>
    </div>
  );
}
