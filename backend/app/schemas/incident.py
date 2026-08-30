"""Response schemas — wire-format compatible with the SAGAR WATCH frontend.

The frontend TypeScript types (src/lib/types.ts) use camelCase, e.g.
`areaKm2`, `perimeterKm2`, `detectedAt`, `locationDescription`. These
Pydantic models serialize with those exact aliases so the UI needs zero
changes when switching from the mock API to FastAPI.
"""

from __future__ import annotations

from typing import Any, Literal

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


class Centroid(CamelModel):
    lat: float
    lon: float


class IncidentResponse(CamelModel):
    """Mirrors the frontend `Incident` interface."""

    id: str
    scene_id: str
    confidence: float
    area_km2: float
    perimeter_km2: float  # NOTE: kept for frontend compatibility
    centroid: Centroid
    geometry: dict[str, Any]          # GeoJSON Polygon (EPSG:4326)
    detected_at: str                  # ISO-8601 with IST offset
    region: str
    location_description: str
    satellite: str
    model: str
    model_version: str
    status: str
    level: Literal["HIGH", "MEDIUM", "LOW"]
    wind_speed_kts: float | None = None
    estimated_volume_tons: float | None = None
    is_demo: bool = False
