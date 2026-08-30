from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_incident_service
from app.api.serializers import incident_to_response
from app.schemas.incident import IncidentResponse
from app.services.incident_service import IncidentService

router = APIRouter(prefix="/spills", tags=["incidents"])


@router.get("", response_model=list[IncidentResponse], response_model_by_alias=True)
def list_spills(
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    bbox: str | None = Query(
        default=None,
        description="Comma-separated west,south,east,north in EPSG:4326",
    ),
    svc: IncidentService = Depends(get_incident_service),
) -> list[IncidentResponse]:
    bbox_tuple = None
    if bbox:
        try:
            w, s, e, n = (float(v) for v in bbox.split(","))
            bbox_tuple = (w, s, e, n)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="bbox must be west,south,east,north") from exc
    incidents = svc.list_incidents(
        min_confidence=min_confidence, start=start, end=end, bbox=bbox_tuple
    )
    return [incident_to_response(i) for i in incidents]


@router.get("/{spill_id}", response_model=IncidentResponse, response_model_by_alias=True)
def get_spill(spill_id: str, svc: IncidentService = Depends(get_incident_service)) -> IncidentResponse:
    inc = svc.get_incident(spill_id)
    if inc is None:
        raise HTTPException(status_code=404, detail=f"Incident {spill_id} not found")
    return incident_to_response(inc)


@router.get("/{spill_id}/geometry", response_model_by_alias=True)
def get_spill_geometry(spill_id: str, svc: IncidentService = Depends(get_incident_service)):
    geojson = svc.get_geometry(spill_id)
    if geojson is None:
        raise HTTPException(status_code=404, detail=f"Incident {spill_id} not found")
    return {
        "type": "Feature",
        "properties": {"id": spill_id},
        "geometry": geojson,
    }
