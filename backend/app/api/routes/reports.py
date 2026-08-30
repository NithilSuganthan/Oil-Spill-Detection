"""Report API routes — investigation report generation and retrieval.

Endpoints:
  POST /reports/investigation/{incident_id} — generate investigation report
  GET  /reports/investigation/{incident_id} — get existing report
  GET  /reports — list all reports
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_repo, get_settings_dep
from app.config import Settings
from app.db.repository import SpillRepository
from app.schemas.evidence import InvestigationEvidence
from app.services.drift_engine import FirstOrderDriftProvider, drift_result_to_source_estimate
from app.services.evidence_builder import build_investigation_evidence
from app.services.report_provider import InvestigationReport
from app.services.report_repository import StoredReport, get_report_repository

router = APIRouter(tags=["reports"])


def _get_report_provider(settings: Settings):
    """Create report provider based on configuration."""
    if settings.groq_api_key:
        from app.services.groq_report_provider import GroqReportProviderImpl
        return GroqReportProviderImpl(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
        )
    from app.services.mock_report_provider import MockReportProvider
    return MockReportProvider()


def _get_drift_provider(settings: Settings):
    """Create drift provider with configured environmental data source."""
    if settings.environmental_provider == "real" and settings.cmems_username:
        from app.services.environmental_real_provider import RealEnvironmentalProvider
        env_provider = RealEnvironmentalProvider(
            cmems_username=settings.cmems_username,
            cmems_password=settings.cmems_password,
            cds_api_key=settings.cds_api_key,
            cds_api_url=settings.cds_api_url,
        )
    else:
        from app.services.environmental_mock_provider import MockEnvironmentalProvider
        env_provider = MockEnvironmentalProvider()
    return FirstOrderDriftProvider(environmental_provider=env_provider, settings=settings)


def _get_ais_provider(settings: Settings):
    """Create AIS provider based on configuration."""
    if settings.ais_provider == "gfw" and settings.gfw_api_token:
        from app.services.ais_gfw_provider import GlobalFishingWatchAISProvider
        return GlobalFishingWatchAISProvider(api_token=settings.gfw_api_token)
    from app.services.ais_mock_provider import MockAISProvider
    return MockAISProvider()


def _prepare_real_cache(
    provider: FirstOrderDriftProvider,
    lat: float,
    lon: float,
    observation_time: datetime,
    settings: Settings,
) -> str:
    """Prepare cache for real environmental provider if applicable."""
    import logging
    import math
    from datetime import timedelta

    from app.services.environmental_real_provider import RealEnvironmentalProvider

    if not isinstance(provider._env, RealEnvironmentalProvider):
        return "DEMO"

    pad = settings.env_cache_bbox_pad_deg
    bbox = (lon - pad, lat - pad, lon + pad, lat + pad)

    n_hours = math.ceil(settings.drift_hours) + 1
    timesteps = [
        observation_time - timedelta(hours=h) for h in range(n_hours)
    ]

    try:
        provider._env.prepare_cache(bbox, timesteps)
        return "REAL"
    except RuntimeError as exc:
        logger = logging.getLogger(__name__)
        logger.warning(
            "Real environmental data unavailable, falling back to mock: %s", exc,
        )
        from app.services.environmental_mock_provider import MockEnvironmentalProvider
        provider._env = MockEnvironmentalProvider()
        return "DATA_UNAVAILABLE"


@router.post("/reports/investigation/{incident_id}")
def generate_report(
    incident_id: str,
    repo: SpillRepository = Depends(get_repo),
    settings: Settings = Depends(get_settings_dep),
):
    """Generate investigation report for a completed investigation.

    1. Load incident
    2. Run drift → source estimate
    3. Run AIS correlation
    4. Run intelligence assembly
    5. Build InvestigationEvidence
    6. Send to Groq (or mock)
    7. Store and return report
    """
    incident = repo.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    # Run drift
    drift_provider = _get_drift_provider(settings)
    obs_time = incident.detected_at.replace(tzinfo=timezone.utc) \
        if incident.detected_at.tzinfo is None else incident.detected_at

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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Drift analysis failed: {exc}")

    # Convert to SourceEstimate
    source_estimate = drift_result_to_source_estimate(drift_result)

    # Run AIS correlation
    ais_provider = _get_ais_provider(settings)
    from app.services.ais_correlation import analyze_attribution
    try:
        attribution_result = analyze_attribution(
            incident_id=incident_id,
            source=source_estimate,
            provider=ais_provider,
            settings=settings,
            coverage_known=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AIS analysis failed: {exc}")

    # Run intelligence assembly
    from app.services.intelligence_assembly import assemble_intelligence
    intelligence_result = assemble_intelligence(
        incident=incident,
        candidates=attribution_result.candidates,
        settings=settings,
    )

    # Build evidence
    evidence = build_investigation_evidence(
        incident=incident,
        drift_result=drift_result,
        candidates=attribution_result.candidates,
        intelligence=intelligence_result,
        settings=settings,
        environmental_provider_name=settings.environmental_provider,
        ais_provider_name=settings.ais_provider,
    )

    # Generate report
    report_provider = _get_report_provider(settings)
    try:
        report = report_provider.generate_report(evidence.model_dump(by_alias=True))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {exc}")

    # Store report
    report_id = f"RPT-{incident_id}-{uuid.uuid4().hex[:8]}"
    stored_report = StoredReport(
        report_id=report_id,
        incident_id=incident_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        provider=report_provider.name,
        model=settings.groq_model if settings.groq_api_key else "mock",
        evidence_version="1.0",
        prompt_version="1.0",
        report_json=report.model_dump(by_alias=True),
    )

    repo_store = get_report_repository()
    repo_store.store_report(stored_report)

    return {
        "reportId": report_id,
        "incidentId": incident_id,
        "generatedAt": stored_report.generated_at,
        "provider": report_provider.name,
        "model": settings.groq_model if settings.groq_api_key else "mock",
        "evidenceVersion": "1.0",
        "promptVersion": "1.0",
        "report": report.model_dump(by_alias=True),
    }


@router.get("/reports/investigation/{incident_id}")
def get_report(
    incident_id: str,
):
    """Get existing investigation report for an incident."""
    repo_store = get_report_repository()
    stored = repo_store.get_report_by_incident(incident_id)
    if stored is None:
        raise HTTPException(
            status_code=404,
            detail=f"No report found for incident {incident_id}. Generate one first.",
        )
    return {
        "reportId": stored.report_id,
        "incidentId": stored.incident_id,
        "generatedAt": stored.generated_at,
        "provider": stored.provider,
        "model": stored.model,
        "evidenceVersion": stored.evidence_version,
        "promptVersion": stored.prompt_version,
        "report": stored.report_json,
    }


@router.get("/reports")
def list_reports():
    """List all reports."""
    repo_store = get_report_repository()
    reports = repo_store.list_reports()
    return [
        {
            "reportId": r.report_id,
            "incidentId": r.incident_id,
            "generatedAt": r.generated_at,
            "provider": r.provider,
            "model": r.model,
        }
        for r in reports
    ]
