"""Confidence calibrator using Platt scaling.

Converts raw model confidence scores into calibrated probabilities.
Uses a simple logistic calibration: P(y=1|s) = 1 / (1 + exp(A*s + B))

Default parameters are initialized to identity mapping (no calibration).
When a calibration dataset is available, ``fit()`` computes optimal A, B.
"""

from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)


class ConfidenceCalibrator:
    """Platt scaling calibrator for model confidence scores.

    Usage:
        calibrator = ConfidenceCalibrator()
        # Optional: calibrate on labeled data
        # calibrator.fit(scores=[0.8, 0.3, ...], labels=[1, 0, ...])
        calibrated = calibrator.calibrate(0.75)  # → calibrated probability
    """

    def __init__(self, a: float = 1.0, b: float = 0.0) -> None:
        """Initialize with optional pre-computed Platt parameters.

        Args:
            a: Platt scaling parameter A (slope). Default 1.0.
            b: Platt scaling parameter B (intercept). Default 0.0.

        NOTE: Default A=1.0, B=0.0 is NOT an identity mapping.
        When is_fitted is False, callers should set calibration_shift=0
        and calibrated_confidence=null.
        """
        self.a = a
        self.b = b
        self._is_fitted = (a != 1.0 or b != 0.0)

    def calibrate(self, raw_score: float) -> float:
        """Apply Platt scaling to a raw confidence score.

        Args:
            raw_score: Raw model confidence in [0, 1].

        Returns:
            Calibrated probability in [0, 1].
        """
        # Clamp input
        s = max(0.0, min(1.0, raw_score))

        # Platt scaling: P = 1 / (1 + exp(-(A*s + B)))
        logit = -(self.a * s + self.b)
        # Numerical stability
        if logit > 500:
            return 0.0
        if logit < -500:
            return 1.0
        return 1.0 / (1.0 + math.exp(logit))

    def fit(
        self,
        scores: list[float],
        labels: list[int],
        learning_rate: float = 0.01,
        max_iter: int = 1000,
    ) -> None:
        """Fit Platt scaling parameters on labeled validation data.

        Args:
            scores: List of raw model confidence scores.
            labels: List of binary labels (1 = true spill, 0 = false positive).
            learning_rate: SGD learning rate.
            max_iter: Maximum iterations.
        """
        if len(scores) != len(labels) or len(scores) < 10:
            logger.warning(
                "Insufficient data for calibration fitting (need >=10 samples, got %d). "
                "Using identity mapping.",
                len(scores),
            )
            self.a, self.b = 1.0, 0.0
            self._is_fitted = False
            return

        # Target: use softened labels for numerical stability
        n_pos = sum(labels)
        n_neg = len(labels) - n_pos
        t_pos = (n_pos + 1) / (n_pos + 2) if n_pos > 0 else 0.5
        t_neg = 1 / (n_neg + 2) if n_neg > 0 else 0.5
        targets = [t_pos if l == 1 else t_neg for l in labels]

        # SGD over Platt parameters
        a, b = 0.0, 0.0
        for _ in range(max_iter):
            da, db = 0.0, 0.0
            for s, t in zip(scores, targets):
                p = self._sigmoid(a * s + b)
                err = p - t
                da += err * s
                db += err
            a -= learning_rate * da / len(scores)
            b -= learning_rate * db / len(scores)

        self.a = a
        self.b = b
        self._is_fitted = True
        logger.info("Platt calibration fitted: A=%.4f, B=%.4f", a, b)

    @staticmethod
    def _sigmoid(x: float) -> float:
        if x > 500:
            return 1.0
        if x < -500:
            return 0.0
        return 1.0 / (1.0 + math.exp(-x))

    @property
    def is_fitted(self) -> bool:
        return self._is_fitted

    def to_dict(self) -> dict[str, float]:
        return {"a": self.a, "b": self.b, "fitted": self._is_fitted}

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> ConfidenceCalibrator:
        return cls(a=d.get("a", 1.0), b=d.get("b", 0.0))
