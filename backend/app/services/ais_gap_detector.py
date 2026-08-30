"""AIS gap detection and static spacing analysis.

Detects suspicious AIS transmission patterns:
- Gaps: periods where AIS transmission stops, then resumes
- Static spacing: suspiciously regular intervals indicating simulated data

These signals enhance false-positive identification:
- Gaps near a detection suggest intentional transponder manipulation
- Static spacing suggests AIS spoofing or synthetic data
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta

from app.domain.ais import AisObservation
from app.domain.entities import AISGapSignal, StaticSpacingDetection

logger = logging.getLogger(__name__)

# GFW returns this when transponder was off
GAP_SENTINEL_VALUE = 91.0  # degrees — outside valid lat/lon range


class AISGapDetector:
    """Detect suspicious AIS transmission gaps near a detection."""

    def __init__(
        self,
        gap_threshold_minutes: float = 30.0,
        max_gap_hours: float = 6.0,
        max_distance_km: float = 100.0,
    ) -> None:
        """Initialize gap detector.

        Args:
            gap_threshold_minutes: Minimum gap duration to consider suspicious.
            max_gap_hours: Maximum gap duration to flag (longer = different cause).
            max_distance_km: Max distance from detection to flag a gap.
        """
        self.gap_threshold_minutes = gap_threshold_minutes
        self.max_gap_hours = max_gap_hours
        self.max_distance_km = max_distance_km

    def detect_gaps(
        self,
        observations: list[AisObservation],
        detection_lat: float,
        detection_lon: float,
        detection_time: datetime,
    ) -> list[AISGapSignal]:
        """Analyze AIS track for suspicious gaps near a detection.

        Looks for gaps in the observation timeline that overlap
        with the detection time window.

        Returns:
            List of AISGapSignal for detected gaps.
        """
        if len(observations) < 2:
            return []

        # Sort by timestamp
        sorted_obs = sorted(observations, key=lambda o: o.timestamp)

        # Check for sentinel values (transponder manipulation indicators)
        sentinel_gaps = self._detect_sentinel_gaps(
            sorted_obs, detection_lat, detection_lon, detection_time
        )

        # Check for temporal gaps
        temporal_gaps = self._detect_temporal_gaps(
            sorted_obs, detection_lat, detection_lon, detection_time
        )

        return sentinel_gaps + temporal_gaps

    def _detect_sentinel_gaps(
        self,
        observations: list[AisObservation],
        detection_lat: float,
        detection_lon: float,
        detection_time: datetime,
    ) -> list[AISGapSignal]:
        """Detect gaps indicated by sentinel values (91.0 lat/lon)."""
        signals: list[AISGapSignal] = []
        gap_start_idx = None

        for i, obs in enumerate(observations):
            is_sentinel = (
                abs(obs.lat - GAP_SENTINEL_VALUE) < 0.01
                or abs(obs.lon - GAP_SENTINEL_VALUE) < 0.01
            )
            if is_sentinel:
                if gap_start_idx is None:
                    gap_start_idx = i
            else:
                if gap_start_idx is not None:
                    # Gap from first sentinel to current non-sentinel
                    gap_duration = (
                        obs.timestamp - observations[gap_start_idx].timestamp
                    )
                    gap_hours = gap_duration.total_seconds() / 3600

                    if gap_hours * 60 >= self.gap_threshold_minutes:
                        # For sentinel values (91.0), use detection location
                        # since sentinel coordinates are not real positions
                        is_sentinel_gap = (
                            abs(observations[gap_start_idx].lat - GAP_SENTINEL_VALUE) < 0.01
                            or abs(observations[gap_start_idx].lon - GAP_SENTINEL_VALUE) < 0.01
                        )
                        if is_sentinel_gap:
                            distance = self._haversine(
                                detection_lat, detection_lon,
                                detection_lat, detection_lon,
                            )
                            # Sentinel gaps near detection → assume 0km
                            distance = 0.0
                        else:
                            distance = self._haversine(
                                detection_lat, detection_lon,
                                observations[gap_start_idx].lat, observations[gap_start_idx].lon,
                            )
                        if distance <= self.max_distance_km:
                            score = self._compute_gap_score(gap_hours, distance)
                            signals.append(AISGapSignal(
                                mmsi=observations[gap_start_idx].mmsi,
                                gap_start=observations[gap_start_idx].timestamp,
                                gap_end=obs.timestamp,
                                gap_duration_hours=round(gap_hours, 2),
                                distance_to_detection_km=round(distance, 2),
                                gap_score=round(score, 3),
                                explanation=(
                                    f"Sentinel value (91.0) gap detected: "
                                    f"transponder likely disabled for {gap_hours:.1f}h "
                                    f"({distance:.1f}km from detection)"
                                ),
                            ))
                    gap_start_idx = None

        return signals

    def _detect_temporal_gaps(
        self,
        observations: list[AisObservation],
        detection_lat: float,
        detection_lon: float,
        detection_time: datetime,
    ) -> list[AISGapSignal]:
        """Detect temporal gaps in AIS transmission."""
        signals: list[AISGapSignal] = []

        for i in range(len(observations) - 1):
            gap = observations[i + 1].timestamp - observations[i].timestamp
            gap_hours = gap.total_seconds() / 3600

            if gap_hours * 60 < self.gap_threshold_minutes:
                continue
            if gap_hours > self.max_gap_hours:
                continue

            mid_lat = (observations[i].lat + observations[i + 1].lat) / 2
            mid_lon = (observations[i].lon + observations[i + 1].lon) / 2
            distance = self._haversine(
                detection_lat, detection_lon, mid_lat, mid_lon
            )

            if distance > self.max_distance_km:
                continue

            score = self._compute_gap_score(gap_hours, distance)
            signals.append(AISGapSignal(
                mmsi=observations[i].mmsi,
                gap_start=observations[i].timestamp,
                gap_end=observations[i + 1].timestamp,
                gap_duration_hours=round(gap_hours, 2),
                distance_to_detection_km=round(distance, 2),
                gap_score=round(score, 3),
                explanation=(
                    f"Temporal gap: {gap_hours:.1f}h without AIS transmission "
                    f"({distance:.1f}km from detection)"
                ),
            ))

        return signals

    def _compute_gap_score(self, gap_hours: float, distance_km: float) -> float:
        """Compute suspiciousness score for a gap.

        Higher score = more suspicious = more likely intentional manipulation.
        """
        # Duration factor: longer gaps are more suspicious (up to a point)
        duration_score = min(1.0, gap_hours / 3.0)  # max at 3 hours

        # Distance factor: closer gaps are more suspicious
        distance_score = max(0.0, 1.0 - distance_km / self.max_distance_km)

        return 0.6 * duration_score + 0.4 * distance_score

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class StaticSpacingDetector:
    """Detect suspiciously regular AIS transmission intervals (spoofing indicator)."""

    def __init__(
        self,
        expected_interval_minutes: float = 10.0,
        tolerance_fraction: float = 0.05,
    ) -> None:
        self.expected_interval = expected_interval_minutes
        self.tolerance = tolerance_fraction

    def detect(
        self,
        observations: list[AisObservation],
        detection_lat: float,
        detection_lon: float,
        max_distance_km: float = 50.0,
    ) -> StaticSpacingDetection | None:
        """Check if AIS track shows static spacing anomaly.

        Real AIS transmissions have variable intervals due to
        transponder behavior, satellite pass timing, etc.
        Suspiciously regular intervals suggest synthetic/spoofed data.
        """
        if len(observations) < 4:
            return None

        sorted_obs = sorted(observations, key=lambda o: o.timestamp)

        # Compute intervals
        intervals = []
        for i in range(len(sorted_obs) - 1):
            delta = (sorted_obs[i + 1].timestamp - sorted_obs[i].timestamp)
            intervals.append(delta.total_seconds() / 60.0)

        if not intervals:
            return None

        # Check for suspiciously regular intervals
        mean_interval = sum(intervals) / len(intervals)
        if mean_interval == 0:
            return None

        # Coefficient of variation — low = very regular
        variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
        cv = (variance ** 0.5) / mean_interval if mean_interval > 0 else 1.0

        # Distance from detection
        lats = [o.lat for o in sorted_obs]
        lons = [o.lon for o in sorted_obs]
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)

        distance = AISGapDetector._haversine(
            detection_lat, detection_lon, center_lat, center_lon
        )

        is_static = cv < self.tolerance and distance <= max_distance_km

        if is_static:
            confidence = max(0.0, 1.0 - cv / self.tolerance)
            return StaticSpacingDetection(
                mmsi=sorted_obs[0].mmsi,
                is_static_spaced=True,
                spacing_interval_minutes=round(mean_interval, 1),
                distance_km=round(distance, 2),
                confidence=round(confidence, 3),
                explanation=(
                    f"Static spacing detected: {mean_interval:.1f}min intervals "
                    f"(CV={cv:.4f}) at {distance:.1f}km from detection. "
                    f"Regular intervals suggest possible AIS spoofing."
                ),
            )

        return None
