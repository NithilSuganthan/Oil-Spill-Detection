"""Environmental data reliability assessment.

Evaluates whether environmental conditions (wind, current, wave) are
within the reliable detection window for oil spills on SAR imagery.

Key principle: oil spill detectability on SAR is highly dependent on
environmental conditions.  Certain conditions make detection unreliable
or impossible, regardless of model confidence.

Detection reliability bands:
- IDEAL: wind 3-10 m/s, moderate current → high detectability
- GOOD: wind 2-12 m/s → detectability OK with minor degradation
- MARGINAL: wind < 2 or 12-15 m/s → degraded, increased look-alike risk
- POOR: wind > 15 m/s or < 1 m/s → unreliable detection
"""

from __future__ import annotations

import logging

from app.services.environmental_provider import EnvironmentalConditions

logger = logging.getLogger(__name__)


class EnvironmentalReliability:
    """Assess detection reliability based on environmental conditions."""

    # Wind speed thresholds (knots)
    WIND_IDEAL_LOW = 6.0    # ~3 m/s
    WIND_IDEAL_HIGH = 20.0  # ~10 m/s
    WIND_GOOD_LOW = 4.0     # ~2 m/s
    WIND_GOOD_HIGH = 25.0   # ~13 m/s
    WIND_MARGINAL_HIGH = 30.0  # ~15 m/s

    def assess(
        self,
        conditions: EnvironmentalConditions,
    ) -> tuple[str, float, str]:
        """Assess environmental reliability.

        Returns:
            (band, penalty, explanation)
            band: "IDEAL" | "GOOD" | "MARGINAL" | "POOR"
            penalty: 0.0 to 0.3 (subtracted from model confidence)
            explanation: human-readable explanation
        """
        # Compute wind speed from u/v components (m/s → knots)
        wind_ms = (conditions.wind_u ** 2 + conditions.wind_v ** 2) ** 0.5
        wind_kts = wind_ms / 0.514444  # m/s → knots
        current_speed_ms = (
            conditions.current_u ** 2 + conditions.current_v ** 2
        ) ** 0.5
        wave_height = conditions.wave_height or 0.0

        # ── Wind assessment ──────────────────────────────────────────────
        if wind_kts < 1.0:
            band = "POOR"
            penalty = 0.30
            explanation = (
                f"Wind speed {wind_kts:.1f} knots (< 1 knot): "
                "near-calm conditions produce very low backscatter, "
                "making oil spills indistinguishable from low-wind areas. "
                "Detection reliability is very poor."
            )
        elif wind_kts < self.WIND_GOOD_LOW:
            band = "MARGINAL"
            penalty = 0.15
            explanation = (
                f"Wind speed {wind_kts:.1f} knots ({wind_kts * 0.514:.1f} m/s): "
                "low wind conditions reduce SAR sensitivity to surface films. "
                "Oil spills may appear weak or absent. "
                "Increased risk of false negatives."
            )
        elif wind_kts < self.WIND_IDEAL_LOW:
            band = "GOOD"
            penalty = 0.05
            explanation = (
                f"Wind speed {wind_kts:.1f} knots ({wind_kts * 0.514:.1f} m/s): "
                "slightly below ideal range but detectability remains acceptable."
            )
        elif wind_kts <= self.WIND_IDEAL_HIGH:
            band = "IDEAL"
            penalty = 0.0
            explanation = (
                f"Wind speed {wind_kts:.1f} knots ({wind_kts * 0.514:.1f} m/s): "
                "within ideal detection window. "
                "Oil spills produce strong damping signatures on SAR."
            )
        elif wind_kts <= self.WIND_GOOD_HIGH:
            band = "GOOD"
            penalty = 0.05
            explanation = (
                f"Wind speed {wind_kts:.1f} knots ({wind_kts * 0.514:.1f} m/s): "
                "slightly above ideal range but detectability remains acceptable."
            )
        elif wind_kts <= self.WIND_MARGINAL_HIGH:
            band = "MARGINAL"
            penalty = 0.15
            explanation = (
                f"Wind speed {wind_kts:.1f} knots ({wind_kts * 0.514:.1f} m/s): "
                "high wind generates surface roughening that can mask oil signatures. "
                "Detection confidence is degraded."
            )
        else:
            band = "POOR"
            penalty = 0.30
            explanation = (
                f"Wind speed {wind_kts:.1f} knots ({wind_kts * 0.514:.1f} m/s): "
                "very high wind conditions significantly degrade SAR oil detection. "
                "Surface roughening dominates the backscatter signal. "
                "Detection reliability is very poor."
            )

        # ── Wave height modifier ─────────────────────────────────────────
        if wave_height > 3.0:
            penalty = min(0.30, penalty + 0.10)
            explanation += (
                f" Significant wave height {wave_height:.1f}m further degrades reliability."
            )

        # ── Current speed modifier ───────────────────────────────────────
        if current_speed_ms > 1.0:
            explanation += (
                f" Strong current ({current_speed_ms:.2f} m/s) may disperse oil rapidly."
            )

        logger.debug(
            "Environmental reliability: band=%s penalty=%.2f wind=%.1fkts",
            band,
            penalty,
            wind_kts,
        )
        return band, penalty, explanation
