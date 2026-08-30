from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas.system import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=request.app.state.settings.api_version,
    )
