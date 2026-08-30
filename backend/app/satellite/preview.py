"""Web-friendly SAR preview generation.

Produces a lightweight PNG from a (preprocessed) GeoTIFF without serving the
raw product. Percentile-stretched to uint8 grayscale; written with GDAL's
PNG driver so no image library beyond rasterio is required.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

MAX_PREVIEW_DIM = 1024


def generate_preview_png(
    source: str | Path,
    dest: str | Path,
    *,
    max_dim: int = MAX_PREVIEW_DIM,
    low_pct: float = 2.0,
    high_pct: float = 98.0,
) -> Path:
    """Create a downscaled, contrast-stretched PNG preview of a SAR raster."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.shutil import copy as rio_copy  # noqa: F401 — kept explicit

    src_path = str(source)
    with rasterio.open(src_path) as src:
        scale = max(src.width, src.height) / float(max_dim)
        out_height = max(int(src.height / scale), 1)
        out_width = max(int(src.width / scale), 1)

        data = src.read(
            1,
            out_shape=(out_height, out_width),
            resampling=Resampling.average,
        ).astype(np.float32)

    finite = data[np.isfinite(data)]
    if finite.size == 0:
        raise ValueError(f"Preview source {src_path} has no finite pixels")
    lo, hi = np.percentile(finite, [low_pct, high_pct])
    denom = (hi - lo) or 1.0
    stretched = np.clip((data - lo) / denom, 0.0, 1.0)
    stretched[~np.isfinite(stretched)] = 0.0
    gray = (stretched * 255.0).astype(np.uint8)

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "PNG",
        "width": out_width,
        "height": out_height,
        "count": 1,
        "dtype": "uint8",
    }
    with rasterio.open(dest, "w", **profile) as dst:
        dst.write(gray, 1)
    logger.info("Preview written: %s (%dx%d)", dest, out_width, out_height)
    return dest
