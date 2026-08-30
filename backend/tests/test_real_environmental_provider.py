"""Unit tests for RealEnvironmentalProvider.

These tests cover:
- Bilinear interpolation accuracy
- Temporal interpolation
- Cache preparation
- Boundary handling
- Provider name / provenance
- Error handling (missing credentials, missing cache)
- Deterministic drift with fixture data
- Mock provider regression

Live external API tests are marked with @pytest.mark.live and are NOT
required for the normal test suite.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.config import Settings
from app.services.drift_engine import FirstOrderDriftProvider
from app.services.environmental_mock_provider import MockEnvironmentalProvider


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_fake_grids(
    lats: np.ndarray,
    lons: np.ndarray,
    times: list[datetime],
) -> dict[datetime, np.ndarray]:
    """Create fake environmental grids for testing interpolation.

    Currents increase with latitude and longitude.
    Winds have a simple sinusoidal pattern.
    """
    grids: dict[datetime, np.ndarray] = {}
    for t in times:
        grid = np.zeros((len(lats), len(lons), 2), dtype=np.float64)
        for i, lat in enumerate(lats):
            for j, lon in enumerate(lons):
                # Currents: uo increases with lat, vo increases with lon
                grid[i, j, 0] = 0.1 + 0.01 * lat  # uo (eastward)
                grid[i, j, 1] = 0.05 + 0.005 * lon  # vo (northward)
                # Winds: u10 has sinusoidal pattern, v10 is constant
                hour_offset = (t - times[0]).total_seconds() / 3600.0
                grid[i, j, 0] += 5.0 * math.sin(2 * math.pi * hour_offset / 24)
                grid[i, j, 1] += 3.0
        grids[t] = grid
    return grids


# ── Bilinear interpolation tests ─────────────────────────────────────────


class TestBilinearInterpolation:
    """Test bilinear spatial interpolation from cached grids."""

    def test_exact_grid_point(self):
        """Interpolation at exact grid point returns exact value."""
        from app.services.environmental_real_provider import RealEnvironmentalProvider

        provider = RealEnvironmentalProvider.__new__(RealEnvironmentalProvider)
        lats = np.array([15.0, 15.25, 15.5, 15.75])
        lons = np.array([72.5, 72.75, 73.0, 73.25])
        provider._cache_lats = lats
        provider._cache_lons = lons

        grid = np.zeros((4, 4, 2), dtype=np.float64)
        grid[1, 2, 0] = 0.15  # uo at lat=15.25, lon=73.0
        grid[1, 2, 1] = 0.08  # vo at lat=15.25, lon=73.0

        uo, vo = provider._bilinear_at(grid, 15.25, 73.0)
        assert abs(uo - 0.15) < 1e-10
        assert abs(vo - 0.08) < 1e-10

    def test_interpolated_value_between_points(self):
        """Interpolation between grid points produces weighted average."""
        from app.services.environmental_real_provider import RealEnvironmentalProvider

        provider = RealEnvironmentalProvider.__new__(RealEnvironmentalProvider)
        lats = np.array([15.0, 15.5])
        lons = np.array([72.5, 73.0])
        provider._cache_lats = lats
        provider._cache_lons = lons

        grid = np.zeros((2, 2, 2), dtype=np.float64)
        grid[0, 0, 0] = 0.0  # bottom-left
        grid[0, 1, 0] = 0.2  # bottom-right
        grid[1, 0, 0] = 0.4  # top-left
        grid[1, 1, 0] = 0.6  # top-right

        # Midpoint should be average of all four
        uo, _ = provider._bilinear_at(grid, 15.25, 72.75)
        expected = (0.0 + 0.2 + 0.4 + 0.6) / 4.0
        assert abs(uo - expected) < 1e-10

    def test_clamping_at_boundary(self):
        """Query outside grid bounds is clamped to nearest edge."""
        from app.services.environmental_real_provider import RealEnvironmentalProvider

        provider = RealEnvironmentalProvider.__new__(RealEnvironmentalProvider)
        lats = np.array([15.0, 15.5])
        lons = np.array([72.5, 73.0])
        provider._cache_lats = lats
        provider._cache_lons = lons

        grid = np.zeros((2, 2, 2), dtype=np.float64)
        grid[:, :, 0] = 0.1
        grid[:, :, 1] = 0.2

        # Query way outside bounds
        uo, vo = provider._bilinear_at(grid, 20.0, 80.0)
        assert abs(uo - 0.1) < 1e-10
        assert abs(vo - 0.2) < 1e-10

    def test_interpolation_preserves_units(self):
        """Interpolated values are in m/s (no unit conversion)."""
        from app.services.environmental_real_provider import RealEnvironmentalProvider

        provider = RealEnvironmentalProvider.__new__(RealEnvironmentalProvider)
        lats = np.array([15.0, 15.5])
        lons = np.array([72.5, 73.0])
        provider._cache_lats = lats
        provider._cache_lons = lons

        grid = np.zeros((2, 2, 2), dtype=np.float64)
        grid[:, :, 0] = 0.15  # 0.15 m/s eastward current
        grid[:, :, 1] = 0.08  # 0.08 m/s northward current

        uo, vo = provider._bilinear_at(grid, 15.25, 72.75)
        # Values should be in m/s, not modified
        assert 0.0 < uo < 1.0  # reasonable ocean current range
        assert 0.0 < vo < 1.0


# ── Temporal interpolation tests ─────────────────────────────────────────


class TestTemporalInterpolation:
    """Test temporal interpolation between cached timesteps."""

    def test_exact_timestep_match(self):
        """Exact timestep returns grid value without interpolation."""
        from app.services.environmental_real_provider import RealEnvironmentalProvider

        provider = RealEnvironmentalProvider.__new__(RealEnvironmentalProvider)
        lats = np.array([15.0, 15.5])
        lons = np.array([72.5, 73.0])
        provider._cache_lats = lats
        provider._cache_lons = lons

        t0 = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 8, 19, 13, 0, tzinfo=timezone.utc)
        provider._cache_timesteps = [t0, t1]

        grid0 = np.ones((2, 2, 2), dtype=np.float64) * 0.1
        grid1 = np.ones((2, 2, 2), dtype=np.float64) * 0.2
        provider._currents_grids = {t0: grid0, t1: grid1}
        provider._winds_grids = {t0: grid0, t1: grid1}
        provider._prepared = True

        conditions = provider.get_conditions(15.25, 72.75, t0)
        assert abs(conditions.current_u - 0.1) < 1e-10

    def test_midpoint_interpolation(self):
        """Midpoint between two timesteps returns average."""
        from app.services.environmental_real_provider import RealEnvironmentalProvider

        provider = RealEnvironmentalProvider.__new__(RealEnvironmentalProvider)
        lats = np.array([15.0, 15.5])
        lons = np.array([72.5, 73.0])
        provider._cache_lats = lats
        provider._cache_lons = lons

        t0 = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 8, 19, 14, 0, tzinfo=timezone.utc)
        provider._cache_timesteps = [t0, t1]

        grid0 = np.ones((2, 2, 2), dtype=np.float64) * 0.1
        grid1 = np.ones((2, 2, 2), dtype=np.float64) * 0.3
        provider._currents_grids = {t0: grid0, t1: grid1}
        provider._winds_grids = {t0: grid0, t1: grid1}
        provider._prepared = True

        # Midpoint
        t_mid = datetime(2026, 8, 19, 13, 0, tzinfo=timezone.utc)
        conditions = provider.get_conditions(15.25, 72.75, t_mid)
        assert abs(conditions.current_u - 0.2) < 1e-10


# ── Cache preparation tests ──────────────────────────────────────────────


class TestCachePreparation:
    """Test cache preparation and validation."""

    def test_empty_timesteps_raises(self):
        """Empty timesteps list raises ValueError."""
        from app.services.environmental_real_provider import RealEnvironmentalProvider

        provider = RealEnvironmentalProvider.__new__(RealEnvironmentalProvider)
        with pytest.raises(ValueError, match="timesteps list must not be empty"):
            provider.prepare_cache((72.0, 15.0, 73.0, 16.0), [])

    def test_get_conditions_without_cache_raises(self):
        """get_conditions before prepare_cache raises RuntimeError."""
        from app.services.environmental_real_provider import RealEnvironmentalProvider

        provider = RealEnvironmentalProvider.__new__(RealEnvironmentalProvider)
        provider._prepared = False
        with pytest.raises(RuntimeError, match="Cache not prepared"):
            provider.get_conditions(15.0, 72.5, datetime.now(timezone.utc))


# ── Credential validation tests ──────────────────────────────────────────


class TestCredentialValidation:
    """Test that missing credentials are caught at init time."""

    def test_missing_cmems_username_raises(self):
        """Missing CMEMS username raises ValueError."""
        from app.services.environmental_real_provider import RealEnvironmentalProvider

        with pytest.raises(ValueError, match="CMEMS credentials required"):
            RealEnvironmentalProvider(
                cmems_username="",
                cmems_password="pass",
                cds_api_key="key",
            )

    def test_missing_cmems_password_raises(self):
        """Missing CMEMS password raises ValueError."""
        from app.services.environmental_real_provider import RealEnvironmentalProvider

        with pytest.raises(ValueError, match="CMEMS credentials required"):
            RealEnvironmentalProvider(
                cmems_username="user",
                cmems_password="",
                cds_api_key="key",
            )

    def test_missing_cds_api_key_raises(self):
        """Missing CDS API key raises ValueError."""
        from app.services.environmental_real_provider import RealEnvironmentalProvider

        with pytest.raises(ValueError, match="CDS API key required"):
            RealEnvironmentalProvider(
                cmems_username="user",
                cmems_password="pass",
                cds_api_key="",
            )


# ── Provider name / provenance tests ─────────────────────────────────────


class TestProviderName:
    """Test provider name and provenance metadata."""

    def test_provider_name_is_real(self):
        """RealEnvironmentalProvider.name is 'real'."""
        from app.services.environmental_real_provider import RealEnvironmentalProvider

        assert RealEnvironmentalProvider.name == "real"

    def test_provenance_includes_environmental_provider(self):
        """Drift result provenance includes environmental_provider='real'."""
        # Create a provider with mocked fetch methods
        from app.services.environmental_real_provider import RealEnvironmentalProvider

        provider = RealEnvironmentalProvider.__new__(RealEnvironmentalProvider)
        provider._cmems_user = "test"
        provider._cmems_pass = "test"
        provider._cds_key = "test"
        provider._cds_url = "https://example.com"

        lats = np.array([15.0, 15.5])
        lons = np.array([72.5, 73.0])
        t0 = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)

        provider._currents_grids = {t0: np.ones((2, 2, 2)) * 0.1}
        provider._winds_grids = {t0: np.ones((2, 2, 2)) * 0.2}
        provider._cache_lats = lats
        provider._cache_lons = lons
        provider._cache_timesteps = [t0]
        provider._prepared = True

        settings = Settings(
            drift_provider="first_order",
            environmental_provider="real",
            drift_ensemble_size=5,
        )
        engine = FirstOrderDriftProvider(
            environmental_provider=provider,
            settings=settings,
        )
        result = engine.estimate_source(
            incident_id="test-001",
            slick_lat=15.3,
            slick_lon=72.8,
            observation_time=t0,
        )
        assert result.provenance["environmental_provider"] == "real"


# ── Deterministic drift with fixture data ────────────────────────────────


class TestDeterministicDrift:
    """Test drift engine produces deterministic results with fixed env data."""

    def test_same_input_same_output(self):
        """Same inputs produce identical drift results."""
        from app.services.environmental_real_provider import RealEnvironmentalProvider

        def _make_provider():
            provider = RealEnvironmentalProvider.__new__(RealEnvironmentalProvider)
            lats = np.array([15.0, 15.25, 15.5])
            lons = np.array([72.5, 72.75, 73.0])
            t0 = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)

            # Fixed conditions: 0.1 m/s eastward current, 5 m/s eastward wind
            grid = np.zeros((3, 3, 2), dtype=np.float64)
            grid[:, :, 0] = 0.1  # current_u
            grid[:, :, 1] = 0.0  # current_v
            # Wind grid separate
            wind_grid = np.zeros((3, 3, 2), dtype=np.float64)
            wind_grid[:, :, 0] = 5.0  # wind_u
            wind_grid[:, :, 1] = 0.0  # wind_v

            provider._currents_grids = {t0: grid}
            provider._winds_grids = {t0: wind_grid}
            provider._cache_lats = lats
            provider._cache_lons = lons
            provider._cache_timesteps = [t0]
            provider._prepared = True
            return provider

        settings = Settings(
            drift_provider="first_order",
            environmental_provider="real",
            drift_hours=6.0,
            drift_timestep_minutes=60.0,
            drift_ensemble_size=10,
            windage_coefficient=0.03,
            windage_coefficient_std=0.0,
            current_fraction=1.0,
            position_noise_km=0.0,
            drift_uncertainty_km_per_hour=0.5,
        )

        results = []
        for _ in range(3):
            provider = _make_provider()
            engine = FirstOrderDriftProvider(
                environmental_provider=provider,
                settings=settings,
            )
            results.append(engine.estimate_source(
                incident_id="test-det",
                slick_lat=15.3,
                slick_lon=72.8,
                observation_time=datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc),
            ))

        # All three runs should produce identical results
        for i in range(1, len(results)):
            assert results[0].source_latitude == results[i].source_latitude
            assert results[0].source_longitude == results[i].source_longitude
            assert results[0].uncertainty_km == results[i].uncertainty_km


# ── Mock provider regression ─────────────────────────────────────────────


class TestMockProviderRegression:
    """Ensure MockEnvironmentalProvider still works correctly."""

    def test_mock_provider_returns_conditions(self):
        """Mock provider returns valid EnvironmentalConditions."""
        mock = MockEnvironmentalProvider()
        t = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
        conditions = mock.get_conditions(15.3, 72.8, t)

        assert conditions.latitude == 15.3
        assert conditions.longitude == 72.8
        assert conditions.timestamp == t
        assert isinstance(conditions.current_u, float)
        assert isinstance(conditions.current_v, float)
        assert isinstance(conditions.wind_u, float)
        assert isinstance(conditions.wind_v, float)

    def test_mock_provider_name(self):
        """Mock provider name is 'mock'."""
        mock = MockEnvironmentalProvider()
        assert mock.name == "mock"

    def test_mock_drift_engine_works(self):
        """Drift engine works with mock provider."""
        mock = MockEnvironmentalProvider()
        settings = Settings(
            drift_provider="first_order",
            environmental_provider="mock",
            drift_ensemble_size=5,
        )
        engine = FirstOrderDriftProvider(
            environmental_provider=mock,
            settings=settings,
        )
        result = engine.estimate_source(
            incident_id="mock-test",
            slick_lat=15.3,
            slick_lon=72.8,
            observation_time=datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc),
        )
        assert result.provenance["environmental_provider"] == "mock"
        assert "DEMO_ENVIRONMENTAL_FORCING" in result.quality_flags


# ── Live external API tests (opt-in) ─────────────────────────────────────

pytestmark_live = pytest.mark.live


@pytest.mark.live
class TestLiveCMEMSFetch:
    """Live tests against CMEMS API. Run with: pytest -m live."""

    @pytest.fixture
    def real_provider(self):
        """Create a real provider with credentials from environment."""
        import os

        cmems_user = os.environ.get("CMEMS_USERNAME", "")
        cmems_pass = os.environ.get("CMEMS_PASSWORD", "")
        cds_key = os.environ.get("CDS_API_KEY", "")

        if not cmems_user or not cmems_pass or not cds_key:
            pytest.skip("CMEMS/CDS credentials not set in environment")

        from app.services.environmental_real_provider import RealEnvironmentalProvider
        return RealEnvironmentalProvider(
            cmems_username=cmems_user,
            cmems_password=cmems_pass,
            cds_api_key=cds_key,
        )

    def test_live_fetch_small_bbox(self, real_provider):
        """Fetch real data for a small bbox around the demo incident."""
        bbox = (72.6, 15.0, 73.1, 15.6)
        timesteps = [
            datetime(2026, 8, 19, h, 0, tzinfo=timezone.utc)
            for h in range(10, 14)
        ]

        real_provider.prepare_cache(bbox, timesteps)

        assert real_provider._prepared
        assert len(real_provider._cache_timesteps) > 0
        assert len(real_provider._cache_lats) > 0
        assert len(real_provider._cache_lons) > 0

        # Test interpolation at center of bbox
        conditions = real_provider.get_conditions(15.3, 72.85, timesteps[1])
        assert isinstance(conditions.current_u, float)
        assert isinstance(conditions.wind_u, float)
        # Ocean currents should be reasonable (not zero from mock)
        assert abs(conditions.current_u) > 0.001 or abs(conditions.current_v) > 0.001

        real_provider.close()
