"""Mock environmental provider — deterministic currents and winds.

Provides realistic-scale but synthetic environmental forcing for drift testing.
All data is clearly labeled DEMO. Never fabricate real environmental data.
"""

from __future__ import annotations

import math
from datetime import datetime

from app.services.environmental_provider import (
    EnvironmentalConditions,
    EnvironmentalProvider,
)


class MockEnvironmentalProvider(EnvironmentalProvider):
    """Deterministic mock environmental conditions for development.

    Generates spatially and temporally varying currents and winds
    that produce a physically interpretable drift pattern.
    """

    name = "mock"

    def get_conditions(
        self,
        lat: float,
        lon: float,
        timestamp: datetime,
    ) -> EnvironmentalConditions:
        """Return deterministic environmental conditions.

        Currents: weak northeastward flow (~0.15 m/s) with spatial variation.
        Winds: moderate eastward breeze (~5 m/s) with diurnal variation.
        """
        # Spatial variation: currents rotate slightly with latitude
        lat_factor = math.sin(math.radians(lat))  # Coriolis-like variation
        lon_factor = math.cos(math.radians(lon))

        # Temporal variation: wind has diurnal cycle
        hour = timestamp.hour + timestamp.minute / 60.0
        diurnal = math.sin(2 * math.pi * (hour - 6) / 24)  # peak at noon

        # Ocean current: ~0.1-0.2 m/s, generally northeastward
        current_u = 0.12 + 0.05 * lon_factor  # eastward component
        current_v = 0.08 + 0.03 * lat_factor  # northward component

        # Wind: ~4-6 m/s, predominantly eastward with diurnal variation
        wind_u = 5.0 + 1.5 * diurnal  # eastward
        wind_v = 1.0 + 0.5 * lat_factor  # slight northward

        return EnvironmentalConditions(
            latitude=lat,
            longitude=lon,
            timestamp=timestamp,
            current_u=current_u,
            current_v=current_v,
            wind_u=wind_u,
            wind_v=wind_v,
            wave_height=None,
            sea_surface_temp=None,
            provider="mock",
            dataset="deterministic_synthetic",
            spatial_resolution_deg=None,
            temporal_resolution_hours=None,
            environment_status="DEMO",
        )
