"""Provider / storage factories wired from application settings."""

from __future__ import annotations

import logging

from app.config import Settings
from app.satellite.providers.base import SatelliteSceneProvider
from app.satellite.providers.mock import MockSatelliteProvider
from app.satellite.storage import S3StorageBackend, StorageBackend, create_storage

logger = logging.getLogger(__name__)


def create_satellite_provider(settings: Settings):
    """Build the configured SatelliteSceneProvider.

    'copernicus' requires CDSE_USERNAME/CDSE_PASSWORD; when they are missing
    the app falls back to the clearly-labeled mock provider and logs a warning
    rather than crashing startup.
    """
    kind = settings.satellite_provider.strip().lower()
    if kind == "copernicus":
        from app.satellite.auth import CdseTokenManager
        from app.satellite.providers.copernicus import CopernicusSatelliteProvider

        # STAC search is anonymous; credentials are only required when a
        # download is attempted. Missing creds therefore do not block
        # discovery — CdseTokenManager raises at get_token() time.
        if not settings.cdse_username or not settings.cdse_password:
            logger.info(
                "CDSE credentials not set: catalogue search available, "
                "downloads will fail until CDSE_USERNAME/CDSE_PASSWORD are set."
            )
        auth = CdseTokenManager(
            username=settings.cdse_username,
            password=settings.cdse_password,
            token_url=settings.cdse_token_url,
        )
        return CopernicusSatelliteProvider(
            auth,
            stac_search_url=settings.cdse_stac_search_url,
            stac_item_url=settings.cdse_stac_item_url,
        )
    return MockSatelliteProvider()


def create_storage_backend(settings: Settings) -> StorageBackend:
    backend = create_storage(settings)
    if isinstance(backend, S3StorageBackend):
        logger.info("Using S3-compatible storage (bucket=%s)", settings.s3_bucket)
    return backend
