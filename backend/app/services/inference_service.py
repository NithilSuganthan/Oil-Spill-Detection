"""Inference orchestration — the Phase 1B core pipeline.

    Sentinel-1-like raster
        ↓  SceneInput
    model adapter .preprocess() / .predict()
        ↓  probability mask
    threshold -> morphological cleanup -> connected components
        ↓  polygons (raster CRS)
    georeference to EPSG:4326
        ↓  WGS84 slick polygons
    geodesic area/perimeter + model confidence
        ↓  SpillIncident entities
    repository (PostGIS or in-memory dev)
        ↓  SSE event per detection

CONFIDENCE here is MODEL CONFIDENCE (mean predicted probability over the
polygon). It is NOT a validation metric such as IoU/F1 — see
docs/ml-integration-contract.md.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from app.config import Settings
from app.db.repository import SpillRepository
from app.domain.entities import (
    ModelRun,
    SatelliteSceneRecord,
    SpillIncident,
)
from app.domain.regions import classify_region
from app.geospatial.area import compute_metrics, crs_is_geographic, reproject_geometry
from app.geospatial.mask import morphological_cleanup, threshold_mask
from app.geospatial.polygon import mask_to_polygons, simplify_polygon
from app.geospatial.raster import RasterData, read_raster
from app.inference.base import OilSpillModel, SceneInput
from app.services.event_hub import EventHub

logger = logging.getLogger(__name__)

WGS84 = "EPSG:4326"


class InferenceService:
    def __init__(
        self,
        repo: SpillRepository,
        settings: Settings,
        event_hub: EventHub | None = None,
    ) -> None:
        self._repo = repo
        self._settings = settings
        self._hub = event_hub

    # ------------------------------------------------------------------
    def process_scene(
        self,
        scene: SatelliteSceneRecord,
        raster_path: str | Path,
        *,
        model: OilSpillModel,
    ) -> tuple[list[SpillIncident], str, int]:
        """Run the full detection pipeline for one scene.

        Returns (created incidents, model_run id, inference_time_ms).
        Incidents are persisted and published to the event hub.
        """
        started_at = datetime.now(timezone.utc)
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        run = ModelRun(
            id=run_id,
            scene_id=scene.id,
            model_name=model.name,
            model_version=model.version,
            started_at=started_at,
            status="running",
        )
        self._repo.add_model_run(run)
        self._repo.update_scene_status(scene.id, "processing")

        try:
            raster: RasterData = read_raster(raster_path)

            scene_input = SceneInput(
                scene=scene,
                intensity=raster.data,
                transform=raster.transform,
                crs=raster.crs,
            )
            preprocessed = model.preprocess(scene_input)
            prediction = model.predict(preprocessed)

            incidents = self._postprocess_to_incidents(
                scene=scene,
                probability=prediction.probability_mask,
                transform=preprocessed.spatial_transform,
                crs=preprocessed.crs,
                raster_size=(raster.data.shape[1], raster.data.shape[0]),
                model=model,
                inference_time_ms=prediction.inference_time_ms,
            )

            completed_at = datetime.now(timezone.utc)
            self._repo.update_model_run(
                run_id,
                status="completed",
                completed_at=completed_at,
                inference_time_ms=prediction.inference_time_ms,
            )
            self._repo.update_scene_status(scene.id, "processed", processed_at=completed_at)

            for inc in incidents:
                self._publish(inc)
            return incidents, run_id, prediction.inference_time_ms

        except Exception as exc:  # noqa: BLE001 — record and re-raise
            self._repo.update_model_run(
                run_id,
                status="failed",
                completed_at=datetime.now(timezone.utc),
                error_message=str(exc),
            )
            self._repo.update_scene_status(scene.id, "failed")
            raise

    # ------------------------------------------------------------------
    def _postprocess_to_incidents(
        self,
        *,
        scene: SatelliteSceneRecord,
        probability: np.ndarray,
        transform,
        crs,
        raster_size: tuple[int, int],
        model: OilSpillModel,
        inference_time_ms: int,
    ) -> list[SpillIncident]:
        binary = threshold_mask(probability, self._settings.model_threshold)
        binary = morphological_cleanup(binary)

        polys_crs = mask_to_polygons(binary, transform, min_area_px=4)
        if not crs_is_geographic(crs):
            polys_wgs84 = [reproject_geometry(p, crs, WGS84) for p in polys_crs]
        else:
            polys_wgs84 = polys_crs

        # tolerance is configured in metres; simplify BEFORE reprojection if the
        # raster CRS is projected, otherwise approximate degrees (~1 m ≈ 9e-6°).
        simplified: list = []
        tol_m = self._settings.polygon_simplify_tolerance_m
        for poly_crs, poly_wgs in zip(polys_crs, polys_wgs84):
            if crs_is_geographic(crs):
                simplified.append(poly_wgs.simplify(tol_m * 9e-6, preserve_topology=True))
            else:
                simplified.append(reproject_geometry(
                    poly_crs.simplify(tol_m, preserve_topology=True), crs, WGS84
                ))

        incidents: list[SpillIncident] = []
        detected_at = (scene.acquired_at or datetime.now(timezone.utc)) + timedelta(minutes=11)

        for idx, poly in enumerate(simplified, start=1):
            metrics = compute_metrics(poly)
            if metrics.area_km2 < self._settings.min_poly_area_km2:
                continue

            confidence = self._polygon_confidence(poly, crs, probability, transform, raster_size)
            if confidence < 0.05:
                continue

            geojson = {
                "type": "Polygon",
                "coordinates": [[[round(x, 5), round(y, 5)] for x, y in poly.exterior.coords]],
            }
            region = classify_region(metrics.centroid_lon, metrics.centroid_lat)

            incidents.append(
                SpillIncident(
                    id=self._next_incident_id(detected_at),
                    scene_id=scene.id,
                    confidence=round(confidence, 3),
                    area_km2=round(metrics.area_km2, 2),
                    perimeter_km=round(metrics.perimeter_km, 2),
                    centroid_lon=round(metrics.centroid_lon, 5),
                    centroid_lat=round(metrics.centroid_lat, 5),
                    geometry=geojson,
                    bbox=tuple(round(v, 5) for v in metrics.bbox),  # type: ignore[arg-type]
                    detected_at=detected_at,
                    region=region,
                    location_description=f"{region} · Detected from SAR scene",
                    satellite=scene.platform,
                    model_name=model.name,
                    model_version=model.version,
                    status="completed",
                    wind_speed_kts=None,
                    estimated_volume_tons=None,  # never fabricated by this pipeline
                    is_demo=scene.is_demo,
                )
            )
        logger.info(
            "Scene %s: %d candidate polygons -> %d incidents (%d ms inference)",
            scene.id, len(polys_wgs84), len(incidents), inference_time_ms,
        )
        return incidents

    # ------------------------------------------------------------------
    def _polygon_confidence(
        self,
        poly_wgs84,
        src_crs,
        probability: np.ndarray,
        transform,
        raster_size: tuple[int, int],
    ) -> float:
        """MODEL CONFIDENCE = mean predicted probability inside the polygon."""
        import rasterio.features

        poly_src = (
            reproject_geometry(poly_wgs84, WGS84, src_crs)
            if not crs_is_geographic(src_crs)
            else poly_wgs84
        )
        width, height = raster_size
        inside = rasterio.features.geometry_mask(
            [poly_src], out_shape=(height, width), transform=transform, invert=True, all_touched=True
        )
        count = int(inside.sum())
        if count == 0:
            return 0.0
        return float(np.clip(probability[inside].mean(), 0.0, 1.0))

    # ------------------------------------------------------------------
    def _next_incident_id(self, detected_at: datetime) -> str:
        ist_date = detected_at + timedelta(hours=5, minutes=30)
        stamp = ist_date.strftime("%y%m%d")
        existing = {
            i.id for i in self._repo.list_incidents()
            if i.id.startswith(f"IN-{stamp}")
        }
        seq = 1
        while f"IN-{stamp}-{seq:03d}" in existing:
            seq += 1
        return f"IN-{stamp}-{seq:03d}"

    def _persist(self, incident: SpillIncident) -> None:
        self._repo.add_incident(incident)

    def _publish(self, incident: SpillIncident) -> None:
        self._persist(incident)
        if self._hub is not None:
            self._hub.publish("detection.created", {"incidentId": incident.id})
