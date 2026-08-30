"""Repository interface — the ONLY persistence boundary.

Two implementations exist:
  * PostgisRepository  (production; PostgreSQL + PostGIS via GeoAlchemy2)
  * InMemoryRepository (development/tests when no database server is available)

The service layer depends exclusively on this interface.
"""

from __future__ import annotations

import abc
from datetime import datetime

from app.domain.entities import ModelRun, SatelliteSceneRecord, SpillIncident

BBox = tuple[float, float, float, float]  # west, south, east, north


class SpillRepository(abc.ABC):
    # -- incidents ---------------------------------------------------------
    @abc.abstractmethod
    def list_incidents(
        self,
        *,
        min_confidence: float | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        bbox: BBox | None = None,
        include_demo: bool = True,
    ) -> list[SpillIncident]: ...

    @abc.abstractmethod
    def get_incident(self, incident_id: str) -> SpillIncident | None: ...

    @abc.abstractmethod
    def add_incident(self, incident: SpillIncident) -> None: ...

    @abc.abstractmethod
    def count_incidents(self) -> int: ...

    # -- scenes ------------------------------------------------------------
    @abc.abstractmethod
    def list_scenes(self, *, bbox: BBox | None = None) -> list[SatelliteSceneRecord]: ...

    @abc.abstractmethod
    def get_scene(self, scene_id: str) -> SatelliteSceneRecord | None: ...

    @abc.abstractmethod
    def add_scene(self, scene: SatelliteSceneRecord) -> None: ...

    @abc.abstractmethod
    def update_scene_status(self, scene_id: str, status: str, processed_at: datetime | None = None) -> None: ...

    # -- model runs ----------------------------------------------------------
    @abc.abstractmethod
    def add_model_run(self, run: ModelRun) -> None: ...

    @abc.abstractmethod
    def update_model_run(self, run_id: str, **fields: object) -> None: ...

    @abc.abstractmethod
    def list_model_runs(self, scene_id: str | None = None) -> list[ModelRun]: ...
