"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useQuery } from "@tanstack/react-query";
import { getAnalytics } from "@/lib/api/client";
import { PageShell } from "@/components/layout/page-shell";
import { SummaryCards } from "@/components/monitor/summary-cards";
import { LoadingBlock } from "@/components/ui/states";

const AXIS = { stroke: "#5c718f", fontSize: 10, fontFamily: "var(--font-jetbrains)" };
const GRID = "#16233b";
const TOOLTIP_STYLE = {
  backgroundColor: "#0a1120",
  border: "1px solid #27405f",
  borderRadius: "6px",
  fontSize: "11px",
  fontFamily: "var(--font-inter)",
  color: "#e6edf5",
};

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="panel p-4">
      <h2 className="font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-ink-dim">
        {title}
      </h2>
      {subtitle && <p className="mb-3 mt-0.5 text-[11px] text-ink-faint">{subtitle}</p>}
      <div className={subtitle ? "" : "mt-3"}>{children}</div>
    </section>
  );
}

export default function AnalyticsPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["analytics"],
    queryFn: getAnalytics,
  });

  if (isLoading) {
    return (
      <PageShell>
        <LoadingBlock label="Aggregating analytics…" />
      </PageShell>
    );
  }
  if (isError || !data) {
    return (
      <PageShell>
        <p className="py-16 text-center font-mono text-xs uppercase tracking-widest text-signal-red">
          Failed to load analytics
        </p>
      </PageShell>
    );
  }

  const REGION_COLORS = [
    "#38bdf8", "#2dd4bf", "#34d399", "#fbbf24",
    "#fb923c", "#f87171", "#a5b4fc", "#94a3b8",
  ];

  return (
    <PageShell>
      <div className="mb-5">
        <h1 className="font-mono text-lg font-bold tracking-[0.15em] text-ink">
          OPERATIONS ANALYTICS
        </h1>
        <p className="mt-0.5 text-xs text-ink-faint">
          Detection trends across the Indian focus region · last 7 days.
        </p>
      </div>

      <SummaryCards totals={data.totals} />

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard
          title="Detections Over Time"
          subtitle="Daily count with high-confidence subset"
        >
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={data.daily} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
              <defs>
                <linearGradient id="gDet" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#38bdf8" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gHigh" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f87171" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#f87171" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} />
              <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ stroke: "#27405f" }} />
              <Area type="monotone" dataKey="detections" name="Detections" stroke="#38bdf8" fill="url(#gDet)" strokeWidth={1.6} />
              <Area type="monotone" dataKey="highConfidence" name="High confidence" stroke="#f87171" fill="url(#gHigh)" strokeWidth={1.6} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Total Detected Area" subtitle="km² of slick area per day">
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={data.daily} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
              <defs>
                <linearGradient id="gArea" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#fb923c" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#fb923c" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} />
              <YAxis tick={AXIS} tickLine={false} axisLine={false} unit="" />
              <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ stroke: "#27405f" }} formatter={(v) => [`${v} km²`, "Detected area"]} />
              <Area type="monotone" dataKey="areaKm2" name="Area (km²)" stroke="#fb923c" fill="url(#gArea)" strokeWidth={1.6} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Detections by Region" subtitle="Indian coastal regions & seas">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data.byRegion} layout="vertical" margin={{ top: 0, right: 16, left: 40, bottom: 0 }}>
              <CartesianGrid stroke={GRID} strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} allowDecimals={false} />
              <YAxis type="category" dataKey="region" tick={{ ...AXIS, fontSize: 9 }} tickLine={false} axisLine={false} width={110} />
              <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "rgba(56,189,248,0.06)" }} />
              <Bar dataKey="detections" name="Detections" radius={[0, 3, 3, 0]} barSize={12}>
                {data.byRegion.map((_, i) => (
                  <Cell key={i} fill={REGION_COLORS[i % REGION_COLORS.length]} fillOpacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <div className="space-y-4">
          <ChartCard title="Confidence Distribution" subtitle="Model score histogram · last 7 days">
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={data.confidenceBuckets} margin={{ top: 4, right: 8, left: -22, bottom: 0 }}>
                <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="bucket" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} />
                <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "rgba(251,146,60,0.06)" }} />
                <Bar dataKey="count" name="Detections" radius={[3, 3, 0, 0]} barSize={26}>
                  {[["#facc15"], ["#facc15"], ["#fb923c"], ["#fb923c"], ["#f87171"]].map((c, i) => (
                    <Cell key={i} fill={c[0]} fillOpacity={0.85} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Scenes Processed" subtitle="Sentinel-1 acquisitions through the pipeline per day">
            <ResponsiveContainer width="100%" height={92}>
              <BarChart data={data.daily} margin={{ top: 4, right: 8, left: -22, bottom: 0 }}>
                <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} />
                <YAxis tick={AXIS} tickLine={false} axisLine={false} domain={[0, "auto"]} />
                <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "rgba(45,212,191,0.06)" }} />
                <Bar dataKey="scenesProcessed" name="Scenes" fill="#2dd4bf" fillOpacity={0.8} radius={[3, 3, 0, 0]} barSize={18} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      </div>

      <p className="mt-4 border-t border-line pt-3 font-mono text-[10px] uppercase tracking-widest text-ink-faint/70">
        Prototype note · all figures derive from mock data for interface demonstration only
      </p>
    </PageShell>
  );
}
