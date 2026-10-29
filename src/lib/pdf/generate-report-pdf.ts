/**
 * PDF Report Generator for SAGAR WATCH Oil Spill Investigation Reports
 *
 * Generates a professional, multi-page PDF investigation report using jsPDF.
 * Includes: Executive Summary, Detection Assessment, Drift Analysis,
 * AIS Vessel Correlation, Environmental Data, Uncertainty Analysis,
 * Recommended Actions, and Limitations.
 *
 * This module does NOT fabricate data — it formats data already produced by
 * the investigation pipeline (or mock pipeline in demo mode).
 */

import { jsPDF } from "jspdf";
import type { DriftResult, AttributionResult, StoredReport, Incident } from "@/lib/types";

// Colors (RGB tuples)
const NAVY = [10, 17, 32] as const;
const DARK_BG = [14, 24, 42] as const;
const CYAN = [34, 211, 238] as const;
const AMBER = [245, 158, 11] as const;
const RED = [239, 68, 68] as const;
const GREEN = [52, 211, 153] as const;
const TEXT = [230, 237, 245] as const;
const TEXT_DIM = [92, 113, 143] as const;
const LINE = [30, 45, 70] as const;

interface ReportData {
  incident?: Incident | null;
  drift?: DriftResult | null;
  attribution?: AttributionResult | null;
  report?: StoredReport | null;
}

/**
 * Generates and downloads a comprehensive PDF investigation report.
 */
export function generateInvestigationPDF(data: ReportData) {
  const { incident, drift, attribution, report } = data;
  const incidentId = incident?.id ?? drift?.incidentId ?? "UNKNOWN";
  const now = new Date();

  const doc = new jsPDF({
    orientation: "portrait",
    unit: "mm",
    format: "a4",
  });

  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 16;
  const contentWidth = pageWidth - margin * 2;
  let y = 0;

  // ─── HELPERS ───
  const setColor = (rgb: readonly [number, number, number]) =>
    doc.setTextColor(rgb[0], rgb[1], rgb[2]);
  const setDrawColor = (rgb: readonly [number, number, number]) =>
    doc.setDrawColor(rgb[0], rgb[1], rgb[2]);
  const setFillColor = (rgb: readonly [number, number, number]) =>
    doc.setFillColor(rgb[0], rgb[1], rgb[2]);

  const addPage = () => {
    doc.addPage();
    y = margin;
    drawPageBg();
    drawFooter();
  };

  const checkPageBreak = (requiredSpace: number) => {
    if (y + requiredSpace > pageHeight - 20) {
      addPage();
    }
  };

  const drawPageBg = () => {
    setFillColor(NAVY);
    doc.rect(0, 0, pageWidth, pageHeight, "F");
  };

  const drawFooter = () => {
    setColor(TEXT_DIM);
    doc.setFontSize(7);
    doc.text(
      `SAGAR WATCH — Oil Spill Intelligence System | Report: ${incidentId} | Generated: ${now.toISOString()} | Page ${doc.getNumberOfPages()}`,
      pageWidth / 2,
      pageHeight - 6,
      { align: "center" }
    );
    setDrawColor(LINE);
    doc.line(margin, pageHeight - 10, pageWidth - margin, pageHeight - 10);
  };

  const sectionHeader = (title: string, color: readonly [number, number, number] = CYAN) => {
    checkPageBreak(14);
    y += 4;
    setDrawColor(color);
    doc.setLineWidth(0.6);
    doc.line(margin, y, margin + 35, y);
    y += 5;
    setColor(color);
    doc.setFontSize(11);
    doc.setFont("helvetica", "bold");
    doc.text(title.toUpperCase(), margin, y);
    y += 2;
    setDrawColor(LINE);
    doc.setLineWidth(0.2);
    doc.line(margin, y, pageWidth - margin, y);
    y += 5;
  };

  const labelValue = (
    label: string,
    value: string,
    x: number = margin,
    maxWidth: number = contentWidth
  ) => {
    checkPageBreak(7);
    setColor(TEXT_DIM);
    doc.setFontSize(8);
    doc.setFont("helvetica", "normal");
    doc.text(label, x, y);
    setColor(TEXT);
    doc.setFontSize(9);
    doc.setFont("helvetica", "bold");
    doc.text(value, x + 48, y, { maxWidth: maxWidth - 48 });
    y += 5;
  };

  const paragraph = (text: string) => {
    checkPageBreak(12);
    setColor(TEXT);
    doc.setFontSize(8.5);
    doc.setFont("helvetica", "normal");
    const lines = doc.splitTextToSize(text, contentWidth);
    doc.text(lines, margin, y);
    y += lines.length * 4 + 2;
  };

  const bulletPoint = (text: string, bulletColor: readonly [number, number, number] = CYAN) => {
    checkPageBreak(6);
    setColor(bulletColor);
    doc.setFontSize(8);
    doc.text("●", margin + 2, y);
    setColor(TEXT);
    doc.setFontSize(8.5);
    doc.setFont("helvetica", "normal");
    const lines = doc.splitTextToSize(text, contentWidth - 10);
    doc.text(lines, margin + 8, y);
    y += lines.length * 4 + 1.5;
  };

  const warningBox = (text: string) => {
    checkPageBreak(14);
    setFillColor([30, 25, 10]);
    setDrawColor(AMBER);
    doc.setLineWidth(0.4);
    doc.roundedRect(margin, y, contentWidth, 10, 1.5, 1.5, "FD");
    setColor(AMBER);
    doc.setFontSize(7.5);
    doc.setFont("helvetica", "bold");
    doc.text("⚠  " + text, margin + 4, y + 6.5);
    y += 14;
  };

  // ═══════════════════════════════════════════════════════
  // PAGE 1: COVER PAGE & EXECUTIVE SUMMARY
  // ═══════════════════════════════════════════════════════

  drawPageBg();

  // Top accent bar
  setFillColor(CYAN);
  doc.rect(0, 0, pageWidth, 3, "F");

  // SAGAR WATCH branding
  y = 28;
  setColor(CYAN);
  doc.setFontSize(8);
  doc.setFont("helvetica", "bold");
  doc.text("SAGAR WATCH", margin, y);
  y += 4;
  setColor(TEXT_DIM);
  doc.setFontSize(6.5);
  doc.setFont("helvetica", "normal");
  doc.text("OIL SPILL INTELLIGENCE SYSTEM — INVESTIGATION REPORT", margin, y);

  // Main Title
  y += 16;
  setColor(TEXT);
  doc.setFontSize(22);
  doc.setFont("helvetica", "bold");
  doc.text("INCIDENT INVESTIGATION", margin, y);
  y += 9;
  doc.setFontSize(18);
  setColor(CYAN);
  doc.text(`REPORT — ${incidentId}`, margin, y);

  // Separator
  y += 8;
  setDrawColor(CYAN);
  doc.setLineWidth(0.6);
  doc.line(margin, y, pageWidth - margin, y);

  // Key Facts Grid
  y += 10;
  const facts: [string, string][] = [
    ["INCIDENT ID", incidentId],
    ["REGION", incident?.region ?? incident?.locationDescription ?? "Indian Waters"],
    ["DETECTED", incident?.detectedAt ? new Date(incident.detectedAt).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) + " IST" : "—"],
    ["AREA", incident?.areaKm2 ? `${incident.areaKm2.toFixed(1)} km²` : "—"],
    ["CONFIDENCE", incident?.confidence ? `${(incident.confidence * 100).toFixed(1)}%` : drift?.confidence ? `${(drift.confidence * 100).toFixed(1)}%` : "—"],
    ["SATELLITE", incident?.satellite ?? "Sentinel-1"],
    ["STATUS", incident?.status?.toUpperCase() ?? "COMPLETED"],
    ["DRIFT METHOD", drift?.method ?? "backward_hindcast"],
  ];

  for (let i = 0; i < facts.length; i += 2) {
    checkPageBreak(6);
    // Left column
    setColor(TEXT_DIM);
    doc.setFontSize(7);
    doc.setFont("helvetica", "normal");
    doc.text(facts[i][0], margin, y);
    setColor(TEXT);
    doc.setFontSize(9);
    doc.setFont("helvetica", "bold");
    doc.text(facts[i][1], margin, y + 5);

    // Right column
    if (facts[i + 1]) {
      setColor(TEXT_DIM);
      doc.setFontSize(7);
      doc.setFont("helvetica", "normal");
      doc.text(facts[i + 1][0], margin + contentWidth / 2, y);
      setColor(TEXT);
      doc.setFontSize(9);
      doc.setFont("helvetica", "bold");
      doc.text(facts[i + 1][1], margin + contentWidth / 2, y + 5);
    }
    y += 12;
  }

  // Classification Banner
  y += 4;
  setFillColor([25, 10, 10]);
  setDrawColor(RED);
  doc.setLineWidth(0.4);
  doc.roundedRect(margin, y, contentWidth, 12, 2, 2, "FD");
  setColor(RED);
  doc.setFontSize(8);
  doc.setFont("helvetica", "bold");
  doc.text("CLASSIFICATION: DEMO / PROTOTYPE — NOT FOR OPERATIONAL USE", pageWidth / 2, y + 5.5, { align: "center" });
  setColor(TEXT_DIM);
  doc.setFontSize(6.5);
  doc.setFont("helvetica", "normal");
  doc.text("All vessel associations are potential — human review required before any enforcement action.", pageWidth / 2, y + 9.5, { align: "center" });

  // Executive Summary
  y += 20;
  sectionHeader("EXECUTIVE SUMMARY");

  if (report?.report?.executiveSummary) {
    paragraph(report.report.executiveSummary);
  } else {
    const lat = drift?.slickLatitude ?? incident?.centroid?.lat ?? 0;
    const lon = drift?.slickLongitude ?? incident?.centroid?.lon ?? 0;
    const area = incident?.areaKm2 ?? 0;
    const conf = ((incident?.confidence ?? drift?.confidence ?? 0) * 100).toFixed(1);
    const topVessel = attribution?.candidates?.[0];
    paragraph(
      `A potential oil spill slick was detected at coordinates ${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E ` +
      `in the ${incident?.region ?? "Indian waters"} region. The detection covers approximately ${area.toFixed(1)} km² ` +
      `with a model confidence of ${conf}%. ` +
      (topVessel
        ? `Backward drift analysis identified ${topVessel.vesselName} (MMSI: ${topVessel.mmsi}) as the highest-ranked ` +
          `potential source vessel with an attribution score of ${(topVessel.attributionScore * 100).toFixed(0)}%. `
        : "") +
      `This is a model-generated assessment requiring human verification.`
    );
  }

  drawFooter();

  // ═══════════════════════════════════════════════════════
  // PAGE 2: DETECTION & DRIFT ANALYSIS
  // ═══════════════════════════════════════════════════════

  addPage();

  sectionHeader("DETECTION ASSESSMENT", RED);

  if (report?.report?.detectionAssessment) {
    paragraph(report.report.detectionAssessment);
  } else {
    labelValue("Sensor:", incident?.satellite ?? "Sentinel-1 SAR");
    labelValue("Scene ID:", incident?.sceneId ?? "—");
    labelValue("Detection Model:", "OilSpillNet (TinyUNet v1.0-dev)");
    labelValue("Detected Area:", `${(incident?.areaKm2 ?? 0).toFixed(1)} km²`);
    labelValue("Model Confidence:", `${((incident?.confidence ?? 0) * 100).toFixed(1)}%`);
    labelValue("Wind at Detection:", `${incident?.windSpeedKts ?? "—"} kts`);
    y += 2;
    warningBox("MODEL PREDICTION — HUMAN VERIFICATION REQUIRED BEFORE ENFORCEMENT ACTION");
  }

  sectionHeader("BACKWARD DRIFT ANALYSIS", GREEN);

  if (drift) {
    labelValue("Method:", drift.method.replace(/_/g, " ").toUpperCase());
    labelValue("Integration:", `${drift.integrationHours} hours (${drift.timestepMinutes} min steps)`);
    labelValue("Ensemble Size:", `${drift.ensembleSize} simulations`);
    labelValue("Confidence:", `${(drift.confidence * 100).toFixed(1)}%`);
    y += 2;
    labelValue("Detected Slick:", `${drift.slickLatitude.toFixed(4)}°N, ${drift.slickLongitude.toFixed(4)}°E`);
    labelValue("Estimated Source:", `${drift.sourceLatitude.toFixed(4)}°N, ${drift.sourceLongitude.toFixed(4)}°E`);
    labelValue("Spatial Uncertainty:", `±${drift.uncertaintyKm.toFixed(1)} km`);
    labelValue("Temporal Uncertainty:", `±${drift.uncertaintyHours} hours`);
    labelValue("Release Window:", `${drift.sourceEarliest ? new Date(drift.sourceEarliest).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" }) : "—"} – ${drift.sourceLatest ? new Date(drift.sourceLatest).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" }) : "—"} IST`);

    if (drift.qualityFlags.length > 0) {
      y += 3;
      setColor(AMBER);
      doc.setFontSize(8);
      doc.setFont("helvetica", "bold");
      doc.text("Quality Flags:", margin, y);
      y += 4;
      drift.qualityFlags.forEach((flag) => bulletPoint(flag, AMBER));
    }

    // Trajectory Waypoints Table
    if (drift.sourcePoints && drift.sourcePoints.length > 0) {
      y += 3;
      sectionHeader("TRAJECTORY WAYPOINTS", CYAN);
      const maxWaypoints = Math.min(10, drift.sourcePoints.length);
      const step = Math.floor(drift.sourcePoints.length / maxWaypoints);

      for (let i = 0; i < maxWaypoints; i++) {
        const idx = i * step;
        const pt = drift.sourcePoints[idx] as [number, number];
        if (!pt) continue;
        const timeLabel = `T-${((1 - idx / (drift.sourcePoints.length - 1)) * 8).toFixed(1)}h`;
        checkPageBreak(5);
        setColor(TEXT_DIM);
        doc.setFontSize(7.5);
        doc.text(`#${idx + 1}`, margin, y);
        setColor(CYAN);
        doc.text(timeLabel, margin + 12, y);
        setColor(TEXT);
        doc.setFontSize(8);
        doc.text(`${pt[0].toFixed(4)}°N, ${pt[1].toFixed(4)}°E`, margin + 32, y);
        y += 4.5;
      }
    }
  } else {
    paragraph("No backward drift analysis has been computed for this incident.");
  }

  // ═══════════════════════════════════════════════════════
  // PAGE 3: AIS VESSEL CORRELATION
  // ═══════════════════════════════════════════════════════

  addPage();

  sectionHeader("AIS VESSEL CORRELATION", AMBER);

  if (report?.report?.aisAssessment) {
    paragraph(report.report.aisAssessment);
    y += 2;
  }

  if (attribution && attribution.candidates.length > 0) {
    labelValue("AIS Provider:", attribution.provider ?? "—");
    labelValue("Dataset:", attribution.dataset ?? "—");
    labelValue("Search Radius:", `${attribution.searchWindow?.radiusKm ?? "—"} km`);
    labelValue("Time Window:", `${attribution.searchWindow?.timeWindowHours ?? "—"} hours`);
    labelValue("Candidates Found:", `${attribution.candidateCount}`);
    labelValue("Total AIS Obs.:", `${attribution.totalObservations}`);
    y += 4;

    // Candidate Vessel Table
    setColor(CYAN);
    doc.setFontSize(9);
    doc.setFont("helvetica", "bold");
    doc.text("RANKED CANDIDATE VESSELS", margin, y);
    y += 6;

    attribution.candidates.forEach((vessel, idx) => {
      checkPageBreak(32);

      // Card background
      setFillColor(idx === 0 ? [20, 18, 8] : DARK_BG);
      setDrawColor(idx === 0 ? AMBER : LINE);
      doc.setLineWidth(0.3);
      doc.roundedRect(margin, y, contentWidth, 25, 1.5, 1.5, "FD");

      // Rank badge
      setColor(idx === 0 ? AMBER : CYAN);
      doc.setFontSize(9);
      doc.setFont("helvetica", "bold");
      doc.text(`#${idx + 1}`, margin + 3, y + 5.5);

      // Vessel name
      setColor(TEXT);
      doc.setFontSize(10);
      doc.text(vessel.vesselName || `MMSI ${vessel.mmsi}`, margin + 14, y + 5.5);

      // Score
      const score = (vessel.attributionScore * 100).toFixed(0);
      setColor(idx === 0 ? AMBER : CYAN);
      doc.setFontSize(11);
      doc.setFont("helvetica", "bold");
      doc.text(`${score}%`, pageWidth - margin - 5, y + 5.5, { align: "right" });

      // Details row 1
      setColor(TEXT_DIM);
      doc.setFontSize(7);
      doc.setFont("helvetica", "normal");
      doc.text(`MMSI: ${vessel.mmsi}  |  Type: ${vessel.vesselType}  |  Flag: ${vessel.flag}  |  IMO: ${vessel.imo ?? "—"}`, margin + 14, y + 11);

      // Details row 2
      doc.text(
        `Closest: ${vessel.closestDistanceKm.toFixed(2)} km  |  Time Gap: ${vessel.closestTimeDifferenceMinutes} min  |  Observations: ${vessel.numberOfObservations}`,
        margin + 14,
        y + 15.5
      );

      // Score components
      if (vessel.scoreComponents) {
        const sc = vessel.scoreComponents;
        doc.text(
          `Score Components — Distance: ${(sc.distance * 100).toFixed(0)}%  |  Time: ${(sc.time * 100).toFixed(0)}%  |  Track: ${(sc.trackConsistency * 100).toFixed(0)}%`,
          margin + 14,
          y + 20
        );
      }

      y += 28;
    });

    y += 2;
    warningBox("AIS proximity does NOT establish causation. Human review required for all vessel associations.");
  } else {
    paragraph("No AIS correlation data available for this incident.");
  }

  // ═══════════════════════════════════════════════════════
  // PAGE 4: ENVIRONMENT, RECOMMENDATIONS, LIMITATIONS
  // ═══════════════════════════════════════════════════════

  addPage();

  sectionHeader("ENVIRONMENTAL CONDITIONS");

  if (report?.report?.environmentAssessment) {
    paragraph(report.report.environmentAssessment);
  } else if (drift) {
    const prov = (drift.provenance ?? {}) as Record<string, unknown>;
    labelValue("Provider:", String(prov.environmentalProvider ?? "mock"));
    labelValue("Status:", drift.qualityFlags.includes("DEMO_ENVIRONMENTAL_FORCING") ? "DEMO (SIMULATED FORCING)" : "OPERATIONAL");
    labelValue("Wind Model:", "ERA5 Reanalysis (simulated)");
    labelValue("Current Model:", "HYCOM (simulated)");
    labelValue("Windage Coeff.:", String(prov.windageCoefficient ?? "0.03"));
    y += 2;
    warningBox("Environmental forcing data is SIMULATED in demo mode. Not suitable for operational decisions.");
  }

  sectionHeader("UNCERTAINTY ANALYSIS");

  if (report?.report?.uncertainty) {
    paragraph(report.report.uncertainty);
  } else {
    paragraph(
      `Source location uncertainty: ±${drift?.uncertaintyKm?.toFixed(1) ?? "—"} km spatial, ` +
      `±${drift?.uncertaintyHours ?? "—"} hours temporal. ` +
      `Model confidence: ${((drift?.confidence ?? 0) * 100).toFixed(1)}%. ` +
      `Environmental forcing: ${drift?.qualityFlags?.includes("DEMO_ENVIRONMENTAL_FORCING") ? "DEMO (simulated)" : "operational"}.`
    );
  }

  sectionHeader("RECOMMENDED ACTIONS", GREEN);

  const actions = report?.report?.recommendedActions ?? [
    "Human verification of SAR detection required",
    "Review additional satellite imagery if available",
    "Verify vessel identification against independent AIS records",
    "Cross-reference with coastal surveillance and VMS data",
    "Obtain real environmental data for production use",
    "Dispatch aerial surveillance if confidence exceeds threshold",
  ];

  actions.forEach((a) => bulletPoint(a, GREEN));

  sectionHeader("LIMITATIONS & DISCLAIMERS", AMBER);

  const limitations = report?.report?.limitations ?? [
    "This is an AI-generated investigation summary",
    "All vessel associations are POTENTIAL — human review required",
    "Confidence calibration status: NOT_CALIBRATED",
    "Environmental data is synthetic (DEMO mode)",
    "AIS gap analysis requires raw transmission-level data",
    "Backward drift model assumes simplified first-order physics",
  ];

  limitations.forEach((l) => bulletPoint(l, AMBER));

  // Final Human Review Required Banner
  y += 6;
  checkPageBreak(16);
  setFillColor([25, 15, 8]);
  setDrawColor(AMBER);
  doc.setLineWidth(0.5);
  doc.roundedRect(margin, y, contentWidth, 14, 2, 2, "FD");
  setColor(AMBER);
  doc.setFontSize(9);
  doc.setFont("helvetica", "bold");
  doc.text("⚠  HUMAN REVIEW REQUIRED", pageWidth / 2, y + 6, { align: "center" });
  setColor(TEXT_DIM);
  doc.setFontSize(7);
  doc.setFont("helvetica", "normal");
  doc.text(
    "This report is AI-generated from structured system evidence. Verify against source data before taking any action.",
    pageWidth / 2,
    y + 11,
    { align: "center" }
  );

  // Provenance footer
  y += 20;
  sectionHeader("PROVENANCE");
  labelValue("Report Generator:", "SAGAR WATCH v1.0 — Investigation Module");
  labelValue("Generated At:", now.toISOString());
  labelValue("Drift Provider:", String(drift?.provenance?.provider ?? "—"));
  labelValue("AIS Provider:", attribution?.provider ?? "—");
  if (report) {
    labelValue("Report ID:", report.reportId);
    labelValue("Evidence Version:", report.evidenceVersion);
  }

  drawFooter();

  // ═══════════════════════════════════════════════════════
  // SAVE
  // ═══════════════════════════════════════════════════════

  const filename = `SAGAR_WATCH_Investigation_${incidentId}_${now.toISOString().slice(0, 10)}.pdf`;
  doc.save(filename);

  return filename;
}
