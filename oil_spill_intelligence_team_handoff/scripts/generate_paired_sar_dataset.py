"""
Build paired Sentinel-1 SAR segmentation dataset from real CSIRO Sentinel-1 SAR chips.

This script constructs realistic paired VV/VH SAR scenes with pixel-level ground truth masks
using real Sentinel-1 radar backscatter chips (oil and non-oil/look-alikes).

Output directory structure:
  data/s1_segmentation/
    npz/          <- paired .npz files with sar [2, H, W] and mask [H, W]
    splits/       <- train.txt, val.txt, test.txt
    golden/       <- golden_input.npz, golden_meta.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
import numpy as np
from PIL import Image


def extract_slick_mask(chip_gray: np.ndarray) -> np.ndarray:
    """Extract oil slick region from a real Class 1 SAR chip."""
    chip_f = chip_gray.astype(np.float32) / 255.0
    # Otsu thresholding
    hist, bin_edges = np.histogram(chip_f, bins=64, range=(0.0, 1.0))
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    weight1 = np.cumsum(hist)
    weight2 = np.cumsum(hist[::-1])[::-1]
    mean1 = np.cumsum(hist * bin_centers) / np.maximum(weight1, 1)
    mean2 = (np.cumsum((hist * bin_centers)[::-1])[::-1]) / np.maximum(weight2, 1)
    variance = weight1[:-1] * weight2[1:] * (mean1[:-1] - mean2[1:]) ** 2
    idx = np.argmax(variance)
    thresh = float(bin_centers[idx])
    
    # Oil is the darker cluster
    mask = (chip_f < thresh).astype(np.uint8)
    return mask



def create_scene(
    class0_paths: list[Path],
    class1_paths: list[Path],
    scene_idx: int,
    rng: np.random.Generator,
    tile_size: int = 256,
) -> tuple[np.ndarray, np.ndarray]:
    """Create a paired VV/VH tile [2, tile_size, tile_size] with ground truth mask."""
    # 1. Base ocean background from a Class 0 SAR chip
    bg_path = rng.choice(class0_paths)
    bg_img = Image.open(bg_path).convert("L").resize((tile_size, tile_size))
    bg = np.asarray(bg_img, dtype=np.float32) / 255.0  # [0, 1] linear proxy
    
    # Scale to typical linear sigma-0 range for Sentinel-1 ocean backscatter (0.01 to 0.15)
    vv = bg * 0.10 + 0.01
    mask = np.zeros((tile_size, tile_size), dtype=np.uint8)
    
    # 2. Decide if this scene has an oil slick (80% probability)
    has_slick = rng.random() < 0.85
    if has_slick:
        slick_path = rng.choice(class1_paths)
        slick_chip = np.asarray(Image.open(slick_path).convert("L"), dtype=np.uint8)
        slick_mask_raw = extract_slick_mask(slick_chip)
        
        # If valid slick found, blend into scene
        if slick_mask_raw.sum() >= 20:
            # Resize chip
            scale = rng.uniform(0.6, 1.2)
            nw = max(16, int(slick_chip.shape[1] * scale))
            nh = max(16, int(slick_chip.shape[0] * scale))
            
            sc_img = Image.fromarray(slick_chip).resize((nw, nh), Image.Resampling.BILINEAR)
            sm_img = Image.fromarray(slick_mask_raw * 255).resize((nw, nh), Image.Resampling.NEAREST)
            
            sc_arr = (np.asarray(sc_img, dtype=np.float32) / 255.0) * 0.10 + 0.01
            sm_arr = (np.asarray(sm_img) > 128).astype(np.uint8)
            
            # Place in random position
            max_y = tile_size - nh
            max_x = tile_size - nw
            if max_y > 0 and max_x > 0:
                pos_y = rng.integers(0, max_y)
                pos_x = rng.integers(0, max_x)
                
                # Blend slick into VV channel
                patch_mask = sm_arr == 1
                vv_patch = vv[pos_y:pos_y+nh, pos_x:pos_x+nw]
                # Darken the backscatter where oil is present (damping short capillary waves)
                vv_patch[patch_mask] = np.minimum(vv_patch[patch_mask], sc_arr[patch_mask] * 0.5)
                vv[pos_y:pos_y+nh, pos_x:pos_x+nw] = vv_patch
                mask[pos_y:pos_y+nh, pos_x:pos_x+nw] = sm_arr

    # 3. Simulate VH channel (cross-polarization: lower backscatter by ~6-8 dB and lower contrast)
    vh_noise = rng.normal(0, 0.002, (tile_size, tile_size)).astype(np.float32)
    vh = np.clip(vv * 0.25 + vh_noise, 0.001, 0.05)
    
    sar = np.stack([vv.astype(np.float32), vh.astype(np.float32)], axis=0)  # [2, H, W]
    return sar, mask


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate paired SAR segmentation dataset.")
    parser.add_argument("--csiro-dir", type=Path, default=Path("data/raw/csiro_sentinel1_oil_nooil/kaggle/data"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/s1_segmentation"))
    parser.add_argument("--num-scenes", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    class0 = sorted((args.csiro_dir / "Class_0").glob("*.jpg"))
    class1 = sorted((args.csiro_dir / "Class_1").glob("*.jpg"))
    if not class0 or not class1:
        raise SystemExit(f"Class_0 or Class_1 images not found in {args.csiro_dir}")

    npz_dir = args.out_dir / "npz"
    splits_dir = args.out_dir / "splits"
    golden_dir = args.out_dir / "golden"
    npz_dir.mkdir(parents=True, exist_ok=True)
    splits_dir.mkdir(parents=True, exist_ok=True)
    golden_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(args.seed)
    scene_ids = []
    print(f"Generating {args.num_scenes} paired SAR segmentation scenes...")

    for i in range(args.num_scenes):
        scene_id = f"s1_sar_scene_{i+1:04d}"
        sar, mask = create_scene(class0, class1, i, rng)
        
        # Synthetic geographic bounds (e.g. Arabian Sea off Mumbai)
        west = 72.0 + rng.uniform(0, 1.5)
        north = 19.5 - rng.uniform(0, 1.5)
        bounds = np.array([west, north - 0.5, west + 0.5, north], dtype=np.float32)
        
        npz_path = npz_dir / f"{scene_id}.npz"
        np.savez_compressed(
            npz_path,
            sar=sar,
            mask=mask,
            bounds_lonlat=bounds,
            scene_id=np.bytes_(scene_id.encode()),
        )
        scene_ids.append(scene_id)
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{args.num_scenes} scenes generated")

    # Splits (80% train, 10% val, 10% test)
    rng.shuffle(scene_ids)
    n_test = max(1, int(len(scene_ids) * 0.10))
    n_val = max(1, int(len(scene_ids) * 0.10))
    
    test_ids = scene_ids[:n_test]
    val_ids = scene_ids[n_test:n_test + n_val]
    train_ids = scene_ids[n_test + n_val:]

    (splits_dir / "train.txt").write_text("\n".join(train_ids), encoding="utf-8")
    (splits_dir / "val.txt").write_text("\n".join(val_ids), encoding="utf-8")
    (splits_dir / "test.txt").write_text("\n".join(test_ids), encoding="utf-8")
    print(f"Splits created: {len(train_ids)} train, {len(val_ids)} val, {len(test_ids)} test scenes")

    # Golden test fixture: choose a test scene that contains an oil slick
    golden_id = test_ids[0]
    for tid in test_ids:
        d_test = np.load(npz_dir / f"{tid}.npz")
        if d_test["mask"].sum() >= 100:
            golden_id = tid
            break
    golden_src = npz_dir / f"{golden_id}.npz"
    golden_npz = golden_dir / "golden_input.npz"
    shutil.copy2(golden_src, golden_npz)

    
    sha256 = hashlib.sha256(golden_npz.read_bytes()).hexdigest()
    d = np.load(golden_npz)
    meta = {
        "scene_id": golden_id,
        "sar_shape": list(d["sar"].shape),
        "sar_dtype": str(d["sar"].dtype),
        "mask_shape": list(d["mask"].shape),
        "mask_dtype": str(d["mask"].dtype),
        "channel_order": ["VV_linear_sigma0", "VH_linear_sigma0"],
        "mask_semantics": "1=oil, 0=background_or_look_alike",
        "sha256_golden_npz": sha256,
        "note": "Golden input scene for integration verification.",
    }
    (golden_dir / "golden_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Golden fixture saved to {golden_npz} (SHA256: {sha256[:16]}...)")
    print("Done.")


if __name__ == "__main__":
    main()
