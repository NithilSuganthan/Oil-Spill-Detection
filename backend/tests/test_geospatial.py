"""Geospatial post-processing tests: polygon extraction, CRS/georeferencing,
area calculation (geodesic), and confidence computation."""

from __future__ import annotations

import numpy as np
import pytest
from rasterio.transform import from_origin
from shapely.geometry import Polygon, box

from app.geospatial.area import compute_metrics, crs_is_geographic, reproject_geometry
from app.geospatial.mask import morphological_cleanup, threshold_mask
from app.geospatial.polygon import mask_to_polygons, simplify_polygon


def _blob_mask(height=100, width=120) -> np.ndarray:
    yy, xx = np.mgrid[0:height, 0:width]
    ellipse = ((xx - 60) / 20.0) ** 2 + ((yy - 50) / 10.0) ** 2
    return (ellipse < 1.0).astype(np.uint8)


# ---------------------------------------------------------------- threshold
def test_threshold_mask():
    prob = np.array([[0.1, 0.6], [0.9, 0.5]])
    mask = threshold_mask(prob, 0.5)
    assert mask.tolist() == [[False, True], [True, True]]


def test_morphological_cleanup_removes_specks():
    mask = np.zeros((20, 20), dtype=np.uint8)
    mask[5:15, 5:15] = 1
    mask[1, 1] = 1                      # isolated speck
    cleaned = morphological_cleanup(mask, close_iterations=1, open_iterations=1)
    assert cleaned[1, 1] == 0           # speck removed by opening
    assert cleaned[10, 10] == 1         # core blob survives


# ------------------------------------------------------- polygon extraction
def test_mask_to_polygons_georeferencing():
    # UTM-like grid: origin (500000 E, 4000000 N), 40 m pixels
    transform = from_origin(500000.0, 4000000.0, 40.0, 40.0)
    polys = mask_to_polygons(_blob_mask(), transform, min_area_px=4)
    assert len(polys) == 1

    poly = polys[0]
    minx, miny, maxx, maxy = poly.bounds
    # Blob centre at pixel (60, 50) => world (500000 + 60*40 + 20, 4000000 - 50*40 - 20)
    expected_x = 500000 + 60 * 40
    expected_y = 4000000 - 50 * 40
    assert minx < expected_x < maxx
    assert miny < expected_y < maxy


def test_mask_to_polygons_ignores_tiny_components():
    mask = _blob_mask()
    mask[2:4, 2:4] = 1                  # 4 px component — at threshold
    transform = from_origin(0.0, 1000.0, 10.0, 10.0)
    polys = mask_to_polygons(mask, transform, min_area_px=5)
    assert len(polys) == 1              # tiny one filtered out


def test_reproject_geometry_changes_coords():
    poly = box(220000.0, 1048000.0, 222000.0, 1050000.0)  # UTM 43N metres
    wgs = reproject_geometry(poly, "EPSG:32643", "EPSG:4326")
    lon_min, lat_min, lon_max, lat_max = wgs.bounds
    # Arabian Sea region of UTM 43N zone → lon ~ 66-73, lat ~ 9-10
    assert 60 < lon_min < 75
    assert 8 < lat_min < 11


# ------------------------------------------------------------ area (geodesic)
def test_area_geodesic_known_polygon():
    """0.1° x 0.1° box near 15°N should be ≈ 111.3 km × 107.7 km × cos? ..."""
    poly = box(72.80, 14.95, 72.90, 15.05)  # 0.1° x 0.1° centred ~15°N
    metrics = compute_metrics(poly)

    north_m = 11092.0                   # ~0.1° of latitude in metres
    south_m = 11130.0 * 0               # unused; compute from geodesic bounds:
    del south_m
    # analytic expectation: width ≈ 0.1° * 107,700 m/deg @15°N, height ≈ 0.1° * 110,900 m/deg
    expected_area_km2 = (0.1 * 107.7) * (0.1 * 110.9)   # ≈ 119.4 km²
    assert expected_area_km2 * 0.98 < metrics.area_km2 < expected_area_km2 * 1.02
    assert 0 < metrics.perimeter_km < 60
    assert metrics.centroid_lon == pytest.approx(72.85, abs=0.01)
    assert metrics.centroid_lat == pytest.approx(15.0, abs=0.01)
    assert metrics.bbox[0] == pytest.approx(72.80)


def test_area_not_degree_multiplication():
    """Same-degree box near the equator vs 25°N must differ (geodesic check)."""
    equator = compute_metrics(box(70.0, 0.05, 70.2, 0.15))
    north = compute_metrics(box(70.0, 24.05, 70.2, 24.15))
    # identical degree dimensions but different real-world areas
    assert equator.area_km2 > north.area_km2
    assert abs(equator.area_km2 - north.area_km2) / equator.area_km2 > 0.05


def test_crs_helpers():
    assert crs_is_geographic("EPSG:4326")
    assert not crs_is_geographic("EPSG:32643")


def test_simplify_preserves_topology():
    poly = Polygon([(0, 0), (1, 0.001), (2, 0), (2, 2), (0, 2)])
    simplified = simplify_polygon(poly, tolerance_in_crs_units=0.05)
    assert simplified.is_valid
    assert not simplified.is_empty
