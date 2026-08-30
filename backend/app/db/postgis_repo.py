"""PostGIS repository — production persistence (PostgreSQL + PostGIS)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models_orm import Base
from app.db.repository import BBox, SpillRepository
from app.db.row_mapping import (
    incident_to_row,
    row_to_incident,
    row_to_run,
    row_to_scene,
    run_to_row,
    scene_to_row,
)
from app.domain.entities import ModelRun, SatelliteSceneRecord, SpillIncident


class PostgisRepository(SpillRepository):
    def __init__(self, database_url: str, echo: bool = False) -> None:
        self._engine = create_engine(database_url, echo=echo, pool_pre_ping=True)
        self._session_factory: sessionmaker[Session] = sessionmaker(bind=self._engine)

    def create_tables(self) -> None:
        """Create tables if absent.

        Production deployments should run the SQL migration in
        db/migrations/001_init_postgis.sql instead (it also creates the
        PostGIS extension explicitly).
        """
        Base.metadata.create_all(self._engine)

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
        stmt = select(SpillIncidentRow)
        if min_confidence is not None:
            stmt = stmt.where(SpillIncidentRow.confidence >= min_confidence)
        if start is not None:
            stmt = stmt.where(SpillIncidentRow.detected_at >= start)
        if end is not None:
            stmt = stmt.where(SpillIncidentRow.detected_at <= end)
        if not include_demo:
            stmt = stmt.where(SpillIncidentRow.is_demo.is_(False))
        if bbox is not None:
            w, s, e, n = bbox
            from geoalchemy2.functions import ST_MakeEnvelope
            from sqlalchemy import func

            env = func.ST_GeomFromText(f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))", 4326)
            stmt = stmt.where(
                SpillIncidentRow.centroid.ST_Within(env)  # type: ignore[attr-defined]
            )
        stmt = stmt.order_by(SpillIncidentRow.detected_at.desc())
        with Session(self._engine) as session:
            rows = session.execute(stmt).scalars().all()
            return [row_to_incident(r) for r in rows]

    def get_incident(self, incident_id: str) -> SpillIncident | None:
        with Session(self._engine) as session:
            row = session.get(SpillIncidentRow, incident_id)
            return row_to_incident(row) if row else None

    def add_incident(self, incident: SpillIncident) -> None:
        with Session(self._engine) as session:
            session.merge(incident_to_row(incident))
            session.commit()

    def count_incidents(self) -> int:
        from sqlalchemy import func

        with Session(self._engine) as session:
            return int(session.scalar(func.count(SpillIncidentRow.id)) or 0)

    # -- scenes ------------------------------------------------------------
    def list_scenes(self, *, bbox: BBox | None = None) -> list[SatelliteSceneRecord]:
        stmt = select(SatelliteSceneRow).order_by(
            SatelliteSceneRow.acquisition_time.desc().nullslast()
        )
        if bbox is not None:
            from sqlalchemy import func

            w, s, e, n = bbox
            env = func.ST_GeomFromText(f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))", 4326)
            stmt = stmt.where(SatelliteSceneRow.footprint.ST_Intersects(env))  # type: ignore[attr-defined]
        with Session(self._engine) as session:
            rows = session.execute(stmt).scalars().all()
            return [row_to_scene(r) for r in rows]

    def get_scene(self, scene_id: str) -> SatelliteSceneRecord | None:
        with Session(self._engine) as session:
            row = session.get(SatelliteSceneRow, scene_id)
            return row_to_scene(row) if row else None

    def add_scene(self, scene: SatelliteSceneRecord) -> None:
        with Session(self._engine) as session:
            session.merge(scene_to_row(scene))
            session.commit()

    def update_scene_status(
        self, scene_id: str, status: str, processed_at: datetime | None = None
    ) -> None:
        with Session(self._engine) as session:
            row = session.get(SatelliteSceneRow, scene_id)
            if row:
                row.status = status
                if processed_at:
                    row.processing_time = processed_at
                session.commit()

    # -- model runs ----------------------------------------------------------
    def add_model_run(self, run: ModelRun) -> None:
        with Session(self._engine) as session:
            session.merge(run_to_row(run))
            session.commit()

    def update_model_run(self, run_id: str, **fields: object) -> None:
        with Session(self._engine) as session:
            row = session.get(ModelRunRow, run_id)
            if row:
                for k, v in fields.items():
                    setattr(row, k, v)
                session.commit()

    def list_model_runs(self, scene_id: str | None = None) -> list[ModelRun]:
        stmt = select(ModelRunRow).order_by(ModelRunRow.started_at.desc())
        if scene_id:
            stmt = stmt.where(ModelRunRow.scene_id == scene_id)
        with Session(self._engine) as session:
            rows = session.execute(stmt).scalars().all()
            return [row_to_run(r) for r in rows]
