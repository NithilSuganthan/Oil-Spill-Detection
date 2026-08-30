"""Background processing pipeline with explicit job states.

    DISCOVERED -> QUEUED -> DOWNLOADING -> DOWNLOADED -> PREPROCESSING ->
    READY_FOR_INFERENCE -> INFERENCE -> POSTPROCESSING -> COMPLETED
    (any step may transition to FAILED)

Jobs run on worker threads so HTTP requests never block on downloads or
processing. Every transition is persisted on the scene record and published
to the SSE event hub.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable

from app.config import Settings
from app.db.repository import SpillRepository
from app.domain.entities import SatelliteSceneRecord
from app.satellite.aoi import AreaOfInterest
from app.satellite.providers.base import (
    DownloadOptions,
    SatelliteSceneProvider,
)
from app.satellite.storage import StorageBackend
from app.services.event_hub import EventHub

logger = logging.getLogger(__name__)


class JobState(str, Enum):
    DISCOVERED = "DISCOVERED"
    QUEUED = "QUEUED"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOADED = "DOWNLOADED"
    # real Sentinel-1 GRD preprocessing (Phase 2C)
    EXTRACTING = "EXTRACTING"
    CALIBRATING = "CALIBRATING"
    GEOREFERENCING = "GEOREFERENCING"
    VALIDATING = "VALIDATING"
    PROCESSED = "PROCESSED"
    # legacy generic chain retained for mock/demo scenes and future ML phase
    PREPROCESSING = "PREPROCESSING"
    READY_FOR_INFERENCE = "READY_FOR_INFERENCE"
    INFERENCE = "INFERENCE"
    POSTPROCESSING = "POSTPROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


TERMINAL_STATES = {JobState.COMPLETED, JobState.FAILED, JobState.PROCESSED}

# SSE event names emitted by this pipeline (detection.created comes from
# InferenceService when incidents are persisted).
EVENT_DISCOVERED = "scene.discovered"
EVENT_DOWNLOAD_STARTED = "scene.download.started"
EVENT_DOWNLOAD_COMPLETED = "scene.download.completed"
EVENT_EXTRACTION_STARTED = "scene.extraction.started"
EVENT_EXTRACTION_COMPLETED = "scene.extraction.completed"
EVENT_CALIBRATION_STARTED = "scene.calibration.started"
EVENT_CALIBRATION_COMPLETED = "scene.calibration.completed"
EVENT_GEOREFERENCING_STARTED = "scene.georeferencing.started"
EVENT_GEOREFERENCING_COMPLETED = "scene.georeferencing.completed"
EVENT_PREPROCESSING_COMPLETED = "scene.preprocessing.completed"
EVENT_PREPROCESSING_STARTED = "scene.preprocessing.started"
EVENT_INFERENCE_STARTED = "scene.inference.started"
EVENT_INFERENCE_COMPLETED = "scene.inference.completed"
EVENT_PIPELINE_FAILED = "pipeline.failed"

# internal preprocessor callback -> (job state | None, SSE event | None)
_GRD_CB_MAP = {
    "EXTRACTING": (JobState.EXTRACTING, EVENT_EXTRACTION_STARTED),
    "EXTRACTED": (None, EVENT_EXTRACTION_COMPLETED),
    "GEOLOCATION_PARSED": (None, None),
    "CALIBRATION_STARTED": (JobState.CALIBRATING, EVENT_CALIBRATION_STARTED),
    "CALIBRATION_COMPLETED": (None, EVENT_CALIBRATION_COMPLETED),
    "GEOREFERENCING_STARTED": (JobState.GEOREFERENCING, EVENT_GEOREFERENCING_STARTED),
    "GEOREFERENCING_COMPLETED": (None, EVENT_GEOREFERENCING_COMPLETED),
    "VALIDATING": (JobState.VALIDATING, None),
    "VALIDATED": (None, EVENT_PREPROCESSING_COMPLETED),
}


@dataclass
class PipelineJob:
    id: str
    scene_id: str
    state: JobState = JobState.QUEUED
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "jobId": self.id,
            "sceneId": self.scene_id,
            "state": self.state.value,
            "error": self.error,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "history": self.history,
        }


class PipelineJobManager:
    """Creates, tracks and executes scene-processing jobs."""

    def __init__(
        self,
        repo: SpillRepository,
        provider: SatelliteSceneProvider,
        storage: StorageBackend,
        settings: Settings,
        event_hub: EventHub | None = None,
        aoi: AreaOfInterest | None = None,
        model_handle=None,
        inference_service_factory: Callable[[], object] | None = None,
    ) -> None:
        self._repo = repo
        self._provider = provider
        self._storage = storage
        self._settings = settings
        self._hub = event_hub
        self._aoi = aoi
        self._model_handle = model_handle
        self._inference_factory = inference_service_factory
        self._jobs: dict[str, PipelineJob] = {}
        self._lock = threading.RLock()
        self._tls = threading.local()   # per-worker current scene id

    # ------------------------------------------------------------------ API
    def enqueue(self, scene_id: str) -> PipelineJob:
        scene = self._repo.get_scene(scene_id)
        if scene is None:
            raise KeyError(f"Scene {scene_id} not found")

        active = [j for j in self.list_jobs(scene_id=scene_id)
                  if j.state not in TERMINAL_STATES]
        if active:
            raise RuntimeError(f"Scene {scene_id} already has an active job")

        job = PipelineJob(id=f"job-{uuid.uuid4().hex[:12]}", scene_id=scene_id)
        with self._lock:
            self._jobs[job.id] = job
        self._set_state(job, JobState.QUEUED)
        worker = threading.Thread(
            target=self._run, args=(job,), name=f"pipeline-{job.id}", daemon=True
        )
        worker.start()
        return job

    def get(self, job_id: str) -> PipelineJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self, scene_id: str | None = None) -> list[PipelineJob]:
        with self._lock:
            jobs = list(self._jobs.values())
        if scene_id:
            jobs = [j for j in jobs if j.scene_id == scene_id]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    # ------------------------------------------------------------ internals
    def _run(self, job: PipelineJob) -> None:
        try:
            self._execute(job)
        except Exception as exc:  # noqa: BLE001 — jobs record their own failure
            logger.exception("Pipeline job %s failed", job.id)
            self._set_state(job, JobState.FAILED, error=str(exc))
            self._publish(EVENT_PIPELINE_FAILED, {
                "jobId": job.id, "sceneId": job.scene_id, "error": str(exc),
            })

    def _execute(self, job: PipelineJob) -> None:
        self._tls.scene_id = job.scene_id
        scene = self._require_scene(job)

        # ---- download (skipped when a usable artifact already exists) ----
        artifact_key = self._artifact_key(scene)
        if not self._storage.exists(artifact_key):
            self._set_state(job, JobState.DOWNLOADING)
            self._publish(EVENT_DOWNLOAD_STARTED, {"jobId": job.id, "sceneId": scene.id})
            opts = DownloadOptions(
                max_retries=self._settings.download_max_retries,
                retry_backoff_seconds=self._settings.download_retry_backoff_seconds,
                chunk_size_mb=float(self._settings.download_chunk_mb),
            )
            stored = self._provider.download_scene(scene, self._storage, opts)
            self._update_scene(image_path=stored.path or stored.url,
                               file_size_bytes=stored.size_bytes)
            self._publish(EVENT_DOWNLOAD_COMPLETED, {
                "jobId": job.id, "sceneId": scene.id,
                "sizeBytes": stored.size_bytes, "storageKey": stored.key,
            })
        self._set_state(job, JobState.DOWNLOADED)

        if (scene.source_provider or "mock") == "copernicus":
            # ---- real Sentinel-1 GRD path: calibration only, NO inference --
            self._run_grd_preprocessing(job, scene)
            return

        # ---- mock/demo chain retained for development scenes --------------
        self._run_mock_chain(job, scene)

    def _run_grd_preprocessing(self, job: PipelineJob, scene: SatelliteSceneRecord) -> None:
        """Real Sentinel-1 acquisition -> calibrated, georeferenced products.

        Deliberately STOPS after preprocessing/validation: no ML model runs
        until the trained-model contract is delivered.
        """
        from app.satellite.grd_preprocess import GrdConfig, GrdPreprocessor

        def cb(name: str, detail: dict | None) -> None:
            state, event = _GRD_CB_MAP.get(name, (None, None))
            if state is not None:
                self._set_state(job, state)
            if event is not None:
                payload = {"jobId": job.id, "sceneId": scene.id}
                if detail:
                    payload.update({k: v for k, v in detail.items() if isinstance(v, (str, int, float, bool))})
                self._publish(event, payload)

        product_zip = self._storage.get_path(self._artifact_key(scene))
        workspace_root = Path(self._settings.scene_storage_dir) / "processed"
        pre = GrdPreprocessor(
            scene.id,
            workspace_root,
            config=GrdConfig.from_settings(self._settings),
            state_cb=cb,
        )
        report = pre.run(product_zip, expected_bbox=scene.footprint)
        self._set_state(job, JobState.PROCESSED)
        self._update_scene(
            status="processed",
            processed_at=datetime.now(timezone.utc),
            pipeline_state=JobState.PROCESSED.value,
            metadata_extra={**(scene.metadata_extra or {}),
                            "preprocessing_report": str(
                                Path(workspace_root) / scene.id / "metadata" / "preprocessing_report.json"
                            )},
        )
        logger.info("GRD preprocessing complete for %s (%ss)", scene.id, report.get("elapsed_s"))

    def _run_mock_chain(self, job: PipelineJob, scene: SatelliteSceneRecord) -> None:
        self._set_state(job, JobState.PREPROCESSING)
        self._publish(EVENT_PREPROCESSING_STARTED, {"jobId": job.id, "sceneId": scene.id})
        processed_local = self._preprocess(scene)
        self._set_state(job, JobState.READY_FOR_INFERENCE)
        self._publish(EVENT_PREPROCESSING_COMPLETED, {
            "jobId": job.id, "sceneId": scene.id,
            "processedPath": processed_local.name,
        })

        # ---- inference (existing Phase 1B service + model adapter) ----
        self._set_state(job, JobState.INFERENCE)
        self._publish(EVENT_INFERENCE_STARTED, {"jobId": job.id, "sceneId": scene.id})
        incidents = self._run_inference(scene, processed_local)
        self._publish(EVENT_INFERENCE_COMPLETED, {
            "jobId": job.id, "sceneId": scene.id, "incidents": len(incidents),
        })

        # ---- post-processing: web preview from the processed raster ----
        self._set_state(job, JobState.POSTPROCESSING)
        preview_key = f"previews/{scene.id}.png"
        from app.satellite.preview import generate_preview_png

        generate_preview_png(processed_local, self._storage.get_path(preview_key))
        self._update_scene(preview_path=self._storage.get_url(preview_key))

        self._set_state(job, JobState.COMPLETED)
        logger.info("Pipeline job %s completed for scene %s (%d incidents)",
                    job.id, scene.id, len(incidents))

    def _preprocess(self, scene: SatelliteSceneRecord):
        """Open the acquired artifact and run the configurable stage chain."""
        import numpy as np
        import rasterio

        from app.geospatial.raster import RasterData
        from app.satellite.preprocessing import build_pipeline, run_pipeline

        raw_path = self._storage.get_path(self._artifact_key(scene))
        src = _resolve_raster_source(raw_path)   # handles SAFE zip archives

        with rasterio.open(src) as dataset:
            raster = RasterData(
                data=dataset.read(1).astype(np.float32),
                transform=dataset.transform,
                crs=dataset.crs,
                meta={"width": dataset.width, "height": dataset.height,
                      "dtype": dataset.dtypes[0], "nodata": dataset.nodata},
            )

        stages = build_pipeline(self._settings.preprocessing_stages)
        if self._aoi is not None:
            stages = [
                ("subset_bbox", {"bbox": list(self._aoi.bbox)})
                if name == "subset_bbox" else (name, p)
                for name, p in stages
            ]
        processed, report = run_pipeline(raster, stages)

        out_key = f"preprocessed/{scene.id}.tif"
        out_path = self._storage.get_path(out_key)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        profile = {
            "driver": "GTiff",
            "width": processed.data.shape[1],
            "height": processed.data.shape[0],
            "count": 1,
            "dtype": "float32",
            "crs": processed.crs,
            "transform": processed.transform,
            "nodata": -9999.0,
        }
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(np.nan_to_num(processed.data, nan=-9999.0).astype(np.float32), 1)
            dst.update_tags(preprocessing=json.dumps(report.to_dict()))
        self._update_scene(image_path=str(out_path))
        return out_path

    def _run_inference(self, scene: SatelliteSceneRecord, raster_path):
        if self._inference_factory is None or self._model_handle is None:
            raise RuntimeError("Pipeline not wired to an inference service")
        inference = self._inference_factory()
        model = self._model_handle.get()
        incidents, _run_id, _ms = inference.process_scene(
            scene, raster_path, model=model
        )
        return incidents

    def _require_scene(self, job: PipelineJob) -> SatelliteSceneRecord:
        scene = self._repo.get_scene(job.scene_id)
        if scene is None:
            raise LookupError(f"Scene {job.scene_id} disappeared mid-job")
        return scene

    def _artifact_key(self, scene: SatelliteSceneRecord) -> str:
        from app.storage_keys import product_key_for

        return product_key_for(scene.id, mock=(scene.source_provider or "mock") == "mock")

    def _update_scene(self, **fields) -> None:
        """Patch the current job's scene record (worker-thread scoped)."""
        scene_id = getattr(self._tls, "scene_id", None)
        if scene_id is None:
            return
        scene = self._repo.get_scene(scene_id)
        if scene is None:
            return
        for k, v in fields.items():
            setattr(scene, k, v)
        self._repo.add_scene(scene)

    def _set_state(self, job: PipelineJob, state: JobState, *, error: str | None = None) -> None:
        job.state = state
        job.error = error
        job.updated_at = datetime.now(timezone.utc)
        job.history.append({"state": state.value, "at": job.updated_at.isoformat()})
        self._update_scene(pipeline_state=state.value)
        logger.info("Job %s [%s] -> %s", job.id, job.scene_id, state.value)

    def _publish(self, event_type: str, payload: dict) -> None:
        if self._hub is not None:
            self._hub.publish(event_type, payload)


def _resolve_raster_source(raw_path):
    """Real GRD products arrive as .zip SAFE archives; locate the VV
    measurement GeoTIFF inside and expose it through GDAL's /vsizip/ driver.
    Plain GeoTIFFs pass through unchanged."""
    raw = str(raw_path)
    if not raw.lower().endswith(".zip"):
        return raw_path

    import re
    import zipfile

    with zipfile.ZipFile(raw) as zf:
        names = zf.namelist()
    measurement = sorted(
        n for n in names if re.search(r"measurement/.*\.tiff?$", n, re.IGNORECASE)
    )
    vv = next((n for n in measurement if "vv" in n.lower()), None)
    inner = vv or (measurement[0] if measurement else None)
    if inner is None:
        raise IOError(f"No measurement GeoTIFF found inside {raw}")
    return f"/vsizip/{raw}/{inner}"
