from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SEED_DEMO_DATA", "true")
os.environ.setdefault("SCENE_STORAGE_DIR", "./.tmp-tests/scenes")

from app.config import Settings
from app.main import create_app


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url="",  # in-memory repository
        seed_demo_data=True,
        scene_storage_dir=str(tmp_path / "scenes"),
        model_adapter="mock",
        model_threshold=0.5,
        cors_origins="http://localhost:3000",
    )


@pytest.fixture()
def client(settings: Settings):
    app = create_app(settings)
    with TestClient(app) as c:
        yield c
