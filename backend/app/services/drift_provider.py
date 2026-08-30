"""Drift provider abstraction.

All drift/hindcast implementations depend on this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DriftTrajectory:
    """A single particle trajectory from slick back to estimated source."""

    points: list[tuple[float, float, datetime]] = field(default_factory=list)
    # Each point: (latitude, longitude, timestamp)


@dataclass
class DriftResult:
    """Complete result of a drift/hindcast analysis."""

    incident_id: str
    method: str
    slick_latitude: float
    slick_longitude: float
    observation_time: datetime
    integration_hours: float
    timestep_minutes: float
    ensemble_size: int
    source_latitude: float          # ensemble centroid
    source_longitude: float         # ensemble centroid
    source_earliest: datetime       # earliest estimated release
    source_latest: datetime         # latest estimated release
    uncertainty_km: float           # spatial spread of ensemble
    uncertainty_hours: float        # temporal spread
    trajectories: list[DriftTrajectory] = field(default_factory=list)
    source_points: list[tuple[float, float]] = field(default_factory=list)
    confidence: float = 0.0
    quality_flags: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    analyzed_at: datetime | None = None


class DriftProvider(ABC):
    """Abstract base class for drift/hindcast providers."""

    name: str = "base"

    @abstractmethod
    def estimate_source(
        self,
        incident_id: str,
        slick_lat: float,
        slick_lon: float,
        observation_time: datetime,
        integration_hours: float = 24.0,
        timestep_minutes: float = 15.0,
        ensemble_size: int = 50,
    ) -> DriftResult:
        """Run backward drift hindcast to estimate source location/time.

        Args:
            incident_id: Incident identifier.
            slick_lat: Observed slick centroid latitude.
            slick_lon: Observed slick centroid longitude.
            observation_time: When the slick was observed.
            integration_hours: How far back to integrate.
            timestep_minutes: Integration timestep.
            ensemble_size: Number of ensemble particles.

        Returns:
            DriftResult with estimated source and uncertainty.
        """

    def close(self) -> None:
        """Release any resources."""
