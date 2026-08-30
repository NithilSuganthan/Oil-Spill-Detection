"""Mock AIS provider — deterministic test data for development.

Creates realistic vessel trajectories around a test potential slick.
All data is clearly synthetic. Never mix with real AIS data.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from app.domain.ais import AisObservation, AisSearchWindow
from app.services.ais_provider import AISProvider

# ── DEMO vessel definitions ─────────────────────────────────────────────
# Each vessel has a fixed track (list of (lat, lon, hours_offset)) relative
# to the slick center.  The mock provider interpolates positions along these
# tracks and assigns realistic MMSI / identity fields.

DEMO_VESSELS = [
    {
        "mmsi": "987654321",
        "vessel_name": "PACIFIC CARRIER",
        "imo": "9876543",
        "vessel_type": "Cargo",
        "flag": "IND",
        # Approaches within ~3 km of slick, right at observation time
        "track": [
            (0.040, -0.050, -4.0),   # 4h before, 4.4 km NW
            (0.025, -0.030, -2.0),   # 2h before, 2.9 km NW
            (0.010, -0.015, -0.5),   # 30min before, 1.2 km N
            (0.003, -0.003,  0.0),   # at observation time, ~0.4 km (CLOSEST)
            (-0.005, 0.008,  0.5),   # 30min after, 0.9 km E
            (-0.015, 0.020,  2.0),   # 2h after, 2.3 km SE
            (-0.030, 0.040,  4.0),   # 4h after, 4.9 km SE
        ],
    },
    {
        "mmsi": "987654322",
        "vessel_name": "ARABIAN TRADER",
        "imo": "9876544",
        "vessel_type": "Tanker",
        "flag": "LKA",
        # Passes ~12 km away, within time window
        "track": [
            (0.100, -0.020, -5.0),
            (0.080,  0.010, -3.0),
            (0.060,  0.040, -1.0),
            (0.040,  0.070,  1.0),
            (0.020,  0.100,  3.0),
            (0.000,  0.130,  5.0),
        ],
    },
    {
        "mmsi": "987654323",
        "vessel_name": "COASTAL FISHER",
        "imo": None,
        "vessel_type": "Fishing",
        "flag": "IND",
        # Nearby spatially but outside strongest temporal window
        "track": [
            (0.030,  0.020, -10.0),
            (0.025,  0.025, -8.0),
            (0.020,  0.030, -6.0),
            (0.018,  0.032, -4.0),
            (0.015,  0.035, -2.0),
            (0.012,  0.038,  0.0),
        ],
    },
    {
        "mmsi": "987654324",
        "vessel_name": "Distant Voyager",
        "imo": "9876546",
        "vessel_type": "Bulk Carrier",
        "flag": "SGP",
        # Far away — should be filtered out by spatial filter
        "track": [
            (0.500, -0.300, -3.0),
            (0.520, -0.280, -1.0),
            (0.540, -0.260,  1.0),
            (0.560, -0.240,  3.0),
        ],
    },
]


def _interpolate_track(
    track: list[tuple[float, float, float]],
    target_offset_hours: float,
) -> tuple[float, float]:
    """Linearly interpolate lat/lon at a given hour offset along the track."""
    if target_offset_hours <= track[0][2]:
        return track[0][0], track[0][1]
    if target_offset_hours >= track[-1][2]:
        return track[-1][0], track[-1][1]
    for i in range(len(track) - 1):
        lat0, lon0, t0 = track[i]
        lat1, lon1, t1 = track[i + 1]
        if t0 <= target_offset_hours <= t1:
            frac = (target_offset_hours - t0) / (t1 - t0) if t1 != t0 else 0.0
            return lat0 + frac * (lat1 - lat0), lon0 + frac * (lon1 - lon0)
    return track[-1][0], track[-1][1]


class MockAISProvider(AISProvider):
    """Deterministic mock AIS provider for development and testing.

    Generates synthetic vessel positions around a given slick location.
    """

    name = "mock"
    dataset = "DEMO AIS — not real data"

    def query_positions(
        self,
        search_window: AisSearchWindow,
    ) -> list[AisObservation]:
        """Generate mock AIS observations within the search window."""
        observations: list[AisObservation] = []

        # Slick observation time is the midpoint of the search window
        t_mid = search_window.start_time + (
            search_window.end_time - search_window.start_time
        ) / 2

        for vessel in DEMO_VESSELS:
            for lat_offset, lon_offset, hour_offset in vessel["track"]:
                obs_time = t_mid + timedelta(hours=hour_offset)
                obs_lat = search_window.center_lat + lat_offset
                obs_lon = search_window.center_lon + lon_offset

                # Spatial filter: check against bbox (with margin)
                w, s, e, n = search_window.bbox
                if not (s <= obs_lat <= n and w <= obs_lon <= e):
                    continue

                # Temporal filter
                if not (search_window.start_time <= obs_time <= search_window.end_time):
                    continue

                observations.append(AisObservation(
                    mmsi=vessel["mmsi"],
                    timestamp=obs_time,
                    lat=obs_lat,
                    lon=obs_lon,
                    sog=_estimate_sog(vessel["track"], hour_offset),
                    cog=_estimate_cog(vessel["track"], hour_offset),
                    heading=_estimate_cog(vessel["track"], hour_offset),
                    vessel_type=vessel["vessel_type"],
                    imo=vessel.get("imo"),
                    vessel_name=vessel.get("vessel_name"),
                    navigation_status="Under way using engine",
                    draft=None,
                ))

        return observations

    def get_vessel(self, vessel_id: str) -> dict | None:
        """Return vessel identity for a known demo MMSI."""
        for v in DEMO_VESSELS:
            if v["mmsi"] == vessel_id:
                return {
                    "mmsi": v["mmsi"],
                    "shipname": v["vessel_name"],
                    "imo": v.get("imo"),
                    "vessel_type": v["vessel_type"],
                    "flag": v.get("flag"),
                }
        return None


def _estimate_sog(track: list[tuple[float, float, float]], hour_offset: float) -> float:
    """Estimate speed over ground from track segment (knots approximation)."""
    lat, lon = _interpolate_track(track, hour_offset)
    lat2, lon2 = _interpolate_track(track, hour_offset + 0.1)
    # Rough approximation: 1 degree lat ~ 111 km
    dlat = (lat2 - lat) * 111.0
    dlon = (lon2 - lon) * 111.0 * math.cos(math.radians(lat))
    dist_km = math.sqrt(dlat**2 + dlon**2)
    return round(dist_km / 0.1, 1)  # km per 0.1 hour -> knots approx


def _estimate_cog(track: list[tuple[float, float, float]], hour_offset: float) -> float:
    """Estimate course over ground from track segment (degrees)."""
    lat, lon = _interpolate_track(track, hour_offset)
    lat2, lon2 = _interpolate_track(track, hour_offset + 0.1)
    dlat = lat2 - lat
    dlon = lon2 - lon
    if dlat == 0 and dlon == 0:
        return 0.0
    angle = math.degrees(math.atan2(dlon, dlat))  # bearing from north
    return round(angle % 360, 1)
