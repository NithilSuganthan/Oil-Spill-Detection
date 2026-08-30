"""Look-alike classifier for oil spill detections.

Distinguishes true oil spills from natural SAR look-alikes:
- Biogenic surface slicks (natural surfactants)
- Low-wind areas (reduced backscatter)
- Current shear zones
- Rain cells (volume scattering)
- Natural wind shadows near coastlines

Uses deterministic feature extraction + simple threshold-based scoring
(no external ML dependency).  Can be upgraded to a trained model later.
"""

from __future__ import annotations

import logging
import math

from app.domain.entities import LookAlikeFeatures

logger = logging.getLogger(__name__)


class LookAlikeClassifier:
    """Deterministic look-alike classification using extracted features.

    Each feature is scored against known thresholds from SAR literature
    (Liu et al. 2017, Topouzelis et al. 2019, Saloghlu et al. 2023).
    The output is P(look-alike) ∈ [0, 1].
    """

    # Feature importance weights (sum to 1.0)
    WEIGHTS = {
        "intensity_anomaly": 0.25,
        "texture": 0.15,
        "shape": 0.20,
        "context": 0.15,
        "wind": 0.25,
    }

    def classify(self, features: LookAlikeFeatures) -> LookAlikeFeatures:
        """Classify a detection patch as look-alike or real spill.

        Returns the same features object with ``look_alike_probability`` set.
        """
        scores: dict[str, float] = {}

        # ── Intensity anomaly score ──────────────────────────────────────
        # Oil spills typically show strong negative anomaly (< -3 dB)
        # Look-alikes are weaker (-1 to -3 dB)
        mean_db = features.mean_intensity_anomaly_db
        if mean_db > -1.0:
            scores["intensity_anomaly"] = 0.9  # very weak anomaly → likely look-alike
        elif mean_db > -2.0:
            scores["intensity_anomaly"] = 0.6
        elif mean_db > -3.0:
            scores["intensity_anomaly"] = 0.3
        else:
            scores["intensity_anomaly"] = 0.1  # strong anomaly → likely real

        # High variance within patch → mixed surface → possible look-alike
        if features.std_intensity_anomaly_db > 2.0:
            scores["intensity_anomaly"] = min(1.0, scores["intensity_anomaly"] + 0.2)

        # ── Texture score ────────────────────────────────────────────────
        # Oil spills have smooth texture (low contrast, low edge density)
        # Look-alikes (wind, rain) have rough texture
        # NOTE: local_contrast and edge_density are NOT currently extracted
        # from the SAR patch. When unavailable, texture_score defaults to 0.0
        # and texture_status remains UNAVAILABLE.
        texture_score = 0.0
        if features.local_contrast != 0.0 or features.edge_density != 0.0:
            # Texture features were actually computed (not just defaults)
            if features.local_contrast > 0.5:
                texture_score += 0.5
            if features.edge_density > 0.3:
                texture_score += 0.5
            features.texture_status = "COMPUTED"
        else:
            features.texture_status = "UNAVAILABLE"
        scores["texture"] = min(1.0, texture_score)

        # ── Shape score ──────────────────────────────────────────────────
        # Oil spills are elongated (high aspect ratio, high elongation)
        # Look-alikes tend to be rounder or irregular
        shape_score = 0.0
        if features.aspect_ratio < 2.0:
            shape_score += 0.4  # not elongated → suspicious
        if features.compactness > 0.7:
            shape_score += 0.3  # very compact → suspicious
        if features.elongation < 0.3:
            shape_score += 0.3  # not elongated → suspicious
        scores["shape"] = min(1.0, shape_score)

        # ── Context score ────────────────────────────────────────────────
        # Biogenic slicks are common in coastal areas, shipping lanes
        context_score = 0.0
        if features.distance_to_coast_km < 10.0:
            context_score += 0.4  # near coast → more likely biogenic
        if features.is_near_shipping_lane:
            context_score += 0.3  # shipping lane → possible bilge dumping
        if features.water_depth_m < 50.0:
            context_score += 0.3  # shallow water → more biogenic activity
        scores["context"] = min(1.0, context_score)

        # ── Wind score ───────────────────────────────────────────────────
        # Low wind (< 3 m/s) → look-alike (low wind backscatter reduction)
        # High wind (> 10 m/s) → look-alike (wind roughening masks oil)
        wind_ms = features.wind_speed_knots * 0.514444  # knots → m/s
        if wind_ms < 3.0:
            scores["wind"] = 0.9  # very low wind → almost certainly look-alike
        elif wind_ms < 5.0:
            scores["wind"] = 0.6  # low wind → probable look-alike
        elif wind_ms < 10.0:
            scores["wind"] = 0.1  # ideal wind window → likely real
        elif wind_ms < 15.0:
            scores["wind"] = 0.4  # moderate wind → mixed
        else:
            scores["wind"] = 0.7  # very high wind → possible look-alike

        # ── Weighted sum ─────────────────────────────────────────────────
        p_look_alike = sum(
            self.WEIGHTS[k] * scores[k] for k in self.WEIGHTS
        )
        p_look_alike = max(0.0, min(1.0, p_look_alike))

        features.look_alike_probability = round(p_look_alike, 4)
        logger.debug(
            "Look-alike classification: P=%.3f  scores=%s",
            p_look_alike,
            {k: round(v, 3) for k, v in scores.items()},
        )
        return features


def extract_look_alike_features(
    detection_patch_db: list[list[float]] | None = None,
    *,
    area_km2: float = 0.0,
    perimeter_km: float = 0.0,
    distance_to_coast_km: float = 0.0,
    is_near_shipping_lane: bool = False,
    water_depth_m: float = 0.0,
    wind_speed_knots: float = 0.0,
    wind_direction_deg: float = 0.0,
    incidence_angle_deg: float = 0.0,
    pass_direction: str = "",
) -> LookAlikeFeatures:
    """Extract look-alike features from a detection patch and context.

    If ``detection_patch_db`` is None, uses defaults (useful for testing).
    In production, the patch is the VV dB values around the detection.
    """
    features = LookAlikeFeatures(
        distance_to_coast_km=distance_to_coast_km,
        is_near_shipping_lane=is_near_shipping_lane,
        water_depth_m=water_depth_m,
        wind_speed_knots=wind_speed_knots,
        wind_direction_deg=wind_direction_deg,
        incidence_angle_deg=incidence_angle_deg,
        pass_direction=pass_direction,
    )

    # Shape from area/perimeter (computed regardless of patch)
    if area_km2 > 0 and perimeter_km > 0:
        # Compactness: 4π·A / P² (1.0 = perfect circle)
        features.compactness = round(
            (4 * math.pi * area_km2) / (perimeter_km ** 2), 4
        )
        # Elongation: 1 - min_axis/max_axis (approximation from A and P)
        features.elongation = round(
            max(0.0, 1.0 - (4 * math.pi * area_km2) / (perimeter_km ** 2)), 4
        )
        # Aspect ratio approximation
        features.aspect_ratio = round(
            max(1.0, perimeter_km / (2 * math.sqrt(math.pi * area_km2))), 2
        )

    if detection_patch_db is None or not detection_patch_db:
        return features

    # Flatten patch
    flat = [v for row in detection_patch_db for v in row]
    if not flat:
        return features

    import statistics

    features.mean_intensity_anomaly_db = round(statistics.mean(flat), 3)
    features.std_intensity_anomaly_db = round(
        statistics.stdev(flat) if len(flat) > 1 else 0.0, 3
    )
    features.min_intensity_anomaly_db = round(min(flat), 3)

    return features
