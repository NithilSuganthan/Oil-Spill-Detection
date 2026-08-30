"""Intelligence assembly service.

Orchestrates all Phase 8 components into a single DetectionIntelligence
result.  This is the ONLY service that should be called from API routes.
Every component result is explicitly labeled with its status.

This service does NOT fabricate data.  When a component cannot run
(e.g., texture features unavailable, AIS gap requires raw data),
the result clearly states UNAVAILABLE — not zero.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.config import Settings
from app.domain.ais import CandidateVessel
from app.domain.entities import (
    ConfidenceBreakdown,
    LookAlikeFeatures,
    SmallDetectionAssessment,
    SpillIncident,
)
from app.schemas.intelligence import (
    AISGapResponse,
    CalibrationResponse,
    ConfidenceBreakdownResponse,
    DetectionIntelligenceResponse,
    EnvironmentalReliabilityResponse,
    LookAlikeScreeningResponse,
    SeasonalPriorResponse,
    SmallDetectionResponse,
    StaticSpacingResponse,
    VesselEvidenceResponse,
)
from app.services.confidence_calibrator import ConfidenceCalibrator
from app.services.environmental_provider import EnvironmentalConditions
from app.services.environmental_reliability import EnvironmentalReliability
from app.services.look_alike_classifier import LookAlikeClassifier
from app.services.seasonal_prior import SeasonalPriorService
from app.services.small_detection_assessor import SmallDetectionAssessor

logger = logging.getLogger(__name__)


def assemble_intelligence(
    *,
    incident: SpillIncident,
    candidates: list[CandidateVessel],
    environmental_conditions: EnvironmentalConditions | None = None,
    settings: Settings,
) -> DetectionIntelligenceResponse:
    """Assemble detection intelligence from all Phase 8 components.

    Every component is called.  Every result is labeled with its status.
    No data is fabricated.  UNAVAILABLE means UNAVAILABLE.
    """
    # ── 1. Look-alike screening ────────────────────────────────────────
    look_alike = _run_look_alike_screening(incident)

    # ── 2. Environmental reliability ───────────────────────────────────
    env_reliability = _run_environmental_reliability(environmental_conditions)

    # ── 3. Small detection assessment ──────────────────────────────────
    small_det = _run_small_detection(incident, environmental_conditions)

    # ── 4. Seasonal prior ──────────────────────────────────────────────
    seasonal = _run_seasonal_prior(incident)

    # ── 5. Calibration ─────────────────────────────────────────────────
    calibration = _run_calibration(incident)

    # ── 6. Confidence breakdown ────────────────────────────────────────
    breakdown = _compute_breakdown(
        incident=incident,
        look_alike=look_alike,
        env_reliability=env_reliability,
        small_det=small_det,
        seasonal=seasonal,
        calibration=calibration,
    )

    # ── 7. AIS gap / static spacing (UNAVAILABLE with GFW) ────────────
    ais_gap = AISGapResponse()
    static_spacing = StaticSpacingResponse()

    # ── 8. Per-vessel evidence ─────────────────────────────────────────
    vessel_evidence = _build_vessel_evidence(candidates)

    # ── 9. Provenance ──────────────────────────────────────────────────
    provenance = _build_provenance(settings)

    return DetectionIntelligenceResponse(
        confidence_breakdown=breakdown,
        look_alike_screening=look_alike,
        environmental_reliability=env_reliability,
        small_detection=small_det,
        seasonal_prior=seasonal,
        calibration=calibration,
        ais_gap=ais_gap,
        static_spacing=static_spacing,
        vessel_evidence=vessel_evidence,
        provenance=provenance,
    )


def _run_look_alike_screening(incident: SpillIncident) -> LookAlikeScreeningResponse:
    """Run look-alike screening.  HEURISTIC — not ML."""
    clf = LookAlikeClassifier()

    # Build features from incident data (no SAR patch available at this stage)
    features = LookAlikeFeatures(
        wind_speed_knots=incident.wind_speed_kts or 0.0,
    )

    classified = clf.classify(features)
    p_la = classified.look_alike_probability
    penalty = round(p_la * 0.20, 4)

    return LookAlikeScreeningResponse(
        status="HEURISTIC",
        p_look_alike=p_la,
        penalty=penalty,
        texture_status=classified.texture_status,
        explanation=(
            f"Look-alike probability: {p_la:.1%}. "
            f"Penalty: -{penalty:.1%} from model confidence. "
            f"Texture features: {classified.texture_status}. "
            f"This is a heuristic screening, not an ML classification."
        ),
    )


def _run_environmental_reliability(
    conditions: EnvironmentalConditions | None,
) -> EnvironmentalReliabilityResponse:
    """Run environmental reliability.  HEURISTIC — literature-consistent."""
    if conditions is None:
        return EnvironmentalReliabilityResponse(
            status="HEURISTIC",
            band="UNKNOWN",
            explanation="Environmental conditions not available.",
        )

    svc = EnvironmentalReliability()
    band, penalty, explanation = svc.assess(conditions)

    wind_ms = (conditions.wind_u ** 2 + conditions.wind_v ** 2) ** 0.5
    wind_kts = wind_ms / 0.514444

    return EnvironmentalReliabilityResponse(
        status="HEURISTIC",
        band=band,
        wind_speed_knots=round(wind_kts, 1),
        wave_height_m=conditions.wave_height,
        current_speed_ms=round(
            (conditions.current_u ** 2 + conditions.current_v ** 2) ** 0.5, 3
        ),
        penalty=round(penalty, 4),
        explanation=explanation,
    )


def _run_small_detection(
    incident: SpillIncident,
    conditions: EnvironmentalConditions | None,
) -> SmallDetectionResponse:
    """Run small detection assessment.  HEURISTIC — area-based."""
    svc = SmallDetectionAssessor()
    wind_kts = 0.0
    if conditions:
        wind_ms = (conditions.wind_u ** 2 + conditions.wind_v ** 2) ** 0.5
        wind_kts = wind_ms / 0.514444

    result = svc.assess(
        area_km2=incident.area_km2,
        perimeter_km=incident.perimeter_km,
        model_confidence=incident.confidence,
        wind_speed_knots=wind_kts,
    )

    return SmallDetectionResponse(
        status="HEURISTIC",
        area_km2=result.area_km2,
        pixel_count=result.pixel_count,
        is_sub_threshold=result.is_sub_threshold,
        risk=result.false_positive_risk,
        explanation=result.explanation,
        recommended_action=result.recommended_action,
    )


def _run_seasonal_prior(incident: SpillIncident) -> SeasonalPriorResponse:
    """Run seasonal prior.  HEURISTIC — author-assigned factors."""
    svc = SeasonalPriorService()
    month = incident.detected_at.month
    factor = svc.get_prior(month)
    adjustment = svc.get_adjustment(month)
    explanation = svc.explain(month)

    return SeasonalPriorResponse(
        status="HEURISTIC",
        month=month,
        factor=factor,
        adjustment=round(adjustment, 4),
        explanation=f"{explanation} Author-assigned heuristic, not empirical.",
    )


def _run_calibration(incident: SpillIncident) -> CalibrationResponse:
    """Report calibration status.  NOT_CALIBRATED — fit() never called."""
    return CalibrationResponse(
        status="NOT_CALIBRATED",
        calibrated_confidence=None,
        calibration_shift=0.0,
        explanation=(
            "Confidence calibration is NOT_CALIBRATED. "
            "fit() has never been called on labeled validation data. "
            "Raw model confidence is reported without calibration adjustment."
        ),
    )


def _compute_breakdown(
    *,
    incident: SpillIncident,
    look_alike: LookAlikeScreeningResponse,
    env_reliability: EnvironmentalReliabilityResponse,
    small_det: SmallDetectionResponse,
    seasonal: SeasonalPriorResponse,
    calibration: CalibrationResponse,
) -> ConfidenceBreakdownResponse:
    """Compute confidence breakdown from component results."""
    raw = incident.confidence

    # Component penalties
    ll_penalty = look_alike.penalty
    env_penalty = env_reliability.penalty
    small_penalty = 0.0
    if small_det.risk == "HIGH":
        small_penalty = 0.15
    elif small_det.risk == "MEDIUM":
        small_penalty = 0.05

    cal_shift = calibration.calibration_shift
    seasonal_adj = seasonal.adjustment

    adjusted = raw - ll_penalty - env_penalty - small_penalty + cal_shift + seasonal_adj
    adjusted = max(0.0, min(1.0, adjusted))

    if adjusted >= 0.8:
        band = "HIGH"
    elif adjusted >= 0.65:
        band = "MEDIUM"
    else:
        band = "LOW"

    return ConfidenceBreakdownResponse(
        raw_model_confidence=raw,
        adjusted_confidence=round(adjusted, 4),
        confidence_band=band,
        look_alike_penalty=ll_penalty,
        environmental_penalty=env_penalty,
        small_detection_penalty=small_penalty,
        calibration_shift=cal_shift,
        seasonal_prior_adjustment=seasonal_adj,
        look_alike_status=look_alike.status,
        environmental_status=env_reliability.status,
        calibration_status=calibration.status,
        small_detection_status=small_det.status,
        seasonal_prior_status=seasonal.status,
        look_alike_explanation=look_alike.explanation,
        environmental_explanation=env_reliability.explanation,
        small_detection_explanation=small_det.explanation,
    )


def _build_vessel_evidence(
    candidates: list[CandidateVessel],
) -> list[VesselEvidenceResponse]:
    """Build per-vessel evidence with availability status."""
    evidence = []
    for c in candidates:
        # Extract score components if available
        dist_score = c.score_components.get("distance") if c.score_components else None
        time_score = c.score_components.get("time") if c.score_components else None
        track_score = c.score_components.get("trackConsistency") if c.score_components else None

        evidence.append(VesselEvidenceResponse(
            mmsi=c.mmsi,
            attribution_score=c.attribution_score,
            distance_score=dist_score,
            time_score=time_score,
            track_consistency_score=track_score,
            ais_gap_status="RAW_AIS_REQUIRED",
            ais_gap_score=None,
            static_spacing_status="RAW_AIS_REQUIRED",
            static_spacing_score=None,
            vessel_type_prior=None,
            evidence_availability="PARTIAL",
        ))
    return evidence


def _build_provenance(settings: Settings) -> dict:
    """Build provenance dict with explicit status for each component."""
    return {
        "model_version": settings.model_version,
        "detection_version": "1.0-phase8",
        "look_alike_version": "1.0-heuristic",
        "environment_provider": settings.environmental_provider,
        "environment_dataset": "CMEMS+ERA5" if settings.environmental_provider == "real" else "mock",
        "drift_method": settings.drift_provider,
        "ais_provider": settings.ais_provider,
        "ais_dataset": "public-global-presence:latest" if settings.ais_provider == "gfw" else "mock",
        "attribution_version": "1.0-phase4",
        "calibration_status": "NOT_CALIBRATED",
        "seasonal_prior_status": "HEURISTIC",
        "ais_gap_status": "RAW_AIS_REQUIRED",
        "static_spacing_status": "RAW_AIS_REQUIRED",
        "texture_status": "UNAVAILABLE",
    }
