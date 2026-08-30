"""Investigation evidence schema — structured evidence for Groq reporting.

This is the ONLY source of truth supplied to Groq.
All scientific computation happens before this object is constructed.
Groq receives this evidence and produces a human-readable report.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


def to_camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(w.capitalize() for w in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class DetectionEvidence(CamelModel):
    """SAR detection evidence."""
    incident_id: str
    scene_id: str | None = None
    satellite: str | None = None
    sar_model: str | None = None
    model_version: str | None = None
    raw_model_confidence: float = 0.0
    adjusted_confidence: float = 0.0
    calibration_status: str = "NOT_CALIBRATED"
    detection_area_km2: float = 0.0
    detection_centroid_lat: float = 0.0
    detection_centroid_lon: float = 0.0
    detected_at: str | None = None


class LookAlikeEvidence(CamelModel):
    """Look-alike screening evidence."""
    status: str = "UNAVAILABLE"
    p_look_alike: float = 0.0
    penalty: float = 0.0
    texture_status: str = "UNAVAILABLE"
    explanation: str = ""


class EnvironmentalEvidence(CamelModel):
    """Environmental forcing evidence."""
    provider: str = "unknown"
    dataset: str = ""
    environment_status: str = "UNKNOWN"
    wind_speed_knots: float | None = None
    wave_height_m: float | None = None
    current_speed_ms: float | None = None
    reliability_band: str = "UNKNOWN"
    penalty: float = 0.0
    spatial_resolution_deg: float | None = None
    temporal_resolution_hours: float | None = None
    explanation: str = ""


class DriftEvidence(CamelModel):
    """Drift hindcast evidence."""
    method: str = ""
    source_latitude: float = 0.0
    source_longitude: float = 0.0
    uncertainty_km: float = 0.0
    uncertainty_hours: float = 0.0
    ensemble_size: int = 0
    time_window_hours: float = 0.0
    confidence: float = 0.0
    quality_flags: list[str] = []
    environmental_provider: str = "unknown"


class AISEvidence(CamelModel):
    """AIS vessel correlation evidence."""
    provider: str = "unknown"
    dataset: str = ""
    data_availability: str = "UNKNOWN"
    observation_count: int = 0
    vessel_count: int = 0
    search_radius_km: float = 0.0
    time_window_hours: float = 0.0


class CandidateVesselEvidence(CamelModel):
    """Per-vessel candidate evidence."""
    mmsi: str
    vessel_name: str | None = None
    vessel_type: str | None = None
    distance_km: float = 0.0
    time_difference_minutes: float = 0.0
    track_consistency: float = 0.0
    attribution_score: float = 0.0
    score_components: dict[str, float] = {}
    ais_gap_status: str = "UNAVAILABLE"
    static_spacing_status: str = "UNAVAILABLE"
    vessel_type_prior: float | None = None
    evidence_availability: str = "UNAVAILABLE"


class SmallDetectionEvidence(CamelModel):
    """Small detection assessment evidence."""
    area_km2: float = 0.0
    pixel_count: int = 0
    is_sub_threshold: bool = False
    risk: str = "LOW"
    explanation: str = ""
    recommended_action: str = ""


class SeasonalPriorEvidence(CamelModel):
    """Seasonal prior evidence."""
    status: str = "UNAVAILABLE"
    month: int = 0
    factor: float = 1.0
    adjustment: float = 0.0
    explanation: str = ""


class CalibrationEvidence(CamelModel):
    """Confidence calibration evidence."""
    status: str = "NOT_CALIBRATED"
    calibrated_confidence: float | None = None
    calibration_shift: float = 0.0
    explanation: str = ""


class HumanReviewEvidence(CamelModel):
    """Human review status evidence."""
    review_status: str = "NOT_REVIEWED"
    review_notes: str | None = None


class ProvenanceEvidence(CamelModel):
    """Pipeline provenance evidence."""
    model_version: str = ""
    pipeline_version: str = ""
    environment_version: str = ""
    ais_version: str = ""
    attribution_version: str = ""
    intelligence_version: str = ""


class InvestigationEvidence(CamelModel):
    """Complete structured investigation evidence.

    This is the ONLY source of truth supplied to Groq.
    All scientific computation happens before this object is constructed.
    Groq receives this evidence and produces a human-readable report.
    """
    incident_id: str
    detection: DetectionEvidence
    look_alike: LookAlikeEvidence
    environment: EnvironmentalEvidence
    drift: DriftEvidence
    ais: AISEvidence
    candidates: list[CandidateVesselEvidence] = []
    small_detection: SmallDetectionEvidence
    seasonal_prior: SeasonalPriorEvidence
    calibration: CalibrationEvidence
    human_review: HumanReviewEvidence
    provenance: ProvenanceEvidence
    # Confidence breakdown
    raw_model_confidence: float = 0.0
    adjusted_confidence: float = 0.0
    confidence_band: str = "LOW"
    look_alike_penalty: float = 0.0
    environmental_penalty: float = 0.0
    small_detection_penalty: float = 0.0
    calibration_shift: float = 0.0
    seasonal_prior_adjustment: float = 0.0
