"""Explainable, coverage-aware AIS candidate ranking; never a culpability decision."""
from __future__ import annotations

from datetime import datetime, timezone
import math
import pandas as pd

from oil_spill_intel.contracts import ScoreComponent, VesselCandidate

KM_PER_LAT_DEGREE = 111.32


def _distance_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    return math.hypot((lon1 - lon2) * KM_PER_LAT_DEGREE * math.cos(math.radians((lat1 + lat2) / 2)), (lat1 - lat2) * KM_PER_LAT_DEGREE)


def _normalise_ais(ais: pd.DataFrame) -> pd.DataFrame:
    required = {"mmsi", "timestamp", "lat", "lon"}; missing = required - set(ais.columns)
    if missing: raise ValueError(f"AIS missing columns: {sorted(missing)}")
    frame = ais.copy(); frame["mmsi"] = frame["mmsi"].astype(str); frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True); frame = frame.dropna(subset=["lat", "lon", "timestamp"]).sort_values(["mmsi", "timestamp"])
    return frame


def rank_vessels(ais: pd.DataFrame, source_lonlat: tuple[float, float], release_start: datetime, release_end: datetime, max_distance_km: float = 80.0, coverage_known: bool = False) -> list[VesselCandidate]:
    """Rank candidates by source-window proximity, timing, vessel context and AIS continuity.

    Scores are prioritisation signals. They are explicitly not probabilities of
    culpability and must be reviewed with source/hindcast uncertainty.
    """
    frame = _normalise_ais(ais)
    start = pd.Timestamp(release_start).tz_convert("UTC") if release_start.tzinfo else pd.Timestamp(release_start, tz="UTC")
    end = pd.Timestamp(release_end).tz_convert("UTC") if release_end.tzinfo else pd.Timestamp(release_end, tz="UTC")
    window = frame[(frame.timestamp >= start - pd.Timedelta(hours=6)) & (frame.timestamp <= end + pd.Timedelta(hours=6))].copy()
    candidates: list[VesselCandidate] = []
    risk_types = {"tanker": 1.0, "cargo": 0.65, "oil": 1.0, "chemical": 0.85}
    for mmsi, vessel in window.groupby("mmsi"):
        vessel = vessel.sort_values("timestamp"); distances = vessel.apply(lambda r: _distance_km(float(r.lon), float(r.lat), *source_lonlat), axis=1)
        nearest_idx = distances.idxmin(); nearest = vessel.loc[nearest_idx]; min_distance = float(distances.min())
        if min_distance > max_distance_km: continue
        proximity = math.exp(-min_distance / 25)
        nearest_time = nearest.timestamp; center = start + (end - start) / 2; elapsed_hours = abs((nearest_time - center).total_seconds()) / 3600
        timing = math.exp(-elapsed_hours / max((end - start).total_seconds() / 7200, 1))
        vessel_type = str(nearest.get("vessel_type", "unknown")).lower(); type_prior = risk_types.get(vessel_type, 0.35)
        gaps = vessel.timestamp.diff().dt.total_seconds().div(3600); gap = float(gaps.max()) if gaps.notna().any() else 0.0
        gap_score = min(gap / 24, 1.0) if coverage_known else 0.0
        components = [
            ScoreComponent("source_proximity", round(proximity, 4), 0.45, f"Nearest AIS point was {min_distance:.1f} km from the inferred source region."),
            ScoreComponent("time_alignment", round(timing, 4), 0.25, "Measures alignment of the nearest point with the inferred release window."),
            ScoreComponent("vessel_context", round(type_prior, 4), 0.15, f"Context prior for declared vessel type '{vessel_type}'. It is not proof of discharge risk."),
            ScoreComponent("ais_continuity_gap", round(gap_score, 4), 0.15 if coverage_known else 0.0, "AIS gap contributes only when receiver coverage/latency has been independently established."),
        ]
        score = sum(c.value * c.weight for c in components); candidates.append(VesselCandidate(str(mmsi), 0, round(score, 4), components, [float(nearest.lon), float(nearest.lat)], vessel_type, gap if gap else None))
    candidates.sort(key=lambda x: x.suspicion_score, reverse=True)
    for rank, candidate in enumerate(candidates, start=1): candidate.rank = rank
    return candidates
