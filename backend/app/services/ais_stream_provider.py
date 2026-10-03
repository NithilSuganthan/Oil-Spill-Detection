"""AISStream real-time WebSocket provider.

Connects to AISStream.io WebSocket API, subscribes to geographic bounding
boxes, and maintains an in-memory cache of latest vessel positions.

Architecture:
    AISStream WebSocket → background thread → vessel cache → REST/SSE → frontend

The API key is NEVER exposed to the frontend. All WebSocket traffic
is server-side only.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Default bounding box: Indian Ocean region
# AISStream format: [[[lat_min, lon_min], [lat_max, lon_max]]]
# Our region: longitude 55°E → 100°E, latitude -5° → 25°N
INDIAN_OCEAN_BBOX = [[-5.0, 55.0], [25.0, 100.0]]

# Connection constants
RECONNECT_DELAY_BASE = 2.0
RECONNECT_DELAY_MAX = 30.0
STALE_THRESHOLD_SECONDS = 300  # 5 minutes without update → stale
HEALTH_LOG_INTERVAL = 30.0     # Log health every 30 seconds


@dataclass
class VesselPosition:
    """Latest known position for a single vessel."""

    mmsi: str
    lat: float
    lon: float
    sog: float | None = None       # speed over ground (knots)
    cog: float | None = None       # course over ground (degrees)
    heading: float | None = None   # true heading (degrees)
    vessel_name: str | None = None
    vessel_type: str | None = None
    imo: str | None = None
    flag: str | None = None
    navigation_status: str | None = None
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message_count: int = 0


@dataclass
class AISStreamStatus:
    """Current status of the AISStream connection."""

    connected: bool = False
    subscription_confirmed: bool = False
    last_message_time: datetime | None = None
    total_messages: int = 0
    position_reports_received: int = 0
    total_vessels: int = 0
    subscribed_areas: int = 0
    reconnect_count: int = 0
    last_error: str | None = None
    receive_loop_alive: bool = False


class AISStreamCache:
    """Thread-safe in-memory cache of vessel positions from AISStream."""

    def __init__(self, max_vessels: int = 10000) -> None:
        self._vessels: dict[str, VesselPosition] = {}
        self._lock = threading.Lock()
        self._max_vessels = max_vessels
        self._status = AISStreamStatus()

    @property
    def status(self) -> AISStreamStatus:
        with self._lock:
            self._status.total_vessels = len(self._vessels)
            return self._status

    def update(self, mmsi: str, data: dict[str, Any]) -> None:
        """Update or insert a vessel position from an AISStream message."""
        with self._lock:
            now = datetime.now(timezone.utc)
            existing = self._vessels.get(mmsi)

            if existing:
                existing.lat = data.get("lat", existing.lat)
                existing.lon = data.get("lon", existing.lon)
                existing.sog = data.get("sog", existing.sog)
                existing.cog = data.get("cog", existing.cog)
                existing.heading = data.get("heading", existing.heading)
                existing.vessel_name = data.get("shipname") or data.get("name") or existing.vessel_name
                existing.vessel_type = data.get("shiptype") or data.get("type") or existing.vessel_type
                existing.imo = data.get("imo") or existing.imo
                existing.flag = data.get("flag") or existing.flag
                existing.navigation_status = data.get("navstat") or existing.navigation_status
                existing.last_update = now
                existing.message_count += 1
            else:
                if len(self._vessels) >= self._max_vessels:
                    # Evict oldest vessel
                    oldest_mmsi = min(self._vessels, key=lambda k: self._vessels[k].last_update)
                    del self._vessels[oldest_mmsi]

                self._vessels[mmsi] = VesselPosition(
                    mmsi=mmsi,
                    lat=data.get("lat", 0.0),
                    lon=data.get("lon", 0.0),
                    sog=data.get("sog"),
                    cog=data.get("cog"),
                    heading=data.get("heading"),
                    vessel_name=data.get("shipname") or data.get("name"),
                    vessel_type=data.get("shiptype") or data.get("type"),
                    imo=data.get("imo"),
                    flag=data.get("flag"),
                    navigation_status=data.get("navstat"),
                    last_update=now,
                    message_count=1,
                )

            self._status.last_message_time = now
            self._status.total_messages += 1

    def get_all(self) -> list[VesselPosition]:
        """Return all cached vessel positions."""
        with self._lock:
            return list(self._vessels.values())

    def get_recent(self, within_seconds: float = 300.0) -> list[VesselPosition]:
        """Return vessels updated within the last N seconds."""
        cutoff = datetime.now(timezone.utc).timestamp() - within_seconds
        with self._lock:
            return [
                v for v in self._vessels.values()
                if v.last_update.timestamp() > cutoff
            ]

    def get_bbox(self, west: float, south: float, east: float, north: float) -> list[VesselPosition]:
        """Return vessels within a geographic bounding box."""
        with self._lock:
            return [
                v for v in self._vessels.values()
                if south <= v.lat <= north and west <= v.lon <= east
            ]

    def to_geojson(self, vessels: list[VesselPosition] | None = None) -> dict:
        """Convert cached vessels to GeoJSON FeatureCollection."""
        if vessels is None:
            vessels = self.get_all()

        features = []
        for v in vessels:
            # Determine vessel color by type
            vtype = (v.vessel_type or "").lower()
            if "tank" in vtype or "oil" in vtype:
                color = "#ef4444"  # red - tanker
            elif "cargo" in vtype:
                color = "#f59e0b"  # amber - cargo
            elif "fish" in vtype:
                color = "#22c55e"  # green - fishing
            elif "passenger" in vtype:
                color = "#8b5cf6"  # purple - passenger
            elif "sailing" in vtype or "pleasure" in vtype:
                color = "#06b6d4"  # cyan - pleasure
            else:
                color = "#94a3b8"  # slate - other/unknown

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [v.lon, v.lat],
                },
                "properties": {
                    "mmsi": v.mmsi,
                    "name": v.vessel_name or f"MMSI-{v.mmsi}",
                    "type": v.vessel_type or "unknown",
                    "sog": v.sog,
                    "cog": v.cog,
                    "heading": v.heading,
                    "imo": v.imo,
                    "flag": v.flag,
                    "nav_status": v.navigation_status,
                    "last_update": v.last_update.isoformat(),
                    "color": color,
                    "message_count": v.message_count,
                },
            })

        return {
            "type": "FeatureCollection",
            "features": features,
        }

    def clear(self) -> None:
        with self._lock:
            self._vessels.clear()
            self._status = AISStreamStatus()


# Global singleton
_cache: AISStreamCache | None = None


def get_ais_cache() -> AISStreamCache:
    global _cache
    if _cache is None:
        _cache = AISStreamCache()
    return _cache


class AISStreamProvider:
    """WebSocket client for AISStream.io real-time vessel positions.

    Runs in a background thread. Automatically reconnects on failure.
    Subscribes to configurable geographic bounding boxes.
    """

    def __init__(
        self,
        api_key: str,
        bbox: list[list[float]] | None = None,
        cache: AISStreamCache | None = None,
    ) -> None:
        self.api_key = api_key
        self.bbox = bbox or INDIAN_OCEAN_BBOX
        self.cache = cache or get_ais_cache()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._connected = False

    def start(self) -> None:
        """Start the background WebSocket listener."""
        if self._thread and self._thread.is_alive():
            logger.warning("AISStream provider already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="aisstream")
        self._thread.start()
        logger.info("AISStream provider started (bbox=%s)", self.bbox)

    def stop(self) -> None:
        """Stop the background listener."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        self._connected = False
        logger.info("AISStream provider stopped")

    def _run_loop(self) -> None:
        """Main loop: connect, subscribe, receive, reconnect."""
        try:
            import websockets.sync.client as ws_sync  # type: ignore[import-untyped]
        except ImportError:
            try:
                import websocket  # type: ignore[import-untyped]
                self._run_loop_legacy(websocket)
                return
            except ImportError:
                logger.error(
                    "AISStream requires a WebSocket library. "
                    "Install: pip install websockets"
                )
                return

        delay = RECONNECT_DELAY_BASE
        while not self._stop_event.is_set():
            try:
                self._connect_and_listen_ws()
                delay = RECONNECT_DELAY_BASE
            except Exception as exc:
                logger.exception("AISStream connection error: %s", exc)
                self.cache._status.connected = False
                self.cache._status.subscription_confirmed = False
                self.cache._status.receive_loop_alive = False
                self.cache._status.last_error = str(exc)
                self.cache._status.reconnect_count += 1
                self._stop_event.wait(delay)
                delay = min(delay * 2, RECONNECT_DELAY_MAX)

    def _connect_and_listen_ws(self) -> None:
        """Connect using websockets.sync.client (Python 3.12+)."""
        import websockets.sync.client as ws_sync  # type: ignore[import-untyped]

        url = f"wss://stream.aisstream.io/v0/stream?apikey={self.api_key}"

        logger.info("AISSTREAM connecting to wss://stream.aisstream.io/v0/stream")
        with ws_sync.connect(url) as ws:
            self._connected = True
            self.cache._status.connected = True
            self.cache._status.last_error = None
            logger.info("AISSTREAM connected successfully")

            # Subscribe to bounding box with FilterMessageTypes for PositionReport only
            subscribe_msg = json.dumps({
                "APIKey": self.api_key,
                "BoundingBoxes": [self.bbox],
                "FilterMessageTypes": ["PositionReport"],
            })
            logger.info("AISSTREAM subscription payload (key redacted): %s",
                        subscribe_msg.replace(self.api_key, "<REDACTED>"))
            ws.send(subscribe_msg)
            self.cache._status.subscribed_areas = 1
            logger.info("AISSTREAM subscription sent (bbox=%s)", self.bbox)

            # Read messages
            subscription_confirmed = False
            total_frames = 0
            position_count = 0
            last_health_log = time.time()
            self.cache._status.receive_loop_alive = True

            while not self._stop_event.is_set():
                try:
                    msg = ws.recv(timeout=5.0)
                    if msg is None:
                        # recv() returned None — connection closed cleanly
                        logger.warning("AISSTREAM recv() returned None — connection closed by server")
                        break

                    total_frames += 1

                    if isinstance(msg, bytes):
                        # Binary frame — try to decode as UTF-8 JSON
                        try:
                            msg = msg.decode("utf-8")
                        except UnicodeDecodeError:
                            logger.warning("AISSTREAM received undecodable binary frame (length=%d)", len(msg))
                            continue

                    # Log every received frame at INFO level for diagnosis
                    preview = msg[:200] if len(msg) > 200 else msg
                    logger.info("AISSTREAM FRAME #%d (len=%d): %s", total_frames, len(msg), preview)

                    # Parse JSON
                    try:
                        data = json.loads(msg)
                    except json.JSONDecodeError:
                        logger.warning("AISSTREAM frame is not valid JSON (length=%d)", len(msg))
                        continue

                    msg_type = data.get("MessageType", "unknown")

                    # Handle SubscriptionConfirmation
                    if msg_type == "SubscriptionConfirmation":
                        subscription_confirmed = True
                        self.cache._status.subscription_confirmed = True
                        logger.info("AISSTREAM SUBSCRIPTION CONFIRMED")
                        continue

                    # Handle PositionReport
                    if msg_type == "PositionReport":
                        position_count += 1
                        self.cache._status.position_reports_received = position_count
                        self._handle_position_report(data)
                        continue

                    # Any other message type — log it
                    logger.info("AISSTREAM other MessageType=%s (not PositionReport)", msg_type)

                except TimeoutError:
                    # No message within 5 seconds — normal, just continue
                    continue
                except Exception as exc:
                    exc_type = type(exc).__name__
                    logger.warning("AISSTREAM recv() exception type=%s: %s", exc_type, exc)
                    self.cache._status.last_error = f"{exc_type}: {exc}"
                    break

                # Periodic health check log
                now = time.time()
                if now - last_health_log >= HEALTH_LOG_INTERVAL:
                    last_health_log = now
                    logger.info(
                        "AISSTREAM HEALTH: connected=%s confirmed=%s frames=%d positions=%d vessels_cached=%d",
                        self._connected, subscription_confirmed, total_frames,
                        position_count, self.cache._status.total_vessels,
                    )

            # exited receive loop
            self.cache._status.receive_loop_alive = False
            self.cache._status.connected = False
            self.cache._status.subscription_confirmed = False
            logger.warning(
                "AISSTREAM receive loop ENDED: confirmed=%s total_frames=%d positions=%d",
                subscription_confirmed, total_frames, position_count,
            )

    def _handle_position_report(self, data: dict) -> None:
        """Parse a PositionReport and update the vessel cache."""
        try:
            msg = data.get("Message", data)

            # Log the raw Message keys for diagnosis
            msg_keys = list(msg.keys()) if isinstance(msg, dict) else []
            logger.info("AISSTREAM POSITION REPORT keys=%s", msg_keys)

            mmsi = str(msg.get("MMSI", ""))
            if not mmsi:
                logger.warning("AISSTREAM POSITION REPORT missing MMSI, keys=%s", msg_keys)
                return

            # Extract position fields
            lat = msg.get("Latitude")
            lon = msg.get("Longitude")
            sog = msg.get("SpeedOverGround")
            cog = msg.get("CourseOverGround")
            heading = msg.get("TrueHeading")
            shipname = msg.get("ShipName")
            shiptype = msg.get("ShipType")

            logger.info(
                "AISSTREAM POSITION REPORT MMSI=%s lat=%s lon=%s sog=%s heading=%s name=%s type=%s",
                mmsi, lat, lon, sog, heading, shipname, shiptype,
            )

            # Filter out None/invalid positions
            if lat is None or lon is None:
                logger.warning("AISSTREAM POSITION REPORT MMSI=%s has null lat/lon — skipping", mmsi)
                return
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                logger.warning("AISSTREAM POSITION REPORT MMSI=%s has invalid coords (%s, %s) — skipping", mmsi, lat, lon)
                return

            pos_data = {
                "lat": lat,
                "lon": lon,
                "sog": sog,
                "cog": cog,
                "heading": heading,
                "shipname": shipname,
                "shiptype": shiptype,
                "imo": msg.get("IMO"),
                "flag": msg.get("Flag"),
                "navstat": msg.get("NavigationalStatus"),
            }

            self.cache.update(mmsi, pos_data)
            cache_size = self.cache._status.total_vessels
            logger.info(
                "AISSTREAM VESSEL CACHED MMSI=%s name=%s cache_size=%d",
                mmsi, shipname or "unknown", cache_size,
            )

        except Exception as exc:
            logger.exception("AISSTREAM POSITION REPORT parse error: %s", exc)

    def _run_loop_legacy(self, websocket_module: Any) -> None:
        """Fallback for websocket-client library."""
        delay = RECONNECT_DELAY_BASE
        while not self._stop_event.is_set():
            try:
                logger.info("AISSTREAM connecting (legacy websocket-client)")
                ws = websocket_module.create_connection(
                    f"wss://stream.aisstream.io/v0/stream?apikey={self.api_key}",
                    timeout=10,
                )
                self._connected = True
                self.cache._status.connected = True
                delay = RECONNECT_DELAY_BASE
                logger.info("AISSTREAM connected successfully (legacy)")

                subscribe_msg = json.dumps({
                    "APIKey": self.api_key,
                    "BoundingBoxes": [self.bbox],
                    "FilterMessageTypes": ["PositionReport"],
                })
                logger.info("AISSTREAM subscription payload (legacy, key redacted): %s",
                            subscribe_msg.replace(self.api_key, "<REDACTED>"))
                ws.send(subscribe_msg)
                self.cache._status.subscribed_areas = 1
                logger.info("AISSTREAM subscription sent (legacy, bbox=%s)", self.bbox)

                subscription_confirmed = False
                total_frames = 0
                position_count = 0
                last_health_log = time.time()
                self.cache._status.receive_loop_alive = True

                while not self._stop_event.is_set():
                    try:
                        ws.settimeout(5.0)
                        msg = ws.recv()
                        if msg is None:
                            logger.warning("AISSTREAM recv() returned None (legacy)")
                            break

                        total_frames += 1
                        if isinstance(msg, bytes):
                            try:
                                msg = msg.decode("utf-8")
                            except UnicodeDecodeError:
                                logger.warning("AISSTREAM undecodable binary frame (legacy, length=%d)", len(msg))
                                continue

                        preview = msg[:200] if len(msg) > 200 else msg
                        logger.info("AISSTREAM FRAME #%d (legacy, len=%d): %s", total_frames, len(msg), preview)

                        try:
                            data = json.loads(msg)
                        except json.JSONDecodeError:
                            logger.warning("AISSTREAM non-JSON frame (legacy, length=%d)", len(msg))
                            continue

                        msg_type = data.get("MessageType", "unknown")

                        if msg_type == "SubscriptionConfirmation":
                            subscription_confirmed = True
                            self.cache._status.subscription_confirmed = True
                            logger.info("AISSTREAM SUBSCRIPTION CONFIRMED (legacy)")
                            continue

                        if msg_type == "PositionReport":
                            position_count += 1
                            self.cache._status.position_reports_received = position_count
                            self._handle_position_report(data)
                            continue

                        logger.info("AISSTREAM other MessageType=%s (legacy)", msg_type)

                    except Exception as exc:
                        exc_type = type(exc).__name__
                        logger.warning("AISSTREAM recv() exception (legacy) type=%s: %s", exc_type, exc)
                        self.cache._status.last_error = f"{exc_type}: {exc}"
                        break

                    now = time.time()
                    if now - last_health_log >= HEALTH_LOG_INTERVAL:
                        last_health_log = now
                        logger.info(
                            "AISSTREAM HEALTH (legacy): confirmed=%s frames=%d positions=%d vessels_cached=%d",
                            subscription_confirmed, total_frames, position_count,
                            self.cache._status.total_vessels,
                        )

                self.cache._status.receive_loop_alive = False
                self.cache._status.connected = False
                self.cache._status.subscription_confirmed = False
                ws.close()
                logger.warning(
                    "AISSTREAM connection closed (legacy): confirmed=%s frames=%d positions=%d",
                    subscription_confirmed, total_frames, position_count,
                )
            except Exception:
                logger.exception("AISStream legacy connection error")
                self.cache._status.connected = False
                self.cache._status.subscription_confirmed = False
                self.cache._status.receive_loop_alive = False
                self.cache._status.reconnect_count += 1
                self._stop_event.wait(delay)
                delay = min(delay * 2, RECONNECT_DELAY_MAX)


def create_aisstream_provider(api_key: str) -> AISStreamProvider | None:
    """Factory: create AISStream provider if API key is configured."""
    if not api_key:
        logger.info("AISStream API key not configured — real-time AIS disabled")
        return None
    return AISStreamProvider(api_key=api_key)
