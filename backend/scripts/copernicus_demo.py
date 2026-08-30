"""Controlled Copernicus Data Space development demo.

Flow:
    1. Search REAL Sentinel-1 GRD scenes over the India maritime AOI.
    2. Print discovered metadata.
    3. Select ONE scene (--index).
    4. Stream-download ONLY that scene.
    5. Generate a lightweight PNG preview.
    6. Persist the scene metadata (+ artifacts) so the API can serve it.

Safety rails:
    * hard result cap via --limit (default 5)
    * exactly one scene is downloaded per run
    * requires SATELLITE_PROVIDER=copernicus and CDSE credentials

Usage:
    python scripts/copernicus_demo.py                       # search + pick interactively
    python scripts/copernicus_demo.py --list                # search only
    python scripts/copernicus_demo.py --index 0             # download scene #0
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.db.session import create_repository
from app.satellite.aoi import AreaOfInterest
from app.satellite.factory import create_satellite_provider
from app.satellite.pipeline import _resolve_raster_source
from app.satellite.preview import generate_preview_png
from app.satellite.providers.base import SceneQuery


def _print_scene(idx: int, s) -> None:
    print(f"[{idx}] {s.id}")
    print(f"     platform      : {s.platform}")
    print(f"     product       : {s.product_name} ({s.product_type})")
    print(f"     acquired      : {s.acquired_at}")
    print(f"     processed     : {s.processed_at}")
    print(f"     orbit         : {s.orbit_state} abs={s.absolute_orbit} rel={s.relative_orbit}")
    print(f"     polarisation  : {s.polarisation}  mode={s.acquisition_mode}")
    print(f"     size (advert) : {(s.file_size_bytes or 0) / 1e6:.1f} MB")
    print(f"     footprint bbox: {s.footprint}")
    print(f"     product_id    : {s.product_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5, help="max catalogue results (hard cap)")
    parser.add_argument("--days", type=int, default=10, help="search window length in days")
    parser.add_argument("--bbox", type=str, default=None, help="override AOI: west,south,east,north")
    parser.add_argument("--list", action="store_true", help="search only, download nothing")
    parser.add_argument("--index", type=int, default=None, help="download exactly this result index")
    parser.add_argument("--yes", action="store_true", help="assume yes at confirmation")
    args = parser.parse_args()

    settings = get_settings()
    provider = create_satellite_provider(settings)
    info = provider.info()
    print(f"provider: {info.name} (is_real={info.is_real}) — {info.description}")

    aoi = AreaOfInterest.from_settings(
        bbox_str=args.bbox or settings.india_aoi_bbox,
        geojson_path=settings.india_aoi_geojson_path or None,
    )
    print(f"AOI: {aoi.describe()}")

    end = datetime.now(timezone.utc)
    query_start = end - timedelta(days=args.days)
    limit = min(args.limit, max(1, settings.catalogue_query_limit))
    scenes = provider.search_scenes(
        SceneQuery(start=query_start, end=end, bbox=aoi.bbox, limit=limit),
        aoi,
    )
    if not scenes:
        print("No Sentinel-1 GRD scenes found for this AOI/time window.")
        return 1

    print(f"\nDiscovered {len(scenes)} Sentinel-1 GRD scenes "
          f"({query_start:%Y-%m-%d} .. {end:%Y-%m-%d}):\n")
    for i, s in enumerate(scenes):
        _print_scene(i, s)

    if args.list:
        print("\n--list given: no downloads performed.")
        return 0

    index = args.index
    if index is None:
        raw = input(f"\nDownload which scene? [0-{len(scenes) - 1}] (empty = abort): ").strip()
        if not raw.isdigit():
            print("Aborted — nothing was downloaded.")
            return 0
        index = int(raw)
    if not 0 <= index < len(scenes):
        print(f"Index {index} out of range — nothing downloaded.")
        return 2

    scene = scenes[index]
    size_mb = (scene.file_size_bytes or 0) / 1e6
    if not args.yes:
        answer = input(f"About to download {scene.id} (~{size_mb:.0f} MB). Proceed? [y/N]: ")
        if answer.strip().lower() != "y":
            print("Aborted.")
            return 0

    from app.satellite.storage import create_storage
    from app.storage_keys import preview_key_for, product_key_for

    storage = create_storage(settings)
    key = product_key_for(scene.id, mock=False)
    stored = provider.download_scene(scene, storage)
    print(f"downloaded -> {stored.path or stored.url} ({stored.size_bytes / 1e6:.1f} MB)")
    scene.image_path = stored.path or stored.url
    scene.file_size_bytes = stored.size_bytes

    # lightweight preview straight from the archive (decimated read)
    preview_key = preview_key_for(scene.id)
    try:
        src = _resolve_raster_source(storage.get_path(key))
        generate_preview_png(src, storage.get_path(preview_key))
        scene.preview_path = storage.get_url(preview_key)
        print(f"preview    -> {storage.get_path(preview_key)}")
    except Exception as exc:  # noqa: BLE001 — preview must never kill ingestion
        print(f"preview generation skipped: {exc}")

    repo = create_repository(settings)
    scene.status = "discovered"
    repo.add_scene(scene)
    print(f"persisted scene {scene.id} (status=DISCOVERED).")
    print("Start the API and POST /api/v1/satellite/scenes/"
          f"{scene.id}/process to run the pipeline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
