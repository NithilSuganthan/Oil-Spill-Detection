"""SQLAlchemy ORM models for PostgreSQL + PostGIS.

Used only when DATABASE_URL points at Postgres. Geometry columns are
GeoAlchemy2 Geometry types with GiST spatial indexes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class SatelliteSceneRow(Base):
    __tablename__ = "satellite_scenes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # product-style scene id
    product_id: Mapped[str] = mapped_column(String(128))
    product_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    satellite: Mapped[str] = mapped_column(String(32))
    sensor: Mapped[str] = mapped_column(String(32), default="SAR C-band")
    acquisition_mode: Mapped[str] = mapped_column(String(8), default="IW")
    polarisation: Mapped[str] = mapped_column(String(16), default="VV + VH")
    acquisition_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    # ---- catalogue ingestion metadata (Phase 2) --------------------------
    source_provider: Mapped[str | None] = mapped_column(String(32), nullable=True, default="mock")
    orbit_state: Mapped[str | None] = mapped_column(String(16), nullable=True)
    absolute_orbit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relative_orbit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    download_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    preview_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    pipeline_state: Mapped[str | None] = mapped_column(String(24), nullable=True)
    metadata_extra_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # footprint polygon (EPSG:4326), indexed for bbox queries
    footprint: Mapped[object] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True), nullable=True
    )


class SpillIncidentRow(Base):
    __tablename__ = "spill_incidents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # e.g. IN-250825-001
    scene_id: Mapped[str] = mapped_column(ForeignKey("satellite_scenes.id"), index=True)
    confidence: Mapped[float] = mapped_column(Float)               # model confidence 0..1
    area_km2: Mapped[float] = mapped_column(Float)                 # geodesic area
    perimeter_km: Mapped[float] = mapped_column(Float)             # geodesic perimeter
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    region: Mapped[str] = mapped_column(String(48), index=True)
    location_description: Mapped[str] = mapped_column(Text)
    satellite: Mapped[str] = mapped_column(String(32))
    model_name: Mapped[str] = mapped_column(String(64))
    model_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="completed")
    wind_speed_kts: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_volume_tons: Mapped[float | None] = mapped_column(Float, nullable=True)
    level: Mapped[str] = mapped_column(String(8))                  # HIGH/MEDIUM/LOW (derived)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    # slick polygon + centroid (EPSG:4326), GiST-indexed
    geometry: Mapped[object] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True)
    )
    centroid: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True)
    )


class ModelRunRow(Base):
    __tablename__ = "model_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scene_id: Mapped[str] = mapped_column(ForeignKey("satellite_scenes.id"), index=True)
    model_name: Mapped[str] = mapped_column(String(64))
    model_version: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    inference_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
