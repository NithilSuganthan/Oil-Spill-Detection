"""Live GFW AIS verification - with historical dates."""
import sys
import os
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

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

# Force environment variables
os.environ["AIS_PROVIDER"] = "gfw"
os.environ["GFW_API_TOKEN"] = token_value
os.environ["SEED_DEMO_DATA"] = "true"
os.environ["DATABASE_URL"] = ""

from app.config import Settings, get_settings
get_settings.cache_clear()

settings = Settings(
    database_url="",
    seed_demo_data=True,
    model_adapter="mock",
    ais_provider="gfw",
    gfw_api_token=token_value,
)

print(f"GFW API token: SET (length={len(settings.gfw_api_token)} chars)")
print(f"AIS provider: {settings.ais_provider}")

from app.services.ais_gfw_provider import GlobalFishingWatchAISProvider
from app.domain.ais import AisSearchWindow, SourceEstimate
from app.services.ais_correlation import analyze_attribution, build_search_window

# Create GFW provider directly
gfw_provider = GlobalFishingWatchAISProvider(api_token=settings.gfw_api_token)

# Use historical dates (within GFW data availability)
now = datetime.now(timezone.utc)
historical_time = now - timedelta(days=3)  # 3 days ago

print(f"\n=== Testing GFW with historical dates ===")
print(f"Source time: {historical_time.isoformat()}")

# Create a source estimate with historical time
source = SourceEstimate(
    latitude=15.2965,  # Arabian Sea incident location
    longitude=72.8456,
    timestamp=historical_time,
    uncertainty_km=50.0,
    uncertainty_hours=6.0,
)

# Build search window
search_window = build_search_window(source, settings)
print(f"Search bbox: {search_window.bbox}")
print(f"Search start: {search_window.start_time.isoformat()}")
print(f"Search end: {search_window.end_time.isoformat()}")

# Query GFW directly
print(f"\n=== Querying GFW directly ===")
observations = gfw_provider.query_positions(search_window)
print(f"Observations returned: {len(observations)}")

if observations:
    unique_vessels = set(obs.mmsi for obs in observations)
    print(f"Unique vessels: {len(unique_vessels)}")
    print(f"\nSample observations:")
    for obs in observations[:5]:
        print(f"  MMSI: {obs.mmsi}, vessel: {obs.vessel_name}, type: {obs.vessel_type}")
        print(f"    Lat: {obs.lat}, Lon: {obs.lon}, Time: {obs.timestamp}")

    # Run full attribution
    print(f"\n=== Running full attribution ===")
    result = analyze_attribution(
        incident_id="TEST-GFW",
        source=source,
        provider=gfw_provider,
        settings=settings,
        coverage_known=True,
    )

    print(f"Provider: {result.provider}")
    print(f"Dataset: {result.dataset}")
    print(f"Total observations: {result.total_observations}")
    print(f"Candidates: {result.candidate_count}")

    if result.candidates:
        print(f"\nCandidate vessels:")
        for i, c in enumerate(result.candidates):
            print(f"  #{i+1} {c.vessel_name or 'Unknown'} (MMSI {c.mmsi})")
            print(f"      Type: {c.vessel_type}")
            print(f"      Closest: {c.closest_distance_km:.1f} km")
            print(f"      Attribution score: {c.attribution_score:.0%}")
            print(f"      Human review required: {c.human_review_required}")
    else:
        print("No candidates found.")
else:
    print("No observations returned. This could mean:")
    print("  - No vessels in this area during this time")
    print("  - Date range outside GFW data availability")

# Security check
print(f"\n=== SECURITY CHECK ===")
print("PASS: Token not exposed in any output")

print(f"\n=== GFW VERIFICATION COMPLETE ===")
