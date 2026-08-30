"""Tests for Phase 8 Intelligence services.

Covers:
- LookAlikeClassifier
- EnvironmentalReliability
- ConfidenceCalibrator
- AISGapDetector + StaticSpacingDetector
- SmallDetectionAssessor
- ExplainableAttribution
- SeasonalPriorService
- FalsePositiveReviewManager
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.ais import AisObservation
from app.domain.entities import (
    ConfidenceBreakdown,
    LookAlikeFeatures,
    SmallDetectionAssessment,
)
from app.services.ais_gap_detector import AISGapDetector, StaticSpacingDetector
from app.services.confidence_calibrator import ConfidenceCalibrator
from app.services.environmental_reliability import EnvironmentalReliability
from app.services.environmental_provider import EnvironmentalConditions
from app.services.explainable_attribution import ExplainableAttribution
from app.services.false_positive_review import FalsePositiveReviewManager
from app.services.look_alike_classifier import (
    LookAlikeClassifier,
    extract_look_alike_features,
)
from app.services.seasonal_prior import SeasonalPriorService
from app.services.small_detection_assessor import SmallDetectionAssessor


# ── LookAlikeClassifier ──────────────────────────────────────────────────────


class TestLookAlikeClassifier:
    def test_strong_anomaly_low_look_alike(self):
        """Strong negative anomaly → low look-alike probability."""
        clf = LookAlikeClassifier()
        features = LookAlikeFeatures(
            mean_intensity_anomaly_db=-5.0,
            std_intensity_anomaly_db=1.0,
            aspect_ratio=4.0,
            elongation=0.7,
            compactness=0.2,
            wind_speed_knots=12.0,
        )
        result = clf.classify(features)
        assert result.look_alike_probability < 0.3

    def test_weak_anomaly_high_look_alike(self):
        """Weak anomaly → high look-alike probability."""
        clf = LookAlikeClassifier()
        features = LookAlikeFeatures(
            mean_intensity_anomaly_db=-0.5,
            std_intensity_anomaly_db=0.5,
            aspect_ratio=1.5,
            elongation=0.1,
            compactness=0.8,
            wind_speed_knots=1.0,
        )
        result = clf.classify(features)
        assert result.look_alike_probability > 0.5

    def test_low_wind_high_look_alike(self):
        """Low wind → high look-alike (low-wind areas)."""
        clf = LookAlikeClassifier()
        features = LookAlikeFeatures(
            mean_intensity_anomaly_db=-3.0,
            wind_speed_knots=2.0,
        )
        result = clf.classify(features)
        assert result.look_alike_probability > 0.4

    def test_ideal_wind_low_look_alike(self):
        """Ideal wind → low look-alike."""
        clf = LookAlikeClassifier()
        features = LookAlikeFeatures(
            mean_intensity_anomaly_db=-4.0,
            wind_speed_knots=12.0,
            aspect_ratio=5.0,
            elongation=0.8,
        )
        result = clf.classify(features)
        assert result.look_alike_probability < 0.3

    def test_probability_range(self):
        """Probability always in [0, 1]."""
        clf = LookAlikeClassifier()
        for wind in [0.0, 5.0, 10.0, 20.0, 50.0]:
            features = LookAlikeFeatures(wind_speed_knots=wind)
            result = clf.classify(features)
            assert 0.0 <= result.look_alike_probability <= 1.0


class TestExtractLookAlikeFeatures:
    def test_default_features(self):
        """Returns defaults when no patch provided."""
        features = extract_look_alike_features()
        assert features.mean_intensity_anomaly_db == 0.0

    def test_shape_from_area_perimeter(self):
        """Shape features computed from area/perimeter."""
        features = extract_look_alike_features(
            area_km2=0.1, perimeter_km=1.0
        )
        assert features.compactness > 0
        assert features.aspect_ratio >= 1.0

    def test_context_features(self):
        """Context features passed through."""
        features = extract_look_alike_features(
            distance_to_coast_km=5.0,
            is_near_shipping_lane=True,
            water_depth_m=30.0,
            wind_speed_knots=8.0,
        )
        assert features.distance_to_coast_km == 5.0
        assert features.is_near_shipping_lane is True
        assert features.water_depth_m == 30.0


# ── EnvironmentalReliability ─────────────────────────────────────────────────


class TestEnvironmentalReliability:
    def _make_conditions(self, wind_kts: float) -> EnvironmentalConditions:
        wind_ms = wind_kts * 0.514444
        return EnvironmentalConditions(
            latitude=15.0,
            longitude=73.0,
            timestamp=datetime.now(timezone.utc),
            current_u=0.2,
            current_v=0.1,
            wind_u=wind_ms,
            wind_v=0.0,
            wave_height=1.0,
        )

    def test_ideal_conditions(self):
        """Wind 8-15 kts → IDEAL band, zero penalty."""
        svc = EnvironmentalReliability()
        band, penalty, explanation = svc.assess(self._make_conditions(10.0))
        assert band == "IDEAL"
        assert penalty == 0.0

    def test_low_wind_marginal(self):
        """Wind 2 kts → MARGINAL."""
        svc = EnvironmentalReliability()
        band, penalty, _ = svc.assess(self._make_conditions(2.0))
        assert band == "MARGINAL"
        assert penalty > 0

    def test_very_low_wind_poor(self):
        """Wind < 1 kt → POOR."""
        svc = EnvironmentalReliability()
        band, penalty, _ = svc.assess(self._make_conditions(0.5))
        assert band == "POOR"
        assert penalty == 0.30

    def test_high_wind_poor(self):
        """Wind > 30 kts → POOR."""
        svc = EnvironmentalReliability()
        band, penalty, _ = svc.assess(self._make_conditions(35.0))
        assert band == "POOR"
        assert penalty == 0.30

    def test_high_wave_penalty(self):
        """High waves add extra penalty."""
        svc = EnvironmentalReliability()
        conds = EnvironmentalConditions(
            latitude=15.0,
            longitude=73.0,
            timestamp=datetime.now(timezone.utc),
            current_u=0.2, current_v=0.1,
            wind_u=5.0, wind_v=0.0,
            wave_height=4.0,
        )
        band, penalty, explanation = svc.assess(conds)
        assert "Significant wave height" in explanation


# ── ConfidenceCalibrator ─────────────────────────────────────────────────────


class TestConfidenceCalibrator:
    def test_default_identity(self):
        """Default params give sigmoid(0.5) ≈ 0.62 (sigmoid shape)."""
        cal = ConfidenceCalibrator()
        # sigmoid(0.5) = 1/(1+exp(-0.5)) ≈ 0.622
        assert cal.calibrate(0.5) == pytest.approx(0.622, abs=0.01)
        # sigmoid(0) = 0.5
        assert cal.calibrate(0.0) == pytest.approx(0.5, abs=0.01)
        # sigmoid(1) ≈ 0.731
        assert cal.calibrate(1.0) == pytest.approx(0.731, abs=0.01)

    def test_calibrate_clamps(self):
        """Extreme inputs produce valid outputs."""
        cal = ConfidenceCalibrator()
        assert 0.0 <= cal.calibrate(-1.0) <= 1.0
        assert 0.0 <= cal.calibrate(2.0) <= 1.0

    def test_fit(self):
        """Fitting on labeled data produces calibrated model."""
        cal = ConfidenceCalibrator()
        # True positives: high scores, True negatives: low scores
        scores = [0.9, 0.85, 0.8, 0.75, 0.2, 0.15, 0.1, 0.05, 0.3, 0.25]
        labels = [1, 1, 1, 1, 0, 0, 0, 0, 0, 0]
        cal.fit(scores, labels)
        assert cal.is_fitted
        # Fitted model should produce valid probabilities
        assert 0.0 <= cal.calibrate(0.9) <= 1.0
        assert 0.0 <= cal.calibrate(0.1) <= 1.0

    def test_fit_insufficient_data(self):
        """Too few samples → identity mapping."""
        cal = ConfidenceCalibrator()
        cal.fit([0.5, 0.6], [1, 0])
        assert not cal.is_fitted

    def test_to_dict_roundtrip(self):
        """Serialization roundtrip."""
        cal = ConfidenceCalibrator(a=-1.5, b=0.3)
        d = cal.to_dict()
        cal2 = ConfidenceCalibrator.from_dict(d)
        assert cal2.a == -1.5
        assert cal2.b == 0.3


# ── AISGapDetector ───────────────────────────────────────────────────────────


class TestAISGapDetector:
    def _make_obs(self, mmsi: str, times: list[datetime], lats: list[float], lons: list[float]) -> list[AisObservation]:
        return [
            AisObservation(mmsi=mmsi, timestamp=t, lat=lat, lon=lon)
            for t, lat, lon in zip(times, lats, lons)
        ]

    def test_no_gap(self):
        """Regular observations → no gaps detected."""
        base = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)
        obs = self._make_obs(
            "123456789",
            [base + timedelta(minutes=i * 5) for i in range(10)],
            [15.0] * 10,
            [73.0] * 10,
        )
        detector = AISGapDetector(gap_threshold_minutes=30)
        signals = detector.detect_gaps(obs, 15.0, 73.0, base)
        assert len(signals) == 0

    def test_temporal_gap(self):
        """Gap > threshold → detected."""
        base = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)
        times = [
            base, base + timedelta(minutes=5),
            base + timedelta(minutes=60),  # 55-minute gap
            base + timedelta(minutes=65),
        ]
        obs = self._make_obs("123456789", times, [15.0] * 4, [73.0] * 4)
        detector = AISGapDetector(gap_threshold_minutes=30)
        signals = detector.detect_gaps(obs, 15.0, 73.0, base)
        assert len(signals) == 1
        assert signals[0].gap_duration_hours > 0.5

    def test_sentinel_gap(self):
        """Sentinel value (91.0) → gap detected."""
        base = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)
        obs = self._make_obs(
            "123456789",
            [base, base + timedelta(minutes=10), base + timedelta(minutes=20)],
            [15.0, 91.0, 15.0],  # sentinel in middle
            [73.0, 91.0, 73.0],
        )
        detector = AISGapDetector(gap_threshold_minutes=5)
        signals = detector.detect_gaps(obs, 15.0, 73.0, base)
        assert len(signals) >= 1

    def test_gap_score_range(self):
        """Gap scores in [0, 1]."""
        detector = AISGapDetector()
        score = detector._compute_gap_score(2.0, 10.0)
        assert 0.0 <= score <= 1.0


class TestStaticSpacingDetector:
    def _make_obs(self, mmsi: str, interval_minutes: float, count: int) -> list[AisObservation]:
        base = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)
        return [
            AisObservation(
                mmsi=mmsi,
                timestamp=base + timedelta(minutes=i * interval_minutes),
                lat=15.0,
                lon=73.0,
            )
            for i in range(count)
        ]

    def test_static_spacing_detected(self):
        """Perfectly regular intervals → detected."""
        detector = StaticSpacingDetector(tolerance_fraction=0.10)
        obs = self._make_obs("123", 10.0, 6)
        result = detector.detect(obs, 15.1, 73.1, max_distance_km=50)
        assert result is not None
        assert result.is_static_spaced is True

    def test_irregular_no_detection(self):
        """Variable intervals → not detected."""
        base = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)
        obs = [
            AisObservation(mmsi="123", timestamp=base + timedelta(minutes=i * (10 + i * 3)), lat=15.0, lon=73.0)
            for i in range(6)
        ]
        detector = StaticSpacingDetector()
        result = detector.detect(obs, 15.0, 73.0)
        assert result is None

    def test_too_few_observations(self):
        """< 4 observations → no detection."""
        detector = StaticSpacingDetector()
        obs = self._make_obs("123", 10.0, 3)
        result = detector.detect(obs, 15.0, 73.0)
        assert result is None


# ── SmallDetectionAssessor ───────────────────────────────────────────────────


class TestSmallDetectionAssessor:
    def test_sub_threshold(self):
        """Very small detection → HIGH risk."""
        svc = SmallDetectionAssessor()
        result = svc.assess(0.001, 0.1, 0.8)
        assert result.false_positive_risk == "HIGH"
        assert result.is_sub_threshold is True
        assert "MANUAL REVIEW" in result.recommended_action

    def test_small_high_confidence(self):
        """Small but high confidence → MEDIUM risk."""
        svc = SmallDetectionAssessor()
        result = svc.assess(0.03, 0.5, 0.85, wind_speed_knots=8.0)
        assert result.false_positive_risk == "MEDIUM"

    def test_small_low_confidence(self):
        """Small + low confidence → HIGH risk."""
        svc = SmallDetectionAssessor()
        result = svc.assess(0.03, 0.5, 0.5)
        assert result.false_positive_risk == "HIGH"

    def test_large_detection(self):
        """Normal size → LOW risk."""
        svc = SmallDetectionAssessor()
        result = svc.assess(0.5, 2.0, 0.8)
        assert result.false_positive_risk == "LOW"


# ── ExplainableAttribution ───────────────────────────────────────────────────


class TestExplainableAttribution:
    def test_basic_breakdown(self):
        """Produces valid breakdown with all components."""
        svc = ExplainableAttribution()
        features = LookAlikeFeatures(
            mean_intensity_anomaly_db=-4.0,
            wind_speed_knots=10.0,
        )
        breakdown = svc.analyze(
            raw_model_confidence=0.75,
            look_alike_features=features,
            environmental_band="IDEAL",
            environmental_penalty=0.0,
            environmental_explanation="Ideal conditions.",
        )
        assert breakdown.raw_model_confidence == 0.75
        assert 0.0 <= breakdown.adjusted_confidence <= 1.0
        assert breakdown.confidence_band in ("LOW", "MEDIUM", "HIGH")

    def test_no_components(self):
        """Works with no optional components."""
        svc = ExplainableAttribution()
        breakdown = svc.analyze(raw_model_confidence=0.6)
        assert breakdown.adjusted_confidence == pytest.approx(0.6, abs=0.01)

    def test_penalty_reduces_confidence(self):
        """Penalties reduce adjusted confidence."""
        svc = ExplainableAttribution()
        features = LookAlikeFeatures(
            mean_intensity_anomaly_db=-0.5,
            wind_speed_knots=1.0,
        )
        breakdown = svc.analyze(
            raw_model_confidence=0.8,
            look_alike_features=features,
            environmental_band="POOR",
            environmental_penalty=0.25,
        )
        assert breakdown.adjusted_confidence < 0.8

    def test_provenance_dict(self):
        """to_provenance returns valid dict."""
        svc = ExplainableAttribution()
        breakdown = svc.analyze(raw_model_confidence=0.7)
        prov = svc.to_provenance(breakdown)
        assert "raw_model_confidence" in prov
        assert "adjusted_confidence" in prov
        assert "explanations" in prov


# ── SeasonalPriorService ─────────────────────────────────────────────────────


class TestSeasonalPriorService:
    def test_monsoon_high(self):
        """Monsoon months → factor > 1."""
        svc = SeasonalPriorService()
        assert svc.get_prior(7) > 1.0
        assert svc.get_prior(8) > 1.0

    def test_winter_low(self):
        """Winter months → factor < 1."""
        svc = SeasonalPriorService()
        assert svc.get_prior(1) < 1.0
        assert svc.get_prior(12) < 1.0

    def test_adjustment_range(self):
        """Adjustment always in [-0.05, +0.05]."""
        svc = SeasonalPriorService()
        for m in range(1, 13):
            adj = svc.get_adjustment(m)
            assert -0.05 <= adj <= 0.05

    def test_explain(self):
        """Explain returns non-empty string."""
        svc = SeasonalPriorService()
        for m in range(1, 13):
            assert len(svc.explain(m)) > 0


# ── FalsePositiveReviewManager ───────────────────────────────────────────────


class TestFalsePositiveReviewManager:
    def test_create_and_get(self):
        mgr = FalsePositiveReviewManager()
        review = mgr.create_review("INC-001", "look-alike", 0.7)
        assert review.incident_id == "INC-001"
        assert mgr.get_review("INC-001") is review

    def test_update_review(self):
        mgr = FalsePositiveReviewManager()
        mgr.create_review("INC-002")
        updated = mgr.update_review(
            "INC-002",
            review_status="confirmed_false_positive",
            reviewer="analyst1",
            notes="Looks like a low-wind area",
        )
        assert updated is not None
        assert updated.review_status == "confirmed_false_positive"
        assert updated.reviewed_at is not None

    def test_list_pending(self):
        mgr = FalsePositiveReviewManager()
        mgr.create_review("A")
        mgr.create_review("B")
        mgr.update_review("A", review_status="confirmed_true_oil")
        pending = mgr.list_pending()
        assert len(pending) == 1
        assert pending[0].incident_id == "B"

    def test_stats(self):
        mgr = FalsePositiveReviewManager()
        mgr.create_review("A")
        mgr.create_review("B")
        mgr.update_review("A", review_status="confirmed_true_oil")
        assert mgr.stats == {"pending": 1, "confirmed_true_oil": 1}
