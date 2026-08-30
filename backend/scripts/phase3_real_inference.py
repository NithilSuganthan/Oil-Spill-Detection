"""Phase 3 — Real TinyUNet inference on the Sentinel-1 scene.

Reads calibrated VV/VH linear sigma0, runs tiled TinyUNet inference,
generates prediction GeoTIFFs, and feeds into the geospatial pipeline
to create potential slick detections.

DO NOT retrain, modify weights, or fabricate detections.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("phase3_inference")

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(r"D:\Oil spill detection")
PROCESSED = ROOT / "data" / "scenes" / "processed" / "S1C_IW_GRDH_1SDV_20260826T005736_20260826T005758_009159_012318_7B48_COG"
CHECKPOINT = ROOT / "oil_spill_intelligence_team_handoff" / "artifacts" / "sar_unet.pt"
OUTPUT_DIR = PROCESSED / "inference"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VV_LINEAR = PROCESSED / "calibrated" / "vv_sigma0_linear.tif"
VH_LINEAR = PROCESSED / "calibrated" / "vh_sigma0_linear.tif"

# ── Load model ────────────────────────────────────────────────────────────────
def load_model():
    import torch
    from oil_spill_intel.detection.model import TinyUNet

    logger.info("Loading TinyUNet from %s", CHECKPOINT)
    t0 = time.perf_counter()
    checkpoint = torch.load(CHECKPOINT, map_location="cpu", weights_only=True)
    model = TinyUNet(
        in_channels=checkpoint.get("in_channels", 2),
        base_channels=checkpoint.get("base_channels", 32),
    )
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    elapsed = time.perf_counter() - t0
    logger.info("Model loaded in %.2fs", elapsed)
    return model, checkpoint


# ── Read VV/VH and stack ─────────────────────────────────────────────────────
def read_vv_vh() -> tuple[np.ndarray, object, object]:
    """Read calibrated VV and VH linear sigma0, return [2, H, W] + metadata."""
    logger.info("Reading VV: %s", VV_LINEAR)
    with rasterio.open(VV_LINEAR) as vv:
        vv_data = vv.read(1).astype(np.float32)
        transform = vv.transform
        crs = vv.crs
        h, w = vv.height, vv.width
    logger.info("  VV shape: %s", vv_data.shape)

    logger.info("Reading VH: %s", VH_LINEAR)
    with rasterio.open(VH_LINEAR) as vh:
        vh_data = vh.read(1).astype(np.float32)
    logger.info("  VH shape: %s", vh_data.shape)

    # Stack to [2, H, W]
    sar = np.stack([vv_data, vh_data], axis=0)
    logger.info("Stacked SAR: %s", sar.shape)
    return sar, transform, crs


# ── Robust normalize ──────────────────────────────────────────────────────────
def robust_normalize(sar: np.ndarray) -> np.ndarray:
    """Per-channel p1-p99 percentile rescale to [0, 1].

    NaN/nodata pixels (value <= 0 or NaN) are masked and set to 0 after normalization.
    Percentiles are computed only from valid pixels.
    """
    x = sar.astype(np.float32, copy=True)
    for ch in range(x.shape[0]):
        valid = np.isfinite(x[ch]) & (x[ch] > 0)
        if valid.sum() == 0:
            x[ch] = 0.0
            continue
        lo, hi = np.percentile(x[ch][valid], [1, 99])
        x[ch] = np.clip((x[ch] - lo) / max(hi - lo, 1e-6), 0, 1)
        x[ch][~valid] = 0.0  # nodata -> 0
    return x


# ── Tiled inference ───────────────────────────────────────────────────────────
def tiled_inference(model, sar_norm: np.ndarray, tile_size: int = 512, stride: int = 384) -> np.ndarray:
    """Run tiled inference with raised-cosine blending."""
    import torch

    _, H, W = sar_norm.shape
    prob_sum = np.zeros((H, W), dtype=np.float64)
    weight_sum = np.zeros((H, W), dtype=np.float64)

    # Raised cosine blending window
    def blend_window(size):
        w = np.hanning(size * 2)[:size].astype(np.float64)
        w = np.maximum(w, 0.1)
        return w

    wx = blend_window(tile_size)
    wy = blend_window(tile_size)
    window_2d = wy[:, None] * wx[None, :]

    # Generate tiles
    tiles = []
    for y0 in range(0, H, stride):
        for x0 in range(0, W, stride):
            y1 = min(y0 + tile_size, H)
            x1 = min(x0 + tile_size, W)
            tiles.append((y0, x0, y1, x1))

    logger.info("Tiled inference: %d tiles (size=%d, stride=%d) on %dx%d",
                len(tiles), tile_size, stride, W, H)

    t0 = time.perf_counter()
    for i, (y0, x0, y1, x1) in enumerate(tiles):
        tile_h, tile_w = y1 - y0, x1 - x0
        tile = sar_norm[:, y0:y1, x0:x1].astype(np.float32)

        # Pad to be divisible by 4 (TinyUNet has 2 maxpool layers)
        pad_h = (4 - tile_h % 4) % 4
        pad_w = (4 - tile_w % 4) % 4
        if pad_h > 0 or pad_w > 0:
            tile = np.pad(tile, ((0, 0), (0, pad_h), (0, pad_w)), mode="reflect")

        inp = torch.from_numpy(tile)[None, ...]
        with torch.no_grad():
            logits = model(inp)
            prob = torch.sigmoid(logits).squeeze().numpy()

        # Crop back to original tile size
        prob = prob[:tile_h, :tile_w]
        win = window_2d[:tile_h, :tile_w]
        prob_sum[y0:y1, x0:x1] += prob * win
        weight_sum[y0:y1, x0:x1] += win
        if (i + 1) % 100 == 0:
            logger.info("  tile %d/%d", i + 1, len(tiles))

    weight_sum = np.maximum(weight_sum, 1e-8)
    prob_mask = (prob_sum / weight_sum).astype(np.float32)
    prob_mask = np.clip(prob_mask, 0.0, 1.0)

    elapsed = time.perf_counter() - t0
    logger.info("Inference complete: %d tiles in %.1fs", len(tiles), elapsed)
    return prob_mask


# ── Save GeoTIFFs ────────────────────────────────────────────────────────────
def save_geotiff(data: np.ndarray, path: Path, transform, crs, dtype="float32",
                 nodata=None, tags=None):
    """Save a single-band GeoTIFF."""
    h, w = data.shape
    profile = {
        "driver": "GTiff", "width": w, "height": h, "count": 1,
        "dtype": dtype, "crs": crs, "transform": transform,
        "compress": "deflate", "tiled": True,
        "blockxsize": 512, "blockysize": 512,
    }
    # predictor=3 (floating point LZW) only works with float types
    if dtype in ("float32", "float64"):
        profile["predictor"] = 3
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data.astype(dtype), 1)
        if tags:
            dst.update_tags(**tags)


# ── Run full pipeline ────────────────────────────────────────────────────────
def run():
    from app.config import Settings
    from app.domain.entities import SatelliteSceneRecord
    from app.geospatial.area import compute_metrics, crs_is_geographic, reproject_geometry
    from app.geospatial.mask import morphological_cleanup, threshold_mask
    from app.geospatial.polygon import mask_to_polygons
    from app.inference.torch_adapter import TorchOilSpillModel

    settings = Settings()

    # 1. Load model
    model, checkpoint = load_model()

    # 2. Read VV/VH
    sar, transform, crs = read_vv_vh()

    # 3. Normalize
    logger.info("Applying robust_normalize...")
    sar_norm = robust_normalize(sar)
    logger.info("Normalized range: [%.4f, %.4f]", sar_norm.min(), sar_norm.max())

    # 4. Tiled inference
    prob_mask = tiled_inference(model, sar_norm, tile_size=512, stride=384)
    logger.info("Probability mask: shape=%s range=[%.6f, %.6f] mean=%.6f",
                prob_mask.shape, prob_mask.min(), prob_mask.max(), prob_mask.mean())

    # 5. Save probability GeoTIFF
    prob_path = OUTPUT_DIR / "prediction_probability.tif"
    save_geotiff(prob_mask, prob_path, transform, crs, tags={
        "sar_quantity": "oil_spill_probability",
        "model": "TinyUNet",
        "model_version": checkpoint.get("model_version", "tiny-unet-v1"),
        "label": "MODEL PREDICTION - not confirmed oil spill",
    })
    logger.info("Saved probability: %s", prob_path)

    # 6. Binary mask
    threshold = settings.model_threshold
    binary = threshold_mask(prob_mask, threshold)
    binary_u8 = binary.astype(np.uint8)
    binary_path = OUTPUT_DIR / "prediction_mask.tif"
    save_geotiff(binary_u8, binary_path, transform, crs, dtype="uint8",
                 nodata=255, tags={
                     "sar_quantity": "oil_spill_binary_mask",
                     "threshold": str(threshold),
                     "label": "MODEL PREDICTION - not confirmed oil spill",
                 })
    logger.info("Saved binary mask: %s (threshold=%.2f)", binary_path, threshold)

    # 7. Probability statistics
    valid_prob = prob_mask[np.isfinite(prob_mask)]
    stats = {
        "prob_min": float(valid_prob.min()),
        "prob_max": float(valid_prob.max()),
        "prob_mean": float(valid_prob.mean()),
        "prob_median": float(np.median(valid_prob)),
        "prob_std": float(valid_prob.std()),
        "n_above_threshold": int((binary_u8 == 1).sum()),
        "n_total": int(binary_u8.size),
        "fraction_above_threshold": float((binary_u8 == 1).mean()),
        "threshold": threshold,
    }
    logger.info("Probability stats: %s", json.dumps(stats, indent=2))

    # 8. Morphological cleanup + polygon extraction
    cleaned = morphological_cleanup(binary)
    polys = mask_to_polygons(cleaned, transform, min_area_px=4)
    logger.info("Extracted %d candidate polygons", len(polys))

    # 9. Georeference to WGS84 and compute metrics
    WGS84 = "EPSG:4326"
    detections = []
    for idx, poly in enumerate(polys, 1):
        if crs_is_geographic(crs):
            poly_wgs84 = poly
        else:
            poly_wgs84 = reproject_geometry(poly, crs, WGS84)

        metrics = compute_metrics(poly_wgs84)
        if metrics.area_km2 < settings.min_poly_area_km2:
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

    # 10. Save detection results
    result = {
        "scene_id": "S1C_IW_GRDH_1SDV_20260826T005736_20260826T005758_009159_012318_7B48_COG",
        "model": "TinyUNet",
        "model_version": checkpoint.get("model_version", "tiny-unet-v1"),
        "checkpoint_sha256": checkpoint.get("checkpoint_sha256", ""),
        "val_dice_f1": checkpoint.get("val_dice_f1", None),
        "val_iou": checkpoint.get("val_iou", None),
        "threshold": threshold,
        "input_files": {
            "vv_linear": str(VV_LINEAR),
            "vh_linear": str(VH_LINEAR),
        },
        "preprocessing": "robust_normalize (per-channel p1-p99)",
        "inference": {
            "tile_size": 512,
            "tile_stride": 384,
        },
        "probability_stats": stats,
        "n_candidate_components": len(detections),
        "detections": detections,
        "output_files": {
            "probability": str(prob_path),
            "binary_mask": str(binary_path),
        },
        "classification": "MODEL PREDICTION - requires human review",
    }

    result_path = OUTPUT_DIR / "inference_result.json"
    result_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    logger.info("Saved result: %s", result_path)

    # 11. Visual QC images
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # VV dB preview
        vv_db = 10 * np.log10(np.maximum(sar[0], 1e-10))
        fig, ax = plt.subplots(figsize=(14, 10))
        valid = vv_db[np.isfinite(vv_db)]
        lo, hi = np.percentile(valid, [2, 98])
        ax.imshow(vv_db, cmap="gray", vmin=lo, vmax=hi)
        ax.set_title("SAR backscatter - not oil detection\nVV sigma0 (dB)", fontsize=13)
        plt.colorbar(ax.images[0], ax=ax, label="sigma0 (dB)")
        plt.tight_layout()
        fig.savefig(OUTPUT_DIR / "vv_sigma0_db_preview.png", dpi=120, bbox_inches="tight")
        plt.close(fig)

        # Probability mask
        fig, ax = plt.subplots(figsize=(14, 10))
        im = ax.imshow(prob_mask, cmap="hot", vmin=0, vmax=1)
        ax.set_title("MODEL PREDICTION - not confirmed oil spill\nTinyUNet probability", fontsize=13)
        plt.colorbar(im, ax=ax, label="Probability")
        plt.tight_layout()
        fig.savefig(OUTPUT_DIR / "probability_preview.png", dpi=120, bbox_inches="tight")
        plt.close(fig)

        # Binary mask overlay on VV
        fig, ax = plt.subplots(figsize=(14, 10))
        vv_vis = np.clip((vv_db - lo) / max(hi - lo, 1e-9), 0, 1)
        overlay = np.stack([vv_vis, vv_vis, vv_vis], axis=-1)
        overlay[cleaned, 0] = 1.0  # Red channel for detections
        overlay[cleaned, 1] = 0.0
        overlay[cleaned, 2] = 0.0
        ax.imshow(overlay)
        ax.set_title("MODEL PREDICTION overlay on SAR\nRed = predicted potential slick", fontsize=13)
        plt.tight_layout()
        fig.savefig(OUTPUT_DIR / "sar_prediction_overlay.png", dpi=120, bbox_inches="tight")
        plt.close(fig)

        logger.info("Visual QC images saved to %s", OUTPUT_DIR)
    except Exception as e:
        logger.warning("Visual QC failed: %s", e)

    print("\n" + "=" * 70)
    print("PHASE 3 INFERENCE COMPLETE")
    print("=" * 70)
    print(f"Scene: {result['scene_id']}")
    print(f"Model: {result['model']} v{result['model_version']}")
    print(f"Threshold: {result['threshold']}")
    print(f"Probability range: [{stats['prob_min']:.6f}, {stats['prob_max']:.6f}]")
    print(f"Probability mean: {stats['prob_mean']:.6f}")
    print(f"Candidate components: {result['n_candidate_components']}")
    for d in detections:
        print(f"  {d['id']}: {d['area_km2']} km^2 at ({d['centroid_lon']}, {d['centroid_lat']})")
    print(f"\nOutputs in: {OUTPUT_DIR}")
    print("LABEL: MODEL PREDICTION - not confirmed oil spill")

    return result


if __name__ == "__main__":
    run()
