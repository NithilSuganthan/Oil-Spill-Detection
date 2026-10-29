"""Drift analysis and investigation orchestrator routes.

Endpoints:
  POST /drift/analyze     — run drift hindcast for an incident
  GET  /drift/{id}        — get drift result for an incident
  POST /investigation/{id}/run — full drift + AIS pipeline
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_event_hub_dep, get_repo, get_settings_dep
from app.config import Settings
from app.db.repository import SpillRepository
from app.schemas.attribution import (
    AttributionResponse,
    CandidateVesselResponse,
    ScoreComponentsResponse,
    SearchWindowResponse,
)
from app.schemas.drift import (
    DriftResponse,
    InvestigationRequest,
    InvestigationResponse,
)
from app.services.ais_correlation import analyze_attribution, build_search_window
from app.services.ais_mock_provider import MockAISProvider
from app.services.drift_engine import FirstOrderDriftProvider, drift_result_to_source_estimate
from app.services.drift_provider import DriftResult
from app.services.environmental_mock_provider import MockEnvironmentalProvider
from app.services.event_hub import EventHub
from app.services.intelligence_assembly import assemble_intelligence

router = APIRouter(tags=["drift"])


def _get_drift_provider(settings: Settings):
    """Create drift provider with configured environmental data source.

    When ENVIRONMENTAL_PROVIDER=real, uses RealEnvironmentalProvider
    which requires CMEMS and CDS credentials.  Cache must be prepared
    separately before calling estimate_source().
    """
    if settings.environmental_provider == "real" and settings.cmems_username:
        from app.services.environmental_real_provider import RealEnvironmentalProvider
        env_provider = RealEnvironmentalProvider(
            cmems_username=settings.cmems_username,
            cmems_password=settings.cmems_password,
            cds_api_key=settings.cds_api_key,
            cds_api_url=settings.cds_api_url,
        )
    else:
        env_provider = MockEnvironmentalProvider()
    return FirstOrderDriftProvider(environmental_provider=env_provider, settings=settings)


def _get_ais_provider(settings: Settings):
    if settings.ais_provider == "gfw" and settings.gfw_api_token:
        from app.services.ais_gfw_provider import GlobalFishingWatchAISProvider
        return GlobalFishingWatchAISProvider(api_token=settings.gfw_api_token)
    return MockAISProvider()


def _compute_bbox(
    lat: float, lon: float, settings: Settings,
) -> tuple[float, float, float, float]:
    """Compute bbox around slick with configured padding."""
    pad = settings.env_cache_bbox_pad_deg
    return (lon - pad, lat - pad, lon + pad, lat + pad)


def _compute_timesteps(
    observation_time: datetime, settings: Settings,
) -> list[datetime]:
    """Compute hourly timesteps for the backward drift window."""
    n_hours = math.ceil(settings.drift_hours) + 1
    return [
        observation_time - timedelta(hours=h) for h in range(n_hours)
    ]


def _prepare_real_cache(
    provider: FirstOrderDriftProvider,
    lat: float,
    lon: float,
    observation_time: datetime,
    settings: Settings,
) -> str:
    """Prepare cache for real environmental provider if applicable.

    Returns:
        "REAL" if real cache was prepared successfully,
        "DATA_UNAVAILABLE" if real provider was configured but data unavailable,
        "DEMO" if using mock provider.
    """
    from app.services.environmental_real_provider import RealEnvironmentalProvider

    if not isinstance(provider._env, RealEnvironmentalProvider):
        return "DEMO"

    bbox = _compute_bbox(lat, lon, settings)
    timesteps = _compute_timesteps(observation_time, settings)

    try:
        provider._env.prepare_cache(bbox, timesteps)
        return "REAL"
    except RuntimeError as exc:
        # Real provider configured but data unavailable for this time range
        # Fall back to mock — report status but don't crash
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            "Real environmental data unavailable, falling back to mock: %s", exc,
        )
        # Replace the real env provider with mock so drift can proceed
        from app.services.environmental_mock_provider import MockEnvironmentalProvider
        provider._env = MockEnvironmentalProvider()
        return "DATA_UNAVAILABLE"


def _drift_result_to_response(result: DriftResult) -> DriftResponse:
    return DriftResponse(
        incident_id=result.incident_id,
        method=result.method,
        slick_latitude=result.slick_latitude,
        slick_longitude=result.slick_longitude,
        observation_time=result.observation_time.isoformat(),
        integration_hours=result.integration_hours,
        timestep_minutes=result.timestep_minutes,
        ensemble_size=result.ensemble_size,
        source_latitude=result.source_latitude,
        source_longitude=result.source_longitude,
        source_earliest=result.source_earliest.isoformat(),
        source_latest=result.source_latest.isoformat(),
        uncertainty_km=result.uncertainty_km,
        uncertainty_hours=result.uncertainty_hours,
        confidence=result.confidence,
        quality_flags=result.quality_flags,
        source_points=[[lat, lon] for lat, lon in result.source_points],
        provenance=result.provenance,
        analyzed_at=result.analyzed_at.isoformat() if result.analyzed_at else None,
    )


def _attribution_to_dict(resp: AttributionResponse) -> dict:
    return resp.model_dump(by_alias=True)


def _determine_env_status(settings: Settings) -> str:
    """Determine environment status string for investigation response."""
    if settings.environmental_provider == "real" and settings.cmems_username:
        if settings.cmems_password and settings.cds_api_key:
            return "REAL"
        return "CREDENTIALS_REQUIRED"
    return "DEMO"


# ── Drift endpoints ──────────────────────────────────────────────────────

@router.post("/drift/analyze", response_model=DriftResponse)
def analyze_drift(
    request: InvestigationRequest,
    repo: SpillRepository = Depends(get_repo),
    settings: Settings = Depends(get_settings_dep),
    event_hub: EventHub = Depends(get_event_hub_dep),
):
    """Run drift hindcast for a potential spill incident."""
    incident = repo.get_incident(request.incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {request.incident_id} not found")

    event_hub.publish("drift.started", {"incidentId": request.incident_id})

    obs_time = incident.detected_at.replace(tzinfo=timezone.utc) \
        if incident.detected_at.tzinfo is None else incident.detected_at

    provider = _get_drift_provider(settings)

    try:
        _prepare_real_cache(
            provider, incident.centroid_lat, incident.centroid_lon, obs_time, settings,
        )
        result = provider.estimate_source(
            incident_id=request.incident_id,
            slick_lat=incident.centroid_lat,
            slick_lon=incident.centroid_lon,
            observation_time=obs_time,
        )
    except Exception as exc:
        event_hub.publish("drift.failed", {"incidentId": request.incident_id, "error": str(exc)})
        raise HTTPException(status_code=500, detail=f"Drift analysis failed: {exc}")

    event_hub.publish("drift.completed", {"incidentId": request.incident_id})
    return _drift_result_to_response(result)


@router.get("/drift/{incident_id}", response_model=DriftResponse)
def get_drift(
    incident_id: str,
    repo: SpillRepository = Depends(get_repo),
    settings: Settings = Depends(get_settings_dep),
):
    """Get or perform drift analysis for an incident."""
    incident = repo.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    obs_time = incident.detected_at.replace(tzinfo=timezone.utc) \
        if incident.detected_at.tzinfo is None else incident.detected_at

    provider = _get_drift_provider(settings)
    _prepare_real_cache(
        provider, incident.centroid_lat, incident.centroid_lon, obs_time, settings,
    )
    result = provider.estimate_source(
        incident_id=incident_id,
        slick_lat=incident.centroid_lat,
        slick_lon=incident.centroid_lon,
        observation_time=obs_time,
    )
    return _drift_result_to_response(result)


# ── Investigation orchestrator ────────────────────────────────────────────

@router.post("/investigation/{incident_id}/run", response_model=InvestigationResponse)
def run_investigation(
    incident_id: str,
    repo: SpillRepository = Depends(get_repo),
    settings: Settings = Depends(get_settings_dep),
    event_hub: EventHub = Depends(get_event_hub_dep),
):
    """Full investigation pipeline: drift → source estimate → AIS correlation.

    Orchestrates:
    1. Load incident
    2. Run drift hindcast → SourceEstimate
    3. Run AIS correlation using SourceEstimate
    4. Return combined result
    """
    incident = repo.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    event_hub.publish("investigation.started", {"incidentId": incident_id})

    # Step 1: Drift analysis
    drift_provider = _get_drift_provider(settings)
    obs_time = incident.detected_at.replace(tzinfo=timezone.utc) \
        if incident.detected_at.tzinfo is None else incident.detected_at

    env_status = "DEMO"
    try:
        cache_status = _prepare_real_cache(
            drift_provider, incident.centroid_lat, incident.centroid_lon, obs_time, settings,
        )
        drift_result = drift_provider.estimate_source(
            incident_id=incident_id,
            slick_lat=incident.centroid_lat,
            slick_lon=incident.centroid_lon,
            observation_time=obs_time,
        )
        env_status = cache_status
    except Exception as exc:
        event_hub.publish("investigation.failed", {"incidentId": incident_id, "error": str(exc)})
        raise HTTPException(status_code=500, detail=f"Drift analysis failed: {exc}")

    # Step 2: Convert to SourceEstimate
    source_estimate = drift_result_to_source_estimate(drift_result)

    # Step 3: AIS correlation using drift-derived source estimate
    # Adjust search radius to include source uncertainty
    effective_radius = settings.ais_search_radius_km + source_estimate.uncertainty_km
    settings.ais_search_radius_km = effective_radius

    ais_provider = _get_ais_provider(settings)
    try:
        attribution_result = analyze_attribution(
            incident_id=incident_id,
            source=source_estimate,
            provider=ais_provider,
            settings=settings,
            coverage_known=True,
        )
    except Exception as exc:
        event_hub.publish("investigation.failed", {"incidentId": incident_id, "error": str(exc)})
        raise HTTPException(status_code=500, detail=f"AIS analysis failed: {exc}")

    env_status = cache_status

    # Step 4: Phase 8 — Detection Intelligence
    intelligence_result = assemble_intelligence(
        incident=incident,
        candidates=attribution_result.candidates,
        settings=settings,
    )

    # Step 5: Phase 1 — Operational Criticality Score
    from app.services.criticality_scorer import compute_criticality

    # Build dicts for the scorer (using camelCase wire format)
    incident_dict = {
        "id": incident.id,
        "areaKm2": incident.area_km2,
        "confidence": incident.confidence,
        "region": incident.region,
        "windSpeedKts": incident.wind_speed_kts,
    }
    drift_dict = _drift_result_to_response(drift_result).model_dump(by_alias=True)

    from app.api.routes.attribution import _result_to_response as _attr_resp
    attr_response = _attr_resp(attribution_result)
    attr_dict = _attribution_to_dict(attr_response)
    intel_dict = intelligence_result.model_dump(by_alias=True)

    criticality_result = compute_criticality(
        incident=incident_dict,
        drift=drift_dict,
        attribution=attr_dict,
        intelligence=intel_dict,
    )

    event_hub.publish("investigation.completed", {
        "incidentId": incident_id,
        "candidateCount": attribution_result.candidate_count,
        "criticalityScore": criticality_result.score,
        "criticalityLevel": criticality_result.level,
    })

    return InvestigationResponse(
        incident_id=incident_id,
        drift=_drift_result_to_response(drift_result),
        attribution=_attribution_to_dict(attr_response),
        intelligence=intelligence_result.model_dump(by_alias=True),
        criticality=criticality_result,
        environment=env_status,
        status="completed",
    )
