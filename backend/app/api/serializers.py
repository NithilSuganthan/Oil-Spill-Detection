"""Entity -> response-schema serializers."""

from __future__ import annotations

from app.domain.entities import SatelliteSceneRecord, SpillIncident
from app.schemas.analytics import (
    ActiveSceneInfo,
    ServiceStatus,
    SystemStatusResponse,
)
from app.schemas.incident import Centroid, IncidentResponse
from app.schemas.satellite import BoundingBox, SceneResponse


def incident_to_response(inc: SpillIncident) -> IncidentResponse:
    return IncidentResponse(
        id=inc.id,
        scene_id=inc.scene_id,
        confidence=round(inc.confidence, 3),
        area_km2=inc.area_km2,
        perimeter_km2=inc.perimeter_km,
        centroid=Centroid(lat=inc.centroid_lat, lon=inc.centroid_lon),
        geometry=inc.geometry,
        detected_at=_ist_iso(inc.detected_at),
        region=inc.region,
        location_description=inc.location_description,
        satellite=inc.satellite,
        model=inc.model_name,
        model_version=inc.model_version,
        status=inc.status,
        level=inc.level,  # type: ignore[arg-type]
        wind_speed_kts=inc.wind_speed_kts,
        estimated_volume_tons=inc.estimated_volume_tons,
        is_demo=inc.is_demo,
    )


def scene_to_response(sc: SatelliteSceneRecord) -> SceneResponse:
    footprint = None
    if sc.footprint:
        w, s, e, n = sc.footprint
        footprint = BoundingBox(west=w, south=s, east=e, north=n)
    return SceneResponse(
        id=sc.id,
        product_id=sc.product_id or sc.id,
        platform=sc.platform,
        sensor=sc.sensor,
        acquisition_mode=sc.acquisition_mode,
        polarisation=sc.polarisation,
        acquired_at=_ist_iso(sc.acquired_at),
        processed_at=_ist_iso(sc.processed_at),
        footprint=footprint,
        status=sc.status,
        image_path=None,  # never leak storage paths to the wire
        is_demo=sc.is_demo,
        product_name=sc.product_name,
        source_provider=sc.source_provider or "mock",
        orbit_state=sc.orbit_state,
        absolute_orbit=sc.absolute_orbit,
        relative_orbit=sc.relative_orbit,
        file_size_bytes=sc.file_size_bytes,
        product_type=sc.product_type,
        pipeline_state=sc.pipeline_state,
        has_preview=bool(sc.preview_path),
    )


def system_status_response(
    scenes: list[SatelliteSceneRecord],
    *,
    database_backend: str,
    model_adapter: str,
) -> SystemStatusResponse:
    active = next((s for s in scenes if s.status == "processing"), None)
    if active is None:
        active = next((s for s in scenes if s.status == "processed"), None)
    return SystemStatusResponse(
        services=[
            ServiceStatus(name="Satellite Feed", status="LIVE"),
            ServiceStatus(name="Processing Engine", status="RUNNING"),
            ServiceStatus(name="AI Model", status="OPERATIONAL"),
            ServiceStatus(
                name="Database",
                status="CONNECTED" if database_backend != "in-memory-dev" else "CONNECTED",
            ),
        ],
        active_scene=(
            ActiveSceneInfo(
                id=active.id,
                platform=active.platform,
                acquired_at=_ist_iso(active.acquired_at),
                processed_at=_ist_iso(active.processed_at),
                status=(active.status or "").upper(),
            )
            if active
            else None
        ),
        database_backend=database_backend,
        model_adapter=model_adapter,
    )


def _ist_iso(dt) -> str | None:
    """ISO-8601 with +05:30 offset, matching frontend expectations."""
    if dt is None:
        return None
    from datetime import timedelta, timezone

    ist = timezone(timedelta(hours=5, minutes=30))
    return dt.astimezone(ist).isoformat()
