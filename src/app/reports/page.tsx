"use client";

import { useState, useEffect } from "react";
import { FileText, ShieldCheck, AlertTriangle, CheckCircle, Clock, FileDown } from "lucide-react";
import { PageShell } from "@/components/layout/page-shell";
import { generateReport, getReport, getAllIncidents, getIncident, getDrift, getAttribution } from "@/lib/api/client";
import { generateInvestigationPDF } from "@/lib/pdf/generate-report-pdf";
import type { Incident, StoredReport } from "@/lib/types";

export default function ReportsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<string>("");
  const [report, setReport] = useState<StoredReport | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAllIncidents().then(setIncidents).catch(console.error);
  }, []);

  const handleGenerate = async () => {
    if (!selectedIncident) return;
    setGenerating(true);
    setError(null);
    try {
      const result = await generateReport(selectedIncident);
      setReport(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate report");
    } finally {
      setGenerating(false);
    }
  };

  const handleCheckExisting = async () => {
    if (!selectedIncident) return;
    try {
      const existing = await getReport(selectedIncident);
      if (existing) setReport(existing);
    } catch {
      // Ignore 404
    }
  };

  return (
    <PageShell maxWidth="max-w-4xl">
      <h1 className="font-mono text-lg font-bold tracking-[0.15em] text-ink">
        INCIDENT REPORTING &amp; EVIDENCE PACKAGES
      </h1>
      <p className="mt-1 text-xs text-ink-faint">
        Structured, shareable documentation of detected spill incidents.
      </p>

      {/* Report Generation Panel */}
      <div className="panel mt-8 p-6">
        <h2 className="font-mono text-xs font-medium uppercase tracking-wider text-ink-dim">
          Generate Investigation Report
        </h2>
        <p className="mt-1 text-xs text-ink-faint">
          Generate an AI-assisted investigation report from structured system evidence.
        </p>

        <div className="mt-4 flex flex-col gap-4 sm:flex-row">
          <select
            value={selectedIncident}
            onChange={(e) => {
              setSelectedIncident(e.target.value);
              setReport(null);
              setError(null);
            }}
            className="flex-1 rounded border border-line-bright/60 bg-base-900 px-3 py-2 text-xs text-ink"
          >
            <option value="">Select incident...</option>
            {incidents.map((inc) => (
              <option key={inc.id} value={inc.id}>
                {inc.id} — {inc.locationDescription}
              </option>
            ))}
          </select>

          <button
            onClick={handleGenerate}
            disabled={!selectedIncident || generating}
            className="rounded border border-signal-cyan/60 bg-signal-cyan/10 px-4 py-2 font-mono text-[11px] uppercase tracking-wider text-signal-cyan hover:bg-signal-cyan/20 disabled:opacity-50"
          >
            {generating ? "GENERATING..." : "GENERATE INVESTIGATION REPORT"}
          </button>

          <button
            onClick={async () => {
              if (!report || !selectedIncident) return;
              const [inc, drift, attribution] = await Promise.all([
                getIncident(selectedIncident),
                getDrift(selectedIncident),
                getAttribution(selectedIncident),
              ]);
              generateInvestigationPDF({
                incident: inc,
                drift,
                attribution,
                report,
              });
            }}
            disabled={!report}
            className="rounded border border-amber-400/50 bg-amber-400/10 px-4 py-2 font-mono text-[11px] uppercase tracking-wider text-amber-400 hover:bg-amber-400/20 disabled:opacity-40 flex items-center gap-1.5"
          >
            <FileDown className="h-3.5 w-3.5" />
            DOWNLOAD PDF
          </button>
        </div>

        {error && (
          <div className="mt-4 flex items-center gap-2 rounded border border-signal-red/40 bg-signal-red/10 p-3 text-xs text-signal-red">
            <AlertTriangle className="h-4 w-4" />
            {error}
          </div>
        )}
      </div>

      {/* Report Display */}
      {report && (
        <div className="mt-6 space-y-4">
          {/* Report Header */}
          <div className="panel p-6">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="font-mono text-sm font-medium text-ink">
                  {report.report.title}
                </h2>
                <p className="mt-1 text-xs text-ink-faint">
                  Generated: {new Date(report.generatedAt).toLocaleString()} | Provider: {report.provider} | Model: {report.model}
                </p>
              </div>
              <span className="rounded bg-signal-cyan/10 px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-signal-cyan">
                AI-GENERATED SUMMARY
              </span>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-ink-dim">
              {report.report.executiveSummary}
            </p>
          </div>

          {/* Detection Assessment */}
          <div className="panel p-4">
            <h3 className="font-mono text-[11px] font-medium uppercase tracking-wider text-ink-dim">
              Detection Assessment
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-ink-faint">
              {report.report.detectionAssessment}
            </p>
          </div>

          {/* Environmental Assessment */}
          <div className="panel p-4">
            <h3 className="font-mono text-[11px] font-medium uppercase tracking-wider text-ink-dim">
              Environmental Assessment
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-ink-faint">
              {report.report.environmentAssessment}
            </p>
          </div>

          {/* Drift Assessment */}
          <div className="panel p-4">
            <h3 className="font-mono text-[11px] font-medium uppercase tracking-wider text-ink-dim">
              Drift / Source Assessment
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-ink-faint">
              {report.report.driftAssessment}
            </p>
          </div>

          {/* AIS Assessment */}
          <div className="panel p-4">
            <h3 className="font-mono text-[11px] font-medium uppercase tracking-wider text-ink-dim">
              AIS Assessment
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-ink-faint">
              {report.report.aisAssessment}
            </p>
          </div>

          {/* Candidate Assessments */}
          {report.report.candidateAssessments.length > 0 && (
            <div className="panel p-4">
              <h3 className="font-mono text-[11px] font-medium uppercase tracking-wider text-ink-dim">
                Potential Source Vessel Assessment
              </h3>
              <div className="mt-3 space-y-3">
                {report.report.candidateAssessments.map((c) => (
                  <div key={c.mmsi} className="rounded border border-line-bright/40 p-3">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-medium text-ink">
                        {c.vesselName} (MMSI: {c.mmsi})
                      </span>
                      <span className="font-mono text-xs text-signal-cyan">
                        Score: {c.attributionScore.toFixed(3)}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-ink-faint">{c.explanation}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Uncertainty */}
          <div className="panel p-4">
            <h3 className="font-mono text-[11px] font-medium uppercase tracking-wider text-ink-dim">
              Uncertainty
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-ink-faint">
              {report.report.uncertainty}
            </p>
          </div>

          {/* Recommended Actions */}
          <div className="panel p-4">
            <h3 className="font-mono text-[11px] font-medium uppercase tracking-wider text-ink-dim">
              Recommended Actions
            </h3>
            <ul className="mt-2 space-y-1">
              {report.report.recommendedActions.map((action, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-ink-faint">
                  <CheckCircle className="mt-0.5 h-3 w-3 shrink-0 text-signal-cyan" />
                  {action}
                </li>
              ))}
            </ul>
          </div>

          {/* Limitations */}
          <div className="panel p-4">
            <h3 className="font-mono text-[11px] font-medium uppercase tracking-wider text-ink-dim">
              Limitations
            </h3>
            <ul className="mt-2 space-y-1">
              {report.report.limitations.map((limitation, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-ink-faint">
                  <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-signal-yellow" />
                  {limitation}
                </li>
              ))}
            </ul>
          </div>

          {/* Human Review Required */}
          {report.report.humanReviewRequired && (
            <div className="rounded border border-signal-yellow/40 bg-signal-yellow/10 p-4 text-center">
              <p className="font-mono text-xs uppercase tracking-wider text-signal-yellow">
                Human Review Required
              </p>
              <p className="mt-1 text-xs text-ink-faint">
                This is an AI-generated summary. Verify against source data before taking action.
              </p>
            </div>
          )}

          {/* Provenance */}
          <div className="panel p-4">
            <h3 className="font-mono text-[11px] font-medium uppercase tracking-wider text-ink-dim">
              Provenance
            </h3>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-ink-faint">
              <div>Report ID: {report.reportId}</div>
              <div>Provider: {report.provider}</div>
              <div>Model: {report.model}</div>
              <div>Evidence Version: {report.evidenceVersion}</div>
              <div>Prompt Version: {report.promptVersion}</div>
              <div>Generated: {new Date(report.generatedAt).toLocaleString()}</div>
            </div>
          </div>
        </div>
      )}

      {/* Placeholder if no report */}
      {!report && !generating && (
        <div className="panel mt-8 flex flex-col items-center gap-3 rounded-md border border-dashed border-line-bright/60 bg-base-900/40 px-6 py-14 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full border border-line bg-base-850">
            <FileText className="h-5 w-5 text-ink-faint" />
          </div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-ink-dim">
            Select an incident and generate a report
          </p>
          <p className="max-w-md text-xs leading-relaxed text-ink-faint">
            Report generation uses structured system evidence to produce an AI-assisted
            investigation summary. All vessel associations are potential — human review required.
          </p>
        </div>
      )}
    </PageShell>
  );
}
