"""CRS handling and geodesic area/perimeter.

Area is computed with pyproj.Geod (WGS84 geodesic), NOT by multiplying
lat/lon degree deltas. This is correct at any latitude.
"""

from __future__ import annotations

from dataclasses import dataclass

from pyproj import CRS, Geod, Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

_GEOD = Geod(ellps="WGS84")


@dataclass
class PolygonMetrics:
    area_km2: float
    perimeter_km: float
    centroid_lon: float
    centroid_lat: float
    bbox: tuple[float, float, float, float]  # west, south, east, north


def reproject_geometry(geom: BaseGeometry, src_crs: object, dst_crs: object = "EPSG:4326") -> BaseGeometry:
    """Reproject a shapely geometry between CRSs."""
    transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    return shapely_transform(transformer.transform, geom)


def compute_metrics(poly_wgs84: BaseGeometry) -> PolygonMetrics:
    """Geodesic metrics for a WGS84 (EPSG:4326) polygon.

    Returns signed-area-corrected absolute values from pyproj.Geod —
    geodesically accurate for Indian waters (or anywhere on Earth).
    """
    area_m2, perimeter_m = _GEOD.geometry_area_perimeter(poly_wgs84)
    centroid = poly_wgs84.centroid
    minx, miny, maxx, maxy = poly_wgs84.bounds
    return PolygonMetrics(
        area_km2=abs(area_m2) / 1_000_000.0,
        perimeter_km=abs(perimeter_m) / 1000.0,
        centroid_lon=centroid.x,
        centroid_lat=centroid.y,
        bbox=(minx, miny, maxx, maxy),
    )


def crs_is_geographic(crs: object) -> bool:
    return CRS.from_user_input(crs).is_geographic
