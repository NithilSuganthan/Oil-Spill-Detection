"""Attribution API routes — AIS vessel correlation endpoints.

Follows the existing API patterns:
- Prefix: /api/v1/attribution
- Dependencies via Depends()
- CamelModel response schemas
- SSE events via EventHub
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_event_hub_dep, get_repo, get_settings_dep
from app.config import Settings
from app.db.repository import SpillRepository
from app.domain.ais import SourceEstimate
from app.schemas.attribution import (
    AttributionRequest,
    AttributionResponse,
    CandidateVesselResponse,
    ScoreComponentsResponse,
    SearchWindowResponse,
)
from app.services.ais_correlation import analyze_attribution
from app.services.ais_mock_provider import MockAISProvider
from app.services.event_hub import EventHub
from app.services.intelligence_assembly import assemble_intelligence

router = APIRouter(prefix="/attribution", tags=["attribution"])


def _get_provider(settings: Settings):
    """Create the appropriate AIS provider based on settings."""
    if settings.ais_provider == "gfw" and settings.gfw_api_token:
        from app.services.ais_gfw_provider import GlobalFishingWatchAISProvider

        return GlobalFishingWatchAISProvider(api_token=settings.gfw_api_token)
    return MockAISProvider()


def _result_to_response(result, intelligence=None) -> AttributionResponse:
    """Convert domain AttributionResult to API response schema."""
    return AttributionResponse(
        incident_id=result.incident_id,
        search_window=SearchWindowResponse(
            start=result.search_window.start_time.isoformat(),
            end=result.search_window.end_time.isoformat(),
            center_lat=result.search_window.center_lat,
            center_lon=result.search_window.center_lon,
            radius_km=result.search_window.radius_km,
            time_window_hours=result.search_window.time_window_hours,
        ),
        coverage_known=result.coverage_known,
        provider=result.provider,
        dataset=result.dataset,
        candidate_count=result.candidate_count,
        candidates=[
            CandidateVesselResponse(
                mmsi=c.mmsi,
                vessel_name=c.vessel_name,
                imo=c.imo,
                vessel_type=c.vessel_type,
                number_of_observations=c.number_of_observations,
                closest_distance_km=c.closest_distance_km,
                closest_timestamp=c.closest_timestamp.isoformat() if c.closest_timestamp else None,
                closest_time_difference_minutes=c.closest_time_difference_minutes,
                mean_distance_km=c.mean_distance_km,
                first_observation=c.first_observation.isoformat() if c.first_observation else None,
                last_observation=c.last_observation.isoformat() if c.last_observation else None,
                attribution_score=c.attribution_score,
                score_components=ScoreComponentsResponse(**c.score_components) if c.score_components else None,
                quality_flags=c.quality_flags,
                human_review_required=c.human_review_required,
            )
            for c in result.candidates
        ],
        total_observations=result.total_observations,
        analyzed_at=result.analyzed_at.isoformat() if result.analyzed_at else None,
        provenance=result.provenance,
        intelligence=intelligence.model_dump(by_alias=True) if intelligence else None,
    )


@router.post("/analyze", response_model=AttributionResponse)
def analyze_incident(
    request: AttributionRequest,
    repo: SpillRepository = Depends(get_repo),
    settings: Settings = Depends(get_settings_dep),
    event_hub: EventHub = Depends(get_event_hub_dep),
):
    """Analyze AIS vessel correlation for a potential spill incident.

    Accepts an incident ID (or explicit lat/lon/time) and returns
    ranked potential source vessels with attribution scores.
    """
    # Load incident
    incident = repo.get_incident(request.incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {request.incident_id} not found")

    # Build source estimate from request or incident
    lat = request.latitude or incident.centroid_lat
    lon = request.longitude or incident.centroid_lon
    if request.observation_time:
        try:
            obs_time = datetime.fromisoformat(request.observation_time)
        except ValueError:
            obs_time = incident.detected_at
    else:
        obs_time = incident.detected_at

    # Ensure timezone-aware
    if obs_time.tzinfo is None:
        obs_time = obs_time.replace(tzinfo=timezone.utc)

    source = SourceEstimate(
        latitude=lat,
        longitude=lon,
        timestamp=obs_time,
        uncertainty_km=settings.ais_search_radius_km,
        uncertainty_hours=settings.ais_time_window_hours,
    )

    # Override settings if request provides custom values
    if request.search_radius_km is not None:
        settings.ais_search_radius_km = request.search_radius_km
    if request.time_window_hours is not None:
        settings.ais_time_window_hours = request.time_window_hours

    # Publish started event
    event_hub.publish("attribution.started", {"incidentId": request.incident_id})

    # Run analysis
    provider = _get_provider(settings)
    try:
        result = analyze_attribution(
            incident_id=request.incident_id,
            source=source,
            provider=provider,
            settings=settings,
            coverage_known=True,
        )
    except Exception as exc:
        event_hub.publish("attribution.failed", {
            "incidentId": request.incident_id,
            "error": str(exc),
        })
        raise HTTPException(status_code=500, detail=f"Attribution analysis failed: {exc}")

    # Assemble intelligence
    intelligence = assemble_intelligence(
        incident=incident,
        candidates=result.candidates,
        settings=settings,
    )

    # Publish completed event
    event_hub.publish("attribution.completed", {
        "incidentId": request.incident_id,
        "candidateCount": result.candidate_count,
    })

    return _result_to_response(result, intelligence)


@router.get("/{incident_id}", response_model=AttributionResponse)
def get_attribution(
    incident_id: str,
    repo: SpillRepository = Depends(get_repo),
    settings: Settings = Depends(get_settings_dep),
):
    """Retrieve or perform attribution analysis for an incident.

    This is a convenience endpoint that runs the analysis on GET
    (suitable for development; in production POST /analyze is preferred).
    """
    incident = repo.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    source = SourceEstimate(
        latitude=incident.centroid_lat,
        longitude=incident.centroid_lon,
        timestamp=incident.detected_at.replace(tzinfo=timezone.utc)
        if incident.detected_at.tzinfo is None
        else incident.detected_at,
        uncertainty_km=settings.ais_search_radius_km,
        uncertainty_hours=settings.ais_time_window_hours,
    )

    provider = _get_provider(settings)
    result = analyze_attribution(
        incident_id=incident_id,
        source=source,
        provider=provider,
        settings=settings,
    )

    # Assemble intelligence
    from app.services.intelligence_assembly import assemble_intelligence
    intelligence = assemble_intelligence(
        incident=incident,
        candidates=result.candidates,
        settings=settings,
    )

    return _result_to_response(result, intelligence)
