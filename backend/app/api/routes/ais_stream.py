"""Real-time AIS vessel stream endpoints.

Exposes the AISStream in-memory cache to the frontend via:
- GET /ais/vessels       — current snapshot of all cached vessels (GeoJSON)
- GET /ais/vessels/nearby — vessels within a bbox
- GET /ais/status        — connection status + data freshness
- GET /ais/stream        — SSE stream of vessel position updates
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncIterator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.services.ais_stream_provider import get_ais_cache

router = APIRouter(prefix="/ais", tags=["ais"])

# SSE heartbeat interval
HEARTBEAT_INTERVAL = 10.0


@router.get("/vessels")
def get_vessels():
    """Return all cached vessel positions as GeoJSON FeatureCollection."""
    cache = get_ais_cache()
    return cache.to_geojson()


@router.get("/vessels/nearby")
def get_vessels_nearby(
    west: float = Query(..., description="West bound"),
    south: float = Query(..., description="South bound"),
    east: float = Query(..., description="East bound"),
    north: float = Query(..., description="North bound"),
):
    """Return vessels within a geographic bounding box."""
    cache = get_ais_cache()
    vessels = cache.get_bbox(west, south, east, north)
    return cache.to_geojson(vessels)


@router.get("/status")
def get_ais_status():
    """Return AISStream connection status and data freshness."""
    cache = get_ais_cache()
    status = cache.status
    recent = cache.get_recent(within_seconds=300)

    freshness = "UNAVAILABLE"
    if status.last_message_time:
        age_seconds = time.time() - status.last_message_time.timestamp()
        if age_seconds < 30:
            freshness = "REAL-TIME"
        elif age_seconds < 300:
            freshness = "RECENT"
        else:
            freshness = "STALE"

    return {
        "connected": status.connected,
        "subscription_confirmed": status.subscription_confirmed,
        "freshness": freshness,
        "total_vessels": status.total_vessels,
        "recent_vessels": len(recent),
        "total_messages": status.total_messages,
        "position_reports_received": status.position_reports_received,
        "last_message_time": status.last_message_time.isoformat() if status.last_message_time else None,
        "reconnect_count": status.reconnect_count,
        "receive_loop_alive": status.receive_loop_alive,
        "last_error": status.last_error,
    }


async def _ais_event_stream() -> AsyncIterator[str]:
    """Generate SSE events from AIS vessel updates."""
    cache = get_ais_cache()
    last_vessel_count = 0
    last_status_check = 0.0

    while True:
        await asyncio.sleep(2.0)  # Update every 2 seconds

        now = time.time()

        # Send status update every 10 seconds
        if now - last_status_check > HEARTBEAT_INTERVAL:
            status = cache.status
            freshness = "UNAVAILABLE"
            if status.last_message_time:
                age = now - status.last_message_time.timestamp()
                if age < 30:
                    freshness = "REAL-TIME"
                elif age < 300:
                    freshness = "RECENT"
                else:
                    freshness = "STALE"

            status_data = json.dumps({
                "type": "ais.status",
                "payload": {
                    "connected": status.connected,
                    "subscription_confirmed": status.subscription_confirmed,
                    "freshness": freshness,
                    "total_vessels": status.total_vessels,
                    "total_messages": status.total_messages,
                    "position_reports_received": status.position_reports_received,
                },
            })
            yield f"event: ais.status\ndata: {status_data}\n\n"
            last_status_check = now

        # Send vessel update if count changed
        current_count = cache.status.total_vessels
        if current_count != last_vessel_count:
            vessels = cache.get_recent(within_seconds=30)
            if vessels:
                geojson = cache.to_geojson(vessels)
                vessel_data = json.dumps({
                    "type": "ais.vessels.update",
                    "payload": {
                        "count": len(vessels),
                        "geojson": geojson,
                    },
                })
                yield f"event: ais.vessels.update\ndata: {vessel_data}\n\n"
                last_vessel_count = current_count

        # Heartbeat
        yield ": heartbeat\n\n"


@router.get("/stream")
async def ais_stream():
    """SSE endpoint for real-time AIS vessel position updates.

    Emits:
    - ais.status: connection status + freshness
    - ais.vessels.update: GeoJSON vessel positions (when count changes)
    """
    return StreamingResponse(
        _ais_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
