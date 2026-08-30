"""Region classification for the Indian maritime focus area.

Region names are IDENTICAL to INDIAN_REGIONS in src/lib/types.ts so the
frontend's region filter keeps working unchanged.
"""

from __future__ import annotations

# (region_name, west, south, east, north) — coarse assignment boxes, checked in order.
_REGION_BOXES: list[tuple[str, float, float, float, float]] = [
    ("Gulf of Kutch",           68.5, 22.0, 70.6, 23.5),
    ("Gulf of Khambhat",        71.5, 19.5, 73.2, 22.4),
    ("Konkan Coast",            72.5, 14.0, 74.5, 20.5),
    ("Malabar Coast",           73.5,  8.0, 76.5, 14.5),
    ("Lakshadweep Sea",         70.0,  7.0, 74.5, 12.5),
    ("Arabian Sea",             62.0,  5.0, 75.5, 24.0),
    ("Northern Bay of Bengal",  84.0, 16.0, 91.5, 22.5),
    ("Coromandel Coast",        79.5, 10.0, 84.5, 16.5),
    ("Andaman Sea",             90.5,  6.0, 98.0, 14.5),
    ("Bay of Bengal",           78.0,  4.0, 94.0, 24.0),
]


def classify_region(lon: float, lat: float) -> str:
    """Assign an Indian coastal/maritime region from a WGS84 position."""
    for name, w, s, e, n in _REGION_BOXES:
        if w <= lon <= e and s <= lat <= n:
            return name
    return "Arabian Sea" if lon < 78.0 else "Bay of Bengal"
