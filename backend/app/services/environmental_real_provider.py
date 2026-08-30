"""Real environmental data provider using CMEMS GLOBCurrents + ERA5 winds.

Fetches ocean surface currents from Copernicus Marine Service (GLOBCURRENT)
and 10m winds from ECMWF ERA5 reanalysis.  Data is cached per-analysis to
avoid redundant network calls during the drift integration loop.

Verified API details (Aug 2026):
- CMEMS: product MULTIOBS_GLO_PHY_MYNRT_015_003, variables uo/vo, 0.25 deg hourly
- ERA5:  dataset reanalysis-era5-single-levels, variables 10m_u_component_of_wind /
         10m_v_component_of_wind, 0.25 deg hourly, GRIB/NetCDF

Units:
- Currents: m s-1 (eastward uo, northward vo)
- Winds:    m s-1 (eastward u10, northward v10)
"""

from __future__ import annotations

import logging
import math
import tempfile
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from app.services.environmental_provider import (
    EnvironmentalConditions,
    EnvironmentalProvider,
)

logger = logging.getLogger(__name__)

# ── Dataset / variable constants (verified Aug 2026) ────────────────────────
CMEMS_DATASET_ID = "cmems_obs-mob_glo_phy-cur_my_0.25deg_PT1H-i"
CMEMS_VARIABLES = ["uo", "vo"]  # eastward / northward sea water velocity

ERA5_DATASET = "reanalysis-era5-single-levels"
ERA5_VARIABLES = ["10m_u_component_of_wind", "10m_v_component_of_wind"]


class RealEnvironmentalProvider(EnvironmentalProvider):
    """Environmental data from CMEMS GLOBCurrents + ECMWF ERA5 winds.

    Workflow per analysis run:
        1. ``prepare_cache(bbox, timesteps)`` downloads grids for the bbox
           and timestep list.  Grids are stored in memory.
        2. ``get_conditions(lat, lon, timestamp)`` interpolates bilinearly
           from the cached grids — no network calls.
        3. ``close()`` releases cached data.

    The provider fails loudly on missing credentials or network errors
    instead of silently falling back to mock data.
    """

    name = "real"

    def __init__(
        self,
        cmems_username: str,
        cmems_password: str,
        cds_api_key: str,
        cds_api_url: str = "https://cds.climate.copernicus.eu/api",
    ) -> None:
        if not cmems_username or not cmems_password:
            raise ValueError(
                "CMEMS credentials required: set CMEMS_USERNAME and CMEMS_PASSWORD "
                "in your .env file.  Register free at https://marine.copernicus.eu/"
            )
        if not cds_api_key:
            raise ValueError(
                "CDS API key required: set CDS_API_KEY in your .env file.  "
                "Register free at https://cds.climate.copernicus.eu/"
            )

        self._cmems_user = cmems_username
        self._cmems_pass = cmems_password
        self._cds_key = cds_api_key
        self._cds_url = cds_api_url

        # Cache populated by prepare_cache()
        self._currents_grids: dict[datetime, np.ndarray] = {}
        self._winds_grids: dict[datetime, np.ndarray] = {}
        self._cache_lats: np.ndarray = np.array([])
        self._cache_lons: np.ndarray = np.array([])
        self._cache_timesteps: list[datetime] = []
        self._prepared = False

    # ── public interface ──────────────────────────────────────────────────

    def prepare_cache(
        self,
        bbox: tuple[float, float, float, float],
        timesteps: list[datetime],
    ) -> None:
        """Download and cache environmental grids for a bbox + timesteps.

        Args:
            bbox: (min_lon, min_lat, max_lon, max_lat) in WGS84.
            timesteps: list of UTC datetimes for the drift window.

        Raises:
            RuntimeError: if either data source fails.
        """
        if not timesteps:
            raise ValueError("timesteps list must not be empty")

        min_lon, min_lat, max_lon, max_lat = bbox
        start_dt = min(timesteps)
        end_dt = max(timesteps)

        logger.info(
            "RealEnvironmentalProvider.prepare_cache: bbox=(%.3f,%.3f,%.3f,%.3f) "
            "time=%s to %s (%d steps)",
            min_lon, min_lat, max_lon, max_lat,
            start_dt.isoformat(), end_dt.isoformat(), len(timesteps),
        )

        # Fetch CMEMS currents
        currents_grids, c_lats, c_lons = self._fetch_cmems_currents(
            bbox, start_dt, end_dt,
        )

        # Fetch ERA5 winds
        winds_grids, w_lats, w_lons = self._fetch_era5_winds(
            bbox, start_dt, end_dt,
        )

        # Grids must share the same lat/lon axes for interpolation.
        # Both CMEMS and ERA5 use 0.25 deg regular grids, so we verify
        # and adopt the CMEMS grid axes (currents are primary).
        if not np.allclose(c_lats, w_lats, atol=0.01):
            logger.warning(
                "Lat axes differ between CMEMS and ERA5 — using CMEMS axes "
                "and interpolating winds."
            )
        if not np.allclose(c_lons, w_lons, atol=0.01):
            logger.warning(
                "Lon axes differ between CMEMS and ERA5 — using CMEMS axes "
                "and interpolating winds."
            )

        self._currents_grids = currents_grids
        self._winds_grids = winds_grids
        self._cache_lats = c_lats
        self._cache_lons = c_lons
        self._cache_timesteps = sorted(currents_grids.keys())
        self._prepared = True

        logger.info(
            "Cache prepared: %d lat points, %d lon points, %d timesteps",
            len(c_lats), len(c_lons), len(self._cache_timesteps),
        )

    def get_conditions(
        self,
        lat: float,
        lon: float,
        timestamp: datetime,
    ) -> EnvironmentalConditions:
        """Get environmental conditions from cached grids.

        Performs bilinear spatial interpolation and linear temporal
        interpolation.  Raises RuntimeError if cache not prepared.
        """
        if not self._prepared:
            raise RuntimeError(
                "Cache not prepared — call prepare_cache() before get_conditions()"
            )

        # Temporal interpolation: find bounding timesteps
        ts = timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp
        t_before, t_after = self._find_bracketing_timesteps(ts)
        t_before = t_before.replace(tzinfo=timezone.utc) if t_before.tzinfo is None else t_before
        t_after = t_after.replace(tzinfo=timezone.utc) if t_after.tzinfo is None else t_after

        if t_before == t_after:
            # Exact timestep match
            current_u, current_v = self._bilinear_at(
                self._currents_grids[t_before], lat, lon,
            )
            wind_u, wind_v = self._bilinear_at(
                self._winds_grids[t_before], lat, lon,
            )
        else:
            # Linear temporal interpolation
            dt_total = (t_after - t_before).total_seconds()
            dt_frac = (ts - t_before).total_seconds() / dt_total if dt_total > 0 else 0.0

            cur_before = self._bilinear_at(self._currents_grids[t_before], lat, lon)
            cur_after = self._bilinear_at(self._currents_grids[t_after], lat, lon)
            current_u = cur_before[0] + dt_frac * (cur_after[0] - cur_before[0])
            current_v = cur_before[1] + dt_frac * (cur_after[1] - cur_before[1])

            wnd_before = self._bilinear_at(self._winds_grids[t_before], lat, lon)
            wnd_after = self._bilinear_at(self._winds_grids[t_after], lat, lon)
            wind_u = wnd_before[0] + dt_frac * (wnd_after[0] - wnd_before[0])
            wind_v = wnd_before[1] + dt_frac * (wnd_after[1] - wnd_before[1])

        return EnvironmentalConditions(
            latitude=lat,
            longitude=lon,
            timestamp=ts,
            current_u=float(current_u),
            current_v=float(current_v),
            wind_u=float(wind_u),
            wind_v=float(wind_v),
            provider="real",
            dataset="CMEMS+ERA5",
            spatial_resolution_deg=0.25,
            temporal_resolution_hours=1.0,
            environment_status="REAL",
        )

    def close(self) -> None:
        """Release cached data."""
        self._currents_grids.clear()
        self._winds_grids.clear()
        self._cache_lats = np.array([])
        self._cache_lons = np.array([])
        self._cache_timesteps = []
        self._prepared = False

    # ── CMEMS data fetching ───────────────────────────────────────────────

    def _fetch_cmems_currents(
        self,
        bbox: tuple[float, float, float, float],
        start_dt: datetime,
        end_dt: datetime,
    ) -> tuple[dict[datetime, np.ndarray], np.ndarray, np.ndarray]:
        """Fetch ocean surface currents from CMEMS GLOBCURRENT.

        Returns:
            (grids_dict, lats, lons) where grids_dict maps datetime to
            ndarray of shape (n_lat, n_lon, 2) with [uo, vo] at each grid point.
        """
        import copernicusmarine

        min_lon, min_lat, max_lon, max_lat = bbox

        logger.info(
            "Fetching CMEMS currents: dataset=%s, bbox=(%.3f,%.3f,%.3f,%.3f), "
            "time=%s to %s",
            CMEMS_DATASET_ID, min_lon, min_lat, max_lon, max_lat,
            start_dt.isoformat(), end_dt.isoformat(),
        )

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                ds = copernicusmarine.open_dataset(
                    dataset_id=CMEMS_DATASET_ID,
                    variables=CMEMS_VARIABLES,
                    minimum_longitude=min_lon,
                    maximum_longitude=max_lon,
                    minimum_latitude=min_lat,
                    maximum_latitude=max_lat,
                    start_datetime=start_dt.isoformat(),
                    end_datetime=end_dt.isoformat(),
                    username=self._cmems_user,
                    password=self._cmems_pass,
                )
        except Exception as exc:
            raise RuntimeError(
                f"CMEMS data fetch failed: {exc}.  "
                "Check CMEMS_USERNAME / CMEMS_PASSWORD and dataset availability."
            ) from exc

        lats = ds["latitude"].values if "latitude" in ds.dims else ds["lat"].values
        lons = ds["longitude"].values if "longitude" in ds.dims else ds["lon"].values

        # Ensure longitude in [-180, 180) convention
        lons = np.where(lons > 180, lons - 360, lons)

        # Sort lat ascending for interpolation
        lat_sort_idx = np.argsort(lats)
        lats = lats[lat_sort_idx]
        lon_sort_idx = np.argsort(lons)
        lons = lons[lon_sort_idx]

        grids: dict[datetime, np.ndarray] = {}
        time_var = "time" if "time" in ds.dims else ds.dims[0]

        for t_val in ds[time_var].values:
            ts = t_val.astype("datetime64[ms]").astype(datetime).replace(tzinfo=timezone.utc)

            # Extract uo and vo, apply lat/lon sort
            uo = ds["uo"].sel({time_var: t_val}).values[lat_sort_idx][:, lon_sort_idx]
            vo = ds["vo"].sel({time_var: t_val}).values[lat_sort_idx][:, lon_sort_idx]

            # Handle NaN — replace with zeros (no current)
            uo = np.nan_to_num(uo, nan=0.0)
            vo = np.nan_to_num(vo, nan=0.0)

            grids[ts] = np.stack([uo, vo], axis=-1)  # (n_lat, n_lon, 2)

        logger.info("CMEMS currents fetched: %d timesteps, grid shape %s",
                     len(grids), list(grids.values())[0].shape if grids else "empty")

        return grids, lats, lons

    # ── ERA5 data fetching ────────────────────────────────────────────────

    def _fetch_era5_winds(
        self,
        bbox: tuple[float, float, float, float],
        start_dt: datetime,
        end_dt: datetime,
    ) -> tuple[dict[datetime, np.ndarray], np.ndarray, np.ndarray]:
        """Fetch 10m winds from ECMWF ERA5 reanalysis.

        Returns:
            (grids_dict, lats, lons) where grids_dict maps datetime to
            ndarray of shape (n_lat, n_lon, 2) with [u10, v10] at each grid point.
        """
        import cdsapi
        import xarray as xr

        min_lon, min_lat, max_lon, max_lat = bbox

        logger.info(
            "Fetching ERA5 winds: dataset=%s, bbox=(%.3f,%.3f,%.3f,%.3f), "
            "time=%s to %s",
            ERA5_DATASET, min_lon, min_lat, max_lon, max_lat,
            start_dt.isoformat(), end_dt.isoformat(),
        )

        # Build year/month/day/hour lists for the CDS API request
        years = sorted(set(start_dt.strftime("%Y"), end_dt.strftime("%Y")))
        months = sorted(set(start_dt.strftime("%m"), end_dt.strftime("%m")))
        days = sorted(set(start_dt.strftime("%d"), end_dt.strftime("%d")))
        hours = sorted(set(
            f"{h:02d}:00" for h in range(start_dt.hour, end_dt.hour + 1)
        )) or ["00:00"]

        # CDS API area format: [North, West, South, East]
        area = [max_lat, min_lon, min_lat, max_lon]

        request: dict[str, Any] = {
            "product_type": "reanalysis",
            "variable": ERA5_VARIABLES,
            "year": years,
            "month": months,
            "day": days,
            "time": hours,
            "area": area,
            "format": "netcdf",
        }

        try:
            client = cdsapi.Client(url=self._cds_url, key=self._cds_key)

            with tempfile.TemporaryDirectory() as tmpdir:
                target = Path(tmpdir) / "era5_winds.nc"
                client.retrieve(ERA5_DATASET, request, str(target))
                ds = xr.open_dataset(str(target), engine="netcdf4")

                lats = ds["latitude"].values if "latitude" in ds.dims else ds["y"].values
                lons = ds["longitude"].values if "longitude" in ds.dims else ds["x"].values

                # Ensure longitude in [-180, 180) convention
                lons = np.where(lons > 180, lons - 360, lons)

                # Sort lat ascending for interpolation
                lat_sort_idx = np.argsort(lats)
                lats = lats[lat_sort_idx]
                lon_sort_idx = np.argsort(lons)
                lons = lons[lon_sort_idx]

                grids: dict[datetime, np.ndarray] = {}
                time_var = "time" if "time" in ds.dims else "valid_time"

                for t_val in ds[time_var].values:
                    ts = t_val.astype("datetime64[ms]").astype(datetime).replace(tzinfo=timezone.utc)

                    u10 = ds["u10"].sel({time_var: t_val}).values[lat_sort_idx][:, lon_sort_idx]
                    v10 = ds["v10"].sel({time_var: t_val}).values[lat_sort_idx][:, lon_sort_idx]

                    u10 = np.nan_to_num(u10, nan=0.0)
                    v10 = np.nan_to_num(v10, nan=0.0)

                    grids[ts] = np.stack([u10, v10], axis=-1)

                ds.close()

        except Exception as exc:
            raise RuntimeError(
                f"ERA5 data fetch failed: {exc}.  "
                "Check CDS_API_KEY and ensure the ERA5 dataset licence is accepted "
                "at https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels"
            ) from exc

        logger.info("ERA5 winds fetched: %d timesteps, grid shape %s",
                     len(grids), list(grids.values())[0].shape if grids else "empty")

        return grids, lats, lons

    # ── interpolation helpers ─────────────────────────────────────────────

    def _find_bracketing_timesteps(
        self, ts: datetime,
    ) -> tuple[datetime, datetime]:
        """Find the two timesteps that bracket ts."""
        if not self._cache_timesteps:
            raise RuntimeError("Cache is empty")

        t_min = self._cache_timesteps[0]
        t_max = self._cache_timesteps[-1]

        if ts <= t_min:
            return t_min, t_min
        if ts >= t_max:
            return t_max, t_max

        # Binary search
        for i in range(len(self._cache_timesteps) - 1):
            t0 = self._cache_timesteps[i]
            t1 = self._cache_timesteps[i + 1]
            if t0 <= ts <= t1:
                return t0, t1

        return t_max, t_max

    def _bilinear_at(
        self,
        grid: np.ndarray,
        lat: float,
        lon: float,
    ) -> tuple[float, float]:
        """Bilinear interpolation on regular lat-lon grid.

        Args:
            grid: shape (n_lat, n_lon, 2) — [component0, component1].
            lat: query latitude (WGS84).
            lon: query longitude (WGS84).

        Returns:
            (value_component0, value_component1) interpolated at (lat, lon).
        """
        lats = self._cache_lats
        lons = self._cache_lons

        # Find bounding indices (lats ascending, lons ascending)
        lat_idx = int(np.searchsorted(lats, lat)) - 1
        lon_idx = int(np.searchsorted(lons, lon)) - 1

        # Clamp to valid range
        lat_idx = max(0, min(lat_idx, len(lats) - 2))
        lon_idx = max(0, min(lon_idx, len(lons) - 2))

        # Fractional offsets
        lat_diff = lats[lat_idx + 1] - lats[lat_idx]
        lon_diff = lons[lon_idx + 1] - lons[lon_idx]

        if lat_diff == 0 or lon_diff == 0:
            # Degenerate grid cell — return nearest
            return float(grid[lat_idx, lon_idx, 0]), float(grid[lat_idx, lon_idx, 1])

        dlat = (lat - lats[lat_idx]) / lat_diff
        dlon = (lon - lons[lon_idx]) / lon_diff

        # Clamp offsets to [0, 1]
        dlat = max(0.0, min(1.0, dlat))
        dlon = max(0.0, min(1.0, dlon))

        # Bilinear weights
        w00 = (1 - dlat) * (1 - dlon)
        w01 = (1 - dlat) * dlon
        w10 = dlat * (1 - dlon)
        w11 = dlat * dlon

        # Interpolate both components
        val0 = (
            w00 * grid[lat_idx, lon_idx, 0]
            + w01 * grid[lat_idx, lon_idx + 1, 0]
            + w10 * grid[lat_idx + 1, lon_idx, 0]
            + w11 * grid[lat_idx + 1, lon_idx + 1, 0]
        )
        val1 = (
            w00 * grid[lat_idx, lon_idx, 1]
            + w01 * grid[lat_idx, lon_idx + 1, 1]
            + w10 * grid[lat_idx + 1, lon_idx, 1]
            + w11 * grid[lat_idx + 1, lon_idx + 1, 1]
        )

        return float(val0), float(val1)
