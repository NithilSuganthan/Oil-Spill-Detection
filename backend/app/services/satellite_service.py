"""Satellite scene queries + the SatelliteSceneProvider abstraction.

Phase 1B ships a MOCK provider that fabricates Sentinel-1-like metadata and
synthetic rasters for development. A real Copernicus/Data Space provider
implements the same interface later (credentials via environment only).
"""

from __future__ import annotations

import abc
from pathlib import Path

import numpy as np

from app.config import Settings
from app.db.repository import SpillRepository
from app.domain.entities import SatelliteSceneRecord


class SatelliteSceneProvider(abc.ABC):
    """Interface for scene discovery / retrieval.

    The real Copernicus Data Space provider will implement:
      search_scenes(aoi, time_range) -> list of scene metadata
      get_scene(product_id)          -> full record
      download_scene(record, dest)   -> local raster path
    """

    @abc.abstractmethod
    def search_scenes(self, **filters) -> list[SatelliteSceneRecord]: ...

    @abc.abstractmethod
    def get_scene(self, scene_id: str) -> SatelliteSceneRecord | None: ...

    @abc.abstractmethod
    def download_scene(self, scene: SatelliteSceneRecord, dest: Path) -> Path: ...


class MockSceneProvider(SatelliteSceneProvider):
    """DEVELOPMENT ONLY — generates synthetic SAR-like scenes."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def search_scenes(self, **filters) -> list[SatelliteSceneRecord]:
        # In dev mode scenes live in the repository already.
        return []

    def get_scene(self, scene_id: str) -> SatelliteSceneRecord | None:
        return None  # repository is authoritative in this phase

    def download_scene(self, scene: SatelliteSceneRecord, dest: Path) -> Path:
        return generate_synthetic_sar_raster(dest, seed=hash(scene.id) % (2**32))


def generate_synthetic_sar_raster(
    path: Path,
    *,
    width: int = 512,
    height: int = 512,
    seed: int = 7,
    crs: str = "EPSG:32643",   # UTM 43N — Arabian Sea / west India
    pixel_size_m: float = 40.0,
) -> Path:
    """Create a synthetic 'Sentinel-1-like' GRD GeoTIFF.

    Contains speckle-textured sea with one elongated dark slick — enough to
    exercise preprocessing → mock model → polygon extraction end-to-end.
    DEVELOPMENT ONLY.
    """
    import rasterio
    from rasterio.transform import from_origin

    rng = np.random.default_rng(seed)
    sea = -8.0 + rng.normal(0.0, 2.2, size=(height, width))  # sigma0-ish dB

    # elongated dark slick (oil damps capillary waves -> low backscatter)
    yy, xx = np.mgrid[0:height, 0:width]
    cx, cy = width * 0.42, height * 0.55
    theta = np.deg2rad(28)
    xr = (xx - cx) * np.cos(theta) + (yy - cy) * np.sin(theta)
    yr = -(xx - cx) * np.sin(theta) + (yy - cy) * np.cos(theta)
    ellipse = (xr / (width * 0.16)) ** 2 + (yr / (height * 0.055)) ** 2
    slick = ellipse < 1.0
    edge = np.clip((1.12 - ellipse) * 6.0, 0, 1)
    sea[slick] -= 5.5 * edge[slick]  # dark core with feathered edges

    path.parent.mkdir(parents=True, exist_ok=True)
    transform = from_origin(220_000.0, 1_050_000.0, pixel_size_m, pixel_size_m)
    profile = {
        "driver": "GTiff",
        "width": width,
        "height": height,
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "nodata": None,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(sea.astype(np.float32), 1)
    return path


class SceneService:
    """Read-side scene operations backed by the repository."""

    def __init__(self, repo: SpillRepository, provider: SatelliteSceneProvider | None = None) -> None:
        self._repo = repo
        self.provider = provider or MockSceneProvider(Settings())

    def list_scenes(self, bbox=None) -> list[SatelliteSceneRecord]:
        return self._repo.list_scenes(bbox=bbox)

    def get_scene(self, scene_id: str) -> SatelliteSceneRecord | None:
        return self._repo.get_scene(scene_id)

    def add_scene(self, scene: SatelliteSceneRecord) -> None:
        self._repo.add_scene(scene)
