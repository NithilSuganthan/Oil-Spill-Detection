"""Mock report provider — deterministic report generation for testing.

Clearly labeled DEMO. Never fabricate real investigation reports.
"""

from __future__ import annotations

import json
from typing import Any

from app.services.report_provider import GroqReportProvider, InvestigationReport


class MockReportProvider(GroqReportProvider):
    """Deterministic mock report provider for development/testing."""

    name = "mock"

    def generate_report(self, evidence_json: dict[str, Any]) -> InvestigationReport:
        """Generate a deterministic mock report from evidence."""
        incident_id = evidence_json.get("incidentId", "unknown")
        detection = evidence_json.get("detection", {})
        candidates = evidence_json.get("candidates", [])
        environment = evidence_json.get("environment", {})
        drift = evidence_json.get("drift", {})

        raw_conf = detection.get("rawModelConfidence", 0.0)
        adj_conf = detection.get("adjustedConfidence", 0.0)
        area_km2 = detection.get("detectionAreaKm2", 0.0)

        # Executive summary
        exec_summary = (
            f"Investigation of incident {incident_id} identified a detection "
            f"with raw model confidence {raw_conf:.1%} (adjusted: {adj_conf:.1%}). "
            f"The detected area covers {area_km2:.2f} km². "
        )
        if candidates:
            top = candidates[0]
            exec_summary += (
                f"The highest-ranked potential source vessel is "
                f"{top.get('vesselName', 'unknown')} (MMSI {top.get('mmsi', 'unknown')}) "
                f"with an attribution score of {top.get('attributionScore', 0.0):.3f}."
            )
        else:
            exec_summary += "No candidate vessels were identified in the search area."

        # Detection assessment
        detection_assessment = (
            f"The SAR detection was made by {detection.get('sarModel', 'unknown')} "
            f"(version {detection.get('modelVersion', 'unknown')}). "
            f"Raw confidence: {raw_conf:.1%}. Adjusted confidence: {adj_conf:.1%}. "
            f"Calibration status: {detection.get('calibrationStatus', 'NOT_CALIBRATED')}. "
            f"This is a model prediction requiring human verification."
        )

        # Environment assessment
        env_status = environment.get("environmentStatus", "UNKNOWN")
        env_assessment = (
            f"Environmental data provider: {environment.get('provider', 'unknown')}. "
            f"Status: {env_status}. "
            f"Reliability band: {environment.get('reliabilityBand', 'UNKNOWN')}. "
        )
        if env_status == "DEMO":
            env_assessment += "WARNING: Environmental data is synthetic (DEMO mode)."
        elif env_status == "REAL":
            env_assessment += "Environmental data is from real operational sources."

        # Drift assessment
        drift_assessment = (
            f"Drift hindcast method: {drift.get('method', 'unknown')}. "
            f"Estimated source: ({drift.get('sourceLatitude', 0.0):.4f}, "
            f"{drift.get('sourceLongitude', 0.0):.4f}). "
            f"Uncertainty: {drift.get('uncertaintyKm', 0.0):.1f} km. "
            f"Ensemble size: {drift.get('ensembleSize', 0)}."
        )

        # AIS assessment
        ais = evidence_json.get("ais", {})
        ais_assessment = (
            f"AIS provider: {ais.get('provider', 'unknown')}. "
            f"Data availability: {ais.get('dataAvailability', 'UNKNOWN')}. "
            f"Vessels found: {ais.get('vesselCount', 0)}. "
            f"Observations: {ais.get('observationCount', 0)}."
        )

        # Candidate assessments
        candidate_assessments = []
        for c in candidates:
            assessment = {
                "mmsi": c.get("mmsi", "unknown"),
                "vesselName": c.get("vesselName", "unknown"),
                "attributionScore": c.get("attributionScore", 0.0),
                "distanceKm": c.get("distanceKm", 0.0),
                "timeDifferenceMinutes": c.get("timeDifferenceMinutes", 0.0),
                "explanation": (
                    f"Vessel ranked with score {c.get('attributionScore', 0.0):.3f} "
                    f"based on distance ({c.get('distanceKm', 0.0):.1f} km), "
                    f"time ({c.get('timeDifferenceMinutes', 0.0):.0f} min), "
                    f"and track consistency ({c.get('trackConsistency', 0.0):.3f})."
                ),
            }
            candidate_assessments.append(assessment)

        # Uncertainty
        uncertainty = (
            f"Source uncertainty: {drift.get('uncertaintyKm', 0.0):.1f} km spatial, "
            f"{drift.get('uncertaintyHours', 0.0):.1f} hours temporal. "
            f"Confidence: {drift.get('confidence', 0.0):.1%}. "
            f"Environmental forcing: {environment.get('environmentStatus', 'UNKNOWN')}."
        )

        # Recommended actions
        recommended_actions = [
            "Human verification of SAR detection required",
            "Review additional satellite imagery if available",
            "Verify vessel identification against AIS records",
        ]
        if env_status == "DEMO":
            recommended_actions.append("Obtain real environmental data for production use")
        if not candidates:
            recommended_actions.append("Expand search radius or time window")

        # Limitations
        limitations = [
            "This is an AI-generated summary based on system evidence",
            "All vessel associations are potential — human review required",
            "Confidence calibration is NOT_CALIBRATED",
        ]
        if env_status == "DEMO":
            limitations.append("Environmental data is synthetic (DEMO mode)")
        limitations.append("AIS gap analysis requires raw transmission-level data")

        return InvestigationReport(
            title=f"Investigation Report — {incident_id}",
            executive_summary=exec_summary,
            detection_assessment=detection_assessment,
            environment_assessment=env_assessment,
            drift_assessment=drift_assessment,
            ais_assessment=ais_assessment,
            candidate_assessments=candidate_assessments,
            uncertainty=uncertainty,
            recommended_actions=recommended_actions,
            limitations=limitations,
            human_review_required=True,
        )
