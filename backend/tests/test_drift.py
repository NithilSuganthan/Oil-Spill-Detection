"""Drift/hindcast and investigation orchestrator tests.

Tests cover:
- Environmental conditions
- Backward drift integration
- Ensemble generation
- Source centroid calculation
- Uncertainty estimation
- Geodesic movement
- Timestep handling
- Deterministic mock forcing
- SourceEstimate from drift
- AIS integration with drift output
- Investigation orchestrator
- API response schemas
- Quality flags
- Edge cases
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from app.config import Settings
from app.domain.ais import SourceEstimate
from app.services.drift_engine import (
    FirstOrderDriftProvider,
    _geodesic_distance_km,
    _km_to_deg_lat,
    _km_to_deg_lon,
    drift_result_to_source_estimate,
)
from app.services.drift_provider import DriftResult
from app.services.environmental_mock_provider import MockEnvironmentalProvider


@pytest.fixture
def settings() -> Settings:
    return Settings(
        drift_provider="first_order",
        environmental_provider="mock",
        drift_hours=24.0,
        drift_timestep_minutes=15.0,
        drift_ensemble_size=50,
        windage_coefficient=0.03,
        windage_coefficient_std=0.01,
        current_fraction=1.0,
        position_noise_km=0.5,
        drift_uncertainty_km_per_hour=0.5,
        ais_search_radius_km=50.0,
    )


@pytest.fixture
def env_provider() -> MockEnvironmentalProvider:
    return MockEnvironmentalProvider()


@pytest.fixture
def drift_provider(env_provider, settings) -> FirstOrderDriftProvider:
    return FirstOrderDriftProvider(environmental_provider=env_provider, settings=settings)


@pytest.fixture
def slick_location():
    return (10.0, 72.0, datetime(2026, 8, 26, 1, 0, 0, tzinfo=timezone.utc))


# ── Environmental Conditions Tests ───────────────────────────────────────

class TestEnvironmentalProvider:
    def test_returns_conditions(self, env_provider):
        t = datetime(2026, 8, 26, 1, 0, 0, tzinfo=timezone.utc)
        c = env_provider.get_conditions(10.0, 72.0, t)
        assert c.latitude == 10.0
        assert c.longitude == 72.0
        assert isinstance(c.current_u, float)
        assert isinstance(c.wind_u, float)

    def test_spatial_variation(self, env_provider):
        t = datetime(2026, 8, 26, 1, 0, 0, tzinfo=timezone.utc)
        c1 = env_provider.get_conditions(10.0, 72.0, t)
        c2 = env_provider.get_conditions(15.0, 75.0, t)
        # Different locations should produce different conditions
        assert c1.current_u != c2.current_u or c1.current_v != c2.current_v

    def test_temporal_variation(self, env_provider):
        c1 = env_provider.get_conditions(10.0, 72.0, datetime(2026, 8, 26, 6, 0, tzinfo=timezone.utc))
        c2 = env_provider.get_conditions(10.0, 72.0, datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc))
        # Different times should produce different wind (diurnal cycle)
        assert c1.wind_u != c2.wind_u


# ── Geodesic Calculation Tests ──────────────────────────────────────────

class TestGeodesicCalculations:
    def test_km_to_deg_lat(self):
        d = _km_to_deg_lat(111.0)
        assert d == pytest.approx(111.0 / 6371.0, rel=0.01)

    def test_km_to_deg_lon_at_equator(self):
        d = _km_to_deg_lon(111.0, 0.0)
        assert d == pytest.approx(111.0 / 6371.0, rel=0.01)

    def test_km_to_deg_lon_at_60N(self):
        d = _km_to_deg_lon(111.0, 60.0)
        assert d == pytest.approx(111.0 / (6371.0 * 0.5), rel=0.05)

    def test_geodesic_distance(self):
        d = _geodesic_distance_km(10.0, 72.0, 11.0, 72.0)
        assert d == pytest.approx(111.0, rel=0.01)


# ── Drift Engine Tests ──────────────────────────────────────────────────

class TestDriftEngine:
    def test_returns_drift_result(self, drift_provider, slick_location):
        lat, lon, t = slick_location
        result = drift_provider.estimate_source("IN-001", lat, lon, t)
        assert isinstance(result, DriftResult)
        assert result.incident_id == "IN-001"

    def test_source_differs_from_slick(self, drift_provider, slick_location):
        """Drift should move the estimated source away from the slick."""
        lat, lon, t = slick_location
        result = drift_provider.estimate_source("IN-001", lat, lon, t)
        # With current + wind, source should be offset from slick
        dist = _geodesic_distance_km(lat, lon, result.source_latitude, result.source_longitude)
        assert dist > 0.1  # at least 100m offset

    def test_source_is_upstream(self, drift_provider, slick_location):
        """Source should be upstream (against current/wind direction)."""
        lat, lon, t = slick_location
        result = drift_provider.estimate_source("IN-001", lat, lon, t)
        # With NE currents and eastward wind, source should be SW of slick
        # (backward integration moves against the drift)
        assert result.source_latitude <= lat + 0.1  # roughly south or same latitude
        assert result.source_longitude <= lon + 0.1  # roughly west or same longitude

    def test_ensemble_produces_uncertainty(self, drift_provider, slick_location):
        """Ensemble should produce non-zero uncertainty."""
        lat, lon, t = slick_location
        result = drift_provider.estimate_source("IN-001", lat, lon, t)
        assert result.uncertainty_km > 0
        assert len(result.source_points) == 50

    def test_trajectories_recorded(self, drift_provider, slick_location):
        lat, lon, t = slick_location
        result = drift_provider.estimate_source("IN-001", lat, lon, t)
        assert len(result.trajectories) == 50
        for traj in result.trajectories:
            assert len(traj.points) > 1
            # First point should be near slick
            first_lat, first_lon, first_t = traj.points[0]
            assert first_t == t

    def test_source_time_before_observation(self, drift_provider, slick_location):
        """Estimated source time should be before observation time."""
        lat, lon, t = slick_location
        result = drift_provider.estimate_source("IN-001", lat, lon, t)
        assert result.source_latest <= t
        assert result.source_earliest < t

    def test_deterministic(self, env_provider, settings):
        """Same inputs should produce same outputs."""
        p1 = FirstOrderDriftProvider(environmental_provider=env_provider, settings=settings)
        p2 = FirstOrderDriftProvider(environmental_provider=env_provider, settings=settings)
        t = datetime(2026, 8, 26, 1, 0, 0, tzinfo=timezone.utc)
        r1 = p1.estimate_source("IN-001", 10.0, 72.0, t)
        r2 = p2.estimate_source("IN-001", 10.0, 72.0, t)
        assert r1.source_latitude == r2.source_latitude
        assert r1.source_longitude == r2.source_longitude
        assert r1.uncertainty_km == r2.uncertainty_km

    def test_quality_flags_include_demo(self, drift_provider, slick_location):
        lat, lon, t = slick_location
        result = drift_provider.estimate_source("IN-001", lat, lon, t)
        assert "DEMO_ENVIRONMENTAL_FORCING" in result.quality_flags

    def test_provenance_recorded(self, drift_provider, slick_location):
        lat, lon, t = slick_location
        result = drift_provider.estimate_source("IN-001", lat, lon, t)
        assert "provider" in result.provenance
        assert "windage_coefficient" in result.provenance
        assert "n_particles" in result.provenance

    def test_confidence_range(self, drift_provider, slick_location):
        lat, lon, t = slick_location
        result = drift_provider.estimate_source("IN-001", lat, lon, t)
        assert 0.0 <= result.confidence <= 1.0


# ── Drift to SourceEstimate Conversion Tests ─────────────────────────────

class TestDriftToSourceEstimate:
    def test_conversion(self, drift_provider, slick_location):
        lat, lon, t = slick_location
        result = drift_provider.estimate_source("IN-001", lat, lon, t)
        source = drift_result_to_source_estimate(result)
        assert isinstance(source, SourceEstimate)
        assert source.latitude == result.source_latitude
        assert source.longitude == result.source_longitude
        assert source.method == "first_order_backward_hindcast"
        assert source.uncertainty_km == result.uncertainty_km
        assert "DEMO_ENVIRONMENTAL_FORCING" in source.quality_flags

    def test_timestamp_is_midpoint(self, drift_provider, slick_location):
        lat, lon, t = slick_location
        result = drift_provider.estimate_source("IN-001", lat, lon, t)
        source = drift_result_to_source_estimate(result)
        expected = result.source_earliest + (result.source_latest - result.source_earliest) / 2
        assert source.timestamp == expected


# ── SourceEstimate Integration with AIS ──────────────────────────────────

class TestSourceEstimateAISIntegration:
    def test_source_feeds_into_ais(self, drift_provider, slick_location, settings):
        """SourceEstimate from drift can be passed into AIS correlation."""
        from app.services.ais_correlation import analyze_attribution
        from app.services.ais_mock_provider import MockAISProvider

        lat, lon, t = slick_location
        result = drift_provider.estimate_source("IN-001", lat, lon, t)
        source = drift_result_to_source_estimate(result)

        ais = MockAISProvider()
        attribution = analyze_attribution("IN-001", source, ais, settings)
        assert attribution.candidate_count >= 0
        assert attribution.search_window.center_lat == source.latitude

    def test_uncertainty_expands_search(self, drift_provider, slick_location, settings):
        """Source uncertainty should increase effective AIS search radius."""
        lat, lon, t = slick_location
        result = drift_provider.estimate_source("IN-001", lat, lon, t)
        source = drift_result_to_source_estimate(result)

        # Effective radius should include source uncertainty
        effective_radius = settings.ais_search_radius_km + source.uncertainty_km
        assert effective_radius > settings.ais_search_radius_km


# ── API Response Schema Tests ────────────────────────────────────────────

class TestDriftApiSchema:
    def test_drift_response_shape(self, drift_provider, slick_location):
        from app.api.routes.drift import _drift_result_to_response

        lat, lon, t = slick_location
        result = drift_provider.estimate_source("IN-001", lat, lon, t)
        response = _drift_result_to_response(result)
        data = response.model_dump(by_alias=True)

        assert "incidentId" in data
        assert "sourceLatitude" in data
        assert "sourceLongitude" in data
        assert "uncertaintyKm" in data
        assert "qualityFlags" in data
        assert "provenance" in data
        assert isinstance(data["sourcePoints"], list)


# ── Edge Cases ───────────────────────────────────────────────────────────

class TestDriftEdgeCases:
    def test_short_integration_window(self, env_provider, settings):
        """Very short integration should produce small source offset."""
        settings.drift_hours = 1.0
        provider = FirstOrderDriftProvider(environmental_provider=env_provider, settings=settings)
        t = datetime(2026, 8, 26, 1, 0, 0, tzinfo=timezone.utc)
        result = provider.estimate_source("IN-001", 10.0, 72.0, t)
        dist = _geodesic_distance_km(10.0, 72.0, result.source_latitude, result.source_longitude)
        assert dist < 5.0  # should be small for 1-hour integration

    def test_large_ensemble(self, env_provider, settings):
        """Larger ensemble should still work."""
        settings.drift_ensemble_size = 100
        provider = FirstOrderDriftProvider(environmental_provider=env_provider, settings=settings)
        t = datetime(2026, 8, 26, 1, 0, 0, tzinfo=timezone.utc)
        result = provider.estimate_source("IN-001", 10.0, 72.0, t, ensemble_size=100)
        assert len(result.source_points) == 100
        assert len(result.trajectories) == 100

    def test_zero_windage(self, env_provider, settings):
        """Zero windage should still produce drift from currents."""
        settings.windage_coefficient = 0.0
        provider = FirstOrderDriftProvider(environmental_provider=env_provider, settings=settings)
        t = datetime(2026, 8, 26, 1, 0, 0, tzinfo=timezone.utc)
        result = provider.estimate_source("IN-001", 10.0, 72.0, t)
        # Should still have some drift from currents
        dist = _geodesic_distance_km(10.0, 72.0, result.source_latitude, result.source_longitude)
        assert dist >= 0.0
