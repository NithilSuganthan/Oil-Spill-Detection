"""Tests for the operational alerts system."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from app.config import get_settings
from app.db.memory_repo import InMemoryRepository
from app.domain.entities import SpillIncident
from app.schemas.alert import AlertResponse
from app.services.alert_service import AlertService


@pytest.fixture
def clean_alert_service():
    return AlertService()


@pytest.fixture
def repo_with_incidents():
    repo = InMemoryRepository()
    # High confidence, large area incident -> will produce HIGH/CRITICAL criticality
    high_inc = SpillIncident(
        id="IN-HIGH-001",
        scene_id="SCENE-001",
        confidence=0.92,
        area_km2=18.5,
        perimeter_km=22.0,
        centroid_lon=72.84,
        centroid_lat=15.29,
        geometry={"type": "Polygon", "coordinates": [[[72.8, 15.2], [72.9, 15.2], [72.9, 15.3], [72.8, 15.3], [72.8, 15.2]]]},
        bbox=(72.8, 15.2, 72.9, 15.3),
        detected_at=datetime(2026, 8, 25, 18, 30, tzinfo=timezone.utc),
        region="Arabian Sea",
        location_description="Arabian Sea · Off Maharashtra Coast",
        satellite="Sentinel-1A",
        model_name="OilSpillNet",
        model_version="v1.0",
        wind_speed_kts=9.0,
        is_demo=True,
    )
    # Low confidence, tiny area incident -> will produce LOW/MODERATE criticality
    low_inc = SpillIncident(
        id="IN-LOW-001",
        scene_id="SCENE-002",
        confidence=0.15,
        area_km2=0.05,
        perimeter_km=0.8,
        centroid_lon=75.82,
        centroid_lat=9.61,
        geometry={"type": "Polygon", "coordinates": [[[75.8, 9.6], [75.9, 9.6], [75.9, 9.7], [75.8, 9.7], [75.8, 9.6]]]},
        bbox=(75.8, 9.6, 75.9, 9.7),
        detected_at=datetime(2026, 8, 25, 15, 30, tzinfo=timezone.utc),
        region="Malabar Coast",
        location_description="Arabian Sea · Off Kerala Coast",
        satellite="Sentinel-1B",
        model_name="OilSpillNet",
        model_version="v1.0",
        wind_speed_kts=2.0,
        is_demo=True,
    )
    repo.add_incident(high_inc)
    repo.add_incident(low_inc)
    return repo


def test_initial_empty_state(clean_alert_service):
    assert clean_alert_service.list_alerts() == []
    summary = clean_alert_service.get_summary()
    assert summary.total == 0
    assert summary.critical == 0
    assert summary.high == 0
    assert summary.new == 0


def test_low_moderate_detection_creates_no_alert(clean_alert_service, repo_with_incidents):
    settings = get_settings()
    res = clean_alert_service.analyze_incident_for_alert("IN-LOW-001", repo_with_incidents, settings)
    assert res.created is False
    assert res.alert is None
    assert res.criticality_level in ("LOW", "MODERATE")
    assert clean_alert_service.list_alerts() == []


def test_high_critical_detection_creates_alert(clean_alert_service, repo_with_incidents):
    settings = get_settings()
    res = clean_alert_service.analyze_incident_for_alert("IN-HIGH-001", repo_with_incidents, settings)
    assert res.created is True
    assert res.alert is not None
    assert res.alert.incident_id == "IN-HIGH-001"
    assert res.alert.severity in ("HIGH", "CRITICAL")
    assert res.alert.status == "NEW"
    assert len(clean_alert_service.list_alerts()) == 1


def test_duplicate_protection_reuses_existing_alert(clean_alert_service, repo_with_incidents):
    settings = get_settings()
    res1 = clean_alert_service.analyze_incident_for_alert("IN-HIGH-001", repo_with_incidents, settings)
    assert res1.created is True

    # Re-analyzing must NOT create duplicate
    res2 = clean_alert_service.analyze_incident_for_alert("IN-HIGH-001", repo_with_incidents, settings)
    assert res2.created is False
    assert res2.reused is True
    assert res2.alert is not None
    assert res2.alert.alert_id == res1.alert.alert_id
    assert len(clean_alert_service.list_alerts()) == 1


def test_status_update(clean_alert_service, repo_with_incidents):
    settings = get_settings()
    res = clean_alert_service.analyze_incident_for_alert("IN-HIGH-001", repo_with_incidents, settings)
    alert_id = res.alert.alert_id

    updated = clean_alert_service.update_status(alert_id, "REVIEWING")
    assert updated.status == "REVIEWING"

    updated2 = clean_alert_service.update_status(alert_id, "RESOLVED")
    assert updated2.status == "RESOLVED"


def test_alerts_api_flow(client):
    # 1. GET /alerts initially works
    res = client.get("/api/v1/alerts")
    assert res.status_code == 200
    initial_alerts = res.json()

    # 2. Analyze high-confidence incident from demo seed: IN-250825-001
    analyze_res = client.post("/api/v1/alerts/analyze/IN-250825-001")
    assert analyze_res.status_code == 200
    data = analyze_res.json()
    assert data["criticalityLevel"] in ("HIGH", "CRITICAL")
    assert data["alert"] is not None
    alert_id = data["alert"]["alertId"]

    # 3. GET /alerts now includes this alert
    list_res = client.get("/api/v1/alerts")
    assert list_res.status_code == 200
    alerts = list_res.json()
    assert any(a["alertId"] == alert_id for a in alerts)

    # 4. GET /alerts/{alert_id}
    single_res = client.get(f"/api/v1/alerts/{alert_id}")
    assert single_res.status_code == 200
    assert single_res.json()["alertId"] == alert_id

    # 5. GET /alerts/summary
    summary_res = client.get("/api/v1/alerts/summary")
    assert summary_res.status_code == 200
    assert summary_res.json()["total"] >= 1

    # 6. PATCH /alerts/{alert_id}/status
    patch_res = client.patch(f"/api/v1/alerts/{alert_id}/status", json={"status": "REVIEWING"})
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "REVIEWING"

    # 7. Re-analyze same incident -> duplicate protection
    dup_res = client.post("/api/v1/alerts/analyze/IN-250825-001")
    assert dup_res.status_code == 200
    dup_data = dup_res.json()
    assert dup_data["reused"] is True
    assert dup_data["alert"]["alertId"] == alert_id

