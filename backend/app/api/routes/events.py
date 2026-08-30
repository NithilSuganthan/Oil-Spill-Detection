from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.deps import get_event_hub_dep
from app.services.event_hub import EventHub

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/stream")
async def event_stream(
    hub: EventHub = Depends(get_event_hub_dep),
    cursor: int = Query(default=0, ge=0),
) -> StreamingResponse:
    """Server-Sent Events stream.

    Emits `detection.created` events when the pipeline registers new
    incidents. Clients should reconnect with ?cursor=<last id> to resume.
    """
    return StreamingResponse(
        hub.stream(cursor=cursor, heartbeat=15.0),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
