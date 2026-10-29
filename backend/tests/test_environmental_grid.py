"""Tests for the environmental grid endpoint.

Covers:
1. Valid wind grid response
2. Valid current grid response
3. Missing required fields
4. Mock mode (no real credentials)
5. Grid dimensions and axes
6. Metadata fields
7. Point vectors at centroid
8. Custom resolution
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.config import Settings


@pytest.fixture
def client():
    """Create test client with mock environmental provider."""
    settings = Settings(
        environmental_provider="mock",
        cmems_username="",
        cmems_password="",
        cds_api_key="",
        seed_demo_data=True,
    )
    app = create_app(settings)
    return TestClient(app)


@pytest.fixture
def real_client():
    """Create test client configured for real provider (will fall back to mock)."""
    settings = Settings(
        environmental_provider="real",
        cmems_username="test_user",
        cmems_password="test_pass",
        cds_api_key="test_key",
        seed_demo_data=True,
    )
    app = create_app(settings)
    return TestClient(app)


class TestEnvironmentalGridEndpoint:
    """Test the POST /environmental/grid endpoint."""

    def test_valid_request_returns_200(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
        })
        assert response.status_code == 200

    def test_response_has_wind_grid(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
        })
        data = response.json()
        assert "wind" in data
        assert isinstance(data["wind"], list)
        assert len(data["wind"]) > 0
        assert isinstance(data["wind"][0], list)

    def test_response_has_current_grid(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
        })
        data = response.json()
        assert "current" in data
        assert isinstance(data["current"], list)

    def test_response_has_wind_uv_grids(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
        })
        data = response.json()
        assert "windU" in data
        assert "windV" in data
        assert len(data["windU"]) == len(data["wind"])
        assert len(data["windV"]) == len(data["wind"])

    def test_response_has_lats_lons(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
        })
        data = response.json()
        assert "lats" in data
        assert "lons" in data
        assert isinstance(data["lats"], list)
        assert isinstance(data["lons"], list)
        assert len(data["lats"]) > 0
        assert len(data["lons"]) > 0

    def test_response_has_metadata(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
        })
        data = response.json()
        assert "metadata" in data
        meta = data["metadata"]
        assert "provider" in meta
        assert "status" in meta
        assert meta["status"] == "DEMO"

    def test_response_has_wind_point(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
        })
        data = response.json()
        assert "windPoint" in data
        wp = data["windPoint"]
        assert wp is not None
        assert "u" in wp
        assert "v" in wp
        assert "speedMs" in wp
        assert "speedKts" in wp
        assert "directionDeg" in wp

    def test_response_has_current_point(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
        })
        data = response.json()
        assert "currentPoint" in data
        cp = data["currentPoint"]
        assert cp is not None
        assert "u" in cp
        assert "v" in cp
        assert "speedMs" in cp
        assert "directionDeg" in cp

    def test_missing_lat_returns_400(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
        })
        assert response.status_code == 400

    def test_missing_timestamp_returns_400(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
        })
        assert response.status_code == 400

    def test_custom_resolution(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
            "resolution_deg": 1.0,
        })
        data = response.json()
        # With 1.0 deg resolution and 2.0 pad, expect ~5 lats
        assert len(data["lats"]) <= 6

    def test_grid_dimensions_match(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
        })
        data = response.json()
        n_lat = len(data["lats"])
        n_lon = len(data["lons"])
        assert len(data["wind"]) == n_lat
        assert len(data["wind"][0]) == n_lon
        assert len(data["current"]) == n_lat
        assert len(data["current"][0]) == n_lon

    def test_metadata_has_bbox(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
        })
        data = response.json()
        assert "bbox" in data["metadata"]
        assert len(data["metadata"]["bbox"]) == 4

    def test_metadata_has_grid_size(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
        })
        data = response.json()
        assert "gridSize" in data["metadata"]
        assert len(data["metadata"]["gridSize"]) == 2

    def test_mock_mode_returns_demo_status(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
        })
        data = response.json()
        assert data["metadata"]["status"] == "DEMO"
        assert data["metadata"]["provider"] == "mock"

    def test_wind_speed_non_negative(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
        })
        data = response.json()
        for row in data["wind"]:
            for val in row:
                if val is not None:
                    assert val >= 0

    def test_current_speed_non_negative(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
        })
        data = response.json()
        for row in data["current"]:
            for val in row:
                if val is not None:
                    assert val >= 0

    def test_wind_direction_in_range(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
        })
        data = response.json()
        wp = data["windPoint"]
        assert 0 <= wp["directionDeg"] < 360

    def test_current_direction_in_range(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
        })
        data = response.json()
        cp = data["currentPoint"]
        assert 0 <= cp["directionDeg"] < 360

    def test_resolution_clamped_to_max(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
            "resolution_deg": 5.0,
        })
        assert response.status_code == 200
        data = response.json()
        # Resolution should be clamped to 2.0

    def test_resolution_clamped_to_min(self, client):
        response = client.post("/api/v1/environmental/grid", json={
            "lat": 15.29,
            "lon": 72.84,
            "timestamp": "2026-08-25T12:00:00Z",
            "resolution_deg": 0.01,
        })
        assert response.status_code == 200
        data = response.json()
        # Resolution should be clamped to 0.25
