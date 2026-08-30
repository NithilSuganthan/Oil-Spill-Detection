"""Mapping between domain entities and GeoAlchemy2 ORM rows."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import shapely.geometry
from geoalchemy2.shape import from_shape, to_shape

from app.db.models_orm import ModelRunRow, SatelliteSceneRow, SpillIncidentRow
from app.domain.entities import (
    ModelRun,
    SatelliteSceneRecord,
    SpillIncident,
    confidence_level,
)


def _dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def scene_to_row(rec: SatelliteSceneRecord) -> SatelliteSceneRow:
    footprint_geom = None
    if rec.geometry is not None:
        footprint_geom = from_shape(shapely.geometry.shape(rec.geometry), srid=4326)
    elif rec.footprint:
        west, south, east, north = rec.footprint
        footprint_geom = from_shape(shapely.geometry.box(west, south, east, north), srid=4326)
    return SatelliteSceneRow(
        id=rec.id,
        product_id=rec.product_id or rec.id,
        product_name=rec.product_name,
        satellite=rec.platform,
        sensor=rec.sensor,
        acquisition_mode=rec.acquisition_mode,
        polarisation=rec.polarisation,
        acquisition_time=_dt(rec.acquired_at),
        processing_time=_dt(rec.processed_at),
        status=rec.status,
        image_path=rec.image_path,
        is_demo=rec.is_demo,
        source_provider=rec.source_provider,
        orbit_state=rec.orbit_state,
        absolute_orbit=rec.absolute_orbit,
        relative_orbit=rec.relative_orbit,
        download_url=rec.download_url,
        file_size_bytes=rec.file_size_bytes,
        product_type=rec.product_type,
        thumbnail_url=rec.thumbnail_url,
        preview_path=rec.preview_path,
        pipeline_state=rec.pipeline_state,
        metadata_extra_json=json.dumps(rec.metadata_extra or {}, default=str),
        footprint=footprint_geom,
    )


def row_to_scene(row: SatelliteSceneRow) -> SatelliteSceneRecord:
    fp = None
    geometry = None
    if row.footprint is not None:
        shape = to_shape(row.footprint)
        minx, miny, maxx, maxy = shape.bounds
        fp = (minx, miny, maxx, maxy)
        geojson = shapely.geometry.mapping(
            shape if not isinstance(shape, shapely.geometry.Polygon) else shapely.geometry.box(minx, miny, maxx, maxy)
        )
        geometry = json.loads(json.dumps(geojson))
    return SatelliteSceneRecord(
        id=row.id,
        platform=row.satellite,
        sensor=row.sensor,
        acquisition_mode=row.acquisition_mode,
        polarisation=row.polarisation,
        acquired_at=_dt(row.acquisition_time),
        processed_at=_dt(row.processing_time),
        footprint=fp,
        status=row.status,  # type: ignore[arg-type]
        image_path=row.image_path,
        is_demo=row.is_demo,
        product_id=row.product_id,
        product_name=row.product_name,
        source_provider=row.source_provider or "mock",
        orbit_state=row.orbit_state,
        absolute_orbit=row.absolute_orbit,
        relative_orbit=row.relative_orbit,
        download_url=row.download_url,
        file_size_bytes=row.file_size_bytes,
        product_type=row.product_type,
        thumbnail_url=row.thumbnail_url,
        preview_path=row.preview_path,
        pipeline_state=row.pipeline_state,
        metadata_extra=json.loads(row.metadata_extra_json) if row.metadata_extra_json else {},
        geometry=geometry,
    )


def incident_to_row(inc: SpillIncident) -> SpillIncidentRow:
    poly = shapely.geometry.shape(inc.geometry)
    centroid = shapely.geometry.Point(inc.centroid_lon, inc.centroid_lat)
    return SpillIncidentRow(
        id=inc.id,
        scene_id=inc.scene_id,
        confidence=inc.confidence,
        area_km2=inc.area_km2,
        perimeter_km=inc.perimeter_km,
        detected_at=_dt(inc.detected_at),
        region=inc.region,
        location_description=inc.location_description,
        satellite=inc.satellite,
        model_name=inc.model_name,
        model_version=inc.model_version,
        status=inc.status,
        wind_speed_kts=inc.wind_speed_kts,
        estimated_volume_tons=inc.estimated_volume_tons,
        level=confidence_level(inc.confidence),
        is_demo=inc.is_demo,
        geometry=from_shape(poly, srid=4326),
        centroid=from_shape(centroid, srid=4326),
    )


def row_to_incident(row: SpillIncidentRow) -> SpillIncident:
    poly = to_shape(row.geometry)
    cx = to_shape(row.centroid)
    geojson = shapely.geometry.mapping(poly)
    return SpillIncident(
        id=row.id,
        scene_id=row.scene_id,
        confidence=row.confidence,
        area_km2=row.area_km2,
        perimeter_km=row.perimeter_km,
        centroid_lon=cx.x,
        centroid_lat=cx.y,
        geometry=json.loads(json.dumps(geojson)),
        bbox=tuple(poly.bounds),  # type: ignore[assignment]
        detected_at=_dt(row.detected_at),  # type: ignore[arg-type]
        region=row.region,
        location_description=row.location_description,
        satellite=row.satellite,
        model_name=row.model_name,
        model_version=row.model_version,
        status=row.status,  # type: ignore[arg-type]
        wind_speed_kts=row.wind_speed_kts,
        estimated_volume_tons=row.estimated_volume_tons,
        is_demo=row.is_demo,
    )


def run_to_row(run: ModelRun) -> ModelRunRow:
    return ModelRunRow(
        id=run.id,
        scene_id=run.scene_id,
        model_name=run.model_name,
        model_version=run.model_version,
        started_at=_dt(run.started_at),  # type: ignore[arg-type]
        completed_at=_dt(run.completed_at),
        inference_time_ms=run.inference_time_ms,
        status=run.status,
        error_message=run.error_message,
    )


def row_to_run(row: ModelRunRow) -> ModelRun:
    return ModelRun(
        id=row.id,
        scene_id=row.scene_id,
        model_name=row.model_name,
        model_version=row.model_version,
        started_at=_dt(row.started_at),  # type: ignore[arg-type]
        completed_at=_dt(row.completed_at),
        inference_time_ms=row.inference_time_ms,
        status=row.status,  # type: ignore[arg-type]
        error_message=row.error_message,
    )
