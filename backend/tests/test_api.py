"""API contract tests — response shapes must stay compatible with the
SAGAR WATCH frontend (camelCase aliases, GeoJSON geometry)."""

from __future__ import annotations

import time


EXPECTED_INCIDENT_KEYS = {
    "id", "sceneId", "confidence", "areaKm2", "perimeterKm2",
    "centroid", "geometry", "detectedAt", "region", "locationDescription",
    "satellite", "model", "modelVersion", "status", "level",
    "windSpeedKts", "estimatedVolumeTons",
}


# ------------------------------------------------------------------ health/system
def test_health(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"


def test_system_status(client):
    res = client.get("/api/v1/system/status")
    assert res.status_code == 200
    body = res.json()
    names = [s["name"] for s in body["services"]]
    assert "Satellite Feed" in names and "AI Model" in names
    assert body["modelAdapter"] == "mock"
    assert body["activeScene"]["id"]


# ------------------------------------------------------------------ spills
def test_list_spills_shape(client):
    res = client.get("/api/v1/spills")
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 9                       # demo seed loaded
    first = items[0]
    assert EXPECTED_INCIDENT_KEYS.issubset(first.keys())
    assert first["level"] in ("HIGH", "MEDIUM", "LOW")
    assert first["geometry"]["type"] == "Polygon"
    assert len(first["geometry"]["coordinates"][0]) >= 4
    lat, lon = first["centroid"]["lat"], first["centroid"]["lon"]
    assert 5 < lat < 25 and 62 < lon < 98        # Indian maritime focus region


def test_get_spill_by_id(client):
    res = client.get("/api/v1/spills/IN-250825-001")
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == "IN-250825-001"
    assert body["region"] == "Arabian Sea"
    assert body["satellite"].startswith("Sentinel-1")


def test_get_spill_404(client):
    assert client.get("/api/v1/spills/NOPE").status_code == 404


def test_spill_geometry_geojson(client):
    res = client.get("/api/v1/spills/IN-250825-002/geometry")
    assert res.status_code == 200
    feature = res.json()
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Polygon"
    ring = feature["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]                   # closed ring


def test_spill_filters_min_confidence(client):
    res = client.get("/api/v1/spills", params={"min_confidence": 0.8})
    assert res.status_code == 200
    for item in res.json():
        assert item["confidence"] >= 0.8
        assert item["level"] == "HIGH"


def test_spill_filters_bbox(client):
    # Arabian Sea box only
    res = client.get("/api/v1/spills", params={"bbox": "70,13,75,17"})
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 1
    for item in items:
        assert 70 <= item["centroid"]["lon"] <= 75
        assert 13 <= item["centroid"]["lat"] <= 17


def test_spill_filters_time_window_excludes_old(client):
    far_past = "2030-01-01T00:00:00+05:30"
    res = client.get("/api/v1/spills", params={"start": far_past})
    assert res.status_code == 200
    assert res.json() == []


# ------------------------------------------------------------------ scenes
def test_scenes_list_and_detail(client):
    res = client.get("/api/v1/satellite/scenes")
    assert res.status_code == 200
    scenes = res.json()
    assert len(scenes) >= 6
    scene_id = scenes[0]["id"]

    detail = client.get(f"/api/v1/satellite/scenes/{scene_id}")
    assert detail.status_code == 200
    fp = detail.json()["footprint"]
    assert set(fp) == {"west", "south", "east", "north"}


# ------------------------------------------------------------------ analytics
def test_analytics_summary_matches_frontend_schema(client):
    res = client.get("/api/v1/analytics/summary")
    assert res.status_code == 200
    body = res.json()
    totals = body["totals"]
    assert {"detections", "highConfidence", "totalAreaKm2", "scenesProcessed"} == set(totals)
    daily = body["daily"][0]
    assert {"date", "detections", "highConfidence", "areaKm2", "scenesProcessed"} == set(daily)
    assert {"hour", "detections"} == set(body["hourly"][0])
    assert {"region", "detections", "areaKm2"} == set(body["byRegion"][0])
    assert {"bucket", "count"} == set(body["confidenceBuckets"][0])
    assert totals["detections"] >= 9
    assert totals["totalAreaKm2"] > 0


def test_analytics_detections(client):
    res = client.get("/api/v1/analytics/detections")
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) >= 9
    row = rows[0]
    assert {"incidentId", "detectedAt", "confidence", "areaKm2", "level", "region"} == set(row)


# ------------------------------------------------------------------ SSE + pipeline
def test_pipeline_creates_incidents_and_events(client):
    """Full local pipeline: synthetic raster -> mock adapter -> polygons ->
    repository -> GET /spills -> SSE event."""
    cursor_before = client.app.state.events._next_id  # noqa: SLF001

    run = client.post("/api/v1/system/run-demo-pipeline")
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["incidentsCreated"], "mock pipeline should detect the synthetic slick"
    assert body["sceneId"].startswith("DEMO_")
    assert body["modelRunId"].startswith("run-")
    assert body["inferenceTimeMs"] >= 0

    # incident is queryable through the API and marked as demo
    inc_id = body["incidentsCreated"][0]
    inc = client.get(f"/api/v1/spills/{inc_id}").json()
    assert inc["isDemo"] is True
    assert inc["model"] == "MockOilSpillModel"
    # detection must be georeferenced inside its scene's footprint
    scene_id = body["sceneId"]
    scene = client.get(f"/api/v1/satellite/scenes/{scene_id}").json()
    fp = scene["footprint"]
    assert fp["west"] <= inc["centroid"]["lon"] <= fp["east"]
    assert fp["south"] <= inc["centroid"]["lat"] <= fp["north"]

    # one detection.created event per new incident
    events = client.app.state.events.since(cursor_before - 1)
    types = {e.type for e in events}
    assert "detection.created" in types
    assert len([e for e in events if e.type == "detection.created"]) >= len(body["incidentsCreated"])


def test_model_run_recorded(client):
    before = len(_all_model_runs(client))
    client.post("/api/v1/system/run-demo-pipeline")
    runs = _all_model_runs(client)
    assert len(runs) == before + 1
    run = runs[0]
    assert run.status == "completed" or run.error_message is None


def _all_model_runs(client):
    return list(client.app.state.repo.list_model_runs())


# ------------------------------------------------------------------ attribution
def test_attribution_analyze_returns_200(client):
    """POST /attribution/analyze with a valid incident ID returns 200."""
    incidents = client.get("/api/v1/spills").json()
    if not incidents:
        return  # no incidents to test against
    incident_id = incidents[0]["id"]
    res = client.post("/api/v1/attribution/analyze", json={"incidentId": incident_id})
    assert res.status_code == 200


def test_attribution_analyze_response_shape(client):
    """Attribution response has all required fields."""
    incidents = client.get("/api/v1/spills").json()
    if not incidents:
        return
    incident_id = incidents[0]["id"]
    res = client.post("/api/v1/attribution/analyze", json={"incidentId": incident_id})
    assert res.status_code == 200
    body = res.json()
    assert "incidentId" in body
    assert "searchWindow" in body
    assert "coverageKnown" in body
    assert "candidateCount" in body
    assert "candidates" in body
    assert "totalObservations" in body
    assert "provenance" in body
    assert isinstance(body["candidates"], list)


def test_attribution_analyze_404_unknown_incident(client):
    """POST /attribution/analyze with unknown incident returns 404."""
    res = client.post("/api/v1/attribution/analyze", json={"incidentId": "NOPE"})
    assert res.status_code == 404


def test_attribution_get_returns_200(client):
    """GET /attribution/{id} returns 200."""
    incidents = client.get("/api/v1/spills").json()
    if not incidents:
        return
    incident_id = incidents[0]["id"]
    res = client.get(f"/api/v1/attribution/{incident_id}")
    assert res.status_code == 200


def test_attribution_get_404_unknown_incident(client):
    """GET /attribution/{id} with unknown incident returns 404."""
    res = client.get("/api/v1/attribution/NOPE")
    assert res.status_code == 404


def test_attribution_candidate_has_required_fields(client):
    """Each candidate vessel has required fields."""
    incidents = client.get("/api/v1/spills").json()
    if not incidents:
        return
    incident_id = incidents[0]["id"]
    res = client.post("/api/v1/attribution/analyze", json={"incidentId": incident_id})
    body = res.json()
    for candidate in body["candidates"]:
        assert "mmsi" in candidate
        assert "closestDistanceKm" in candidate
        assert "attributionScore" in candidate
        assert "scoreComponents" in candidate
        assert "humanReviewRequired" in candidate
        assert "qualityFlags" in candidate
        assert candidate["humanReviewRequired"] is True


def test_attribution_search_window_has_correct_shape(client):
    """Search window has correct fields."""
    incidents = client.get("/api/v1/spills").json()
    if not incidents:
        return
    incident_id = incidents[0]["id"]
    res = client.post("/api/v1/attribution/analyze", json={"incidentId": incident_id})
    body = res.json()
    sw = body["searchWindow"]
    assert "start" in sw
    assert "end" in sw
    assert "radiusKm" in sw
    assert "timeWindowHours" in sw


def test_attribution_custom_search_radius(client):
    """Custom search radius is applied."""
    incidents = client.get("/api/v1/spills").json()
    if not incidents:
        return
    incident_id = incidents[0]["id"]
    res = client.post(
        "/api/v1/attribution/analyze",
        json={"incidentId": incident_id, "searchRadiusKm": 25.0},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["searchWindow"]["radiusKm"] == 25.0


def test_attribution_provenance_recorded(client):
    """Provenance data is included in the response."""
    incidents = client.get("/api/v1/spills").json()
    if not incidents:
        return
    incident_id = incidents[0]["id"]
    res = client.post("/api/v1/attribution/analyze", json={"incidentId": incident_id})
    body = res.json()
    prov = body["provenance"]
    assert "provider" in prov
    assert "search_radius_km" in prov
    assert "time_window_hours" in prov
    assert "scoring_weights" in prov


# ------------------------------------------------------------------ drift
def test_drift_analyze_returns_200(client):
    incidents = client.get("/api/v1/spills").json()
    if not incidents:
        return
    incident_id = incidents[0]["id"]
    res = client.post("/api/v1/drift/analyze", json={"incidentId": incident_id})
    assert res.status_code == 200


def test_drift_analyze_response_shape(client):
    incidents = client.get("/api/v1/spills").json()
    if not incidents:
        return
    incident_id = incidents[0]["id"]
    res = client.post("/api/v1/drift/analyze", json={"incidentId": incident_id})
    body = res.json()
    assert "incidentId" in body
    assert "sourceLatitude" in body
    assert "sourceLongitude" in body
    assert "uncertaintyKm" in body
    assert "qualityFlags" in body
    assert "DEMO_ENVIRONMENTAL_FORCING" in body["qualityFlags"]


def test_drift_analyze_404(client):
    res = client.post("/api/v1/drift/analyze", json={"incidentId": "NOPE"})
    assert res.status_code == 404


def test_drift_get_returns_200(client):
    incidents = client.get("/api/v1/spills").json()
    if not incidents:
        return
    incident_id = incidents[0]["id"]
    res = client.get(f"/api/v1/drift/{incident_id}")
    assert res.status_code == 200


# ------------------------------------------------------------------ investigation
def test_investigation_run_returns_200(client):
    incidents = client.get("/api/v1/spills").json()
    if not incidents:
        return
    incident_id = incidents[0]["id"]
    res = client.post(f"/api/v1/investigation/{incident_id}/run")
    assert res.status_code == 200


def test_investigation_run_response_shape(client):
    incidents = client.get("/api/v1/spills").json()
    if not incidents:
        return
    incident_id = incidents[0]["id"]
    res = client.post(f"/api/v1/investigation/{incident_id}/run")
    body = res.json()
    assert "incidentId" in body
    assert "drift" in body
    assert "attribution" in body
    assert "environment" in body
    assert body["environment"] in ("DEMO", "MIXED", "REAL", "DATA_UNAVAILABLE", "CREDENTIALS_REQUIRED")


def test_investigation_includes_drift_and_attribution(client):
    incidents = client.get("/api/v1/spills").json()
    if not incidents:
        return
    incident_id = incidents[0]["id"]
    res = client.post(f"/api/v1/investigation/{incident_id}/run")
    body = res.json()
    assert body["drift"] is not None
    assert body["attribution"] is not None
    assert body["drift"]["sourceLatitude"] != 0
    assert "candidates" in body["attribution"]


def test_investigation_404(client):
    res = client.post("/api/v1/investigation/NOPE/run")
    assert res.status_code == 404
