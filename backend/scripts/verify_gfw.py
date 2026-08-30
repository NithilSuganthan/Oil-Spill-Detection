"""Live GFW AIS verification - with debugging."""
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, r"D:\Oil spill detection\backend")

# Read token from root .env
root_env = Path(r"D:\Oil spill detection\.env")
token_value = ""
if root_env.exists():
    for line in root_env.read_text().splitlines():
        line = line.strip()
        if line.startswith("GFW_API_TOKEN=") and not line.startswith("#"):
            token_value = line.split("=", 1)[1].strip()
            break

if not token_value:
    print("ERROR: GFW_API_TOKEN not found in root .env")
    sys.exit(1)

# Force environment variables BEFORE importing any app modules
os.environ["AIS_PROVIDER"] = "gfw"
os.environ["GFW_API_TOKEN"] = token_value
os.environ["SEED_DEMO_DATA"] = "true"
os.environ["DATABASE_URL"] = ""

# Clear any cached settings
from app.config import Settings, get_settings
get_settings.cache_clear()

# Create settings directly with explicit token
settings = Settings(
    database_url="",
    seed_demo_data=True,
    model_adapter="mock",
    ais_provider="gfw",
    gfw_api_token=token_value,
)

print(f"GFW API token: SET (length={len(settings.gfw_api_token)} chars)")
print(f"AIS provider: {settings.ais_provider}")
print(f"Token first 10 chars: {settings.gfw_api_token[:10]}...")

# Run the API test
from fastapi.testclient import TestClient
from app.main import create_app

app = create_app(settings)

# Verify app state has the right settings
print(f"\nApp state settings ais_provider: {app.state.settings.ais_provider}")
print(f"App state settings gfw_api_token length: {len(app.state.settings.gfw_api_token)}")

with TestClient(app) as client:
    incidents = client.get("/api/v1/spills").json()
    inc = incidents[0]
    print(f"\nUsing incident: {inc['id']}")

    # Run attribution analysis
    print(f"\n=== POST /api/v1/attribution/analyze ===")
    res = client.post("/api/v1/attribution/analyze", json={"incidentId": inc["id"]})
    print(f"HTTP status: {res.status_code}")

    body = res.json()
    print(f"Provider: {body['provider']}")
    print(f"Dataset: {body['dataset']}")
    print(f"Total AIS observations: {body['totalObservations']}")
    print(f"Candidate vessels: {body['candidateCount']}")

    if body['candidateCount'] > 0:
        print(f"\nCandidate vessels:")
        for i, c in enumerate(body['candidates']):
            print(f"  #{i+1} {c.get('vesselName') or 'Unknown'} (MMSI {c['mmsi']})")
            print(f"      Type: {c.get('vesselType', 'Unknown')}")
            print(f"      Closest: {c['closestDistanceKm']:.1f} km")
            print(f"      Attribution score: {c['attributionScore']:.0%}")
            print(f"      Human review required: {c['humanReviewRequired']}")
    else:
        print("\nNo candidate vessels found in this area/time.")

    # Security check
    print(f"\n=== SECURITY CHECK ===")
    full_response = str(body)
    if token_value[:10] in full_response:
        print("SECURITY FAIL: Token prefix found in response!")
    else:
        print("PASS: Token not exposed in API response")

    print(f"\n=== GFW VERIFICATION COMPLETE ===")
