"""Live GFW AIS verification - with exact working dates."""
import sys
import os
import json
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, r"D:\Oil spill detection\backend")

root_env = Path(r"D:\Oil spill detection\.env")
token_value = ""
if root_env.exists():
    for line in root_env.read_text().splitlines():
        line = line.strip()
        if line.startswith("GFW_API_TOKEN=") and not line.startswith("#"):
            token_value = line.split("=", 1)[1].strip()
            break

print(f"Token: SET ({len(token_value)} chars)")

# Use the exact date range that worked before
bbox = (72.6, 15.0, 73.1, 15.6)
date_range = "2026-08-19,2026-08-20"

geojson = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [bbox[0], bbox[1]],
                [bbox[2], bbox[1]],
                [bbox[2], bbox[3]],
                [bbox[0], bbox[3]],
                [bbox[0], bbox[1]],
            ]]
        }
    }]
}

body = json.dumps({"geojson": geojson}).encode("utf-8")

params = {
    "format": "JSON",
    "group-by": "VESSEL_ID",
    "temporal-resolution": "HOURLY",
    "datasets[0]": "public-global-presence:latest",
    "date-range": date_range,
    "spatial-aggregation": "false",
    "spatial-resolution": "HIGH",
}

query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
url = f"https://gateway.api.globalfishingwatch.org/v3/4wings/report?{query_string}"

print(f"Date range: {date_range}")
print(f"BBox: {bbox}")

req = urllib.request.Request(
    url,
    data=body,
    headers={
        "Authorization": f"Bearer {token_value}",
        "Content-Type": "application/json",
        "Content-Language": "en-EN",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        entries = data.get("entries", [])
        print(f"\nSUCCESS! Status: {resp.status}")
        print(f"Entries: {len(entries)}")
        if entries:
            for key, vessel_list in entries[0].items():
                if isinstance(vessel_list, list):
                    print(f"Dataset key: {key}")
                    print(f"Vessels: {len(vessel_list)}")
                    for v in vessel_list[:5]:
                        print(f"  MMSI={v.get('mmsi')}, vessel={v.get('shipName')}, type={v.get('vesselType')}, lat={v.get('lat')}, lon={v.get('lon')}")
except urllib.error.HTTPError as e:
    error_body = e.read().decode("utf-8") if e.fp else "No body"
    print(f"\nHTTP Error {e.code}: {e.reason}")
    print(f"Response: {error_body[:300]}")
except Exception as e:
    print(f"\nError: {e}")
