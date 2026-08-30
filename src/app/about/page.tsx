import { Brain, Radar, Satellite, Waves } from "lucide-react";
import { PageShell } from "@/components/layout/page-shell";

const PILLARS = [
  {
    icon: Satellite,
    title: "Sentinel-1 SAR Imagery",
    desc: "Synthetic Aperture Radar from the Copernicus Sentinel-1 mission provides all-weather, day-and-night observation of Indian waters — the ideal sensor for oil slick visibility.",
  },
  {
    icon: Brain,
    title: "AI-Based Segmentation",
    desc: "A deep-learning segmentation model (OilSpillNet) classifies dark formations in SAR scenes and separates genuine slicks from natural look-alikes such as low-wind zones and algal blooms.",
  },
  {
    icon: Radar,
    title: "Geospatial Analysis",
    desc: "Model predictions are converted into precise geospatial polygons with confidence scoring, area estimation and coastal region attribution.",
  },
  {
    icon: Waves,
    title: "Near-Real-Time Monitoring",
    desc: "A continuous pipeline — satellite downlink → processing engine → detection database → operations console — designed around maritime situational awareness.",
  },
];

const PHASES = [
  ["Phase 1", "Satellite Oil-Spill Detection", true],
  ["Phase 2", "Ocean Drift / Source Backtracking", false],
  ["Phase 3", "AIS Vessel Tracking", false],
  ["Phase 4", "Spill ↔ Vessel Correlation", false],
  ["Phase 5", "Evidence & Attribution", false],
] as const;

export default function AboutPage() {
  return (
    <PageShell maxWidth="max-w-4xl">
      <div className="mb-8 border-l-2 border-signal-cyan/50 pl-4">
        <h1 className="font-mono text-lg font-bold tracking-[0.15em] text-ink">ABOUT SAGAR WATCH</h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-dim">
          SAGAR WATCH is a satellite-based maritime intelligence platform designed to detect
          and monitor potential oil spills in Indian waters. It fuses Sentinel-1 Synthetic
          Aperture Radar imagery with AI-based segmentation and geospatial analysis to give
          responders a near-real-time picture of marine pollution events along India&apos;s
          coastline and exclusive economic zone.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {PILLARS.map((p) => (
          <section key={p.title} className="panel p-4">
            <p.icon className="mb-2 h-4 w-4 text-signal-cyan" />
            <h2 className="font-mono text-[11px] font-semibold uppercase tracking-wider text-ink-dim">
              {p.title}
            </h2>
            <p className="mt-1.5 text-xs leading-relaxed text-ink-faint">{p.desc}</p>
          </section>
        ))}
      </div>

      <section className="panel mt-6 p-4">
        <h2 className="panel-title mb-3">Roadmap</h2>
        <ol className="space-y-2">
          {PHASES.map(([phase, name, current]) => (
            <li key={phase} className="flex items-center gap-3 text-xs">
              <span
                className={`w-16 shrink-0 rounded border px-1.5 py-0.5 text-center font-mono text-[10px] tracking-wider ${
                  current
                    ? "border-signal-cyan/40 bg-signal-cyan/10 text-signal-cyan"
                    : "border-line text-ink-faint"
                }`}
              >
                {phase}
              </span>
              <span className={current ? "text-ink" : "text-ink-faint"}>{name}</span>
              {current && (
                <span className="rounded bg-signal-green/10 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-signal-green">
                  Current Prototype
                </span>
              )}
            </li>
          ))}
        </ol>
      </section>

      <section className="mt-6 rounded-md border border-signal-amber/25 bg-signal-amber/[0.04] p-4">
        <h2 className="font-mono text-[11px] font-semibold uppercase tracking-wider text-signal-amber">
          Prototype Notice
        </h2>
        <p className="mt-1.5 text-xs leading-relaxed text-ink-dim">
          This application is an interactive prototype built for demonstration purposes.
          All detections, satellite scenes, analytics and system statuses shown across the
          interface are mock data generated locally in the browser — they do not represent
          real satellite acquisitions, real pollution events, or live system telemetry.
          The architecture is prepared so a production backend (SAR ingestion, ML inference,
          drift modelling and AIS integration) can replace the mock layer without changes to
          the user interface.
        </p>
      </section>

      <p className="mt-6 text-center font-mono text-[10px] uppercase tracking-[0.25em] text-ink-faint/70">
        Focus Region · Republic of India 🇮🇳 · Arabian Sea · Bay of Bengal · Indian Ocean
      </p>
    </PageShell>
  );
}
