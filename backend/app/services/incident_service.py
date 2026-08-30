"""Incident queries — thin service over the repository."""

from __future__ import annotations

from datetime import datetime

from app.db.repository import SpillRepository
from app.domain.entities import SpillIncident


class IncidentService:
    def __init__(self, repo: SpillRepository) -> None:
        self._repo = repo

    def list_incidents(
        self,
        *,
        min_confidence: float | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[SpillIncident]:
        return self._repo.list_incidents(
            min_confidence=min_confidence, start=start, end=end, bbox=bbox
        )

    def get_incident(self, incident_id: str) -> SpillIncident | None:
        return self._repo.get_incident(incident_id)

    def get_geometry(self, incident_id: str):
        inc = self._repo.get_incident(incident_id)
        return None if inc is None else inc.geometry
