# Drift + AIS Integration — Architecture & Reference

## Overview

The drift/AIS integration connects oil-spill detection to potential source vessel identification through a two-stage pipeline:

```
Observed Slick (centroid lat/lon + time)
    ↓
Stage 1: Backward Drift Hindcast → Estimated Source Location + Time
    ↓
Stage 2: AIS Vessel Correlation → Ranked Potential Source Vessels
    ↓
Incident Detail (Frontend: map layers + info panels)
```

---

## Stage 1: First-Order Backward Drift Hindcast

### Physical Model

Surface oil drift is approximated by:

```
v_drift = v_current + λ × v_wind
```

Where:
- `v_current` = ocean surface current velocity (m/s, east/north components)
- `v_wind` = wind velocity at 10m height (m/s)
- `λ` = windage coefficient (dimensionless, typically 0.02–0.04 for floating oil)

### Backward Integration

Starting from the observed slick centroid position at observation time `t₀`, particles are traced backward in time:

```
position(t₀ - Δt) = position(t₀) - v_drift × Δt
```

At each timestep:
1. Retrieve environmental conditions (current, wind) at the current particle position and time
2. Compute drift velocity: `v = current + windage × wind`
3. Move the particle backward: subtract the displacement
4. Add small random perturbation for ensemble spread

### Default Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `integration_hours` | 24 | How far back to trace |
| `timestep_minutes` | 15 | Integration timestep |
| `ensemble_size` | 50 | Number of particles |
| `windage_coefficient` | 0.03 | Wind drift factor |
| `windage_coefficient_std` | 0.01 | Perturbation std for ensemble |
| `current_fraction` | 1.0 | Scaling for current velocity |
| `position_noise_km` | 0.5 | Initial position perturbation |

### Ensemble Methodology

Multiple particles (default: 50) are released from slightly perturbed initial conditions:

- Initial position: Gaussian perturbation around slick centroid (`σ = position_noise_km`)
- Windage coefficient: each particle gets a random windage from `N(base_windage, windage_std)`
- Current fraction: each particle gets a random fraction from `N(1.0, 0.1)`, clamped ≥ 0.5

The ensemble centroid becomes the estimated source location. Spatial and temporal spread quantify uncertainty.

### Uncertainty Calculation

**Spatial uncertainty:**
1. Compute geodesic distance (Haversine) from each particle's final position to the ensemble centroid
2. Take the maximum distance as the ensemble spread
3. Add systematic uncertainty: `uncertainty_km += drift_uncertainty_km_per_hour × integration_hours`

**Temporal uncertainty:**
- Time spread = `max(source_times) - min(source_times)` across particles

### Quality Flags

| Flag | Condition |
|------|-----------|
| `DEMO_ENVIRONMENTAL_FORCING` | Always set (current implementation uses mock forcing) |
| `LARGE_SOURCE_UNCERTAINTY` | Uncertainty > 20 km |

### Confidence Score

```
spread_ratio = uncertainty_km / ais_search_radius_km
confidence = clamp(1.0 - spread_ratio, 0.1, 0.9)
```

---

## Stage 2: AIS Vessel Correlation

### SourceEstimate Interface

The drift output is converted to a `SourceEstimate` for AIS correlation:

```python
SourceEstimate(
    latitude=drift_result.source_latitude,
    longitude=drift_result.source_longitude,
    timestamp=midpoint(source_earliest, source_latest),
    uncertainty_km=drift_result.uncertainty_km,
    uncertainty_hours=drift_result.uncertainty_hours,
    method="first_order_backward_hindcast",
    confidence=drift_result.confidence,
    quality_flags=drift_result.quality_flags,
)
```

### Search Window Construction

The AIS search window is built from the source estimate:
- Center: estimated source location (from drift)
- Radius: `ais_search_radius_km + source.uncertainty_km` (drift uncertainty expands the search)
- Time window: `timestamp ± uncertainty_hours`

### Attribution Scoring

Each candidate vessel receives an attribution score based on three components:

| Component | Weight | Description |
|-----------|--------|-------------|
| Distance | 0.50 | Exponential decay from closest distance |
| Time | 0.30 | Gaussian around observation time |
| Track Consistency | 0.20 | Number of observations in window |

```
score = w_d × exp(-d/d_ref) + w_t × exp(-Δt²/2σ²) + w_c × min(n_obs/n_ref, 1.0)
```

All candidates are flagged with `human_review_required: true`. The system never claims causation.

---

## DEMO vs REAL Data

### DEMO Mode (Default for Development)

| Component | Provider | Status |
|-----------|----------|--------|
| Environmental forcing | `MockEnvironmentalProvider` | Deterministic, synthetic currents/winds |
| AIS positions | `MockAISProvider` | 4 hardcoded demo vessels |
| Drift engine | `FirstOrderDriftProvider` | Real physics, DEMO forcing |
| Attribution scoring | `analyze_attribution()` | Real algorithm, DEMO data |

All DEMO responses include:
- `DEMO_ENVIRONMENTAL_FORCING` quality flag
- `"environment": "DEMO"` in investigation response
- Warning banner in frontend UI

### REAL Mode (Phase 7 — Implemented)

| Component | Provider | Requirement |
|-----------|----------|-------------|
| Environmental forcing | `RealEnvironmentalProvider` | CMEMS + CDS credentials |
| AIS positions | Global Fishing Watch API | `GFW_API_TOKEN` environment variable |
| Drift engine | Same `FirstOrderDriftProvider` | Real environmental data |

**Data Sources:**

**CMEMS GLOBCURRENT** (ocean surface currents):
- Product: `MULTIOBS_GLO_PHY_MYNRT_015_003`
- Dataset: `cmems_obs-mob_glo_phy-cur_my_0.25deg_PT1H-i`
- Variables: `uo` (eastward), `vo` (northward) — m s⁻¹
- Resolution: 0.25° × 0.25° (~27 km), hourly, 1993–present
- Access: `copernicusmarine` Python toolbox (free registration)

**ECMWF ERA5** (10m winds):
- Dataset: `reanalysis-era5-single-levels`
- Variables: `10m_u_component_of_wind`, `10m_v_component_of_wind` — m s⁻¹
- Resolution: 0.25° × 0.25°, hourly, 1940–present
- Access: `cdsapi` Python client (free registration)

**Configuration** (`.env`):
```bash
ENVIRONMENTAL_PROVIDER=real
CMEMS_USERNAME=your_cmems_username
CMEMS_PASSWORD=your_cmems_password
CDS_API_KEY=your_cds_api_key
```

**Architecture:**
1. `prepare_cache(bbox, timesteps)` downloads grids for the bbox and time window
2. `get_conditions(lat, lon, timestamp)` interpolates bilinearly from cached grids
3. No network calls during the 4,800 call drift loop (50 particles × 96 timesteps)

**Interpolation:**
- Spatial: bilinear interpolation from regular lat-lon grid
- Temporal: linear interpolation between hourly timesteps
- Boundary: clamped to nearest grid cell at edges

**Error Handling:**
- Missing credentials → ValueError at init (does NOT silently fall back to mock)
- Network/auth failure → RuntimeError at prepare_cache
- Unavailable data → RuntimeError at prepare_cache

**Quality Flags:**
- `REAL_ENVIRONMENTAL_FORCING` when real data is used
- `DEMO_ENVIRONMENTAL_FORCING` when mock data is used

---

## API Endpoints

### POST `/drift/analyze`

Run drift hindcast for an incident.

**Request:** `{"incidentId": "IN-250825-001"}`

**Response:** `DriftResponse` with source location, uncertainty, trajectories.

### GET `/drift/{incident_id}`

Get or compute drift analysis for an incident.

### POST `/investigation/{incident_id}/run`

Full pipeline: drift → source estimate → AIS correlation.

**Response:** `InvestigationResponse` containing:
- `drift`: DriftResult
- `attribution`: AttributionResult
- `environment`: "DEMO" | "MIXED" | "REAL"
- `status`: "completed" | "failed"

---

## Limitations

1. **First-order model**: Does not account for oil weathering, emulsification, or spreading
2. **No vertical mixing**: Model treats oil as purely surface floating
3. **Constant windage**: Real windage depends on oil type, thickness, and sea state
4. **No tidal effects**: Tidal currents can dominate in coastal areas
5. **No Stokes drift**: Surface wave effects not included
6. **Grid resolution**: 0.25° (~27 km) may miss mesoscale eddies and coastal currents
7. **ERA5 latency**: Reanalysis data has ~5-day delay; final release lags by months
8. **CMEMS NRT**: Near-real-time data has ~1-day latency
9. **Indian Ocean coverage**: Both datasets provide global coverage including the Indian Ocean

### Accuracy Expectations

With real environmental forcing:
- Source location accuracy: typically 5–20 km for 24-hour hindcast in open ocean
- Degrades significantly in coastal areas, estuaries, and near complex bathymetry
- Accuracy depends critically on quality of current/wind forecasts

With DEMO forcing:
- Demonstrates pipeline functionality only
- Source estimates are not physically meaningful
- Always labeled as DEMO

---

## File Reference

| File | Purpose |
|------|---------|
| `backend/app/services/drift_provider.py` | DriftProvider ABC + DriftResult dataclass |
| `backend/app/services/drift_engine.py` | FirstOrderDriftProvider implementation |
| `backend/app/services/environmental_provider.py` | EnvironmentalProvider ABC |
| `backend/app/services/environmental_mock_provider.py` | MockEnvironmentalProvider |
| `backend/app/services/environmental_real_provider.py` | RealEnvironmentalProvider (CMEMS + ERA5) |
| `backend/app/domain/ais.py` | SourceEstimate with drift fields |
| `backend/app/api/routes/drift.py` | Drift + Investigation API routes |
| `backend/app/schemas/drift.py` | Drift API response schemas |
| `backend/tests/test_drift.py` | Drift engine + API tests |
| `backend/tests/test_real_environmental_provider.py` | Real provider unit tests |
| `src/lib/types.ts` | Frontend TypeScript types (DriftResult, InvestigationResult) |
| `src/lib/api/client.ts` | Frontend API client (getDrift, runInvestigation) |
| `src/app/incident/[id]/page.tsx` | Incident detail page with Drift panel |
| `src/components/map/map-view.tsx` | Map with drift trajectory + source layers |
| `src/lib/store/use-app-store.ts` | Map layer definitions (drift-trajectories, source-probability) |
