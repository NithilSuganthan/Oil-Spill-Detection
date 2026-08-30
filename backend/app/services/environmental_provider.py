"""Environmental data provider abstraction.

Provides ocean current and wind conditions for drift modeling.
All drift providers depend on this abstraction — never on concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class EnvironmentalConditions:
    """Environmental conditions at a single point and time."""

    latitude: float
    longitude: float
    timestamp: datetime
    current_u: float = 0.0   # eastward current velocity (m/s)
    current_v: float = 0.0   # northward current velocity (m/s)
    wind_u: float = 0.0      # eastward wind velocity (m/s) at 10m height
    wind_v: float = 0.0      # northward wind velocity (m/s) at 10m height
    wave_height: float | None = None
    sea_surface_temp: float | None = None
    # Provenance fields
    provider: str = "unknown"
    dataset: str = ""
    spatial_resolution_deg: float | None = None
    temporal_resolution_hours: float | None = None
    environment_status: str = "UNKNOWN"  # REAL, DEMO, CREDENTIALS_REQUIRED, UNAVAILABLE


class EnvironmentalProvider(ABC):
    """Abstract base class for environmental data providers."""

    name: str = "base"

    @abstractmethod
    def get_conditions(
        self,
        lat: float,
        lon: float,
        timestamp: datetime,
    ) -> EnvironmentalConditions:
        """Get environmental conditions at a point and time.

        Args:
            lat: Latitude (EPSG:4326)
            lon: Longitude (EPSG:4326)
            timestamp: Time of interest

        Returns:
            EnvironmentalConditions with current/wind data.
        """

    def close(self) -> None:
        """Release any resources."""
