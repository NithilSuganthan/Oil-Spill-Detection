"""Stable, JSON-serialisable contracts for frontend/service integration."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class QualityFlag:
    code: str
    level: str  # info | warning | critical
    message: str


@dataclass(slots=True)
class SlickGeometry:
    polygon_lonlat: list[list[float]]
    area_km2: float
    pixel_area: int
    centroid_lonlat: list[float]


@dataclass(slots=True)
class DetectionResult:
    scene_id: str
    acquired_at: str
    potential_slicks: list[SlickGeometry]
    detection_confidence: float
    look_alike_risk: float
    quality_flags: list[QualityFlag]
    human_review_required: bool = True
    model_version: str = "untrained-baseline"
    estimated_age_hours: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HindcastParticle:
    release_lon: float
    release_lat: float
    release_time: str
    final_distance_km: float
    score: float


@dataclass(slots=True)
class HindcastResult:
    observation_time: str
    observation_lonlat: list[float]
    source_centroid_lonlat: list[float] | None
    source_time_window: list[str] | None
    particles: list[HindcastParticle]
    forcing_summary: dict[str, Any]
    uncertainty_km: float | None
    quality_flags: list[QualityFlag]
    estimated_age_hours: float | None = None
    human_review_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScoreComponent:
    name: str
    value: float
    weight: float
    explanation: str


@dataclass(slots=True)
class VesselCandidate:
    mmsi: str
    rank: int
    suspicion_score: float
    score_components: list[ScoreComponent]
    last_known_lonlat: list[float] | None
    vessel_type: str | None
    ais_gap_hours: float | None
    evidence_status: str = "potential source — human review required"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
