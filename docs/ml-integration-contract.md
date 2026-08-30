# ML Integration Contract — Oil Spill Detection Model

**Audience:** the ML teammate delivering the trained oil-spill segmentation model.
**Consumed by:** `backend/app/inference/` via the `OilSpillModel` interface
(`backend/app/inference/base.py`).

Nothing in this repository invents or trains a model. Until you deliver, the
service runs `MockOilSpillModel`, a clearly-labeled development heuristic whose
outputs are NOT real predictions.

---

## What you must provide (checklist)

### 1. Model file
* Format: PyTorch state-dict (`model.pth`) **or** TorchScript (`.pt`) — tell us which.
* Delivered at a URL/path we configure through `MODEL_PATH` (no code edits).
* Include a checksum and the training git commit for traceability.

### 2. Architecture
* Class name + repo/tag containing the architecture definition
  (e.g. `sagarwatch_ml.models.OilSpillNetV1`), with pinned dependencies
  (`torch==x.y`, etc.).

### 3. Input dimensions
* Spatial size: fixed tile (e.g. `512×512`) or variable with tiling/stitching
  strategy described.
* Batch semantics if relevant.

### 4. Input channels
* Which bands/polarisations: e.g. `[VV_dB]`, `[VV_dB, VH_dB]`, plus any aux
  channels (incidence angle, wind field…). State channel order explicitly.

### 5. Preprocessing
* Exact steps from calibrated GRD sigma0 to model input:
  calibration → speckle filtering (which filter/kernel) → resampling/tiling → …
* Anything you expect the backend to already have done vs. what your
  `preprocess()` performs.

### 6. Normalization
* Formula + constants (per-channel mean/std or min/max), dB conversion details,
  clipping ranges.

### 7. Output format
* We expect **a per-pixel spill probability mask**, float32, values in `[0,1]`,
  same grid as the input raster (or an exact mapping back to it).
* If your raw output is logits/multi-class, specify the softmax/sigmoid step
  and which class index means "oil".

### 8. Threshold
* Recommended operating threshold on the probability mask (becomes
  `MODEL_THRESHOLD`). If you provide precision/recall trade-off data even better.

### 9. Inference requirements
* Device(s): CPU/GPU, min VRAM/RAM, expected latency per scene-tile,
  thread-safety / batching constraints, warm-up needs.

### 10. Example input
* One small sample raster (GeoTIFF, CRS + transform included) that exercises a
  representative case, plus the command/code to run it.

### 11. Example output
* The probability mask produced from (10) — used as a golden regression test
  in `backend/tests/`.

## What the backend does with your model

```
raster ──▶ your preprocess() ──▶ your predict()
       ──▶ probability mask [0..1]
       ──▶ threshold (MODEL_THRESHOLD)
       ──▶ morphological close/open
       ──▶ connected components → contours → polygons (raster CRS)
       ──▶ reproject to EPSG:4326
       ──▶ geodesic area/perimeter (pyproj.Geod)   ← NOT degree-multiplication
       ──▶ MODEL CONFIDENCE = mean probability inside polygon
       ──▶ incident row (PostGIS) + SSE event
```

## Confidence ≠ validation metrics

* **MODEL CONFIDENCE** (stored per incident) = mean predicted probability over
  the detected polygon at inference time. It says nothing about accuracy.
* **MODEL VALIDATION METRICS** (IoU, F1, precision/recall on held-out data) come
  only from YOUR evaluation and will be documented separately when available.
* Never present one as the other; never quote accuracy figures that don't come
  from a real evaluation run.

## Integration steps once delivered

1. Add `app/inference/torch_adapter.py` implementing `OilSpillModel`.
2. Register it in `create_model()` under `MODEL_ADAPTER=torch`.
3. Configure `MODEL_PATH`, `MODEL_DEVICE`, `MODEL_THRESHOLD` via env.
4. Add your example input/output pair as a regression test.
5. Run `pytest tests -q` — the full pipeline tests must stay green.

## Out of scope (do not bundle)

AIS, vessel attribution, drift modelling, dark-vessel detection, authentication,
cloud deployment. Those are later phases of SAGAR WATCH.
