"""AIS correlation engine — spatial/temporal filtering, vessel grouping, scoring.

This module consumes normalized AIS observations and a source estimate
(potential slick location/time) and produces ranked candidate vessels
with transparent attribution scores.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.domain.ais import (
    AisObservation,
    AisSearchWindow,
    AttributionResult,
    CandidateVessel,
    SourceEstimate,
)
from app.services.ais_provider import AISProvider


def build_search_window(
    source: SourceEstimate,
    settings: Settings,
) -> AisSearchWindow:
    """Construct an AIS search window from a source estimate and config."""
    radius_km = settings.ais_search_radius_km
    time_hours = settings.ais_time_window_hours

    # Approximate bbox from radius (1 degree lat ~ 111 km)
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * math.cos(math.radians(source.latitude)))

    return AisSearchWindow(
        bbox=(
            source.longitude - dlon,
            source.latitude - dlat,
            source.longitude + dlon,
            source.latitude + dlat,
        ),
        start_time=source.timestamp - timedelta(hours=time_hours),
        end_time=source.timestamp + timedelta(hours=time_hours),
        center_lat=source.latitude,
        center_lon=source.longitude,
        radius_km=radius_km,
        time_window_hours=time_hours,
    )


def geodesic_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate geodesic distance between two points using Haversine formula.

    Returns distance in kilometers.
    """
    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def spatial_filter(
    observations: list[AisObservation],
    source: SourceEstimate,
    radius_km: float,
) -> list[tuple[AisObservation, float]]:
    """Filter observations by geodesic distance from source.

    Returns list of (observation, distance_km) for observations within radius.
    """
    result = []
    for obs in observations:
        dist = geodesic_distance_km(source.latitude, source.longitude, obs.lat, obs.lon)
        if dist <= radius_km:
            result.append((obs, dist))
    return result


def temporal_filter(
    observations: list[tuple[AisObservation, float]],
    source_time: datetime,
    time_window_hours: float,
) -> list[tuple[AisObservation, float, float]]:
    """Filter observations by temporal proximity.

    Returns list of (observation, distance_km, time_diff_minutes).
    """
    window = timedelta(hours=time_window_hours)
    result = []
    for obs, dist in observations:
        diff = obs.timestamp - source_time
        diff_minutes = diff.total_seconds() / 60.0
        if abs(diff) <= window:
            result.append((obs, dist, diff_minutes))
    return result


def group_by_vessel(
    observations: list[tuple[AisObservation, float, float]],
) -> dict[str, list[tuple[AisObservation, float, float]]]:
    """Group filtered observations by MMSI."""
    groups: dict[str, list[tuple[AisObservation, float, float]]] = {}
    for obs, dist, diff in observations:
        groups.setdefault(obs.mmsi, []).append((obs, dist, diff))
    return groups


def compute_candidate_vessel(
    mmsi: str,
    obs_group: list[tuple[AisObservation, float, float]],
) -> CandidateVessel:
    """Compute candidate vessel metrics from grouped observations."""
    distances = [d for _, d, _ in obs_group]
    times = [t for _, _, t in obs_group]

    closest_idx = distances.index(min(distances))
    closest_obs, closest_dist, closest_time_diff = obs_group[closest_idx]

    timestamps = [o.timestamp for o, _, _ in obs_group]

    return CandidateVessel(
        mmsi=mmsi,
        vessel_name=closest_obs.vessel_name,
        imo=closest_obs.imo,
        vessel_type=closest_obs.vessel_type,
        observations=[o for o, _, _ in obs_group],
        number_of_observations=len(obs_group),
        closest_distance_km=round(closest_dist, 2),
        closest_timestamp=closest_obs.timestamp,
        closest_time_difference_minutes=round(closest_time_diff, 1),
        mean_distance_km=round(sum(distances) / len(distances), 2),
        first_observation=min(timestamps),
        last_observation=max(timestamps),
    )


def compute_attribution_scores(
    candidates: list[CandidateVessel],
    source: SourceEstimate,
    settings: Settings,
) -> list[CandidateVessel]:
    """Compute transparent attribution scores for candidate vessels.

    Scoring components (all configurable):
      - distance_score (50%): closer = higher score
      - time_score (30%): smaller time difference = higher score
      - track_consistency_score (20%): more observations = higher score

    The final attribution_score is a weighted sum, NOT a probability.
    """
    dist_weight = settings.ais_distance_weight
    time_weight = settings.ais_time_weight
    track_weight = settings.ais_track_weight

    max_dist = settings.ais_search_radius_km
    max_time = settings.ais_time_window_hours * 60  # convert to minutes

    for c in candidates:
        # Distance score: 1.0 at 0km, 0.0 at max radius
        distance_score = max(0.0, 1.0 - (c.closest_distance_km / max_dist))

        # Time score: 1.0 at 0 minutes, 0.0 at max window
        time_diff_abs = abs(c.closest_time_difference_minutes or max_time)
        time_score = max(0.0, 1.0 - (time_diff_abs / max_time))

        # Track consistency: based on number of observations (diminishing returns)
        # 1 obs = 0.3, 3 obs = 0.7, 6+ obs = ~1.0
        track_score = min(1.0, 0.3 + 0.15 * min(c.number_of_observations, 5))

        c.score_components = {
            "distance": round(distance_score, 3),
            "time": round(time_score, 3),
            "trackConsistency": round(track_score, 3),
        }

        c.attribution_score = round(
            dist_weight * distance_score
            + time_weight * time_score
            + track_weight * track_score,
            3,
        )

        # Quality flags
        if c.number_of_observations < 2:
            c.quality_flags.append("SINGLE_OBSERVATION")
        if c.closest_distance_km > max_dist * 0.7:
            c.quality_flags.append("LARGE_DISTANCE")
        if abs(c.closest_time_difference_minutes or 0) > max_time * 0.7:
            c.quality_flags.append("LARGE_TIME_DIFFERENCE")

        c.human_review_required = True  # always require human review

    # Sort by attribution_score descending
    candidates.sort(key=lambda c: c.attribution_score, reverse=True)
    return candidates


def analyze_attribution(
    incident_id: str,
    source: SourceEstimate,
    provider: AISProvider,
    settings: Settings,
    coverage_known: bool = True,
) -> AttributionResult:
    """Full attribution analysis pipeline.

    1. Build search window
    2. Query AIS provider
    3. Spatial filter
    4. Temporal filter
    5. Group by vessel
    6. Compute candidate metrics
    7. Score and rank
    8. Return AttributionResult
    """
    search_window = build_search_window(source, settings)

    # Query AIS
    observations = provider.query_positions(search_window)

    # Spatial filter
    spatial = spatial_filter(observations, source, settings.ais_search_radius_km)

    # Temporal filter
    filtered = temporal_filter(
        spatial, source.timestamp, settings.ais_time_window_hours
    )

    # Group by MMSI
    groups = group_by_vessel(filtered)

    # Build candidates
    candidates = [
        compute_candidate_vessel(mmsi, obs_list)
        for mmsi, obs_list in groups.items()
    ]

    # Score and rank
    scored = compute_attribution_scores(candidates, source, settings)

    return AttributionResult(
        incident_id=incident_id,
        search_window=search_window,
        coverage_known=coverage_known,
        provider=provider.name,
        dataset=provider.dataset,
        candidate_count=len(scored),
        candidates=scored,
        total_observations=len(observations),
        analyzed_at=datetime.now(timezone.utc),
        provenance={
            "provider": provider.name,
            "dataset": provider.dataset,
            "search_bbox": list(search_window.bbox),
            "search_start": search_window.start_time.isoformat(),
            "search_end": search_window.end_time.isoformat(),
            "search_radius_km": settings.ais_search_radius_km,
            "time_window_hours": settings.ais_time_window_hours,
            "total_ais_observations": len(observations),
            "filtered_observations": len(filtered),
            "candidate_vessels": len(scored),
            "scoring_weights": {
                "distance": settings.ais_distance_weight,
                "time": settings.ais_time_weight,
                "trackConsistency": settings.ais_track_weight,
            },
        },
    )
