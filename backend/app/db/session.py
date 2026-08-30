"""Database session / repository factory."""

from __future__ import annotations

import logging

from app.config import Settings
from app.db.memory_repo import InMemoryRepository
from app.db.postgis_repo import PostgisRepository
from app.db.repository import SpillRepository

logger = logging.getLogger(__name__)


def create_repository(settings: Settings) -> SpillRepository:
    """Choose the persistence backend from configuration.

    * postgresql:// or postgresql+psycopg2://  -> PostGIS (production path)
    * anything else / unset                    -> in-memory dev repository

    The in-memory backend exists so the complete inference pipeline can be
    developed and verified locally without a database server. It holds no
    data across restarts and must never be used in production.
    """
    if settings.use_postgis:
        logger.info("Using PostgreSQL + PostGIS repository")
        return PostgisRepository(settings.database_url)
    logger.warning(
        "DATABASE_URL not set to Postgres — using IN-MEMORY development "
        "repository (data is lost on restart; demo/testing only)"
    )
    return InMemoryRepository()
