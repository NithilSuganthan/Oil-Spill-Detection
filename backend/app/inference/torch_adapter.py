"""PRODUCTION TORCH MODEL ADAPTER — TinyUNet SAR oil-spill segmentation.

Loads the trained checkpoint (sar_unet.pt) and runs fully-convolutional
tiled inference on real Sentinel-1 VV/VH linear sigma0 data.

This adapter implements OilSpillModel and is selected via MODEL_ADAPTER=torch.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

from app.config import Settings
from app.inference.base import (
    OilSpillModel,
    PreprocessResult,
    PredictionResult,
    SceneInput,
)

logger = logging.getLogger(__name__)


def _robust_normalize(sar: np.ndarray) -> np.ndarray:
    """Per-channel percentile [p1, p99] rescale to [0, 1].

    Identical to oil_spill_intel.detection.data.robust_normalize but
    inlined here to avoid import coupling with the src/ package.
    """
    x = sar.astype(np.float32, copy=True)
    for ch in range(x.shape[0]):
        finite = x[ch][np.isfinite(x[ch])]
        if finite.size == 0:
            continue
        lo, hi = np.percentile(finite, [1, 99])
        x[ch] = np.clip((x[ch] - lo) / max(hi - lo, 1e-6), 0, 1)
    return x


class TorchOilSpillModel(OilSpillModel):
    """Production TinyUNet adapter for Sentinel-1 SAR oil-spill segmentation.

    Loads checkpoint once, runs tiled fully-convolutional inference,
    blends overlapping tiles, and returns a probability mask.
    """

    name = "TinyUNet"
    version = "tiny-unet-v1"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = None
        self._device = None
        self._loaded = False

    def load_model(self) -> None:
        import torch
        from oil_spill_intel.detection.model import TinyUNet

        model_path = Path(self._settings.model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"Model checkpoint not found: {model_path}")

        device_str = self._settings.model_device
        if device_str == "auto":
            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self._device = torch.device(device_str)

        logger.info("Loading TinyUNet from %s onto %s", model_path, self._device)
        t0 = time.perf_counter()

        checkpoint = torch.load(model_path, map_location=self._device, weights_only=True)
        in_channels = checkpoint.get("in_channels", 2)
        base_channels = checkpoint.get("base_channels", 32)

        self._model = TinyUNet(in_channels=in_channels, base_channels=base_channels)
        self._model.load_state_dict(checkpoint["model_state"])
        self._model.to(self._device)
        self._model.eval()

        elapsed = time.perf_counter() - t0
        logger.info(
            "TinyUNet loaded in %.2fs — in_channels=%d, base_channels=%d, device=%s, "
            "model_version=%s, epoch=%s, val_dice=%.4f, val_iou=%.4f",
            elapsed, in_channels, base_channels, self._device,
            checkpoint.get("model_version", "?"),
            checkpoint.get("epoch", "?"),
            checkpoint.get("val_dice_f1", "?"),
            checkpoint.get("val_iou", "?"),
        )
        self._loaded = True

    def preprocess(self, scene_input: SceneInput) -> PreprocessResult:
        """Accept 2-channel VV/VH linear sigma0 and normalize.

        The scene_input.intensity must be [2, H, W] (VV channel 0, VH channel 1).
        If a single-band array is passed (legacy), it is stacked as [band, band].
        """
        import numpy as np

        intensity = scene_input.intensity
        if intensity.ndim == 2:
            # Single band — stack as [VV, VH] = [band, band]
            intensity = np.stack([intensity, intensity], axis=0)
            logger.warning("Single-band input; stacking as [VV, VH] = [band, band]")

        if intensity.shape[0] != 2:
            raise ValueError(
                f"Expected 2 channels (VV, VH), got {intensity.shape[0]}"
            )

        normalized = _robust_normalize(intensity)
        return PreprocessResult(
            input_data=normalized,
            spatial_transform=scene_input.transform,
            crs=scene_input.crs,
            meta={"normalization": "percentile-1-99", "channels": ["VV", "VH"]},
        )

    def predict(self, data: PreprocessResult) -> PredictionResult:
        """Run tiled inference and blend overlapping tiles into full probability mask."""
        import torch

        if not self._loaded or self._model is None:
            raise RuntimeError("Model not loaded — call load_model() first")

        t0 = time.perf_counter()
        sar = data.input_data  # [2, H, W] float32 normalized
        _, H, W = sar.shape

        tile_size = int(getattr(self._settings, "model_tile_size", 512))
        tile_stride = int(getattr(self._settings, "model_tile_stride", 384))

        # Accumulator for blending
        prob_sum = np.zeros((H, W), dtype=np.float64)
        weight_sum = np.zeros((H, W), dtype=np.float64)

        # Generate tile coordinates
        tiles = []
        for y0 in range(0, H, tile_stride):
            for x0 in range(0, W, tile_stride):
                y1 = min(y0 + tile_size, H)
                x1 = min(x0 + tile_size, W)
                tiles.append((y0, x0, y1, x1))

        logger.info(
            "Tiled inference: %d tiles (size=%d, stride=%d) on %dx%d image",
            len(tiles), tile_size, tile_stride, W, H,
        )

        # Create weight window (raised cosine) for blending
        def _blend_window(size: int) -> np.ndarray:
            """Raised cosine window for tile blending."""
            w = np.hanning(size * 2)[:size].astype(np.float64)
            # Avoid zero weights at edges
            w = np.maximum(w, 0.1)
            return w

        wx = _blend_window(tile_size)
        wy = _blend_window(tile_size)
        window_2d = wy[:, None] * wx[None, :]

        for i, (y0, x0, y1, x1) in enumerate(tiles):
            tile_h = y1 - y0
            tile_w = x1 - x0

            # Extract tile
            tile_sar = sar[:, y0:y1, x0:x1].astype(np.float32)

            # Run model
            inp = torch.from_numpy(tile_sar)[None, ...].to(self._device)
            with torch.no_grad():
                logits = self._model(inp)
                prob_tile = torch.sigmoid(logits).squeeze().cpu().numpy()

            # Apply blending window (crop to tile size in case of edge tiles)
            win = window_2d[:tile_h, :tile_w]
            prob_sum[y0:y1, x0:x1] += prob_tile * win
            weight_sum[y0:y1, x0:x1] += win

            if (i + 1) % 50 == 0:
                logger.info("  tile %d/%d done", i + 1, len(tiles))

        # Normalize
        weight_sum = np.maximum(weight_sum, 1e-8)
        prob_mask = (prob_sum / weight_sum).astype(np.float32)
        prob_mask = np.clip(prob_mask, 0.0, 1.0)

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(
            "Inference complete: %d tiles, %d ms, device=%s",
            len(tiles), elapsed_ms, self._device,
        )

        return PredictionResult(
            probability_mask=prob_mask,
            inference_time_ms=elapsed_ms,
            meta={
                "adapter": self.name,
                "device": str(self._device),
                "n_tiles": len(tiles),
                "tile_size": tile_size,
                "tile_stride": tile_stride,
                "prob_min": float(prob_mask.min()),
                "prob_max": float(prob_mask.max()),
                "prob_mean": float(prob_mask.mean()),
            },
        )
