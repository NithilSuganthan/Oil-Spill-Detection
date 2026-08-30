from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Request

from app.api.deps import (
    get_event_hub_dep,
    get_inference_service,
    get_model_handle,
    get_scene_service,
)
from app.api.serializers import system_status_response
from app.config import Settings
from app.domain.entities import SatelliteSceneRecord
from app.schemas.analytics import SystemStatusResponse
from app.schemas.system import PipelineRunResponse
from app.services.inference_service import InferenceService
from app.services.satellite_service import SceneService, generate_synthetic_sar_raster

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status", response_model=SystemStatusResponse, response_model_by_alias=True)
def status(
    request: Request,
    scene_svc: SceneService = Depends(get_scene_service),
) -> SystemStatusResponse:
    settings: Settings = request.app.state.settings
    backend = "postgres-postgis" if settings.use_postgis else "in-memory-dev"
    resp = system_status_response(
        scene_svc.list_scenes(),
        database_backend=backend,
        model_adapter=settings.model_adapter,
    )
    handle_info = request.app.state.model_handle.model_info
    if resp.active_scene is None:
        # keep the UI's status bar populated even before any scene exists
        from app.schemas.analytics import ActiveSceneInfo

        resp.active_scene = ActiveSceneInfo(
            id="—", platform=handle_info["model"], processed_at=None, status="IDLE"
        )
    return resp


@router.post("/run-demo-pipeline", response_model=PipelineRunResponse)
def run_demo_pipeline(
    request: Request,
    svc: InferenceService = Depends(get_inference_service),
    scene_svc: SceneService = Depends(get_scene_service),
    model_handle=Depends(get_model_handle),
    events=Depends(get_event_hub_dep),
) -> PipelineRunResponse:
    """DEVELOPMENT ONLY.

    Generates a synthetic SAR-like GeoTIFF, registers a demo scene, runs the
    configured MODEL ADAPTER (mock heuristic by default) and stores any
    resulting incidents — proving the full Phase 1 pipeline:

    scene -> preprocess -> adapter.predict -> probability mask ->
    polygons -> geodesic metrics -> repository -> SSE -> frontend

    Incidents produced here are marked is_demo=true and must never be
    presented as real satellite detections.
    """
    settings: Settings = request.app.state.settings
    now = datetime.now(timezone.utc)
    scene_id = f"DEMO_S1A_IW_{now.strftime('%Y%m%dT%H%M%S')}"
    raster_path = Path(settings.scene_storage_dir) / f"{scene_id}.tif"

    generate_synthetic_sar_raster(raster_path, seed=int(now.timestamp()))
    # Footprint matches the synthetic raster's actual georeferencing
    # (UTM 43N origin 220000E/1050000N, 40 m px, 512x512 -> Arabian Sea).
    scene = SatelliteSceneRecord(
        id=scene_id,
        platform="Sentinel-1A",
        sensor="SAR C-band",
        acquisition_mode="IW",
        polarisation="VV + VH",
        acquired_at=now - timedelta(minutes=11),
        footprint=(72.45, 9.304, 72.638, 9.491),
        status="processing",
        image_path=str(raster_path),
        is_demo=True,
    )
    scene_svc.add_scene(scene)

    created, model_run_id, inference_ms = svc.process_scene(
        scene, raster_path, model=model_handle.get()
    )
    del events

    return PipelineRunResponse(
        scene_id=scene_id,
        model_run_id=model_run_id,
        incidents_created=[i.id for i in created],
        inference_time_ms=inference_ms,
    )
