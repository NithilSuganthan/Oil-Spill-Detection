#!/usr/bin/env python3
"""
Download and prepare the Zenodo Sentinel-1 oil-spill segmentation dataset.

Dataset: Sentinel-1 SAR Oil Spill Detection Dataset
URL:     https://zenodo.org/records/8346860
License: CC BY 4.0
Size:    ~1.5 GB (compressed)

The dataset contains paired 512×512 Sentinel-1 GeoTIFFs:
  - VV polarization images  (linear sigma0, not dB)
  - VH polarization images  (linear sigma0, not dB)
  - Binary segmentation masks (0 = background/look-alike, 1 = oil)

After running this script you will have:
  data/zenodo_s1_segmentation/
      raw/          <- extracted GeoTIFFs
      npz/          <- paired .npz files ready for train.py
      splits/       <- train.txt / val.txt / test.txt (scene-level split)
      golden/       <- one held-out golden input/output pair for integration testing
      dataset_info.json

Usage
-----
    python scripts/prepare_zenodo_segmentation_dataset.py \\
        --out-dir data/zenodo_s1_segmentation \\
        [--zenodo-dir /path/to/already-downloaded/zenodo_8346860]

If --zenodo-dir is not given the script will attempt to download from Zenodo
using requests (pip install requests).  The download is ~1.5 GB; use
--zenodo-dir to point at an already-extracted directory if you have it.

NPZ contract (matches SARSegmentationDataset and TinyUNet)
----------------------------------------------------------
Each .npz file contains:
    sar   : float32 array [2, H, W]
              channel 0 = VV (linear sigma0, raw from GeoTIFF)
              channel 1 = VH (linear sigma0, raw from GeoTIFF)
    mask  : uint8  array [H, W]   -- 1 = oil pixel, 0 = background
    scene_id   : str   -- original filename stem
    bounds_lonlat : float32 [4] -- [west, south, east, north] from GeoTIFF geotransform

Note on scale:
    The TinyUNet is trained on robust_normalize(sar) which clips each channel
    to its own [p1, p99] and rescales to [0, 1].  This means it is
    preprocessing-agnostic to the absolute scale; the key invariant is that
    you provide RAW values from the GeoTIFF without applying any dB conversion
    or additional global normalization before calling robust_normalize().
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Optional
import numpy as np

# optional heavy deps (only needed at runtime)
try:
    import rasterio
    from rasterio.errors import NotGeoreferencedWarning
    import warnings
    warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False

ZENODO_RECORD_ID = "8346860"
ZENODO_BASE_URL = f"https://zenodo.org/api/records/{ZENODO_RECORD_ID}"


def _check_rasterio() -> None:
    if not HAS_RASTERIO:
        sys.exit(
            "ERROR: rasterio is required to read GeoTIFF files.\n"
            "Install it with:  pip install rasterio\n"
            "or the full ML extras:  pip install -e '.[ml]'"
        )


def _download_with_progress(url: str, dest: Path, expected_bytes: int = 0) -> None:
    try:
        import requests
    except ImportError:
        sys.exit(
            "ERROR: 'requests' is required for automatic download.\n"
            "Install it with:  pip install requests\n"
            "Or download manually from https://zenodo.org/records/8346860\n"
            "and pass the path with --zenodo-dir."
        )
    print(f"  Downloading {url}")
    print(f"  -> {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", expected_bytes))
        written = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                written += len(chunk)
                if total:
                    pct = written / total * 100
                    mb = written / 1e6
                    print(f"\r  {mb:.0f} MB / {total / 1e6:.0f} MB ({pct:.1f}%)", end="", flush=True)
    print()


def _resolve_download_url(out_dir: Path) -> str:
    try:
        import requests
        resp = requests.get(ZENODO_BASE_URL, timeout=15)
        resp.raise_for_status()
        record = resp.json()
        for f in record.get("files", []):
            key = f.get("key", "")
            if key.endswith(".zip") or key.endswith(".tar.gz"):
                return f["links"]["self"]
        files = record.get("files", [])
        if files:
            return files[0]["links"]["self"]
    except Exception as exc:
        print(f"  WARNING: Could not resolve Zenodo API ({exc}). Trying direct URL.")
    return f"https://zenodo.org/records/{ZENODO_RECORD_ID}/files/sentinel1_oil_spill_dataset.zip"


def _extract_zip(zip_path: Path, dest_dir: Path) -> None:
    print(f"  Extracting {zip_path.name} -> {dest_dir}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        members = zf.namelist()
        for i, member in enumerate(members, 1):
            zf.extract(member, dest_dir)
            if i % 500 == 0:
                print(f"\r  {i}/{len(members)} files", end="", flush=True)
    print()


def _read_geotiff_pair(vv_path: Path, vh_path: Path, mask_path: Path) -> dict:
    """
    Read a VV/VH GeoTIFF pair and its binary mask.
    Values are linear sigma0 (raw from GeoTIFF band 1).
    """
    _check_rasterio()
    with rasterio.open(vv_path) as ds_vv:
        vv = ds_vv.read(1).astype(np.float32)
        transform = ds_vv.transform
        width, height = ds_vv.width, ds_vv.height
        west = transform.c
        north = transform.f
        east = west + transform.a * width
        south = north + transform.e * height
        bounds = np.array([west, south, east, north], dtype=np.float32)

    with rasterio.open(vh_path) as ds_vh:
        vh = ds_vh.read(1).astype(np.float32)

    with rasterio.open(mask_path) as ds_mask:
        mask = ds_mask.read(1).astype(np.uint8)
        mask = (mask > 0).astype(np.uint8)  # binarise

    sar = np.stack([vv, vh], axis=0)  # [2, H, W]
    return {"sar": sar, "mask": mask, "bounds_lonlat": bounds}


def _scene_id_from_path(p: Path) -> str:
    return p.stem.replace("_VV", "").replace("_VH", "").replace("_mask", "")


def _find_triplets(raw_dir: Path) -> list[tuple[Path, Path, Path]]:
    """
    Scan raw_dir for (VV, VH, mask) file triplets.
    The Zenodo dataset naming convention is:
        <scene_id>_VV.tif / <scene_id>_VH.tif / <scene_id>_mask.tif
    """
    vv_files = sorted(raw_dir.rglob("*_VV*.tif")) + sorted(raw_dir.rglob("*_vv*.tif"))
    triplets: list[tuple[Path, Path, Path]] = []
    for vv in vv_files:
        stem = vv.stem
        base = vv.parent
        for vh_name in (stem.replace("_VV", "_VH"), stem.replace("_vv", "_vh")):
            vh = base / (vh_name + ".tif")
            if not vh.exists():
                continue
            for mask_name in (
                stem.replace("_VV", "_mask").replace("_vv", "_mask"),
                stem.replace("_VV", "_label").replace("_vv", "_label"),
            ):
                mask = base / (mask_name + ".tif")
                if mask.exists():
                    triplets.append((vv, vh, mask))
                    break
    return triplets


def _scene_geographic_split(
    triplets: list[tuple[Path, Path, Path]],
    val_frac: float = 0.10,
    test_frac: float = 0.10,
    seed: int = 42,
) -> dict[str, list[int]]:
    n = len(triplets)
    rng = np.random.default_rng(seed)
    indices = np.arange(n)
    rng.shuffle(indices)
    n_test = max(1, int(n * test_frac))
    n_val = max(1, int(n * val_frac))
    return {
        "test": indices[:n_test].tolist(),
        "val": indices[n_test: n_test + n_val].tolist(),
        "train": indices[n_test + n_val:].tolist(),
    }


def prepare(
    raw_dir: Path,
    out_dir: Path,
    val_frac: float = 0.10,
    test_frac: float = 0.10,
) -> None:
    npz_dir = out_dir / "npz"
    splits_dir = out_dir / "splits"
    golden_dir = out_dir / "golden"
    npz_dir.mkdir(parents=True, exist_ok=True)
    splits_dir.mkdir(parents=True, exist_ok=True)
    golden_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nScanning {raw_dir} for VV/VH/mask triplets ...")
    triplets = _find_triplets(raw_dir)
    if not triplets:
        sys.exit(
            f"ERROR: No (VV, VH, mask) GeoTIFF triplets found under {raw_dir}.\n"
            "Check the directory layout matches the Zenodo record description."
        )
    print(f"  Found {len(triplets)} scene triplets.")

    scene_ids: list[str] = []
    print("\nConverting GeoTIFFs -> .npz ...")
    for i, (vv, vh, mask_path) in enumerate(triplets, 1):
        scene_id = _scene_id_from_path(vv)
        scene_ids.append(scene_id)
        npz_path = npz_dir / f"{scene_id}.npz"
        if npz_path.exists():
            continue
        try:
            data = _read_geotiff_pair(vv, vh, mask_path)
            np.savez_compressed(
                npz_path,
                sar=data["sar"],
                mask=data["mask"],
                bounds_lonlat=data["bounds_lonlat"],
                scene_id=np.bytes_(scene_id.encode()),
            )
        except Exception as exc:
            print(f"  WARNING: skipping {scene_id}: {exc}")
        if i % 50 == 0:
            print(f"  {i}/{len(triplets)} done")
    print(f"  All NPZ files written to {npz_dir}")

    splits = _scene_geographic_split(triplets, val_frac, test_frac)
    for split_name, indices in splits.items():
        lines = [scene_ids[i] for i in indices if (npz_dir / f"{scene_ids[i]}.npz").exists()]
        (splits_dir / f"{split_name}.txt").write_text("\n".join(lines), encoding="utf-8")
        print(f"  {split_name}: {len(lines)} scenes")

    # golden test fixture
    test_ids = [scene_ids[i] for i in splits["test"] if (npz_dir / f"{scene_ids[i]}.npz").exists()]
    if test_ids:
        import shutil
        golden_id = test_ids[0]
        src = npz_dir / f"{golden_id}.npz"
        golden_npz = golden_dir / "golden_input.npz"
        shutil.copy2(src, golden_npz)
        sha256 = hashlib.sha256(golden_npz.read_bytes()).hexdigest()
        d = np.load(golden_npz)
        golden_meta = {
            "scene_id": golden_id,
            "sar_shape": list(d["sar"].shape),
            "sar_dtype": str(d["sar"].dtype),
            "mask_shape": list(d["mask"].shape),
            "mask_dtype": str(d["mask"].dtype),
            "channel_order": ["VV_linear_sigma0", "VH_linear_sigma0"],
            "mask_semantics": "1=oil, 0=background_or_look_alike",
            "sha256_golden_npz": sha256,
            "note": (
                "Pass sar to robust_normalize() then to TinyUNet. "
                "Compare sigmoid(logits) > threshold against mask to verify integration correctness."
            ),
        }
        (golden_dir / "golden_meta.json").write_text(json.dumps(golden_meta, indent=2), encoding="utf-8")
        print(f"\n  Golden fixture: {golden_npz}")
        print(f"  SHA-256: {sha256}")

    dataset_info = {
        "zenodo_record": ZENODO_RECORD_ID,
        "zenodo_url": f"https://zenodo.org/records/{ZENODO_RECORD_ID}",
        "license": "CC BY 4.0",
        "total_scenes": len(triplets),
        "split_fractions": {"train": 1 - val_frac - test_frac, "val": val_frac, "test": test_frac},
        "split_counts": {k: len(v) for k, v in splits.items()},
        "sar_channels": ["VV_linear_sigma0", "VH_linear_sigma0"],
        "sar_scale": "linear_sigma0_raw_from_geotiff (NOT dB)",
        "preprocessing_for_model": (
            "robust_normalize(): per-channel clip [p1, p99], rescale to [0, 1]. "
            "Implemented in oil_spill_intel.detection.data.robust_normalize(). "
            "Applied per-scene at inference time — no global mean/std."
        ),
        "tile_size_pixels": "512x512 (native from dataset)",
        "model_input_shape": "[2, 512, 512] or any [2, H, W] — no fixed spatial dim in TinyUNet",
        "model_output": "raw logits [1, H, W]; apply torch.sigmoid() to get probability map",
        "mask_semantics": "1=oil, 0=background_or_look_alike (binary uint8)",
    }
    (out_dir / "dataset_info.json").write_text(json.dumps(dataset_info, indent=2), encoding="utf-8")
    print(f"\n  Dataset info written to {out_dir / 'dataset_info.json'}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download and prepare the Zenodo Sentinel-1 SAR segmentation dataset.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--out-dir", type=Path, default=Path("data/zenodo_s1_segmentation"))
    parser.add_argument("--zenodo-dir", type=Path, default=None,
                        help="Path to an already-extracted Zenodo directory.")
    parser.add_argument("--val-frac", type=float, default=0.10)
    parser.add_argument("--test-frac", type=float, default=0.10)
    args = parser.parse_args()
    _check_rasterio()

    raw_dir = args.zenodo_dir if args.zenodo_dir else args.out_dir / "raw"

    if not args.zenodo_dir:
        zip_dest = args.out_dir / "zenodo_8346860.zip"
        if not zip_dest.exists():
            print(f"\nResolving Zenodo download URL for record {ZENODO_RECORD_ID} ...")
            url = _resolve_download_url(args.out_dir)
            print(f"  URL: {url}")
            _download_with_progress(url, zip_dest, expected_bytes=1_500_000_000)
        else:
            print(f"  Zip already present: {zip_dest}")

        if not raw_dir.exists() or not any(raw_dir.rglob("*.tif")):
            _extract_zip(zip_dest, raw_dir)
        else:
            print(f"  Raw GeoTIFFs already extracted: {raw_dir}")

    prepare(raw_dir, args.out_dir, val_frac=args.val_frac, test_frac=args.test_frac)

    print("\nDataset preparation complete.")
    print("\nNext step — train the TinyUNet segmentation model:")
    print(
        f"  python -m oil_spill_intel.detection.train_and_evaluate \\\n"
        f"      --train-dir {args.out_dir / 'npz'} \\\n"
        f"      --split-dir {args.out_dir / 'splits'} \\\n"
        f"      --golden-dir {args.out_dir / 'golden'} \\\n"
        f"      --out artifacts/sar_unet.pt"
    )


if __name__ == "__main__":
    main()
