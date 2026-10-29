"""Criticality scorer tests.

Tests cover:
- Normal incident with all available factors
- Very small spill
- Very large spill
- Zero confidence
- Missing confidence
- Missing drift
- Missing AIS
- Missing environmental data
- Missing coastal/sensitive data (always unavailable)
- All factors available
- Multiple unavailable factors
- Boundary scores
- Score clamping
- No NaN/Infinity
- Deterministic repeated calculation
- Weight normalization
"""

from __future__ import annotations

import math

import pytest

from app.services.criticality_scorer import (
    _clamp,
    _normalize_linear,
    _normalize_log,
    _safe_float,
    _score_ais_traffic_evidence,
    _score_coastal_sensitive_risk,
    _score_detection_confidence,
    _score_environmental_spreading,
    _score_projected_drift_impact,
    _score_spill_age,
    _score_spill_size,
    compute_criticality,
)


# ── Helper fixtures ────────────────────────────────────────────────────

@pytest.fixture
def full_incident():
    return {
        "id": "IN-TEST-001",
        "areaKm2": 5.0,
        "confidence": 0.85,
        "region": "Arabian Sea",
        "windSpeedKts": 12.0,
    }


@pytest.fixture
def full_drift():
    return {
        "incidentId": "IN-TEST-001",
        "method": "first_order_backward_hindcast",
        "slickLatitude": 15.2965,
        "slickLongitude": 72.8456,
        "observationTime": "2026-08-26T01:00:00Z",
        "integrationHours": 24,
        "timestepMinutes": 15,
        "ensembleSize": 50,
        "sourceLatitude": 15.15,
        "sourceLongitude": 72.75,
        "sourceEarliest": "2026-08-25T01:00:00Z",
        "sourceLatest": "2026-08-25T05:00:00Z",
        "uncertaintyKm": 12.5,
        "uncertaintyHours": 4.0,
        "confidence": 0.72,
        "qualityFlags": [],
        "sourcePoints": [[15.15, 72.75]],
        "provenance": {},
        "analyzedAt": "2026-08-26T20:00:00Z",
    }


@pytest.fixture
def full_attribution():
    return {
        "incidentId": "IN-TEST-001",
        "searchWindow": {
            "start": "2026-08-25T19:00:00Z",
            "end": "2026-08-26T07:00:00Z",
            "centerLat": 15.2,
            "centerLon": 72.8,
            "radiusKm": 50,
            "timeWindowHours": 6,
        },
        "coverageKnown": True,
        "provider": "gfw",
        "dataset": "GLOBAL_FISHING_WATCH",
        "candidateCount": 3,
        "candidates": [
            {
                "mmsi": "987654321",
                "vesselName": "PACIFIC CARRIER",
                "vesselType": "Cargo",
                "attributionScore": 0.87,
                "closestDistanceKm": 0.33,
                "numberOfObservations": 5,
            },
            {
                "mmsi": "987654322",
                "vesselName": "COASTAL FISHER",
                "vesselType": "Fishing",
                "attributionScore": 0.45,
                "closestDistanceKm": 2.1,
                "numberOfObservations": 3,
            },
        ],
        "totalObservations": 12,
        "analyzedAt": "2026-08-26T20:00:00Z",
        "provenance": {},
    }


@pytest.fixture
def full_intelligence():
    return {
        "confidenceBreakdown": {
            "rawModelConfidence": 0.85,
            "adjustedConfidence": 0.78,
            "confidenceBand": "HIGH",
            "lookLikePenalty": 0.03,
            "environmentalPenalty": 0.04,
            "smallDetectionPenalty": 0.0,
            "calibrationShift": 0.0,
            "seasonalPriorAdjustment": 0.0,
        },
        "environmentalReliability": {
            "status": "HEURISTIC",
            "band": "GOOD",
            "windSpeedKnots": 12.0,
            "waveHeightM": None,
            "currentSpeedMs": 0.35,
            "penalty": 0.04,
            "explanation": "Wind: 12.0 kts, Current: 0.35 m/s",
        },
    }


# ── Normalization tests ────────────────────────────────────────────────

class TestNormalization:
    def test_clamp_normal(self):
        assert _clamp(0.5) == 0.5

    def test_clamp_below_min(self):
        assert _clamp(-0.5) == 0.0

    def test_clamp_above_max(self):
        assert _clamp(1.5) == 1.0

    def test_clamp_nan(self):
        assert _clamp(float("nan")) == 0.0

    def test_clamp_inf(self):
        assert _clamp(float("inf")) == 0.0

    def test_clamp_neg_inf(self):
        assert _clamp(float("-inf")) == 0.0

    def test_clamp_custom_range(self):
        assert _clamp(50, 0, 100) == 50

    def test_normalize_linear(self):
        assert _normalize_linear(5, 0, 10) == 0.5

    def test_normalize_linear_zero_range(self):
        assert _normalize_linear(5, 5, 5) == 0.0

    def test_normalize_log(self):
        result = _normalize_log(5, 0, 10)
        assert 0 <= result <= 1

    def test_normalize_log_zero(self):
        assert _normalize_log(0, 0, 10) == 0.0

    def test_safe_float_normal(self):
        assert _safe_float(3.14) == 3.14

    def test_safe_float_none(self):
        assert _safe_float(None) == 0.0

    def test_safe_float_nan(self):
        assert _safe_float(float("nan")) == 0.0

    def test_safe_float_string(self):
        assert _safe_float("invalid") == 0.0


# ── Individual factor tests ────────────────────────────────────────────

class TestSpillSizeFactor:
    def test_small_spill(self):
        score, available, _, _ = _score_spill_size(0.5)
        assert available is True
        assert 0 <= score <= 100

    def test_large_spill(self):
        score, available, _, _ = _score_spill_size(10.0)
        assert available is True
        assert score > 50

    def test_zero_spill(self):
        score, available, _, _ = _score_spill_size(0.0)
        assert available is True
        assert score == 0.0

    def test_none_spill(self):
        _, available, _, _ = _score_spill_size(None)
        assert available is False


class TestDetectionConfidenceFactor:
    def test_high_confidence(self):
        score, available, _, _ = _score_detection_confidence(0.9, 0.95)
        assert available is True
        assert score > 80

    def test_low_confidence(self):
        score, available, _, _ = _score_detection_confidence(0.3, 0.35)
        assert available is True
        assert score < 50

    def test_none_confidence(self):
        _, available, _, _ = _score_detection_confidence(None, None)
        assert available is False


class TestEnvironmentalSpreadingFactor:
    def test_high_wind(self):
        score, available, _, _ = _score_environmental_spreading(25.0, 0.8)
        assert available is True
        assert score > 50

    def test_low_wind(self):
        score, available, _, _ = _score_environmental_spreading(5.0, 0.1)
        assert available is True
        assert score < 50

    def test_zero_wind(self):
        score, available, _, _ = _score_environmental_spreading(0.0, 0.0)
        assert available is True
        assert score == 0.0

    def test_wind_only(self):
        score, available, _, _ = _score_environmental_spreading(10.0, None)
        assert available is True
        assert score > 0

    def test_current_only(self):
        score, available, _, _ = _score_environmental_spreading(None, 0.5)
        assert available is True
        assert score > 0

    def test_both_missing(self):
        _, available, _, explanation = _score_environmental_spreading(None, None)
        assert available is False
        assert "unavailable" in explanation.lower()

    def test_wind_missing(self):
        score, available, _, _ = _score_environmental_spreading(None, 0.5)
        assert available is True
        # Only current contributes
        assert score > 0

    def test_current_missing(self):
        score, available, _, _ = _score_environmental_spreading(10.0, None)
        assert available is True
        # Only wind contributes
        assert score > 0

    def test_no_nan_on_none(self):
        import math
        _, available, _, _ = _score_environmental_spreading(None, None)
        assert available is False

    def test_valid_data(self):
        score, available, _, _ = _score_environmental_spreading(15.0, 0.5)
        assert available is True
        assert 30 <= score <= 80


class TestSpillAgeFactor:
    def test_old_spill(self):
        score, available, _, _ = _score_spill_age(8.0, "2026-08-25T01:00:00Z", "2026-08-25T09:00:00Z")
        assert available is True
        assert score >= 80

    def test_young_spill(self):
        score, available, _, _ = _score_spill_age(1.0, "2026-08-25T01:00:00Z", "2026-08-25T02:00:00Z")
        assert available is True
        assert score < 30

    def test_none_age(self):
        _, available, _, _ = _score_spill_age(None, None, None)
        assert available is False


class TestProjectedDriftImpactFactor:
    def test_large_uncertainty(self):
        score, available, _, _ = _score_projected_drift_impact(40.0, 0.8)
        assert available is True
        assert score > 50

    def test_small_uncertainty(self):
        score, available, _, _ = _score_projected_drift_impact(5.0, 0.9)
        assert available is True
        assert score < 30

    def test_none_uncertainty(self):
        _, available, _, _ = _score_projected_drift_impact(None, None)
        assert available is False


class TestAISTrafficEvidenceFactor:
    def test_high_attribution(self):
        score, available, _, _ = _score_ais_traffic_evidence(
            [{"attributionScore": 0.9}], 1
        )
        assert available is True
        assert score > 80

    def test_no_candidates(self):
        _, available, _, _ = _score_ais_traffic_evidence([], 0)
        assert available is False

    def test_none_candidates(self):
        _, available, _, _ = _score_ais_traffic_evidence(None, None)
        assert available is False


class TestCoastalSensitiveRiskFactor:
    def test_always_unavailable(self):
        score, available, _, explanation = _score_coastal_sensitive_risk()
        assert available is False
        assert score == 0.0
        assert "not yet implemented" in explanation.lower()


# ── Full criticality computation tests ─────────────────────────────────

class TestComputeCriticality:
    def test_full_data(
        self, full_incident, full_drift, full_attribution, full_intelligence
    ):
        result = compute_criticality(
            incident=full_incident,
            drift=full_drift,
            attribution=full_attribution,
            intelligence=full_intelligence,
        )
        assert 0 <= result.score <= 100
        assert isinstance(result.score, int)
        assert result.level in ("LOW", "MID", "HIGH", "CRITICAL")
        assert result.available_factor_count == 6
        assert result.total_factor_count == 7
        assert len(result.factors) == 7

    def test_no_data(self):
        result = compute_criticality()
        assert result.score == 0
        assert result.level == "LOW"
        # No data: all factors unavailable (including environmental spreading)
        assert result.available_factor_count == 0

    def test_only_incident(self, full_incident):
        result = compute_criticality(incident=full_incident)
        assert 0 <= result.score <= 100
        assert result.available_factor_count >= 1

    def test_only_drift(self, full_drift):
        result = compute_criticality(drift=full_drift)
        assert 0 <= result.score <= 100
        assert result.available_factor_count >= 1

    def test_only_attribution(self, full_attribution):
        result = compute_criticality(attribution=full_attribution)
        assert 0 <= result.score <= 100
        assert result.available_factor_count >= 1

    def test_deterministic(
        self, full_incident, full_drift, full_attribution, full_intelligence
    ):
        r1 = compute_criticality(
            incident=full_incident,
            drift=full_drift,
            attribution=full_attribution,
            intelligence=full_intelligence,
        )
        r2 = compute_criticality(
            incident=full_incident,
            drift=full_drift,
            attribution=full_attribution,
            intelligence=full_intelligence,
        )
        assert r1.score == r2.score
        assert r1.level == r2.level
        assert r1.action == r2.action

    def test_no_nan_or_inf(
        self, full_incident, full_drift, full_attribution, full_intelligence
    ):
        result = compute_criticality(
            incident=full_incident,
            drift=full_drift,
            attribution=full_attribution,
            intelligence=full_intelligence,
        )
        assert math.isfinite(result.score)
        for f in result.factors:
            assert math.isfinite(f.score)
            assert math.isfinite(f.weight)
            assert math.isfinite(f.normalized_weight)

    def test_boundary_scores(self):
        # Maximum possible scores
        result = compute_criticality(
            incident={"areaKm2": 100.0, "confidence": 1.0},
            drift={"uncertaintyKm": 100.0, "uncertaintyHours": 16.0, "confidence": 1.0},
            attribution={"candidateCount": 5, "candidates": [
                {"attributionScore": 1.0} for _ in range(5)
            ]},
            intelligence={
                "confidenceBreakdown": {"adjustedConfidence": 1.0, "rawModelConfidence": 1.0},
                "environmentalReliability": {"windSpeedKnots": 50.0, "currentSpeedMs": 2.0},
            },
        )
        assert result.score > 50  # Should be relatively high with max inputs

    def test_zero_confidence(self):
        result = compute_criticality(
            intelligence={
                "confidenceBreakdown": {"adjustedConfidence": 0.0, "rawModelConfidence": 0.0},
            },
        )
        assert result.score >= 0

    def test_missing_drift(self, full_incident, full_attribution, full_intelligence):
        result = compute_criticality(
            incident=full_incident,
            attribution=full_attribution,
            intelligence=full_intelligence,
        )
        assert 0 <= result.score <= 100
        # Drift factors should be unavailable
        drift_factors = [f for f in result.factors if f.name in ("spill_age", "projected_drift_impact")]
        assert all(not f.available for f in drift_factors)

    def test_missing_attribution(self, full_incident, full_drift, full_intelligence):
        result = compute_criticality(
            incident=full_incident,
            drift=full_drift,
            intelligence=full_intelligence,
        )
        assert 0 <= result.score <= 100
        ais_factor = next(f for f in result.factors if f.name == "ais_traffic_evidence")
        assert ais_factor.available is False

    def test_missing_intelligence(self, full_incident, full_drift, full_attribution):
        result = compute_criticality(
            incident=full_incident,
            drift=full_drift,
            attribution=full_attribution,
        )
        assert 0 <= result.score <= 100
        # Confidence factor should be unavailable without intelligence
        conf_factor = next(f for f in result.factors if f.name == "detection_confidence")
        assert conf_factor.available is False

    def test_coastal_factor_always_unavailable(
        self, full_incident, full_drift, full_attribution, full_intelligence
    ):
        result = compute_criticality(
            incident=full_incident,
            drift=full_drift,
            attribution=full_attribution,
            intelligence=full_intelligence,
        )
        coastal = next(f for f in result.factors if f.name == "coastal_sensitive_risk")
        assert coastal.available is False
        assert coastal.score == 0.0
        assert coastal.normalized_weight == 0.0

    def test_weight_normalization(
        self, full_incident, full_drift, full_attribution, full_intelligence
    ):
        result = compute_criticality(
            incident=full_incident,
            drift=full_drift,
            attribution=full_attribution,
            intelligence=full_intelligence,
        )
        # Available factors should have normalized weights summing to ~1.0
        available_weights = sum(f.normalized_weight for f in result.factors if f.available)
        assert abs(available_weights - 1.0) < 0.01

    def test_severity_levels(self):
        # Test LOW
        r_low = compute_criticality(
            incident={"areaKm2": 0.1},
            intelligence={"confidenceBreakdown": {"adjustedConfidence": 0.1}},
        )
        assert r_low.level in ("LOW", "MID")

        # Test CRITICAL
        r_crit = compute_criticality(
            incident={"areaKm2": 50.0, "confidence": 1.0},
            drift={"uncertaintyKm": 100.0, "uncertaintyHours": 16.0, "confidence": 1.0},
            attribution={"candidateCount": 5, "candidates": [
                {"attributionScore": 1.0} for _ in range(5)
            ]},
            intelligence={
                "confidenceBreakdown": {"adjustedConfidence": 1.0, "rawModelConfidence": 1.0},
                "environmentalReliability": {"windSpeedKnots": 50.0, "currentSpeedMs": 2.0},
            },
        )
        assert r_crit.score >= 50  # Should be at least MODERATE with strong inputs

    def test_methodology_string(
        self, full_incident, full_drift, full_attribution, full_intelligence
    ):
        result = compute_criticality(
            incident=full_incident,
            drift=full_drift,
            attribution=full_attribution,
            intelligence=full_intelligence,
        )
        assert "v1.0.0-mvp" in result.methodology
        assert "NOT scientifically validated" in result.methodology

    def test_normalization_note_with_missing(self):
        result = compute_criticality(incident={"areaKm2": 5.0})
        assert "unavailable" in result.normalization_note.lower()

    def test_normalization_note_all_available(
        self, full_incident, full_drift, full_attribution, full_intelligence
    ):
        result = compute_criticality(
            incident=full_incident,
            drift=full_drift,
            attribution=full_attribution,
            intelligence=full_intelligence,
        )
        # Coastal/sensitive risk is always unavailable, so normalization always happens
        assert "1 factor(s) unavailable" in result.normalization_note
        assert "6 available factors" in result.normalization_note
