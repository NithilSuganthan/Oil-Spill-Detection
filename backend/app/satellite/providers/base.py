"""SatelliteSceneProvider abstraction.

The rest of the backend depends ONLY on this interface:
    search_scenes(query)        -> list[SatelliteSceneRecord]
    get_scene_metadata(scene_id)-> SatelliteSceneRecord | None
    download_scene(scene, storage, ...) -> StoredFile

Implementations: CopernicusSatelliteProvider (real CDSE catalogue) and
MockSatelliteProvider (clearly-labeled demo).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.entities import SatelliteSceneRecord
from app.satellite.aoi import AreaOfInterest
from app.satellite.storage import StorageBackend, StoredFile


@dataclass
class SceneQuery:
    """Catalogue query parameters (all optional except defaults)."""

    start: datetime | None = None
    end: datetime | None = None
    bbox: tuple[float, float, float, float] | None = None
    geometry: dict | None = None            # GeoJSON polygon for intersection
    platform: str | None = None             # e.g. "sentinel-1a"
    product_type: str | None = None         # e.g. "IW_GRDH_1S"
    limit: int = 20

    def __post_init__(self) -> None:
        if self.limit < 1 or self.limit > 200:
            raise ValueError("limit must be between 1 and 200")


@dataclass
class DownloadOptions:
    """Behaviour knobs for scene acquisition."""

    max_retries: int = 3
    retry_backoff_seconds: float = 5.0
    chunk_size_mb: float = 1.0
    progress_cb: object | None = None   # callable(bytes_done, total_or_none)
    cancel_check: object | None = None  # callable() -> bool


@dataclass
class ProviderInfo:
    name: str
    is_real: bool                      # False => demo/mock data source
    description: str = ""
    extra: dict = field(default_factory=dict)


class SatelliteSceneProvider(abc.ABC):
    """Contract between SAGAR WATCH and any satellite data source."""

    @abc.abstractmethod
    def info(self) -> ProviderInfo: ...

    @abc.abstractmethod
    def search_scenes(
        self,
        query: SceneQuery,
        aoi: AreaOfInterest | None = None,
    ) -> list[SatelliteSceneRecord]: ...

    @abc.abstractmethod
    def get_scene_metadata(self, scene_id: str) -> SatelliteSceneRecord | None: ...

    @abc.abstractmethod
    def download_scene(
        self,
        scene: SatelliteSceneRecord,
        storage: StorageBackend,
        options: DownloadOptions | None = None,
    ) -> StoredFile: ...
