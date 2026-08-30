"""Domain entities — pure Python, framework-free.

These are the objects the service layer manipulates. Persistence details
(PostGIS rows vs. in-memory records) stay behind the repository interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

GeoJSONDict = dict[str, Any]

IncidentStatus = Literal["completed", "processing", "review"]
SceneStatus = Literal["processed", "processing", "queued", "failed"]


def confidence_level(confidence: float) -> str:
    """Mirrors src/lib/mock-data/incidents.ts:confidenceLevel on the frontend."""
    if confidence >= 0.8:
        return "HIGH"
    if confidence >= 0.65:
        return "MEDIUM"
    return "LOW"


@dataclass
class SatelliteSceneRecord:
    id: str                       # product-style scene identifier
    platform: str                 # e.g. Sentinel-1A
    sensor: str = "SAR C-band"
    acquisition_mode: str = "IW"
    polarisation: str = "VV + VH"
    acquired_at: datetime | None = None
    processed_at: datetime | None = None
    footprint: tuple[float, float, float, float] | None = None  # west, south, east, north
    status: SceneStatus = "queued"
    image_path: str | None = None
    is_demo: bool = False

    # ---- real-catalogue ingestion metadata (Phase 2) --------------------
    product_id: str | None = None          # catalogue UUID (e.g. CDSE OData id)
    product_name: str | None = None        # full SAFE-style product name
    source_provider: str = "mock"          # 'copernicus' | 'mock'
    orbit_state: str | None = None         # ascending / descending
    absolute_orbit: int | None = None
    relative_orbit: int | None = None
    download_url: str | None = None        # authenticated acquisition reference
    file_size_bytes: int | None = None     # advertised product size
    product_type: str | None = None        # e.g. IW_GRDH_1S
    thumbnail_url: str | None = None       # public quicklook reference
    geometry: GeoJSONDict | None = None    # exact footprint polygon (EPSG:4326)
    preview_path: str | None = None        # stored web preview artifact key/path
    pipeline_state: str | None = None      # detailed job state (PipelineJobState)
    metadata_extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SpillIncident:
    id: str
    scene_id: str
    confidence: float             # MODEL CONFIDENCE (0..1), from inference only
    area_km2: float
    perimeter_km: float
    centroid_lon: float
    centroid_lat: float
    geometry: GeoJSONDict         # GeoJSON Polygon (EPSG:4326)
    bbox: tuple[float, float, float, float]  # west, south, east, north
    detected_at: datetime
    region: str
    location_description: str
    satellite: str
    model_name: str
    model_version: str
    status: IncidentStatus = "completed"
    wind_speed_kts: float | None = None
    estimated_volume_tons: float | None = None  # never fabricated; None unless estimated
    is_demo: bool = False

    @property
    def level(self) -> str:
        return confidence_level(self.confidence)


@dataclass
class ModelRun:
    id: str
    scene_id: str
    model_name: str
    model_version: str
    started_at: datetime
    completed_at: datetime | None = None
    inference_time_ms: int | None = None
    status: Literal["running", "completed", "failed"] = "running"
    error_message: str | None = None


@dataclass
class RepositoryState:
    """Bookkeeping so tests/startup know whether demo seed data was applied."""
    seeded_demo: bool = False
    incidents: list[SpillIncident] = field(default_factory=list)


# ── Phase 8: Intelligence / False-Positive Mitigation ────────────────────────


@dataclass
class LookAlikeFeatures:
    """Extracted features for look-alike classification.

    Each feature is a scalar value derived from the SAR detection patch
    and its surrounding context.  The classifier uses these to distinguish
    true oil spills from natural look-alikes (biogenic slicks, low-wind
    areas, current shears, rain cells).
    """

    # Intensity statistics (dB relative to local background)
    mean_intensity_anomaly_db: float = 0.0
    std_intensity_anomaly_db: float = 0.0
    min_intensity_anomaly_db: float = 0.0

    # Texture (GLCM-inspired simple metrics)
    local_contrast: float = 0.0
    edge_density: float = 0.0

    # Shape / geometry (normalized by patch size)
    aspect_ratio: float = 1.0
    elongation: float = 0.0
    compactness: float = 0.0

    # Context
    distance_to_coast_km: float = 0.0
    is_near_shipping_lane: bool = False
    water_depth_m: float = 0.0

    # Wind / environmental (from ERA5 at detection time)
    wind_speed_knots: float = 0.0
    wind_direction_deg: float = 0.0

    # SAR imaging geometry
    incidence_angle_deg: float = 0.0
    pass_direction: str = ""  # ascending / descending

    # Derived
    look_alike_probability: float = 0.0  # classifier output P(look-alike)
    texture_status: str = "UNAVAILABLE"  # UNAVAILABLE | COMPUTED


@dataclass
class ConfidenceBreakdown:
    """Component-wise confidence attribution for a single detection.

    Each factor contributes to the overall adjusted confidence.
    The breakdown is fully explainable — every number has a traceable origin.
    """

    raw_model_confidence: float = 0.0
    look_alike_penalty: float = 0.0
    environmental_penalty: float = 0.0
    small_detection_penalty: float = 0.0
    calibration_shift: float = 0.0
    seasonal_prior_adjustment: float = 0.0
    adjusted_confidence: float = 0.0
    confidence_band: str = "LOW"  # LOW / MEDIUM / HIGH

    # Explanations (human-readable)
    look_alike_explanation: str = ""
    environmental_explanation: str = ""
    small_detection_explanation: str = ""

    def compute_adjusted(self) -> float:
        """Recompute adjusted_confidence from components."""
        adj = (
            self.raw_model_confidence
            - self.look_alike_penalty
            - self.environmental_penalty
            - self.small_detection_penalty
            + self.calibration_shift
            + self.seasonal_prior_adjustment
        )
        self.adjusted_confidence = max(0.0, min(1.0, adj))
        if self.adjusted_confidence >= 0.8:
            self.confidence_band = "HIGH"
        elif self.adjusted_confidence >= 0.65:
            self.confidence_band = "MEDIUM"
        else:
            self.confidence_band = "LOW"
        return self.adjusted_confidence


@dataclass
class AISGapSignal:
    """Signal derived from AIS transmission gaps near a detection."""

    mmsi: str
    gap_start: datetime | None = None
    gap_end: datetime | None = None
    gap_duration_hours: float = 0.0
    distance_to_detection_km: float = 0.0
    gap_score: float = 0.0  # 0..1, higher = more suspicious
    explanation: str = ""


@dataclass
class StaticSpacingDetection:
    """Detection of static spacing anomaly in AIS track."""

    mmsi: str
    is_static_spaced: bool = False
    spacing_interval_minutes: float = 0.0
    distance_km: float = 0.0
    confidence: float = 0.0
    explanation: str = ""


@dataclass
class SmallDetectionAssessment:
    """Assessment of detection reliability for small-area slicks."""

    area_km2: float = 0.0
    pixel_count: int = 0
    is_sub_threshold: bool = False
    false_positive_risk: str = "LOW"  # LOW / MEDIUM / HIGH
    explanation: str = ""
    recommended_action: str = ""


@dataclass
class FalsePositiveReview:
    """Human or automated review status for a false-positive candidate."""

    incident_id: str
    review_status: str = "pending"  # pending / confirmed_true_oil / confirmed_false_positive / uncertain
    reviewer: str = ""
    notes: str = ""
    reviewed_at: datetime | None = None
    automated_classification: str = ""
    automated_confidence: float = 0.0
