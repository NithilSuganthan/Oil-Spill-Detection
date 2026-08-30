"""In-memory repository — DEVELOPMENT / TESTS ONLY.

Used when DATABASE_URL is not set (or not Postgres) so the full pipeline can
run and be verified locally without a PostgreSQL/PostGIS server.
NOT suitable for production; no persistence across restarts.
"""

from __future__ import annotations

import threading
from datetime import datetime

from app.db.repository import BBox, SpillRepository
from app.domain.entities import ModelRun, SatelliteSceneRecord, SpillIncident


def _in_bbox(
    west: float, south: float, east: float, north: float, bbox: BBox | None
) -> bool:
    if bbox is None:
        return True
    bw, bs, be, bn = bbox
    return not (east < bw or west > be or north < bs or south > bn)


class InMemoryRepository(SpillRepository):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._incidents: dict[str, SpillIncident] = {}
        self._scenes: dict[str, SatelliteSceneRecord] = {}
        self._model_runs: dict[str, ModelRun] = {}

    # -- incidents ---------------------------------------------------------
    def list_incidents(
        self,
        *,
        min_confidence: float | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        bbox: BBox | None = None,
        include_demo: bool = True,
    ) -> list[SpillIncident]:
        with self._lock:
            out: list[SpillIncident] = []
            for inc in self._incidents.values():
                if min_confidence is not None and inc.confidence < min_confidence:
                    continue
                if start is not None and inc.detected_at < start:
                    continue
                if end is not None and inc.detected_at > end:
                    continue
                if not include_demo and inc.is_demo:
                    continue
                w, s, e, n = inc.bbox
                if not _in_bbox(w, s, e, n, bbox):
                    continue
                out.append(inc)
            out.sort(key=lambda i: i.detected_at, reverse=True)
            return out

    def get_incident(self, incident_id: str) -> SpillIncident | None:
        with self._lock:
            return self._incidents.get(incident_id)

    def add_incident(self, incident: SpillIncident) -> None:
        with self._lock:
            self._incidents[incident.id] = incident

    def count_incidents(self) -> int:
        with self._lock:
            return len(self._incidents)

    # -- scenes ------------------------------------------------------------
    def list_scenes(self, *, bbox: BBox | None = None) -> list[SatelliteSceneRecord]:
        with self._lock:
            out = []
            for sc in self._scenes.values():
                fp = sc.footprint or (0.0, 0.0, 0.0, 0.0)
                if _in_bbox(fp[0], fp[1], fp[2], fp[3], bbox):
                    out.append(sc)
            out.sort(key=lambda s: s.acquired_at or datetime.min, reverse=True)
            return out

    def get_scene(self, scene_id: str) -> SatelliteSceneRecord | None:
        with self._lock:
            return self._scenes.get(scene_id)

    def add_scene(self, scene: SatelliteSceneRecord) -> None:
        with self._lock:
            self._scenes[scene.id] = scene

    def update_scene_status(
        self, scene_id: str, status: str, processed_at: datetime | None = None
    ) -> None:
        with self._lock:
            sc = self._scenes.get(scene_id)
            if sc:
                sc.status = status  # type: ignore[assignment]
                if processed_at:
                    sc.processed_at = processed_at

    # -- model runs ----------------------------------------------------------
    def add_model_run(self, run: ModelRun) -> None:
        with self._lock:
            self._model_runs[run.id] = run

    def update_model_run(self, run_id: str, **fields: object) -> None:
        with self._lock:
            run = self._model_runs.get(run_id)
            if not run:
                return
            for k, v in fields.items():
                setattr(run, k, v)

    def list_model_runs(self, scene_id: str | None = None) -> list[ModelRun]:
        with self._lock:
            runs = list(self._model_runs.values())
            if scene_id:
                runs = [r for r in runs if r.scene_id == scene_id]
            return sorted(runs, key=lambda r: r.started_at, reverse=True)
