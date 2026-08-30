"""DEVELOPMENT / DEMO SEED DATA.

These records exist purely so the UI can be developed and demonstrated
without real satellite data. They are marked `is_demo=True` everywhere they
are stored and served. They are NOT real oil spills and must never be
presented as such.

Values intentionally mirror the frontend's mock dataset
(src/lib/mock-data/) so switching API modes keeps the demo coherent.
"""

from __future__ import annotations

import logging
from datetime import datetime

from app.db.repository import SpillRepository
from app.domain.entities import SatelliteSceneRecord, SpillIncident, confidence_level

logger = logging.getLogger(__name__)


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def make_slick_ring(
    lon: float, lat: float, heading_deg: float,
    length_km: float, width_km: float, seed: int,
) -> list[list[float]]:
    """Deterministic irregular slick polygon — mirrors the frontend generator."""
    a = seed | 0

    def rand() -> float:
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = a
        t = ((t ^ (t >> 15)) * (1 | t)) & 0xFFFFFFFF
        t = ((t + (((t ^ (t >> 7)) * (61 | t)) & 0xFFFFFFFF)) & 0xFFFFFFFF) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    import math

    rad = math.radians(heading_deg)
    ux, uy = math.cos(rad), math.sin(rad)
    deg_lat = 1 / 111.0
    deg_lon = 1 / (111.0 * math.cos(math.radians(lat)))
    pts = []
    n = 16
    for i in range(n):
        theta = i / n * 2 * math.pi
        r_along = length_km / 2 * math.cos(theta)
        r_cross = width_km / 2 * math.sin(theta)
        j = 0.78 + rand() * 0.44
        ax = r_along * ux - r_cross * uy
        ay = r_along * uy + r_cross * ux
        pts.append([
            round(lon + ax * deg_lon * j, 5),
            round(lat + ay * deg_lat * j, 5),
        ])
    pts.append(pts[0])
    return pts


_SEED_SCENES: list[dict] = [
    dict(id="S1A_IW_GRDH_20260825T1820", platform="Sentinel-1A", acquisition_mode="IW",
         polarisation="VV + VH", acquired_at="2026-08-25T18:20:00+05:30",
         processed_at="2026-08-25T18:26:00+05:30",
         footprint=(70.5, 13.5, 75.0, 17.0), status="processed"),
    dict(id="S1A_IW_GRDH_20260825T1745", platform="Sentinel-1A", acquisition_mode="IW",
         polarisation="VV + VH", acquired_at="2026-08-25T17:45:00+05:30",
         processed_at="2026-08-25T17:51:00+05:30",
         footprint=(71.0, 19.0, 74.5, 21.5), status="processed"),
    dict(id="S1B_IW_GRDH_20260825T1638", platform="Sentinel-1B", acquisition_mode="IW",
         polarisation="VV + VH", acquired_at="2026-08-25T16:38:00+05:30",
         processed_at="2026-08-25T16:44:00+05:30",
         footprint=(79.5, 11.8, 83.0, 14.6), status="processed"),
    dict(id="S1B_IW_GRDH_20260825T1530", platform="Sentinel-1B", acquisition_mode="IW",
         polarisation="VV + VH", acquired_at="2026-08-25T15:30:00+05:30",
         processed_at="2026-08-25T15:36:00+05:30",
         footprint=(73.5, 8.2, 77.5, 10.9), status="processed"),
    dict(id="S1A_EW_GRDM_20260824T1840", platform="Sentinel-1A", acquisition_mode="EW",
         polarisation="HH + HV", acquired_at="2026-08-24T18:40:00+05:30",
         processed_at="2026-08-24T18:52:00+05:30",
         footprint=(69.5, 9.0, 74.0, 12.0), status="processed"),
    dict(id="S1B_EW_GRDM_20260825T1925", platform="Sentinel-1B", acquisition_mode="EW",
         polarisation="VV + VH", acquired_at="2026-08-25T19:25:00+05:30",
         processed_at=None,
         footprint=(85.0, 17.5, 89.5, 21.0), status="processing"),
    # Scenes referenced by incidents (acquisitions whose rasters are archived
    # in this demo dataset without being part of the live feed).
    dict(id="S1A_IW_GRDH_20260825T1422", platform="Sentinel-1A", acquisition_mode="IW",
         polarisation="VV + VH", acquired_at="2026-08-25T14:22:00+05:30",
         processed_at="2026-08-25T14:28:00+05:30",
         footprint=(84.5, 18.2, 88.0, 20.9), status="processed"),
    dict(id="S1B_IW_GRDH_20260824T2058", platform="Sentinel-1B", acquisition_mode="IW",
         polarisation="VV + VH", acquired_at="2026-08-24T20:58:00+05:30",
         processed_at="2026-08-24T21:05:00+05:30",
         footprint=(91.5, 10.4, 95.0, 13.1), status="processed"),
    dict(id="S1A_IW_GRDH_20260825T1205", platform="Sentinel-1A", acquisition_mode="IW",
         polarisation="VV + VH", acquired_at="2026-08-25T12:05:00+05:30",
         processed_at="2026-08-25T12:11:00+05:30",
         footprint=(68.2, 21.6, 71.7, 23.9), status="processed"),
    dict(id="S1A_IW_GRDH_20260824T1506", platform="Sentinel-1A", acquisition_mode="IW",
         polarisation="VV + VH", acquired_at="2026-08-24T15:06:00+05:30",
         processed_at="2026-08-24T15:12:00+05:30",
         footprint=(84.0, 16.8, 87.5, 19.5), status="processed"),
]

_SEED_INCIDENTS: list[dict] = [
    dict(id="IN-250825-001", confidence=0.914, area_km2=18.4, perimeter_km=21.6,
         lat=15.2965, lon=72.8456, heading=62, length_km=8.2, width_km=3.1,
         detected_at="2026-08-25T18:31:00+05:30", region="Arabian Sea",
         location_description="Arabian Sea · Off Maharashtra Coast",
         satellite="Sentinel-1A", scene_id="S1A_IW_GRDH_20260825T1820",
         status="completed", wind_speed_kts=9, estimated_volume_tons=42),
    dict(id="IN-250825-002", confidence=0.847, area_km2=7.2, perimeter_km=13.9,
         lat=20.108, lon=72.391, heading=118, length_km=4.9, width_km=2.0,
         detected_at="2026-08-25T17:52:00+05:30", region="Gulf of Khambhat",
         location_description="Gulf of Khambhat · Off Gujarat Coast",
         satellite="Sentinel-1A", scene_id="S1A_IW_GRDH_20260825T1745",
         status="completed", wind_speed_kts=12, estimated_volume_tons=18),
    dict(id="IN-250825-003", confidence=0.713, area_km2=3.8, perimeter_km=9.4,
         lat=13.204, lon=80.612, heading=205, length_km=3.6, width_km=1.5,
         detected_at="2026-08-25T16:44:00+05:30", region="Coromandel Coast",
         location_description="Bay of Bengal · Off Tamil Nadu Coast",
         satellite="Sentinel-1B", scene_id="S1B_IW_GRDH_20260825T1638",
         status="completed", wind_speed_kts=11, estimated_volume_tons=None),
    dict(id="IN-250825-004", confidence=0.689, area_km2=2.1, perimeter_km=6.7,
         lat=9.618, lon=75.824, heading=340, length_km=2.8, width_km=1.1,
         detected_at="2026-08-25T15:36:00+05:30", region="Malabar Coast",
         location_description="Arabian Sea · Off Kerala Coast",
         satellite="Sentinel-1B", scene_id="S1B_IW_GRDH_20260825T1530",
         status="review", wind_speed_kts=14, estimated_volume_tons=None),
    dict(id="IN-250825-005", confidence=0.552, area_km2=1.0, perimeter_km=4.1,
         lat=19.342, lon=86.418, heading=95, length_km=1.9, width_km=0.8,
         detected_at="2026-08-25T14:28:00+05:30", region="Northern Bay of Bengal",
         location_description="Bay of Bengal · Off Odisha Coast",
         satellite="Sentinel-1A", scene_id="S1A_IW_GRDH_20260825T1422",
         status="review", wind_speed_kts=16, estimated_volume_tons=None),
    dict(id="IN-250825-006", confidence=0.882, area_km2=11.6, perimeter_km=16.8,
         lat=22.574, lon=69.318, heading=45, length_km=6.4, width_km=2.6,
         detected_at="2026-08-25T12:14:00+05:30", region="Gulf of Kutch",
         location_description="Gulf of Kutch · Off Gujarat Coast",
         satellite="Sentinel-1A", scene_id="S1A_IW_GRDH_20260825T1205",
         status="completed", wind_speed_kts=8, estimated_volume_tons=31),
    dict(id="IN-250824-011", confidence=0.765, area_km2=5.4, perimeter_km=11.2,
         lat=11.632, lon=93.214, heading=150, length_km=4.2, width_km=1.8,
         detected_at="2026-08-24T21:05:00+05:30", region="Andaman Sea",
         location_description="Andaman Sea · Off Port Blair Approach",
         satellite="Sentinel-1B", scene_id="S1B_IW_GRDH_20260824T2058",
         status="completed", wind_speed_kts=10, estimated_volume_tons=None),
    dict(id="IN-250824-007", confidence=0.583, area_km2=1.7, perimeter_km=5.6,
         lat=10.512, lon=71.806, heading=280, length_km=2.4, width_km=1.0,
         detected_at="2026-08-24T18:47:00+05:30", region="Lakshadweep Sea",
         location_description="Lakshadweep Sea · East of Kavaratti",
         satellite="Sentinel-1A", scene_id="S1A_EW_GRDM_20260824T1840",
         status="review", wind_speed_kts=13, estimated_volume_tons=None),
    dict(id="IN-250824-003", confidence=0.821, area_km2=6.9, perimeter_km=12.4,
         lat=17.894, lon=85.562, heading=75, length_km=4.7, width_km=2.1,
         detected_at="2026-08-24T15:12:00+05:30", region="Northern Bay of Bengal",
         location_description="Bay of Bengal · Off Visakhapatnam",
         satellite="Sentinel-1A", scene_id="S1A_IW_GRDH_20260824T1506",
         status="completed", wind_speed_kts=11, estimated_volume_tons=None),
]


def build_demo_scenes() -> list[SatelliteSceneRecord]:
    scenes = []
    for s in _SEED_SCENES:
        scenes.append(
            SatelliteSceneRecord(
                id=s["id"],
                platform=s["platform"],
                sensor="SAR C-band",
                acquisition_mode=s["acquisition_mode"],
                polarisation=s["polarisation"],
                acquired_at=_dt(s["acquired_at"]),
                processed_at=_dt(s["processed_at"]) if s["processed_at"] else None,
                footprint=tuple(s["footprint"]),  # type: ignore[arg-type]
                status=s["status"],  # type: ignore[arg-type]
                image_path=None,
                is_demo=True,
            )
        )
    return scenes


def build_demo_incidents() -> list[SpillIncident]:
    incidents = []
    for idx, s in enumerate(_SEED_INCIDENTS):
        ring = make_slick_ring(
            s["lon"], s["lat"], s["heading"], s["length_km"], s["width_km"], 1000 + idx * 37
        )
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        incidents.append(
            SpillIncident(
                id=s["id"],
                scene_id=s["scene_id"],
                confidence=s["confidence"],
                area_km2=s["area_km2"],
                perimeter_km=s["perimeter_km"],
                centroid_lon=s["lon"],
                centroid_lat=s["lat"],
                geometry={"type": "Polygon", "coordinates": [ring]},
                bbox=(min(lons), min(lats), max(lons), max(lats)),
                detected_at=_dt(s["detected_at"]),
                region=s["region"],
                location_description=s["location_description"],
                satellite=s["satellite"],
                model_name="OilSpillNet",
                model_version="v1.0",
                status=s["status"],  # type: ignore[arg-type]
                wind_speed_kts=s["wind_speed_kts"],
                estimated_volume_tons=s["estimated_volume_tons"],
                is_demo=True,
            )
        )
    return incidents


def seed_demo_data(repo: SpillRepository, *, force: bool = False) -> int:
    """Insert demo scenes/incidents if the repository is empty (or force=True).

    Returns the number of incidents inserted.
    """
    if not force and repo.count_incidents() > 0:
        logger.info("Repository already contains data — skipping demo seed")
        return 0

    for sc in build_demo_scenes():
        repo.add_scene(sc)
    incidents = build_demo_incidents()
    for inc in incidents:
        repo.add_incident(inc)
    logger.warning("Seeded %d DEMO incidents (development data only)", len(incidents))
    return len(incidents)


__all__ = [
    "build_demo_incidents",
    "build_demo_scenes",
    "seed_demo_data",
    "confidence_level",
]
