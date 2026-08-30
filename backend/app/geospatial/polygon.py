"""Binary mask -> vector polygons (in the raster's CRS).

Uses rasterio.features.shapes for exact, georeferenced contour extraction —
no pixel-coordinate guessing.
"""

from __future__ import annotations

import logging

import numpy as np
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

logger = logging.getLogger(__name__)


def mask_to_polygons(
    mask: np.ndarray,
    transform,
    *,
    min_area_px: int = 4,
) -> list[BaseGeometry]:
    """Extract connected-component polygons from a binary mask.

    Returns shapely geometries in the CRS implied by `transform`.
    """
    import rasterio.features

    if mask.dtype != np.uint8:
        mask = mask.astype(np.uint8)

    # Convert the pixel-count threshold into CRS square units.
    pixel_area = abs(transform.a * transform.e)
    min_area_crs = max(min_area_px * pixel_area, 1e-9)

    polygons: list[BaseGeometry] = []
    for geom, value in rasterio.features.shapes(mask, mask=mask.astype(bool), transform=transform):
        if value != 1:
            continue
        poly = shape(geom)
        if poly.area < min_area_crs:
            continue
        if not poly.is_valid:
            poly = poly.buffer(0)
            if poly.is_empty:
                continue
        polygons.append(poly)

    logger.debug("Extracted %d candidate polygons from mask", len(polygons))
    return polygons


def simplify_polygon(poly: BaseGeometry, tolerance_in_crs_units: float) -> BaseGeometry:
    """Light simplification to remove raster stair-steps."""
    simplified = poly.simplify(tolerance_in_crs_units, preserve_topology=True)
    return simplified if not simplified.is_empty else poly
