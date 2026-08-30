# SAGAR WATCH — Backend (Phase 1B)

FastAPI service implementing the oil-spill detection pipeline:

```
Sentinel-1-like scene
      ↓  ingestion (SatelliteSceneProvider)
SAR preprocessing            app/inference/<adapter>.preprocess
Oil-spill ML model           app/inference/<adapter>.predict   ← MODEL ADAPTER INTERFACE
Probability mask             float32 [0..1]
Post-processing              threshold → morphology → polygons → georeferencing
Spill polygon + metrics      geodesic area/perimeter (pyproj.Geod), confidence
Repository                   PostgreSQL+PostGIS (prod) | in-memory (dev)
FastAPI REST + SSE           /api/v1/*
SAGAR WATCH frontend
```

> **Status: development prototype.** The only model adapter shipped is a
> clearly-labeled MOCK heuristic (`MockOilSpillModel`). Its outputs are NOT
> trained-model predictions and must never be presented as real detections.
> See `docs/ml-integration-contract.md` for plugging in the real model.

---

## 1. Prerequisites

* Python 3.11–3.12
* PostgreSQL 14+ with the PostGIS extension (production path) — or nothing at
  all for local dev (in-memory repository fallback)

### Starting PostgreSQL + PostGIS

The repo ships `docker-compose.yml` at the project root:

```bash
docker compose up -d postgis     # postgres:16 + postgis on localhost:5432
```

Or use any existing instance; just point `DATABASE_URL` at it.

## 2. Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt        # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # Linux/macOS

copy .env.example .env                               # then edit as needed
```

## 3. Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | *(empty)* | `postgresql+psycopg2://user:pass@host:5432/sagarwatch`. Empty ⇒ in-memory dev repository |
| `SEED_DEMO_DATA` | `true` | Auto-seed demo incidents/scenes when store is empty |
| `MODEL_ADAPTER` | `mock` | `mock` (dev heuristic) or `torch` (real model, arrives later) |
| `MODEL_PATH` | `/models/oil_spill/model.pth` | Weights file for the real adapter |
| `MODEL_NAME` | `OilSpillNet` | Model identity stored with each incident |
| `MODEL_VERSION` | `1.0-dev` | Version string stored with each incident |
| `MODEL_DEVICE` | `cpu` | Inference device (`cpu`, `cuda`, …) |
| `MODEL_THRESHOLD` | `0.5` | Probability-mask binarization threshold |
| `MIN_POLY_AREA_KM2` | `0.05` | Detections below this area are discarded |
| `POLYGON_SIMPLIFY_TOLERANCE_M` | `25` | Polygon simplification tolerance (metres) |
| `SCENE_STORAGE_DIR` | `./data/scenes` | Where demo/synthetic rasters are written |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed browser origins |

Nothing model-related is hardcoded.

## 4. Database migration

With PostGIS running:

```bash
psql "postgresql://sagar:sagar@localhost:5432/sagarwatch" \
     -f app/db/migrations/001_init_postgis.sql
```

Creates `satellite_scenes`, `spill_incidents`, `model_runs` with PostGIS
geometry columns (`POLYGON`/`POINT`, SRID 4326) and GiST spatial indexes.

Without a database server the API runs against the **in-memory development
repository** (data resets on restart). This exists so the full pipeline can be
developed and tested locally — it is not a production option.

## 5. Run

```bash
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

* Interactive docs: <http://localhost:8000/docs>
* Health: <http://localhost:8000/api/v1/health>

Demo data seeds automatically (`SEED_DEMO_DATA=true`). To seed manually:

```bash
.venv\Scripts\python -c "from app.config import get_settings; from app.db.session import create_repository; from app.db.seed import seed_demo_data; seed_demo_data(create_repository(get_settings()), force=True)"
```

## 6. Model adapter interface

```python
class OilSpillModel(abc.ABC):
    name: str
    version: str
    def load_model(self) -> None: ...
    def preprocess(self, scene_input: SceneInput) -> PreprocessResult: ...
    def predict(self, data: PreprocessResult) -> PredictionResult: ...
```

* `PredictionResult.probability_mask` — float32 array in `[0,1]`, aligned to
  the original raster grid.
* Post-processing (threshold, morphology, connected components, contours,
  georeferencing, geodesic metrics, confidence) is shared code in
  `app/geospatial/` + `app/services/inference_service.py`, so every adapter
  gets identical treatment.

The active adapter is selected by `MODEL_ADAPTER` in
`app/inference/model_loader.py::create_model`.

### Plugging in the real trained model later

1. Implement `app/inference/torch_adapter.py::TorchOilSpillModel(OilSpillModel)`
   following the checklist in `docs/ml-integration-contract.md`.
2. Register it:

   ```python
   if adapter == "torch":
       from app.inference.torch_adapter import TorchOilSpillModel
       return TorchOilSpillModel(settings)
   ```
3. Set env vars (`MODEL_ADAPTER=torch`, `MODEL_PATH=…`, `MODEL_DEVICE=…`,
   `MODEL_THRESHOLD=…`) — no other code changes.

## 7. API endpoints

Base URL: `/api/v1`

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/system/status` | Services, active scene, DB backend, model adapter |
| POST | `/system/run-demo-pipeline` | **DEV ONLY**: synthetic raster → mock model → incidents (+ SSE events) |
| GET | `/spills` | Filters: `min_confidence`, `start`, `end`, `bbox=w,s,e,n` |
| GET | `/spills/{id}` | Incident detail (camelCase, frontend-compatible) |
| GET | `/spills/{id}/geometry` | GeoJSON Feature of the slick polygon |
| GET | `/satellite/scenes` | List scenes (`bbox` filter) |
| GET | `/satellite/scenes/{id}` | Scene detail |
| GET | `/analytics/summary` | Totals/daily/hourly/by-region/confidence buckets |
| GET | `/analytics/detections` | Flat detection records |
| GET | `/events/stream` | SSE; emits `detection.created` per new incident |

### Example requests

```bash
curl "http://localhost:8000/api/v1/spills?min_confidence=0.8"
curl "http://localhost:8000/api/v1/spills/IN-250825-001"
curl -X POST "http://localhost:8000/api/v1/system/run-demo-pipeline"
curl -N "http://localhost:8000/api/v1/events/stream"
```

### Example response (`GET /api/v1/spills/IN-250825-001`, truncated)

```json
{
  "id": "IN-250825-001",
  "sceneId": "S1A_IW_GRDH_20260825T1820",
  "confidence": 0.914,
  "areaKm2": 18.4,
  "perimeterKm2": 21.6,
  "centroid": { "lat": 15.2965, "lon": 72.8456 },
  "geometry": { "type": "Polygon", "coordinates": [[[72.8456, 15.2965], ...]] },
  "detectedAt": "2026-08-25T18:31:00+05:30",
  "region": "Arabian Sea",
  "locationDescription": "Arabian Sea · Off Maharashtra Coast",
  "satellite": "Sentinel-1A",
  "model": "OilSpillNet",
  "modelVersion": "v1.0",
  "status": "completed",
  "level": "HIGH",
  "isDemo": true
}
```

Response schemas intentionally mirror the frontend's TypeScript types
(`src/lib/types.ts`). The only naming quirk kept for compatibility is
`perimeterKm2` (frontend field name).

## 8. Tests

```bash
.venv\Scripts\python -m pytest tests -q
```

Covers: polygon extraction, CRS/georeferencing, geodesic area, morphological
cleanup, confidence calculation, mock adapter contract, API schemas/filters,
seed integrity, incident creation, and the full demo pipeline including SSE
event publication.

## 9. Honest-data policy

* Seed/demo records carry `is_demo=true` and are labelled development data.
* The mock adapter logs a warning on load and stamps its predictions with
  `adapter_kind: MOCK_DEVELOPMENT_HEURISTIC`.
* MODEL CONFIDENCE (mean predicted probability inside a detected polygon) is
  distinct from MODEL VALIDATION METRICS (IoU/F1 etc.) — the latter come only
  from the ML team's evaluation, never from this service.
