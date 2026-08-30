"""Model adapter interface + MOCK adapter behaviour."""

from __future__ import annotations

import numpy as np
import pytest
from rasterio.transform import from_origin

from app.config import Settings
from app.inference.base import OilSpillModel, PreprocessResult, SceneInput
from app.inference.mock_adapter import MockOilSpillModel
from app.domain.entities import SatelliteSceneRecord


@pytest.fixture()
def mock_model() -> MockOilSpillModel:
    m = MockOilSpillModel(Settings(model_threshold=0.5))
    m.load_model()
    return m


def _scene_input(dark_blob: bool = True) -> SceneInput:
    rng = np.random.default_rng(3)
    sea = -8.0 + rng.normal(0.0, 2.0, size=(128, 128))
    if dark_blob:
        yy, xx = np.mgrid[0:128, 0:128]
        ellipse = ((xx - 64) / 30.0) ** 2 + ((yy - 64) / 14.0) ** 2
        sea[ellipse < 1.0] -= 6.0
    scene = SatelliteSceneRecord(id="TEST_SCENE", platform="Sentinel-1A")
    return SceneInput(
        scene=scene,
        intensity=sea,
        transform=from_origin(500000.0, 4000000.0, 40.0, 40.0),
        crs="EPSG:32643",
    )


def test_mock_adapter_satisfies_interface(mock_model):
    assert isinstance(mock_model, OilSpillModel)
    for method in ("load_model", "preprocess", "predict"):
        assert callable(getattr(mock_model, method))


def test_mock_adapter_is_labeled_mock(mock_model):
    assert "Mock" in mock_model.name or "mock" in mock_model.name.lower()
    # the class docstring must carry an explicit non-real disclaimer
    assert "NOT A TRAINED MODEL" in (type(mock_model).__doc__ or "").upper()


def test_preprocess_normalizes_to_unit_range(mock_model):
    pre = mock_model.preprocess(_scene_input())
    assert pre.input_data.min() >= 0.0
    assert pre.input_data.max() <= 1.0
    assert pre.spatial_transform is not None


def test_predict_returns_probability_mask(mock_model):
    pre = mock_model.preprocess(_scene_input())
    result = mock_model.predict(pre)
    prob = result.probability_mask
    assert prob.shape == (128, 128)
    assert prob.dtype == np.float32
    assert float(prob.min()) >= 0.0 and float(prob.max()) <= 1.0
    assert result.inference_time_ms >= 0


def test_mock_adapter_detects_dark_regions(mock_model):
    """Dark blob region must get higher probability than open sea."""
    si = _scene_input(dark_blob=True)
    pre = mock_model.preprocess(si)
    prob = mock_model.predict(pre).probability_mask
    blob_mean = float(prob[55:75, 50:80].mean())
    sea_mean = float(prob[5:20, 5:20].mean())
    assert blob_mean > sea_mean


def test_unknown_adapter_rejected():
    from app.inference.model_loader import create_model

    with pytest.raises(ValueError):
        create_model(Settings(model_adapter="does-not-exist"))


def test_torch_adapter_loads_when_checkpoint_exists():
    """Torch adapter is now real — verify it creates without error."""
    from app.inference.model_loader import create_model

    adapter = create_model(Settings(model_adapter="torch"))
    assert adapter.name == "TinyUNet"


def test_torch_adapter_predict_without_loading_raises():
    """Calling predict before load_model should raise."""
    from app.inference.model_loader import create_model

    adapter = create_model(Settings(model_adapter="torch"))
    with pytest.raises(RuntimeError, match="not loaded"):
        adapter.predict(PreprocessResult(
            input_data=np.zeros((2, 64, 64), dtype=np.float32),
            spatial_transform=None, crs=None, meta={},
        ))
