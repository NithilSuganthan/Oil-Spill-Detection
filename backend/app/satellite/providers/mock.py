"""DEMO satellite provider — clearly labeled, never real data.

Generates synthetic Sentinel-1-LIKE metadata and rasters so discovery,
download, preprocessing and the API can be exercised without network
access or credentials. Every record it produces is marked is_demo=True.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import numpy as np

from app.domain.entities import SatelliteSceneRecord
from app.satellite.aoi import AreaOfInterest
from app.satellite.providers.base import (
    DownloadOptions,
    ProviderInfo,
    SceneQuery,
    SatelliteSceneProvider,
)
from app.satellite.storage import StorageBackend, StoredFile


class MockSatelliteProvider(SatelliteSceneProvider):
    """DEVELOPMENT ONLY — synthetic scenes over a requested AOI."""

    def __init__(self, seed: int = 42) -> None:
        self._seed = seed

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="mock",
            is_real=False,
            description="SYNTHETIC demo scenes — not real satellite data",
        )

    # ---------------------------------------------------------------- search
    def search_scenes(
        self,
        query: SceneQuery,
        aoi: AreaOfInterest | None = None,
    ) -> list[SatelliteSceneRecord]:
        bbox = query.bbox or (aoi.bbox if aoi else None)
        if bbox is None:
            raise ValueError("SceneQuery requires a bbox or an AOI")
        w, s, e, n = bbox

        rng = np.random.default_rng(self._seed)
        count = min(query.limit, 8)
        end = query.end or datetime.now(timezone.utc)
        start = query.start or (end - timedelta(days=30))

        scenes: list[SatelliteSceneRecord] = []
        for i in range(count):
            acquired = start + (end - start) * (float(rng.random()) * 0.9 + 0.05)
            cx = w + (e - w) * float(rng.random())
            cy = s + (n - s) * float(rng.random())
            half_deg_lon = 0.7 + 0.4 * float(rng.random())
            half_deg_lat = 0.35
            footprint = (
                round(cx - half_deg_lon, 4),
                round(max(cy - half_deg_lat, -89.0), 4),
                round(cx + half_deg_lon, 4),
                round(min(cy + half_deg_lat, 89.0), 4),
            )
            platform = f"Sentinel-1{'AB'[i % 2]}"
            slug = _slug(platform, acquired)
            scene = SatelliteSceneRecord(
                id=f"DEMO_{slug}",
                platform=platform,
                acquisition_mode="IW",
                polarisation="VV + VH",
                acquired_at=acquired.replace(microsecond=0),
                processed_at=(acquired + timedelta(hours=3)).replace(microsecond=0),
                footprint=footprint,
                status="discovered",
                is_demo=True,
                product_id=f"demo-uuid-{i:04d}",
                product_name=f"{slug}.SAFE",
                source_provider="mock",
                orbit_state=("ascending", "descending")[i % 2],
                absolute_orbit=10000 + i,
                relative_orbit=34 + i * 7,
                download_url=None,   # nothing real to fetch
                file_size_bytes=int(5e8 + i * 1e7),
                product_type=query.product_type or "IW_GRDH_1S",
                geometry=_bbox_polygon(footprint),
            )
            if query.platform and query.platform.lower() not in scene.platform.lower():
                continue
            scenes.append(scene)

        if aoi is not None:
            scenes = [sc for sc in scenes if aoi.intersects_bbox(sc.footprint)]  # type: ignore[arg-type]
        return scenes[: query.limit]

    # ------------------------------------------------------------- metadata
    def get_scene_metadata(self, scene_id: str) -> SatelliteSceneRecord | None:
        from app.satellite.aoi import INDIA_MARITIME_DEV_BBOX

        for scene in self.search_scenes(SceneQuery(limit=8), AreaOfInterest(bbox=INDIA_MARITIME_DEV_BBOX)):
            if scene.id == scene_id:
                return scene
        return None

    # -------------------------------------------------------------- download
    def download_scene(
        self,
        scene: SatelliteSceneRecord,
        storage: StorageBackend,
        options: DownloadOptions | None = None,
    ) -> StoredFile:
        from app.services.satellite_service import generate_synthetic_sar_raster

        key = f"products/{scene.id}.tif"
        path = storage.get_path(key)
        generate_synthetic_sar_raster(path, seed=int(hashlib.sha1(scene.id.encode()).hexdigest()[:8], 16))
        size = path.stat().st_size
        return StoredFile(key, size, str(path), storage.get_url(key))


def _slug(platform: str, when: datetime) -> str:
    stamp = when.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"S1_IW_GRDH_1SDV_{stamp}_{platform.replace('-', '').upper()}"


def _bbox_polygon(bbox: tuple[float, float, float, float]) -> dict:
    w, s, e, n = bbox
    return {
        "type": "Polygon",
        "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
    }
