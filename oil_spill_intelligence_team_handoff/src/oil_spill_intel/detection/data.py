"""Data loading and normalisation for paired SAR tiles."""
from __future__ import annotations

from pathlib import Path
import numpy as np


def robust_normalize(sar: np.ndarray) -> np.ndarray:
    """Channelwise percentile scaling without discarding original georeferencing elsewhere."""
    x = sar.astype(np.float32, copy=True)
    for channel in range(x.shape[0]):
        lo, hi = np.nanpercentile(x[channel], [1, 99])
        x[channel] = np.clip((x[channel] - lo) / max(hi - lo, 1e-6), 0, 1)
    return x


class SARSegmentationDataset:
    """NPZ dataset with `sar: CxHxW` and `mask: HxW` arrays."""
    def __init__(self, samples: list[Path]) -> None:
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int):  # type: ignore[no-untyped-def]
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("Install optional ML dependencies: pip install -e '.[ml]'") from exc
        data = np.load(self.samples[index])
        return torch.from_numpy(robust_normalize(data["sar"])), torch.from_numpy(data["mask"].astype(np.float32))[None, ...]
