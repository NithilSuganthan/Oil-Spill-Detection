"use client";

import * as React from "react";
import { SlidersHorizontal, RotateCcw, Radio } from "lucide-react";
import type { ConfidenceLevel, Incident, TimeRange } from "@/lib/types";
import { INDIAN_REGIONS } from "@/lib/types";
import { useAppStore } from "@/lib/store/use-app-store";
import { cn, formatArea, formatPercent, formatISTTimeShort } from "@/lib/utils";
import { SearchInput } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge, levelTone } from "@/components/ui/badge";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/states";

export function IncidentCard({
  incident,
  selected,
  onClick,
}: {
  incident: Incident;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={selected}
      className={cn(
        "focus-ring group w-full rounded-md border px-3 py-2.5 text-left transition-all",
        selected
          ? "border-signal-cyan/60 bg-signal-cyan/[0.07] shadow-panel"
          : "border-line bg-base-850/60 hover:border-line-bright hover:bg-base-800/80"
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-xs font-semibold tracking-wide text-ink">
          {incident.id}
        </span>
        <Badge tone={levelTone[incident.level]}>{incident.level}</Badge>
      </div>
      <div className="mt-1.5 flex items-center gap-3">
        <div className="h-1 flex-1 overflow-hidden rounded-full bg-base-700">
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${incident.confidence * 100}%`,
              backgroundColor:
                incident.level === "HIGH"
                  ? "#f87171"
                  : incident.level === "MEDIUM"
                    ? "#fb923c"
                    : "#facc15",
            }}
          />
        </div>
        <span className="font-mono text-[11px] tabular-nums text-ink-dim">
          {formatPercent(incident.confidence)}
        </span>
      </div>
      <div className="mt-1 flex items-center justify-between font-mono text-[11px] text-ink-faint">
        <span>{formatArea(incident.areaKm2)} km²</span>
        <span>{formatISTTimeShort(incident.detectedAt)} IST</span>
      </div>
    </button>
  );
}

function FiltersPanel() {
  const filters = useAppStore((s) => s.filters);
  const toggleLevel = useAppStore((s) => s.toggleLevel);
  const setTimeRange = useAppStore((s) => s.setTimeRange);
  const setRegion = useAppStore((s) => s.setRegion);
  const resetFilters = useAppStore((s) => s.resetFilters);

  const levels: { id: ConfidenceLevel; label: string; color: string }[] = [
    { id: "HIGH", label: "High", color: "#f87171" },
    { id: "MEDIUM", label: "Medium", color: "#fb923c" },
    { id: "LOW", label: "Low", color: "#facc15" },
  ];

  return (
    <div className="space-y-3 border-b border-line px-3 py-3 animate-fade-in">
      <div>
        <p className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-ink-faint">
          Confidence
        </p>
        <div className="flex gap-1.5">
          {levels.map((l) => {
            const on = filters.levels.includes(l.id);
            return (
              <button
                key={l.id}
                aria-pressed={on}
                onClick={() => toggleLevel(l.id)}
                className={cn(
                  "focus-ring flex-1 rounded border px-2 py-1 font-mono text-[10px] uppercase tracking-wider transition-colors",
                  on
                    ? "text-base-950"
                    : "border-line text-ink-dim hover:border-line-bright"
                )}
                style={on ? { borderColor: l.color, backgroundColor: l.color } : undefined}
              >
                {l.label}
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <p className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-ink-faint">
          Time Range
        </p>
        <Select
          ariaLabel="Time range"
          value={filters.timeRange}
          onValueChange={(v) => setTimeRange(v as TimeRange)}
          options={[
            { value: "6h", label: "Last 6 Hours" },
            { value: "24h", label: "Last 24 Hours" },
            { value: "7d", label: "Last 7 Days" },
          ]}
        />
      </div>

      <div>
        <p className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-ink-faint">
          Region
        </p>
        <Select
          ariaLabel="Region"
          value={filters.region}
          onValueChange={setRegion}
          options={INDIAN_REGIONS.map((r) => ({ value: r, label: r }))}
        />
      </div>

      <button
        onClick={resetFilters}
        className="focus-ring flex items-center gap-1.5 rounded px-1 py-0.5 font-mono text-[10px] uppercase tracking-wider text-ink-faint hover:text-ink"
      >
        <RotateCcw className="h-3 w-3" /> Reset Filters
      </button>
    </div>
  );
}

export interface DetectionsSidebarProps {
  incidents: Incident[];
  isLoading: boolean;
  isError: boolean;
  refetch: () => void;
}

export function DetectionsSidebar({
  incidents,
  isLoading,
  isError,
  refetch,
}: DetectionsSidebarProps) {
  const search = useAppStore((s) => s.filters.search);
  const setSearch = useAppStore((s) => s.setSearch);
  const [filtersOpen, setFiltersOpen] = React.useState(false);
  const selectedIncidentId = useAppStore((s) => s.selectedIncidentId);
  const selectIncident = useAppStore((s) => s.selectIncident);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="panel-header shrink-0">
        <div className="flex items-center gap-2">
          <Radio className="h-3.5 w-3.5 text-signal-cyan" />
          <span className="panel-title">Detections</span>
        </div>
        <span className="font-mono text-[11px] tabular-nums text-signal-teal">
          {isLoading ? "…" : incidents.length} active
        </span>
      </div>

      <div className="flex shrink-0 items-center gap-2 border-b border-line px-3 py-2">
        <SearchInput
          value={search}
          onValueChange={setSearch}
          placeholder="Search incidents…"
          aria-label="Search incidents"
        />
        <button
          aria-label="Toggle filters"
          aria-expanded={filtersOpen}
          onClick={() => setFiltersOpen((o) => !o)}
          className={cn(
            "focus-ring flex h-8 w-8 shrink-0 items-center justify-center rounded-md border transition-colors",
            filtersOpen
              ? "border-signal-cyan/50 bg-signal-cyan/10 text-signal-cyan"
              : "border-line text-ink-dim hover:border-line-bright hover:text-ink"
          )}
        >
          <SlidersHorizontal className="h-4 w-4" />
        </button>
      </div>

      {filtersOpen && <FiltersPanel />}

      <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto p-2">
        {isError ? (
          <ErrorState message="Failed to load detection feed." onRetry={refetch} />
        ) : isLoading ? (
          <LoadingBlock label="Querying detections…" />
        ) : incidents.length === 0 ? (
          <EmptyState
            title="No detections match"
            description="Adjust search terms or widen the confidence / time-range filters."
          />
        ) : (
          incidents.map((inc, i) => (
            <div key={inc.id} style={{ animationDelay: `${i * 40}ms` }} className="animate-fade-up">
              <IncidentCard
                incident={inc}
                selected={inc.id === selectedIncidentId}
                onClick={() => selectIncident(inc)}
              />
            </div>
          ))
        )}
      </div>
    </div>
  );
}
