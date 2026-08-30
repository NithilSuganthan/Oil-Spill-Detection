from __future__ import annotations

from app.schemas.incident import CamelModel


class Totals(CamelModel):
    detections: int
    high_confidence: int
    total_area_km2: float
    scenes_processed: int


class DailyStat(CamelModel):
    date: str            # e.g. "25 Aug"
    detections: int
    high_confidence: int
    area_km2: float
    scenes_processed: int


class HourlyPoint(CamelModel):
    hour: str            # "00".."22"
    detections: int


class RegionStat(CamelModel):
    region: str
    detections: int
    area_km2: float


class ConfidenceBucket(CamelModel):
    bucket: str          # "50–60%", ...
    count: int


class AnalyticsSummaryResponse(CamelModel):
    totals: Totals
    daily: list[DailyStat]
    hourly: list[HourlyPoint]
    by_region: list[RegionStat]
    confidence_buckets: list[ConfidenceBucket]


class DetectionPoint(CamelModel):
    """Compact record for the /analytics/detections time-series."""

    incident_id: str
    detected_at: str
    confidence: float
    area_km2: float
    level: str
    region: str


class ServiceStatus(CamelModel):
    name: str
    status: str


class ActiveSceneInfo(CamelModel):
    id: str
    platform: str
    acquired_at: str | None = None
    processed_at: str | None = None
    status: str


class SystemStatusResponse(CamelModel):
    services: list[ServiceStatus]
    active_scene: ActiveSceneInfo | None = None
    database_backend: str = "in-memory-dev"
    model_adapter: str = "mock"
