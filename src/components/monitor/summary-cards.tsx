"use client";

import * as React from "react";
import { Activity, AlertTriangle, Radar, Satellite, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SummaryTotals {
  detections: number;
  highConfidence: number;
  totalAreaKm2: number;
  scenesProcessed: number;
}

function AnimatedNumber({ value, decimals = 0 }: { value: number; decimals?: number }) {
  const [displayValue, setDisplayValue] = React.useState(value);
  const [isAnimating, setIsAnimating] = React.useState(false);
  const prevRef = React.useRef(value);

  React.useEffect(() => {
    if (prevRef.current === value) return;
    const start = prevRef.current;
    const end = value;
    const duration = 600;
    const startTime = Date.now();

    setIsAnimating(true);

    function tick() {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayValue(start + (end - start) * eased);

      if (progress < 1) {
        requestAnimationFrame(tick);
      } else {
        setIsAnimating(false);
        prevRef.current = end;
      }
    }

    requestAnimationFrame(tick);
  }, [value]);

  return (
    <span className={cn("tabular-nums transition-colors", isAnimating && "text-signal-cyan")}>
      {decimals > 0 ? displayValue.toFixed(decimals) : Math.round(displayValue)}
    </span>
  );
}

function TrendIndicator({ trend }: { trend?: "up" | "down" | "neutral" }) {
  if (!trend || trend === "neutral") {
    return <Minus className="h-3 w-3 text-ink-faint" />;
  }
  if (trend === "up") {
    return <TrendingUp className="h-3 w-3 text-signal-green" />;
  }
  return <TrendingDown className="h-3 w-3 text-signal-red" />;
}

function StatCard({
  icon,
  value,
  decimals,
  label,
  accent,
  trend,
  trendLabel,
  onClick,
  subtitle,
}: {
  icon: React.ReactNode;
  value: number;
  decimals?: number;
  label: string;
  accent?: string;
  trend?: "up" | "down" | "neutral";
  trendLabel?: string;
  onClick?: () => void;
  subtitle?: string;
}) {
  const [flash, setFlash] = React.useState(false);
  const [hovered, setHovered] = React.useState(false);
  const prevRef = React.useRef(value);

  React.useEffect(() => {
    if (prevRef.current !== value) {
      setFlash(true);
      const t = setTimeout(() => setFlash(false), 800);
      prevRef.current = value;
      return () => clearTimeout(t);
    }
  }, [value]);

  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={cn(
        "panel group flex items-center gap-3 px-3.5 py-2.5 text-left transition-all duration-200",
        flash && "glow-pulse",
        hovered && "border-line-bright shadow-lg -translate-y-0.5",
        onClick && "cursor-pointer"
      )}
    >
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded border transition-colors",
          accent ?? "border-signal-cyan/30 bg-signal-cyan/10"
        )}
      >
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <p className="stat-value">
            <AnimatedNumber value={value} decimals={decimals} />
          </p>
          {trend && (
            <div className="flex items-center gap-0.5">
              <TrendIndicator trend={trend} />
              {trendLabel && (
                <span className="text-[9px] text-ink-faint">{trendLabel}</span>
              )}
            </div>
          )}
        </div>
        <p className="stat-label">{label}</p>
        {subtitle && (
          <p className="mt-0.5 text-[9px] text-ink-faint/70">{subtitle}</p>
        )}
      </div>
    </button>
  );
}

export function SummaryCards({ totals }: { totals: SummaryTotals }) {
  return (
    <div className="grid shrink-0 grid-cols-2 gap-2 xl:grid-cols-4">
      <StatCard
        icon={<Radar className="h-4 w-4 text-signal-cyan" />}
        value={totals.detections}
        label="DETECTIONS · 24H"
        subtitle="Potential slick detections"
      />
      <StatCard
        icon={<AlertTriangle className="h-4 w-4 text-signal-red" />}
        value={totals.highConfidence}
        label="HIGH CONFIDENCE"
        accent="border-signal-red/30 bg-signal-red/10"
        subtitle="≥80% model confidence"
      />
      <StatCard
        icon={<Activity className="h-4 w-4 text-signal-orange" />}
        value={totals.totalAreaKm2}
        decimals={1}
        label="TOTAL DETECTED AREA (km²)"
        accent="border-signal-orange/30 bg-signal-orange/10"
      />
      <StatCard
        icon={<Satellite className="h-4 w-4 text-signal-teal" />}
        value={totals.scenesProcessed}
        label="SCENES PROCESSED"
        accent="border-signal-teal/30 bg-signal-teal/10"
      />
    </div>
  );
}
