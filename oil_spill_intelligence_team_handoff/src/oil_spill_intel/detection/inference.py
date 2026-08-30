"""Native-resolution potential-slick inference with transparent quality signals."""
from __future__ import annotations

from datetime import datetime
from typing import Any
import numpy as np

from oil_spill_intel.contracts import DetectionResult, QualityFlag, SlickGeometry, iso
from .data import robust_normalize
from .quality import assess_observation_quality


def _components(mask: np.ndarray, min_pixels: int) -> list[np.ndarray]:
    """4-neighbour connected components without a mandatory SciPy dependency."""
    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool); groups: list[np.ndarray] = []
    for row, col in zip(*np.where(mask & ~seen)):
        if seen[row, col]: continue
        stack = [(int(row), int(col))]; seen[row, col] = True; points: list[tuple[int, int]] = []
        while stack:
            y, x = stack.pop(); points.append((y, x))
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True; stack.append((ny, nx))
        if len(points) >= min_pixels: groups.append(np.asarray(points))
    return groups


def _bbox_polygon(points: np.ndarray, bounds: list[float], height: int, width: int) -> tuple[list[list[float]], list[float]]:
    miny, minx = points.min(axis=0); maxy, maxx = points.max(axis=0)
    west, south, east, north = bounds
    def lon(x: float) -> float: return west + (east - west) * x / max(width - 1, 1)
    def lat(y: float) -> float: return north - (north - south) * y / max(height - 1, 1)
    poly = [[lon(minx), lat(miny)], [lon(maxx), lat(miny)], [lon(maxx), lat(maxy)], [lon(minx), lat(maxy)], [lon(minx), lat(miny)]]
    return poly, [lon(float(points[:, 1].mean())), lat(float(points[:, 0].mean()))]


class PotentialSlickDetector:
    """Model wrapper. A trained PyTorch model is optional; demo mode is explicit."""
    def __init__(self, model_path: str | None = None, verifier_model_path: str | None = None, threshold: float = 0.5, min_pixels: int = 32) -> None:
        self.threshold, self.min_pixels = threshold, min_pixels
        self.model: Any | None = None; self.numpy_model: dict[str, np.ndarray] | None = None; self.model_version = "heuristic-demo-not-for-deployment"
        if model_path:
            if model_path.lower().endswith(".npz"):
                loaded = np.load(model_path); self.numpy_model = {key: loaded[key] for key in loaded.files}; self.model_version = str(self.numpy_model.get("model_version", "numpy-logistic-v1"))
            else:
                import torch
                from .model import TinyUNet
                checkpoint = torch.load(model_path, map_location="cpu", weights_only=True)
                self.model = TinyUNet(checkpoint.get("in_channels", 2)); self.model.load_state_dict(checkpoint["model_state"]); self.model.eval()
                self.model_version = checkpoint.get("model_version", "tiny-unet-v1")
        self.verifier = None
        if verifier_model_path:
            from .classifier import SARChipVerifier
            self.verifier = SARChipVerifier.load(verifier_model_path)

    def _probabilities(self, sar: np.ndarray) -> np.ndarray:
        x = robust_normalize(sar)
        if self.model is not None:
            import torch
            with torch.no_grad(): return torch.sigmoid(self.model(torch.from_numpy(x)[None, ...])).squeeze().numpy()
        if self.numpy_model is not None:
            features = x.reshape(x.shape[0], -1).T
            logits = ((features - self.numpy_model["mean"]) / self.numpy_model["std"]) @ self.numpy_model["weights"] + float(self.numpy_model["bias"])
            return (1 / (1 + np.exp(-np.clip(logits, -30, 30)))).reshape(x.shape[1:])
        # Explicit visual-baseline only; the trained model path must be used in production.
        vv = x[0]
        local_darkness = np.clip(1 - vv, 0, 1)
        return local_darkness

    def predict(self, scene_id: str, acquired_at: datetime, sar: np.ndarray, metadata: dict[str, Any]) -> DetectionResult:
        if sar.ndim != 3: raise ValueError("SAR must have shape [channels, height, width].")
        probability = self._probabilities(sar)
        look_alike_risk, flags = assess_observation_quality(metadata.get("wind_speed_mps"), metadata.get("wave_height_m"), metadata.get("incidence_angle_deg"))
        groups = _components(probability >= self.threshold, self.min_pixels)
        bounds = metadata.get("bounds_lonlat", [0.0, 0.0, 1.0, 1.0]); height, width = probability.shape
        pixel_km2 = float(metadata.get("pixel_area_km2", 0.0001))
        slicks: list[SlickGeometry] = []
        verifier_scores: list[float] = []
        for group in groups:
            polygon, centroid = _bbox_polygon(group, bounds, height, width)
            slicks.append(SlickGeometry(polygon, len(group) * pixel_km2, len(group), centroid))
            if self.verifier is not None:
                miny, minx = group.min(axis=0); maxy, maxx = group.max(axis=0)
                chip = (robust_normalize(sar)[0, miny:maxy + 1, minx:maxx + 1] * 255).astype(np.uint8)
                from PIL import Image
                chip = np.asarray(Image.fromarray(chip).resize((128, 128)), dtype=np.uint8)
                verifier_scores.append(self.verifier.predict_proba(chip))
        if not slicks:
            flags.append(QualityFlag("no_potential_slick", "info", "No region crossed the configured potential-slick threshold."))
        raw_confidence = float(probability[probability >= self.threshold].mean()) if slicks else 0.0
        if verifier_scores:
            flags.append(QualityFlag("real_sar_verifier", "info", f"CSIRO-trained SAR candidate verifier score: {float(np.mean(verifier_scores)):.3f}."))
        verifier_confidence = float(np.mean(verifier_scores)) if verifier_scores else 1.0
        confidence = round(max(0.0, raw_confidence * verifier_confidence * (1 - 0.45 * look_alike_risk)), 4)
        return DetectionResult(scene_id, iso(acquired_at), slicks, confidence, look_alike_risk, flags, model_version=self.model_version)
