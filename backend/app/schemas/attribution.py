"""Attribution API response schemas — wire-format compatible with SAGAR WATCH frontend.

Uses camelCase aliases matching the frontend TypeScript types.
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


class SearchWindowResponse(CamelModel):
    start: str
    end: str
    center_lat: float
    center_lon: float
    radius_km: float
    time_window_hours: float


class ScoreComponentsResponse(CamelModel):
    distance: float
    time: float
    track_consistency: float


class CandidateVesselResponse(CamelModel):
    mmsi: str
    vessel_name: str | None = None
    imo: str | None = None
    vessel_type: str | None = None
    flag: str | None = None
    number_of_observations: int = 0
    closest_distance_km: float = 0.0
    closest_timestamp: str | None = None
    closest_time_difference_minutes: float | None = None
    mean_distance_km: float = 0.0
    first_observation: str | None = None
    last_observation: str | None = None
    attribution_score: float = 0.0
    score_components: ScoreComponentsResponse | None = None
    quality_flags: list[str] = []
    human_review_required: bool = True
    # Phase 8: Intelligence signals
    gap_signals: list[dict[str, Any]] = []
    static_spacing: dict[str, Any] | None = None


class ConfidenceBreakdownResponse(CamelModel):
    raw_model_confidence: float = 0.0
    look_alike_penalty: float = 0.0
    environmental_penalty: float = 0.0
    small_detection_penalty: float = 0.0
    calibration_shift: float = 0.0
    seasonal_prior_adjustment: float = 0.0
    adjusted_confidence: float = 0.0
    confidence_band: str = "LOW"
    explanations: dict[str, str] = {}


class SmallDetectionResponse(CamelModel):
    area_km2: float = 0.0
    pixel_count: int = 0
    is_sub_threshold: bool = False
    false_positive_risk: str = "LOW"
    explanation: str = ""
    recommended_action: str = ""


class AttributionResponse(CamelModel):
    incident_id: str
    search_window: SearchWindowResponse
    coverage_known: bool = True
    provider: str = "mock"
    dataset: str = ""
    candidate_count: int = 0
    candidates: list[CandidateVesselResponse] = []
    total_observations: int = 0
    analyzed_at: str | None = None
    provenance: dict[str, Any] = {}
    # Phase 8: Intelligence
    intelligence: dict[str, Any] | None = None
    confidence_breakdown: ConfidenceBreakdownResponse | None = None
    small_detection: SmallDetectionResponse | None = None
    environmental_band: str | None = None
    seasonal_adjustment: float = 0.0


class AttributionRequest(CamelModel):
    incident_id: str
    latitude: float | None = None
    longitude: float | None = None
    observation_time: str | None = None
    search_radius_km: float | None = None
    time_window_hours: float | None = None
