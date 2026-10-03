"""Environmental grid endpoint.

Provides wind and ocean-current vector fields for frontend particle
visualization.  The endpoint fetches real data from CMEMS/ERA5 when
credentials are available, otherwise returns DEMO data from the mock
provider.

Endpoint:
  POST /environmental/grid — fetch environmental grid for a bbox + time
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

import numpy as np
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_settings_dep
from app.config import Settings
from app.schemas.environmental import (
    CurrentVectorResponse,
    EnvironmentalGridResponse,
    EnvironmentalMetadataResponse,
    WindVectorResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["environmental"])


def _wind_components_to_speed_and_dir(
    u: float, v: float,
) -> tuple[float, float, float]:
    """Convert wind u/v to speed (m/s), speed (kts), and direction (deg).

    Direction uses meteorological convention: direction wind is coming FROM.
    """
    speed_ms = math.sqrt(u * u + v * v)
    speed_kts = speed_ms / 0.514444
    # Meteorological direction: atan2(-u, -v) converted to degrees [0, 360)
    direction_rad = math.atan2(-u, -v)
    direction_deg = math.degrees(direction_rad) % 360
    return speed_ms, speed_kts, direction_deg


def _current_components_to_speed_and_dir(
    u: float, v: float,
) -> tuple[float, float]:
    """Convert current u/v to speed (m/s) and direction (deg)."""
    speed_ms = math.sqrt(u * u + v * v)
    direction_rad = math.atan2(-u, -v)
    direction_deg = math.degrees(direction_rad) % 360
    return speed_ms, direction_deg


def _grid_from_provider(
    provider: Any,
    lats: np.ndarray,
    lons: np.ndarray,
    timestamp: datetime,
    n_lat: int,
    n_lon: int,
) -> tuple[list[list[float | None]], list[list[float | None]],
           list[list[float | None]], list[list[float | None]]]:
    """Sample wind and current grids from the provider at all grid points.

    Returns:
        (wind_grid, current_grid, wind_u_grid, wind_v_grid)
        where each is [lat_idx][lon_idx].
    """
    wind_grid: list[list[float | None]] = []
    current_grid: list[list[float | None]] = []
    wind_u_grid: list[list[float | None]] = []
    wind_v_grid: list[list[float | None]] = []

    for i, lat in enumerate(lats):
        wind_row: list[float | None] = []
        current_row: list[float | None] = []
        wind_u_row: list[float | None] = []
        wind_v_row: list[float | None] = []

        for j, lon in enumerate(lons):
            try:
                conditions = provider.get_conditions(float(lat), float(lon), timestamp)
                wind_speed_kts = math.sqrt(conditions.wind_u ** 2 + conditions.wind_v ** 2) / 0.514444
                current_speed_ms = math.sqrt(conditions.current_u ** 2 + conditions.current_v ** 2)
                wind_row.append(round(wind_speed_kts, 1))
                current_row.append(round(current_speed_ms, 3))
                wind_u_row.append(round(conditions.wind_u, 2))
                wind_v_row.append(round(conditions.wind_v, 2))
            except Exception:
                wind_row.append(None)
                current_row.append(None)
                wind_u_row.append(None)
                wind_v_row.append(None)

        wind_grid.append(wind_row)
        current_grid.append(current_row)
        wind_u_grid.append(wind_u_row)
        wind_v_grid.append(wind_v_row)

    return wind_grid, current_grid, wind_u_grid, wind_v_grid


def _build_grid_axes(
    bbox: tuple[float, float, float, float],
    resolution_deg: float,
) -> tuple[list[float], list[float]]:
    """Build lat/lon axes from bbox and resolution."""
    min_lon, min_lat, max_lon, max_lat = bbox
    lats = np.arange(min_lat, max_lat + resolution_deg * 0.5, resolution_deg)
    lons = np.arange(min_lon, max_lon + resolution_deg * 0.5, resolution_deg)
    return [round(float(x), 4) for x in lats], [round(float(x), 4) for x in lons]


@router.post("/environmental/grid", response_model=EnvironmentalGridResponse)
def get_environmental_grid(
    request: dict[str, Any],
    settings: Settings = Depends(get_settings_dep),
):
    """Fetch environmental grid for a geographic bbox and time range.

    Request body:
        lat: incident centroid latitude
        lon: incident centroid longitude
        timestamp: ISO-8601 observation time
        resolution_deg: grid resolution (default 0.5, min 0.25)
    """
    lat = request.get("lat")
    lon = request.get("lon")
    timestamp_str = request.get("timestamp")
    resolution_deg = float(request.get("resolution_deg", 0.5))

    if lat is None or lon is None or timestamp_str is None:
        raise HTTPException(
            status_code=400,
            detail="Required fields: lat, lon, timestamp",
        )

    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid timestamp format")

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    # Clamp resolution
    resolution_deg = max(0.25, min(2.0, resolution_deg))

    # Compute bbox around incident centroid
    pad = settings.env_cache_bbox_pad_deg
    bbox = (float(lon) - pad, float(lat) - pad, float(lon) + pad, float(lat) + pad)

    # Build grid axes
    lats, lons = _build_grid_axes(bbox, resolution_deg)
    n_lat = len(lats)
    n_lon = len(lons)

    # Determine which provider to use
    use_real = (
        settings.environmental_provider == "real"
        and settings.cmems_username
        and settings.cmems_password
        and settings.cds_api_key
    )

    if use_real:
        return _build_real_grid(
            settings, bbox, timestamp, lats, lons, n_lat, n_lon, lat, lon, pad,
        )
    else:
        return _build_mock_grid(
            timestamp, lats, lons, n_lat, n_lon, lat, lon, pad,
        )


def _build_real_grid(
    settings: Settings,
    bbox: tuple[float, float, float, float],
    timestamp: datetime,
    lats: list[float],
    lons: list[float],
    n_lat: int,
    n_lon: int,
    center_lat: float,
    center_lon: float,
    pad: float,
) -> EnvironmentalGridResponse:
    """Build environmental grid from real CMEMS/ERA5 provider."""
    from app.services.environmental_real_provider import RealEnvironmentalProvider

    provider = RealEnvironmentalProvider(
        cmems_username=settings.cmems_username,
        cmems_password=settings.cmems_password,
        cds_api_key=settings.cds_api_key,
        cds_api_url=settings.cds_api_url,
    )

    # Build timesteps for cache (single timestamp ± 1 hour for interpolation)
    timesteps = [
        timestamp,
        timestamp,
    ]

    try:
        provider.prepare_cache(bbox, timesteps)

        # Convert lats/lons to numpy for provider
        lat_arr = np.array(lats)
        lon_arr = np.array(lons)

        wind_grid, current_grid, wind_u_grid, wind_v_grid = _grid_from_provider(
            provider, lat_arr, lon_arr, timestamp, n_lat, n_lon,
        )

        # Point vector at incident centroid
        try:
            center_conditions = provider.get_conditions(center_lat, center_lon, timestamp)
            wind_speed_ms, wind_speed_kts, wind_dir = _wind_components_to_speed_and_dir(
                center_conditions.wind_u, center_conditions.wind_v,
            )
            current_speed_ms, current_dir = _current_components_to_speed_and_dir(
                center_conditions.current_u, center_conditions.current_v,
            )
            wind_point = WindVectorResponse(
                u=center_conditions.wind_u,
                v=center_conditions.wind_v,
                speed_ms=round(wind_speed_ms, 2),
                speed_kts=round(wind_speed_kts, 1),
                direction_deg=round(wind_dir, 1),
            )
            current_point = CurrentVectorResponse(
                u=center_conditions.current_u,
                v=center_conditions.current_v,
                speed_ms=round(current_speed_ms, 3),
                direction_deg=round(current_dir, 1),
            )
        except Exception:
            wind_point = None
            current_point = None

        metadata = EnvironmentalMetadataResponse(
            provider="CMEMS+ERA5",
            status="REAL",
            data_time=timestamp.isoformat(),
            data_age_minutes=None,
            spatial_resolution_deg=0.25,
            temporal_resolution_hours=1.0,
            bbox=list(bbox),
            grid_size=[n_lat, n_lon],
        )

        provider.close()

        return EnvironmentalGridResponse(
            wind=wind_grid,
            current=current_grid,
            wind_u=wind_u_grid,
            wind_v=wind_v_grid,
            current_u=[[None for _ in lons] for _ in lats],
            current_v=[[None for _ in lons] for _ in lats],
            lats=lats,
            lons=lons,
            metadata=metadata,
            wind_point=wind_point,
            current_point=current_point,
        )

    except Exception as exc:
        logger.warning(
            "Real environmental data unavailable, falling back to mock: %s", exc,
        )
        provider.close()
        return _build_mock_grid(
            timestamp, lats, lons, n_lat, n_lon, center_lat, center_lon, pad,
        )


def _build_mock_grid(
    timestamp: datetime,
    lats: list[float],
    lons: list[float],
    n_lat: int,
    n_lon: int,
    center_lat: float,
    center_lon: float,
    pad: float,
) -> EnvironmentalGridResponse:
    """Build environmental grid from mock provider (DEMO mode)."""
    from app.services.environmental_mock_provider import MockEnvironmentalProvider

    provider = MockEnvironmentalProvider()

    lat_arr = np.array(lats)
    lon_arr = np.array(lons)

    wind_grid, current_grid, wind_u_grid, wind_v_grid = _grid_from_provider(
        provider, lat_arr, lon_arr, timestamp, n_lat, n_lon,
    )

    # Point vector at incident centroid
    try:
        center_conditions = provider.get_conditions(center_lat, center_lon, timestamp)
        wind_speed_ms, wind_speed_kts, wind_dir = _wind_components_to_speed_and_dir(
            center_conditions.wind_u, center_conditions.wind_v,
        )
        current_speed_ms, current_dir = _current_components_to_speed_and_dir(
            center_conditions.current_u, center_conditions.current_v,
        )
        wind_point = WindVectorResponse(
            u=center_conditions.wind_u,
            v=center_conditions.wind_v,
            speed_ms=round(wind_speed_ms, 2),
            speed_kts=round(wind_speed_kts, 1),
            direction_deg=round(wind_dir, 1),
        )
        current_point = CurrentVectorResponse(
            u=center_conditions.current_u,
            v=center_conditions.current_v,
            speed_ms=round(current_speed_ms, 3),
            direction_deg=round(current_dir, 1),
        )
    except Exception:
        wind_point = None
        current_point = None

    metadata = EnvironmentalMetadataResponse(
        provider="mock",
        status="DEMO",
        data_time=timestamp.isoformat(),
        data_age_minutes=None,
        spatial_resolution_deg=None,
        temporal_resolution_hours=None,
        bbox=[float(lons[0]), float(lats[0]), float(lons[-1]), float(lats[-1])],
        grid_size=[n_lat, n_lon],
    )

    return EnvironmentalGridResponse(
        wind=wind_grid,
        current=current_grid,
        wind_u=wind_u_grid,
        wind_v=wind_v_grid,
        current_u=[[None for _ in lons] for _ in lats],
        current_v=[[None for _ in lons] for _ in lats],
        lats=lats,
        lons=lons,
        metadata=metadata,
        wind_point=wind_point,
        current_point=current_point,
    )
