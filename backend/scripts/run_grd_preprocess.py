"""Run REAL Sentinel-1 GRD preprocessing for an acquired product.

    python scripts/run_grd_preprocess.py [--scene-id S1C_...]

Extracts metadata, applies radiometric calibration (sigma0 = DN^2/A_sigma^2),
georeferences via the product GCPs, produces dB model_input representations,
validates everything and writes previews + provenance under
data/scenes/processed/<scene_id>/.

NO oil-spill detection runs here. Dark SAR regions are not oil.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.satellite.grd_preprocess import GrdConfig, GrdPreprocessor
from app.storage_keys import product_key_for


def _working_set_mb() -> float:
    """Current process working set on Windows (diagnostic only)."""
    import psutil  # optional

    return psutil.Process().memory_info().rss / 1e6


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--bbox", default=None, help="expected footprint west,south,east,north")
    args = parser.parse_args()

    settings = get_settings()
    zip_path = Path(settings.scene_storage_dir) / "products" / f"{args.scene_id}.zip"
    if not zip_path.exists():
        print(f"product not found: {zip_path}")
        return 1

    bbox = tuple(float(v) for v in args.bbox.split(",")) if args.bbox else None

    def cb(name: str, detail: dict | None) -> None:
        mem = f"{_working_set_mb():7.0f} MB RSS" if _psutil_ok() else ""
        print(f"[{time.strftime('%H:%M:%S')}] {name:<26} {json.dumps(detail or {})[:120]} {mem}", flush=True)

    pre = GrdPreprocessor(args.scene_id,
                          Path(settings.scene_storage_dir) / "processed",
                          config=GrdConfig.from_settings(settings),
                          state_cb=cb)
    try:
        report = pre.run(zip_path, expected_bbox=bbox)
    except Exception as exc:  # noqa: BLE001
        print(f"PREPROCESSING FAILED: {exc}")
        return 2

    print("\n==== summary ====")
    print(json.dumps({
        "status": report["status"],
        "outputs": {k: v["outputs"] for k, v in report["outputs"].items()},
        "stats_linear": {k: v["stats_linear"] for k, v in report["outputs"].items()},
        "stats_db": {k: v["stats_db"] for k, v in report["outputs"].items()},
        "gcps": report["gcps"]["count"],
        "elapsed_s": report["elapsed_s"],
    }, indent=2))
    if _psutil_ok():
        print(f"peak-ish RSS: {_working_set_mb():.0f} MB")
    return 0


_PSUTIL = None
def _psutil_ok() -> bool:
    global _PSUTIL
    if _PSUTIL is None:
        try:
            import psutil
            _PSUTIL = psutil
        except ImportError:
            _PSUTIL = False
    return bool(_PSUTIL)


if __name__ == "__main__":
    raise SystemExit(main())
