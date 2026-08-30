"""Detection intelligence API response schemas.

Exposes Phase 8 intelligence layer as honest, labeled evidence.
Every field is explicitly marked as HEURISTIC, UNAVAILABLE, or NOT_CALIBRATED.
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


# ── Detection Intelligence ────────────────────────────────────────────────


class LookAlikeScreeningResponse(CamelModel):
    """Look-alike screening result. HEURISTIC — not ML."""

    status: str = "HEURISTIC"
    p_look_alike: float = 0.0
    penalty: float = 0.0
    texture_status: str = "UNAVAILABLE"
    explanation: str = ""


class EnvironmentalReliabilityResponse(CamelModel):
    """Environmental reliability assessment. HEURISTIC — literature-consistent thresholds."""

    status: str = "HEURISTIC"
    band: str = "UNKNOWN"
    wind_speed_knots: float = 0.0
    wave_height_m: float | None = None
    current_speed_ms: float = 0.0
    penalty: float = 0.0
    explanation: str = ""


class CalibrationResponse(CamelModel):
    """Confidence calibration status. NOT_CALIBRATED — fit() never called."""

    status: str = "NOT_CALIBRATED"
    calibrated_confidence: float | None = None
    calibration_shift: float = 0.0
    explanation: str = ""


class SmallDetectionResponse(CamelModel):
    """Small detection follow-up assessment. HEURISTIC — area-based thresholds."""

    status: str = "HEURISTIC"
    area_km2: float = 0.0
    pixel_count: int = 0
    is_sub_threshold: bool = False
    risk: str = "UNKNOWN"
    explanation: str = ""
    recommended_action: str = ""


class SeasonalPriorResponse(CamelModel):
    """Seasonal prior adjustment. HEURISTIC — author-assigned monthly factors."""

    status: str = "HEURISTIC"
    month: int = 0
    factor: float = 1.0
    adjustment: float = 0.0
    explanation: str = ""


class AISGapResponse(CamelModel):
    """AIS gap detection status. UNAVAILABLE — requires raw AIS data."""

    status: str = "RAW_AIS_REQUIRED"
    explanation: str = (
        "Raw AIS transmission-level observations are required for validated "
        "gap analysis. Current GFW presence data is aggregated and cannot "
        "support transmission-gap inference."
    )


class StaticSpacingResponse(CamelModel):
    """Static spacing detection status. UNAVAILABLE — requires raw AIS data."""

    status: str = "RAW_AIS_REQUIRED"
    explanation: str = (
        "Raw AIS transmission-level observations are required for validated "
        "static spacing analysis. Current GFW presence data is aggregated "
        "and cannot support interval regularity inference."
    )


class ConfidenceBreakdownResponse(CamelModel):
    """Full confidence breakdown with explicit component statuses."""

    raw_model_confidence: float = 0.0
    adjusted_confidence: float = 0.0
    confidence_band: str = "LOW"

    # Component penalties/shifts
    look_alike_penalty: float = 0.0
    environmental_penalty: float = 0.0
    small_detection_penalty: float = 0.0
    calibration_shift: float = 0.0
    seasonal_prior_adjustment: float = 0.0

    # Component statuses
    look_alike_status: str = "HEURISTIC"
    environmental_status: str = "HEURISTIC"
    calibration_status: str = "NOT_CALIBRATED"
    small_detection_status: str = "HEURISTIC"
    seasonal_prior_status: str = "HEURISTIC"

    # Explanations
    look_alike_explanation: str = ""
    environmental_explanation: str = ""
    small_detection_explanation: str = ""


class VesselEvidenceResponse(CamelModel):
    """Per-vessel evidence breakdown with availability status."""

    mmsi: str
    attribution_score: float = 0.0
    distance_score: float | None = None
    time_score: float | None = None
    track_consistency_score: float | None = None
    ais_gap_status: str = "RAW_AIS_REQUIRED"
    ais_gap_score: float | None = None
    static_spacing_status: str = "RAW_AIS_REQUIRED"
    static_spacing_score: float | None = None
    vessel_type_prior: float | None = None
    evidence_availability: str = "PARTIAL"


class DetectionIntelligenceResponse(CamelModel):
    """Complete detection intelligence — assembled from Phase 8 components."""

    # Confidence breakdown
    confidence_breakdown: ConfidenceBreakdownResponse

    # Component results
    look_alike_screening: LookAlikeScreeningResponse
    environmental_reliability: EnvironmentalReliabilityResponse
    small_detection: SmallDetectionResponse
    seasonal_prior: SeasonalPriorResponse
    calibration: CalibrationResponse

    # AIS availability
    ais_gap: AISGapResponse
    static_spacing: StaticSpacingResponse

    # Per-vessel evidence
    vessel_evidence: list[VesselEvidenceResponse] = []

    # Provenance
    provenance: dict[str, Any] = {}
