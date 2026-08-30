"""Phase 3 — Real inference using GEOREFERENCED VV/VH (EPSG:4326).

Uses the georeferenced linear sigma0 files which have proper CRS/transform.
NaN regions (34% from GCP warp) are handled gracefully.
Output prediction GeoTIFFs are directly georeferenced.
"""
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

ROOT = Path(r"D:\Oil spill detection")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("phase3")

PROCESSED = ROOT / "data" / "scenes" / "processed" / "S1C_IW_GRDH_1SDV_20260826T005736_20260826T005758_009159_012318_7B48_COG"
CHECKPOINT = ROOT / "oil_spill_intelligence_team_handoff" / "artifacts" / "sar_unet.pt"
OUTPUT_DIR = PROCESSED / "inference"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VV_PATH = PROCESSED / "georeferenced" / "vv_sigma0_epsg4326.tif"
VH_PATH = PROCESSED / "georeferenced" / "vh_sigma0_epsg4326.tif"


def load_model():
    import torch
    from oil_spill_intel.detection.model import TinyUNet
    logger.info("Loading TinyUNet from %s", CHECKPOINT)
    t0 = time.perf_counter()
    ckpt = torch.load(CHECKPOINT, map_location="cpu", weights_only=True)
    model = TinyUNet(in_channels=ckpt.get("in_channels", 2), base_channels=ckpt.get("base_channels", 32))
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    logger.info("Model loaded in %.2fs", time.perf_counter() - t0)
    return model, ckpt


def robust_normalize(sar: np.ndarray) -> np.ndarray:
    """Per-channel p1-p99 rescale. NaN/nodata -> 0."""
    x = sar.astype(np.float32, copy=True)
    for ch in range(x.shape[0]):
        valid = np.isfinite(x[ch]) & (x[ch] > 0)
        if valid.sum() == 0:
            x[ch] = 0.0
            continue
        lo, hi = np.percentile(x[ch][valid], [1, 99])
        x[ch] = np.clip((x[ch] - lo) / max(hi - lo, 1e-6), 0, 1)
        x[ch][~valid] = 0.0
    return x


def tiled_inference(model, sar_norm, tile_size=512, stride=384):
    import torch
    _, H, W = sar_norm.shape
    prob_sum = np.zeros((H, W), dtype=np.float64)
    weight_sum = np.zeros((H, W), dtype=np.float64)

    def blend_window(size):
        w = np.hanning(size * 2)[:size].astype(np.float64)
        return np.maximum(w, 0.1)

    wx, wy = blend_window(tile_size), blend_window(tile_size)
    window_2d = wy[:, None] * wx[None, :]

    tiles = []
    for y0 in range(0, H, stride):
        for x0 in range(0, W, stride):
            tiles.append((y0, x0, min(y0 + tile_size, H), min(x0 + tile_size, W)))

    logger.info("Inference: %d tiles (%dx%d stride %d)", len(tiles), tile_size, tile_size, stride)
    t0 = time.perf_counter()

    for i, (y0, x0, y1, x1) in enumerate(tiles):
        th, tw = y1 - y0, x1 - x0
        tile = sar_norm[:, y0:y1, x0:x1].astype(np.float32)
        pad_h = (4 - th % 4) % 4
        pad_w = (4 - tw % 4) % 4
        if pad_h or pad_w:
            tile = np.pad(tile, ((0, 0), (0, pad_h), (0, pad_w)), mode="reflect")
        inp = torch.from_numpy(tile)[None, ...]
        with torch.no_grad():
            prob = torch.sigmoid(model(inp)).squeeze().numpy()[:th, :tw]
        win = window_2d[:th, :tw]
        prob_sum[y0:y1, x0:x1] += prob * win
        weight_sum[y0:y1, x0:x1] += win
        if (i + 1) % 200 == 0:
            logger.info("  %d/%d tiles", i + 1, len(tiles))

    weight_sum = np.maximum(weight_sum, 1e-8)
    prob_mask = np.clip(prob_sum / weight_sum, 0, 1).astype(np.float32)
    logger.info("Inference done: %.1fs", time.perf_counter() - t0)
    return prob_mask


def save_geotiff(data, path, transform, crs, dtype="float32", nodata=None, tags=None):
    h, w = data.shape
    profile = {"driver": "GTiff", "width": w, "height": h, "count": 1,
               "dtype": dtype, "crs": crs, "transform": transform,
               "compress": "deflate", "tiled": True, "blockxsize": 512, "blockysize": 512}
    if dtype in ("float32", "float64"):
        profile["predictor"] = 3
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data.astype(dtype), 1)
        if tags:
            dst.update_tags(**tags)


def run():
    from app.config import Settings
    from app.geospatial.mask import morphological_cleanup
    from app.geospatial.polygon import mask_to_polygons
    from app.geospatial.area import compute_metrics, crs_is_geographic, reproject_geometry

    settings = Settings()
    model, ckpt = load_model()

    # Read georeferenced VV/VH
    logger.info("Reading georeferenced VV/VH...")
    with rasterio.open(VV_PATH) as vv:
        vv_data = vv.read(1).astype(np.float32)
        transform = vv.transform
        crs = vv.crs
        h, w = vv.height, vv.width
    with rasterio.open(VH_PATH) as vh:
        vh_data = vh.read(1).astype(np.float32)
    sar = np.stack([vv_data, vh_data], axis=0)
    logger.info("SAR: %s, transform=%s, crs=%s", sar.shape, transform, crs)

    # Normalize
    sar_norm = robust_normalize(sar)
    logger.info("Normalized: [%.4f, %.4f]", np.nanmin(sar_norm), np.nanmax(sar_norm))

    # Inference
    prob_mask = tiled_inference(model, sar_norm, tile_size=512, stride=384)
    logger.info("Prob: [%.6f, %.6f], mean=%.6f", prob_mask.min(), prob_mask.max(), prob_mask.mean())

    # Save probability
    prob_path = OUTPUT_DIR / "prediction_probability.tif"
    save_geotiff(prob_mask, prob_path, transform, crs, tags={
        "sar_quantity": "oil_spill_probability",
        "model": "TinyUNet", "model_version": ckpt.get("model_version", "tiny-unet-v1"),
        "label": "MODEL PREDICTION - not confirmed oil spill",
    })
    logger.info("Saved: %s", prob_path)

    # Binary mask
    threshold = settings.model_threshold
    binary = (prob_mask >= threshold).astype(np.uint8)
    binary_path = OUTPUT_DIR / "prediction_mask.tif"
    save_geotiff(binary, binary_path, transform, crs, dtype="uint8", nodata=255, tags={
        "sar_quantity": "oil_spill_binary_mask", "threshold": str(threshold),
        "label": "MODEL PREDICTION - not confirmed oil spill",
    })
    logger.info("Saved: %s (%d pixels above %.2f)", binary_path, binary.sum(), threshold)

    # Polygon extraction
    cleaned = morphological_cleanup(binary)
    polys = mask_to_polygons(cleaned, transform, min_area_px=4)
    logger.info("Candidate polygons: %d", len(polys))

    WGS84 = "EPSG:4326"
    detections = []
    for idx, poly in enumerate(polys, 1):
        poly_wgs84 = poly if crs_is_geographic(crs) else reproject_geometry(poly, crs, WGS84)
        metrics = compute_metrics(poly_wgs84)
        if metrics.area_km2 < settings.min_poly_area_km2:
            continue
        geojson = {"type": "Polygon",
                   "coordinates": [[[round(x, 5), round(y, 5)] for x, y in poly_wgs84.exterior.coords]]}
        detections.append({
            "id": f"IN-260826-{idx:03d}", "area_km2": round(metrics.area_km2, 4),
            "perimeter_km": round(metrics.perimeter_km, 4),
            "centroid_lon": round(metrics.centroid_lon, 5), "centroid_lat": round(metrics.centroid_lat, 5),
            "geometry": geojson, "bbox": [round(v, 5) for v in metrics.bbox],
        })

    logger.info("Detections: %d", len(detections))
    for d in detections:
        logger.info("  %s: %.4f km2 at (%.5f, %.5f)", d["id"], d["area_km2"], d["centroid_lon"], d["centroid_lat"])

    valid = prob_mask[np.isfinite(prob_mask)]
    result = {
        "scene_id": PROCESSED.name, "model": "TinyUNet",
        "model_version": ckpt.get("model_version", "tiny-unet-v1"),
        "threshold": threshold, "input_files": {"vv": str(VV_PATH), "vh": str(VH_PATH)},
        "preprocessing": "robust_normalize (per-channel p1-p99)",
        "inference": {"tile_size": 512, "tile_stride": 384, "n_tiles": 2640},
        "probability_stats": {
            "prob_min": float(valid.min()), "prob_max": float(valid.max()),
            "prob_mean": float(valid.mean()), "prob_median": float(np.median(valid)),
            "prob_std": float(valid.std()),
            "n_above_threshold": int(binary.sum()), "n_total": int(binary.size),
            "fraction_above": float(binary.mean()),
        },
        "n_candidate_components": len(detections), "detections": detections,
        "output_files": {"probability": str(prob_path), "binary_mask": str(binary_path)},
        "classification": "MODEL PREDICTION - requires human review",
    }
    result_path = OUTPUT_DIR / "inference_result.json"
    result_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    logger.info("Saved: %s", result_path)

    print("\n" + "=" * 70)
    print("PHASE 3 - FIRST REAL DETECTION")
    print("=" * 70)
    print(f"Model: {result['model']} v{result['model_version']}")
    print(f"Threshold: {result['threshold']}")
    print(f"Prob range: [{result['probability_stats']['prob_min']:.6f}, {result['probability_stats']['prob_max']:.6f}]")
    print(f"Prob mean: {result['probability_stats']['prob_mean']:.6f}")
    print(f"Above threshold: {result['probability_stats']['n_above_threshold']} / {result['probability_stats']['n_total']}")
    print(f"Candidates: {result['n_candidate_components']}")
    for d in detections:
        print(f"  {d['id']}: {d['area_km2']} km2 at ({d['centroid_lon']}, {d['centroid_lat']})")
    if not detections:
        print("  No potential slick detected above minimum area threshold.")
    print(f"\nOutputs: {OUTPUT_DIR}")
    print("LABEL: MODEL PREDICTION - not confirmed oil spill")


if __name__ == "__main__":
    run()
