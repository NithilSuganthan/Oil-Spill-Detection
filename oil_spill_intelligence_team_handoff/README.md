# Oil Spill Intelligence — ML Module

This repository contains the integration-ready backend for the three analytical parts of the project:

1. SAR potential-oil-slick segmentation and characterisation;
2. forward-physics ensemble hindcasting/forecasting; and
3. explainable AIS candidate ranking.

It deliberately produces **potential-slick** and **potential-source** evidence, never autonomous enforcement conclusions. Every response carries confidence, limitations, and a `human_review_required` field.

## Quick start

```powershell
python -m pip install -e ".[ml,dev]"
python -m oil_spill_intel.demo --output-dir demo_output
python -m pytest
```

The demo creates synthetic data only, runs detection, hindcasting, and vessel ranking, and writes API-friendly JSON/GeoJSON artifacts. It proves component integration; it is not a trained operational model.

## Data contracts

- Detection input: `.npz` containing `sar` as `[channels, height, width]`, optional `mask`, plus a JSON sidecar with acquisition time, bounds, wind, wave and incidence-angle metadata.
- Training data: paired `.npz` files with `sar` and `mask`. `SARSegmentationDataset` can be extended for georeferenced Sentinel-1 GeoTIFFs where Rasterio is installed.
- AIS input: CSV with `mmsi`, `timestamp`, `lat`, `lon`, and optional `sog`, `cog`, `heading`, `vessel_type`, `imo`, `vessel_name`.
- Hindcast input: an observed slick location/time and an ocean-forcing provider. The included `ConstantForcing` is for tests/demo only. Integrators should supply a validated gridded INCOIS/ocean model adapter.

## Included real SAR training data

`data/raw/csiro_sentinel1_oil_nooil/` contains the downloaded CC BY-SA 4.0 CSIRO Sentinel-1 chip dataset (via Kaggle): 5,630 labelled 400×400 oil/no-oil chips, including look-alikes. Train the real-SAR verifier with:

```powershell
python -m oil_spill_intel.detection.classifier --data-dir data/raw/csiro_sentinel1_oil_nooil/kaggle/data --out artifacts/csiro_s1_verifier.joblib
```

It is a candidate verifier/classifier, not a segmentation dataset. Pixel-level boundary training still requires paired masks such as the cited Zenodo Sentinel-1 segmentation collection.

## Deployment guardrails

- A dark SAR region is not proof of oil; use `look_alike_risk`, confidence calibration and human review.
- Do not treat a missing AIS match as exculpatory or incriminating by itself; coverage, latency and reception data must be considered.
- Hindcasts return a probability ensemble, not a single certain source point.
- Use independent observations and documented datasets for validation before operational use.

See [PROJECT_CONTEXT_HANDOFF.md](PROJECT_CONTEXT_HANDOFF.md) for the researched technical context and sources.
