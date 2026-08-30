# Integration Contract

The backend exports small JSON-serialisable dataclasses. Import the components directly:

```python
from oil_spill_intel.detection import PotentialSlickDetector
from oil_spill_intel.drift import EnsembleHindcaster
from oil_spill_intel.attribution import rank_vessels
```

## Processing order

1. Call `PotentialSlickDetector(model_path, verifier_model_path="artifacts/csiro_s1_verifier.joblib").predict(scene_id, acquired_at, sar, metadata)`. The verifier is trained on real Sentinel-1 chips and adjusts candidate confidence; it does not replace a mask-trained segmenter.
2. Select a reviewed potential slick; pass its centroid, observation time and candidate release window to `EnsembleHindcaster.infer(...)`.
3. Copy `hindcast.estimated_age_hours` into the reviewed detection record; this is a model-derived estimate, not directly measured by SAR.
4. Pass the hindcast source centroid and source time window plus a normalized AIS DataFrame to `rank_vessels(...)`.
5. Return all fields to the UI. Do not strip `quality_flags`, component explanations, or `human_review_required`.

## Detection metadata

```json
{
  "bounds_lonlat": [west, south, east, north],
  "pixel_area_km2": 0.0001,
  "wind_speed_mps": 6.2,
  "wave_height_m": 1.0,
  "incidence_angle_deg": 34.0
}
```

## AIS columns

Required: `mmsi`, `timestamp` (ISO-8601), `lat`, `lon`.

Recommended: `sog`, `cog`, `heading`, `vessel_type`, `imo`, `vessel_name`, `draft`, `status`.

`coverage_known=True` should be passed to attribution only when the product knows the receiving coverage and data latency. Otherwise AIS gaps are reported but deliberately contribute zero to the score.

## Production replacement points

- Replace `ConstantForcing` with a validated gridded ocean-current/wind adapter. It must interpolate location/time and record source/version/latency.
- Replace the demo heuristic with a trained `TinyUNet` checkpoint (`.pt`) after training on properly licensed SAR imagery plus masks. The portable `.npz` logistic model is only a smoke-test baseline.
- Add calibrated confidence (temperature scaling or isotonic calibration) using an independent regional validation set.
- Use GeoTIFF/GeoJSON adapters in the API boundary. The supplied core remains format-agnostic so it is straightforward to integrate.

## Response language

Use `potential slick` and `potential source`. Every result is advisory and requires human review/independent validation before any enforcement action.
