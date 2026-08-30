# Phase 7: Real Environmental Forcing - Implementation Plan

## Objective
Replace the `MockEnvironmentalProvider` with real ocean current and wind data from Copernicus Marine Service (CMEMS) and ECMWF ERA5, enabling physically-based drift hindcast using actual environmental conditions.

## Data Sources

### 1. CMEMS GLOBCURRENT (Ocean Currents)
- **Product**: `MULTIOBS_GLO_PHY_MYNRT_015_003`
- **Variables**: `uo` (eastward current), `vo` (northward current) at surface
- **Resolution**: 0.25° × 0.25° (~27 km)
- **Temporal**: Hourly, 1993–Jul 2026 (multi-year + NRT)
- **Access**: `copernicusmarine` Python toolbox (free, no quotas)
- **Auth**: CMEMS account (free registration at marine.copernicus.eu)

### 2. ECMWF ERA5 (10m Winds)
- **Product**: `reanalysis-era5-single-levels`
- **Variables**: `10m_u_component_of_wind`, `10m_v_component_of_wind`
- **Resolution**: 0.25° × 0.25°
- **Temporal**: Hourly, 1940–present
- **Access**: `cdsapi` Python package
- **Auth**: CDS API token (free registration at cds.climate.copernicus.eu)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Drift Engine Loop                      │
│  (4,800 calls: 50 particles × 96 timesteps)            │
└─────────────┬───────────────────────────────────────────┘
              │ get_conditions(lat, lon, timestamp)
              ▼
┌─────────────────────────────────────────────────────────┐
│              RealEnvironmentalProvider                    │
│  ┌───────────────────────────────────────────────────┐  │
│  │              Grid Cache (per analysis)             │  │
│  │  currents_grid: dict[datetime, ndarray]           │  │
│  │  winds_grid: dict[datetime, ndarray]              │  │
│  │  lats: ndarray, lons: ndarray                     │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │ CMEMS Client │    │ CDS Client   │                   │
│  │ (currents)   │    │ (winds)      │                   │
│  └──────┬───────┘    └──────┬───────┘                   │
└─────────┼───────────────────┼───────────────────────────┘
          │                   │
          ▼                   ▼
   CMEMS GLOBCURRENT    ERA5 Single Levels
```

## Implementation Steps

### Step 1: Add Dependencies
**File**: `backend/requirements.txt`

Add:
```
copernicusmarine>=2.0
cdsapi>=0.7
xarray>=2024.0
netCDF4>=1.6
```

### Step 2: Add Configuration Settings
**File**: `backend/app/config.py`

Add new settings to `Settings` class:
```python
# Real environmental data (Phase 7)
cmems_username: str = ""          # CMEMS account username
cmems_password: str = ""          # CMEMS account password
cds_api_key: str = ""             # CDS API personal access token
cds_api_url: str = "https://cds.climate.copernicus.eu/api"

# Drift environmental cache
env_cache_bbox_pad_deg: float = 0.5   # padding around slick for bbox
env_cache_temporal_pad_hours: float = 1.0  # padding around time window
```

### Step 3: Update Environment Files
**Files**: `.env`, `backend/.env.example`

Add:
```bash
# Real environmental data (Phase 7)
CMEMS_USERNAME=your_cmems_username
CMEMS_PASSWORD=your_cmems_password
CDS_API_KEY=your_cds_personal_access_token
```

### Step 4: Create RealEnvironmentalProvider
**File**: `backend/app/services/environmental_real_provider.py` (NEW)

```python
class RealEnvironmentalProvider(EnvironmentalProvider):
    """Real environmental data from CMEMS + ERA5."""

    name = "real"

    def __init__(
        self,
        cmems_username: str,
        cmems_password: str,
        cds_api_key: str,
        cds_api_url: str = "https://cds.climate.copernicus.eu/api",
    ):
        self._cmems_username = cmems_username
        self._cmems_password = cmems_password
        self._cds_api_key = cds_api_key
        self._cds_api_url = cds_api_url

        # Cache: populated per-analysis
        self._currents_cache: dict[datetime, np.ndarray] = {}
        self._winds_cache: dict[datetime, np.ndarray] = {}
        self._cache_lats: np.ndarray | None = None
        self._cache_lons: np.ndarray | None = None
        self._cache_timesteps: list[datetime] = []

    def prepare_cache(
        self,
        bbox: tuple[float, float, float, float],  # (min_lon, min_lat, max_lon, max_lat)
        timesteps: list[datetime],
    ) -> None:
        """Pre-fetch environmental grids for a bbox and timesteps.

        Call this before starting the drift loop to populate the cache.
        """
        # 1. Fetch CMEMS currents for bbox + timesteps
        # 2. Fetch ERA5 winds for bbox + timesteps
        # 3. Store in self._currents_cache, self._winds_cache

    def get_conditions(
        self, lat: float, lon: float, timestamp: datetime,
    ) -> EnvironmentalConditions:
        """Get conditions from cached grids using bilinear interpolation."""
        # 1. Find nearest timestep in cache
        # 2. Bilinear interpolate currents at (lat, lon)
        # 3. Bilinear interpolate winds at (lat, lon)
        # 4. Return EnvironmentalConditions

    def _bilinear_interpolate(
        self, grid: np.ndarray, lats: np.ndarray, lons: np.ndarray,
        lat: float, lon: float,
    ) -> float:
        """Bilinear interpolation from regular lat-lon grid."""

    def _fetch_cmems_currents(
        self, bbox: tuple, timesteps: list[datetime],
    ) -> dict[datetime, np.ndarray]:
        """Fetch ocean currents from CMEMS GLOBCURRENT."""

    def _fetch_era5_winds(
        self, bbox: tuple, timesteps: list[datetime],
    ) -> dict[datetime, np.ndarray]:
        """Fetch 10m winds from ERA5."""

    def close(self) -> None:
        """Clear cache."""
        self._currents_cache.clear()
        self._winds_cache.clear()
```

### Step 5: Implement CMEMS Data Fetching
**Inside** `RealEnvironmentalProvider._fetch_cmems_currents()`

```python
import copernicusmarine

def _fetch_cmems_currents(self, bbox, timesteps):
    """Fetch GLOBCURRENT data from CMEMS."""
    min_lon, min_lat, max_lon, max_lat = bbox

    # CMEMS subset request
    dataset_id = "cmems_obs-mob_glo_phy-cur_my_0.25deg_PT1H-i"

    # Calculate time range
    start_time = min(timesteps)
    end_time = max(timesteps)

    # Download subset as xarray Dataset
    ds = copernicusmarine.subset(
        dataset_id=dataset_id,
        variables=["uo", "vo"],  # eastward/northward current
        minimum_longitude=min_lon,
        maximum_longitude=max_lon,
        minimum_latitude=min_lat,
        maximum_latitude=max_lat,
        start_datetime=start_time.isoformat(),
        end_datetime=end_time.isoformat(),
        username=self._cmems_username,
        password=self._cmems_password,
    )

    # Parse into cache dict
    cache = {}
    for t in ds.time.values:
        timestamp = pd.Timestamp(t).to_pydatetime()
        uo = ds["uo"].sel(time=t).values  # shape: (lat, lon)
        vo = ds["vo"].sel(time=t).values
        cache[timestamp] = np.stack([uo, vo], axis=-1)  # (lat, lon, 2)

    return cache, ds.latitude.values, ds.longitude.values
```

### Step 6: Implement ERA5 Data Fetching
**Inside** `RealEnvironmentalProvider._fetch_era5_winds()`

```python
import cdsapi

def _fetch_era5_winds(self, bbox, timesteps):
    """Fetch 10m winds from ERA5."""
    min_lon, min_lat, max_lon, max_lat = bbox

    client = cdsapi.Client(
        url=self._cds_api_url,
        key=self._cds_api_key,
    )

    # Build date/time lists
    dates = sorted(set(t.strftime("%Y-%m-%d") for t in timesteps))
    hours = sorted(set(t.strftime("%H:%M") for t in timesteps))

    result = client.retrieve(
        "reanalysis-era5-single-levels",
        {
            "product_type": "reanalysis",
            "variable": ["10m_u_component_of_wind", "10m_v_component_of_wind"],
            "year": [d[:4] for d in dates],
            "month": [d[5:7] for d in dates],
            "day": [d[8:10] for d in dates],
            "time": hours,
            "area": [max_lat, min_lon, min_lat, max_lon],  # N, W, S, E
            "format": "netcdf",
        },
        "era5_winds_subset.nc",
    )

    # Parse NetCDF
    ds = xr.open_dataset(result)
    cache = {}
    for t in ds.time.values:
        timestamp = pd.Timestamp(t).to_pydatetime()
        u10 = ds["u10"].sel(time=t).values
        v10 = ds["v10"].sel(time=t).values
        cache[timestamp] = np.stack([u10, v10], axis=-1)

    return cache, ds.latitude.values, ds.longitude.values
```

### Step 7: Implement Bilinear Interpolation
**Inside** `RealEnvironmentalProvider._bilinear_interpolate()`

```python
def _bilinear_interpolate(self, grid, lats, lons, lat, lon):
    """Bilinear interpolation on regular lat-lon grid.

    Args:
        grid: ndarray of shape (n_lat, n_lon) or (n_lat, n_lon, n_comp)
        lats: 1D array of latitudes (ascending)
        lons: 1D array of longitudes (ascending)
        lat, lon: query point

    Returns:
        Interpolated value (float or ndarray of components)
    """
    # Find bounding indices
    lat_idx = np.searchsorted(lats, lat) - 1
    lon_idx = np.searchsorted(lons, lon) - 1

    # Clamp to valid range
    lat_idx = np.clip(lat_idx, 0, len(lats) - 2)
    lon_idx = np.clip(lon_idx, 0, len(lons) - 2)

    # Fractional offsets
    dlat = (lat - lats[lat_idx]) / (lats[lat_idx + 1] - lats[lat_idx])
    dlon = (lon - lons[lon_idx]) / (lons[lon_idx + 1] - lons[lon_idx])

    # Bilinear weights
    w00 = (1 - dlat) * (1 - dlon)
    w01 = (1 - dlat) * dlon
    w10 = dlat * (1 - dlon)
    w11 = dlat * dlon

    # Interpolate
    val = (w00 * grid[lat_idx, lon_idx] +
           w01 * grid[lat_idx, lon_idx + 1] +
           w10 * grid[lat_idx + 1, lon_idx] +
           w11 * grid[lat_idx + 1, lon_idx + 1])

    return val
```

### Step 8: Update Drift Route Factory
**File**: `backend/app/api/routes/drift.py`

Modify `_get_drift_provider()`:
```python
def _get_drift_provider(settings: Settings):
    if settings.environmental_provider == "real" and settings.cmems_username:
        from app.services.environmental_real_provider import RealEnvironmentalProvider
        env_provider = RealEnvironmentalProvider(
            cmems_username=settings.cmems_username,
            cmems_password=settings.cmems_password,
            cds_api_key=settings.cds_api_key,
            cds_api_url=settings.cds_api_url,
        )
    else:
        env_provider = MockEnvironmentalProvider()
    return FirstOrderDriftProvider(environmental_provider=env_provider, settings=settings)
```

### Step 9: Add Cache Preparation to Investigation Orchestrator
**File**: `backend/app/api/routes/drift.py`

Modify `analyze_drift()` and `run_investigation()` to prepare cache before drift:
```python
# Before calling drift_provider.estimate_source():
if isinstance(env_provider, RealEnvironmentalProvider):
    bbox = _compute_bbox(incident.centroid_lat, incident.centroid_lon, settings)
    timesteps = _compute_timesteps(incident.detected_at, settings)
    env_provider.prepare_cache(bbox, timesteps)
```

### Step 10: Add Helper Functions
**File**: `backend/app/api/routes/drift.py`

```python
def _compute_bbox(lat: float, lon: float, settings: Settings) -> tuple:
    """Compute bbox around slick with padding."""
    pad = settings.env_cache_bbox_pad_deg
    return (lon - pad, lat - pad, lon + pad, lat + pad)

def _compute_timesteps(detected_at: datetime, settings: Settings) -> list[datetime]:
    """Compute hourly timesteps for drift window."""
    import math
    n_hours = math.ceil(settings.drift_hours) + 1
    return [detected_at - timedelta(hours=h) for h in range(n_hours)]
```

### Step 11: Update Quality Flags
**File**: `backend/app/services/drift_engine.py`

Add real environmental forcing quality flag:
```python
quality_flags={
    "low_ensemble_count": n_ensemble < 20,
    "large_position_spread_km": spread_km > 20.0,
    "environmental_forcing": self._env.name,  # "mock" or "real"
},
```

### Step 12: Update Frontend Drift Panel
**File**: `src/app/incident/[id]/page.tsx`

Show real provider provenance when available:
```tsx
{drift.provenance?.environmental_provider === "real" ? (
  <Badge variant="success">REAL ENVIRONMENTAL FORCING</Badge>
) : (
  <Badge variant="warning">DEMO ENVIRONMENTAL FORCING</Badge>
)}
```

### Step 13: Add Tests
**File**: `backend/tests/test_real_environmental_provider.py` (NEW)

Test cases:
1. `test_bilinear_interpolation准确性` - Verify interpolation against known grid values
2. `test_cache_preparation` - Verify cache is populated for bbox + timesteps
3. `test_get_conditions_from_cache` - Verify conditions are interpolated correctly
4. `test_temporal_interpolation` - Verify behavior between cached timesteps
5. `test_boundary_handling` - Verify clamping at grid edges
6. `test_provider_name_provenance` - Verify `name = "real"` appears in provenance
7. `test_fallback_to_mock` - Verify mock is used when credentials missing

### Step 14: Run Full Test Suite
```bash
cd backend
python -m pytest tests/ -v
```

### Step 15: Update Documentation
**File**: `docs/drift-ais-integration.md`

Add section on real environmental forcing:
- CMEMS GLOBCURRENT data source
- ERA5 wind data source
- Bilinear interpolation methodology
- Caching strategy
- Configuration and credentials
- Limitations (0.25° resolution, hourly temporal)

## Verification Commands

1. **Unit tests**: `python -m pytest tests/test_real_environmental_provider.py -v`
2. **Integration test**: `python scripts/verify_real_env.py` (small bbox, 3 timesteps)
3. **Drift test**: `POST /drift/analyze` with real forcing → verify quality_flags show "real"
4. **Full pipeline**: `POST /investigation/{id}/run` → verify env_status = "REAL"
5. **Regression**: `python -m pytest tests/ -v` (all 219+ tests pass)

## Limitations

1. **Resolution**: 0.25° grid (~27 km) - adequate for open ocean, may miss coastal effects
2. **Latency**: ERA5 has ~5-day delay; CMEMS NRT has ~1-day delay
3. **Demo incident**: Aug 2026 incident is in the future; data may not be available yet
4. **Account required**: Free CMEMS and CDS accounts needed
5. **Download time**: Initial grid download may take 30-60 seconds per analysis
