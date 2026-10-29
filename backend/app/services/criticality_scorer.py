"""Operational Criticality Score service for SAGAR WATCH.

This computes an operational priority index (0-100) to help operators
decide which incident requires attention first.

IMPORTANT: This is NOT:
- probability of oil being present
- detection confidence
- attribution probability
- environmental damage prediction

This IS:
- operational priority index based on available evidence
- deterministic, explainable, traceable to actual data sources
- heuristic weights (NOT scientifically validated)

The calculation uses 7 conceptual factors, but coastal/sensitive-area
risk is currently unavailable. When factors are unavailable, the score
is normalized across available factors only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.schemas.criticality import CriticalityFactorResponse, CriticalityResponse


# ── Factor Definitions ─────────────────────────────────────────────────
# These are operational heuristics, NOT scientifically validated thresholds.

FACTOR_WEIGHTS = {
    "spill_size": 0.20,
    "detection_confidence": 0.15,
    "coastal_sensitive_risk": 0.20,
    "environmental_spreading": 0.15,
    "spill_age": 0.10,
    "projected_drift_impact": 0.10,
    "ais_traffic_evidence": 0.10,
}

# Severity classification thresholds
SEVERITY_THRESHOLDS = [
    (0, 29, "LOW", "ROUTINE MONITORING"),
    (30, 59, "MID", "REVIEW WHEN AVAILABLE"),
    (60, 79, "HIGH", "PRIORITY REVIEW"),
    (80, 100, "CRITICAL", "IMMEDIATE REVIEW"),
]

METHODOLOGY_VERSION = "1.0.0-mvp"


# ── Normalization Helpers ──────────────────────────────────────────────

def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp a value to [min_val, max_val]. Never returns NaN or Infinity."""
    if not math.isfinite(value):
        return min_val
    return max(min_val, min(max_val, value))


def _normalize_linear(value: float, low: float, high: float) -> float:
    """Normalize value to 0-1 using linear interpolation between low and high."""
    if high == low:
        return 0.0
    normalized = (value - low) / (high - low)
    return _clamp(normalized)


def _normalize_log(value: float, low: float, high: float) -> float:
    """Normalize value to 0-1 using log scale (for values with large dynamic range)."""
    if value <= 0 or high <= low:
        return 0.0
    log_val = math.log(value + 1)
    log_low = math.log(low + 1)
    log_high = math.log(high + 1)
    if log_high == log_low:
        return 0.0
    normalized = (log_val - log_low) / (log_high - log_low)
    return _clamp(normalized)


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float, returning default for None/NaN/Infinity."""
    if value is None:
        return default
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ── Factor Scorers ─────────────────────────────────────────────────────
# Each scorer returns (score_0_100, available, source, explanation)

def _score_spill_size(area_km2: float | None) -> tuple[float, bool, str, str]:
    """Score based on spill area. Larger spills = higher priority.

    Thresholds (operational heuristics):
    - 0 km² → 0
    - 1 km² → 30
    - 5 km² → 70
    - 10+ km² → 100
    """
    area = _safe_float(area_km2)
    if area is None or area_km2 is None:
        return (0.0, False, "incident.area_km2", "Spill area data unavailable")

    score = _normalize_log(area, 0, 10) * 100
    explanation = f"Spill area: {area:.2f} km²"
    if area < 1:
        explanation += " (small detection)"
    elif area < 5:
        explanation += " (moderate size)"
    else:
        explanation += " (large spill)"

    return (score, True, "incident.area_km2", explanation)


def _score_detection_confidence(
    adjusted_confidence: float | None,
    raw_confidence: float | None,
) -> tuple[float, bool, str, str]:
    """Score based on detection confidence. Higher confidence = higher priority.

    Uses adjusted confidence (after look-alike, environmental penalties).
    Thresholds:
    - 0.0 → 0
    - 0.5 → 50
    - 1.0 → 100
    """
    adj = _safe_float(adjusted_confidence)
    raw = _safe_float(raw_confidence)

    if adj == 0.0 and raw == 0.0 and adjusted_confidence is None and raw_confidence is None:
        return (0.0, False, "intelligence.confidence_breakdown.adjusted_confidence", "Confidence data unavailable")

    score = adj * 100
    explanation = f"Adjusted confidence: {adj:.1%} (raw: {raw:.1%})"
    return (score, True, "intelligence.confidence_breakdown.adjusted_confidence", explanation)


def _score_environmental_spreading(
    wind_speed_knots: float | None,
    current_speed_ms: float | None,
) -> tuple[float, bool, str, str]:
    """Score based on environmental conditions that promote spreading.

    Higher wind/current = more spreading potential = higher priority.

    Thresholds (operational heuristics):
    - Wind: 0 kts → 0, 15 kts → 50, 30+ kts → 100
    - Current: 0 m/s → 0, 0.5 m/s → 50, 1.0+ m/s → 100

    Marked unavailable when BOTH wind and current are missing.
    Zero values (0.0, 0.0) are valid data — not missing.
    """
    if wind_speed_knots is None and current_speed_ms is None:
        return (
            0.0,
            False,
            "intelligence.environmentalReliability",
            "Environmental data unavailable (wind and current both missing)",
        )

    wind = _safe_float(wind_speed_knots)
    current = _safe_float(current_speed_ms)

    wind_score = _normalize_linear(wind, 0, 30) * 100
    current_score = _normalize_linear(current, 0, 1.0) * 100

    # Weighted average: wind 60%, current 40%
    score = wind_score * 0.6 + current_score * 0.4

    explanation = f"Wind: {wind:.1f} kts, Current: {current:.2f} m/s"
    if wind > 15 or current > 0.5:
        explanation += " (elevated spreading risk)"
    else:
        explanation += " (low spreading risk)"

    return (score, True, "intelligence.environmentalReliability", explanation)


def _score_spill_age(
    uncertainty_hours: float | None,
    source_earliest: str | None,
    source_latest: str | None,
) -> tuple[float, bool, str, str]:
    """Score based on estimated release window / spill age.

    Older spills with larger time uncertainty = higher priority
    (harder to locate source, more urgent to investigate).

    Thresholds (operational heuristics):
    - 0 hours → 0
    - 4 hours → 40
    - 8+ hours → 100
    """
    unc_hours = _safe_float(uncertainty_hours)

    if unc_hours == 0.0 and uncertainty_hours is None:
        return (0.0, False, "drift.uncertainty_hours", "Time uncertainty data unavailable")

    score = _normalize_linear(unc_hours, 0, 8) * 100
    explanation = f"Release window uncertainty: {unc_hours:.1f} hours"
    if unc_hours > 6:
        explanation += " (wide window, source harder to pinpoint)"
    elif unc_hours > 3:
        explanation += " (moderate uncertainty)"
    else:
        explanation += " (narrow window)"

    return (score, True, "drift.uncertainty_hours", explanation)


def _score_projected_drift_impact(
    uncertainty_km: float | None,
    drift_confidence: float | None,
) -> tuple[float, bool, str, str]:
    """Score based on projected drift impact zone.

    Higher spatial uncertainty = larger potential impact = higher priority.

    Thresholds (operational heuristics):
    - 0 km → 0
    - 25 km → 50
    - 50+ km → 100
    """
    unc_km = _safe_float(uncertainty_km)
    conf = _safe_float(drift_confidence)

    if unc_km == 0.0 and uncertainty_km is None:
        return (0.0, False, "drift.uncertainty_km", "Drift uncertainty data unavailable")

    # Score based on spatial uncertainty
    score = _normalize_linear(unc_km, 0, 50) * 100

    # Adjust by drift confidence (low confidence = less reliable prediction = slightly lower score)
    confidence_factor = 0.7 + 0.3 * conf  # 0.7 to 1.0
    score = score * confidence_factor

    explanation = f"Spatial uncertainty: {unc_km:.1f} km, Drift confidence: {conf:.1%}"
    if unc_km > 25:
        explanation += " (large impact zone)"
    else:
        explanation += " (contained zone)"

    return (score, True, "drift.uncertainty_km", explanation)


def _score_ais_traffic_evidence(
    candidates: list[dict[str, Any]] | None,
    candidate_count: int | None,
) -> tuple[float, bool, str, str]:
    """Score based on AIS vessel traffic evidence.

    Higher attribution scores and more candidates = more evidence = higher priority.

    Thresholds (operational heuristics):
    - No candidates → 0
    - Best score 0.3 → 30
    - Best score 0.7 → 70
    - Best score 1.0 → 100
    """
    if not candidates or candidate_count is None or candidate_count == 0:
        return (0.0, False, "attribution.candidates", "AIS correlation data unavailable")

    # Find best attribution score
    best_score = 0.0
    for c in candidates:
        attr_score = _safe_float(c.get("attributionScore", 0))
        best_score = max(best_score, attr_score)

    # Score based on best attribution
    score = best_score * 100

    # Bonus for having multiple candidates (more traffic = more evidence)
    n_candidates = min(len(candidates), 5)
    candidate_bonus = n_candidates * 2  # +2 per candidate, max +10
    score = min(100, score + candidate_bonus)

    explanation = f"Best attribution: {best_score:.1%}, {len(candidates)} candidate(s)"
    if best_score > 0.5:
        explanation += " (strong vessel association)"
    elif best_score > 0.2:
        explanation += " (moderate vessel association)"
    else:
        explanation += " (weak vessel association)"

    return (score, True, "attribution.candidates", explanation)


def _score_coastal_sensitive_risk() -> tuple[float, bool, str, str]:
    """Score based on proximity to coastlines and sensitive areas.

    STATUS: UNAVAILABLE — requires coastline geometry lookup.
    Natural Earth or GSHHG data needed with Shapely spatial indexing.
    """
    return (
        0.0,
        False,
        "NOT_AVAILABLE",
        "Coastal/sensitive-area risk requires coastline geometry data (not yet implemented)",
    )


# ── Main Scorer ────────────────────────────────────────────────────────

def compute_criticality(
    *,
    incident: dict[str, Any] | None = None,
    drift: dict[str, Any] | None = None,
    attribution: dict[str, Any] | None = None,
    intelligence: dict[str, Any] | None = None,
) -> CriticalityResponse:
    """Compute the Operational Criticality Score for an incident.

    This is a deterministic, explainable priority index.
    All thresholds are operational heuristics, NOT scientifically validated.

    Args:
        incident: SpillIncident data (area_km2, confidence, etc.)
        drift: DriftResponse data (uncertainty_km, uncertainty_hours, etc.)
        attribution: AttributionResponse data (candidates, etc.)
        intelligence: DetectionIntelligenceResponse data (confidence breakdown, etc.)

    Returns:
        CriticalityResponse with score, level, action, and factor breakdown.
    """
    incident = incident or {}
    drift = drift or {}
    attribution = attribution or {}
    intelligence = intelligence or {}

    # Extract data from nested structures
    conf_breakdown = intelligence.get("confidenceBreakdown", {})
    env_reliability = intelligence.get("environmentalReliability", {})

    # ── Compute each factor ───────────────────────────────────────────
    factors: list[CriticalityFactorResponse] = []

    # Factor 1: Spill Size (weight: 20%)
    spill_score, spill_avail, spill_src, spill_expl = _score_spill_size(
        incident.get("areaKm2")
    )
    factors.append(CriticalityFactorResponse(
        name="spill_size",
        label="Spill Size",
        score=spill_score,
        max_score=100,
        weight=FACTOR_WEIGHTS["spill_size"],
        normalized_weight=0.0,  # computed below
        available=spill_avail,
        source=spill_src,
        explanation=spill_expl,
    ))

    # Factor 2: Detection Confidence (weight: 15%)
    det_score, det_avail, det_src, det_expl = _score_detection_confidence(
        conf_breakdown.get("adjustedConfidence"),
        conf_breakdown.get("rawModelConfidence"),
    )
    factors.append(CriticalityFactorResponse(
        name="detection_confidence",
        label="Detection Confidence",
        score=det_score,
        max_score=100,
        weight=FACTOR_WEIGHTS["detection_confidence"],
        normalized_weight=0.0,
        available=det_avail,
        source=det_src,
        explanation=det_expl,
    ))

    # Factor 3: Coastal/Sensitive Risk (weight: 20%) — UNAVAILABLE
    coast_score, coast_avail, coast_src, coast_expl = _score_coastal_sensitive_risk()
    factors.append(CriticalityFactorResponse(
        name="coastal_sensitive_risk",
        label="Coastal/Sensitive Risk",
        score=coast_score,
        max_score=100,
        weight=FACTOR_WEIGHTS["coastal_sensitive_risk"],
        normalized_weight=0.0,
        available=coast_avail,
        source=coast_src,
        explanation=coast_expl,
    ))

    # Factor 4: Environmental Spreading (weight: 15%)
    env_score, env_avail, env_src, env_expl = _score_environmental_spreading(
        env_reliability.get("windSpeedKnots"),
        env_reliability.get("currentSpeedMs"),
    )
    factors.append(CriticalityFactorResponse(
        name="environmental_spreading",
        label="Environmental Spreading",
        score=env_score,
        max_score=100,
        weight=FACTOR_WEIGHTS["environmental_spreading"],
        normalized_weight=0.0,
        available=env_avail,
        source=env_src,
        explanation=env_expl,
    ))

    # Factor 5: Spill Age (weight: 10%)
    age_score, age_avail, age_src, age_expl = _score_spill_age(
        drift.get("uncertaintyHours"),
        drift.get("sourceEarliest"),
        drift.get("sourceLatest"),
    )
    factors.append(CriticalityFactorResponse(
        name="spill_age",
        label="Release Window Uncertainty",
        score=age_score,
        max_score=100,
        weight=FACTOR_WEIGHTS["spill_age"],
        normalized_weight=0.0,
        available=age_avail,
        source=age_src,
        explanation=age_expl,
    ))

    # Factor 6: Projected Drift Impact (weight: 10%)
    drift_score, drift_avail, drift_src, drift_expl = _score_projected_drift_impact(
        drift.get("uncertaintyKm"),
        drift.get("confidence"),
    )
    factors.append(CriticalityFactorResponse(
        name="projected_drift_impact",
        label="Projected Drift Impact",
        score=drift_score,
        max_score=100,
        weight=FACTOR_WEIGHTS["projected_drift_impact"],
        normalized_weight=0.0,
        available=drift_avail,
        source=drift_src,
        explanation=drift_expl,
    ))

    # Factor 7: AIS/Traffic Evidence (weight: 10%)
    candidates = attribution.get("candidates", [])
    ais_score, ais_avail, ais_src, ais_expl = _score_ais_traffic_evidence(
        candidates,
        attribution.get("candidateCount"),
    )
    factors.append(CriticalityFactorResponse(
        name="ais_traffic_evidence",
        label="AIS Traffic Evidence",
        score=ais_score,
        max_score=100,
        weight=FACTOR_WEIGHTS["ais_traffic_evidence"],
        normalized_weight=0.0,
        available=ais_avail,
        source=ais_src,
        explanation=ais_expl,
    ))

    # ── Normalize weights across available factors ────────────────────
    available_weight = sum(f.weight for f in factors if f.available)
    unavailable_count = sum(1 for f in factors if not f.available)
    available_count = len(factors) - unavailable_count

    if available_weight > 0:
        for f in factors:
            if f.available:
                f.normalized_weight = f.weight / available_weight
            else:
                f.normalized_weight = 0.0

    # ── Compute weighted score ────────────────────────────────────────
    raw_score = sum(f.score * f.normalized_weight for f in factors if f.available)

    # Clamp to 0-100 and convert to integer
    final_score = int(_clamp(raw_score, 0, 100))

    # ── Determine severity level ──────────────────────────────────────
    level = "LOW"
    action = "ROUTINE MONITORING"
    for min_s, max_s, lvl, act in SEVERITY_THRESHOLDS:
        if min_s <= final_score <= max_s:
            level = lvl
            action = act
            break

    # ── Build normalization note ──────────────────────────────────────
    if unavailable_count > 0:
        normalization_note = (
            f"{unavailable_count} factor(s) unavailable. Score normalized across "
            f"{available_count} available factors (total weight: {available_weight:.0%}). "
            f"Missing factors: {', '.join(f.label for f in factors if not f.available)}"
        )
    else:
        normalization_note = "All 7 factors available. No weight redistribution needed."

    # ── Determine methodology ─────────────────────────────────────────
    methodology = (
        f"Operational Criticality Index v{METHODOLOGY_VERSION}. "
        f"Heuristic weights (NOT scientifically validated). "
        f"Factors trace to: incident metadata, drift model output, "
        f"AIS correlation results, and detection intelligence. "
        f"Coastal/sensitive-area factor pending coastline geometry integration."
    )

    return CriticalityResponse(
        score=final_score,
        level=level,
        action=action,
        methodology=methodology,
        factors=factors,
        available_factor_count=available_count,
        total_factor_count=len(factors),
        normalization_note=normalization_note,
    )
