"""Run the full detection pipeline on a synthetic scene and print results.

Usage:
    python scripts/run_pipeline_demo.py

DEVELOPMENT DEMO ONLY — synthetic raster + MOCK model adapter.
Outputs are heuristics, not real satellite detections.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.db.session import create_repository
from app.domain.entities import SatelliteSceneRecord
from app.inference.model_loader import ModelHandle
from app.services.inference_service import InferenceService
from app.services.satellite_service import generate_synthetic_sar_raster


def main() -> None:
    settings = get_settings()
    repo = create_repository(settings)
    now = datetime.now(timezone.utc)

    scene_id = f"DEMO_S1A_IW_{now.strftime('%Y%m%dT%H%M%S')}"
    raster_path = Path(settings.scene_storage_dir) / f"{scene_id}.tif"
    generate_synthetic_sar_raster(raster_path, seed=int(now.timestamp()))

    scene = SatelliteSceneRecord(
        id=scene_id,
        platform="Sentinel-1A",
        acquired_at=now - timedelta(minutes=11),
        footprint=(72.45, 9.304, 72.638, 9.491),
        status="processing",
        image_path=str(raster_path),
        is_demo=True,
    )
    repo.add_scene(scene)

    svc = InferenceService(repo, settings)
    incidents, run_id, ms = svc.process_scene(
        scene, raster_path, model=ModelHandle(settings).get()
    )

    print(f"scene:     {scene_id}")
    print(f"model_run: {run_id} ({ms} ms)")
    for inc in incidents:
        print(json.dumps({
            "id": inc.id,
            "confidence": inc.confidence,
            "area_km2": inc.area_km2,
            "perimeter_km": inc.perimeter_km,
            "centroid": [inc.centroid_lat, inc.centroid_lon],
            "region": inc.region,
            "is_demo": inc.is_demo,
        }, indent=2))
    if not incidents:
        print("no detections above threshold")


if __name__ == "__main__":
    main()
