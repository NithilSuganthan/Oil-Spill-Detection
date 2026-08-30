"use client";

import { Activity, AlertTriangle, Radar, Satellite } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SummaryTotals {
  detections: number;
  highConfidence: number;
  totalAreaKm2: number;
  scenesProcessed: number;
}

function StatCard({
  icon,
  value,
  label,
  accent,
}: {
  icon: React.ReactNode;
  value: string;
  label: string;
  accent?: string;
}) {
  return (
    <div className="panel flex items-center gap-3 px-3.5 py-2.5">
      <div className={cn("flex h-8 w-8 items-center justify-center rounded border", accent ?? "border-signal-cyan/30 bg-signal-cyan/10")}>
        {icon}
      </div>
      <div>
        <p className="stat-value">{value}</p>
        <p className="stat-label">{label}</p>
      </div>
    </div>
  );
}

export function SummaryCards({ totals }: { totals: SummaryTotals }) {
  return (
    <div className="grid shrink-0 grid-cols-2 gap-2 xl:grid-cols-4">
      <StatCard
        icon={<Radar className="h-4 w-4 text-signal-cyan" />}
        value={String(totals.detections)}
        label="Detections · 24h"
      />
      <StatCard
        icon={<AlertTriangle className="h-4 w-4 text-signal-red" />}
        value={String(totals.highConfidence)}
        label="High Confidence"
        accent="border-signal-red/30 bg-signal-red/10"
      />
      <StatCard
        icon={<Activity className="h-4 w-4 text-signal-orange" />}
        value={`${totals.totalAreaKm2.toFixed(1)} km²`}
        label="Total Detected Area"
        accent="border-signal-orange/30 bg-signal-orange/10"
      />
      <StatCard
        icon={<Satellite className="h-4 w-4 text-signal-teal" />}
        value={String(totals.scenesProcessed)}
        label="Scenes Processed"
        accent="border-signal-teal/30 bg-signal-teal/10"
      />
    </div>
  );
}
