"""Alert service — Manages operational alerts generated from analyzed model detections.

Follows strict rules:
- Alerts are ONLY created for analyzed detections with HIGH or CRITICAL criticality.
- Duplicate protection: Re-analyzing an incident reuses the existing alert.
- In-app statuses only: NEW, REVIEWING, RESOLVED.
- No email / external notifications.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.db.repository import SpillRepository
from app.schemas.alert import (
    AlertAnalysisResult,
    AlertResponse,
    AlertSeverity,
    AlertStatus,
    AlertSummaryResponse,
)
from app.services.criticality_scorer import compute_criticality
from app.services.drift_engine import FirstOrderDriftProvider, drift_result_to_source_estimate
from app.services.intelligence_assembly import assemble_intelligence

logger = logging.getLogger(__name__)


def _get_drift_provider(settings: Settings) -> FirstOrderDriftProvider:
    if settings.environmental_provider == "real" and settings.cmems_username:
        try:
            from app.services.environmental_real_provider import RealEnvironmentalProvider
            env_provider = RealEnvironmentalProvider(
                cmems_username=settings.cmems_username,
                cmems_password=settings.cmems_password,
                cds_api_key=settings.cds_api_key,
                cds_api_url=settings.cds_api_url,
            )
        except Exception:
            from app.services.environmental_mock_provider import MockEnvironmentalProvider
            env_provider = MockEnvironmentalProvider()
    else:
        from app.services.environmental_mock_provider import MockEnvironmentalProvider
        env_provider = MockEnvironmentalProvider()

    return FirstOrderDriftProvider(environmental_provider=env_provider, settings=settings)


def _get_ais_provider(settings: Settings):
    if settings.ais_provider == "gfw" and settings.gfw_api_token:
        try:
            from app.services.ais_gfw_provider import GlobalFishingWatchAISProvider
            return GlobalFishingWatchAISProvider(api_token=settings.gfw_api_token)
        except Exception:
            from app.services.ais_mock_provider import MockAISProvider
            return MockAISProvider()
    from app.services.ais_mock_provider import MockAISProvider
    return MockAISProvider()


class AlertService:
    """Thread-safe operational alert repository and management service."""

    def __init__(self) -> None:
        self._alerts: dict[str, AlertResponse] = {}
        self._incident_to_alert: dict[str, str] = {}
        self._lock = threading.RLock()

    def list_alerts(
        self,
        *,
        status: AlertStatus | None = None,
        severity: AlertSeverity | None = None,
    ) -> list[AlertResponse]:
        with self._lock:
            alerts = list(self._alerts.values())

        if status:
            alerts = [a for a in alerts if a.status == status]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        # Sort: CRITICAL first, then HIGH, then newest
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3}
        alerts.sort(
            key=lambda a: (
                severity_order.get(a.severity, 99),
                -a.criticality_score,
                a.created_at,
            ),
            reverse=False,
        )
        return alerts

    def get_alert(self, alert_id: str) -> AlertResponse | None:
        with self._lock:
            return self._alerts.get(alert_id)

    def get_alert_by_incident(self, incident_id: str) -> AlertResponse | None:
        with self._lock:
            alert_id = self._incident_to_alert.get(incident_id)
            if alert_id:
                return self._alerts.get(alert_id)
            return None

    def update_status(self, alert_id: str, new_status: AlertStatus) -> AlertResponse | None:
        with self._lock:
            alert = self._alerts.get(alert_id)
            if not alert:
                return None
            updated_alert = alert.model_copy(update={"status": new_status})
            self._alerts[alert_id] = updated_alert
            return updated_alert

    def get_summary(self) -> AlertSummaryResponse:
        with self._lock:
            alerts = list(self._alerts.values())
        critical_count = sum(1 for a in alerts if a.severity == "CRITICAL")
        high_count = sum(1 for a in alerts if a.severity == "HIGH")
        new_count = sum(1 for a in alerts if a.status == "NEW")
        return AlertSummaryResponse(
            critical=critical_count,
            high=high_count,
            new=new_count,
            total=len(alerts),
        )

    def analyze_incident_for_alert(
        self,
        incident_id: str,
        repo: SpillRepository,
        settings: Settings,
    ) -> AlertAnalysisResult:
        """Analyze a model detection and generate an alert if criticality is HIGH or CRITICAL.

        Duplicate protection: If an alert already exists for this incident, reuse it.
        """
        # Check existing alert (Duplicate protection)
        with self._lock:
            existing_alert = self.get_alert_by_incident(incident_id)
            if existing_alert is not None:
                return AlertAnalysisResult(
                    created=False,
                    reused=True,
                    alert=existing_alert,
                    criticality_score=existing_alert.criticality_score,
                    criticality_level=existing_alert.severity,
                    reason=f"Alert already exists for incident {incident_id} (reused).",
                )

        incident = repo.get_incident(incident_id)
        if incident is None:
            raise ValueError(f"Incident {incident_id} not found")

        # 1. Run Drift analysis
        drift_provider = _get_drift_provider(settings)
        obs_time = (
            incident.detected_at.replace(tzinfo=timezone.utc)
            if incident.detected_at.tzinfo is None
            else incident.detected_at
        )

        try:
            drift_result = drift_provider.estimate_source(
                incident_id=incident_id,
                slick_lat=incident.centroid_lat,
                slick_lon=incident.centroid_lon,
                observation_time=obs_time,
            )
        except Exception as exc:
            logger.warning("Drift hindcast failed for %s, continuing with empty drift: %s", incident_id, exc)
            drift_result = None

        # 2. Run AIS attribution
        attribution_result = None
        if drift_result:
            source_estimate = drift_result_to_source_estimate(drift_result)
            ais_provider = _get_ais_provider(settings)
            try:
                from app.services.ais_correlation import analyze_attribution
                attribution_result = analyze_attribution(
                    incident_id=incident_id,
                    source=source_estimate,
                    provider=ais_provider,
                    settings=settings,
                    coverage_known=True,
                )
            except Exception as exc:
                logger.warning("AIS correlation failed for %s: %s", incident_id, exc)

        # 3. Assemble detection intelligence
        candidates = attribution_result.candidates if attribution_result else []
        try:
            intelligence_result = assemble_intelligence(
                incident=incident,
                candidates=candidates,
                settings=settings,
            )
        except Exception as exc:
            logger.warning("Intelligence assembly failed for %s: %s", incident_id, exc)
            intelligence_result = None

        # 4. Compute operational criticality score
        from app.api.routes.drift import _attribution_to_dict, _drift_result_to_response
        from app.api.routes.attribution import _result_to_response as _attr_resp

        incident_dict = {
            "id": incident.id,
            "areaKm2": incident.area_km2,
            "confidence": incident.confidence,
            "region": incident.region,
            "windSpeedKts": incident.wind_speed_kts,
        }
        drift_dict = _drift_result_to_response(drift_result).model_dump(by_alias=True) if drift_result else {}
        attr_dict = _attribution_to_dict(_attr_resp(attribution_result)) if attribution_result else {}
        intel_dict = intelligence_result.model_dump(by_alias=True) if intelligence_result else {}

        criticality = compute_criticality(
            incident=incident_dict,
            drift=drift_dict,
            attribution=attr_dict,
            intelligence=intel_dict,
        )

        score = criticality.score
        level_raw = criticality.level.upper()

        # Map level to AlertSeverity
        if score >= 80 or level_raw == "CRITICAL":
            severity: AlertSeverity = "CRITICAL"
        elif score >= 50 or level_raw == "HIGH":
            severity = "HIGH"
        elif score >= 25 or level_raw in ("MID", "MODERATE"):
            severity = "MODERATE"
        else:
            severity = "LOW"

        # Check creation threshold: only HIGH or CRITICAL creates an alert
        if severity not in ("HIGH", "CRITICAL"):
            return AlertAnalysisResult(
                created=False,
                reused=False,
                alert=None,
                criticality_score=score,
                criticality_level=severity,
                reason=(
                    f"Analyzed model detection did not reach alert threshold: "
                    f"Criticality is {score}/100 ({severity}). Only HIGH or CRITICAL trigger alerts."
                ),
            )

        # Build AlertResponse
        alert_id = f"ALT-{incident.id}"
        now_iso = datetime.now(timezone.utc).isoformat()
        det_time_iso = incident.detected_at.isoformat()

        # Build evidence payload
        evidence = {
            "environmental": {
                "windSpeedKts": incident.wind_speed_kts,
                "region": incident.region,
            },
            "drift": {
                "uncertaintyKm": getattr(drift_result, "uncertainty_km", None),
                "uncertaintyHours": getattr(drift_result, "uncertainty_hours", None),
                "sourceLat": getattr(drift_result, "source_lat", None),
                "sourceLon": getattr(drift_result, "source_lon", None),
            } if drift_result else None,
            "ais": {
                "candidateCount": len(candidates),
                "topCandidate": {
                    "vesselName": candidates[0].get("vessel_name") or candidates[0].get("vesselName"),
                    "mmsi": candidates[0].get("mmsi"),
                    "attributionScore": candidates[0].get("attribution_score") or candidates[0].get("attributionScore"),
                } if candidates else None,
            },
        }

        title = f"Model-detected oil-spill candidate in {incident.region or 'coastal waters'}"
        summary = (
            f"Incident {incident.id} ({incident.location_description}) reached operational priority "
            f"{score}/100 ({severity}). Action recommendation: {criticality.action}."
        )

        alert = AlertResponse(
            alert_id=alert_id,
            incident_id=incident.id,
            severity=severity,
            criticality_score=score,
            status="NEW",
            title=title,
            summary=summary,
            created_at=now_iso,
            detection_time=det_time_iso,
            latitude=incident.centroid_lat,
            longitude=incident.centroid_lon,
            area_km2=incident.area_km2,
            model_confidence=incident.confidence,
            location_description=incident.location_description,
            action=criticality.action,
            factors=criticality.factors,
            geometry=incident.geometry,
            evidence=evidence,
        )

        with self._lock:
            # Double check before storing
            if incident.id in self._incident_to_alert:
                existing = self._alerts[self._incident_to_alert[incident.id]]
                return AlertAnalysisResult(
                    created=False,
                    reused=True,
                    alert=existing,
                    criticality_score=existing.criticality_score,
                    criticality_level=existing.severity,
                    reason=f"Alert already exists for incident {incident.id} (reused).",
                )
            self._alerts[alert_id] = alert
            self._incident_to_alert[incident.id] = alert_id

        return AlertAnalysisResult(
            created=True,
            reused=False,
            alert=alert,
            criticality_score=score,
            criticality_level=severity,
            reason=f"Operational alert created with criticality {score}/100 ({severity}).",
        )


_ALERT_SERVICE: AlertService | None = None
_SERVICE_LOCK = threading.Lock()


def get_alert_service() -> AlertService:
    global _ALERT_SERVICE
    if _ALERT_SERVICE is None:
        with _SERVICE_LOCK:
            if _ALERT_SERVICE is None:
                _ALERT_SERVICE = AlertService()
    return _ALERT_SERVICE
