"""API contract tests for satellite ingestion routes (mock provider mode)."""

from __future__ import annotations

from app.domain.entities import SatelliteSceneRecord
from datetime import datetime, timezone


def _seed_scene(client) -> str:
    scene = SatelliteSceneRecord(
        id="DEMO_API_SCENE",
        platform="Sentinel-1B",
        acquired_at=datetime(2026, 8, 1, 6, tzinfo=timezone.utc),
        footprint=(72.5, 18.0, 73.5, 19.0),
        status="discovered",
        source_provider="mock",
        is_demo=True,
        product_id="demo-api-uuid",
        orbit_state="ascending",
        absolute_orbit=999,
        product_type="IW_GRDH_1S",
    )
    client.app.state.repo.add_scene(scene)
    return scene.id


def test_provider_endpoint_reports_mock(client):
    res = client.get("/api/v1/satellite/scenes/provider")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "mock"
    assert body["isReal"] is False
    assert "synthetic" in body["note"].lower()


def test_stored_scenes_filters(client):
    _seed_scene(client)
    res = client.get("/api/v1/satellite/scenes", params={
        "start": "2026-07-01T00:00:00Z",
        "end": "2026-08-10T00:00:00Z",
        "platform": "sentinel-1b",
        "product_type": "IW_GRDH_1S",
    })
    assert res.status_code == 200
    ids = [s["id"] for s in res.json()]
    assert "DEMO_API_SCENE" in ids


def test_catalogue_source_uses_provider_and_never_persists(client):
    before = {s["id"] for s in client.get("/api/v1/satellite/scenes").json()}
    res = client.get("/api/v1/satellite/scenes", params={
        "source": "catalogue", "limit": "3", "region": "india",
    })
    assert res.status_code == 200
    items = res.json()
    assert len(items) <= 3
    for item in items:
        assert item["isDemo"] is True          # mock provider => demo data
        assert item["sourceProvider"] == "mock"
        assert item["status"] == "discovered"
    after = {s["id"] for s in client.get("/api/v1/satellite/scenes").json()}
    assert after == before                     # catalogue results not persisted


def test_import_persists_discovered_scene(client):
    catalogue = client.get("/api/v1/satellite/scenes", params={
        "source": "catalogue", "limit": "5", "region": "india",
    }).json()
    target = catalogue[0]["id"]

    res = client.post("/api/v1/satellite/scenes/import", json={"scene_id": target})
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == target
    assert body["isDemo"] is True

    # discovery event published exactly once; second import is idempotent
    cursor = client.app.state.events._next_id  # noqa: SLF001
    client.post("/api/v1/satellite/scenes/import", json={"scene_id": target})
    events = [e.type for e in client.app.state.events.since(cursor - 1)]  # noqa: SLF001
    assert events.count("scene.discovered") == 0   # already existed

    detail = client.get(f"/api/v1/satellite/scenes/{target}")
    assert detail.status_code == 200


def test_import_unknown_scene_404(client):
    res = client.post("/api/v1/satellite/scenes/import", json={"scene_id": "NOPE"})
    assert res.status_code == 404


def test_process_enqueues_job_and_status_endpoint(client):
    scene_id = _seed_scene(client)
    res = client.post(f"/api/v1/satellite/scenes/{scene_id}/process")
    assert res.status_code == 202
    job_id = res.json()["jobId"]
    assert res.json()["state"] == "QUEUED"

    status = client.get(f"/api/v1/pipeline/jobs/{job_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["sceneId"] == scene_id
    assert isinstance(body["history"], list)

    listing = client.get("/api/v1/pipeline/jobs", params={"scene_id": scene_id})
    assert any(j["jobId"] == job_id for j in listing.json())

    unknown = client.get("/api/v1/pipeline/jobs/job-nope")
    assert unknown.status_code == 404


def test_process_unknown_scene_404(client):
    res = client.post("/api/v1/satellite/scenes/GHOST/process")
    assert res.status_code == 404


def test_preview_404_before_processing(client):
    scene_id = _seed_scene(client)
    res = client.get(f"/api/v1/satellite/scenes/{scene_id}/preview")
    assert res.status_code == 404


def test_preview_served_after_processing(client):
    """Full loop through the API: seed -> process -> wait -> fetch preview."""
    import time

    scene_id = _seed_scene(client)
    job = client.post(f"/api/v1/satellite/scenes/{scene_id}/process").json()
    for _ in range(200):
        state = client.get(f"/api/v1/pipeline/jobs/{job['jobId']}").json()["state"]
        if state in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.05)
    assert state == "COMPLETED"

    preview = client.get(f"/api/v1/satellite/scenes/{scene_id}/preview")
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("image/png")
    assert preview.content[:8] == b"\x89PNG\r\n\x1a\n"

    scene = client.get(f"/api/v1/satellite/scenes/{scene_id}").json()
    assert scene["pipelineState"] == "COMPLETED"
    assert scene["hasPreview"] is True
