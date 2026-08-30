"""Drift API response schemas — wire-format compatible with SAGAR WATCH frontend."""

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


class DriftTrajectoryResponse(CamelModel):
    points: list[list[Any]]  # [[lat, lon, timestamp], ...]


class DriftResponse(CamelModel):
    incident_id: str
    method: str
    slick_latitude: float
    slick_longitude: float
    observation_time: str
    integration_hours: float
    timestep_minutes: float
    ensemble_size: int
    source_latitude: float
    source_longitude: float
    source_earliest: str
    source_latest: str
    uncertainty_km: float
    uncertainty_hours: float
    confidence: float
    quality_flags: list[str] = []
    source_points: list[list[float]] = []
    provenance: dict[str, Any] = {}
    analyzed_at: str | None = None


class InvestigationRequest(CamelModel):
    incident_id: str
    search_radius_km: float | None = None
    time_window_hours: float | None = None


class InvestigationResponse(CamelModel):
    incident_id: str
    drift: DriftResponse | None = None
    attribution: dict[str, Any] | None = None
    intelligence: dict[str, Any] | None = None  # Phase 8 detection intelligence
    environment: str = "DEMO"  # DEMO or REAL
    status: str = "completed"
