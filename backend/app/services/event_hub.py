"""In-process event hub for Server-Sent Events.

Simple append-only buffer + cursor-based subscription. Works from both
sync (pipeline) and async (route) contexts; SSE consumers poll with a
cursor. For multi-worker production deployments this would be replaced by
Redis pub/sub — the API contract stays identical.
"""

from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class Event:
    id: int
    type: str          # e.g. "detection.created"
    payload: dict


class EventHub:
    def __init__(self, max_events: int = 500) -> None:
        self._events: list[Event] = []
        self._lock = threading.Lock()
        self._next_id = 1
        self._max_events = max_events
        self._cond = threading.Condition(self._lock)

    def publish(self, event_type: str, payload: dict) -> Event:
        with self._cond:
            event = Event(id=self._next_id, type=event_type, payload=payload)
            self._next_id += 1
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]
            self._cond.notify_all()
            return event

    def since(self, cursor: int, timeout: float | None = None) -> list[Event]:
        """Return events newer than cursor; optionally wait for new ones."""
        with self._cond:
            if timeout is not None:
                def has_new() -> bool:
                    return bool(self._events) and self._events[-1].id > cursor
                if not has_new():
                    self._cond.wait(timeout)
            return [e for e in self._events if e.id > cursor]

    async def stream(self, cursor: int = 0, heartbeat: float = 15.0) -> AsyncIterator[str]:
        last = cursor
        while True:
            events = await asyncio.to_thread(self.since, last, heartbeat)
            if not events:
                yield ": heartbeat\n\n"
                continue
            for ev in events:
                last = max(last, ev.id)
                data = json.dumps({"type": ev.type, "payload": ev.payload}, default=str)
                yield f"id: {ev.id}\nevent: {ev.type}\ndata: {data}\n\n"


_hub: EventHub | None = None


def get_event_hub() -> EventHub:
    global _hub
    if _hub is None:
        _hub = EventHub()
    return _hub


def set_event_hub(hub: EventHub) -> None:
    global _hub
    _hub = hub
