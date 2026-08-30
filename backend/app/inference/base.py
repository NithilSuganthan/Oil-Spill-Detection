"""MODEL ADAPTER INTERFACE — the only contract between this service and any
oil-spill ML model.

The application depends on `OilSpillModel`, never on a concrete architecture
(U-Net, DeepLab, etc.). The trained model from the ML team will implement this
interface (see docs/ml-integration-contract.md for exactly what to provide).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

import numpy as np

from app.domain.entities import SatelliteSceneRecord


@dataclass
class SceneInput:
    """A scene ready for preprocessing.

    intensity: 2-D SAR backscatter array (any float dtype; e.g. sigma0 in dB
               or linear power). Spatial metadata travels with it.
    transform: affine mapping pixel -> world coords of `intensity`.
    crs:       coordinate reference system of the raster.
    """

    scene: SatelliteSceneRecord
    intensity: np.ndarray
    transform: object            # rasterio.transform.Affine
    crs: object                  # rasterio CRS or EPSG int


@dataclass
class PreprocessResult:
    """Model-ready tensor(s) plus whatever metadata predict() needs."""

    input_data: np.ndarray                       # shape depends on the real model
    spatial_transform: object                    # affine of the ORIGINAL raster
    crs: object
    meta: dict = field(default_factory=dict)


@dataclass
class PredictionResult:
    """Probability mask aligned with the original raster grid."""

    probability_mask: np.ndarray                 # float32, values in [0, 1]
    inference_time_ms: int
    meta: dict = field(default_factory=dict)


class OilSpillModel(abc.ABC):
    """Abstract oil-spill detection model.

    Lifecycle:
        model = <Adapter>(settings)
        model.load_model()
        pre   = model.preprocess(scene_input)
        pred  = model.predict(pre)          -> probability mask [0..1]

    Post-processing (threshold -> cleanup -> polygons -> georeferencing ->
    area/confidence) is handled by app/services/inference_service.py using the
    shared geospatial pipeline so EVERY adapter gets identical treatment.
    """

    name: str = "abstract"
    version: str = "0"

    @abc.abstractmethod
    def load_model(self) -> None:
        """Load weights / initialize runtime. Idempotent."""

    @abc.abstractmethod
    def preprocess(self, scene_input: SceneInput) -> PreprocessResult:
        """Convert raw SAR intensity into model input tensors."""

    @abc.abstractmethod
    def predict(self, data: PreprocessResult) -> PredictionResult:
        """Run inference; return per-pixel spill probability in [0, 1]."""
