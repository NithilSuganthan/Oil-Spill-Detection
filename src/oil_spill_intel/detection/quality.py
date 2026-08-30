"""Environmental observation quality assessment; this is not an oil classifier."""
from __future__ import annotations

from oil_spill_intel.contracts import QualityFlag


def assess_observation_quality(
    wind_speed_mps: float | None,
    wave_height_m: float | None,
    incidence_angle_deg: float | None,
) -> tuple[float, list[QualityFlag]]:
    """Return look-alike risk in [0, 1] and explicit flags.

    Thresholds are conservative rules from the supplied research context. They
    must be re-calibrated for a production geography/model.
    """
    risk = 0.15
    flags: list[QualityFlag] = []
    if wind_speed_mps is None:
        risk += 0.15
        flags.append(QualityFlag("wind_missing", "warning", "Wind is unavailable; SAR contrast confidence is reduced."))
    elif wind_speed_mps < 3:
        risk += 0.45
        flags.append(QualityFlag("low_wind_look_alike", "warning", "Low wind can create dark look-alikes and weaken oil discrimination."))
    elif wind_speed_mps > 12:
        risk += 0.30
        flags.append(QualityFlag("rough_sea_false_negative", "warning", "High wind may fragment or mask a real slick."))
    if wave_height_m is not None and wave_height_m > 2.5:
        risk += 0.20
        flags.append(QualityFlag("high_wave_state", "warning", "High waves reduce reliability; absence of a detection is not evidence of absence."))
    if incidence_angle_deg is not None and not 21 <= incidence_angle_deg <= 45:
        risk += 0.12
        flags.append(QualityFlag("incidence_angle_edge", "info", "Incidence angle is outside the strongest reported operating range."))
    return min(risk, 1.0), flags
