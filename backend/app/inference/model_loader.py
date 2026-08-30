"""Model adapter factory.

Selects the active OilSpillModel implementation from configuration
(MODEL_ADAPTER env var). Adding the real trained model later means adding a
`torch` branch here that instantiates the teammate's adapter class — nothing
else in the application changes.
"""

from __future__ import annotations

import logging

from app.config import Settings, get_settings
from app.inference.base import OilSpillModel
from app.inference.mock_adapter import MockOilSpillModel

logger = logging.getLogger(__name__)


def create_model(settings: Settings) -> OilSpillModel:
    adapter = settings.model_adapter.strip().lower()

    if adapter == "mock":
        return MockOilSpillModel(settings)

    if adapter == "torch":
        from app.inference.torch_adapter import TorchOilSpillModel
        return TorchOilSpillModel(settings)

    raise ValueError(f"Unknown MODEL_ADAPTER: {adapter!r} (expected 'mock' or 'torch')")


class ModelHandle:
    """Lazy, cached model instance shared by the application."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model: OilSpillModel | None = None

    @property
    def model_info(self) -> dict[str, str]:
        m = self._model
        return {
            "model": m.name if m else self._settings.model_name,
            "version": m.version if m else self._settings.model_version,
            "device": self._settings.model_device,
            "threshold": str(self._settings.model_threshold),
        }

    def get(self) -> OilSpillModel:
        if self._model is None:
            self._model = create_model(self._settings)
            self._model.load_model()
        return self._model


_handle: ModelHandle | None = None


def get_model_handle() -> ModelHandle:
    global _handle
    if _handle is None:
        _handle = ModelHandle(get_settings())
    return _handle


def set_model_handle(handle: ModelHandle) -> None:
    """Used by tests to inject a controlled adapter."""
    global _handle
    _handle = handle
