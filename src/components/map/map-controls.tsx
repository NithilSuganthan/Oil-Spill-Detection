"use client";

import * as React from "react";
import {
  Plus,
  Minus,
  Maximize,
  Minimize,
  Layers,
  Crosshair,
  Locate,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface ControlButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
}

function ControlButton({ className, active, ...props }: ControlButtonProps) {
  return (
    <button
      type="button"
      {...props}
      className={cn(
        "focus-ring flex h-8 w-8 items-center justify-center rounded border border-line bg-base-900/90 text-ink-dim backdrop-blur transition-colors hover:border-line-bright hover:text-ink",
        active && "border-signal-cyan/50 text-signal-cyan",
        className
      )}
    />
  );
}

export interface MapControlsProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetView: () => void;
  onLocate: () => void;
  onToggleFullscreen: () => void;
  isFullscreen: boolean;
}

export function MapControls({
  onZoomIn,
  onZoomOut,
  onResetView,
  onLocate,
  onToggleFullscreen,
  isFullscreen,
}: MapControlsProps) {
  return (
    <div className="absolute right-3 top-3 z-10 flex flex-col gap-1.5">
      <ControlButton aria-label="Zoom in" onClick={onZoomIn}>
        <Plus className="h-4 w-4" />
      </ControlButton>
      <ControlButton aria-label="Zoom out" onClick={onZoomOut}>
        <Minus className="h-4 w-4" />
      </ControlButton>
      <div className="my-0.5 h-px bg-line" />
      <ControlButton aria-label="Reset view to India" onClick={onResetView}>
        <Crosshair className="h-4 w-4" />
      </ControlButton>
      <ControlButton aria-label="Center camera" onClick={onLocate}>
        <Locate className="h-4 w-4" />
      </ControlButton>
      <div className="my-0.5 h-px bg-line" />
      <ControlButton
        aria-label={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
        onClick={onToggleFullscreen}
      >
        {isFullscreen ? (
          <Minimize className="h-4 w-4" />
        ) : (
          <Maximize className="h-4 w-4" />
        )}
      </ControlButton>
    </div>
  );
}

export function LayerToggleButton({
  active,
  onClick,
}: {
  active: boolean;
  onClick: () => void;
}) {
  return (
    <div className="absolute right-3 top-[15.4rem] z-10">
      <ControlButton aria-label="Map layers" active={active} onClick={onClick}>
        <Layers className="h-4 w-4" />
      </ControlButton>
    </div>
  );
}
