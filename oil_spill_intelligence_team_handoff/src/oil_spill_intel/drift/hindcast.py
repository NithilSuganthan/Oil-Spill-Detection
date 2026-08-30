"""Forward-iterative ensemble source localisation (BAKTRAK-inspired baseline)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
import math
import numpy as np

from oil_spill_intel.contracts import HindcastParticle, HindcastResult, QualityFlag, iso

KM_PER_LAT_DEGREE = 111.32


class ForcingProvider(Protocol):
    def velocity_mps(self, lon: float, lat: float, when: datetime) -> tuple[float, float]: ...


@dataclass(slots=True)
class ConstantForcing:
    """Test/demo forcing. Replace with validated gridded current/wind data."""
    east_current_mps: float = 0.0
    north_current_mps: float = 0.0
    east_wind_mps: float = 0.0
    north_wind_mps: float = 0.0
    windage: float = 0.03

    def velocity_mps(self, lon: float, lat: float, when: datetime) -> tuple[float, float]:
        return self.east_current_mps + self.windage * self.east_wind_mps, self.north_current_mps + self.windage * self.north_wind_mps


def _move(lon: float, lat: float, east_m: float, north_m: float) -> tuple[float, float]:
    return lon + east_m / (KM_PER_LAT_DEGREE * 1000 * max(math.cos(math.radians(lat)), 0.1)), lat + north_m / (KM_PER_LAT_DEGREE * 1000)


def _distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    x = (a[0] - b[0]) * KM_PER_LAT_DEGREE * math.cos(math.radians((a[1] + b[1]) / 2)); y = (a[1] - b[1]) * KM_PER_LAT_DEGREE
    return math.hypot(x, y)


class EnsembleHindcaster:
    def __init__(self, forcing: ForcingProvider, particles: int = 1200, iterations: int = 5, seed: int = 7) -> None:
        self.forcing, self.particles, self.iterations, self.rng = forcing, particles, iterations, np.random.default_rng(seed)

    def _forward(self, lon: float, lat: float, released: datetime, observed_at: datetime, step_minutes: int) -> tuple[float, float]:
        now = released
        while now < observed_at:
            dt = min(timedelta(minutes=step_minutes), observed_at - now)
            east, north = self.forcing.velocity_mps(lon, lat, now)
            lon, lat = _move(lon, lat, east * dt.total_seconds(), north * dt.total_seconds())
            now += dt
        return lon, lat

    def infer(self, observed_lonlat: tuple[float, float], observed_at: datetime, earliest_release: datetime, latest_release: datetime, search_radius_km: float = 60.0, target_radius_km: float = 5.0, step_minutes: int = 30) -> HindcastResult:
        if observed_at.tzinfo is None: observed_at = observed_at.replace(tzinfo=timezone.utc)
        if earliest_release.tzinfo is None: earliest_release = earliest_release.replace(tzinfo=timezone.utc)
        if latest_release.tzinfo is None: latest_release = latest_release.replace(tzinfo=timezone.utc)
        if not earliest_release < latest_release <= observed_at: raise ValueError("Expected earliest < latest <= observation time.")
        parents: list[tuple[float, float, datetime, float]] = []
        center = observed_lonlat; radius = search_radius_km
        all_successes: list[tuple[float, float, datetime, float]] = []
        for _ in range(self.iterations):
            candidates: list[tuple[float, float, datetime, float]] = []
            for i in range(self.particles):
                if parents:
                    plon, plat, ptime, _ = parents[i % len(parents)]
                    bearing = self.rng.uniform(0, 2 * math.pi); distance = abs(self.rng.normal(radius * 0.35, radius * 0.18))
                    lon, lat = _move(plon, plat, math.cos(bearing) * distance * 1000, math.sin(bearing) * distance * 1000)
                    release = ptime + timedelta(hours=float(self.rng.normal(0, 2)))
                    release = min(max(release, earliest_release), latest_release)
                else:
                    bearing = self.rng.uniform(0, 2 * math.pi); distance = radius * math.sqrt(self.rng.random())
                    lon, lat = _move(center[0], center[1], math.cos(bearing) * distance * 1000, math.sin(bearing) * distance * 1000)
                    release = earliest_release + (latest_release - earliest_release) * float(self.rng.random())
                final = self._forward(lon, lat, release, observed_at, step_minutes)
                distance_km = _distance_km(final, observed_lonlat); score = math.exp(-distance_km / max(target_radius_km, 0.1))
                candidates.append((lon, lat, release, distance_km))
            candidates.sort(key=lambda x: x[3]); parents = candidates[: max(32, self.particles // 20)]
            all_successes.extend(x for x in parents if x[3] <= target_radius_km)
            radius = max(2.0, radius * 0.55)
        accepted = all_successes or parents[: min(100, len(parents))]
        weights = np.asarray([math.exp(-x[3] / max(target_radius_km, 0.1)) for x in accepted]); weights /= weights.sum()
        lon = float(sum(w * x[0] for w, x in zip(weights, accepted))); lat = float(sum(w * x[1] for w, x in zip(weights, accepted)))
        uncertainty = float(np.sqrt(sum(w * _distance_km((x[0], x[1]), (lon, lat)) ** 2 for w, x in zip(weights, accepted))))
        particles = [HindcastParticle(x[0], x[1], iso(x[2]), x[3], math.exp(-x[3] / max(target_radius_km, 0.1))) for x in accepted]
        estimated_age = float(sum(w * (observed_at - x[2]).total_seconds() / 3600 for w, x in zip(weights, accepted)))
        flags = [QualityFlag("ensemble_source_estimate", "warning", "Output is a probabilistic model result and requires human review plus independent validation."), QualityFlag("forcing_adapter_required", "warning", "Use a validated gridded wind/current provider for operational hindcasting.")]
        return HindcastResult(iso(observed_at), list(observed_lonlat), [lon, lat], [iso(min(x[2] for x in accepted)), iso(max(x[2] for x in accepted))], particles, {"provider": type(self.forcing).__name__, "particles_per_iteration": self.particles, "iterations": self.iterations}, uncertainty, flags, estimated_age)
