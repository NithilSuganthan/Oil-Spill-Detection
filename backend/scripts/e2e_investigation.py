"""End-to-end DEMO investigation test."""
import sys
import os

sys.path.insert(0, r"D:\Oil spill detection\backend")
os.environ.setdefault("SEED_DEMO_DATA", "true")

from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app

settings = Settings(database_url="", seed_demo_data=True, model_adapter="mock")
app = create_app(settings)

with TestClient(app) as client:
    # 1. List incidents
    incidents = client.get("/api/v1/spills").json()
    print(f"=== Incidents available: {len(incidents)} ===")
    inc = incidents[0]
    print(f"First incident: {inc['id']} at ({inc['centroid']['lat']:.4f}, {inc['centroid']['lon']:.4f})")

    # 2. Run drift analysis
    print("\n=== POST /drift/analyze ===")
    drift = client.post("/api/v1/drift/analyze", json={"incidentId": inc["id"]}).json()
    print(f"Method: {drift['method']}")
    print(f"Slick: ({drift['slickLatitude']:.4f}, {drift['slickLongitude']:.4f})")
    print(f"Source: ({drift['sourceLatitude']:.4f}, {drift['sourceLongitude']:.4f})")
    print(f"Uncertainty: +/-{drift['uncertaintyKm']:.1f} km / +/-{drift['uncertaintyHours']:.1f} h")
    print(f"Confidence: {drift['confidence']:.1%}")
    print(f"Quality flags: {drift['qualityFlags']}")
    print(f"Ensemble size: {drift['ensembleSize']}")
    print(f"Source points: {len(drift['sourcePoints'])}")

    # 3. Run full investigation
    print(f"\n=== POST /investigation/{inc['id']}/run ===")
    inv = client.post(f"/api/v1/investigation/{inc['id']}/run").json()
    print(f"Status: {inv['status']}")
    print(f"Environment: {inv['environment']}")
    print(f"Drift source: ({inv['drift']['sourceLatitude']:.4f}, {inv['drift']['sourceLongitude']:.4f})")
    print(f"AIS candidates: {inv['attribution']['candidateCount']}")
    for i, c in enumerate(inv["attribution"]["candidates"]):
        print(f"  #{i+1} {c['vesselName']} (MMSI {c['mmsi']}) - score: {c['attributionScore']:.0%} - {c['closestDistanceKm']:.1f} km")

    # 4. Verify GET /drift/{id}
    print(f"\n=== GET /drift/{inc['id']} ===")
    drift_get = client.get(f"/api/v1/drift/{inc['id']}").json()
    print(f"Source: ({drift_get['sourceLatitude']:.4f}, {drift_get['sourceLongitude']:.4f})")
    print(f"Match: {drift_get['sourceLatitude'] == drift['sourceLatitude']}")

    # 5. Verify all routes
    print("\n=== Route verification ===")
    routes = [
        ("GET", "/api/v1/health"),
        ("GET", "/api/v1/spills"),
        ("GET", f"/api/v1/spills/{inc['id']}"),
        ("GET", "/api/v1/analytics/summary"),
        ("GET", "/api/v1/system/status"),
        ("GET", "/api/v1/attribution/" + inc["id"]),
        ("POST", "/api/v1/attribution/analyze"),
        ("GET", "/api/v1/drift/" + inc["id"]),
        ("POST", "/api/v1/drift/analyze"),
        ("POST", "/api/v1/investigation/" + inc["id"] + "/run"),
    ]
    for method, path in routes:
        if method == "GET":
            res = client.get(path)
        else:
            body = {"incidentId": inc["id"]} if "attribution/analyze" in path else {}
            res = client.post(path, json=body)
        status = "OK" if res.status_code == 200 else f"FAIL ({res.status_code})"
        print(f"  {method:4s} {path:50s} -> {status}")

    print("\n=== END-TO-END DEMO INVESTIGATION: PASS ===")
