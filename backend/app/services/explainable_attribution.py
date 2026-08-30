"""Explainable attribution service.

Combines all Phase 8 components into a transparent confidence breakdown
and attribution analysis.  Every number has a traceable origin.
"""

from __future__ import annotations

import logging
from datetime import datetime

from app.domain.entities import (
    ConfidenceBreakdown,
    LookAlikeFeatures,
    SmallDetectionAssessment,
)
from app.services.ais_gap_detector import AISGapDetector, StaticSpacingDetector
from app.services.confidence_calibrator import ConfidenceCalibrator
from app.services.environmental_reliability import EnvironmentalReliability
from app.services.look_alike_classifier import LookAlikeClassifier
from app.services.small_detection_assessor import SmallDetectionAssessor

logger = logging.getLogger(__name__)


class ExplainableAttribution:
    """Generate explainable confidence breakdown for a detection.

    Orchestrates:
    1. Look-alike classification → penalty
    2. Environmental reliability → penalty
    3. Small detection assessment → penalty
    4. Confidence calibration → shift
    5. Produces ConfidenceBreakdown with human-readable explanations
    """

    def __init__(
        self,
        look_alike_classifier: LookAlikeClassifier | None = None,
        environmental_reliability: EnvironmentalReliability | None = None,
        confidence_calibrator: ConfidenceCalibrator | None = None,
        small_detection_assessor: SmallDetectionAssessor | None = None,
    ) -> None:
        self.look_alike = look_alike_classifier or LookAlikeClassifier()
        self.env_reliability = environmental_reliability or EnvironmentalReliability()
        self.calibrator = confidence_calibrator or ConfidenceCalibrator()
        self.small_detector = small_detection_assessor or SmallDetectionAssessor()

    def analyze(
        self,
        *,
        raw_model_confidence: float,
        look_alike_features: LookAlikeFeatures | None = None,
        environmental_band: str | None = None,
        environmental_penalty: float = 0.0,
        environmental_explanation: str = "",
        small_detection: SmallDetectionAssessment | None = None,
        seasonal_prior_adjustment: float = 0.0,
    ) -> ConfidenceBreakdown:
        """Produce a full confidence breakdown.

        All parameters are optional — the service gracefully handles
        missing data by skipping that component.
        """
        breakdown = ConfidenceBreakdown(raw_model_confidence=raw_model_confidence)

        # ── Look-alike penalty ───────────────────────────────────────────
        if look_alike_features is not None:
            classified = self.look_alike.classify(look_alike_features)
            p_la = classified.look_alike_probability
            breakdown.look_alike_penalty = round(p_la * 0.20, 4)  # max 20% penalty
            breakdown.look_alike_explanation = (
                f"Look-alike probability: {p_la:.1%}. "
                f"Penalty: -{breakdown.look_alike_penalty:.1%} from model confidence."
            )
        else:
            breakdown.look_alike_penalty = 0.0
            breakdown.look_alike_explanation = "Look-alike analysis not available."

        # ── Environmental penalty ────────────────────────────────────────
        if environmental_band is not None:
            breakdown.environmental_penalty = round(environmental_penalty, 4)
            breakdown.environmental_explanation = environmental_explanation or (
                f"Environmental band: {environmental_band}. "
                f"Penalty: -{breakdown.environmental_penalty:.1%}."
            )
        else:
            breakdown.environmental_penalty = 0.0
            breakdown.environmental_explanation = "Environmental analysis not available."

        # ── Small detection penalty ──────────────────────────────────────
        if small_detection is not None:
            if small_detection.false_positive_risk == "HIGH":
                breakdown.small_detection_penalty = 0.15
            elif small_detection.false_positive_risk == "MEDIUM":
                breakdown.small_detection_penalty = 0.05
            else:
                breakdown.small_detection_penalty = 0.0
            breakdown.small_detection_explanation = small_detection.explanation
        else:
            breakdown.small_detection_penalty = 0.0
            breakdown.small_detection_explanation = "Small detection analysis not available."

        # ── Calibration shift ────────────────────────────────────────────
        if self.calibrator.is_fitted:
            calibrated = self.calibrator.calibrate(raw_model_confidence)
            breakdown.calibration_shift = round(
                calibrated - raw_model_confidence, 4
            )
        else:
            breakdown.calibration_shift = 0.0

        # ── Seasonal prior ───────────────────────────────────────────────
        breakdown.seasonal_prior_adjustment = round(seasonal_prior_adjustment, 4)

        # ── Compute final ────────────────────────────────────────────────
        breakdown.compute_adjusted()

        logger.debug(
            "Explainable attribution: raw=%.3f adjusted=%.3f "
            "(LL=%.3f, env=%.3f, small=%.3f, cal=%.3f, seasonal=%.3f)",
            raw_model_confidence,
            breakdown.adjusted_confidence,
            breakdown.look_alike_penalty,
            breakdown.environmental_penalty,
            breakdown.small_detection_penalty,
            breakdown.calibration_shift,
            breakdown.seasonal_prior_adjustment,
        )

        return breakdown

    def to_provenance(self, breakdown: ConfidenceBreakdown) -> dict:
        """Convert breakdown to a provenance dict for storage/API."""
        return {
            "raw_model_confidence": breakdown.raw_model_confidence,
            "adjusted_confidence": breakdown.adjusted_confidence,
            "confidence_band": breakdown.confidence_band,
            "look_alike_penalty": breakdown.look_alike_penalty,
            "environmental_penalty": breakdown.environmental_penalty,
            "small_detection_penalty": breakdown.small_detection_penalty,
            "calibration_shift": breakdown.calibration_shift,
            "seasonal_prior_adjustment": breakdown.seasonal_prior_adjustment,
            "explanations": {
                "look_alike": breakdown.look_alike_explanation,
                "environmental": breakdown.environmental_explanation,
                "small_detection": breakdown.small_detection_explanation,
            },
        }
