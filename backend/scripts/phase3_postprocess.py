"""Add GCPs to probability file and run postprocessing."""
import json
import numpy as np
import rasterio
import sys
from pathlib import Path

ROOT = Path(r"D:\Oil spill detection")
PROCESSED = ROOT / "data" / "scenes" / "processed" / "S1C_IW_GRDH_1SDV_20260826T005736_20260826T005758_009159_012318_7B48_COG"
OUTPUT_DIR = PROCESSED / "inference"
sys.path.insert(0, str(ROOT / "backend"))

# Read GCPs from the source calibrated file
src_path = PROCESSED / "calibrated" / "vv_sigma0_linear.tif"
prob_path = OUTPUT_DIR / "prediction_probability.tif"
prob_fixed_path = OUTPUT_DIR / "prediction_probability_gcps.tif"

with rasterio.open(src_path) as src:
    gcps, gcp_crs = src.gcps
    src_transform = src.transform
    src_crs = src.crs
print(f"Source: {len(gcps)} GCPs, CRS={gcp_crs}, transform={src_transform}")

# Read probability
with rasterio.open(prob_path) as prob_src:
    prob_data = prob_src.read(1)
    prob_meta = prob_src.meta.copy()

# Write probability with GCPs
h, w = prob_data.shape
profile = {
    "driver": "GTiff", "width": w, "height": h, "count": 1,
    "dtype": "float32", "compress": "deflate", "tiled": True,
    "blockxsize": 512, "blockysize": 512,
}
with rasterio.open(prob_fixed_path, "w", **profile) as dst:
    dst.write(prob_data, 1)
    dst.gcps = (gcps, gcp_crs)
    dst.update_tags(
        sar_quantity="oil_spill_probability",
        model="TinyUNet",
        model_version="tiny-unet-v1",
        label="MODEL PREDICTION - not confirmed oil spill",
    )
print(f"Saved with GCPs: {prob_fixed_path}")

# Now run postprocessing
from app.geospatial.mask import morphological_cleanup
from app.geospatial.polygon import mask_to_polygons
from app.geospatial.area import compute_metrics, crs_is_geographic, reproject_geometry

threshold = 0.5
binary = (prob_data >= threshold).astype(np.uint8)
print(f"Binary: {binary.sum()} pixels above threshold ({binary.mean()*100:.4f}%)")

# Save binary with GCPs
binary_path = OUTPUT_DIR / "prediction_mask.tif"
profile_bin = {
    "driver": "GTiff", "width": w, "height": h, "count": 1,
    "dtype": "uint8", "compress": "deflate", "tiled": True,
    "blockxsize": 512, "blockysize": 512, "nodata": 255,
}
with rasterio.open(binary_path, "w", **profile_bin) as dst:
    dst.write(binary, 1)
    dst.gcps = (gcps, gcp_crs)
    dst.update_tags(
        sar_quantity="oil_spill_binary_mask",
        threshold=str(threshold),
        label="MODEL PREDICTION - not confirmed oil spill",
    )
print(f"Saved: {binary_path}")

# Morphological cleanup
cleaned = morphological_cleanup(binary)
polys = mask_to_polygons(cleaned, src_transform, min_area_px=4)
print(f"Candidate polygons from raster: {len(polys)}")

# The source has identity transform + GCPs in EPSG:4326
# Polygons are in pixel space; need to convert using GCPs
WGS84 = "EPSG:4326"

# Build a mapping from pixel to geo using GCPs
gcp_lons = np.array([g.x for g in gcps])
gcp_lats = np.array([g.y for g in gcps])
gcp_cols = np.array([g.col for g in gcps])
gcp_lows = np.array([g.row for g in gcps])

# Simple affine from GCPs: use the first and last GCPs to build approximate transform
# Actually, use the full GCP set with a polynomial fit
from pyproj import Transformer

transformer = Transformer.from_crs(gcp_crs, WGS84, always_xy=True)

detections = []
for idx, poly in enumerate(polys, 1):
    # Convert pixel polygon to geographic using GCPs
    # Sample the polygon boundary and convert each point
    from shapely.geometry import mapping
    coords = list(poly.exterior.coords)
    geo_coords = []
    for px, py in coords:
        # Simple bilinear interpolation from GCPs
        # Find nearest GCPs
        dists = np.sqrt((gcp_cols - px)**2 + (gcp_lows - py)**2)
        nearest_idx = np.argsort(dists)[:4]
        weights = 1.0 / (dists[nearest_idx] + 1e-10)
        weights /= weights.sum()
        lon = np.sum(gcp_lons[nearest_idx] * weights)
        lat = np.sum(gcp_lats[nearest_idx] * weights)
        geo_coords.append((float(lon), float(lat)))

    from shapely.geometry import Polygon as ShapelyPolygon
    try:
        poly_wgs84 = ShapelyPolygon(geo_coords)
        if not poly_wgs84.is_valid:
            poly_wgs84 = poly_wgs84.buffer(0)
    except Exception:
        continue

    if poly_wgs84.is_empty:
        continue

    metrics = compute_metrics(poly_wgs84)
    if metrics.area_km2 < 0.05:
        continue

    geojson = {
        "type": "Polygon",
        "coordinates": [[[round(x, 5), round(y, 5)] for x, y in poly_wgs84.exterior.coords]],
    }
    detections.append({
        "id": f"IN-260826-{idx:03d}",
        "area_km2": round(metrics.area_km2, 4),
        "perimeter_km": round(metrics.perimeter_km, 4),
        "centroid_lon": round(metrics.centroid_lon, 5),
        "centroid_lat": round(metrics.centroid_lat, 5),
        "geometry": geojson,
        "bbox": [round(v, 5) for v in metrics.bbox],
    })

print(f"Detections after area filter: {len(detections)}")
for d in detections:
    print(f"  {d['id']}: {d['area_km2']} km2 at ({d['centroid_lon']}, {d['centroid_lat']})")

# Save result
valid_prob = prob_data[np.isfinite(prob_data)]
result = {
    "scene_id": "S1C_IW_GRDH_1SDV_20260826T005736_20260826T005758_009159_012318_7B48_COG",
    "model": "TinyUNet",
    "model_version": "tiny-unet-v1",
    "threshold": threshold,
    "probability_stats": {
        "prob_min": float(valid_prob.min()),
        "prob_max": float(valid_prob.max()),
        "prob_mean": float(valid_prob.mean()),
        "prob_median": float(np.median(valid_prob)),
        "prob_std": float(valid_prob.std()),
        "n_above_threshold": int(binary.sum()),
        "n_total": int(binary.size),
        "fraction_above": float(binary.mean()),
    },
    "n_candidate_components": len(detections),
    "detections": detections,
    "output_files": {
        "probability": str(prob_fixed_path),
        "binary_mask": str(binary_path),
    },
    "classification": "MODEL PREDICTION - requires human review",
}
result_path = OUTPUT_DIR / "inference_result.json"
result_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
print(f"Saved: {result_path}")
