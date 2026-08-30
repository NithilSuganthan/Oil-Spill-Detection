"""Satellite scene routes: discovery, import, preview, processing trigger.

Discovery sources:
  * source=stored    (default) — scenes already ingested into the repository
  * source=catalogue — LIVE search of the configured provider (real CDSE
    STAC catalogue in 'copernicus' mode; synthetic demo in 'mock' mode).
Catalogue results are NOT persisted unless explicitly imported.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.deps import (
    get_event_hub_dep,
    get_job_manager,
    get_satellite_provider,
    get_scene_service,
    get_settings_dep,
    get_storage,
)
from app.api.serializers import scene_to_response
from app.config import Settings
from app.domain.regions import classify_region
from app.schemas.satellite import SceneResponse
from app.services.event_hub import EventHub
from app.services.satellite_service import SceneService
from app.satellite.aoi import AreaOfInterest
from app.satellite.pipeline import EVENT_DISCOVERED
from app.satellite.providers.base import ProviderInfo, SceneQuery
from app.storage_keys import preview_key_for

router = APIRouter(prefix="/satellite", tags=["satellite"])


def _parse_bbox(bbox: str | None):
    if not bbox:
        return None
    try:
        w, s, e, n = (float(v) for v in bbox.split(","))
        return (w, s, e, n)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="bbox must be west,south,east,north") from exc


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid ISO-8601 datetime: {raw}") from exc


def _resolve_region(region: str | None) -> AreaOfInterest | None:
    if region is None:
        return None
    areas = {"india": AreaOfInterest()}
    area = areas.get(region.strip().lower())
    if area is None:
        raise HTTPException(status_code=422, detail=f"Unknown region AOI '{region}'")
    return area


@router.get("/scenes", response_model=list[SceneResponse], response_model_by_alias=True)
def list_scenes(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    bbox: str | None = Query(default=None),
    region: str | None = Query(default=None, description="Named AOI, e.g. 'india'"),
    platform: str | None = Query(default=None),
    product_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    source: str = Query(default="stored", pattern="^(stored|catalogue)$"),
    svc: SceneService = Depends(get_scene_service),
    provider=Depends(get_satellite_provider),
    settings: Settings = Depends(get_settings_dep),
) -> list[SceneResponse]:
    if source == "catalogue":
        query = SceneQuery(
            start=_parse_dt(start),
            end=_parse_dt(end),
            bbox=_parse_bbox(bbox),
            platform=platform,
            product_type=product_type,
            limit=min(limit, settings.catalogue_query_limit * 10),
        )
        aoi = _resolve_region(region)
        scenes = provider.search_scenes(query, aoi)
        return [scene_to_response(s) for s in scenes]

    scenes = svc.list_scenes(bbox=_parse_bbox(bbox))
    if start:
        start_dt = _parse_dt(start)
        scenes = [s for s in scenes if s.acquired_at and s.acquired_at >= start_dt]
    if end:
        end_dt = _parse_dt(end)
        scenes = [s for s in scenes if s.acquired_at and s.acquired_at <= end_dt]
    if platform:
        scenes = [s for s in scenes if platform.lower() in s.platform.lower()]
    if product_type:
        scenes = [s for s in scenes if (s.product_type or "").upper() == product_type.upper()]
    if region:
        wanted = region.strip().lower()
        scenes = [
            s for s in scenes
            if s.footprint and classify_region(
                (s.footprint[0] + s.footprint[2]) / 2,
                (s.footprint[1] + s.footprint[3]) / 2,
            ).lower() == wanted
        ]
    return [scene_to_response(s) for s in scenes[:limit]]


@router.get("/scenes/provider")
def provider_info(provider=Depends(get_satellite_provider)) -> dict:
    """Which data source is active and whether it is REAL."""
    info: ProviderInfo = provider.info()
    return {
        "name": info.name,
        "isReal": info.is_real,
        "description": info.description,
        "note": None if info.is_real else "DEMO — synthetic scenes, never real satellite data",
    }


@router.post("/scenes/import", response_model=SceneResponse, response_model_by_alias=True)
def import_scene(
    body: dict,
    svc: SceneService = Depends(get_scene_service),
    provider=Depends(get_satellite_provider),
    events: EventHub = Depends(get_event_hub_dep),
) -> SceneResponse:
    """Persist a discovered catalogue scene (by item id) into the repository
    with status DISCOVERED so it can be queued for processing."""
    scene_id = str(body.get("scene_id") or body.get("productId") or "").strip()
    if not scene_id:
        raise HTTPException(status_code=422, detail="body must include scene_id")
    record = provider.get_scene_metadata(scene_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Catalogue scene {scene_id} not found")
    existing = svc.get_scene(record.id)
    if existing is None:
        svc.add_scene(record)
        events.publish(EVENT_DISCOVERED, {
            "sceneId": record.id, "provider": record.source_provider,
        })
        stored = record
    else:
        stored = existing
    return scene_to_response(stored)


@router.get("/scenes/{scene_id}/preview")
def scene_preview(
    scene_id: str,
    svc: SceneService = Depends(get_scene_service),
    storage=Depends(get_storage),
) -> FileResponse:
    """Serve the lightweight PNG preview generated from an acquired scene."""
    scene = svc.get_scene(scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    key = preview_key_for(scene_id)
    if not storage.exists(key):
        raise HTTPException(
            status_code=404,
            detail="Preview not available yet — process the scene first",
        )
    path = storage.get_path(key)
    return FileResponse(path, media_type="image/png", filename=f"{scene_id}_preview.png")


@router.get("/scenes/{scene_id}/processing")
def scene_processing(
    scene_id: str,
    svc: SceneService = Depends(get_scene_service),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    """Processing state + available SAR products for a real acquired scene.

    Returns pipeline state, product references (logical storage keys, never
    raw filesystem paths) and the preprocessing provenance summary when the
    scene has been through the GRD calibration chain.
    """
    from pathlib import Path

    import json as _json

    scene = svc.get_scene(scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")

    products: list[str] = []
    provenance: dict | None = None
    report_key = (scene.metadata_extra or {}).get("preprocessing_report")
    if report_key:
        report_path = Path(report_key)
        if report_path.exists():
            doc = _json.loads(report_path.read_text(encoding="utf-8"))
            provenance = {
                "status": doc.get("status"),
                "calibration_method": (
                    doc.get("outputs", {}).get("vv", {}).get("calibration", {}).get("method")
                ),
                "calibration_units": "linear power (dimensionless)",
                "output_crs": settings.grd_target_crs,
                "outputs": list((doc.get("outputs") or {}).get("vv", {}).get("outputs", {}).values())
                + list((doc.get("outputs") or {}).get("vh", {}).get("outputs", {}).values()),
                "previews": doc.get("previews", []),
                "gcps": (doc.get("gcps") or {}).get("count"),
                "quality_failures": doc.get("quality_failures", []),
                "elapsed_s": doc.get("elapsed_s"),
            }
            for pol in ("vv", "vh"):
                outs = (doc.get("outputs") or {}).get(pol, {}).get("outputs", {})
                products.extend(outs.values())

    return {
        "sceneId": scene.id,
        "state": scene.pipeline_state or scene.status,
        "isRealData": not scene.is_demo,
        "note": None if scene.is_demo else
        "real Sentinel-1 data — calibrated backscatter only; NO oil detection has been performed",
        "availableProducts": products,
        "previewAvailable": bool(scene.preview_path),
        "preprocessing": provenance,
    }


@router.get("/scenes/{scene_id}", response_model=SceneResponse, response_model_by_alias=True)
def get_scene(scene_id: str, svc: SceneService = Depends(get_scene_service)) -> SceneResponse:
    scene = svc.get_scene(scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    return scene_to_response(scene)


@router.post("/scenes/{scene_id}/process", status_code=202)
def process_scene(
    scene_id: str,
    job_manager=Depends(get_job_manager),
) -> dict:
    """Enqueue background acquisition + processing; returns immediately."""
    try:
        job = job_manager.enqueue(scene_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"jobId": job.id, "state": job.state.value}
