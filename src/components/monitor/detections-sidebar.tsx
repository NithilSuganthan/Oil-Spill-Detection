"use client";

import * as React from "react";
import { SlidersHorizontal, RotateCcw, Radio, Clock, MapPin, AlertTriangle } from "lucide-react";
import type { ConfidenceLevel, Incident, TimeRange } from "@/lib/types";
import { INDIAN_REGIONS } from "@/lib/types";
import { useAppStore } from "@/lib/store/use-app-store";
import { cn, formatArea, formatPercent, formatISTTimeShort } from "@/lib/utils";
import { SearchInput } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge, levelTone } from "@/components/ui/badge";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/states";

function StatusDot({ status }: { status: string }) {
  const color =
    status === "completed"
      ? "bg-signal-green"
      : status === "processing"
        ? "bg-signal-cyan animate-status-blink"
        : "bg-signal-amber";
  return (
    <span className="relative flex h-2 w-2">
      {(status === "processing") && (
        <span className="absolute inline-flex h-full w-full rounded-full opacity-75 animate-pulse-dot bg-signal-cyan" />
      )}
      <span className={cn("relative inline-flex h-2 w-2 rounded-full", color)} />
    </span>
  );
}

function StatusLabel({ status }: { status: string }) {
  const label =
    status === "completed"
      ? "COMPLETED"
      : status === "processing"
        ? "ANALYZING"
        : "UNDER REVIEW";
  const tone =
    status === "completed"
      ? "green"
      : status === "processing"
        ? "cyan"
        : "low";
  return <Badge tone={tone}>{label}</Badge>;
}

export function IncidentCard({
  incident,
  selected,
  onClick,
  isNew,
}: {
  incident: Incident;
  selected: boolean;
  onClick: () => void;
  isNew?: boolean;
}) {
  const [hovered, setHovered] = React.useState(false);

  return (
    <button
      onClick={onClick}
      aria-pressed={selected}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={cn(
        "focus-ring group w-full rounded-md border px-3 py-2.5 text-left transition-all duration-200",
        selected
          ? "border-signal-cyan/60 bg-signal-cyan/[0.07] shadow-panel glow-pulse"
          : "border-line bg-base-850/60 hover:border-line-bright hover:bg-base-800/80",
        isNew && "highlight-new"
      )}
    >
      {/* Row 1: ID + Level badge + status dot */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <StatusDot status={incident.status} />
          <span className="font-mono text-xs font-semibold tracking-wide text-ink">
            {incident.id}
          </span>
        </div>
        <Badge tone={levelTone[incident.level]}>{incident.level}</Badge>
      </div>

      {/* Row 2: Confidence bar */}
      <div className="mt-1.5 flex items-center gap-3">
        <div className="h-1 flex-1 overflow-hidden rounded-full bg-base-700">
          <div
            className="h-full rounded-full transition-all duration-500"
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

      {/* Row 3: Area + Time + Status (always visible) */}
      <div className="mt-1.5 flex items-center justify-between font-mono text-[11px] text-ink-faint">
        <span className="flex items-center gap-1">
          <MapPin className="h-2.5 w-2.5" />
          {formatArea(incident.areaKm2)} km²
        </span>
        <span className="flex items-center gap-1">
          <Clock className="h-2.5 w-2.5" />
          {formatISTTimeShort(incident.detectedAt)} IST
        </span>
      </div>

      {/* Expanded row on hover: region + location */}
      {hovered && (
        <div className="mt-2 border-t border-line/50 pt-2 animate-fade-in">
          <div className="flex items-center justify-between text-[10px] text-ink-faint">
            <span className="truncate max-w-[160px]">{incident.locationDescription}</span>
            <StatusLabel status={incident.status} />
          </div>
          <div className="mt-1 flex items-center justify-between text-[10px] text-ink-faint">
            <span>Region: {incident.region}</span>
            <span>{incident.satellite}</span>
          </div>
        </div>
      )}
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

  const incidentIdsRef = React.useRef<Set<string>>(new Set());
  const [newIds, setNewIds] = React.useState<Set<string>>(new Set());

  React.useEffect(() => {
    const currentIds = new Set(incidents.map((i) => i.id));
    const firstLoad = incidentIdsRef.current.size === 0;
    if (!firstLoad) {
      const added = incidents.filter((i) => !incidentIdsRef.current.has(i.id));
      if (added.length > 0) {
        setNewIds((prev) => {
          const next = new Set(prev);
          added.forEach((a) => next.add(a.id));
          return next;
        });
        // Clear after animation
        setTimeout(() => {
          setNewIds((prev) => {
            const next = new Set(prev);
            added.forEach((a) => next.delete(a.id));
            return next;
          });
        }, 2500);
      }
    }
    incidentIdsRef.current = currentIds;
  }, [incidents]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="panel-header shrink-0">
        <div className="flex items-center gap-2">
          <Radio className="h-3.5 w-3.5 text-signal-cyan" />
          <span className="panel-title">Model Detections</span>
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
                isNew={newIds.has(inc.id)}
              />
            </div>
          ))
        )}
      </div>
    </div>
  );
}
