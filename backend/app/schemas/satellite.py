from __future__ import annotations

from app.schemas.incident import CamelModel


class BoundingBox(CamelModel):
    west: float
    south: float
    east: float
    north: float


class SceneResponse(CamelModel):
    """Mirrors the frontend `SatelliteScene` interface (plus extra backend fields)."""

    id: str
    product_id: str
    platform: str
    sensor: str = "SAR C-band"
    acquisition_mode: str = "IW"
    polarisation: str = "VV + VH"
    acquired_at: str | None = None
    processed_at: str | None = None
    footprint: BoundingBox | None = None
    status: str = "queued"
    image_path: str | None = None
    is_demo: bool = False

    # ---- catalogue ingestion extras (Phase 2; additive, UI-safe) --------
    product_name: str | None = None
    source_provider: str = "mock"
    orbit_state: str | None = None
    absolute_orbit: int | None = None
    relative_orbit: int | None = None
    file_size_bytes: int | None = None
    product_type: str | None = None
    pipeline_state: str | None = None
    has_preview: bool = False
