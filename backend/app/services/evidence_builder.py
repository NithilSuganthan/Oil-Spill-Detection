"""Evidence builder — assembles InvestigationEvidence from pipeline results.

This service constructs the structured evidence object that is the ONLY
source of truth supplied to Groq. All scientific computation happens
before this builder is called.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.config import Settings
from app.domain.ais import CandidateVessel
from app.domain.entities import SpillIncident
from app.schemas.evidence import (
    AISEvidence,
    CalibrationEvidence,
    CandidateVesselEvidence,
    DetectionEvidence,
    DriftEvidence,
    EnvironmentalEvidence,
    HumanReviewEvidence,
    InvestigationEvidence,
    LookAlikeEvidence,
    ProvenanceEvidence,
    SeasonalPriorEvidence,
    SmallDetectionEvidence,
)
from app.schemas.intelligence import DetectionIntelligenceResponse
from app.services.drift_provider import DriftResult

logger = logging.getLogger(__name__)


def build_investigation_evidence(
    *,
    incident: SpillIncident,
    drift_result: DriftResult,
    candidates: list[CandidateVessel],
    intelligence: DetectionIntelligenceResponse,
    settings: Settings,
    environmental_provider_name: str = "unknown",
    ais_provider_name: str = "unknown",
) -> InvestigationEvidence:
    """Build structured investigation evidence from pipeline results.

    This is the ONLY source of truth supplied to Groq.
    All scientific computation happens before this function is called.
    """
    # Detection evidence
    detection = _build_detection_evidence(incident, intelligence, settings)

    # Look-alike screening evidence
    look_alike = _build_look_alike_evidence(intelligence)

    # Environmental evidence
    environment = _build_environmental_evidence(intelligence, environmental_provider_name)

    # Drift evidence
    drift = _build_drift_evidence(drift_result, environmental_provider_name)

    # AIS evidence
    ais = _build_ais_evidence(candidates, ais_provider_name, settings)

    # Candidate vessel evidence
    candidate_evidence = _build_candidate_evidence(candidates)

    # Small detection evidence
    small_detection = _build_small_detection_evidence(intelligence)

    # Seasonal prior evidence
    seasonal_prior = _build_seasonal_prior_evidence(intelligence)

    # Calibration evidence
    calibration = _build_calibration_evidence(intelligence)

    # Human review evidence
    human_review = HumanReviewEvidence()

    # Provenance evidence
    provenance = _build_provenance_evidence(settings, intelligence)

    return InvestigationEvidence(
        incident_id=incident.id,
        detection=detection,
        look_alike=look_alike,
        environment=environment,
        drift=drift,
        ais=ais,
        candidates=candidate_evidence,
        small_detection=small_detection,
        seasonal_prior=seasonal_prior,
        calibration=calibration,
        human_review=human_review,
        provenance=provenance,
        raw_model_confidence=intelligence.confidence_breakdown.raw_model_confidence,
        adjusted_confidence=intelligence.confidence_breakdown.adjusted_confidence,
        confidence_band=intelligence.confidence_breakdown.confidence_band,
        look_alike_penalty=intelligence.confidence_breakdown.look_alike_penalty,
        environmental_penalty=intelligence.confidence_breakdown.environmental_penalty,
        small_detection_penalty=intelligence.confidence_breakdown.small_detection_penalty,
        calibration_shift=intelligence.confidence_breakdown.calibration_shift,
        seasonal_prior_adjustment=intelligence.confidence_breakdown.seasonal_prior_adjustment,
    )


def _build_detection_evidence(
    incident: SpillIncident,
    intelligence: DetectionIntelligenceResponse,
    settings: Settings,
) -> DetectionEvidence:
    """Build detection evidence from incident and intelligence."""
    return DetectionEvidence(
        incident_id=incident.id,
        scene_id=incident.scene_id if hasattr(incident, "scene_id") else None,
        satellite="Sentinel-1",
        sar_model="TinyUNet",
        model_version=settings.model_version,
        raw_model_confidence=incident.confidence,
        adjusted_confidence=intelligence.confidence_breakdown.adjusted_confidence,
        calibration_status=intelligence.calibration.status,
        detection_area_km2=incident.area_km2,
        detection_centroid_lat=incident.centroid_lat,
        detection_centroid_lon=incident.centroid_lon,
        detected_at=incident.detected_at.isoformat() if incident.detected_at else None,
    )


def _build_look_alike_evidence(intelligence: DetectionIntelligenceResponse) -> LookAlikeEvidence:
    """Build look-alike screening evidence."""
    la = intelligence.look_alike_screening
    return LookAlikeEvidence(
        status=la.status,
        p_look_alike=la.p_look_alike,
        penalty=la.penalty,
        texture_status=la.texture_status,
        explanation=la.explanation,
    )


def _build_environmental_evidence(
    intelligence: DetectionIntelligenceResponse,
    provider_name: str,
) -> EnvironmentalEvidence:
    """Build environmental evidence."""
    env = intelligence.environmental_reliability
    return EnvironmentalEvidence(
        provider=provider_name,
        dataset="CMEMS+ERA5" if provider_name == "real" else "deterministic_synthetic",
        environment_status="REAL" if provider_name == "real" else "DEMO",
        wind_speed_knots=env.wind_speed_knots,
        wave_height_m=env.wave_height_m,
        current_speed_ms=env.current_speed_ms,
        reliability_band=env.band,
        penalty=env.penalty,
        spatial_resolution_deg=0.25 if provider_name == "real" else None,
        temporal_resolution_hours=1.0 if provider_name == "real" else None,
        explanation=env.explanation,
    )


def _build_drift_evidence(
    drift_result: DriftResult,
    environmental_provider_name: str,
) -> DriftEvidence:
    """Build drift evidence."""
    return DriftEvidence(
        method=drift_result.method,
        source_latitude=drift_result.source_latitude,
        source_longitude=drift_result.source_longitude,
        uncertainty_km=drift_result.uncertainty_km,
        uncertainty_hours=drift_result.uncertainty_hours,
        ensemble_size=drift_result.ensemble_size,
        time_window_hours=drift_result.integration_hours,
        confidence=drift_result.confidence,
        quality_flags=drift_result.quality_flags,
        environmental_provider=environmental_provider_name,
    )


def _build_ais_evidence(
    candidates: list[CandidateVessel],
    provider_name: str,
    settings: Settings,
) -> AISEvidence:
    """Build AIS evidence."""
    return AISEvidence(
        provider=provider_name,
        dataset="public-global-presence:latest" if provider_name == "gfw" else "deterministic_mock",
        data_availability="AVAILABLE" if provider_name == "gfw" else "DEMO",
        observation_count=sum(c.number_of_observations for c in candidates),
        vessel_count=len(candidates),
        search_radius_km=settings.ais_search_radius_km,
        time_window_hours=settings.ais_time_window_hours,
    )


def _build_candidate_evidence(
    candidates: list[CandidateVessel],
) -> list[CandidateVesselEvidence]:
    """Build per-vessel candidate evidence."""
    evidence = []
    for c in candidates:
        score_components = {}
        if c.score_components:
            score_components = {
                "distance": c.score_components.get("distance", 0.0),
                "time": c.score_components.get("time", 0.0),
                "trackConsistency": c.score_components.get("trackConsistency", 0.0),
            }

        evidence.append(CandidateVesselEvidence(
            mmsi=c.mmsi,
            vessel_name=c.vessel_name,
            vessel_type=c.vessel_type,
            distance_km=c.closest_distance_km,
            time_difference_minutes=c.closest_time_difference_minutes or 0.0,
            track_consistency=score_components.get("trackConsistency", 0.0),
            attribution_score=c.attribution_score,
            score_components=score_components,
            ais_gap_status="RAW_AIS_REQUIRED",
            static_spacing_status="RAW_AIS_REQUIRED",
            vessel_type_prior=None,
            evidence_availability="PARTIAL",
        ))
    return evidence


def _build_small_detection_evidence(
    intelligence: DetectionIntelligenceResponse,
) -> SmallDetectionEvidence:
    """Build small detection evidence."""
    sd = intelligence.small_detection
    return SmallDetectionEvidence(
        area_km2=sd.area_km2,
        pixel_count=sd.pixel_count,
        is_sub_threshold=sd.is_sub_threshold,
        risk=sd.risk,
        explanation=sd.explanation,
        recommended_action=sd.recommended_action,
    )


def _build_seasonal_prior_evidence(
    intelligence: DetectionIntelligenceResponse,
) -> SeasonalPriorEvidence:
    """Build seasonal prior evidence."""
    sp = intelligence.seasonal_prior
    return SeasonalPriorEvidence(
        status=sp.status,
        month=sp.month,
        factor=sp.factor,
        adjustment=sp.adjustment,
        explanation=sp.explanation,
    )


def _build_calibration_evidence(
    intelligence: DetectionIntelligenceResponse,
) -> CalibrationEvidence:
    """Build calibration evidence."""
    cal = intelligence.calibration
    return CalibrationEvidence(
        status=cal.status,
        calibrated_confidence=cal.calibrated_confidence,
        calibration_shift=cal.calibration_shift,
        explanation=cal.explanation,
    )


def _build_provenance_evidence(
    settings: Settings,
    intelligence: DetectionIntelligenceResponse,
) -> ProvenanceEvidence:
    """Build provenance evidence."""
    prov = intelligence.provenance
    return ProvenanceEvidence(
        model_version=prov.get("model_version", ""),
        pipeline_version=prov.get("detection_version", ""),
        environment_version=prov.get("environment_provider", ""),
        ais_version=prov.get("ais_provider", ""),
        attribution_version=prov.get("attribution_version", ""),
        intelligence_version="1.0-phase8",
    )
