"""AIS vessel correlation domain entities — pure Python, framework-free.

These entities represent normalized AIS observations, candidate vessels,
and attribution analysis results. The correlation engine and API layer
manipulate these objects directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AisObservation:
    """A single normalized AIS position observation.

    All providers must normalize their data into this schema.
    Optional fields are None when the source does not provide them.
    """

    mmsi: str
    timestamp: datetime
    lat: float
    lon: float
    sog: float | None = None        # speed over ground (knots)
    cog: float | None = None        # course over ground (degrees)
    heading: float | None = None    # true heading (degrees)
    vessel_type: str | None = None  # e.g. "Cargo", "Tanker", "Fishing"
    imo: str | None = None
    vessel_name: str | None = None
    navigation_status: str | None = None
    draft: float | None = None      # meters


@dataclass
class SourceEstimate:
    """Position/time estimate for the potential spill source.

    Derived from drift hindcast or direct slick observation.
    Designed for future drift-hindcast compatibility.
    """

    latitude: float
    longitude: float
    timestamp: datetime
    uncertainty_km: float = 50.0
    uncertainty_hours: float = 6.0
    method: str = "direct_observation"   # direct_observation | first_order_backward_hindcast
    confidence: float = 1.0              # 0..1, quality of the estimate
    quality_flags: list[str] = field(default_factory=list)


@dataclass
class AisSearchWindow:
    """Geographic and temporal search parameters for AIS queries."""

    bbox: tuple[float, float, float, float]  # west, south, east, north
    start_time: datetime
    end_time: datetime
    center_lat: float
    center_lon: float
    radius_km: float
    time_window_hours: float


@dataclass
class CandidateVessel:
    """A vessel identified as a potential source candidate.

    Aggregates all AIS observations for a single MMSI near the slick.
    """

    mmsi: str
    vessel_name: str | None = None
    imo: str | None = None
    vessel_type: str | None = None
    flag: str | None = None
    observations: list[AisObservation] = field(default_factory=list)
    number_of_observations: int = 0
    closest_distance_km: float = float("inf")
    closest_timestamp: datetime | None = None
    closest_time_difference_minutes: float | None = None
    mean_distance_km: float = 0.0
    first_observation: datetime | None = None
    last_observation: datetime | None = None
    attribution_score: float = 0.0
    score_components: dict[str, float] = field(default_factory=dict)
    quality_flags: list[str] = field(default_factory=list)
    human_review_required: bool = True


@dataclass
class AttributionResult:
    """Complete result of an AIS attribution analysis for one incident."""

    incident_id: str
    search_window: AisSearchWindow
    coverage_known: bool = True
    provider: str = "mock"
    dataset: str = ""
    candidate_count: int = 0
    candidates: list[CandidateVessel] = field(default_factory=list)
    total_observations: int = 0
    analyzed_at: datetime | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
