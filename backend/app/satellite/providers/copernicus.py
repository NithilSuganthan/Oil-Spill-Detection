"""REAL Copernicus Data Space Ecosystem provider.

Discovery uses the official CDSE STAC catalogue (STAC 1.1.0):
    https://stac.dataspace.copernicus.eu/v1/search
Search is anonymous; downloads authenticate against the CDSE Keycloak realm.

Download uses the OData product endpoint surfaced in each STAC item's
`Product` asset:
    https://download.dataspace.copernicus.eu/odata/v1/Products(<uuid>)/$value
Products are streamed to storage in chunks — never buffered in RAM.

Endpoints are configurable via settings so they can be updated without code
changes if Copernicus migrates them.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import httpx

from app.domain.entities import SatelliteSceneRecord
from app.satellite.aoi import AreaOfInterest
from app.satellite.auth import CdseTokenManager
from app.satellite.providers.base import (
    DownloadOptions,
    ProviderInfo,
    SceneQuery,
    SatelliteSceneProvider,
)
from app.satellite.storage import StorageBackend, StoredFile

logger = logging.getLogger(__name__)

SENTINEL_1_GRD_COLLECTION = "sentinel-1-grd"


class CopernicusSatelliteProvider(SatelliteSceneProvider):
    """Real Sentinel-1 GRD discovery + acquisition from CDSE."""

    def __init__(
        self,
        auth: CdseTokenManager,
        stac_search_url: str = "https://stac.dataspace.copernicus.eu/v1/search",
        stac_item_url: str = "https://stac.dataspace.copernicus.eu/v1/collections/sentinel-1-grd/items/{item_id}",
        http_client: httpx.Client | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._auth = auth
        self._stac_search_url = stac_search_url
        self._stac_item_url = stac_item_url
        self._client = http_client or httpx.Client(timeout=timeout)
        self._owns_client = http_client is None

    # ------------------------------------------------------------------ info
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="copernicus",
            is_real=True,
            description="Copernicus Data Space Ecosystem (STAC catalogue + OData download)",
            extra={"collection": SENTINEL_1_GRD_COLLECTION},
        )

    # ---------------------------------------------------------------- search
    def search_scenes(
        self,
        query: SceneQuery,
        aoi: AreaOfInterest | None = None,
    ) -> list[SatelliteSceneRecord]:
        bbox = query.bbox or (aoi.bbox if aoi else None)
        if bbox is None:
            raise ValueError("SceneQuery requires a bbox or an AOI")

        params: dict[str, str] = {
            "collections": SENTINEL_1_GRD_COLLECTION,
            "bbox": ",".join(f"{v:.4f}" for v in bbox),
            "limit": str(min(query.limit, 200)),
        }
        dt_start = query.start or datetime(2014, 10, 1, tzinfo=timezone.utc)
        dt_end = query.end or datetime.now(timezone.utc)
        params["datetime"] = f"{_iso(dt_start)}/{_iso(dt_end)}"

        resp = self._client.get(
            self._stac_search_url,
            params=params,
            headers={"Accept": "application/geo+json"},
        )
        _raise_for_status(resp, "STAC search")

        items = resp.json().get("features", [])
        scenes = [_item_to_scene(item) for item in items]

        # client-side refinement (portable across STAC backends)
        if query.platform:
            want = query.platform.strip().lower()
            scenes = [s for s in scenes if want in s.platform.lower()]
        if query.product_type:
            want_pt = query.product_type.strip().upper()
            scenes = [s for s in scenes if s.product_type == want_pt]
        if query.geometry is not None and aoi is not None:
            scenes = [s for s in scenes if aoi.intersects_geometry(s.geometry)]
        elif aoi is not None:
            scenes = [
                s for s in scenes
                if s.footprint and aoi.intersects_bbox(tuple(s.footprint))
            ]
        return scenes[: query.limit]

    # ------------------------------------------------------------- metadata
    def get_scene_metadata(self, scene_id: str) -> SatelliteSceneRecord | None:
        url = self._stac_item_url.format(item_id=scene_id)
        resp = self._client.get(url, headers={"Accept": "application/geo+json"})
        if resp.status_code == 404:
            return None
        _raise_for_status(resp, f"STAC item {scene_id}")
        return _item_to_scene(resp.json())

    # -------------------------------------------------------------- download
    def download_scene(
        self,
        scene: SatelliteSceneRecord,
        storage: StorageBackend,
        options: DownloadOptions | None = None,
    ) -> StoredFile:
        opts = options or DownloadOptions()
        if not scene.download_url:
            raise ValueError(f"Scene {scene.id} has no download URL")
        key = f"products/{scene.id}.zip"

        last_error: Exception | None = None
        for attempt in range(1, opts.max_retries + 1):
            try:
                return self._attempt_download(scene, storage, key, opts)
            except (httpx.HTTPError, IOError) as exc:
                last_error = exc
                logger.warning(
                    "Download attempt %d/%d failed for %s: %s",
                    attempt, opts.max_retries, scene.id, exc,
                )
                if attempt < opts.max_retries:
                    time.sleep(opts.retry_backoff_seconds * attempt)
                    self._auth.invalidate()  # token may have expired mid-stream
        raise IOError(
            f"Download of {scene.id} failed after {opts.max_retries} attempts: {last_error}"
        ) from last_error

    def _attempt_download(
        self,
        scene: SatelliteSceneRecord,
        storage: StorageBackend,
        key: str,
        opts: DownloadOptions,
    ) -> StoredFile:
        token = self._auth.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        with self._client.stream("GET", scene.download_url, headers=headers) as resp:
            _raise_for_status(resp, f"Download {scene.id}")
            total = _content_length(resp.headers)

            def chunks():
                done = 0
                chunk_bytes = int(opts.chunk_size_mb * 1024 * 1024)
                for raw in resp.iter_bytes(chunk_bytes):
                    done += len(raw)
                    if opts.progress_cb:
                        opts.progress_cb(done, total)
                    yield raw

            stored = storage.save_stream(key, chunks(), expected_size=total)
        logger.info(
            "Downloaded %s (%.2f MB) -> %s",
            scene.id, stored.size_bytes / 1e6, stored.url,
        )
        return stored

    def fetch_thumbnail(self, scene: SatelliteSceneRecord) -> bytes | None:
        """Fetch the small public quicklook PNG for a scene, if available."""
        url = getattr(scene, "thumbnail_url", None) or (
            scene.metadata_extra.get("thumbnail_url") if scene.metadata_extra else None
        )
        if not url:
            return None
        try:
            resp = self._client.get(url)
            _raise_for_status(resp, "thumbnail")
            return resp.content
        except httpx.HTTPError as exc:
            logger.warning("Thumbnail fetch failed for %s: %s", scene.id, exc)
            return None


# ----------------------------------------------------------------------
def _raise_for_status(resp, context: str) -> None:
    if resp.status_code == 401:
        raise PermissionError(
            f"{context}: unauthorized. Check CDSE credentials in the environment."
        )
    if resp.status_code >= 400:
        raise IOError(f"{context}: HTTP {resp.status_code}")


def _content_length(headers) -> int | None:
    try:
        value = headers.get("content-length") or headers.get("Content-Length")
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _title_platform(raw: str | None) -> str:
    """'sentinel-1a' -> 'Sentinel-1A'; unknown values pass through."""
    if not raw:
        return "Sentinel-1"
    slug = raw.strip().lower()
    if slug.startswith("sentinel-"):
        suffix = slug.split("-", 1)[1]
        return f"Sentinel-{suffix.upper()}" if suffix else "Sentinel-1"
    return raw


def _item_to_scene(item: dict) -> SatelliteSceneRecord:
    """Map one CDSE STAC item to our domain record (real data, is_demo=False)."""
    props = item.get("properties", {})
    private = props.get("_private", {}) or {}
    assets = item.get("assets", {}) or {}

    geometry = item.get("geometry")
    footprint = None
    if geometry:
        import shapely.geometry

        bounds = shapely.geometry.shape(geometry).bounds
        footprint = tuple(round(v, 6) for v in bounds)  # type: ignore[assignment]

    polarizations = props.get("sar:polarizations") or []
    download_url = (assets.get("Product") or {}).get("href") or (
        f"https://download.dataspace.copernicus.eu/odata/v1/"
        f"Products({private.get('product_uuid')})/$value"
        if private.get("product_uuid") else None
    )
    thumbnail_url = (assets.get("thumbnail") or {}).get("href")

    acquired = _parse_dt(props.get("start_datetime") or props.get("datetime"))
    processed = _parse_dt(props.get("processing:datetime"))

    return SatelliteSceneRecord(
        id=item["id"],
        platform=_title_platform(props.get("platform")),
        sensor="SAR C-band",
        acquisition_mode=props.get("sar:instrument_mode", "IW"),
        polarisation=" + ".join(polarizations) if polarizations else "VV + VH",
        acquired_at=acquired,
        processed_at=processed,
        footprint=footprint,  # type: ignore[arg-type]
        status="discovered",
        image_path=None,
        is_demo=False,
        product_id=private.get("product_uuid") or item["id"],
        product_name=private.get("product_name") or item["id"],
        source_provider="copernicus",
        orbit_state=props.get("sat:orbit_state"),
        absolute_orbit=props.get("sat:absolute_orbit"),
        relative_orbit=props.get("sat:relative_orbit"),
        download_url=download_url,
        file_size_bytes=private.get("product_size"),
        product_type=props.get("product:type", ""),
        thumbnail_url=thumbnail_url,
        geometry=geometry,
        metadata_extra={
            "incidence_angle_deg": props.get("view:incidence_angle"),
            "pixel_spacing_range_m": props.get("sar:pixel_spacing_range"),
            "pixel_spacing_azimuth_m": props.get("sar:pixel_spacing_azimuth"),
            "processing_level": props.get("processing:level"),
            "timeliness": props.get("product:timeliness"),
        },
    )


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
