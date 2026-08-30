"""MOCK / DEVELOPMENT oil-spill model adapter.

╔══════════════════════════════════════════════════════════════════╗
║  THIS IS NOT A TRAINED MODEL.                                    ║
║  Predictions are a deterministic image-processing heuristic      ║
║  (dark-region detector) used ONLY to exercise the pipeline       ║
║  while the real trained model is being developed.                ║
║  Its outputs must never be presented as real detections or       ║
║  scientific results.                                             ║
╚══════════════════════════════════════════════════════════════════╝

Heuristic: SAR oil slicks appear DARKER than the surrounding sea because
they dampen Bragg-scale capillary waves. The mock adapter simply maps
low normalized backscatter to high spill probability, then smooths the
field. This is a classic "dark spot detection" baseline — it also fires
on look-alikes (low-wind zones, biogenic films), which is exactly why a
trained model is needed.
"""

from __future__ import annotations

import logging
import time

import numpy as np

from app.config import Settings
from app.inference.base import (
    OilSpillModel,
    PreprocessResult,
    PredictionResult,
    SceneInput,
)

logger = logging.getLogger(__name__)


def _box_blur(arr: np.ndarray, iterations: int = 2) -> np.ndarray:
    """Simple separable box blur via cumulative shifts (no scipy needed)."""
    out = arr.astype(np.float32)
    for _ in range(iterations):
        padded = np.pad(out, 1, mode="edge")
        out = (
            padded[:-2, :-2] + padded[:-2, 1:-1] + padded[:-2, 2:]
            + padded[1:-1, :-2] + padded[1:-1, 1:-1] + padded[1:-1, 2:]
            + padded[2:, :-2] + padded[2:, 1:-1] + padded[2:, 2:]
        ) / 9.0
    return out


class MockOilSpillModel(OilSpillModel):
    """DEVELOPMENT-ONLY dark-spot heuristic.

    NOT A TRAINED MODEL. Clearly labeled mock: outputs are image-processing
    heuristics and must never be presented as real detections.
    """

    name = "MockOilSpillModel"
    version = "mock-0.1"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._loaded = False

    def load_model(self) -> None:
        # Nothing to load — heuristic needs no weights.
        logger.warning(
            "Using MOCK oil-spill model (development only). "
            "Outputs are heuristics, NOT trained-model predictions."
        )
        self._loaded = True

    def preprocess(self, scene_input: SceneInput) -> PreprocessResult:
        intensity = scene_input.intensity.astype(np.float32)
        finite = intensity[np.isfinite(intensity)]
        lo, hi = np.percentile(finite, [1.0, 99.0]) if finite.size else (0.0, 1.0)
        denom = (hi - lo) or 1.0
        normalized = np.clip((intensity - lo) / denom, 0.0, 1.0)
        return PreprocessResult(
            input_data=normalized,
            spatial_transform=scene_input.transform,
            crs=scene_input.crs,
            meta={"normalization": "percentile-1-99", "lo": float(lo), "hi": float(hi)},
        )

    def predict(self, data: PreprocessResult) -> PredictionResult:
        t0 = time.perf_counter()
        norm: np.ndarray = data.input_data

        finite = norm[np.isfinite(norm)]
        dark_cut = float(np.quantile(finite, 0.06)) if finite.size else 0.0

        # low backscatter => high spill probability; smooth into soft mask
        prob = np.clip((dark_cut - norm) / max(dark_cut, 1e-6), 0.0, 1.0)
        prob = _box_blur(prob, iterations=2)
        prob = np.clip(prob, 0.0, 1.0).astype(np.float32)

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return PredictionResult(
            probability_mask=prob,
            inference_time_ms=elapsed_ms,
            meta={
                "adapter": self.name,
                "adapter_kind": "MOCK_DEVELOPMENT_HEURISTIC",
                "dark_quantile": dark_cut,
            },
        )
