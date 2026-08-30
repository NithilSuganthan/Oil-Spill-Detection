"""FastAPI dependency providers — everything comes from app.state."""

from __future__ import annotations

from fastapi import Request

from app.config import Settings
from app.db.repository import SpillRepository
from app.inference.model_loader import ModelHandle
from app.services.analytics_service import AnalyticsService
from app.services.event_hub import EventHub
from app.services.incident_service import IncidentService
from app.services.inference_service import InferenceService
from app.services.satellite_service import SceneService


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_repo(request: Request) -> SpillRepository:
    return request.app.state.repo


def get_model_handle(request: Request) -> ModelHandle:
    return request.app.state.model_handle


def get_event_hub_dep(request: Request) -> EventHub:
    return request.app.state.events


def get_incident_service(request: Request) -> IncidentService:
    return IncidentService(request.app.state.repo)


def get_scene_service(request: Request) -> SceneService:
    return request.app.state.scene_service


def get_analytics_service(request: Request) -> AnalyticsService:
    return AnalyticsService(request.app.state.repo)


def get_inference_service(request: Request) -> InferenceService:
    return InferenceService(
        repo=request.app.state.repo,
        settings=request.app.state.settings,
        event_hub=request.app.state.events,
    )


def get_satellite_provider(request: Request):
    return request.app.state.satellite_provider


def get_storage(request: Request):
    return request.app.state.storage


def get_aoi(request: Request):
    return request.app.state.aoi


def get_job_manager(request: Request):
    return request.app.state.job_manager
