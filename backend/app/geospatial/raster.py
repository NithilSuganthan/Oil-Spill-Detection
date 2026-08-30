"""Raster I/O helpers (rasterio)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class RasterData:
    data: np.ndarray          # 2-D band
    transform: object         # rasterio.transform.Affine
    crs: object               # rasterio CRS
    meta: dict


def read_raster(path: str | Path, band: int = 1) -> RasterData:
    """Read a single-band SAR raster (e.g. calibrated GRD sigma0)."""
    import rasterio

    with rasterio.open(path) as src:
        data = src.read(band)
        return RasterData(
            data=data,
            transform=src.transform,
            crs=src.crs,
            meta={
                "width": src.width,
                "height": src.height,
                "dtype": src.dtypes[band - 1],
                "nodata": src.nodata,
            },
        )
