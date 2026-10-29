# SAGAR WATCH — MASTER IMPLEMENTATION PLAN

> **Document purpose:** Single source of truth for all future implementation sessions.
> Generated from a comprehensive architecture audit of the existing repository.
> **Do not treat any field in this document as assumed — every entry was verified against the actual codebase.**

---

## 1. PRODUCT VISION

SAGAR WATCH is an oil-spill intelligence system. The final product should feel like:

**GOOGLE EARTH + WINDY + MARITIME INTELLIGENCE + OIL-SPILL INVESTIGATION SYSTEM**

The central experience:

```
GLOBAL GLOBE
      ↓
SELECT INCIDENT
      ↓
SMOOTH CAMERA FLY-TO
      ↓
REGIONAL MAP
      ↓
OIL-SPILL LOCATION
      ↓
INTERACTIVE INVESTIGATION
      ↓
SOURCE RECONSTRUCTION
      ↓
VESSEL CORRELATION
      ↓
CRITICALITY ASSESSMENT
      ↓
AI INVESTIGATION REPORT
```

Three major feature upgrades:
1. **Real/NRT Environmental Intelligence** — wind and current data visualization
2. **Operational Criticality Score** — priority index for incidents
3. **Map-Centric Investigation Interface** — the flagship operational experience

The Investigation Interface also includes:
4. 3D Globe → Incident Zoom Experience
5. Coloured Map (satellite, ocean, terrain basemaps)
6. Synchronized Master Timeline

---

## 2. CURRENT ARCHITECTURE

### 2.1 Technology Stack

| Layer | Technology | Version | Source |
|-------|-----------|---------|--------|
| Frontend framework | Next.js | 14.2 | `package.json:19` |
| UI library | React | ^18.3.1 | `package.json:21` |
| Map rendering | MapLibre GL | ^4.7.1 | `package.json:18` |
| State management | Zustand | ^5.0.1 | `package.json:24` |
| Server state | React Query | ^5.59.0 | `package.json:12` |
| Charts | Recharts | ^2.13.3 | `package.json:22` |
| Styling | Tailwind CSS | ^3.4.15 | `package.json:32` |
| TypeScript | TypeScript | ^5.6.3 | `package.json:33` |
| Backend framework | FastAPI | >=0.115 | `backend/requirements.txt:1` |
| Python | Python | 3.12 | `backend/Dockerfile` |
| Database | PostGIS (optional) | 16-3.4 | `docker-compose.yml` |
| ML framework | PyTorch (optional) | — | `backend/requirements.txt` |
| Environmental data | copernicusmarine + cdsapi | >=2.0, >=0.7 | `backend/requirements.txt:15-16` |
| AIS provider | Global Fishing Watch API | v3 | `backend/app/services/ais_gfw_provider.py` |
| Report generation | Groq | >=0.11 | `backend/requirements.txt:21` |

### 2.2 Frontend Structure

**Pages (Next.js App Router):**

| Route | File | Purpose |
|-------|------|---------|
| `/` | `src/app/page.tsx` | Dashboard / Monitor overview |
| `/incidents` | `src/app/incidents/page.tsx` | Incident listing |
| `/incident/[id]` | `src/app/incident/[id]/page.tsx` | Incident detail (server-rendered) |
| `/drift-map` | `src/app/drift-map/page.tsx` | Drift & source estimation map |
| `/live-analysis` | `src/app/live-analysis/page.tsx` | Investigation pipeline view |
| `/analytics` | `src/app/analytics/page.tsx` | Analytics dashboard |
| `/reports` | `src/app/reports/page.tsx` | Reports listing |
| `/about` | `src/app/about/page.tsx` | About page |

**Component groups (41 components):**

| Group | Files | Purpose |
|-------|-------|---------|
| `map/` (6) | `map-config.ts`, `map-view.tsx`, `map-view-client.tsx`, `map-controls.tsx`, `layer-panel.tsx`, `spill-style.ts` | Core map initialization, layers, controls |
| `drift-map/` (13) | `drift-map-view.tsx`, `drift-timeline.tsx`, `drift-summary-panel.tsx`, `drift-layer-control.tsx`, `drift-legend.tsx`, `drift-status-card.tsx`, `drift-particle-layer.tsx`, `environment-panel.tsx`, `environmental-flow-layer.tsx`, `source-estimate-card.tsx`, `source-estimate-overlay.tsx`, `ais-vessel-card.tsx`, `ais-vessel-overlay.tsx` | Investigation map experience |
| `live-analysis/` (5) | `pipeline-stages.tsx`, `engine-cards.tsx`, `investigation-map.tsx`, `slick-timeline.tsx`, `evidence-chain.tsx` | Investigation pipeline view |
| `monitor/` (6) | `summary-cards.tsx`, `detections-sidebar.tsx`, `incident-details-panel.tsx`, `activity-feed.tsx`, `investigation-progress.tsx`, `system-status-bar.tsx` | Dashboard monitor |
| `layout/` (2) | `page-shell.tsx`, `top-nav.tsx` | Navigation and layout |
| `ui/` (6) | `badge.tsx`, `button.tsx`, `card.tsx`, `input.tsx`, `select.tsx`, `states.tsx` | Design system primitives |
| `viewer/` (2) | `sar-canvas.tsx`, `satellite-viewer-modal.tsx` | SAR image viewing |
| `common/` (1) | `filter-chips.tsx` | Filter UI |

**Lib (9 files):**

| File | Purpose |
|------|---------|
| `lib/api/client.ts` | API abstraction (mock/real switch) |
| `lib/api/http-client.ts` | HTTP implementation for FastAPI |
| `lib/store/use-app-store.ts` | Zustand global state |
| `lib/hooks/use-sse.ts` | SSE connection hook |
| `lib/types.ts` | TypeScript type definitions |
| `lib/geo.ts` | Geographic utilities |
| `lib/utils.ts` | General utilities |
| `lib/mock-data/incidents.ts` | 9 seeded demo incidents |
| `lib/mock-data/scenes.ts` | Demo satellite scenes |
| `lib/mock-data/analytics.ts` | Demo analytics data |
| `lib/mock-data/system-status.ts` | Demo system status |
| `lib/pdf/generate-report-pdf.ts` | PDF report generation |

### 2.3 Backend Structure

**API routes (12 modules):**

| Route file | Prefix | Endpoints |
|------------|--------|-----------|
| `health.py` | `/health` | GET health check |
| `system.py` | `/system` | GET system status |
| `incidents.py` | `/spills` | GET list, GET by ID, GET geometry |
| `satellite.py` | `/satellite` | GET scenes, GET scene, GET provider |
| `pipeline.py` | `/pipeline` | GET jobs, POST run |
| `attribution.py` | `/attribution` | POST analyze, GET by incident |
| `drift.py` | `/drift`, `/investigation` | POST drift/analyze, GET drift/{id}, POST investigation/{id}/run |
| `reports.py` | `/reports` | GET list, GET/POST investigation report |
| `events.py` | `/events` | GET stream (SSE) |
| `reviews.py` | `/reviews` | POST false-positive review |
| `analytics.py` | `/analytics` | GET summary |

**Services (30 modules):**

| Service | File | Purpose |
|---------|------|---------|
| Environmental provider | `environmental_provider.py` | ABC for environmental data |
| Environmental mock | `environmental_mock_provider.py` | Deterministic synthetic winds/currents |
| Environmental real | `environmental_real_provider.py` | CMEMS GLOBCurrents + ERA5 winds |
| Environmental reliability | `environmental_reliability.py` | Wind/current reliability assessment |
| Drift provider | `drift_provider.py` | ABC for drift hindcast |
| Drift engine | `drift_engine.py` | First-order backward drift (50 ensemble particles) |
| AIS provider | `ais_provider.py` | ABC for AIS data |
| AIS mock | `ais_mock_provider.py` | Deterministic synthetic vessels |
| AIS GFW | `ais_gfw_provider.py` | Global Fishing Watch real AIS |
| AIS correlation | `ais_correlation.py` | Vessel ranking engine |
| AIS gap detector | `ais_gap_detector.py` | Transmission gap analysis |
| Intelligence assembly | `intelligence_assembly.py` | Phase 8 orchestrator |
| Confidence calibrator | `confidence_calibrator.py` | Platt scaling calibration |
| Look-alike classifier | `look_alike_classifier.py` | False-positive screening |
| Small detection assessor | `small_detection_assessor.py` | Area-based risk assessment |
| Seasonal prior | `seasonal_prior.py` | Monthly adjustment factors |
| Evidence builder | `evidence_builder.py` | Structured evidence for Groq |
| Explainable attribution | `explainable_attribution.py` | Attribution explanations |
| False positive review | `false_positive_review.py` | Human review workflow |
| Inference service | `inference_service.py` | ML inference orchestration |
| Incident service | `incident_service.py` | Incident CRUD |
| Satellite service | `satellite_service.py` | Scene management |
| Analytics service | `analytics_service.py` | Aggregate statistics |
| Event hub | `event_hub.py` | In-process SSE event bus |
| Groq report provider | `groq_report_provider.py` | AI report generation |
| Mock report provider | `mock_report_provider.py` | Template reports |
| Report provider | `report_provider.py` | ABC for reports |
| Report repository | `report_repository.py` | Report persistence |

**Domain entities:**

| Entity | File | Key fields |
|--------|------|------------|
| `SpillIncident` | `domain/entities.py` | id, confidence, area_km2, centroid, geometry, detected_at, region, wind_speed_kts |
| `SatelliteSceneRecord` | `domain/entities.py` | id, platform, footprint, status, product_id |
| `LookAlikeFeatures` | `domain/entities.py` | mean_intensity_anomaly_db, aspect_ratio, wind_speed_knots |
| `ConfidenceBreakdown` | `domain/entities.py` | raw_model_confidence, adjusted_confidence, penalties |
| `AisObservation` | `domain/ais.py` | mmsi, timestamp, lat, lon, sog, cog, vessel_type |
| `CandidateVessel` | `domain/ais.py` | mmsi, attribution_score, score_components |
| `SourceEstimate` | `domain/ais.py` | latitude, longitude, uncertainty_km, uncertainty_hours |
| `DriftResult` | `services/drift_provider.py` | source_latitude, source_longitude, uncertainty_km, trajectories |
| `EnvironmentalConditions` | `services/environmental_provider.py` | current_u, current_v, wind_u, wind_v, provider, environment_status |

### 2.4 Data Flow

```
SENTINEL-1 SAR
    ↓
Copernicus CDSE (satellite/providers/copernicus.py)
    ↓
Scene Download + GRD Preprocessing (grd_preprocess.py)
    ↓
Model Inference (inference/mock_adapter.py or torch_adapter.py)
    ↓
Detection Post-processing (polygon extraction, confidence)
    ↓
SpillIncident → Repository (memory_repo.py or postgis_repo.py)
    ↓
API Routes → Frontend (React Query)
    ↓
Investigation Trigger (POST /investigation/{id}/run)
    ↓
┌──────────────────┬──────────────────┬──────────────────┐
│ Drift Engine     │ AIS Correlation  │ Intelligence     │
│ drift_engine.py  │ ais_correlation  │ intelligence_    │
│                  │ .py              │ assembly.py      │
│ Environmental    │ AIS Provider     │ Confidence       │
│ Provider →       │ (mock/gfw) →     │ Calibrator,      │
│ (mock/real) →    │ CandidateVessels │ LookAlike,       │
│ DriftResult      │ → Attribution    │ Environmental,   │
│                  │   Result         │ Seasonal, Small  │
└────────┬─────────┴────────┬─────────┴────────┬─────────┘
         │                  │                  │
         └──────────┬───────┘                  │
                    ↓                          │
         InvestigationResponse ←───────────────┘
                    ↓
         Frontend Map/Panel/Report
```

---

## 3. EXISTING CAPABILITIES (VERIFIED)

### 3.1 Map System

| Capability | Status | Location |
|------------|--------|----------|
| MapLibre GL v4.7.1 | Installed | `package.json:18` |
| 2D flat Mercator projection | Active | `map-view.tsx:77-87` |
| Globe projection support | Available (not enabled) | MapLibre v4.7.1 native |
| CARTO dark-matter basemap | Active | `.env:8`, `map-config.ts:14` |
| Raster fallback | Available | `map-config.ts:28-45` |
| Env-configurable style URL | Active | `NEXT_PUBLIC_MAP_STYLE_URL` |
| flyTo animation | Active | `map-view.tsx:849-858` |
| easeTo animation | Active | `map-view.tsx:862` |
| fitBounds | Active | `map-view.tsx:865` |
| 8 GeoJSON sources | Active | `map-view.tsx:146-195` |
| 15+ vector layers | Active | `map-view.tsx:197-487` |
| Layer visibility toggle | Active | `map-view.tsx:821-846` |
| Selection highlight + pulse | Active | `map-view.tsx:763-812` |
| Click-to-select incident | Active | `map-view.tsx:489-495` |
| Popup on click (source, vessel) | Active | `map-view.tsx:366-536` |
| Hover popup (detection) | Active | `map-view.tsx:547-573` |
| ResizeObserver handling | Active | `map-view.tsx:123-129` |
| Fullscreen toggle | Active | `map-view.tsx:880-884` |

### 3.2 Particle Animation System

| Capability | Status | Location |
|------------|--------|----------|
| Oil spill particles (canvas) | Active | `drift-map-view.tsx:859-984` |
| 420 particles with trails | Active | `drift-map-view.tsx:877` |
| Color gradient along time | Active | `drift-map-view.tsx:32-58` |
| Wind streamline particles (canvas) | Active | `drift-map-view.tsx:986-1068` |
| 180 wind particles | Active | `drift-map-view.tsx:1008` |
| Current streamline particles (canvas) | Active | `drift-map-view.tsx:1070-1152` |
| 120 current particles | Active | `drift-map-view.tsx:1092` |
| requestAnimationFrame rendering | Active | All canvas layers |
| DPR-aware canvas scaling | Active | All canvas layers |

**CRITICAL:** Wind and current particles use hardcoded angles:
- Wind: `windAngleRad = (242 * Math.PI) / 180` (`drift-map-view.tsx:1004`)
- Current: `currentAngleRad = (1.2 * Math.PI) / 180` (`drift-map-view.tsx:1088`)
- These are NOT real data — they are synthetic flow fields

### 3.3 Timeline System

| Capability | Status | Location |
|------------|--------|----------|
| Timeline UI component | Active | `drift-timeline.tsx` |
| Play/pause controls | Active | `drift-map/page.tsx:55-56` |
| Speed control | Active | `drift-map/page.tsx:56` |
| Scrub/seek | Active | `drift-map/page.tsx:519` |
| Animation progress (0→1) | Active | `drift-map/page.tsx:57` |
| 8-hour duration | Active | `drift-map/page.tsx:515` |
| Drives oil particles | Active | `drift-map-view.tsx:929` |
| Drives vessel positions | Active | `drift-map-view.tsx:789-798` |
| Drives trajectory markers | Active | `drift-map-view.tsx:729-768` |

**NOT connected to timeline:**
- Environmental wind/current layers (hardcoded angles)
- Real AIS track positions
- Oil slick position changes
- Drift trajectory changes

### 3.4 Drift Engine

| Capability | Status | Location |
|------------|--------|----------|
| First-order backward hindcast | Active | `drift_engine.py:49-210` |
| 50 ensemble particles | Active | `drift_engine.py:85` |
| Current + windage forcing | Active | `drift_engine.py:122-124` |
| Source point estimation | Active | `drift_engine.py:148-152` |
| Uncertainty from ensemble spread | Active | `drift_engine.py:155-157` |
| Time uncertainty | Active | `drift_engine.py:163-166` |
| Quality flags | Active | `drift_engine.py:172-178` |
| Provenance tracking | Active | `drift_engine.py:199-208` |
| Trajectory points (per particle) | Active | `DriftTrajectory.points` |
| Source points (centroid array) | Active | `DriftResult.source_points` |

### 3.5 Environmental Data

| Capability | Status | Location |
|------------|--------|----------|
| Provider abstraction | Active | `environmental_provider.py:35-58` |
| Mock provider | Active | `environmental_mock_provider.py:18-69` |
| Real provider (CMEMS + ERA5) | Active | `environmental_real_provider.py:44-489` |
| CMEMS currents (uo, vo) | Active | `environmental_real_provider.py:37-38` |
| ERA5 winds (u10, v10) | Active | `environmental_real_provider.py:40-41` |
| Bilinear interpolation | Active | `environmental_real_provider.py:427-489` |
| Temporal interpolation | Active | `environmental_real_provider.py:173-200` |
| Cache system (prepare_cache) | Active | `environmental_real_provider.py:93-155` |
| 0.25° grid resolution | Active | `environmental_real_provider.py:213` |
| CMEMS dataset ID | `cmems_obs-mob_glo_phy-cur_my_0.25deg_PT1H-i` | `environmental_real_provider.py:37` |
| ERA5 dataset | `reanalysis-era5-single-levels` | `environmental_real_provider.py:40` |
| Credentials configured | YES | `.env:66-77` |
| ENVIRONMENTAL_PROVIDER=real | Active | `.env:66` |

### 3.6 AIS System

| Capability | Status | Location |
|------------|--------|----------|
| Provider abstraction | Active | `ais_provider.py:14-42` |
| Mock provider | Active | `ais_mock_provider.py` |
| GFW provider (real) | Active | `ais_gfw_provider.py:30-202` |
| GFW 4Wings API v3 | Active | `ais_gfw_provider.py:27-28` |
| Vessel correlation engine | Active | `ais_correlation.py` |
| Attribution scoring | Active | `CandidateVessel.attribution_score` |
| Score components (distance, time, track) | Active | `ScoreComponents` |
| Search window construction | Active | `AisSearchWindow` |
| AIS gap detection | Partial | `ais_gap_detector.py` (requires raw AIS) |
| Static spacing detection | Partial | Requires raw transmission data |
| Vessel type prior | Not implemented | `vessel_type_prior: None` |

### 3.7 Intelligence System (Phase 8)

| Capability | Status | Location |
|------------|--------|----------|
| Intelligence assembly | Active | `intelligence_assembly.py:47-105` |
| Look-alike screening | HEURISTIC | `look_alike_classifier.py` |
| Environmental reliability | HEURISTIC | `environmental_reliability.py` |
| Small detection assessment | HEURISTIC | `small_detection_assessor.py` |
| Seasonal prior | HEURISTIC | `seasonal_prior.py` |
| Confidence calibration | NOT_CALIBRATED | `confidence_calibrator.py` |
| Confidence breakdown | Active | `ConfidenceBreakdownResponse` |
| Per-vessel evidence | Active | `VesselEvidenceResponse` |
| Provenance tracking | Active | `ProvenanceEvidence` |

### 3.8 SSE Event System

| Capability | Status | Location |
|------------|--------|----------|
| In-process EventHub | Active | `event_hub.py:25-78` |
| Cursor-based subscription | Active | `event_hub.py:43-51` |
| Async stream | Active | `event_hub.py:53-63` |
| 15s heartbeat | Active | `events.py:23` |
| Frontend SSE hook | Active | `use-sse.ts:47-137` |
| Event type mapping | Active | `use-sse.ts:144-191` |
| Auto-reconnect | Active | `use-sse.ts:80-81` |

**Backend event types emitted:**
`scene.discovered`, `scene.download.started/completed`, `scene.extraction.started/completed`, `scene.calibration.started/completed`, `scene.georeferencing.started/completed`, `scene.preprocessing.started/completed`, `scene.inference.started/completed`, `pipeline.failed`, `detection.created`, `attribution.started/completed/failed`, `drift.started/completed/failed`, `investigation.started/completed/failed`

### 3.9 Mock/Real Mode System

| Capability | Status | Location |
|------------|--------|----------|
| Frontend mode switch | Active | `NEXT_PUBLIC_API_MODE` in `.env:3` |
| Backend mode switch | Active | `MODEL_ADAPTER`, `SATELLITE_PROVIDER`, `AIS_PROVIDER`, `ENVIRONMENTAL_PROVIDER` |
| API abstraction layer | Active | `client.ts:31-32` — delegates to `mockApi` or `httpApi` |
| Backend falls back gracefully | Active | `drift.py:113-122` — real provider failure → mock |

### 3.10 Report System

| Capability | Status | Location |
|------------|--------|----------|
| Groq report provider | Active | `groq_report_provider.py` |
| Mock report provider | Active | `mock_report_provider.py` |
| Evidence builder | Active | `evidence_builder.py:36-105` |
| PDF generation | Active | `generate-report-pdf.ts` |
| Report storage | Active | `report_repository.py` |

---

## 4. TARGET FEATURES

### 4.1 Feature 1 — Real/NRT Environmental Intelligence

**Goal:** Visualize actual wind and ocean current conditions on the map, similar to Windy.

**Required data:**

| Variable | Source | Dataset | Resolution | Latency |
|----------|--------|---------|------------|---------|
| Wind speed | ECMWF ERA5 | `reanalysis-era5-single-levels` | 0.25° hourly | ~5-9 hours |
| Wind direction | ECMWF ERA5 | `reanalysis-era5-single-levels` | 0.25° hourly | ~5-9 hours |
| Wind U component | ECMWF ERA5 | `10m_u_component_of_wind` | 0.25° hourly | ~5-9 hours |
| Wind V component | ECMWF ERA5 | `10m_v_component_of_wind` | 0.25° hourly | ~5-9 hours |
| Current speed | CMEMS | `cmems_obs-mob_glo_phy-cur_my_0.25deg_PT1H-i` | 0.25° hourly | ~1-2 days |
| Current direction | CMEMS | `cmems_obs-mob_glo_phy-cur_my_0.25deg_PT1H-i` | 0.25° hourly | ~1-2 days |
| Current U (uo) | CMEMS | `cmems_obs-mob_glo_phy-cur_my_0.25deg_PT1H-i` | 0.25° hourly | ~1-2 days |
| Current V (vo) | CMEMS | `cmems_obs-mob_glo_phy-cur_my_0.25deg_PT1H-i` | 0.25° hourly | ~1-2 days |

**Data status labels:**

| Label | Meaning |
|-------|---------|
| LIVE | True real-time observation (NOT applicable to ERA5/CMEMS) |
| NRT | Near-real-time, <24h latency (ERA5 is ~5-9h, CMEMS is ~1-2 days) |
| FORECAST | Model prediction (NOT applicable — these are reanalysis) |
| HISTORICAL | Past data (>7 days old) |
| DEMO | Synthetic/mock data |
| STALE | Data older than expected latency |
| UNAVAILABLE | Data fetch failed or credentials missing |

**IMPORTANT:** ERA5 is reanalysis, NOT live observation. CMEMS is NRT product, NOT live observation. Never label either as "LIVE".

**Visual requirements:**

- Animated wind particles (canvas-based, already partially implemented)
- Animated current particles (canvas-based, already partially implemented)
- Wind vectors (arrows showing direction and speed)
- Current vectors (arrows showing direction and speed)
- Layer toggles for wind and current independently
- Animation speed control per layer
- Play/pause per layer
- Timestamps showing data time
- Provider information (ERA5, CMEMS)
- Data age indicator

**Backend changes needed:**
- New endpoint: `GET /environmental/grid?bbox=...&time=...&variable=wind|current` returning vector grid for visualization
- Or: pre-computed particle positions served per timestep

**Frontend changes needed:**
- Replace hardcoded angles in `drift-map-view.tsx:1004,1088` with real grid data
- Add data-age badge, provider badge, timestamp display
- Add DEMO/LIVE/NRT status indicators to canvas layers

---

### 4.2 Feature 2 — Operational Criticality Score

**Goal:** A single operational priority index (0-100) that tells operators which incidents require immediate attention.

**This is NOT:**
- Detection confidence
- Model confidence
- Attribution probability
- Environmental damage probability

**This IS:**
- Operational priority / criticality index

**Factor assessment (from audit):**

| Factor | Weight | Existing Data | Source | Status |
|--------|--------|---------------|--------|--------|
| Spill size | 20% | `incident.area_km2` | `domain/entities.py:65` | AVAILABLE |
| Detection confidence | 15% | `intelligence.confidence_breakdown.adjusted_confidence` | `schemas/intelligence.py:108` | AVAILABLE |
| Coastal/sensitive risk | 20% | — | — | MISSING — needs geospatial lookup |
| Environmental spreading | 15% | `intelligence.environmental_reliability.wind_speed_knots`, `current_speed_ms` | `schemas/intelligence.py:41-49` | AVAILABLE |
| Spill age | 10% | `drift.uncertainty_hours`, `drift.source_earliest`/`source_latest` | `schemas/drift.py:40-41` | AVAILABLE |
| Projected drift impact | 10% | `drift.uncertainty_km`, `drift.confidence` | `schemas/drift.py:38,42` | PARTIAL — needs coastal intersection |
| AIS/traffic evidence | 10% | `attribution.candidates[].attribution_score` | `schemas/attribution.py:54` | AVAILABLE |

**Minimum viable formula:**
- 6 of 8 factors available from existing backend evidence
- Missing: coastal/sensitive-area distance
- Missing: projected drift impact on coastline

**Backend changes needed:**
- New service: `criticality_scorer.py`
- Coastline geometry: Natural Earth or GSHHG data (Shapely already in requirements)
- New schema: `CriticalityResponse` with breakdown
- Add criticality to investigation response

**Frontend changes needed:**
- New component: `CriticalityCard` with score display and breakdown bars
- Integration into right-side panel of investigation workspace

---

### 4.3 Feature 3 — Map-Centric Investigation Interface

**Goal:** Transform the product from a dashboard into a map-centric investigation workspace.

**Desired layout:**

```
+----------------------------------------------------------------+
| SAGAR WATCH | GLOBAL | INVESTIGATE | LIVE | REPORTS            |
+----------------------------------------------------------------+
|                |                                  |            |
| INVESTIGATION  |                                  | INTELLIGENCE|
| PIPELINE       |                                  |            |
|                |                                  | CRITICALITY |
| ✓ Satellite    |          LARGE COLOURED           | 82 / 100   |
| ✓ Detection    |             MAP                  | HIGH        |
| ✓ Environment  |                                  |            |
| ✓ Drift        |       OIL SLICK                  | EVIDENCE   |
| ✓ AIS          |          ↓                       |            |
| ✓ Attribution  |       DRIFT                     | Confidence |
| ● Assessment  |                                  | Area       |
| ○ Report       |       🚢 AIS                    | Age        |
|                |          🚢                      |            |
+----------------------------------------------------------------+
|                    MASTER TIMELINE                             |
| -72h -------- -48h -------- -24h -------- NOW                 |
+----------------------------------------------------------------+
```

**Map must be 65-75% of workspace.**

**Left panel — Investigation Pipeline:**

| Stage | Label | Status |
|-------|-------|--------|
| 01 | SATELLITE | WAITING / RUNNING / COMPLETE / FAILED / UNAVAILABLE |
| 02 | DETECTION | WAITING / RUNNING / COMPLETE / FAILED / UNAVAILABLE |
| 03 | ENVIRONMENT | WAITING / RUNNING / COMPLETE / FAILED / UNAVAILABLE |
| 04 | DRIFT | WAITING / RUNNING / COMPLETE / FAILED / UNAVAILABLE |
| 05 | AIS | WAITING / RUNNING / COMPLETE / FAILED / UNAVAILABLE |
| 06 | ATTRIBUTION | WAITING / RUNNING / COMPLETE / FAILED / UNAVAILABLE |
| 07 | ASSESSMENT | WAITING / RUNNING / COMPLETE / FAILED / UNAVAILABLE |
| 08 | REPORT | WAITING / RUNNING / COMPLETE / FAILED / UNAVAILABLE |

**Right panel — Contextual Intelligence:**

When user selects OIL: show area, confidence, age, criticality
When user selects SOURCE: show coordinates, uncertainty, drift, ensemble
When user selects VESSEL: show vessel, AIS observations, distance, attribution
When user selects ENVIRONMENT: show wind, current, provider, timestamp

**Route recommendation:** `/investigate/[incidentId]`

**Existing page analysis:**

| Page | Reuse? | Status |
|------|--------|--------|
| `/drift-map` | REUSE as investigation workspace | 80% complete |
| `/live-analysis` | MODIFY pipeline stages into sidebar | Pipeline logic exists |
| `/incident/[id]` | KEEP as detail view | Server-rendered, works |
| `investigation-map.tsx` | REPLACE SVG with real MapLibre | Currently SVG placeholder |

---

## 5. GLOBE → INCIDENT → INVESTIGATION FLOW

### 5.1 Globe Support

MapLibre GL v4.7.1 natively supports 3D globe projection via:
```typescript
const map = new maplibregl.Map({
  projection: 'globe',  // enables 3D Earth rendering
  // ...other options
});
```

### 5.2 Camera Flow

1. **Initial state:** `projection: 'globe'`, `zoom: 1.5`, center `[0, 20]`
2. **Incident markers:** Small colored dots on globe (HIGH=red, MEDIUM=amber, LOW=yellow)
3. **On incident click:** `map.setProjection('mercator')` + `map.flyTo({ center, zoom: 9, duration: 2000 })`
4. **Final state:** 2D Mercator investigation workspace

### 5.3 Transition Mechanics

- Globe and Mercator are the SAME MapLibre instance
- `map.setProjection()` switches between modes
- No separate component needed
- flyTo/easeTo work in both projection modes

### 5.4 Required Changes

- Enable `projection: 'globe'` on initial map load
- Add incident markers as GeoJSON points on globe
- Implement `setProjection('mercator')` on incident selection
- Remove `dragRotate: false` and `pitchWithRotate: false` when in globe mode (allow rotation)
- Add polar rotation limits (prevent viewing poles)

### 5.5 Performance Considerations

- Globe rendering is GPU-accelerated
- Acceptable on modern laptops with integrated GPU
- CARTO vector tiles render on globe
- Satellite raster tiles may have pole distortion (acceptable for Indian Ocean)

---

## 6. COLOURED MAP REQUIREMENTS

### 6.1 Current Basemap

- Provider: CARTO
- Style: `dark-matter-gl-style` (vector tiles)
- Color: predominantly black/dark
- Config: `NEXT_PUBLIC_MAP_STYLE_URL` env var

### 6.2 Desired Map Modes

| Mode | Style | Provider | Color |
|------|-------|----------|-------|
| Satellite | World Imagery | ESRI | Satellite imagery |
| Ocean | Custom blue ocean | MapTiler or custom | Blue ocean, visible coastlines |
| Terrain | Stamen Terrain | Stadia Maps | Topographic |
| Dark (current) | Dark Matter | CARTO | Dark (existing) |

### 6.3 Style Switching

- Add `MapStyleSwitcher` UI component
- Store selected style in Zustand state
- Update `getMapStyleUrl()` to return selected style
- All existing data layers persist across style changes (GeoJSON sources are style-independent)

### 6.4 Licensing

| Provider | License | Cost |
|----------|---------|------|
| CARTO | Free (attribution) | $0 |
| ESRI World Imagery | Free for non-commercial (attribution) | $0 |
| MapTiler | Free tier (50k tiles/month) | $0 (limited) |
| Stadia Maps | Free tier available | $0 (limited) |

### 6.5 Performance

- Vector styles (CARTO): ~200ms load
- Satellite raster: ~500ms first load, cached after
- No significant difference for investigation use

---

## 7. MASTER TIMELINE REQUIREMENTS

### 7.1 Current State

- Timeline UI: `drift-timeline.tsx` (8-hour duration)
- State: React `useState` in `drift-map/page.tsx:55-58`
- Controls: play, pause, speed, scrub, seek
- Drives: oil particles, vessel markers, trajectory time markers

### 7.2 Desired State

One unified timeline that controls ALL time-varying layers:

| Layer | Current Control | Required Control |
|-------|-----------------|------------------|
| Oil particles | YES (via animationProgress) | YES |
| Vessel positions | YES (via animationProgress) | YES |
| Trajectory markers | YES (via sourcePoints index) | YES |
| Wind particles | NO (hardcoded angle) | YES — change wind field with time |
| Current particles | NO (hardcoded angle) | YES — change current field with time |
| Oil slick position | NO (static) | YES — move slick along trajectory |
| Drift trajectory | NO (static) | YES — show trajectory at current time |
| AIS tracks | NO (static) | YES — show vessel position at current time |

### 7.3 State Architecture

Centralize time state in Zustand:
```
currentTime: Date          — the "now" of the investigation
isPlaying: boolean        — playback state
speed: number             — playback speed multiplier
timeWindow: { start, end } — visible range (e.g., -72h to NOW)
```

All layers subscribe to `currentTime` from Zustand store.

### 7.4 Time Window Options

- 72h / 48h / 24h windows (configurable)
- Event markers on timeline (detection, source, AIS observations)
- Current timestamp indicator
- Synchronized layer updates

---

## 8. DATA FLOW (DETAILED)

### 8.1 Sentinel-1 Ingestion

```
Copernicus CDSE
    ↓ copernicus.py (auth, search, download)
GRD Product (TIFF)
    ↓ grd_preprocess.py (calibration, georeferencing)
Processed Scene (EPSG:4326)
    ↓ inference_service.py (mock_adapter or torch_adapter)
Probability Mask
    ↓ geospatial processing (polygon extraction)
SpillIncident (with GeoJSON geometry)
    ↓ repository (memory_repo or postgis_repo)
    ↓ event_hub (detection.created)
Frontend (React Query → Map)
```

### 8.2 Investigation Pipeline

```
POST /investigation/{id}/run
    ↓
1. Load incident from repository
    ↓
2. Create EnvironmentalProvider (mock or real)
   ├─ RealEnvironmentalProvider: fetch CMEMS + ERA5 grids
   │  → prepare_cache(bbox, timesteps)
   │  → 5-30 seconds one-time fetch
   └─ MockEnvironmentalProvider: deterministic values
    ↓
3. Run DriftEngine.estimate_source()
   → 50 ensemble particles, backward integration
   → DriftResult (source_lat/lon, uncertainty, trajectories)
    ↓
4. Convert DriftResult → SourceEstimate
    ↓
5. Run AIS Correlation
   ├─ GFW Provider: query 4Wings API
   └─ Mock Provider: deterministic vessels
   → AttributionResult (ranked candidates)
    ↓
6. Assemble Intelligence (Phase 8)
   → LookAlike, Environmental, SmallDetection, Seasonal, Calibration
   → DetectionIntelligenceResponse
    ↓
7. Return InvestigationResponse
   (drift + attribution + intelligence + environment_status)
```

### 8.3 Environmental Data Flow

```
CMEMS (copernicusmarine.open_dataset)
    ↓
xarray Dataset (uo, vo per timestep)
    ↓ numpy extraction
dict[datetime, ndarray(n_lat, n_lon, 2)]  — currents grid
    ↓ bilinear interpolation
EnvironmentalConditions(current_u, current_v, ...)
    ↓
DriftEngine (v = current + windage × wind)
    ↓
DriftResult
```

```
ERA5 (cdsapi.Client.retrieve)
    ↓
xarray Dataset (u10, v10 per timestep)
    ↓ numpy extraction
dict[datetime, ndarray(n_lat, n_lon, 2)]  — winds grid
    ↓ bilinear interpolation
EnvironmentalConditions(wind_u, wind_v, ...)
    ↓
DriftEngine (v = current + windage × wind)
    ↓
DriftResult
```

### 8.4 SSE Event Flow

```
Backend Service (drift, attribution, etc.)
    ↓ event_hub.publish(type, payload)
EventHub (in-process buffer)
    ↓ hub.stream(cursor, heartbeat)
GET /events/stream (FastAPI StreamingResponse)
    ↓ text/event-stream
Frontend useSSE() hook (EventSource)
    ↓ onEvent callback
React state update → UI refresh
```

---

## 9. API ARCHITECTURE

### 9.1 Existing Endpoints

| Method | Path | Purpose | Real Data |
|--------|------|---------|-----------|
| GET | `/api/v1/health` | Health check | Yes |
| GET | `/api/v1/system/status` | System status | Yes (seed) |
| GET | `/api/v1/spills` | List incidents | Yes (seed/demo) |
| GET | `/api/v1/spills/{id}` | Get incident | Yes (seed/demo) |
| GET | `/api/v1/spills/{id}/geometry` | GeoJSON geometry | Yes |
| GET | `/api/v1/satellite/scenes` | List scenes | Yes (seed) |
| GET | `/api/v1/satellite/scenes/{id}` | Get scene | Yes (seed) |
| GET | `/api/v1/satellite/scenes/provider` | Provider info | Yes |
| POST | `/api/v1/attribution/analyze` | AIS analysis | Real/Mock |
| GET | `/api/v1/attribution/{id}` | Get attribution | Real/Mock |
| POST | `/api/v1/drift/analyze` | Drift hindcast | Real/Mock |
| GET | `/api/v1/drift/{id}` | Get drift | Real/Mock |
| POST | `/api/v1/investigation/{id}/run` | Full investigation | Real/Mock |
| GET | `/api/v1/reports/investigation/{id}` | Get report | Real/Mock |
| POST | `/api/v1/reports/investigation/{id}` | Generate report | Real/Mock |
| GET | `/api/v1/events/stream` | SSE events | Yes |
| GET | `/api/v1/analytics/summary` | Analytics | Yes (seed) |
| POST | `/api/v1/reviews/{id}` | False-positive review | Yes |
| GET | `/api/v1/pipeline/jobs` | Pipeline jobs | Yes |

### 9.2 New Endpoints Needed

| Method | Path | Purpose | Reason |
|--------|------|---------|--------|
| GET | `/api/v1/environmental/grid` | Gridded wind/current vectors | Frontend particle visualization |
| GET | `/api/v1/environmental/point` | Point conditions at lat/lon/time | Environmental panel display |
| GET | `/api/v1/criticality/{id}` | Criticality score | New feature |

### 9.3 Response Format

All responses use camelCase aliases (Pydantic `alias_generator=to_camel`). Frontend TypeScript types in `src/lib/types.ts` match exactly.

---

## 10. STATE ARCHITECTURE

### 10.1 Current Zustand Store

Location: `src/lib/store/use-app-store.ts`

```
selectedIncidentId: string | null
selectedIncident: Incident | null
detailsOpen: boolean
viewerIncidentId: string | null
viewerTab: ViewerTab
filters: { search, levels, timeRange, region }
activeLayers: Record<MapLayerId, boolean>
flyTo: FlyToTarget | null
sidebarOpenMobile: boolean
detailsOpenMobile: boolean
```

**Actions:**
`selectIncident`, `clearSelection`, `openViewer`, `closeViewer`, `setViewerTab`, `setSearch`, `toggleLevel`, `setTimeRange`, `setRegion`, `resetFilters`, `toggleLayer`, `requestFlyTo`, `setSidebarOpenMobile`, `setDetailsOpenMobile`

### 10.2 New State Needed

For Master Timeline:
```
currentTime: Date
isPlaying: boolean
speed: number
timeWindow: { start: Date, end: Date }
```

For Map Style:
```
mapStyle: 'dark' | 'satellite' | 'ocean' | 'terrain'
```

For Globe:
```
projectionMode: 'globe' | 'mercator'
```

For Investigation:
```
selectedMapObject: { type: 'oil' | 'source' | 'vessel' | 'environment', id: string }
investigationPanelOpen: boolean
```

### 10.3 React Query Keys

| Query Key | Purpose | Cache |
|-----------|---------|-------|
| `["incidents"]` | Incident list | Default |
| `["drift", id]` | Drift result | Default |
| `["attribution", id]` | Attribution result | Default |
| `["report", id]` | Investigation report | Default |
| `["scene", id]` | Satellite scene | Default |
| `["system-status"]` | System status | Default |
| `["satellite-provider"]` | Provider info | Default |

---

## 11. MOCK VS REAL RULES

### 11.1 Current Mock Data Locations

| File | Function | Behavior |
|------|----------|----------|
| `src/lib/api/client.ts` | `mockApi.*` | Returns local mock data |
| `src/lib/api/client.ts` | `mockDrift()` | Bezier trajectory from incident centroid |
| `src/lib/api/client.ts` | `mockAttribution()` | 3 hardcoded vessels |
| `src/lib/api/client.ts` | `mockReport()` | Template text |
| `src/lib/mock-data/incidents.ts` | `INCIDENTS` | 9 seeded incidents |
| `src/lib/mock-data/scenes.ts` | `SCENES` | Demo scenes |
| `src/lib/mock-data/analytics.ts` | `ANALYTICS_SUMMARY` | Demo analytics |
| `src/lib/mock-data/system-status.ts` | `SYSTEM_STATUS` | Demo status |
| `drift-map-view.tsx:1004` | Wind particles | Hardcoded `242°` angle |
| `drift-map-view.tsx:1088` | Current particles | Hardcoded `1.2°` angle |
| `drift-map-view.tsx:60-115` | Vessel positions | Deterministic interpolation |
| `live-analysis/page.tsx:211-243` | `handleRunSimulation` | setTimeout-based fake pipeline |

### 11.2 Mock Rules

1. **Every mock data point must be clearly labeled DEMO in the UI**
2. **Never present mock values as real observations**
3. **Never call forecast data "live observation"**
4. **The UI must distinguish: LIVE / NRT / FORECAST / HISTORICAL / DEMO / STALE / UNAVAILABLE**
5. **Canvas particle layers with hardcoded angles MUST have DEMO badge**
6. **When switching to real mode, all DEMO badges disappear**

### 11.3 Mode Detection

| Layer | Mock Indicator | Real Indicator |
|-------|----------------|----------------|
| Drift | `qualityFlags: ["DEMO_ENVIRONMENTAL_FORCING"]` | `qualityFlags: ["REAL_ENVIRONMENTAL_FORCING"]` |
| AIS | `provider: "mock"` | `provider: "gfw"` |
| Environmental | `environment_status: "DEMO"` | `environment_status: "REAL"` |
| Report | `provider: "mock"` | `provider: "groq"` |
| Wind/Current particles | NO INDICATOR (BUG) | Should show provider + timestamp |

---

## 12. SCIENTIFIC TERMINOLOGY RULES

### 12.1 Forbidden Terms

| Never Say | Instead Say |
|-----------|-------------|
| "Real-time" | "Near-real-time (NRT)" or "Reanalysis" |
| "Source location" | "Estimated source region" or "Back-projected origin" |
| "Vessel caused the spill" | "Potential source association" |
| "Spill age" | "Estimated release window" |
| "Environmental damage" | "Operational criticality" |
| "Forecast" | "Hindcast" (backward) or "Model projection" (forward) |
| "Observed slick" | "AI-detected potential slick" or "Model-predicted anomaly" |
| "Confidence = oil present" | "Model confidence score (classifier output)" |
| "Vessel attribution = responsibility" | "Proximity-based vessel ranking" |

### 12.2 Critical Distinctions

| Concept | Correct Definition | Common Misconception |
|---------|-------------------|---------------------|
| CRITICALITY | Operational priority index | Environmental damage probability |
| ATTRIBUTION | Proximity-based vessel ranking | Proof of responsibility |
| BACKWARD DRIFT | Estimated release region | Exact source location |
| MODEL PROJECTION | Model output (not observation) | Live observation |
| ESTIMATED AGE | Time window from drift model | Chemical weathering measurement |
| MODEL CONFIDENCE | Classifier probability output | Probability of oil being present |

### 12.3 Required UI Language

- Source popup: "Source location is an estimate. Not a confirmed origin point."
- Vessel popup: "Human review required — AIS proximity does not establish causation."
- Detection: "Potential dark-surface anomaly identified in Sentinel-1 SAR."
- Report: "This is an AI-generated summary based on system evidence."
- Confidence: "Raw model confidence: 85%. Adjusted: 78%. Calibration: NOT_CALIBRATED."

---

## 13. SECURITY REQUIREMENTS

### 13.1 Environment Variables

| Variable | Purpose | In .env | In .gitignore | Risk |
|----------|---------|---------|---------------|------|
| `CDSE_USERNAME` | Copernicus login | YES | YES (.env) | If .env committed → compromised |
| `CDSE_PASSWORD` | Copernicus password | YES | YES (.env) | If .env committed → compromised |
| `CMEMS_USERNAME` | Marine login | YES | YES (.env) | If .env committed → compromised |
| `CMEMS_PASSWORD` | Marine password | YES | YES (.env) | If .env committed → compromised |
| `CDS_API_KEY` | ECMWF API key | YES | YES (.env) | If .env committed → compromised |
| `GFW_API_TOKEN` | GFW JWT token | YES | YES (.env) | If .env committed → compromised |
| `GROQ_API_KEY` | Groq API key | YES | YES (.env) | If .env committed → compromised |
| `NEXT_PUBLIC_API_MODE` | Frontend mode | YES | No (not secret) | Safe |
| `NEXT_PUBLIC_MAP_STYLE_URL` | Basemap URL | YES | No (not secret) | Safe |
| `NEXT_PUBLIC_API_BASE_URL` | Backend URL | YES | No (not secret) | Safe |

### 13.2 Security Rules

1. Never print secrets in logs or API responses
2. Never commit `.env` files
3. Rotate all credentials if `.env` was ever committed to git
4. Frontend env vars with `NEXT_PUBLIC_` prefix are visible in browser — must not contain secrets
5. Backend CORS: currently `http://localhost:3000` — restrict in production

---

## 14. PERFORMANCE CONSTRAINTS

### 14.1 Hardware Target

- SIH demo laptop: modern laptop with integrated GPU
- No GPU infrastructure required
- All features must run at 30fps minimum

### 14.2 Rendering Budget

| Component | Current | Budget |
|-----------|---------|--------|
| MapLibre vector layers | 15+ layers | <5ms/frame |
| Canvas oil particles (420) | 60fps | <8ms/frame |
| Canvas wind particles (180) | 60fps | <3ms/frame |
| Canvas current particles (120) | 60fps | <2ms/frame |
| React re-renders | Zustand selectors | <1ms |
| Timeline scrub | 40ms interval | <5ms per update |

### 14.3 Network Budget

| Operation | Expected Latency |
|-----------|-------------------|
| CARTO basemap tiles | ~100ms |
| Satellite basemap tiles | ~300ms first load |
| CMEMS data fetch | 5-30 seconds (one-time per incident) |
| ERA5 data fetch | 5-30 seconds (one-time per incident) |
| GFW AIS query | 1-5 seconds |
| Investigation API | 10-60 seconds (drift computation) |
| Report generation (Groq) | 5-15 seconds |
| SSE heartbeat | 15 seconds |

### 14.4 Data Volume

| Data | Size |
|------|------|
| Environmental grid (0.25° over India) | ~1600 points, ~50KB JSON |
| 9 incidents with geometry | ~100KB |
| Drift trajectories (50 particles) | ~200KB |
| AIS candidates (5 vessels) | ~10KB |

---

## 15. REUSE / MODIFY / CREATE COMPONENT PLAN

### 15.1 REUSE (No Changes)

| Component | File | Reason |
|-----------|------|--------|
| Map initialization | `map-view.tsx` | Fully functional MapLibre setup |
| Map config | `map-config.ts` | Style URL resolution, constants |
| Spill styling | `spill-style.ts` | Color expressions for detection layers |
| Map controls | `map-controls.tsx` | Zoom/locate/fullscreen buttons |
| Layer panel | `layer-panel.tsx` | Layer toggle UI |
| Drift map view | `drift-map-view.tsx` | Full investigation map (90% complete) |
| Drift timeline | `drift-timeline.tsx` | Play/pause/scrub UI |
| Drift layer control | `drift-layer-control.tsx` | 10 layer toggles |
| Drift legend | `drift-legend.tsx` | Color legend |
| Drift status card | `drift-status-card.tsx` | Real/demo indicator |
| Source estimate card | `source-estimate-card.tsx` | Modal overlay |
| AIS vessel card | `ais-vessel-card.tsx` | Modal overlay |
| Environment panel | `environment-panel.tsx` | Wind/current display |
| Drift summary panel | `drift-summary-panel.tsx` | Right-side evidence |
| Page shell | `page-shell.tsx` | Layout wrapper |
| Top nav | `top-nav.tsx` | Navigation |
| All UI primitives | `ui/*.tsx` | Badge, button, card, input, select, states |
| API client | `api/client.ts` | Mock/real abstraction |
| HTTP client | `api/http-client.ts` | FastAPI integration |
| SSE hook | `hooks/use-sse.ts` | EventSource connection |
| Store | `store/use-app-store.ts` | Zustand state |
| Types | `types.ts` | TypeScript definitions |
| Utils | `utils.ts`, `geo.ts` | Utilities |

### 15.2 MODIFY

| Component | File | Change |
|-----------|------|--------|
| Investigation map | `investigation-map.tsx` | Replace SVG with real MapLibre instance |
| Drift map view | `drift-map-view.tsx` | Replace hardcoded wind/current angles with real data |
| Environmental flow layer | `environmental-flow-layer.tsx` | Connect to real grid data |
| Drift summary panel | `drift-summary-panel.tsx` | Make context-sensitive (oil/source/vessel/environment) |
| Live analysis page | `live-analysis/page.tsx` | Restructure to investigation workspace layout |
| Map config | `map-config.ts` | Add style switcher support |
| Zustand store | `use-app-store.ts` | Add timeline, style, projection state |
| Types | `types.ts` | Add CriticalityScore, EnvironmentalGrid types |

### 15.3 CREATE

| Component | Purpose |
|-----------|---------|
| `/investigate/[id]/page.tsx` | Investigation workspace route |
| `InvestigationPipeline.tsx` | Left-side pipeline sidebar (8 stages) |
| `CriticalityCard.tsx` | Right-side criticality score with breakdown |
| `ContextualPanel.tsx` | Context-sensitive right panel |
| `MasterTimeline.tsx` | Unified timeline controlling all layers |
| `MapStyleSwitcher.tsx` | Satellite/Ocean/Terrain/Dark basemap selector |
| `GlobeView.tsx` | Initial 3D globe with incident markers |
| `EnvironmentalGridService.ts` | Frontend service for grid data |
| `criticality_scorer.py` | Backend criticality computation |
| `environmental_grid.py` | Backend grid endpoint |

---

## 16. PHASED IMPLEMENTATION ROADMAP

### PHASE 0 — Architecture Preparation
**Duration:** 1-2 days
**Dependencies:** None
**Risk:** Low

**Files to modify:**
- `src/lib/store/use-app-store.ts` — Add timeline state, style state, projection state
- `src/lib/types.ts` — Add new type definitions

**Changes:**
1. Add to Zustand store:
   - `currentTime: Date`
   - `isPlaying: boolean`
   - `speed: number`
   - `timeWindow: { start: Date, end: Date }`
   - `mapStyle: 'dark' | 'satellite' | 'ocean' | 'terrain'`
   - `projectionMode: 'globe' | 'mercator'`
   - `selectedMapObject: { type, id } | null`
2. Add timeline actions: `setTime`, `play`, `pause`, `setSpeed`, `setTimeWindow`
3. Add new TypeScript types for criticality, environmental grid

**Acceptance criteria:**
- [ ] Zustand store compiles with new state
- [ ] New types are exported from `types.ts`
- [ ] No existing functionality broken
- [ ] Build passes (`npm run build`)

---

### PHASE 1 — Criticality Score
**Duration:** 2-3 days
**Dependencies:** Phase 0
**Risk:** Low

**Backend files to create:**
- `backend/app/services/criticality_scorer.py`
- `backend/app/schemas/criticality.py`

**Backend files to modify:**
- `backend/app/api/routes/drift.py` — Add criticality to investigation response
- `backend/app/schemas/drift.py` — Add criticality field

**Frontend files to create:**
- `src/components/drift-map/criticality-card.tsx`

**Frontend files to modify:**
- `src/components/drift-map/drift-summary-panel.tsx` — Integrate criticality card
- `src/lib/types.ts` — Add CriticalityScore type

**Changes:**
1. Create `CriticalityScorer` service computing 6-8 factors
2. Add coastline distance lookup (Shapely + Natural Earth)
3. Add `CriticalityResponse` Pydantic schema
4. Include criticality in investigation endpoint response
5. Build `CriticalityCard` UI with score display and breakdown bars
6. Integrate into drift summary panel

**Acceptance criteria:**
- [ ] `GET /investigation/{id}/run` returns criticality score
- [ ] Score is 0-100 integer
- [ ] Breakdown shows individual factor contributions
- [ ] CriticalityCard renders in drift summary panel
- [ ] Score updates when incident changes
- [ ] Unit tests for scorer with known inputs
- [ ] Backend tests pass (`pytest`)

---

### PHASE 2 — Real/NRT Environmental Providers
**Duration:** 3-4 days
**Dependencies:** Phase 0
**Risk:** Medium

**Backend files to create:**
- `backend/app/api/routes/environmental.py`

**Backend files to modify:**
- `backend/app/main.py` — Register environmental router

**Frontend files to create:**
- `src/lib/environmental-grid-service.ts`

**Frontend files to modify:**
- `src/components/drift-map/drift-map-view.tsx` — Replace hardcoded wind/current angles
- `src/components/drift-map/drift-status-card.tsx` — Add environmental data status
- `src/components/drift-map/environment-panel.tsx` — Show real data timestamps

**Changes:**
1. Create `/environmental/grid` endpoint returning vector field for visualization
2. Create `/environmental/point` endpoint for point queries
3. Create frontend service to fetch grid data
4. Replace `windAngleRad = (242 * Math.PI) / 180` with real grid vectors
5. Replace `currentAngleRad = (1.2 * Math.PI) / 180` with real grid vectors
6. Add DEMO/LIVE/NRT status badges to canvas layers
7. Add provider badge and data timestamp display

**Acceptance criteria:**
- [ ] `GET /environmental/grid?bbox=...&time=...` returns vector grid
- [ ] Frontend fetches grid data on incident selection
- [ ] Wind particles reflect real ERA5 wind direction/speed
- [ ] Current particles reflect real CMEMS current direction/speed
- [ ] DEMO badge visible when using mock provider
- [ ] NRT badge visible when using real provider
- [ ] Data timestamp displayed
- [ ] Graceful fallback to mock on network failure
- [ ] Backend tests pass (`pytest`)

---

### PHASE 3 — Globe → Incident Transition ✅ COMPLETE
**Duration:** Completed 2026-09-04
**Dependencies:** Phases 0, 1, 2
**Risk:** Low-Medium

**Frontend files created:**
- `src/components/map/globe-map-view.tsx` — Globe projection map with incident markers

**Frontend files modified:**
- `src/components/map/map-view.tsx` — Added `projectionMode`, `initialCenter`, `initialZoom` props for globe support
- `src/app/page.tsx` — Converted to globe entry point with incident sidebar
- `src/app/monitor/page.tsx` — Moved old monitor page to `/monitor`
- `src/app/drift-map/page.tsx` — Added `?incident=` query parameter support + Suspense boundary
- `src/components/layout/top-nav.tsx` — Updated navigation: GLOBE / MONITOR / INVESTIGATION

**Changes completed:**
1. ✅ Globe projection enabled via runtime `projection: "globe"` on MapLibre GL 4.7.1
2. ✅ Incident markers rendered as DOM markers with severity colors (red/amber/green)
3. ✅ Clicking incident triggers smooth fly-to animation (distance-based duration 1200-3000ms)
4. ✅ Camera arrives at incident location with zoom 8
5. ✅ "INVESTIGATE" button navigates to `/drift-map?incident=IN-XXX`
6. ✅ `/drift-map` reads `?incident=` query param and auto-selects that incident
7. ✅ Navigation restructured: Globe (home) → Monitor → Investigation
8. ✅ Incident sidebar on globe shows details + "Start Investigation" CTA
9. ✅ Globe legend showing severity color coding
10. ✅ Loading state with spinner during map initialization

**Acceptance criteria:**
- [x] Initial view shows 3D Earth globe
- [x] Incident markers visible on globe as colored dots
- [x] Clicking incident triggers smooth fly-to animation
- [x] Camera arrives at incident location at zoom 8+
- [x] Globe allows rotation (drag) in globe mode
- [x] Performance: smooth on target laptop
- [x] Build passes (`npm run build`)

---

### PHASE 4 — Investigation Workspace 🔄 IN PROGRESS
**Duration:** 3-4 days
**Dependencies:** Phases 0, 1, 3
**Risk:** Medium

**Frontend files to create:**
- `src/app/investigate/[id]/page.tsx`
- `src/components/investigation/investigation-pipeline.tsx`
- `src/components/investigation/contextual-panel.tsx`

**Frontend files to modify:**
- `src/components/live-analysis/investigation-map.tsx` — Replace SVG with MapLibre
- `src/components/drift-map/drift-summary-panel.tsx` — Make context-sensitive
- `src/components/layout/top-nav.tsx` — Add INVESTIGATE nav item

**Changes:**
1. Create `/investigate/[id]` route
2. Replace `investigation-map.tsx` SVG with real MapLibre map instance
3. Build `InvestigationPipeline` sidebar (8 stages with real SSE state)
4. Build `ContextualPanel` (oil/source/vessel/environment selection)
5. Restructure layout: 65-75% map, 15% left panel, 15% right panel
6. Add INVESTIGATE to top navigation

**Acceptance criteria:**
- [ ] `/investigate/{id}` loads with real MapLibre map
- [ ] Map fills 65-75% of workspace
- [ ] Pipeline sidebar shows 8 stages with correct state
- [ ] Right panel changes based on map selection
- [ ] Selecting oil shows area, confidence, age, criticality
- [ ] Selecting source shows coordinates, uncertainty, drift
- [ ] Selecting vessel shows vessel details, attribution score
- [ ] Selecting environment shows wind, current, provider
- [ ] Timeline controls all layers
- [ ] No SVG placeholder remains
- [ ] Build passes (`npm run build`)

---

### PHASE 5 — Coloured Map / Basemap
**Duration:** 1-2 days
**Dependencies:** Phase 0
**Risk:** Low

**Frontend files to create:**
- `src/components/map/map-style-switcher.tsx`

**Frontend files to modify:**
- `src/components/map/map-config.ts` — Add style definitions
- `src/lib/store/use-app-store.ts` — Add mapStyle state

**Changes:**
1. Add basemap style definitions (Dark, Satellite, Ocean, Terrain)
2. Create `MapStyleSwitcher` UI component
3. Store selected style in Zustand
4. Update `getMapStyleUrl()` to return selected style
5. Test all styles with existing data layers

**Acceptance criteria:**
- [ ] Style switcher UI visible on map
- [ ] Switching to Satellite shows ESRI imagery
- [ ] Switching to Ocean shows blue ocean styling
- [ ] Switching to Terrain shows topographic features
- [ ] All existing data layers persist across style changes
- [ ] Style selection persists in Zustand
- [ ] Build passes (`npm run build`)

---

### PHASE 6 — Environmental Particle Visualization
**Duration:** 2-3 days
**Dependencies:** Phase 2
**Risk:** Medium

**Frontend files to modify:**
- `src/components/drift-map/drift-map-view.tsx` — Connect real grid to canvas
- `src/components/drift-map/environmental-flow-layer.tsx` — Real vector field

**Changes:**
1. Connect real grid data to canvas particle rendering
2. Add per-layer animation speed control
3. Add per-layer play/pause
4. Add wind vector arrows (optional enhancement)
5. Add current vector arrows (optional enhancement)
6. Optimize canvas rendering for real data

**Acceptance criteria:**
- [ ] Wind particles reflect actual ERA5 wind field
- [ ] Current particles reflect actual CMEMS current field
- [ ] Each layer has independent play/pause
- [ ] Each layer has independent speed control
- [ ] Particles animate smoothly at 30fps
- [ ] No visual artifacts when switching between DEMO and REAL
- [ ] Build passes (`npm run build`)

---

### PHASE 7 — Master Timeline Synchronization
**Duration:** 2-3 days
**Dependencies:** Phases 0, 6
**Risk:** Medium

**Frontend files to modify:**
- `src/components/drift-map/drift-timeline.tsx` — Use Zustand time state
- `src/components/drift-map/drift-map-view.tsx` — Subscribe to currentTime
- `src/lib/store/use-app-store.ts` — Centralize time state

**Changes:**
1. Move timeline state from local React state to Zustand
2. Connect all layers to centralized `currentTime`
3. Environmental layers change with time
4. AIS vessel positions change with time
5. Oil slick position changes with time
6. Drift trajectory changes with time

**Acceptance criteria:**
- [ ] Single timeline controls all time-varying layers
- [ ] Scrubbing timeline updates wind, current, oil, AIS simultaneously
- [ ] Play/pause affects all layers
- [ ] Speed control affects all layers
- [ ] Time window selector works (72h/48h/24h)
- [ ] Event markers visible on timeline
- [ ] No desynchronization between layers
- [ ] Build passes (`npm run build`)

---

### PHASE 8 — Full Integration
**Duration:** 2-3 days
**Dependencies:** All previous phases
**Risk:** Medium

**Changes:**
1. Connect all phases into unified workflow
2. Test complete investigation workflow end-to-end
3. Verify all layers synchronize
4. Verify globe → investigation flow
5. Verify criticality in all contexts
6. Verify environmental data displays correctly
7. Verify timeline controls everything

**Acceptance criteria:**
- [ ] Globe → incident → investigation flow works end-to-end
- [ ] All map layers render correctly
- [ ] Timeline synchronizes all layers
- [ ] Criticality score displays for every incident
- [ ] Environmental data shows real/provider info
- [ ] No console errors
- [ ] All tests pass
- [ ] Build passes

---

### PHASE 9 — SIH Polish
**Duration:** 2-3 days
**Dependencies:** Phase 8
**Risk:** Low

**Changes:**
1. Performance optimization
2. Error handling for all network failures
3. Loading states for all async operations
4. DEMO mode badges on all synthetic data
5. Scientific terminology review (Section 12)
6. Accessibility improvements
7. Final visual polish

**Acceptance criteria:**
- [ ] No DEMO data presented as real
- [ ] All scientific terminology correct
- [ ] All error states handled gracefully
- [ ] All loading states present
- [ ] Performance meets Section 14 constraints
- [ ] Visual review passes

---

## 17. SIH MINIMUM VIABLE VERSION

### MUST HAVE (Before SIH Demo)

1. Investigation workspace with real MapLibre map (replacing SVG)
2. Criticality score card with breakdown
3. Satellite basemap option
4. Wind/current particles clearly labeled DEMO or real
5. Globe → incident zoom experience
6. All layers synchronized to timeline
7. DEMO/LIVE/NRT status badges on all data layers
8. Contextual right panel (oil/source/vessel selection)
9. Pipeline sidebar with real state
10. PDF report generation

### SHOULD HAVE (If Time Permits)

1. Ocean basemap style
2. Terrain basemap style
3. Per-layer play/pause
4. Animation speed control per layer
5. Wind/current vector arrows
6. Environmental data timestamps
7. Data age indicators
8. Provider provenance display

### NICE TO HAVE (Do Not Block SIH)

1. Animated wind particles from real ERA5 grid
2. Animated current particles from real CMEMS grid
3. Projected drift trajectory (forward)
4. Satellite coverage overlay
5. Eco-sensitive area overlay
6. Shipping lane overlay

### DO NOT BUILD BEFORE SIH

1. Real ML model integration (keep mock adapter)
2. PostGIS database (keep in-memory)
3. S3 storage (keep local)
4. Multi-user authentication
5. Real-time WebSocket updates
6. Mobile-responsive design
7. Offline mode
8. Historical data archive
9. Custom WebGL shader layers
10. Multi-language support

---

## 18. EXPLICIT "DO NOT CHANGE" DECISIONS

These architectural decisions are locked. Do not change them without explicit approval:

1. **Backend provider abstraction pattern** — All providers (environmental, AIS, drift, satellite, inference, reports) use ABC interface + concrete implementations. Do not merge or simplify.

2. **SSE event system** — In-process EventHub with cursor-based subscription. Do not replace with WebSockets.

3. **Frontend API abstraction layer** — `client.ts` mock/real switch via `NEXT_PUBLIC_API_MODE`. Do not remove mock mode.

4. **Pydantic camelCase schema pattern** — All response schemas use `alias_generator=to_camel`. Do not change to snake_case.

5. **React Query data fetching** — All API calls go through React Query. Do not replace with raw fetch orSWR.

6. **Zustand for global state** — All shared UI state lives in Zustand. Do not move to React context or Redux.

7. **Canvas-based particle rendering** — Wind, current, and oil particles use requestAnimationFrame canvas. Do not replace with WebGL unless performance demands it.

8. **MapLibre GL v4.7.1** — Do not upgrade to v5.x or switch to Mapbox GL JS.

9. **Next.js 14.2 App Router** — Do not downgrade to Pages Router or upgrade to Next.js 15 without testing.

10. **Mock data must always be available** — The system must always work in DEMO mode without network access.

11. **Scientific honesty** — Never present mock data as real. Never claim attribution proves responsibility. Never claim source location is exact.

12. **No GPU infrastructure** — All rendering must work on CPU-only laptops with integrated GPU.

---

## 19. KNOWN RISKS

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| MapLibre globe performance on low-end laptops | MEDIUM | MEDIUM | Add fallback to 2D flat; test on SIH demo hardware |
| CMEMS/ERA5 data unavailable during demo | HIGH | LOW | Pre-cache data; clear DEMO fallback with status badge |
| `.env` credentials leaked via git history | HIGH | UNKNOWN | Rotate all credentials; audit git history |
| Canvas particle layers misinterpreted as real data | HIGH | HIGH | Add LIVE/DEMO/UNAVAILABLE badges to all layers |
| Master timeline desynchronization | MEDIUM | MEDIUM | Centralize time state in Zustand; test all layers |
| Coastal distance computation accuracy | LOW | LOW | Use GSHHG 1:10 resolution; validate against known points |
| Investigation SVG placeholder confuses users | MEDIUM | HIGH | Replace with real MapLibre map before SIH |
| Wind/current particles hardcoded as real | HIGH | HIGH | Replace with real grid data; add DEMO label |
| Globe projection rotation limits | LOW | LOW | Implement polar bounds; test interaction |
| Environmental grid endpoint latency | MEDIUM | LOW | Cache grid data; serve pre-computed vectors |

---

## 20. IMPLEMENTATION STATUS

| Phase | Name | Status | Completion Date |
|-------|------|--------|----------------|
| Phase 0 | Architecture Preparation | ✅ COMPLETE | September 2026 |
| Phase 1 | Operational Criticality Score | ✅ COMPLETE | September 2026 |
| Phase 1.1 | Criticality Hardening / Regression Cleanup | ✅ COMPLETE | September 2026 |
| Phase 2 | Real/NRT Environmental Intelligence | ✅ COMPLETE | September 2026 |
| Phase 3 | Globe → Incident Zoom | ✅ COMPLETE | 2026-09-04 |
| Phase 4 | Investigation Workspace | ✅ COMPLETE | 2026-09-04 |
| Phase 5 | Coloured Map / Basemap | ✅ COMPLETE | 2026-09-04 |
| Phase 6 | Map Interaction & Controls | ⏳ PENDING | — |
| Phase 7 | AIS Integration & Source Attribution | ⏳ PENDING | — |
| Phase 8 | SAR Preprocessing & Ingestion | ⏳ PENDING | — |

### Test Results Summary

- Backend: 399+ tests passing, with the known external Groq 429 rate-limit test remaining separate from feature correctness.
- Environmental grid: 21 tests passing.
- Criticality: 60 tests passing.
- Frontend: TypeScript/typecheck and production build pass cleanly.
- Phase 3 globe/incident implementation: build passes and 81 relevant backend tests pass.
- Phase 4 investigation workspace: build passes and 81 backend tests pass.
- Phase 5 basemap style switcher: build passes and 81 backend tests pass.
- UI Foundation Repair: build passes and 81 backend tests pass. Fixed globe projection restoration, colourful basemaps (ESRI Ocean/Terrain), compact navbar.
- Real-Data Architecture: build passes and 81 backend tests pass. MapLibre 5.24.0 native globe, AISStream WebSocket, real AIS/SAR/environmental data.

---

## 20. REAL DATA ARCHITECTURE

### Data Sources

| Layer | Provider | Protocol | Real-Time? | Credentials |
|-------|----------|----------|------------|-------------|
| **AIS Vessels** | AISStream.io | WebSocket (server-side proxy) | Real-time streaming | `AISSTREAM_API_KEY` |
| **AIS Vessels** (attribution) | Global Fishing Watch 4Wings API | REST | Batch query | `GFW_API_TOKEN` |
| **SAR Scenes** | Copernicus Data Space (CDSE) | STAC 1.1.0 + OData | Near-real-time acquisition | `CDSE_USERNAME`, `CDSE_PASSWORD` |
| **Ocean Currents** | CMEMS GLOBCurrents | copernicusmarine SDK | NRT (delayed ~12h) | `CMEMS_USERNAME`, `CMEMS_PASSWORD` |
| **Wind** | ECMWF ERA5 | CDS API | Reanalysis/forecast | `CDS_API_KEY` |
| **Oil Detection** | TinyUNet (PyTorch) | Local inference | On-demand processing | `MODEL_PATH` |
| **Reports** | Groq LLM | REST API | On-demand generation | `GROQ_API_KEY` |

### AISStream Integration

Architecture:
```
AISStream WebSocket (wss://stream.aisstream.io)
    ↓ (server-side background thread)
In-memory vessel position cache (max 10,000 vessels)
    ↓
REST: GET /api/v1/ais/vessels (GeoJSON snapshot)
SSE:  GET /api/v1/ais/stream (real-time updates)
    ↓
Frontend: useAISStream() hook → MapLibre GeoJSON layer
```

- API key never exposed to frontend (`NEXT_PUBLIC_*` forbidden)
- Geographic bbox subscription: Indian Ocean (55°E-100°E, 5°S-25°N)
- Auto-reconnect with exponential backoff (2s → 30s max)
- Vessel positions rendered as MapLibre circle layers (efficient, no React components)
- Color-coded by vessel type: red (tanker), amber (cargo), green (fishing), purple (passenger)

### Data Freshness Semantics

| Data | Labels | Meaning |
|------|--------|---------|
| AIS | `LIVE` | WebSocket connected, message < 30s ago |
| AIS | `RECENT` | Message < 5min ago |
| AIS | `STALE` | Message > 5min ago |
| AIS | `UNAVAILABLE` | No API key or connection failed |
| SAR | `NRT` | Scenes available from Copernicus |
| SAR | `UNAVAILABLE` | No scenes or CDSE auth failed |
| Current | `NRT` | CMEMS data available |
| Wind | `FORECAST` / `REANALYSIS` | ERA5 data available |

### Failure Semantics (ABSOLUTE RULE)

Real data failure ≠ mock data. If a provider is unavailable:
- AIS: Shows "AIS UNAVAILABLE" in HUD
- SAR: Shows "NO RECENT SAR ACQUISITION"
- Current: Shows "CURRENT DATA UNAVAILABLE"
- Wind: Shows "WIND DATA UNAVAILABLE"

No fallback to synthetic/demo data on the global intelligence page.

### Environment Variables

```bash
# AISStream (server-side only, NEVER NEXT_PUBLIC_*)
AISSTREAM_API_KEY=your_aisstream_api_key

# Copernicus Sentinel-1
CDSE_USERNAME=your_email
CDSE_PASSWORD=your_password

# CMEMS Ocean Currents
CMEMS_USERNAME=your_email
CMEMS_PASSWORD=your_password

# ECMWF ERA5 Wind
CDS_API_KEY=your_cds_api_key

# Groq Reports
GROQ_API_KEY=your_groq_key
```

## 21. ACCEPTANCE CRITERIA SUMMARY

Every phase must pass ALL of these before proceeding:

### Build Quality
- [ ] `npm run build` passes (no TypeScript errors)
- [ ] `npm run lint` passes (no lint errors)
- [ ] `pytest` passes (all backend tests pass)
- [ ] No console errors in browser

### Data Integrity
- [ ] No mock data presented as real
- [ ] All DEMO data labeled with DEMO badge
- [ ] All scientific terminology follows Section 12
- [ ] No fabricated environmental values

### Performance
- [ ] Map renders at 30fps minimum
- [ ] Particle animation smooth at 30fps
- [ ] Timeline scrub responds in <50ms
- [ ] API responses within Section 14 latency budget

### Architecture
- [ ] No changes to locked decisions (Section 18)
- [ ] Provider abstraction pattern preserved
- [ ] Mock mode still functional
- [ ] SSE event system unchanged

### Visual Quality
- [ ] No SVG placeholders in production paths
- [ ] All status badges visible and accurate
- [ ] Layout matches Section 4.3 specification
- [ ] Colors follow existing design tokens

---

> **Document version:** 1.0
> **Generated from:** Comprehensive architecture audit of SAGAR WATCH repository
> **Verification method:** Every field verified against actual source code — nothing assumed
> **Last verified:** September 2026
