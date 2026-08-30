# Satellite Data Ingestion — Copernicus Data Space Ecosystem

Phase 2 of SAGAR WATCH connects the backend to the **official Copernicus
Data Space Ecosystem (CDSE)** so real Sentinel-1 GRD scenes over Indian
maritime waters can be discovered, acquired, stored, preprocessed and served.

```
Copernicus Data Space Ecosystem
        ↓  STAC catalogue (search, anonymous)
Sentinel-1 discovery ──→ scene metadata (real product UUID, orbit, footprint)
        ↓  OData download (Bearer token, streamed in chunks)
Local / S3 storage          products/<scene>.zip
        ↓  configurable stage pipeline
SAR preprocessing           preprocessed/<scene>.tif
        ↓  existing OilSpillModel adapter (mock heuristic until trained model)
Inference                   → incidents via Phase-1B geospatial pipeline
        ↓
PostGIS / in-memory repository → FastAPI → SSE → SAGAR WATCH frontend
```

> **Honesty rules.** Mock-provider output is always marked `isDemo=true` and
> `sourceProvider="mock"`. Real CDSE scenes carry their actual product UUID,
> acquisition time and footprint (`isDemo=false`). The inference adapter is a
> clearly-labeled development heuristic — its outputs are NOT trained-model
> predictions and are never presented as such.

---

## 1. Copernicus account setup

1. Register (free) at <https://dataspace.copernicus.eu/>.
2. Search and download require an authenticated account; catalogue search
   (STAC) is anonymous.
3. If your account uses Two-Factor Authentication, see the official token
   documentation — password-grant tokens then additionally require a TOTP.

## 2. APIs used

| Purpose | API | Endpoint | Auth |
|---|---|---|---|
| Scene discovery | CDSE STAC (v1.1.0) | `https://stac.dataspace.copernicus.eu/v1/search` | none |
| Single-item metadata | CDSE STAC | `.../v1/collections/sentinel-1-grd/items/{id}` | none |
| Access token | CDSE Keycloak | `https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token` | username/password (or refresh token) |
| Product download | CDSE OData | `https://download.dataspace.copernicus.eu/odata/v1/Products({uuid})/$value` | Bearer token |

All endpoints are configurable via environment variables (see §4) so they can
be updated without code changes if Copernicus migrates them.

## 3. Authentication

Implemented in `app/satellite/auth.py`:

* Password grant against the Keycloak realm with `client_id=cdse-public`.
* The refresh token is reused whenever possible; the raw password is sent as
  rarely as possible.
* Tokens are cached in memory and refreshed transparently ~60 s before expiry.
* Credentials live ONLY in environment variables — never in code or git.

## 4. Environment variables

Copy `.env.example` to `.env` and fill in:

| Variable | Default | Meaning |
|---|---|---|
| `SATELLITE_PROVIDER` | `mock` | `mock` (synthetic demo) or `copernicus` (real CDSE) |
| `CDSE_USERNAME` / `CDSE_PASSWORD` | — | your CDSE account (downloads only) |
| `CDSE_TOKEN_URL`, `CDSE_STAC_SEARCH_URL`, `CDSE_STAC_ITEM_URL` | official endpoints | override on migration |
| `CATALOGUE_QUERY_LIMIT` | `20` | hard cap on discovery result size |
| `INDIA_AOI_BBOX` | `68.0,6.0,94.5,24.5` | development AOI bounding box |
| `INDIA_AOI_GEOJSON_PATH` | — | official EEZ GeoJSON (Polygon/MultiPolygon, EPSG:4326) |
| `DOWNLOAD_CHUNK_MB` | `1` | streaming chunk size |
| `DOWNLOAD_MAX_RETRIES` / `DOWNLOAD_RETRY_BACKOFF_SECONDS` | `3` / `5` | retry policy |
| `STORAGE_BACKEND` | `local` | `local` or `s3` (+ `S3_*` variables) |
| `PREPROCESSING_STAGES` | *(defaults)* | JSON list of stages, see §9 |

## 5. India AOI

`app/satellite/aoi.py` defines the Area-of-Interest contract:

* Development default: documented bbox `(68.0°E…94.5°E, 6.0°N…24.5°N)`
  covering the Arabian Sea, Bay of Bengal and Andaman approaches.
* Production: set `INDIA_AOI_GEOJSON_PATH` to an official Indian EEZ /
  coastline GeoJSON. Provider searches then use true polygon intersection;
  the bbox remains as a coarse catalogue pre-filter.
* The API also accepts ad-hoc `bbox=` parameters per request.

## 6. Scene search

### REST API

```
GET /api/v1/satellite/scenes?source=catalogue&region=india&limit=10
GET /api/v1/satellite/scenes?source=catalogue&bbox=72,17,74,20&start=2026-08-01T00:00:00Z&end=2026-08-26T00:00:00Z&platform=sentinel-1c&product_type=IW_GRDH_1S
```

Parameters: `start`, `end` (ISO-8601), `bbox` (`west,south,east,north`),
`region` (named AOI, e.g. `india`), `platform`, `product_type`, `limit`,
and `source`:

* `source=stored` (default) — scenes already ingested into the repository.
* `source=catalogue` — LIVE provider search; results are NOT persisted.

Check the active source any time:

```
GET /api/v1/satellite/scenes/provider
→ {"name": "copernicus", "isReal": true, ...}
```

### Persisting a discovered scene

```
POST /api/v1/satellite/scenes/import
{"scene_id": "S1C_IW_GRDH_1SDV_...__COG"}
```

Stores full metadata (product UUID, name, orbit, footprint geometry,
polarization, advertised size, download reference) with status `DISCOVERED`
and publishes the `scene.discovered` SSE event. Import is idempotent.

### CLI

```powershell
$env:SATELLITE_PROVIDER = "copernicus"
python scripts/copernicus_demo.py --list --limit 5      # search only
python scripts/copernicus_demo.py --index 0 --yes       # download exactly scene #0
```

The demo prints discovered metadata, downloads ONE confirmed scene, generates
a preview, persists it, and tells you how to process it through the API.
It cannot mass-download: results are capped by `--limit`.

## 7. Download

`app/satellite/providers/copernicus.py` streams products to the configured
storage backend in chunks (default 1 MB) — the archive is never buffered in
RAM. Every attempt verifies HTTP status; failures retry with linear backoff
(token is invalidated between attempts). Progress callbacks feed job events.

Downloads NEVER happen inside normal API requests — they run inside
background pipeline jobs (§8).

## 8. Storage

Interface concepts (`app/satellite/storage.py`): `save()`, `save_stream()`,
`get()`, `exists()`, `delete()`, `get_url()`. Keys are logical paths:

```
products/<scene_id>.zip        # acquired GRD product (raw)
preprocessed/<scene_id>.tif    # model-ready calibrated dB raster + provenance tags
previews/<scene_id>.png        # web preview
```

Backends: `LocalStorageBackend` (development root = `SCENE_STORAGE_DIR`) and
`S3StorageBackend` (any S3-compatible store via boto3). Application code never
touches filesystem paths directly.

## 9. SAR preprocessing framework

`app/satellite/preprocessing.py` provides an ordered, independently
configurable stage chain — the final MODEL-specific preprocessing stays
configurable until the trained-model contract arrives. Configure via JSON:

```json
PREPROCESSING_STAGES=[{"name":"subset_bbox"},{"name":"to_db"},{"name":"normalize_percentile"}]
```

Available stages: `subset_bbox` (AOI window read), `extract_polarization`
(VV/VH selection), `calibration` (passthrough for already-calibrated COG
sigma0; LUT-based DN calibration raises rather than silently guessing),
`to_db` (10·log10), `normalize_percentile`, `nodata_mask`, `resample`,
`ocean_mask` (no-op until a land polygon source is supplied), `tiling`
(metadata descriptor). Each run records a provenance report into the output
GeoTIFF tags.

Default chain: `subset_bbox → to_db → normalize_percentile`.

## 10. Processing states & jobs

```
DISCOVERED → QUEUED → DOWNLOADING → DOWNLOADED → PREPROCESSING →
READY_FOR_INFERENCE → INFERENCE → POSTPROCESSING → COMPLETED
(any step → FAILED, with error recorded)
```

Trigger processing (non-blocking, HTTP 202):

```
POST /api/v1/satellite/scenes/{scene_id}/process   → {"jobId", "state"}
GET  /api/v1/pipeline/jobs/{job_id}                → state + transition history
GET  /api/v1/pipeline/jobs?scene_id=...
```

Jobs run on worker threads; every transition updates the scene record and is
published over SSE:

`scene.discovered`, `scene.download.started`, `scene.download.completed`,
`scene.preprocessing.started`, `scene.preprocessing.completed`,
`scene.inference.started`, `scene.inference.completed`,
`detection.created` (existing), `pipeline.failed`.

Subscribe: `GET /api/v1/events/stream?cursor=<last-id>`.

## 11. Scene preview

```
GET /api/v1/satellite/scenes/{scene_id}/preview   → image/png
```

A lightweight PNG (percentile-stretched, downscaled ≤1024 px) generated from
the processed raster during POSTPROCESSING — the raw product is never served.
404 before processing.

## 12. Running things

```powershell
# backend (real catalogue, mock inference adapter)
$env:SATELLITE_PROVIDER = "copernicus"
uvicorn app.main:app --reload --port 8000

# search (no credentials needed)
curl "http://localhost:8000/api/v1/satellite/scenes?source=catalogue&region=india&limit=5"

# import + process one scene
curl -X POST http://localhost:8000/api/v1/satellite/scenes/import \
     -H "Content-Type: application/json" \
     -d '{"scene_id": "S1C_IW_GRDH_1SDV_...._COG"}'
curl -X POST http://localhost:8000/api/v1/satellite/scenes/<SCENE_ID>/process

# watch progress
curl -N http://localhost:8000/api/v1/events/stream
```

Tests (offline by default):

```powershell
python -m pytest tests -q                                  # 75 tests, no network
SAGAR_LIVE_CDSE=1 python -m pytest tests/test_live_copernicus.py -v   # opt-in live checks
```

## 13. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `provider.isReal == false` unexpectedly | `SATELLITE_PROVIDER` not set to `copernicus` |
| Job FAILED: *"Copernicus download requires credentials"* | set `CDSE_USERNAME`/`CDSE_PASSWORD`; STAC search still works without them |
| Job FAILED: HTTP 401 during download | expired/bad credentials or 2FA TOTP required — re-check account |
| `Preview not available yet` | preview is generated in POSTPROCESSING; wait for job COMPLETED |
| Search returns nothing | widen `--days`/time window; verify bbox within WGS84 lon/lat range |
| Very large downloads | GRDH products are typically 0.7–1.5 GB; ensure disk space; consider `STORAGE_BACKEND=s3` |
| In-memory repo lost data after restart | expected in dev; configure `DATABASE_URL` (PostGIS) for persistence |

## 14. Security notes

* No credential is ever hardcoded; everything flows from environment.
* Tokens are kept in memory only, never logged; auth errors never echo secrets.
* `.env` is git-ignored — commit only `.env.example`.
* Storage keys reject path traversal (`..`).

---

## 15. Verified real acquisition record (Phase 2B, 2026-08-26)

A complete discovery → acquisition → inspection cycle was executed against the
live CDSE catalogue. **This is a routine ocean-monitoring SAR scene covering
part of the India maritime AOI — it is NOT an oil-spill scene and no oil
detection has been claimed or performed on it.**

| Field | Actual value |
|---|---|
| Product ID (CDSE UUID) | `e7555c00-b668-4198-b97b-d4da245051b8` |
| Scene / product name | `S1C_IW_GRDH_1SDV_20260826T005736_20260826T005758_009159_012318_7B48_COG.SAFE` |
| Satellite | Sentinel-1C |
| Acquisition | 2026-08-26T00:57:36Z → 00:57:58Z (descending pass, abs orbit 9159, rel orbit 136) |
| Product type | IW_GRDH_1S (IW Level-1 GRD), slice 2/2 |
| Polarizations | VV and VH (both present as separate measurement COG TIFFs) |
| Coverage | W70.742 S5.254 E73.247 N7.076 — Lakshadweep Sea / off Kerala coast |
| Advertised size | 742,265,223 bytes (~742 MB) |
| Downloaded size | 742,265,223 bytes — exact match |
| Integrity | MD5 `b0a0adfe310fad69dddf661e784bb53c` matches official CDSE checksum; zip CRC test clean |
| Download time | ~79 s at ~9.4 MB/s, streamed in 1 MB chunks |
| Local storage | `data/scenes/products/S1C_IW_GRDH_1SDV_20260826T005736_..._7B48_COG.zip` |
| Inspection report | `data/scenes/products/scene_inspection.json` |

### Actual product structure (inspected, not assumed)

```
S1C_IW_GRDH_1SDV_..._7B48_COG.SAFE/
├── manifest.safe
├── annotation/
│   ├── s1c-iw-grd-vv-...-cog.xml          (image annotation)
│   ├── s1c-iw-grd-vh-...-cog.xml
│   ├── calibration/calibration-s1c-iw-grd-{vv,vh}-...xml   ← DN calibration LUTs
│   ├── calibration/noise-s1c-iw-grd-{vv,vh}-...xml
│   └── rfi/rfi-s1c-iw-grd-{vv,vh}-...xml
├── measurement/
│   ├── s1c-iw-grd-vv-20260826t005736-...-001-cog.tiff     ← VV band
│   └── s1c-iw-grd-vh-20260826t005736-...-002-cog.tiff     ← VH band
├── preview/
└── support/
```

### Raster facts (both polarizations)

* Dimensions: **25150 × 15175 px**, uint16 detected DN
* Pixel spacing: **10 m × 10 m** (range × azimuth, from annotation XML)
* Incidence angle (mid-swath): **~39.0°**
* Nodata: **0** (uint16 zero = no-data flag)
* Format: GeoTIFF with COG-style overviews (2…64)
* **No embedded CRS/affine** — geolocation is GCP-based: 189 ground control
  points in EPSG:4326 spanning exactly the advertised footprint. Any
  bbox-subset preprocessing must warp via these GCPs first.
* Pixel values are raw-ish DN; radiometric calibration to σ0 requires the
  shipped per-polarization DN calibration LUTs
  (`absoluteCalibrationConstant = 0.8995` for VV) plus noise LUTs.

### Verification performed through the running API

* `GET /api/v1/satellite/scenes` lists the ingested real scene (`isDemo=false`)
* `GET /api/v1/satellite/scenes/{id}` returns full metadata incl.
  product UUID, orbit, footprint, `pipelineState`
* SSE stream emitted `scene.discovered` → `scene.download.started` →
  `scene.download.completed` in order

---

## 16. Real SAR preprocessing record (Phase 2C, 2026-08-26)

The Phase 2B product was processed end-to-end by the GRD calibration chain
(`app/satellite/grd_preprocess.py`, CLI: `scripts/run_grd_preprocess.py`).

### Scientific basis (verified against official sources — nothing guessed)

| Step | Formula | Source |
|---|---|---|
| Radiometric calibration | `sigma0 = DN² / A_sigma²`, A_sigma **bilinearly interpolated** between the product's 25×630-anchor calibration vectors | ESA SNAP CalibrationOp doc; Copernicus eopf S1 L12 ATBD eq. 6.3–6.4 |
| Thermal noise (implemented, **OFF** by default) | `sigma0_denoised = (DN² − eta_rg·eta_az) / A_sigma²` | ESA noise-LUT convention (Ifremer processor note); disabled until the ML contract defines the final input representation |
| Georeferencing | least-squares polynomial (order 3, **normalized coords**) fitted over the product's GCPs; output grid from advertised footprint; inverse-mapped bi-linear sampling | standard GDAL GCP-warp model class |

Key lesson encoded in the code: raw pixel indices make an unnormalized cubic
GCP fit numerically explosive (x³ ~ 1.6e13) — all fits use [-1,1]-normalized
coordinates.

### Outputs (`data/scenes/processed/<scene_id>/`)

| File | Content |
|---|---|
| `calibrated/{vv,vh}_sigma0_linear.tif` | σ0 linear power on the native GRD grid, GCP-tagged, NaN nodata |
| `georeferenced/{vv,vh}_sigma0_epsg4326.tif` | warped to EPSG:4326 @ ~10 m equivalent (27718×20147), VV/VH grids identical |
| `model_input/{vv,vh}_sigma0_db.tif` | 10·log10(σ0), same grid — *candidate* representation; final model input TBD |
| `preview/*.png` | VV dB, VH dB, VV/VH composite + GCP diagnostic — labelled "SAR backscatter preview"; dark regions are NOT oil |
| `metadata/preprocessing_report.json` | full provenance (LUT files, formulas, stats, QC result) |

### Verified results

* Calibration sanity: VV mean −19.9 dB, VH −28.9 dB (~9 dB pol difference) —
  textbook C-band ocean backscatter.
* Valid pixels: 95.1% on the GRD grid (DN=0 → NaN nodata preserved);
  66.0% on the georeferenced grid (corners outside GCP hull are honestly NaN).
* Runtime ≈ 22 min for both polarizations on a laptop-class machine,
  fully blockwise (peak RAM bounded by per-block buffers, no full-scene load).
* Quality gates: 12 automatic checks passed with zero failures.

### API / lifecycle

Processing states now include `EXTRACTING → CALIBRATING → GEOREFERENCING →
VALIDATING → PROCESSED` for real scenes (mock/demo scenes keep the legacy
chain). New SSE events: `scene.extraction.*`, `scene.calibration.*`,
`scene.georeferencing.*`, `scene.preprocessing.completed`.

```
GET /api/v1/satellite/scenes/{id}/processing
→ state, availableProducts, preprocessing provenance summary
   (note: "real Sentinel-1 data — calibrated backscatter only;
    NO oil detection has been performed")
```

**No ML model ran on this scene. No oil detection exists or is claimed.**
