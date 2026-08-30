"""Small detection assessment for oil spill detections.

Evaluates the reliability of small-area detections that may be:
- Sub-pixel or near-resolution-limit features
- Noise artifacts
- Genuine small spills (bilge dumps, minor leaks)

Small detections are common sources of false positives in SAR oil spill
monitoring. This service provides risk assessment and recommendations.
"""

from __future__ import annotations

import logging

from app.domain.entities import SmallDetectionAssessment

logger = logging.getLogger(__name__)


class SmallDetectionAssessor:
    """Assess reliability of small-area SAR detections."""

    # Thresholds (km²)
    SUB_THRESHOLD_AREA = 0.005   # < 5 pixels at 10m resolution
    SMALL_AREA = 0.05            # < 50 pixels
    MINIMUM_RELIABLE = 0.1       # below this, high FP risk

    # Typical minimum oil spill size visible on SAR (km²)
    PHYSICAL_MINIMUM_KM2 = 0.001  # ~10m x 100m minimum slick

    def assess(
        self,
        area_km2: float,
        perimeter_km: float,
        model_confidence: float,
        wind_speed_knots: float = 0.0,
    ) -> SmallDetectionAssessment:
        """Assess a small detection for reliability.

        Args:
            area_km2: Detection area in km².
            perimeter_km: Detection perimeter in km.
            model_confidence: Raw model confidence (0..1).
            wind_speed_knots: Wind speed at detection time.

        Returns:
            SmallDetectionAssessment with risk level and recommendations.
        """
        # Pixel count approximation (10m resolution → 0.0001 km² per pixel)
        pixel_count = int(area_km2 / 0.0001)

        is_sub_threshold = area_km2 < self.SUB_THRESHOLD_AREA
        is_small = area_km2 < self.SMALL_AREA

        # Risk assessment
        if is_sub_threshold:
            risk = "HIGH"
            explanation = (
                f"Detection area {area_km2:.4f} km² ({pixel_count} pixels) "
                f"is below the sub-pixel threshold ({self.SUB_THRESHOLD_AREA} km²). "
                f"High probability of noise artifact or processing error. "
                f"Minimum physically meaningful oil slick is ~{self.PHYSICAL_MINIMUM_KM2} km²."
            )
            action = (
                "MANUAL REVIEW REQUIRED: Sub-pixel detections should be verified "
                "by a human analyst before classification as potential spills. "
                "Consider discarding if model confidence < 0.7."
            )
        elif is_small:
            if model_confidence > 0.8 and wind_speed_knots > 3.0:
                risk = "MEDIUM"
                explanation = (
                    f"Detection area {area_km2:.3f} km² ({pixel_count} pixels) "
                    f"is small but model confidence is high ({model_confidence:.2f}) "
                    f"with adequate wind ({wind_speed_knots:.1f} kts). "
                    f"May be a genuine small spill (e.g., bilge dump)."
                )
                action = (
                    "RECOMMENDED: Cross-reference with AIS data. "
                    "Small, high-confidence detections near shipping lanes "
                    "are often genuine bilge dumps."
                )
            else:
                risk = "HIGH"
                explanation = (
                    f"Detection area {area_km2:.3f} km² ({pixel_count} pixels) "
                    f"is small with moderate confidence ({model_confidence:.2f}). "
                    f"Small detections are common false-positive sources."
                )
                action = (
                    "MANUAL REVIEW REQUIRED: Small detections with moderate confidence "
                    "have high false-positive rates. Verify with environmental conditions "
                    "and AIS correlation."
                )
        else:
            risk = "LOW"
            explanation = (
                f"Detection area {area_km2:.3f} km² ({pixel_count} pixels) "
                f"is above the minimum reliable threshold. "
                f"Detection reliability is acceptable."
            )
            action = "No special action required."

        logger.debug(
            "Small detection assessment: area=%.4f km² risk=%s",
            area_km2,
            risk,
        )

        return SmallDetectionAssessment(
            area_km2=area_km2,
            pixel_count=pixel_count,
            is_sub_threshold=is_sub_threshold,
            false_positive_risk=risk,
            explanation=explanation,
            recommended_action=action,
        )
