"""SAGAR WATCH backend — FastAPI application factory.

Phase 1B pipeline:
    Sentinel-1-like scene -> preprocessing -> OilSpillModel adapter ->
    probability mask -> geospatial post-processing -> PostGIS/in-memory
    repository -> REST + SSE -> SAGAR WATCH frontend
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    ais_stream,
    analytics,
    attribution,
    drift,
    environmental,
    events,
    health,
    incidents,
    pipeline,
    reports,
    reviews,
    satellite,
    system as system_routes,
)
from app.config import Settings, get_settings
from app.db.seed import seed_demo_data
from app.db.session import create_repository
from app.inference.model_loader import ModelHandle
from app.satellite.aoi import AreaOfInterest
from app.satellite.factory import create_satellite_provider, create_storage_backend
from app.satellite.pipeline import PipelineJobManager
from app.services.event_hub import EventHub
from app.services.inference_service import InferenceService
from app.services.satellite_service import SceneService
from app.services.ais_stream_provider import create_aisstream_provider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    repo = create_repository(settings)
    event_bus = EventHub()
    model_handle = ModelHandle(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # Start AISStream real-time provider if configured
        ais_provider = create_aisstream_provider(settings.aisstream_api_key)
        if ais_provider:
            ais_provider.start()
            app.state.ais_stream_provider = ais_provider

        if settings.use_postgis:
            try:
                from sqlalchemy import create_engine, text

                with create_engine(settings.database_url).connect() as conn:
                    conn.execute(text("SELECT 1"))
                logger.info("PostGIS connection verified")
            except Exception as exc:  # noqa: BLE001
                logger.error("PostGIS unavailable at startup: %s", exc)
        if settings.seed_demo_data:
            seed_demo_data(repo)
        yield
        # Cleanup: stop AISStream provider
        ais_stream_prov = getattr(app.state, "ais_stream_provider", None)
        if ais_stream_prov:
            ais_stream_prov.stop()

    app = FastAPI(
        title="SAGAR WATCH API",
        description=(
            "Oil-spill detection backend. Phase 1B — development status. "
            "Incidents served here may be demo/development records "
            "(is_demo=true) or outputs of a MOCK model adapter."
        ),
        version=settings.api_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # shared state (dependencies read from request.app.state)
    app.state.settings = settings
    app.state.repo = repo
    app.state.events = event_bus
    app.state.model_handle = model_handle
    app.state.scene_service = SceneService(repo)

    # ---- Phase 2: real satellite ingestion infrastructure ---------------
    aoi = AreaOfInterest.from_settings(
        bbox_str=settings.india_aoi_bbox,
        geojson_path=settings.india_aoi_geojson_path or None,
    )
    provider = create_satellite_provider(settings)
    storage = create_storage_backend(settings)

    def _inference_factory() -> InferenceService:
        return InferenceService(repo=repo, settings=settings, event_hub=event_bus)

    job_manager = PipelineJobManager(
        repo=repo,
        provider=provider,
        storage=storage,
        settings=settings,
        event_hub=event_bus,
        aoi=aoi,
        model_handle=model_handle,
        inference_service_factory=_inference_factory,
    )
    app.state.aoi = aoi
    app.state.satellite_provider = provider
    app.state.storage = storage
    app.state.job_manager = job_manager

    api_prefix = "/api/v1"
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(incidents.router, prefix=api_prefix)
    app.include_router(satellite.router, prefix=api_prefix)
    app.include_router(pipeline.router, prefix=api_prefix)
    app.include_router(analytics.router, prefix=api_prefix)
    app.include_router(attribution.router, prefix=api_prefix)
    app.include_router(drift.router, prefix=api_prefix)
    app.include_router(environmental.router, prefix=api_prefix)
    app.include_router(system_routes.router, prefix=api_prefix)
    app.include_router(events.router, prefix=api_prefix)
    app.include_router(ais_stream.router, prefix=api_prefix)
    app.include_router(reviews.router, prefix=api_prefix)
    app.include_router(reports.router, prefix=api_prefix)

    return app


app = create_app()
