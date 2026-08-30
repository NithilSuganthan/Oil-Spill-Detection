from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_analytics_service
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    DetectionPoint,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummaryResponse, response_model_by_alias=True)
def analytics_summary(
    svc: AnalyticsService = Depends(get_analytics_service),
) -> AnalyticsSummaryResponse:
    return AnalyticsSummaryResponse(**svc.summary())


@router.get("/detections", response_model=list[DetectionPoint], response_model_by_alias=True)
def detections(svc: AnalyticsService = Depends(get_analytics_service)) -> list[DetectionPoint]:
    return [DetectionPoint(**d) for d in svc.detections()]
