"""Phase 3 — Development Smoke Test & Benchmark.

Runs TinyUNet on a configurable number of tiles from real Sentinel-1 data.
Supports batched inference with numerical regression against single-tile baseline.

Usage:
    python phase3_smoke_test.py                    # 32 tiles, batch=8
    python phase3_smoke_test.py --max-tiles 16     # 16 tiles
    python phase3_smoke_test.py --batch-size 4     # batch=4
    python phase3_smoke_test.py --single-only      # baseline only, no batching
"""
import argparse
import gc
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(r"D:\Oil spill detection")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("smoke")

PROCESSED = ROOT / "data" / "scenes" / "processed" / "S1C_IW_GRDH_1SDV_20260826T005736_20260826T005758_009159_012318_7B48_COG"
CHECKPOINT = ROOT / "oil_spill_intelligence_team_handoff" / "artifacts" / "sar_unet.pt"
OUTPUT_DIR = PROCESSED / "inference"

VV_PATH = PROCESSED / "georeferenced" / "vv_sigma0_epsg4326.tif"
VH_PATH = PROCESSED / "georeferenced" / "vh_sigma0_epsg4326.tif"


def robust_normalize(sar):
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


def generate_tile_coords(H, W, tile_size, stride):
    tiles = []
    for y0 in range(0, H, stride):
        for x0 in range(0, W, stride):
            tiles.append((y0, x0, min(y0 + tile_size, H), min(x0 + tile_size, W)))
    return tiles


def make_blend_window(size):
    w = np.hanning(size * 2)[:size].astype(np.float64)
    return np.maximum(w, 0.1)


def _tile_bbox(tiles):
    """Return (y_min, x_min, y_max, x_max) bounding box of tiles."""
    y_min = min(y0 for y0, _, _, _ in tiles)
    x_min = min(x0 for _, x0, _, _ in tiles)
    y_max = max(y1 for _, _, y1, _ in tiles)
    x_max = max(x1 for _, _, _, x1 in tiles)
    return y_min, x_min, y_max, x_max


def single_tile_inference(model, tiles, sar_norm, window_2d, device):
    """Run tiles one-by-one. Returns (prob_sum, weight_sum, bbox)."""
    y_min, x_min, y_max, x_max = _tile_bbox(tiles)
    prob_sum = np.zeros((y_max - y_min, x_max - x_min), dtype=np.float64)
    weight_sum = np.zeros((y_max - y_min, x_max - x_min), dtype=np.float64)
    import torch
    for i, (y0, x0, y1, x1) in enumerate(tiles):
        th, tw = y1 - y0, x1 - x0
        tile = sar_norm[:, y0:y1, x0:x1].astype(np.float32)
        inp = torch.from_numpy(tile)[None, ...].to(device)
        with torch.no_grad():
            prob = torch.sigmoid(model(inp)).squeeze().cpu().numpy()
        win = window_2d[:th, :tw]
        prob_sum[y0-y_min:y1-y_min, x0-x_min:x1-x_min] += prob[:th, :tw] * win
        weight_sum[y0-y_min:y1-y_min, x0-x_min:x1-x_min] += win
    return prob_sum, weight_sum, (y_min, x_min, y_max, x_max)


def batch_tile_inference(model, tiles, sar_norm, window_2d, device, batch_size=8):
    """Run tiles in batches. Returns (prob_sum, weight_sum, bbox)."""
    y_min, x_min, y_max, x_max = _tile_bbox(tiles)
    prob_sum = np.zeros((y_max - y_min, x_max - x_min), dtype=np.float64)
    weight_sum = np.zeros((y_max - y_min, x_max - x_min), dtype=np.float64)
    import torch
    for start in range(0, len(tiles), batch_size):
        batch_tiles = tiles[start:start + batch_size]
        batch_tensors = []
        batch_meta = []
        for y0, x0, y1, x1 in batch_tiles:
            tile = sar_norm[:, y0:y1, x0:x1].astype(np.float32)
            th, tw = tile.shape[1], tile.shape[2]
            pad_h = (4 - th % 4) % 4
            pad_w = (4 - tw % 4) % 4
            if pad_h or pad_w:
                tile = np.pad(tile, ((0, 0), (0, pad_h), (0, pad_w)), mode="reflect")
            batch_tensors.append(tile)
            batch_meta.append((y0, x0, y1, x1, th, tw))
        batch_input = torch.from_numpy(np.stack(batch_tensors, axis=0)).to(device)
        with torch.no_grad():
            batch_prob = torch.sigmoid(model(batch_input)).squeeze(1).cpu().numpy()
        for j, (y0, x0, y1, x1, th, tw) in enumerate(batch_meta):
            win = window_2d[:th, :tw]
            prob_sum[y0-y_min:y1-y_min, x0-x_min:x1-x_min] += batch_prob[j, :th, :tw] * win
            weight_sum[y0-y_min:y1-y_min, x0-x_min:x1-x_min] += win
        del batch_input, batch_prob, batch_tensors
        if start % 32 == 0 and start > 0:
            logger.info("  batch %d/%d done", start + len(batch_tiles), len(tiles))
    return prob_sum, weight_sum, (y_min, x_min, y_max, x_max)


def build_output_mask(prob_sum, weight_sum):
    """Build probability mask from accumulator."""
    weight_sum = np.maximum(weight_sum, 1e-8)
    prob_mask = np.clip(prob_sum / weight_sum, 0, 1).astype(np.float32)
    return prob_mask


def save_smoke_geotiff(data, path, transform, crs, dtype="float32", nodata=None, tags=None):
    import rasterio
    h, w = data.shape
    profile = {"driver": "GTiff", "width": w, "height": h, "count": 1,
               "dtype": dtype, "crs": crs, "transform": transform,
               "compress": "deflate", "tiled": True, "blockxsize": 512, "blockysize": 512}
    if dtype in ("float32", "float64"):
        profile["predictor"] = 3
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(path, "w", **profile) as dst:
        # Write data — only the rows/cols covered by the tiles
        # The full scene is H x W but tiles only cover a subset
        # We write the full array (uncovered regions stay 0)
        dst.write(data.astype(dtype), 1)
        if tags:
            dst.update_tags(**tags)


def main():
    parser = argparse.ArgumentParser(description="Phase 3 smoke test")
    parser.add_argument("--max-tiles", type=int, default=32, help="Max tiles (0=all)")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size")
    parser.add_argument("--tile-size", type=int, default=512, help="Tile size")
    parser.add_argument("--tile-stride", type=int, default=384, help="Tile stride")
    parser.add_argument("--single-only", action="store_true", help="Skip batched inference")
    parser.add_argument("--all-batches", action="store_true", help="Test batch sizes 1,2,4,8,16")
    args = parser.parse_args()

    import torch
    from oil_spill_intel.detection.model import TinyUNet

    print("=" * 70)
    print("PHASE 3 — SMOKE TEST & BENCHMARK")
    print("=" * 70)

    # Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    print(f"torch: {torch.__version__}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("GPU: NONE (CPU)")
    print(f"Threads: {torch.get_num_threads()}")
    print()

    # Load model
    print("--- Model Loading ---")
    t0 = time.perf_counter()
    ckpt = torch.load(CHECKPOINT, map_location=device, weights_only=True)
    model = TinyUNet(in_channels=ckpt.get("in_channels", 2), base_channels=ckpt.get("base_channels", 32))
    model.load_state_dict(ckpt["model_state"])
    model.to(device)
    model.eval()
    load_time = time.perf_counter() - t0
    print(f"Checkpoint: {CHECKPOINT.name}")
    print(f"Model: TinyUNet, in_channels={ckpt.get('in_channels')}, base_channels={ckpt.get('base_channels')}")
    print(f"Loaded: {load_time:.3f}s")
    n_params = sum(p.numel() for p in model.parameters())
    print(f"Parameters: {n_params:,}")
    print()

    # Load SAR data
    import rasterio
    print("--- SAR Data Loading ---")
    t0 = time.perf_counter()
    with rasterio.open(VV_PATH) as vv:
        vv_data = vv.read(1).astype(np.float32)
        transform = vv.transform
        crs = vv.crs
        H, W = vv.height, vv.width
    with rasterio.open(VH_PATH) as vh:
        vh_data = vh.read(1).astype(np.float32)
    load_sar_time = time.perf_counter() - t0
    sar = np.stack([vv_data, vh_data], axis=0)
    print(f"Shape: {sar.shape} (C,H,W)")
    print(f"CRS: {crs}")
    print(f"Load time: {load_sar_time:.3f}s")
    print()

    # Normalize
    print("--- Normalization ---")
    t0 = time.perf_counter()
    sar_norm = robust_normalize(sar)
    norm_time = time.perf_counter() - t0
    valid = np.isfinite(sar_norm) & (sar_norm > 0)
    print(f"Normalized: [{sar_norm.min():.6f}, {sar_norm.max():.6f}], mean={sar_norm.mean():.6f}")
    print(f"Valid pixels: {valid.sum():,} / {valid.size:,} ({valid.mean()*100:.1f}%)")
    print(f"Norm time: {norm_time:.3f}s")
    print()

    # Generate tiles
    all_tiles = generate_tile_coords(H, W, args.tile_size, args.tile_stride)
    max_tiles = args.max_tiles if args.max_tiles > 0 else len(all_tiles)
    tiles = all_tiles[:max_tiles]
    print("--- Tile Configuration ---")
    print(f"Full scene: {W} x {H}")
    print(f"Tile size: {args.tile_size}")
    print(f"Tile stride: {args.tile_stride}")
    print(f"Total tiles (full scene): {len(all_tiles)}")
    print(f"Tiles for smoke test: {len(tiles)}")
    print()

    # Blend window
    wx = make_blend_window(args.tile_size)
    wy = make_blend_window(args.tile_size)
    window_2d = wy[:, None] * wx[None, :]

    # Baseline: single-tile inference
    print("--- Single-Tile Baseline ---")
    gc.collect()
    t0 = time.perf_counter()
    prob_sum_s, weight_sum_s, bbox_s = single_tile_inference(model, tiles, sar_norm, window_2d, device)
    single_time = time.perf_counter() - t0
    prob_mask_s = build_output_mask(prob_sum_s, weight_sum_s)
    print(f"Time: {single_time:.3f}s")
    print(f"Tiles/sec: {len(tiles)/single_time:.2f}")
    print(f"ms/tile: {single_time*1000/len(tiles):.1f}")
    print(f"Prob range: [{prob_mask_s.min():.6f}, {prob_mask_s.max():.6f}]")
    print(f"Above 0.5: {(prob_mask_s >= 0.5).sum()}")
    est_full = single_time / len(tiles) * len(all_tiles)
    print(f"Estimated full-scene ({len(all_tiles)} tiles): {est_full:.1f}s = {est_full/60:.1f}min")
    print()

    if args.single_only:
        print("Skipping batched inference (--single-only)")
        results = {"single": {"time": single_time, "tiles": len(tiles), "prob_max": float(prob_mask_s.max())}}
    else:
        # Batched inference
        batch_sizes = [args.batch_size] if not args.all_batches else [1, 2, 4, 8, 16]
        results = {"single": {"time": single_time, "tiles": len(tiles), "prob_max": float(prob_mask_s.max())}}
        for bs in batch_sizes:
            label = f"batch-{bs}"
            print(f"--- Batched Inference (batch_size={bs}) ---")
            gc.collect()
            t0 = time.perf_counter()
            prob_sum_b, weight_sum_b, bbox_b = batch_tile_inference(model, tiles, sar_norm, window_2d, device, batch_size=bs)
            batch_time = time.perf_counter() - t0
            prob_mask_b = build_output_mask(prob_sum_b, weight_sum_b)

            # Regression check
            max_diff = np.max(np.abs(prob_mask_s - prob_mask_b))
            agree = np.allclose(prob_mask_s, prob_mask_b, atol=1e-5, rtol=1e-5)
            finite_mask = np.isfinite(prob_mask_s) & np.isfinite(prob_mask_b)
            if finite_mask.any():
                max_diff_fin = float(np.max(np.abs(prob_mask_s[finite_mask] - prob_mask_b[finite_mask])))
            else:
                max_diff_fin = 0.0

            print(f"Time: {batch_time:.3f}s")
            print(f"Tiles/sec: {len(tiles)/batch_time:.2f}")
            print(f"ms/tile: {batch_time*1000/len(tiles):.1f}")
            print(f"Speedup vs single: {single_time/batch_time:.2f}x")
            print(f"Max diff vs single: {max_diff_fin:.8f}")
            print(f"Match (atol=1e-5): {'PASS' if agree else 'FAIL'}")
            print(f"Prob range: [{prob_mask_b.min():.6f}, {prob_mask_b.max():.6f}]")
            est_full_b = batch_time / len(tiles) * len(all_tiles)
            print(f"Estimated full-scene ({len(all_tiles)} tiles): {est_full_b:.1f}s = {est_full_b/60:.1f}min")
            results[label] = {
                "time": batch_time, "tiles": len(tiles),
                "prob_max": float(prob_mask_b.max()),
                "max_diff_vs_single": max_diff_fin,
                "match": agree,
                "speedup": single_time / batch_time,
            }
            print()

    # Memory
    print("--- Peak Memory ---")
    if torch.cuda.is_available():
        peak = torch.cuda.max_memory_allocated() / 1024**2
        print(f"GPU peak: {peak:.0f} MB")
    else:
        try:
            import psutil
            proc = psutil.Process()
            mem = proc.memory_info().rss / 1024**2
            print(f"RSS: {mem:.0f} MB")
        except ImportError:
            print("psutil not available")
    print()

    # Save smoke test outputs
    print("--- Saving Smoke Test Outputs ---")
    smoke_dir = OUTPUT_DIR / "smoke_test"
    smoke_dir.mkdir(parents=True, exist_ok=True)

    # Only write the tile-covered region
    if tiles:
        y_max = max(y1 for _, _, y1, _ in tiles)
        x_max = max(x1 for _, _, _, x1 in tiles)
    else:
        y_max, x_max = 0, 0

    # Probability (partial)
    prob_partial = prob_mask_s[:y_max, :x_max]
    prob_path = smoke_dir / "prediction_smoke_probability.tif"
    save_smoke_geotiff(prob_partial, prob_path, transform, crs, tags={
        "sar_quantity": "oil_spill_probability_smoke_test",
        "model": "TinyUNet", "model_version": ckpt.get("model_version", "tiny-unet-v1"),
        "n_tiles": str(len(tiles)), "label": "MODEL PREDICTION - DEVELOPMENT SMOKE TEST",
    })

    # Binary mask
    binary_partial = (prob_partial >= 0.5).astype(np.uint8)
    mask_path = smoke_dir / "prediction_smoke_mask.tif"
    save_smoke_geotiff(binary_partial, mask_path, transform, crs, dtype="uint8", nodata=255, tags={
        "sar_quantity": "oil_spill_binary_mask_smoke_test",
        "threshold": "0.5",
        "label": "MODEL PREDICTION - DEVELOPMENT SMOKE TEST",
    })

    print(f"Probability: {prob_path}")
    print(f"Binary mask: {mask_path}")
    print(f"Output region: {x_max} x {y_max} pixels (tile-covered area)")
    print()

    # Save benchmark JSON
    benchmark = {
        "device": str(device),
        "torch_version": torch.__version__,
        "model": "TinyUNet",
        "n_params": n_params,
        "checkpoint": str(CHECKPOINT),
        "tile_size": args.tile_size,
        "tile_stride": args.tile_stride,
        "total_tiles_full_scene": len(all_tiles),
        "smoke_test_tiles": len(tiles),
        "smoke_test_region": f"{x_max}x{y_max}",
        "load_time_s": round(load_time, 3),
        "sar_load_time_s": round(load_sar_time, 3),
        "norm_time_s": round(norm_time, 3),
        "results": results,
        "estimated_full_scene_single_s": round(est_full, 1) if "single" in results else None,
    }
    bench_path = smoke_dir / "benchmark.json"
    bench_path.write_text(json.dumps(benchmark, indent=2, default=str), encoding="utf-8")
    print(f"Benchmark: {bench_path}")

    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Device:        {device}")
    print(f"Batch size:    {args.batch_size}")
    print(f"Tile size:     {args.tile_size}")
    print(f"Stride:        {args.tile_stride}")
    print(f"Total tiles:   {len(all_tiles)}")
    print(f"Smoke tiles:   {len(tiles)}")
    print(f"Single time:   {single_time:.3f}s ({len(tiles)/single_time:.2f} tiles/s)")
    if "single" in results:
        s = results["single"]
        est = s["time"] / s["tiles"] * len(all_tiles)
        print(f"Est. full:     {est:.0f}s = {est/60:.1f}min")
    best_batch = max((k for k in results if k.startswith("batch-")), key=lambda k: results[k].get("speedup", 0), default=None)
    if best_batch:
        b = results[best_batch]
        print(f"Best batch:    {best_batch} ({b['speedup']:.2f}x, match={b['match']})")
    print()
    print("SMOKE TEST COMPLETE. Full-scene inference NOT started.")
    print("=" * 70)


if __name__ == "__main__":
    main()
