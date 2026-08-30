"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpDown, Database, FileSearch } from "lucide-react";
import * as React from "react";
import type { ConfidenceLevel, TimeRange } from "@/lib/types";
import { INDIAN_REGIONS } from "@/lib/types";
import { getAllIncidents, getIncidents } from "@/lib/api/client";
import { useAppStore } from "@/lib/store/use-app-store";
import {
  cn,
  formatArea,
  formatPercent,
  formatISTDate,
  formatISTTime,
} from "@/lib/utils";
import { PageShell } from "@/components/layout/page-shell";
import { SearchInput } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge, levelTone } from "@/components/ui/badge";
import { FilterChips } from "@/components/common/filter-chips";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/states";

type SortKey = "time" | "confidence" | "area";

export default function IncidentsPage() {
  const router = useRouter();
  const filters = useAppStore((s) => s.filters);
  const setSearch = useAppStore((s) => s.setSearch);
  const toggleLevel = useAppStore((s) => s.toggleLevel);
  const setTimeRange = useAppStore((s) => s.setTimeRange);
  const setRegion = useAppStore((s) => s.setRegion);

  const [sortKey, setSortKey] = React.useState<SortKey>("time");
  const [sortDesc, setSortDesc] = React.useState(true);

  const { data: allIncidents } = useQuery({
    queryKey: ["all-incidents"],
    queryFn: getAllIncidents,
  });

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["incidents", filters],
    queryFn: () => getIncidents(filters),
  });

  const sorted = React.useMemo(() => {
    const list = [...(data ?? [])];
    list.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "time")
        cmp = new Date(a.detectedAt).getTime() - new Date(b.detectedAt).getTime();
      if (sortKey === "confidence") cmp = a.confidence - b.confidence;
      if (sortKey === "area") cmp = a.areaKm2 - b.areaKm2;
      return sortDesc ? -cmp : cmp;
    });
    return list;
  }, [data, sortKey, sortDesc]);

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDesc((d) => !d);
    } else {
      setSortKey(key);
      setSortDesc(true);
    }
  };

  return (
    <PageShell>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-mono text-lg font-bold tracking-[0.15em] text-ink">
            INCIDENT REGISTER
          </h1>
          <p className="mt-0.5 text-xs text-ink-faint">
            All recorded spill detections across the Indian focus region.
          </p>
        </div>
        <span className="flex items-center gap-1.5 font-mono text-[11px] text-signal-teal">
          <Database className="h-3.5 w-3.5" />
          {allIncidents?.length ?? "—"} total records
        </span>
      </div>

      {/* filter bar */}
      <div className="panel mb-4 grid grid-cols-1 items-end gap-3 p-3 md:grid-cols-[1fr_auto_auto_auto]">
        <div>
          <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-ink-faint">
            Search
          </label>
          <SearchInput
            value={filters.search}
            onValueChange={setSearch}
            placeholder="Incident ID or location…"
            aria-label="Search incidents"
          />
        </div>
        <div>
          <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-ink-faint">
            Confidence
          </label>
          <FilterChips levels={filters.levels} onToggleLevel={toggleLevel} />
        </div>
        <div>
          <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-ink-faint">
            Date Range
          </label>
          <Select
            ariaLabel="Time range"
            className="w-40"
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
          <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-ink-faint">
            Region
          </label>
          <Select
            ariaLabel="Region"
            className="w-48"
            value={filters.region}
            onValueChange={setRegion}
            options={INDIAN_REGIONS.map((r) => ({ value: r, label: r }))}
          />
        </div>
      </div>

      {/* table */}
      <div className="panel overflow-hidden">
        {isLoading ? (
          <LoadingBlock label="Querying incident register…" />
        ) : isError ? (
          <ErrorState message="Failed to load incidents." onRetry={() => void refetch()} />
        ) : sorted.length === 0 ? (
          <EmptyState
            icon={<FileSearch className="h-8 w-8" />}
            title="No matching incidents"
            description="No detections satisfy the current filters. Try widening the time range or clearing confidence chips."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-xs">
              <thead>
                <tr className="border-b border-line font-mono text-[10px] uppercase tracking-widest text-ink-faint">
                  {(
                    [
                      ["incident", "Incident"],
                      ["time", "Time"],
                      ["region", "Region"],
                      ["area", "Area"],
                      ["confidence", "Confidence"],
                      ["status", "Status"],
                    ] as [SortKey | "region" | "status" | "incident" | "time" | "area" | "confidence", string][]
                  ).map(([key, label]) => (
                    <th key={key} className="px-4 py-2.5 font-medium">
                      {["incident", "time", "area", "confidence"].includes(key) ? (
                        <button
                          onClick={() => toggleSort(key as SortKey)}
                          className={cn(
                            "focus-ring inline-flex items-center gap-1 rounded uppercase tracking-widest hover:text-ink",
                            sortKey === key && "text-signal-cyan"
                          )}
                        >
                          {label}
                          <ArrowUpDown className="h-3 w-3 opacity-60" />
                        </button>
                      ) : (
                        label
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map((inc) => (
                  <tr
                    key={inc.id}
                    tabIndex={0}
                    role="link"
                    onClick={() => router.push(`/incident/${inc.id}`)}
                    onKeyDown={(e) => e.key === "Enter" && router.push(`/incident/${inc.id}`)}
                    className="cursor-pointer border-b border-line/60 transition-colors last:border-0 hover:bg-base-800/70"
                  >
                    <td className="px-4 py-2.5 font-mono font-semibold text-ink">{inc.id}</td>
                    <td className="whitespace-nowrap px-4 py-2.5 font-mono tabular-nums text-ink-dim">
                      {formatISTDate(inc.detectedAt)} · {formatISTTime(inc.detectedAt)}
                    </td>
                    <td className="max-w-[220px] truncate px-4 py-2.5 text-ink-dim">
                      {inc.locationDescription}
                    </td>
                    <td className="px-4 py-2.5 font-mono tabular-nums text-ink-dim">
                      {formatArea(inc.areaKm2)} km²
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <span className="font-mono tabular-nums text-ink">
                          {formatPercent(inc.confidence)}
                        </span>
                        <Badge tone={levelTone[inc.level]}>{inc.level}</Badge>
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      <Badge tone={inc.status === "completed" ? "green" : inc.status === "review" ? "medium" : "cyan"}>
                        {inc.status}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </PageShell>
  );
}
