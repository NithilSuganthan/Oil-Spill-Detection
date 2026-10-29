"""Alert schemas — Operational alert data models for SAGAR WATCH.

Alerts represent operational priority items generated ONLY from analyzed model detections
that meet or exceed the HIGH / CRITICAL criticality threshold.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict

from app.schemas.criticality import CriticalityFactorResponse


def to_camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(w.capitalize() for w in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


AlertStatus = Literal["NEW", "REVIEWING", "RESOLVED"]
AlertSeverity = Literal["CRITICAL", "HIGH", "MODERATE", "LOW"]


class AlertStatusUpdate(CamelModel):
    """Schema for updating alert status."""
    status: AlertStatus


class AlertResponse(CamelModel):
    """Operational Alert data model."""
    alert_id: str
    incident_id: str
    severity: AlertSeverity
    criticality_score: int
    status: AlertStatus
    title: str
    summary: str
    created_at: str
    detection_time: str
    latitude: float
    longitude: float
    area_km2: float
    model_confidence: float
    location_description: str
    action: str
    factors: list[CriticalityFactorResponse]
    geometry: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None


class AlertSummaryResponse(CamelModel):
    """Counts of alerts grouped by severity and status."""
    critical: int
    high: int
    new: int
    total: int


class AlertAnalysisResult(CamelModel):
    """Result of analyzing an incident for alert creation."""
    created: bool
    reused: bool = False
    alert: AlertResponse | None = None
    criticality_score: int
    criticality_level: str
    reason: str
