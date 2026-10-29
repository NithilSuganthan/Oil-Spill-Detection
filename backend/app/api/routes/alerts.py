"""Operational Alerts API routes for SAGAR WATCH.

Endpoints:
  GET    /alerts                 — list all operational alerts (supports status/severity filter)
  GET    /alerts/summary         — get counts of alerts (critical, high, new, total)
  GET    /alerts/{alert_id}      — get alert details
  POST   /alerts/analyze/{incident_id} — analyze detection and generate alert if HIGH/CRITICAL
  PATCH  /alerts/{alert_id}/status — update in-app alert status (NEW, REVIEWING, RESOLVED)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_repo, get_settings_dep
from app.config import Settings
from app.db.repository import SpillRepository
from app.schemas.alert import (
    AlertAnalysisResult,
    AlertResponse,
    AlertSeverity,
    AlertStatus,
    AlertStatusUpdate,
    AlertSummaryResponse,
)
from app.services.alert_service import AlertService, get_alert_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertResponse])
def list_alerts(
    status: AlertStatus | None = Query(None, description="Filter by status (NEW, REVIEWING, RESOLVED)"),
    severity: AlertSeverity | None = Query(None, description="Filter by severity (CRITICAL, HIGH)"),
    alert_service: AlertService = Depends(get_alert_service),
):
    """List operational alerts generated from analyzed model detections."""
    return alert_service.list_alerts(status=status, severity=severity)


@router.get("/summary", response_model=AlertSummaryResponse)
def get_alert_summary(
    alert_service: AlertService = Depends(get_alert_service),
):
    """Get count summary of alerts (critical, high, new, total)."""
    return alert_service.get_summary()


@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert(
    alert_id: str,
    alert_service: AlertService = Depends(get_alert_service),
):
    """Get single alert details."""
    alert = alert_service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return alert


@router.post("/analyze/{incident_id}", response_model=AlertAnalysisResult)
def analyze_incident_for_alert(
    incident_id: str,
    repo: SpillRepository = Depends(get_repo),
    settings: Settings = Depends(get_settings_dep),
    alert_service: AlertService = Depends(get_alert_service),
):
    """Analyze a model detection and generate an alert if criticality is HIGH or CRITICAL.

    Duplicate protection:
    If the same HIGH/CRITICAL incident is analyzed again, the existing alert is reused.
    """
    try:
        return alert_service.analyze_incident_for_alert(
            incident_id=incident_id,
            repo=repo,
            settings=settings,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


@router.patch("/{alert_id}/status", response_model=AlertResponse)
def update_alert_status(
    alert_id: str,
    payload: AlertStatusUpdate,
    alert_service: AlertService = Depends(get_alert_service),
):
    """Update in-app alert status (NEW -> REVIEWING -> RESOLVED)."""
    updated = alert_service.update_status(alert_id, payload.status)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return updated
