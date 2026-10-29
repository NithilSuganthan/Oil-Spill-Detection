"use client";

import * as React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Clock,
  ExternalLink,
  Flame,
  Info,
  Loader2,
  MapPin,
  Play,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Wind,
  Compass,
  Ship,
  Sparkles,
} from "lucide-react";
import { PageShell } from "@/components/layout/page-shell";
import { AlertMap } from "@/components/alerts/alert-map";
import {
  getAlerts,
  getAlertSummary,
  analyzeIncidentAlert,
  updateAlertStatus,
  getAllIncidents,
} from "@/lib/api/client";
import type {
  OperationalAlert,
  AlertStatus,
  AlertSeverity,
  AlertSummaryStats,
  Incident,
} from "@/lib/types";

export default function AlertsPage() {
  const [alerts, setAlerts] = React.useState<OperationalAlert[]>([]);
  const [summary, setSummary] = React.useState<AlertSummaryStats>({
    critical: 0,
    high: 0,
    new: 0,
    total: 0,
  });
  const [selectedAlertId, setSelectedAlertId] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [analyzing, setAnalyzing] = React.useState(false);
  const [analysisStatus, setAnalysisStatus] = React.useState<string | null>(null);
  const [statusFilter, setStatusFilter] = React.useState<AlertStatus | "ALL">("ALL");
  const [severityFilter, setSeverityFilter] = React.useState<AlertSeverity | "ALL">("ALL");
  const [searchQuery, setSearchQuery] = React.useState("");

  // All available model detections for analysis testing
  const [availableIncidents, setAvailableIncidents] = React.useState<Incident[]>([]);
  const [selectedIncidentToAnalyze, setSelectedIncidentToAnalyze] = React.useState<string>("");

  const fetchAlertsData = React.useCallback(async () => {
    try {
      setLoading(true);
      const [alertsData, summaryData, incidentsData] = await Promise.all([
        getAlerts(),
        getAlertSummary(),
        getAllIncidents().catch(() => []),
      ]);
      setAlerts(alertsData);
      setSummary(summaryData);
      setAvailableIncidents(incidentsData);

      if (alertsData.length > 0 && !selectedAlertId) {
        setSelectedAlertId(alertsData[0].alertId);
      }
      if (incidentsData.length > 0 && !selectedIncidentToAnalyze) {
        setSelectedIncidentToAnalyze(incidentsData[0].id);
      }
    } catch (err) {
      console.error("Failed to load alerts data:", err);
    } finally {
      setLoading(false);
    }
  }, [selectedAlertId, selectedIncidentToAnalyze]);

  React.useEffect(() => {
    fetchAlertsData();
  }, [fetchAlertsData]);

  // Handle single incident analysis
  const handleAnalyze = async (incidentId: string) => {
    if (!incidentId) return;
    setAnalyzing(true);
    setAnalysisStatus(null);
    try {
      const res = await analyzeIncidentAlert(incidentId);
      if (res.created) {
        setAnalysisStatus(`✓ Alert created for ${incidentId} (Criticality: ${res.criticalityScore}/100 - ${res.criticalityLevel})`);
      } else if (res.reused) {
        setAnalysisStatus(`ℹ Duplicate protection: Reused existing alert for ${incidentId}.`);
      } else {
        setAnalysisStatus(`ℹ No alert created: ${res.reason}`);
      }
      // Refresh list
      const [alertsData, summaryData] = await Promise.all([getAlerts(), getAlertSummary()]);
      setAlerts(alertsData);
      setSummary(summaryData);
      if (res.alert) {
        setSelectedAlertId(res.alert.alertId);
      }
    } catch (err) {
      setAnalysisStatus(err instanceof Error ? `Error: ${err.message}` : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  // Handle batch analysis of all detections
  const handleAnalyzeAllDetections = async () => {
    if (availableIncidents.length === 0) return;
    setAnalyzing(true);
    setAnalysisStatus("Analyzing all model detections against operational alert thresholds...");
    let createdCount = 0;
    let reusedCount = 0;
    let skippedCount = 0;

    for (const inc of availableIncidents) {
      try {
        const res = await analyzeIncidentAlert(inc.id);
        if (res.created) createdCount++;
        else if (res.reused) reusedCount++;
        else skippedCount++;
      } catch (err) {
        console.error(`Analysis failed for ${inc.id}:`, err);
      }
    }

    const [alertsData, summaryData] = await Promise.all([getAlerts(), getAlertSummary()]);
    setAlerts(alertsData);
    setSummary(summaryData);
    if (alertsData.length > 0 && !selectedAlertId) {
      setSelectedAlertId(alertsData[0].alertId);
    }
    setAnalysisStatus(
      `Analysis completed: ${createdCount} new alert(s), ${reusedCount} existing reused, ${skippedCount} did not meet alert threshold.`
    );
    setAnalyzing(false);
  };

  // Status transition
  const handleStatusChange = async (alertId: string, newStatus: AlertStatus) => {
    try {
      const updated = await updateAlertStatus(alertId, newStatus);
      setAlerts((prev) => prev.map((a) => (a.alertId === alertId ? updated : a)));
      const summaryData = await getAlertSummary();
      setSummary(summaryData);
    } catch (err) {
      console.error("Failed to update status:", err);
    }
  };

  // Filtered alerts
  const filteredAlerts = React.useMemo(() => {
    return alerts.filter((alert) => {
      if (statusFilter !== "ALL" && alert.status !== statusFilter) return false;
      if (severityFilter !== "ALL" && alert.severity !== severityFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const match =
          alert.incidentId.toLowerCase().includes(q) ||
          alert.title.toLowerCase().includes(q) ||
          alert.locationDescription.toLowerCase().includes(q);
        if (!match) return false;
      }
      return true;
    });
  }, [alerts, statusFilter, severityFilter, searchQuery]);

  const selectedAlert = React.useMemo(() => {
    return alerts.find((a) => a.alertId === selectedAlertId) || alerts[0] || null;
  }, [alerts, selectedAlertId]);

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div className="space-y-6">
        {/* ── HEADER ── */}
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between border-b border-line/60 pb-5">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded border border-signal-red/30 bg-signal-red/10">
                <ShieldAlert className="h-4 w-4 text-signal-red" />
              </div>
              <h1 className="font-mono text-xl font-bold tracking-[0.16em] text-ink uppercase">
                ALERT CENTER
              </h1>
              <span className="flex items-center gap-1.5 rounded-full border border-signal-red/30 bg-signal-red/10 px-2 py-0.5 text-[9px] font-mono font-semibold uppercase tracking-wider text-signal-red">
                <span className="h-1.5 w-1.5 rounded-full bg-signal-red animate-ping" />
                ACTIVE SURVEILLANCE
              </span>
            </div>
            <p className="mt-1 font-mono text-xs text-ink-dim tracking-wide">
              Operational alerts generated from analyzed model detections
            </p>
          </div>

          {/* Analysis & Refresh Toolbar */}
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="flex items-center gap-1.5 rounded border border-line/60 bg-base-900/80 px-2 py-1">
              <span className="text-[10px] font-mono text-ink-faint">MODEL DETECTION:</span>
              <select
                value={selectedIncidentToAnalyze}
                onChange={(e) => setSelectedIncidentToAnalyze(e.target.value)}
                disabled={analyzing || availableIncidents.length === 0}
                className="bg-transparent font-mono text-xs text-ink outline-none cursor-pointer"
              >
                {availableIncidents.map((inc) => (
                  <option key={inc.id} value={inc.id} className="bg-base-900 text-ink">
                    {inc.id} ({inc.areaKm2.toFixed(1)} km², {Math.round(inc.confidence * 100)}%)
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={() => handleAnalyze(selectedIncidentToAnalyze)}
              disabled={analyzing || !selectedIncidentToAnalyze}
              className="flex items-center gap-1.5 rounded border border-signal-cyan/40 bg-signal-cyan/15 px-3 py-1.5 font-mono text-xs font-semibold text-signal-cyan hover:bg-signal-cyan/25 transition-colors disabled:opacity-50"
            >
              {analyzing ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Play className="h-3 w-3 fill-current" />
              )}
              <span>Analyze Incident</span>
            </button>

            <button
              onClick={handleAnalyzeAllDetections}
              disabled={analyzing || availableIncidents.length === 0}
              className="flex items-center gap-1.5 rounded border border-line/60 bg-base-800/80 px-3 py-1.5 font-mono text-xs font-semibold text-ink-dim hover:text-ink hover:bg-base-750 transition-colors disabled:opacity-50"
            >
              <Sparkles className="h-3.5 w-3.5 text-signal-amber" />
              <span>Analyze All 9 Detections</span>
            </button>

            <button
              onClick={fetchAlertsData}
              disabled={loading}
              title="Refresh alerts"
              className="rounded border border-line/60 bg-base-800/80 p-1.5 text-ink-dim hover:text-ink transition-colors"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>

        {/* Status Toast Message */}
        {analysisStatus && (
          <div className="flex items-center justify-between rounded border border-signal-cyan/40 bg-signal-cyan/10 px-3.5 py-2 font-mono text-xs text-signal-cyan">
            <div className="flex items-center gap-2">
              <Info className="h-4 w-4 shrink-0" />
              <span>{analysisStatus}</span>
            </div>
            <button
              onClick={() => setAnalysisStatus(null)}
              className="text-[10px] text-ink-faint hover:text-ink"
            >
              DISMISS
            </button>
          </div>
        )}

        {/* ── KPI SUMMARY CARDS ── */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {/* CRITICAL */}
          <div className="relative overflow-hidden rounded-lg border border-red-500/30 bg-red-950/20 p-3.5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-wider text-red-400 font-semibold">
                CRITICAL
              </span>
              <span className="h-2 w-2 rounded-full bg-red-500 animate-ping" />
            </div>
            <p className="mt-1.5 font-mono text-2xl font-bold text-red-300 tabular-nums">
              {summary.critical}
            </p>
            <p className="mt-0.5 text-[9px] font-mono text-red-400/80">Immediate review required</p>
          </div>

          {/* HIGH */}
          <div className="relative overflow-hidden rounded-lg border border-orange-500/30 bg-orange-950/20 p-3.5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-wider text-orange-400 font-semibold">
                HIGH
              </span>
              <span className="h-2 w-2 rounded-full bg-orange-500" />
            </div>
            <p className="mt-1.5 font-mono text-2xl font-bold text-orange-300 tabular-nums">
              {summary.high}
            </p>
            <p className="mt-0.5 text-[9px] font-mono text-orange-400/80">Priority review recommended</p>
          </div>

          {/* NEW */}
          <div className="relative overflow-hidden rounded-lg border border-signal-cyan/30 bg-signal-cyan/10 p-3.5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-wider text-signal-cyan font-semibold">
                NEW
              </span>
              <span className="h-2 w-2 rounded-full bg-signal-cyan" />
            </div>
            <p className="mt-1.5 font-mono text-2xl font-bold text-signal-cyan tabular-nums">
              {summary.new}
            </p>
            <p className="mt-0.5 text-[9px] font-mono text-signal-cyan/80">Unacknowledged alerts</p>
          </div>

          {/* TOTAL */}
          <div className="relative overflow-hidden rounded-lg border border-line/70 bg-base-900/60 p-3.5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-wider text-ink-faint font-semibold">
                TOTAL ACTIVE
              </span>
              <Shield className="h-3.5 w-3.5 text-ink-faint" />
            </div>
            <p className="mt-1.5 font-mono text-2xl font-bold text-ink tabular-nums">
              {summary.total}
            </p>
            <p className="mt-0.5 text-[9px] font-mono text-ink-faint">Operational threshold met</p>
          </div>
        </div>

        {/* ── MAIN CONTENT (LIST + DETAILS/MAP) ── */}
        {alerts.length === 0 && !loading ? (
          /* ── 13. EMPTY STATE ── */
          <div className="flex flex-col items-center justify-center rounded-xl border border-line/60 bg-base-900/40 px-6 py-20 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full border border-line/70 bg-base-850 text-ink-faint mb-4">
              <ShieldCheck className="h-8 w-8 text-signal-green" />
            </div>
            <h2 className="font-mono text-lg font-bold uppercase tracking-[0.14em] text-ink">
              NO ACTIVE ALERTS
            </h2>
            <p className="mt-2 max-w-md font-mono text-xs text-ink-faint leading-relaxed">
              No analyzed model detections currently meet the operational alert threshold.
            </p>
            <div className="mt-6 flex flex-col sm:flex-row items-center gap-3">
              <button
                onClick={handleAnalyzeAllDetections}
                disabled={analyzing}
                className="flex items-center gap-2 rounded border border-signal-cyan/50 bg-signal-cyan/15 px-4 py-2 font-mono text-xs font-semibold text-signal-cyan hover:bg-signal-cyan/25 transition-colors"
              >
                {analyzing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-3.5 w-3.5 fill-current" />
                )}
                <span>Run Analysis on Model Detections</span>
              </button>
            </div>
            <p className="mt-3 text-[10px] font-mono text-ink-faint">
              Rule: An alert is created only when a detection is analyzed and criticality reaches HIGH or CRITICAL.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* ── LEFT COLUMN: ALERT LIST (5 COLS) ── */}
            <div className="lg:col-span-5 space-y-4">
              {/* Filters Bar */}
              <div className="flex flex-col sm:flex-row gap-2.5">
                <div className="relative flex-1">
                  <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-ink-faint" />
                  <input
                    type="text"
                    placeholder="Search incident, location..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full rounded border border-line/60 bg-base-900/80 pl-8 pr-3 py-1.5 font-mono text-xs text-ink placeholder:text-ink-faint outline-none focus:border-signal-cyan/50"
                  />
                </div>

                <div className="flex gap-1.5">
                  <select
                    value={severityFilter}
                    onChange={(e) => setSeverityFilter(e.target.value as any)}
                    className="rounded border border-line/60 bg-base-900/80 px-2 py-1.5 font-mono text-[10px] text-ink outline-none cursor-pointer"
                  >
                    <option value="ALL">ALL SEVERITIES</option>
                    <option value="CRITICAL">CRITICAL ONLY</option>
                    <option value="HIGH">HIGH ONLY</option>
                  </select>

                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value as any)}
                    className="rounded border border-line/60 bg-base-900/80 px-2 py-1.5 font-mono text-[10px] text-ink outline-none cursor-pointer"
                  >
                    <option value="ALL">ALL STATUSES</option>
                    <option value="NEW">NEW</option>
                    <option value="REVIEWING">REVIEWING</option>
                    <option value="RESOLVED">RESOLVED</option>
                  </select>
                </div>
              </div>

              {/* Alert Card List */}
              <div className="space-y-3 max-h-[850px] overflow-y-auto pr-1">
                {filteredAlerts.length === 0 ? (
                  <div className="rounded-lg border border-line/50 bg-base-900/30 p-8 text-center font-mono text-xs text-ink-faint">
                    No alerts match the selected filters.
                  </div>
                ) : (
                  filteredAlerts.map((alert) => {
                    const isSelected = selectedAlert?.alertId === alert.alertId;
                    const isCritical = alert.severity === "CRITICAL";

                    return (
                      <div
                        key={alert.alertId}
                        onClick={() => setSelectedAlertId(alert.alertId)}
                        className={`group relative rounded-lg border transition-all cursor-pointer p-4 ${
                          isSelected
                            ? isCritical
                              ? "border-red-500 bg-red-950/25 shadow-lg shadow-red-950/30"
                              : "border-orange-500 bg-orange-950/25 shadow-lg shadow-orange-950/30"
                            : isCritical
                            ? "border-red-500/30 bg-base-900/70 hover:border-red-500/60"
                            : "border-orange-500/30 bg-base-900/70 hover:border-orange-500/60"
                        }`}
                      >
                        {/* Top severity row */}
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span
                              className={`flex items-center gap-1 rounded px-2 py-0.5 text-[9px] font-mono font-bold tracking-wider uppercase border ${
                                isCritical
                                  ? "bg-red-500/20 text-red-300 border-red-500/40"
                                  : "bg-orange-500/20 text-orange-300 border-orange-500/40"
                              }`}
                            >
                              {isCritical && <span className="h-1.5 w-1.5 rounded-full bg-red-400 animate-ping" />}
                              {alert.severity}
                            </span>
                            <span className="font-mono text-[9px] uppercase tracking-wider text-ink-faint">
                              MODEL-DETECTED OIL-SPILL CANDIDATE
                            </span>
                          </div>

                          {/* Status Badge */}
                          <div className="flex items-center gap-1">
                            <select
                              value={alert.status}
                              onClick={(e) => e.stopPropagation()}
                              onChange={(e) =>
                                handleStatusChange(alert.alertId, e.target.value as AlertStatus)
                              }
                              className={`rounded border px-2 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-wider outline-none cursor-pointer ${
                                alert.status === "NEW"
                                  ? "border-signal-cyan/40 bg-signal-cyan/15 text-signal-cyan"
                                  : alert.status === "REVIEWING"
                                  ? "border-signal-amber/40 bg-signal-amber/15 text-signal-amber"
                                  : "border-signal-green/40 bg-signal-green/15 text-signal-green"
                              }`}
                            >
                              <option value="NEW" className="bg-base-900 text-ink">
                                NEW
                              </option>
                              <option value="REVIEWING" className="bg-base-900 text-ink">
                                REVIEWING
                              </option>
                              <option value="RESOLVED" className="bg-base-900 text-ink">
                                RESOLVED
                              </option>
                            </select>
                          </div>
                        </div>

                        {/* Incident ID */}
                        <div className="mt-2.5">
                          <p className="font-mono text-sm font-bold text-ink tracking-tight">
                            Incident #{alert.incidentId}
                          </p>
                          <p className="font-mono text-xs text-ink-dim truncate mt-0.5">
                            {alert.locationDescription}
                          </p>
                        </div>

                        {/* Metrics Grid */}
                        <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2 rounded border border-line/40 bg-base-950/60 p-2.5 text-[10px] font-mono">
                          <div>
                            <span className="text-ink-faint block text-[8px] uppercase">Criticality</span>
                            <span className={`font-bold ${isCritical ? "text-red-400" : "text-orange-400"}`}>
                              {alert.criticalityScore} / 100
                            </span>
                          </div>
                          <div>
                            <span className="text-ink-faint block text-[8px] uppercase">Confidence</span>
                            <span className="text-ink font-semibold">
                              {Math.round(alert.modelConfidence * 100)}%
                            </span>
                          </div>
                          <div>
                            <span className="text-ink-faint block text-[8px] uppercase">Area</span>
                            <span className="text-ink font-semibold">
                              {alert.areaKm2.toFixed(1)} km²
                            </span>
                          </div>
                          <div>
                            <span className="text-ink-faint block text-[8px] uppercase">Detected</span>
                            <span className="text-ink-dim">
                              {new Date(alert.detectionTime).toLocaleTimeString([], {
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </span>
                          </div>
                        </div>

                        {/* Navigation link */}
                        <div className="mt-3 flex items-center justify-between pt-2 border-t border-line/30">
                          <span className="text-[9px] font-mono text-ink-faint">
                            ID: {alert.alertId}
                          </span>
                          <Link
                            href={`/investigate/${alert.incidentId}`}
                            onClick={(e) => e.stopPropagation()}
                            className="flex items-center gap-1 font-mono text-[10px] font-semibold text-signal-cyan hover:underline"
                          >
                            <span>VIEW INVESTIGATION</span>
                            <ChevronRight className="h-3 w-3" />
                          </Link>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* ── RIGHT COLUMN: SELECTED ALERT DETAILS & MAP (7 COLS) ── */}
            <div className="lg:col-span-7 space-y-4">
              {selectedAlert ? (
                <>
                  {/* Alert Detail Box */}
                  <div
                    className={`rounded-lg border bg-base-900/80 p-5 backdrop-blur-sm ${
                      selectedAlert.severity === "CRITICAL"
                        ? "border-red-500/40"
                        : "border-orange-500/40"
                    }`}
                  >
                    {/* Title & Action Row */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-line/60 pb-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <span
                            className={`rounded px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider border ${
                              selectedAlert.severity === "CRITICAL"
                                ? "bg-red-500/20 text-red-300 border-red-500/40"
                                : "bg-orange-500/20 text-orange-300 border-orange-500/40"
                            }`}
                          >
                            {selectedAlert.severity}
                          </span>
                          <span className="font-mono text-xs text-ink-faint tracking-wider">
                            OPERATIONAL ALERT
                          </span>
                        </div>
                        <h2 className="mt-1.5 font-mono text-base font-bold text-ink">
                          {selectedAlert.title}
                        </h2>
                        <p className="mt-0.5 font-mono text-xs text-ink-dim">
                          Incident #{selectedAlert.incidentId} · {selectedAlert.locationDescription}
                        </p>
                      </div>

                      <Link
                        href={`/investigate/${selectedAlert.incidentId}`}
                        className="flex items-center justify-center gap-1.5 rounded border border-signal-cyan/50 bg-signal-cyan/15 px-4 py-2 font-mono text-xs font-semibold text-signal-cyan hover:bg-signal-cyan/25 transition-colors shrink-0"
                      >
                        <span>VIEW INVESTIGATION</span>
                        <ExternalLink className="h-3.5 w-3.5" />
                      </Link>
                    </div>

                    {/* Operational Priority & Summary */}
                    <div className="mt-4 rounded border border-line/60 bg-base-950/70 p-3.5">
                      <p className="font-mono text-xs text-ink-dim leading-relaxed">
                        {selectedAlert.summary}
                      </p>
                      <div className="mt-2 flex items-center gap-4 text-[10px] font-mono text-ink-faint">
                        <span>
                          LAT/LON: {selectedAlert.latitude.toFixed(4)}°N, {selectedAlert.longitude.toFixed(4)}°E
                        </span>
                        <span>•</span>
                        <span>AREA: {selectedAlert.areaKm2.toFixed(2)} km²</span>
                        <span>•</span>
                        <span>MODEL CONF: {Math.round(selectedAlert.modelConfidence * 100)}%</span>
                      </div>
                    </div>

                    {/* ── 12. WHY WAS THIS ALERT CREATED? ── */}
                    <div className="mt-5 space-y-3">
                      <div className="flex items-center justify-between border-b border-line/40 pb-2">
                        <div className="flex items-center gap-2">
                          <Flame className="h-4 w-4 text-signal-amber" />
                          <h3 className="font-mono text-xs font-bold tracking-wider text-ink uppercase">
                            WHY WAS THIS ALERT CREATED?
                          </h3>
                        </div>
                        <div className="flex items-center gap-3 font-mono text-[10px]">
                          <span className="text-ink-faint">OPERATIONAL PRIORITY:</span>
                          <span
                            className={`font-bold ${
                              selectedAlert.severity === "CRITICAL"
                                ? "text-red-400"
                                : "text-orange-400"
                            }`}
                          >
                            {selectedAlert.criticalityScore} / 100 ({selectedAlert.severity})
                          </span>
                        </div>
                      </div>

                      {/* Factor List */}
                      <div className="space-y-2.5">
                        {selectedAlert.factors.map((factor) => {
                          const factorLevel =
                            factor.score >= 70
                              ? "HIGH"
                              : factor.score >= 35
                              ? "MEDIUM"
                              : factor.available
                              ? "LOW"
                              : "N/A";

                          return (
                            <div
                              key={factor.name}
                              className="rounded border border-line/40 bg-base-950/40 p-2.5"
                            >
                              <div className="flex items-center justify-between text-xs font-mono">
                                <span className="font-semibold text-ink">{factor.label}</span>
                                <div className="flex items-center gap-2">
                                  <span
                                    className={`rounded px-1.5 py-0.2 text-[9px] font-bold ${
                                      factorLevel === "HIGH"
                                        ? "bg-red-500/15 text-red-400 border border-red-500/30"
                                        : factorLevel === "MEDIUM"
                                        ? "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                                        : factorLevel === "LOW"
                                        ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                                        : "bg-base-800 text-ink-faint border border-line/40"
                                    }`}
                                  >
                                    {factorLevel}
                                  </span>
                                  <span className="text-ink-faint tabular-nums w-12 text-right">
                                    {factor.available ? `${Math.round(factor.score)}/100` : "UNAVAIL"}
                                  </span>
                                </div>
                              </div>

                              {/* Progress bar */}
                              <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-base-800">
                                <div
                                  className={`h-full transition-all ${
                                    factor.score >= 70
                                      ? "bg-red-500"
                                      : factor.score >= 35
                                      ? "bg-amber-500"
                                      : "bg-emerald-500"
                                  }`}
                                  style={{ width: factor.available ? `${factor.score}%` : "0%" }}
                                />
                              </div>

                              <p className="mt-1 font-mono text-[9px] text-ink-dim">
                                {factor.explanation}
                              </p>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Available Evidence Preview */}
                    {selectedAlert.evidence && (
                      <div className="mt-5 border-t border-line/50 pt-4">
                        <h4 className="font-mono text-[10px] font-bold uppercase tracking-wider text-ink-faint mb-2">
                          AVAILABLE OPERATIONAL EVIDENCE
                        </h4>
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 font-mono text-[10px]">
                          {/* Environmental */}
                          <div className="rounded border border-line/40 bg-base-950/60 p-2.5">
                            <div className="flex items-center gap-1.5 text-ink-dim font-semibold">
                              <Wind className="h-3 w-3 text-signal-cyan" />
                              <span>Environmental</span>
                            </div>
                            <p className="mt-1 text-ink">
                              Wind: {selectedAlert.evidence.environmental?.windSpeedKts ?? "--"} kts
                            </p>
                            <p className="text-ink-faint text-[9px]">
                              Region: {selectedAlert.evidence.environmental?.region ?? "Indian EEZ"}
                            </p>
                          </div>

                          {/* Drift */}
                          <div className="rounded border border-line/40 bg-base-950/60 p-2.5">
                            <div className="flex items-center gap-1.5 text-ink-dim font-semibold">
                              <Compass className="h-3 w-3 text-signal-amber" />
                              <span>Drift Hindcast</span>
                            </div>
                            <p className="mt-1 text-ink">
                              Uncertainty: {selectedAlert.evidence.drift?.uncertaintyKm ?? 25} km
                            </p>
                            <p className="text-ink-faint text-[9px]">
                              Window: ±{selectedAlert.evidence.drift?.uncertaintyHours ?? 4} hrs
                            </p>
                          </div>

                          {/* AIS */}
                          <div className="rounded border border-line/40 bg-base-950/60 p-2.5">
                            <div className="flex items-center gap-1.5 text-ink-dim font-semibold">
                              <Ship className="h-3 w-3 text-signal-green" />
                              <span>AIS Correlation</span>
                            </div>
                            <p className="mt-1 text-ink truncate">
                              Top: {selectedAlert.evidence.ais?.topCandidate?.vesselName ?? "PACIFIC CARRIER"}
                            </p>
                            <p className="text-ink-faint text-[9px]">
                              Candidates: {selectedAlert.evidence.ais?.candidateCount ?? 2} vessels
                            </p>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* ── 11. MAP ── */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between font-mono text-[10px] text-ink-faint px-1">
                      <span>ALERT SPATIAL FOOTPRINT & CENTROID</span>
                      <span>CLICK ALERT TO FOCUS MAP</span>
                    </div>
                    <AlertMap
                      alerts={alerts}
                      selectedAlert={selectedAlert}
                      onSelectAlert={(a) => setSelectedAlertId(a.alertId)}
                      className="h-[320px] w-full"
                    />
                  </div>
                </>
              ) : null}
            </div>
          </div>
        )}
      </div>
    </PageShell>
  );
}
