"""First-order backward drift/hindcast engine.

Implements a physically interpretable surface drift model using:
  particle_velocity = ocean_current + windage × wind

Backward integration traces particles from the observed slick location
backward in time to estimate where/when the oil originated.

Ensemble approach: multiple particles with perturbed initial conditions
and forcing to estimate source uncertainty.

This is NOT a replacement for a high-fidelity operational oceanographic
forecast. It is a first-order approximation for source attribution.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.domain.ais import SourceEstimate
from app.services.drift_provider import DriftProvider, DriftResult, DriftTrajectory
from app.services.environmental_provider import EnvironmentalProvider


# Earth radius for approximate degree conversions
_EARTH_RADIUS_KM = 6371.0


def _km_to_deg_lat(km: float) -> float:
    return km / _EARTH_RADIUS_KM


def _km_to_deg_lon(km: float, lat: float) -> float:
    return km / (_EARTH_RADIUS_KM * math.cos(math.radians(lat)))


def _geodesic_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return _EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class FirstOrderDriftProvider(DriftProvider):
    """First-order backward drift hindcast using current + wind forcing.

    For each ensemble particle:
      1. Start at observed slick location
      2. At each timestep, retrieve environmental conditions
      3. Calculate drift velocity: v = current + windage × wind
      4. Move particle backward: position -= v × dt
      5. Add small random perturbation for ensemble spread

    The ensemble centroid becomes the estimated source location.
    Spatial/temporal spread becomes the uncertainty.
    """

    name = "first_order"

    def __init__(
        self,
        environmental_provider: EnvironmentalProvider,
        settings: Settings,
    ) -> None:
        self._env = environmental_provider
        self._settings = settings

    def estimate_source(
        self,
        incident_id: str,
        slick_lat: float,
        slick_lon: float,
        observation_time: datetime,
        integration_hours: float | None = None,
        timestep_minutes: float | None = None,
        ensemble_size: int | None = None,
    ) -> DriftResult:
        hours = integration_hours or self._settings.drift_hours
        dt_min = timestep_minutes or self._settings.drift_timestep_minutes
        n_particles = ensemble_size or self._settings.drift_ensemble_size

        dt_seconds = dt_min * 60.0
        n_steps = int(hours * 3600 / dt_seconds)

        # Base parameters
        base_windage = self._settings.windage_coefficient
        windage_std = self._settings.windage_coefficient_std
        current_frac = self._settings.current_fraction
        pos_noise_km = self._settings.position_noise_km
        unc_rate = self._settings.drift_uncertainty_km_per_hour

        # Generate ensemble random seeds for reproducibility
        rng = random.Random(42)

        trajectories: list[DriftTrajectory] = []
        source_points: list[tuple[float, float]] = []

        for p in range(n_particles):
            # Perturbed initial conditions
            lat = slick_lat + _km_to_deg_lat(rng.gauss(0, pos_noise_km))
            lon = slick_lon + _km_to_deg_lon(rng.gauss(0, pos_noise_km), lat)

            # Perturbed parameters
            windage = max(0.0, base_windage + rng.gauss(0, windage_std))
            cur_frac = max(0.5, current_frac + rng.gauss(0, 0.1))

            traj = DriftTrajectory()
            traj.points.append((lat, lon, observation_time))

            for step in range(n_steps):
                t = observation_time - timedelta(seconds=dt_seconds * (step + 1))

                # Get environmental conditions at current particle position
                conditions = self._env.get_conditions(lat, lon, t)

                # Drift velocity: current + windage × wind
                # Convert wind from m/s to an approximate surface drift contribution
                v_east = cur_frac * conditions.current_u + windage * conditions.wind_u
                v_north = cur_frac * conditions.current_v + windage * conditions.wind_v

                # Convert m/s to km per timestep
                dt_hours = dt_seconds / 3600.0
                dist_east_km = v_east * 3.6 * dt_hours  # m/s -> km/h -> km
                dist_north_km = v_north * 3.6 * dt_hours

                # Convert km to degrees
                dlat = _km_to_deg_lat(dist_north_km)
                dlon = _km_to_deg_lon(dist_east_km, lat)

                # Move backward: subtract (we're going back in time)
                lat -= dlat
                lon -= dlon

                # Add ensemble perturbation
                lat += _km_to_deg_lat(rng.gauss(0, pos_noise_km * 0.1))
                lon += _km_to_deg_lon(rng.gauss(0, pos_noise_km * 0.1), lat)

                traj.points.append((lat, lon, t))

            trajectories.append(traj)
            source_points.append((lat, lon))

        # Compute ensemble statistics
        src_lats = [p[0] for p in source_points]
        src_lons = [p[1] for p in source_points]
        centroid_lat = sum(src_lats) / len(src_lats)
        centroid_lon = sum(src_lons) / len(src_lons)

        # Uncertainty from ensemble spread
        distances = [_geodesic_distance_km(centroid_lat, centroid_lon, lat, lon)
                     for lat, lon in source_points]
        uncertainty_km = max(distances) if distances else 0.0

        # Add systematic uncertainty
        uncertainty_km += unc_rate * hours

        # Time uncertainty: particles were released over a window
        source_times = [traj.points[-1][2] for traj in trajectories]
        earliest = min(source_times)
        latest = max(source_times)
        uncertainty_hours = (latest - earliest).total_seconds() / 3600.0

        # Confidence: higher for smaller uncertainty relative to search radius
        spread_ratio = uncertainty_km / self._settings.ais_search_radius_km
        confidence = max(0.1, min(0.9, 1.0 - spread_ratio))

        # Quality flags
        if self._env.name == "real":
            flags = ["REAL_ENVIRONMENTAL_FORCING"]
        else:
            flags = ["DEMO_ENVIRONMENTAL_FORCING"]
        if uncertainty_km > 20:
            flags.append("LARGE_SOURCE_UNCERTAINTY")

        result = DriftResult(
            incident_id=incident_id,
            method="first_order_backward_hindcast",
            slick_latitude=slick_lat,
            slick_longitude=slick_lon,
            observation_time=observation_time,
            integration_hours=hours,
            timestep_minutes=dt_min,
            ensemble_size=n_particles,
            source_latitude=round(centroid_lat, 6),
            source_longitude=round(centroid_lon, 6),
            source_earliest=earliest,
            source_latest=latest,
            uncertainty_km=round(uncertainty_km, 2),
            uncertainty_hours=round(uncertainty_hours, 2),
            trajectories=trajectories,
            source_points=source_points,
            confidence=round(confidence, 3),
            quality_flags=flags,
            provenance={
                "provider": self.name,
                "environmental_provider": self._env.name,
                "windage_coefficient": base_windage,
                "current_fraction": current_frac,
                "position_noise_km": pos_noise_km,
                "n_steps": n_steps,
                "n_particles": n_particles,
            },
            analyzed_at=datetime.now(timezone.utc),
        )
        return result


def drift_result_to_source_estimate(result: DriftResult) -> SourceEstimate:
    """Convert a DriftResult into a SourceEstimate for AIS correlation."""
    return SourceEstimate(
        latitude=result.source_latitude,
        longitude=result.source_longitude,
        timestamp=result.source_earliest + (result.source_latest - result.source_earliest) / 2,
        uncertainty_km=result.uncertainty_km,
        uncertainty_hours=result.uncertainty_hours,
        method=result.method,
        confidence=result.confidence,
        quality_flags=list(result.quality_flags),
    )
