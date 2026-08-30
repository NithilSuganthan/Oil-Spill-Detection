"""Synthetic end-to-end run for integration testing without external datasets."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import numpy as np
import pandas as pd

from oil_spill_intel.attribution import rank_vessels
from oil_spill_intel.detection import PotentialSlickDetector
from oil_spill_intel.drift import ConstantForcing, EnsembleHindcaster


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--output-dir", type=Path, default=Path("demo_output")); args = parser.parse_args(); args.output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(4); sar = rng.normal(-18, 2, (2, 128, 128)).astype(np.float32); yy, xx = np.ogrid[:128, :128]; slick = ((xx - 72) / 25) ** 2 + ((yy - 55) / 8) ** 2 < 1; sar[0, slick] = -29
    observed_at = datetime(2026, 8, 25, 8, tzinfo=timezone.utc)
    detection = PotentialSlickDetector(threshold=0.72, min_pixels=30).predict("synthetic-scene-001", observed_at, sar, {"bounds_lonlat": [72.5, 18.0, 73.5, 19.0], "pixel_area_km2": 0.01, "wind_speed_mps": 6.0, "wave_height_m": 1.0, "incidence_angle_deg": 34})
    observed = tuple(detection.potential_slicks[0].centroid_lonlat) if detection.potential_slicks else (73.0, 18.5)
    hindcast = EnsembleHindcaster(ConstantForcing(east_current_mps=0.18, north_current_mps=0.08, east_wind_mps=4), particles=300, iterations=4).infer(observed, observed_at, observed_at - timedelta(hours=24), observed_at - timedelta(hours=2), search_radius_km=35)
    detection.estimated_age_hours = hindcast.estimated_age_hours
    rows = []
    for mmsi, lon, lat, kind in [("111000111", observed[0] - 0.08, observed[1] - 0.03, "tanker"), ("222000222", observed[0] + 0.38, observed[1] + 0.31, "fishing"), ("333000333", observed[0] - 0.15, observed[1] + 0.07, "cargo")]:
        for hours in range(-28, 1, 2): rows.append({"mmsi": mmsi, "timestamp": observed_at + timedelta(hours=hours), "lon": lon + hours * 0.003, "lat": lat + hours * 0.001, "sog": 11, "cog": 90, "vessel_type": kind})
    ranking = rank_vessels(pd.DataFrame(rows), tuple(hindcast.source_centroid_lonlat), datetime.fromisoformat(hindcast.source_time_window[0].replace("Z", "+00:00")), datetime.fromisoformat(hindcast.source_time_window[1].replace("Z", "+00:00")))
    (args.output_dir / "detection.json").write_text(json.dumps(detection.to_dict(), indent=2), encoding="utf-8")
    (args.output_dir / "hindcast.json").write_text(json.dumps(hindcast.to_dict(), indent=2), encoding="utf-8")
    (args.output_dir / "vessel_ranking.json").write_text(json.dumps([x.to_dict() for x in ranking], indent=2), encoding="utf-8")
    np.savez_compressed(args.output_dir / "synthetic_sar_scene.npz", sar=sar, mask=slick.astype(np.uint8))
    print(f"Wrote integration artifacts to {args.output_dir}")


if __name__ == "__main__":
    main()
