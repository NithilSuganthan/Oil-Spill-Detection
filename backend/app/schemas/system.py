from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.incident import CamelModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    service: str = "sagar-watch-backend"
    version: str


class PipelineRunResponse(CamelModel):
    """Result of a development demo pipeline run."""

    scene_id: str
    model_run_id: str
    incidents_created: list[str]
    inference_time_ms: int
    note: str = (
        "DEVELOPMENT DEMO — synthetic scene, mock model adapter, "
        "not real satellite data"
    )
