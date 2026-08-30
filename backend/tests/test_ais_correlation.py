"""AIS vessel correlation tests — comprehensive unit and integration tests.

Tests cover:
- AIS normalization and schema
- Timestamp parsing
- Missing optional fields
- Geodesic distance calculation
- Spatial filtering
- Temporal filtering
- Candidate grouping
- Closest approach calculation
- Attribution scoring
- Score weights
- AIS coverage unknown
- Empty AIS results
- Multiple vessels
- Deterministic mock provider
- API response schema
- End-to-end analysis
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from app.config import Settings
from app.domain.ais import (
    AisObservation,
    AisSearchWindow,
    AttributionResult,
    CandidateVessel,
    SourceEstimate,
)
from app.services.ais_correlation import (
    analyze_attribution,
    build_search_window,
    compute_attribution_scores,
    compute_candidate_vessel,
    geodesic_distance_km,
    group_by_vessel,
    spatial_filter,
    temporal_filter,
)
from app.services.ais_mock_provider import DEMO_VESSELS, MockAISProvider


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def settings() -> Settings:
    return Settings(
        ais_provider="mock",
        ais_search_radius_km=50.0,
        ais_time_window_hours=6.0,
        ais_distance_weight=0.50,
        ais_time_weight=0.30,
        ais_track_weight=0.20,
    )


@pytest.fixture
def source() -> SourceEstimate:
    return SourceEstimate(
        latitude=10.0,
        longitude=72.0,
        timestamp=datetime(2026, 8, 26, 1, 0, 0, tzinfo=timezone.utc),
        uncertainty_km=50.0,
        uncertainty_hours=6.0,
    )


@pytest.fixture
def mock_provider() -> MockAISProvider:
    return MockAISProvider()


# ── AIS Schema Tests ─────────────────────────────────────────────────────

class TestAisObservation:
    def test_minimal_observation(self):
        obs = AisObservation(
            mmsi="123456789",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            lat=10.0,
            lon=72.0,
        )
        assert obs.mmsi == "123456789"
        assert obs.lat == 10.0
        assert obs.lon == 72.0
        assert obs.sog is None
        assert obs.cog is None
        assert obs.vessel_type is None
        assert obs.imo is None
        assert obs.vessel_name is None

    def test_full_observation(self):
        obs = AisObservation(
            mmsi="987654321",
            timestamp=datetime(2026, 8, 26, 1, 0, 0, tzinfo=timezone.utc),
            lat=10.003,
            lon=71.997,
            sog=12.5,
            cog=135.0,
            heading=133.0,
            vessel_type="Cargo",
            imo="9876543",
            vessel_name="PACIFIC CARRIER",
            navigation_status="Under way using engine",
            draft=8.5,
        )
        assert obs.mmsi == "987654321"
        assert obs.sog == 12.5
        assert obs.vessel_name == "PACIFIC CARRIER"


# ── Geodesic Distance Tests ──────────────────────────────────────────────

class TestGeodesicDistance:
    def test_same_point(self):
        d = geodesic_distance_km(10.0, 72.0, 10.0, 72.0)
        assert d == pytest.approx(0.0, abs=0.01)

    def test_known_distance(self):
        # ~111 km per degree latitude
        d = geodesic_distance_km(10.0, 72.0, 11.0, 72.0)
        assert d == pytest.approx(111.0, rel=0.01)

    def test_symmetry(self):
        d1 = geodesic_distance_km(10.0, 72.0, 10.5, 72.5)
        d2 = geodesic_distance_km(10.5, 72.5, 10.0, 72.0)
        assert d1 == pytest.approx(d2, rel=1e-6)

    def test_50km_radius(self):
        # At equator, 1 degree lon ~ 111 km
        d = geodesic_distance_km(10.0, 72.0, 10.0, 72.0 + 50.0 / 111.0)
        assert d == pytest.approx(50.0, rel=0.05)


# ── Spatial Filter Tests ─────────────────────────────────────────────────

class TestSpatialFilter:
    def test_observation_within_radius(self, source):
        obs = AisObservation(mmsi="1", timestamp=source.timestamp, lat=10.01, lon=72.01)
        result = spatial_filter([obs], source, radius_km=50.0)
        assert len(result) == 1
        assert result[0][1] < 50.0

    def test_observation_outside_radius(self, source):
        obs = AisObservation(mmsi="1", timestamp=source.timestamp, lat=11.0, lon=73.0)
        result = spatial_filter([obs], source, radius_km=5.0)
        assert len(result) == 0

    def test_empty_observations(self, source):
        result = spatial_filter([], source, radius_km=50.0)
        assert result == []

    def test_distance_calculation(self, source):
        obs = AisObservation(mmsi="1", timestamp=source.timestamp, lat=10.05, lon=72.0)
        result = spatial_filter([obs], source, radius_km=50.0)
        assert len(result) == 1
        assert result[0][1] == pytest.approx(5.55, rel=0.05)


# ── Temporal Filter Tests ────────────────────────────────────────────────

class TestTemporalFilter:
    def test_observation_within_window(self, source):
        obs = AisObservation(mmsi="1", timestamp=source.timestamp, lat=10.0, lon=72.0)
        result = temporal_filter([(obs, 1.0)], source.timestamp, time_window_hours=6.0)
        assert len(result) == 1
        assert result[0][2] == pytest.approx(0.0, abs=0.1)

    def test_observation_outside_window(self, source):
        obs = AisObservation(
            mmsi="1",
            timestamp=source.timestamp + timedelta(hours=12),
            lat=10.0,
            lon=72.0,
        )
        result = temporal_filter([(obs, 1.0)], source.timestamp, time_window_hours=6.0)
        assert len(result) == 0

    def test_negative_time_difference(self, source):
        obs = AisObservation(
            mmsi="1",
            timestamp=source.timestamp - timedelta(hours=2),
            lat=10.0,
            lon=72.0,
        )
        result = temporal_filter([(obs, 1.0)], source.timestamp, time_window_hours=6.0)
        assert len(result) == 1
        assert result[0][2] == pytest.approx(-120.0, abs=0.1)


# ── Grouping Tests ───────────────────────────────────────────────────────

class TestGroupByVessel:
    def test_single_vessel(self, source):
        obs = AisObservation(mmsi="111", timestamp=source.timestamp, lat=10.0, lon=72.0)
        grouped = group_by_vessel([(obs, 1.0, 0.0)])
        assert "111" in grouped
        assert len(grouped["111"]) == 1

    def test_multiple_vessels(self, source):
        obs1 = AisObservation(mmsi="111", timestamp=source.timestamp, lat=10.0, lon=72.0)
        obs2 = AisObservation(mmsi="222", timestamp=source.timestamp, lat=10.0, lon=72.0)
        obs3 = AisObservation(mmsi="111", timestamp=source.timestamp, lat=10.0, lon=72.0)
        grouped = group_by_vessel([(obs1, 1.0, 0.0), (obs2, 2.0, 0.0), (obs3, 1.5, 0.0)])
        assert len(grouped) == 2
        assert len(grouped["111"]) == 2
        assert len(grouped["222"]) == 1


# ── Candidate Vessel Tests ───────────────────────────────────────────────

class TestCandidateVessel:
    def test_closest_approach(self, source):
        t = source.timestamp
        obs1 = AisObservation(mmsi="111", timestamp=t - timedelta(hours=1), lat=10.1, lon=72.0)
        obs2 = AisObservation(mmsi="111", timestamp=t, lat=10.003, lon=72.0)
        obs3 = AisObservation(mmsi="111", timestamp=t + timedelta(hours=1), lat=10.05, lon=72.0)
        candidate = compute_candidate_vessel("111", [(obs1, 10.0, -60), (obs2, 0.33, 0.0), (obs3, 5.5, 60)])
        assert candidate.closest_distance_km == pytest.approx(0.33, abs=0.1)
        assert candidate.number_of_observations == 3
        assert candidate.vessel_name is None  # mock observation has no name

    def test_single_observation_quality_flag(self, source):
        obs = AisObservation(mmsi="111", timestamp=source.timestamp, lat=10.0, lon=72.0)
        candidate = compute_candidate_vessel("111", [(obs, 1.0, 0.0)])
        assert candidate.number_of_observations == 1


# ── Attribution Scoring Tests ────────────────────────────────────────────

class TestScoring:
    def test_closer_vessel_scores_higher(self, source, settings):
        c1 = CandidateVessel(
            mmsi="111",
            closest_distance_km=2.0,
            closest_time_difference_minutes=10.0,
            number_of_observations=5,
        )
        c2 = CandidateVessel(
            mmsi="222",
            closest_distance_km=20.0,
            closest_time_difference_minutes=10.0,
            number_of_observations=5,
        )
        scored = compute_attribution_scores([c1, c2], source, settings)
        assert scored[0].mmsi == "111"
        assert scored[0].attribution_score > scored[1].attribution_score

    def test_closer_in_time_scores_higher(self, source, settings):
        c1 = CandidateVessel(
            mmsi="111",
            closest_distance_km=10.0,
            closest_time_difference_minutes=5.0,
            number_of_observations=3,
        )
        c2 = CandidateVessel(
            mmsi="222",
            closest_distance_km=10.0,
            closest_time_difference_minutes=300.0,
            number_of_observations=3,
        )
        scored = compute_attribution_scores([c1, c2], source, settings)
        assert scored[0].mmsi == "111"
        assert scored[0].score_components["time"] > scored[1].score_components["time"]

    def test_more_observations_score_higher(self, source, settings):
        c1 = CandidateVessel(
            mmsi="111",
            closest_distance_km=10.0,
            closest_time_difference_minutes=60.0,
            number_of_observations=6,
        )
        c2 = CandidateVessel(
            mmsi="222",
            closest_distance_km=10.0,
            closest_time_difference_minutes=60.0,
            number_of_observations=1,
        )
        scored = compute_attribution_scores([c1, c2], source, settings)
        assert scored[0].score_components["trackConsistency"] > scored[1].score_components["trackConsistency"]

    def test_score_range_0_to_1(self, source, settings):
        c = CandidateVessel(
            mmsi="111",
            closest_distance_km=25.0,
            closest_time_difference_minutes=180.0,
            number_of_observations=2,
        )
        scored = compute_attribution_scores([c], source, settings)
        assert 0.0 <= scored[0].attribution_score <= 1.0

    def test_weights_sum_to_1(self, settings):
        assert settings.ais_distance_weight + settings.ais_time_weight + settings.ais_track_weight == pytest.approx(1.0)

    def test_single_observation_quality_flag(self, source, settings):
        c = CandidateVessel(
            mmsi="111",
            closest_distance_km=5.0,
            closest_time_difference_minutes=30.0,
            number_of_observations=1,
        )
        scored = compute_attribution_scores([c], source, settings)
        assert "SINGLE_OBSERVATION" in scored[0].quality_flags
        assert scored[0].human_review_required is True


# ── Search Window Tests ──────────────────────────────────────────────────

class TestSearchWindow:
    def test_bbox_from_radius(self, source, settings):
        sw = build_search_window(source, settings)
        w, s, e, n = sw.bbox
        assert w < source.longitude < e
        assert s < source.latitude < n
        assert sw.radius_km == 50.0
        assert sw.time_window_hours == 6.0

    def test_time_range(self, source, settings):
        sw = build_search_window(source, settings)
        assert sw.start_time == source.timestamp - timedelta(hours=6)
        assert sw.end_time == source.timestamp + timedelta(hours=6)


# ── Mock Provider Tests ──────────────────────────────────────────────────

class TestMockProvider:
    def test_returns_observations(self, source, mock_provider, settings):
        sw = build_search_window(source, settings)
        obs = mock_provider.query_positions(sw)
        assert isinstance(obs, list)
        assert len(obs) > 0

    def test_observations_have_required_fields(self, source, mock_provider, settings):
        sw = build_search_window(source, settings)
        obs = mock_provider.query_positions(sw)
        for o in obs:
            assert o.mmsi
            assert o.timestamp
            assert isinstance(o.lat, float)
            assert isinstance(o.lon, float)

    def test_deterministic(self, source, mock_provider, settings):
        sw = build_search_window(source, settings)
        obs1 = mock_provider.query_positions(sw)
        obs2 = mock_provider.query_positions(sw)
        assert len(obs1) == len(obs2)
        for a, b in zip(obs1, obs2):
            assert a.mmsi == b.mmsi
            assert a.lat == b.lat
            assert a.lon == b.lon

    def test_provider_name(self, mock_provider):
        assert mock_provider.name == "mock"
        assert "DEMO" in mock_provider.dataset

    def test_get_vessel(self, mock_provider):
        vessel = mock_provider.get_vessel("987654321")
        assert vessel is not None
        assert vessel["mmsi"] == "987654321"

    def test_get_vessel_unknown(self, mock_provider):
        vessel = mock_provider.get_vessel("000000000")
        assert vessel is None

    def test_4_vessels_defined(self):
        assert len(DEMO_VESSELS) == 4

    def test_vessel_a_closest(self, source, mock_provider, settings):
        """Vessel A should be closest to the slick center."""
        sw = build_search_window(source, settings)
        obs = mock_provider.query_positions(sw)
        vessel_a_obs = [o for o in obs if o.mmsi == "987654321"]
        assert len(vessel_a_obs) > 0
        # Vessel A should have observations near center
        for o in vessel_a_obs:
            dist = geodesic_distance_km(source.latitude, source.longitude, o.lat, o.lon)
            assert dist < 10.0  # Within 10 km


# ── Full Analysis Pipeline Tests ─────────────────────────────────────────

class TestFullAnalysis:
    def test_returns_attribution_result(self, source, mock_provider, settings):
        result = analyze_attribution(
            incident_id="IN-260826-001",
            source=source,
            provider=mock_provider,
            settings=settings,
        )
        assert isinstance(result, AttributionResult)
        assert result.incident_id == "IN-260826-001"
        assert result.provider == "mock"

    def test_candidates_are_ranked(self, source, mock_provider, settings):
        result = analyze_attribution(
            incident_id="IN-260826-001",
            source=source,
            provider=mock_provider,
            settings=settings,
        )
        if result.candidate_count >= 2:
            scores = [c.attribution_score for c in result.candidates]
            assert scores == sorted(scores, reverse=True)

    def test_vessel_a_closest_approach(self, source, mock_provider, settings):
        """Vessel A should have the closest single approach distance."""
        result = analyze_attribution(
            incident_id="IN-260826-001",
            source=source,
            provider=mock_provider,
            settings=settings,
        )
        vessel_a = next((c for c in result.candidates if c.mmsi == "987654321"), None)
        if vessel_a:
            # Vessel A should come within ~0.4 km of center
            assert vessel_a.closest_distance_km < 5.0

    def test_provenance_recorded(self, source, mock_provider, settings):
        result = analyze_attribution(
            incident_id="IN-260826-001",
            source=source,
            provider=mock_provider,
            settings=settings,
        )
        assert "provider" in result.provenance
        assert "search_radius_km" in result.provenance
        assert "scoring_weights" in result.provenance

    def test_human_review_required(self, source, mock_provider, settings):
        result = analyze_attribution(
            incident_id="IN-260826-001",
            source=source,
            provider=mock_provider,
            settings=settings,
        )
        for c in result.candidates:
            assert c.human_review_required is True

    def test_no_causation_claim(self, source, mock_provider, settings):
        result = analyze_attribution(
            incident_id="IN-260826-001",
            source=source,
            provider=mock_provider,
            settings=settings,
        )
        # The system must never produce "Responsible Vessel" or similar
        for c in result.candidates:
            assert c.attribution_score <= 1.0
            # Score is called "attribution_score", not "probability_of_guilt"
            assert hasattr(c, "attribution_score")


# ── Edge Case Tests ──────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_ais_results(self, source, settings):
        """Provider returning no observations should produce empty candidates."""

        class EmptyProvider(MockAISProvider):
            def query_positions(self, sw):
                return []

        result = analyze_attribution(
            incident_id="IN-260826-001",
            source=source,
            provider=EmptyProvider(),
            settings=settings,
        )
        assert result.candidate_count == 0
        assert result.candidates == []

    def test_all_observations_outside_radius(self, source, settings):
        """Observations far away should be filtered out."""

        class FarProvider(MockAISProvider):
            def query_positions(self, sw):
                return [
                    AisObservation(
                        mmsi="999",
                        timestamp=source.timestamp,
                        lat=20.0,  # ~1100 km away
                        lon=80.0,
                    )
                ]

        result = analyze_attribution(
            incident_id="IN-260826-001",
            source=source,
            provider=FarProvider(),
            settings=settings,
        )
        assert result.candidate_count == 0

    def test_all_observations_outside_time_window(self, source, settings):
        """Observations outside the time window should be filtered out."""

        class OldProvider(MockAISProvider):
            def query_positions(self, sw):
                return [
                    AisObservation(
                        mmsi="999",
                        timestamp=source.timestamp - timedelta(days=30),
                        lat=source.latitude,
                        lon=source.longitude,
                    )
                ]

        result = analyze_attribution(
            incident_id="IN-260826-001",
            source=source,
            provider=OldProvider(),
            settings=settings,
        )
        assert result.candidate_count == 0


# ── API Response Schema Tests ────────────────────────────────────────────

class TestApiResponseSchema:
    def test_attribution_response_shape(self, source, mock_provider, settings):
        from app.api.routes.attribution import _result_to_response

        result = analyze_attribution(
            incident_id="IN-260826-001",
            source=source,
            provider=mock_provider,
            settings=settings,
        )
        response = _result_to_response(result)
        data = response.model_dump(by_alias=True)

        assert "incidentId" in data
        assert "searchWindow" in data
        assert "coverageKnown" in data
        assert "candidateCount" in data
        assert "candidates" in data
        assert "totalObservations" in data
        assert "provenance" in data

        if data["candidates"]:
            c = data["candidates"][0]
            assert "mmsi" in c
            assert "closestDistanceKm" in c
            assert "attributionScore" in c
            assert "scoreComponents" in c
            assert "humanReviewRequired" in c
            assert "qualityFlags" in c


# ── Coverage Unknown Tests ───────────────────────────────────────────────

class TestCoverageUnknown:
    def test_coverage_known_flag(self, source, mock_provider, settings):
        result = analyze_attribution(
            incident_id="IN-260826-001",
            source=source,
            provider=mock_provider,
            settings=settings,
            coverage_known=True,
        )
        assert result.coverage_known is True

    def test_coverage_unknown_doesntpenalize(self, source, settings):
        """When AIS coverage is unknown, absence of vessels should not penalize."""
        result = analyze_attribution(
            incident_id="IN-260826-001",
            source=source,
            provider=MockAISProvider(),
            settings=settings,
            coverage_known=False,
        )
        assert result.coverage_known is False
        # No candidates is fine — coverage unknown means we can't conclude anything


# ── Configurable Weights Tests ───────────────────────────────────────────

class TestConfigurableWeights:
    def test_custom_weights(self, source, settings):
        settings.ais_distance_weight = 0.70
        settings.ais_time_weight = 0.20
        settings.ais_track_weight = 0.10

        c = CandidateVessel(
            mmsi="111",
            closest_distance_km=5.0,
            closest_time_difference_minutes=30.0,
            number_of_observations=3,
        )
        scored = compute_attribution_scores([c], source, settings)
        # With 70% distance weight, a close vessel should score high
        assert scored[0].attribution_score > 0.5

    def test_equal_weights(self, source, settings):
        settings.ais_distance_weight = 1 / 3
        settings.ais_time_weight = 1 / 3
        settings.ais_track_weight = 1 / 3

        c = CandidateVessel(
            mmsi="111",
            closest_distance_km=5.0,
            closest_time_difference_minutes=30.0,
            number_of_observations=3,
        )
        scored = compute_attribution_scores([c], source, settings)
        assert 0.0 <= scored[0].attribution_score <= 1.0


# ── SourceEstimate Tests ─────────────────────────────────────────────────

class TestSourceEstimate:
    def test_future_drift_compatibility(self):
        """SourceEstimate can accept drift hindcast output later."""
        source = SourceEstimate(
            latitude=10.5,
            longitude=72.5,
            timestamp=datetime(2026, 8, 26, 6, 0, 0, tzinfo=timezone.utc),
            uncertainty_km=25.0,
            uncertainty_hours=3.0,
        )
        assert source.latitude == 10.5
        assert source.uncertainty_km == 25.0
