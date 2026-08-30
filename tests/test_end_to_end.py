from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
from pathlib import Path

from oil_spill_intel.attribution import rank_vessels
from oil_spill_intel.detection import PotentialSlickDetector
from oil_spill_intel.drift import ConstantForcing, EnsembleHindcaster
from oil_spill_intel.detection.train import _train_numpy_baseline


def test_detection_hindcast_and_ranking_contracts():
    sar = np.full((2, 64, 64), -18, dtype=np.float32); sar[:, 22:34, 12:45] = -30
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    detected = PotentialSlickDetector(threshold=0.75, min_pixels=20).predict("test", now, sar, {"bounds_lonlat": [72, 18, 73, 19], "pixel_area_km2": 0.01, "wind_speed_mps": 6, "wave_height_m": 1, "incidence_angle_deg": 32})
    assert detected.potential_slicks and detected.human_review_required
    point = tuple(detected.potential_slicks[0].centroid_lonlat)
    result = EnsembleHindcaster(ConstantForcing(east_current_mps=0.1), particles=80, iterations=2).infer(point, now, now - timedelta(hours=12), now - timedelta(hours=1), search_radius_km=20)
    assert result.source_centroid_lonlat is not None and result.human_review_required and result.estimated_age_hours is not None
    ais = pd.DataFrame([{"mmsi": "123", "timestamp": now - timedelta(hours=4), "lat": point[1], "lon": point[0], "vessel_type": "tanker"}])
    ranked = rank_vessels(ais, tuple(result.source_centroid_lonlat), now - timedelta(hours=12), now - timedelta(hours=1))
    assert ranked and ranked[0].rank == 1 and ranked[0].evidence_status.startswith("potential")


def test_portable_training_baseline(tmp_path: Path):
    sar = np.full((2, 32, 32), -18, dtype=np.float32); mask = np.zeros((32, 32), dtype=np.uint8); sar[:, 8:20, 8:20] = -30; mask[8:20, 8:20] = 1
    np.savez_compressed(tmp_path / "sample.npz", sar=sar, mask=mask)
    _train_numpy_baseline([tmp_path / "sample.npz"], tmp_path / "model.pt", epochs=1)
    result = PotentialSlickDetector(str(tmp_path / "model.npz"), threshold=0.5, min_pixels=20).predict("test", datetime(2026, 1, 1, tzinfo=timezone.utc), sar, {"bounds_lonlat": [72, 18, 73, 19], "wind_speed_mps": 6})
    assert result.potential_slicks and result.model_version == "numpy-logistic-v1"
