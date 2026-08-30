"""India maritime Area-of-Interest configuration.

Development ships a documented bounding box around Indian maritime waters.
Production should point SAGARWATCH_INDIA_AOI_GEOJSON_PATH at an official
Indian EEZ / coastal boundary GeoJSON (single Polygon or MultiPolygon,
EPSG:4326); the AOI then uses true polygon intersection semantics.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# DEVELOPMENT bounding geometry for Indian maritime waters (Arabian Sea,
# Bay of Bengal, Gulf of Mannar, Andaman Sea approaches). Deliberately
# generous; replace with an official EEZ boundary for operational use.
INDIA_MARITIME_DEV_BBOX = (68.0, 6.0, 94.5, 24.5)


@dataclass
class AreaOfInterest:
    """Search area of interest.

    geometry: GeoJSON dict (Polygon/MultiPolygon, EPSG:4326) when an exact
        boundary is available; falls back to the bounding rectangle otherwise.
    bbox: (west, south, east, north) used for coarse catalogue pre-filtering.
    """

    bbox: tuple[float, float, float, float] = INDIA_MARITIME_DEV_BBOX
    geometry: dict | None = None
    name: str = "india-maritime-dev"
    source: str = "development-bbox"

    @classmethod
    def from_settings(
        cls,
        bbox_str: str | None = None,
        geojson_path: str | Path | None = None,
    ) -> "AreaOfInterest":
        bbox = INDIA_MARITIME_DEV_BBOX
        source = "development-bbox"
        if bbox_str:
            parts = tuple(float(v) for v in bbox_str.split(","))
            if len(parts) != 4:
                raise ValueError("AOI bbox must be west,south,east,north")
            bbox = parts  # type: ignore[assignment]
            source = "configured-bbox"

        geometry: dict | None = None
        if geojson_path:
            path = Path(geojson_path)
            if not path.exists():
                raise FileNotFoundError(f"AOI GeoJSON not found: {path}")
            doc = json.loads(path.read_text(encoding="utf-8"))
            geometry = doc.get("geometry") if doc.get("type") == "Feature" else doc
            if geometry is None or geometry.get("type") not in ("Polygon", "MultiPolygon"):
                raise ValueError("AOI GeoJSON must contain a Polygon/MultiPolygon")
            source = f"geojson:{path.name}"
            logger.info("Loaded AOI geometry from %s", path)

        return cls(bbox=bbox, geometry=geometry, source=source)  # type: ignore[arg-type]

    @property
    def _shape(self):
        import shapely.geometry

        if self.geometry is not None:
            return shapely.geometry.shape(self.geometry)
        w, s, e, n = self.bbox
        return shapely.geometry.box(w, s, e, n)

    def intersects_bbox(self, other: tuple[float, float, float, float]) -> bool:
        ow, os_, oe, on = other
        w, s, e, n = self.bbox
        return not (oe < w or ow > e or on < s or os_ > n)

    def intersects_geometry(self, geom_geojson: dict) -> bool:
        import shapely.geometry

        return self._shape.intersects(shapely.geometry.shape(geom_geojson))

    def describe(self) -> dict:
        return {
            "name": self.name,
            "source": self.source,
            "bbox": list(self.bbox),
            "polygon_defined": self.geometry is not None,
        }


@dataclass
class AoiRegistry:
    """Named AOIs; 'india' is always present."""

    areas: dict[str, AreaOfInterest] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.areas.setdefault("india", AreaOfInterest())

    def get(self, region: str | None) -> AreaOfInterest | None:
        if not region:
            return None
        return self.areas.get(region.strip().lower())
