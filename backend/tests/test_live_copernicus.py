"""OPTIONAL live Copernicus Data Space integration checks.

These hit the REAL CDSE catalogue and are skipped unless explicitly enabled:

    SAGAR_LIVE_CDSE=1 pytest tests/test_live_copernicus.py -v

Search-only checks run without credentials. Download checks additionally
require CDSE_USERNAME/CDSE_PASSWORD and will transfer a full GRD product
(hundreds of MB to >1 GB).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.config import Settings
from app.satellite.auth import CdseTokenManager
from app.satellite.factory import create_satellite_provider
from app.satellite.providers.base import SceneQuery
from app.satellite.storage import LocalStorageBackend

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("SAGAR_LIVE_CDSE") != "1",
        reason="live Copernicus checks are opt-in (SAGAR_LIVE_CDSE=1)",
    ),
]


@pytest.fixture(scope="module")
def settings():
    return Settings()


@pytest.fixture()
def provider(settings):
    return create_satellite_provider(settings)


def test_live_search_india_aoi(settings):
    aoi_bbox = tuple(float(v) for v in settings.india_aoi_bbox.split(","))
    end = datetime.now(timezone.utc)
    scenes = create_satellite_provider(settings).search_scenes(
        SceneQuery(start=end - timedelta(days=7), end=end, bbox=aoi_bbox, limit=5),
    )
    assert scenes, "expected Sentinel-1 GRD coverage over India AOI within 7 days"
    for s in scenes:
        assert s.is_demo is False
        assert s.platform.startswith("Sentinel-1")
        assert s.product_type and s.product_id
        assert s.footprint and -180 <= s.footprint[0] <= 180
        assert s.download_url


def test_live_download_single_scene(settings, tmp_path):
    if not settings.cdse_username or not settings.cdse_password:
        pytest.skip("CDSE credentials not configured — download check skipped")
    from app.satellite.aoi import AreaOfInterest

    provider = create_satellite_provider(settings)
    aoi = AreaOfInterest.from_settings(bbox_str=settings.india_aoi_bbox)
    end = datetime.now(timezone.utc)
    scenes = provider.search_scenes(
        SceneQuery(start=end - timedelta(days=7), end=end,
                   bbox=aoi.bbox, limit=settings.catalogue_query_limit),
        aoi,
    )
    assert scenes
    smallest = min(scenes, key=lambda s: s.file_size_bytes or 0)
    stored = provider.download_scene(smallest, LocalStorageBackend(tmp_path))
    assert stored.size_bytes > 1_000_000
