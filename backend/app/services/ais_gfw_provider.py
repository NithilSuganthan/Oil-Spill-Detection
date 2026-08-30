"""Global Fishing Watch AIS provider — real AIS vessel presence data.

Uses the GFW 4Wings API v3 report endpoint with the
`public-global-presence:latest` dataset to query vessel presence
within a geographic region and time range.

Requires GFW_API_TOKEN environment variable.

API reference: https://globalfishingwatch.org/our-apis/documentation/
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
import urllib.error
from datetime import timezone

from app.domain.ais import AisObservation, AisSearchWindow
from app.services.ais_provider import AISProvider

logger = logging.getLogger(__name__)

GFW_BASE_URL = "https://gateway.api.globalfishingwatch.org/v3"
GFW_PRESENCE_DATASET = "public-global-presence:latest"


class GlobalFishingWatchAISProvider(AISProvider):
    """Real AIS provider using the Global Fishing Watch 4Wings API.

    Queries vessel presence data for a geographic polygon and time range.
    Authentication requires a valid GFW_API_TOKEN.
    """

    name = "gfw"
    dataset = GFW_PRESENCE_DATASET

    def __init__(self, api_token: str) -> None:
        if not api_token:
            raise ValueError("GFW_API_TOKEN is required")
        self._token = api_token

    def query_positions(
        self,
        search_window: AisSearchWindow,
    ) -> list[AisObservation]:
        """Query GFW 4Wings report for vessel presence in a bbox polygon.

        Uses the POST /v3/4wings/report endpoint with a GeoJSON polygon
        and group-by VESSEL_ID to get per-vessel presence data.

        Note: GFW data has a ~4-day availability delay. Queries for dates
        within the last 96 hours may return empty results.
        """
        geojson = self._bbox_to_geojson(search_window.bbox)
        # GFW expects date format: YYYY-MM-DD,YYYY-MM-DD
        start_date = search_window.start_time.strftime("%Y-%m-%d")
        end_date = search_window.end_time.strftime("%Y-%m-%d")
        date_range = f"{start_date},{end_date}"

        params = {
            "format": "JSON",
            "group-by": "VESSEL_ID",
            "temporal-resolution": "HOURLY",
            "datasets[0]": GFW_PRESENCE_DATASET,
            "date-range": date_range,
            "spatial-aggregation": "false",
            "spatial-resolution": "HIGH",
        }

        query_string = "&".join(
            f"{k}={urllib.parse.quote(str(v), safe='')}"
            for k, v in params.items()
        )
        url = f"{GFW_BASE_URL}/4wings/report?{query_string}"

        body = json.dumps({"geojson": geojson}).encode("utf-8")

        try:
            response_data = self._make_request(url, body)
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            logger.error("GFW API request failed: %s", exc)
            return []
        except Exception as exc:
            logger.error("Unexpected GFW API error: %s", exc)
            return []

        return self._parse_report(response_data, search_window)

    def _make_request(self, url: str, body: bytes) -> dict:
        """Make authenticated POST request to GFW API."""
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "Content-Language": "en-EN",
                "User-Agent": "SAGAR-WATCH/1.0 (oil-spill-detection; research)",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _parse_report(
        self,
        data: dict,
        search_window: AisSearchWindow,
    ) -> list[AisObservation]:
        """Parse GFW 4Wings report response into normalized observations.

        The report returns entries nested under a dataset-specific key like
        'public-global-presence:v4.0'. Each entry contains per-vessel
        presence data with lat/lon, timestamps, and vessel identity.
        """
        observations: list[AisObservation] = []
        entries = data.get("entries", [])

        for entry_group in entries:
            # Data is nested under dataset key (e.g., "public-global-presence:v4.0")
            for key, vessel_list in entry_group.items():
                if not isinstance(vessel_list, list):
                    continue

                for vessel in vessel_list:
                    mmsi = vessel.get("mmsi", "")
                    if not mmsi:
                        continue

                    lat = vessel.get("lat")
                    lon = vessel.get("lon")
                    if lat is None or lon is None:
                        continue

                    # Parse entry timestamp (when vessel entered the cell)
                    entry_ts = vessel.get("entryTimestamp")
                    timestamp = _parse_iso(entry_ts) or search_window.start_time

                    observations.append(AisObservation(
                        mmsi=str(mmsi),
                        timestamp=timestamp,
                        lat=float(lat),
                        lon=float(lon),
                        sog=None,
                        cog=None,
                        heading=None,
                        vessel_type=vessel.get("vesselType"),
                        imo=vessel.get("imo"),
                        vessel_name=vessel.get("shipName"),
                        navigation_status=None,
                        draft=None,
                    ))

        logger.info(
            "GFW query returned %d entry groups, %d observations",
            len(entries),
            len(observations),
        )
        return observations

    @staticmethod
    def _bbox_to_geojson(
        bbox: tuple[float, float, float, float],
    ) -> dict:
        """Convert (west, south, east, north) to a GeoJSON Polygon."""
        w, s, e, n = bbox
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [w, s],
                                [e, s],
                                [e, n],
                                [w, n],
                                [w, s],
                            ]
                        ],
                    },
                }
            ],
        }


def _parse_iso(ts: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp string."""
    if not ts:
        return None
    try:
        # Handle both Z and +00:00 suffixes
        ts_clean = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_clean)
    except (ValueError, TypeError):
        return None
