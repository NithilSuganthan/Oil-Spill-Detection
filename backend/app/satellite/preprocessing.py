"""Configurable SAR preprocessing framework.

IMPORTANT: the final MODEL-specific preprocessing is NOT known yet (the
trained segmentation checkpoint has not been delivered). This module therefore
provides an ordered, independently-configurable stage pipeline. Stages are
selected via settings (`PREPROCESSING_STAGES` JSON list) so the ML contract
can be slotted in later WITHOUT code changes.

Default GRD chain (safe, model-agnostic):
    subset_bbox -> extract_polarization -> to_db -> normalize_percentile
    (nodata handled throughout; ocean_mask/tiling available but off by default)

Each stage receives a RasterData and returns a RasterData; provenance of every
stage is recorded for auditability.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from app.geospatial.raster import RasterData

logger = logging.getLogger(__name__)

DEFAULT_STAGE_NAMES = ["subset_bbox", "to_db", "normalize_percentile"]


class PreprocessingError(RuntimeError):
    pass


@dataclass
class StageResult:
    name: str
    params: dict
    note: str


# ----------------------------------------------------------------------
# Stage implementations.
# Signature: (raster: RasterData, params: dict) -> RasterData
# ----------------------------------------------------------------------


def stage_subset_bbox(raster: RasterData, params: dict) -> RasterData:
    """Window-read to a lon/lat bbox {"bbox": [w,s,e,n]} — keeps memory sane
    for full GRD scenes. Requires a geographic raster; skipped otherwise."""
    bbox = params.get("bbox")
    if not bbox:
        return raster
    import rasterio.warp
    from rasterio.windows import from_bounds

    w, s, e, n = (float(v) for v in bbox)
    src_crs = raster.crs
    # transform WGS84 bbox into raster CRS if needed
    try:
        import rasterio

        with rasterio.MemoryFile() as mem:
            pass
    except Exception:  # pragma: no cover - defensive
        return raster

    if not str(src_crs).upper().startswith("EPSG:4326"):
        from pyproj import Transformer

        transformer = Transformer.from_crs("EPSG:4326", src_crs, always_xy=True)
        xs, ys = transformer.transform([w, e], [s, n])
        w, e = min(xs), max(xs)
        s, n = min(ys), max(ys)

    window = from_bounds(w, s, e, n, transform=raster.transform)
    row_off, col_off = max(int(window.row_off), 0), max(int(window.col_off), 0)
    height = min(int(window.height), raster.data.shape[0] - row_off)
    width = min(int(window.width), raster.data.shape[1] - col_off)
    if height <= 0 or width <= 0:
        raise PreprocessingError("subset_bbox does not intersect the raster")
    data = raster.data[row_off:row_off + height, col_off:col_off + width]
    from rasterio.transform import Affine

    new_transform = raster.transform * Affine.translation(col_off, row_off)
    return RasterData(
        data=data,
        transform=new_transform,
        crs=raster.crs,
        meta={**raster.meta, "width": width, "height": height},
    )


def stage_extract_polarization(raster: RasterData, params: dict) -> RasterData:
    """Select one band/polarization: params {"polarization": "vv"} (default vv).
    Multi-band inputs are reduced; single-band inputs pass through."""
    pol = str(params.get("polarization", "vv")).lower()
    band_names = raster.meta.get("band_names") or []
    if band_names:
        match = next(
            (i + 1 for i, bname in enumerate(band_names) if pol in bname.lower()), None
        )
        band = match or 1
    else:
        band = 1
    data = raster.data if raster.data.ndim == 2 else raster.data[band - 1]
    meta = {**raster.meta, "polarization": pol}
    return RasterData(data=np.asarray(data), transform=raster.transform, crs=raster.crs, meta=meta)


def stage_to_db(raster: RasterData, params: dict) -> RasterData:
    """Convert linear-power sigma0 to dB: 10*log10(x). Guarded against <=0.
    No-op when params {"enabled": false} or values already look like dB."""
    if not params.get("enabled", True):
        return raster
    finite = raster.data[np.isfinite(raster.data)]
    if finite.size and float(finite.min()) < 0:
        # negative values imply dB already (linear power is >= 0)
        return raster
    safe = np.where(raster.data > 0, raster.data, np.nan).astype(np.float32)
    with np.errstate(divide="ignore", invalid="ignore"):
        db = 10.0 * np.log10(safe)
    return RasterData(data=db.astype(np.float32), transform=raster.transform, crs=raster.crs,
                      meta={**raster.meta, "unit": "dB"})


def stage_calibration(raster: RasterData, params: dict) -> RasterData:
    """Radiometric calibration hook.

    mode "passthrough" (default): input assumed already-calibrated sigma0
    (true for CDSE COG GRD derivatives). mode "dn_lut": NOT implemented yet —
    requires the SAFE calibration LUTs; raises so nothing silently fakes it.
    """
    mode = str(params.get("mode", "passthrough")).lower()
    if mode == "passthrough":
        return raster
    raise PreprocessingError(
        f"calibration mode '{mode}' requires LUT files; not implemented until "
        "the trained-model preprocessing contract defines it"
    )


def stage_normalize_percentile(raster: RasterData, params: dict) -> RasterData:
    """Percentile clip-and-scale to [0,1]. params {"low":1,"high":99}."""
    lo_pct = float(params.get("low", 1.0))
    hi_pct = float(params.get("high", 99.0))
    data = raster.data.astype(np.float32, copy=True)
    finite = data[np.isfinite(data)]
    if not finite.size:
        return raster
    lo, hi = np.percentile(finite, [lo_pct, hi_pct])
    denom = (hi - lo) or 1.0
    normed = np.clip((data - lo) / denom, 0.0, 1.0)
    normed[~np.isfinite(normed)] = 0.0
    return RasterData(data=normed, transform=raster.transform, crs=raster.crs,
                      meta={**raster.meta, "normalization": f"percentile-{lo_pct}-{hi_pct}"})


def stage_nodata_mask(raster: RasterData, params: dict) -> RasterData:
    """Replace nodata/zero/non-finite cells with params {"fill": 0.0}."""
    fill = params.get("fill", None)
    data = raster.data.astype(np.float32, copy=True)
    nodata = raster.meta.get("nodata")
    bad = ~np.isfinite(data)
    if nodata is not None:
        bad |= data == float(nodata)
    if params.get("mask_zeros", True):
        bad |= data == 0.0
    if fill is not None:
        data[bad] = float(fill)
    else:
        data[bad] = np.nan
    return RasterData(data=data, transform=raster.transform, crs=raster.crs, meta=raster.meta)


def stage_resample(raster: RasterData, params: dict) -> RasterData:
    """Resample by integer factor {"factor": 4} using bilinear averaging."""
    factor = int(params.get("factor", 2))
    if factor <= 1:
        return raster
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    height = max(raster.data.shape[0] // factor, 1)
    width = max(raster.data.shape[1] // factor, 1)
    from rasterio.transform import Affine

    dst_transform = raster.transform * Affine.scale(factor, factor)
    dst = np.zeros((height, width), dtype=np.float32)
    reproject(
        source=raster.data.astype(np.float32),
        destination=dst,
        src_transform=raster.transform,
        src_crs=raster.crs,
        dst_transform=dst_transform,
        dst_crs=raster.crs,
        resampling=Resampling.average,
    )
    return RasterData(data=dst, transform=dst_transform, crs=raster.crs,
                      meta={**raster.meta, "width": width, "height": height})


def stage_ocean_mask(raster: RasterData, params: dict) -> RasterData:
    """Land-mask placeholder. Accepts {"land_geojson": ...}; without a land
    polygon this is a documented NO-OP (a GSHHG/coastline source will be
    integrated separately — never guessed here)."""
    land = params.get("land_geojson")
    if not land:
        logger.info("ocean_mask stage: no land polygons configured — no-op")
        return raster
    import rasterio.features
    import shapely.geometry

    geom = shapely.geometry.shape(land["geometry"] if "geometry" in land else land)
    mask = rasterio.features.geometry_mask(
        [geom], out_shape=raster.data.shape, transform=raster.transform, invert=False
    )
    data = raster.data.copy()
    data[mask] = np.nan
    return RasterData(data=data, transform=raster.transform, crs=raster.crs, meta=raster.meta)


def stage_tiling(raster: RasterData, params: dict) -> RasterData:
    """Metadata-only tiling descriptor; actual tile materialization happens at
    inference time once the model's tile/stitch strategy is known."""
    size = int(params.get("tile_size", 512))
    h, w = raster.data.shape
    raster.meta["tiles"] = {
        "tile_size": size,
        "cols": (w + size - 1) // size,
        "rows": (h + size - 1) // size,
    }
    return raster


STAGES: dict[str, Callable[[RasterData, dict], RasterData]] = {
    "subset_bbox": stage_subset_bbox,
    "extract_polarization": stage_extract_polarization,
    "calibration": stage_calibration,
    "to_db": stage_to_db,
    "normalize_percentile": stage_normalize_percentile,
    "nodata_mask": stage_nodata_mask,
    "resample": stage_resample,
    "ocean_mask": stage_ocean_mask,
    "tiling": stage_tiling,
}


# ----------------------------------------------------------------------
@dataclass
class PreprocessingReport:
    stages_run: list[StageResult] = field(default_factory=list)

    def to_dict(self) -> list[dict[str, Any]]:
        return [{"name": sr.name, "params": sr.params, "note": sr.note} for sr in self.stages_run]


def build_pipeline(config: str | list[dict] | None) -> list[tuple[str, dict]]:
    """Resolve stage configuration into [(name, params)] preserving order."""
    if config is None or config == "" or config == []:
        return [(name, {}) for name in DEFAULT_STAGE_NAMES]
    if isinstance(config, str):
        parsed = json.loads(config)
    else:
        parsed = config
    if not isinstance(parsed, list):
        raise PreprocessingError("preprocessing_stages must be a JSON list of {name, ...}")
    resolved: list[tuple[str, dict]] = []
    for entry in parsed:
        if isinstance(entry, str):
            entry = {"name": entry}
        name = entry.get("name")
        if name not in STAGES:
            raise PreprocessingError(
                f"Unknown preprocessing stage '{name}'. Available: {sorted(STAGES)}"
            )
        params = {k: v for k, v in entry.items() if k != "name"}
        resolved.append((name, params))
    return resolved


def run_pipeline(raster: RasterData, stages: list[tuple[str, dict]]) -> tuple[RasterData, PreprocessingReport]:
    report = PreprocessingReport()
    current = raster
    for name, params in stages:
        fn = STAGES[name]
        before_shape = getattr(current.data, "shape", None)
        current = fn(current, params)
        note = f"shape {before_shape} -> {current.data.shape}"
        report.stages_run.append(StageResult(name=name, params=params, note=note))
        logger.info("preprocess stage %-22s %s", name, note)
    return current, report
