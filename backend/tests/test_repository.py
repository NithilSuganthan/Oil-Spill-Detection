"""Incident creation / repository round-trip tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db.memory_repo import InMemoryRepository
from app.db.seed import build_demo_incidents, build_demo_scenes, make_slick_ring
from app.domain.entities import SatelliteSceneRecord, SpillIncident


def test_seed_builders_are_consistent():
    incidents = build_demo_incidents()
    scenes = build_demo_scenes()
    scene_ids = {s.id for s in scenes}
    assert len(incidents) >= 9
    for inc in incidents:
        assert inc.scene_id in scene_ids
        ring = inc.geometry["coordinates"][0]
        assert ring[0] == ring[-1]
        assert inc.level in ("HIGH", "MEDIUM", "LOW")
        # every seed record is explicitly demo data
        assert inc.is_demo is True


def test_memory_repo_roundtrip_and_filters():
    repo = InMemoryRepository()
    for sc in build_demo_scenes():
        repo.add_scene(sc)
    for inc in build_demo_incidents():
        repo.add_incident(inc)

    assert repo.count_incidents() >= 9

    high = repo.list_incidents(min_confidence=0.8)
    assert all(i.confidence >= 0.8 for i in high)

    start = datetime.fromisoformat("2026-08-25T00:00:00+05:30")
    day25 = repo.list_incidents(start=start)
    assert all(i.detected_at >= start for i in day25)
    assert len(day25) == 6

    arabian = [i for i in repo.list_incidents() if i.region == "Arabian Sea"]
    assert len(arabian) >= 1

    got = repo.get_incident("IN-250824-011")
    assert got is not None and got.region == "Andaman Sea"


def test_incident_id_sequence_generation():
    from app.services.inference_service import InferenceService

    repo = InMemoryRepository()
    svc = InferenceService(repo, None, None)  # type: ignore[arg-type]
    base = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)

    id1 = svc._next_incident_id(base)  # noqa: SLF001
    repo.add_incident(_stub_incident(id1))
    id2 = svc._next_incident_id(base)  # noqa: SLF001
    assert id1.endswith("-001")
    assert id2.endswith("-002")


def test_scene_status_updates():
    repo = InMemoryRepository()
    sc = SatelliteSceneRecord(id="SCN", platform="Sentinel-1A", status="queued")
    repo.add_scene(sc)
    now = datetime.now(timezone.utc)
    repo.update_scene_status("SCN", "processed", processed_at=now)
    stored = repo.get_scene("SCN")
    assert stored.status == "processed"
    assert stored.processed_at == now


def _stub_incident(incident_id: str) -> SpillIncident:
    ring = make_slick_ring(72.5, 15.0, 60, 3.0, 1.2, 42)
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return SpillIncident(
        id=incident_id,
        scene_id="S1A_IW_GRDH_20260825T1820",
        confidence=0.77,
        area_km2=2.5,
        perimeter_km=6.0,
        centroid_lon=72.5,
        centroid_lat=15.0,
        geometry={"type": "Polygon", "coordinates": [ring]},
        bbox=(min(lons), min(lats), max(lons), max(lats)),
        detected_at=datetime.now(timezone.utc),
        region="Arabian Sea",
        location_description="test",
        satellite="Sentinel-1A",
        model_name="MockOilSpillModel",
        model_version="mock-0.1",
    )
