"""Real Sentinel-1 GRD preprocessing pipeline.

Scientific basis (documented per requirement "DO NOT GUESS"):

* Calibration: sigma0 = DN^2 / A_sigma^2 with A_sigma bilinearly interpolated
  between the product's calibration vectors. Sources:
    - ESA SNAP CalibrationOp documentation ("The radiometric calibration is
      applied by ... value(i) = |DN_i|^2 / A_i^2"; LUTs include the absolute
      calibration constant and range-dependent gain)
    - Copernicus eopf S1 L12 RP ATBD eq. 6.4: sigma0 = DN^2 / A_sigma^2
  betaNought/gamma LUTs follow the identical form and are parsed for provenance.

* Thermal noise: denoised sigma0 = (DN^2 - eta_rg*eta_az) / A_sigma^2
  (ESA noise LUT convention). Implemented but DISABLED by default — the final
  model input representation is not yet defined; uncorrected ESA-standard
  Level-1 sigma0 is produced until the ML contract decides. Rationale is
  recorded in the provenance report.

* Georeferencing: measurement TIFFs carry no CRS/affine; geolocation comes
  from the GCP table embedded in each measurement TIFF. Outputs are warped to
  a regular grid via GDAL (polynomial fit over GCPs) into a configurable CRS
  (default EPSG:4326) at configurable resolution (default ~10 m equivalent).

Memory policy: full-scene channels are NEVER loaded. Calibration runs in
row-block windows; statistics accumulate incrementally.
"""

from __future__ import annotations

import json
import logging
import platform
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.satellite.s1_metadata import (
    CalibrationLut,
    GcpDiagnostics,
    SafeProduct,
    discover_safe_product,
    extract_gcps,
    parse_calibration_xml,
    parse_noise_xml,
    read_image_annotation,
    validate_gcps,
)

logger = logging.getLogger(__name__)

DEFAULT_BLOCK_ROWS = 256


class GrdPreprocessError(RuntimeError):
    """Raised when a quality gate fails. Carries all accumulated failures."""


# ----------------------------------------------------------------------
@dataclass
class GrdConfig:
    target_crs: str = "EPSG:4326"
    target_resolution_m: float = 10.0        # preserved from source GRD
    resampling: str = "bilinear"             # continuous calibrated field
    apply_noise_removal: bool = False        # documented default-off (see module docstring)
    block_rows: int = DEFAULT_BLOCK_ROWS
    gcp_poly_order: int = 3                  # GDAL-style GCP warp polynomial

    @classmethod
    def from_settings(cls, settings) -> "GrdConfig":
        return cls(
            target_crs=settings.grd_target_crs,
            target_resolution_m=settings.grd_target_resolution_m,
            resampling=settings.grd_resampling,
            apply_noise_removal=settings.grd_apply_noise_removal,
            gcp_poly_order=settings.grd_gcp_poly_order,
        )


@dataclass
class BandStats:
    valid_px: int = 0
    invalid_px: int = 0
    minimum: float = float("inf")
    maximum: float = float("-inf")
    sum: float = 0.0
    sum_sq: float = 0.0

    def update(self, arr: np.ndarray, valid_mask: np.ndarray) -> None:
        v = arr[valid_mask].astype(np.float64)
        self.valid_px += int(valid_mask.sum())
        self.invalid_px += int((~valid_mask).sum())
        if v.size:
            self.minimum = min(self.minimum, float(v.min()))
            self.maximum = max(self.maximum, float(v.max()))
            self.sum += float(v.sum())
            self.sum_sq += float(np.square(v).sum())

    def finalize(self) -> dict:
        mean = self.sum / self.valid_px if self.valid_px else None
        var = (self.sum_sq / self.valid_px - (self.sum / self.valid_px) ** 2) if self.valid_px else None
        total = self.valid_px + self.invalid_px
        return {
            "valid_pixels": self.valid_px,
            "invalid_pixels": self.invalid_px,
            "valid_fraction": round(self.valid_px / total, 5) if total else None,
            "min": self.minimum if self.valid_px else None,
            "max": self.maximum if self.valid_px else None,
            "mean": round(mean, 6) if mean is not None else None,
            "std": round(max(var, 0.0) ** 0.5, 6) if var is not None else None,
        }


# ----------------------------------------------------------------------
class GrdPreprocessor:
    """One real GRD product -> calibrated + georeferenced SAR products."""

    def __init__(
        self,
        scene_id: str,
        workspace_root: str | Path,
        config: GrdConfig | None = None,
        state_cb=None,          # callable(state_name, detail_dict|None)
    ) -> None:
        self.scene_id = scene_id
        self.root = Path(workspace_root) / scene_id
        self.config = config or GrdConfig()
        self._state_cb = state_cb or (lambda *_: None)
        self.report: dict = {"scene_id": scene_id}
        self._t0 = time.perf_counter()

    # ---------------------------------------------------------------- helpers
    def _state(self, name: str, detail: dict | None = None) -> None:
        logger.info("GRD preprocess [%s] %s %s", self.scene_id, name, detail or "")
        self._state_cb(name, detail)

    def _dir(self, sub: str) -> Path:
        d = self.root / sub
        d.mkdir(parents=True, exist_ok=True)
        return d

    def elapsed_s(self) -> float:
        return round(time.perf_counter() - self._t0, 1)

    # ---------------------------------------------------------------- stages
    def run(self, product_zip: str | Path, expected_bbox: tuple[float, float, float, float] | None = None) -> dict:
        """Full chain. Returns the provenance report dict."""
        failures: list[str] = []
        try:
            safe = self._extract(product_zip)
            gcps_vv, ann_info = self._geolocate(safe, expected_bbox)
            products = {}
            for pol in safe.polarizations:
                products[pol] = self._calibrate_and_georeference(safe, pol, gcps_vv, expected_bbox, failures)
            self._state("VALIDATING")
            self._validate(products, gcps_vv, expected_bbox, failures)
            previews = self.generate_previews(products)
            self.report["previews"] = previews
            self._state("VALIDATED", {"previews": len(previews), "failures": len(failures)})
            self.report.update({
                "status": "PROCESSED" if not failures else "COMPLETED_WITH_FAILURES",
                "quality_failures": failures,
                "outputs": products,
                "elapsed_s": self.elapsed_s(),
            })
            self._write_report()
            self._state("PROCESSED", {"failures": len(failures)})
            if failures:
                raise GrdPreprocessError("; ".join(failures))
            return self.report
        except GrdPreprocessError:
            raise
        except Exception as exc:  # noqa: BLE001 — converted into stage-tagged failure
            self.report["status"] = f"FAILED"
            self.report["error"] = str(exc)
            self._write_report()
            raise GrdPreprocessError(f"{type(exc).__name__}: {exc}") from exc

    # ------------------------------------------------------------ 1. extract
    def _extract(self, product_zip: str | Path) -> SafeProduct:
        self._state("EXTRACTING")
        safe = discover_safe_product(product_zip)   # verifies CRC + structure
        meta_dir = self._dir("metadata")
        raw_dir = self._dir("raw")
        # extract ONLY the small XML/preview members — the giant measurement
        # TIFFs stay in the untouched ZIP and are read through /vsizip/.
        with __import__("zipfile").ZipFile(product_zip) as zf:
            for member in [
                safe.manifest_name, *safe.annotations.values(),
                *safe.calibration.values(), *safe.noise.values(),
            ]:
                target = (meta_dir / member.split("/", 1)[1])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(member))
        self.safe = safe
        self.report["product_structure"] = {
            "safe_root": safe.safe_root,
            "polarizations": safe.polarizations,
            "measurement_members": safe.measurements,
            "calibration_members": safe.calibration,
            "noise_members": safe.noise,
            "annotation_members": safe.annotations,
        }
        (raw_dir / "EXTRACTION_NOTE.txt").write_text(
            "Measurement TIFFs are NOT duplicated here. The original ZIP is the\n"
            "immutable raw archive; rasters were accessed read-only via /vsizip/.\n",
            encoding="utf-8",
        )
        self._state("EXTRACTED", {"polarizations": safe.polarizations})
        return safe

    # --------------------------------------------------- 2. geolocation info
    def _geolocate(self, safe: SafeProduct, expected_bbox):
        vv_path = f"/vsizip/{safe.zip_path}/{safe.measurements['vv']}"
        gcps, gcp_crs = extract_gcps(vv_path)
        diag = validate_gcps(gcps, expected_bbox)
        ann_info = read_image_annotation(safe.member_text(safe.annotations["vv"]))
        self.report["gcps"] = {
            "count": diag.count,
            "crs": str(gcp_crs),
            "lat_range": [diag.lat_min, diag.lat_max],
            "lon_range": [diag.lon_min, diag.lon_max],
            "diagnostics": diag.to_dict(),
        }
        self.report["source_annotation"] = ann_info
        self._write_gcp_diagnostic_image(vv_path, gcps)
        self._state("GEOLOCATION_PARSED", {
            "gcp_count": diag.count, "warnings": diag.warnings,
        })
        return gcps, ann_info

    # ------------------------------------------- 3+4. calibrate & warp & dB
    def _calibrate_and_georeference(
        self, safe: SafeProduct, pol: str, gcps_vv, expected_bbox, failures: list[str]
    ) -> dict:
        import rasterio

        member = safe.measurements[pol]
        src_path = f"/vsizip/{safe.zip_path}/{member}"
        self._state("CALIBRATION_STARTED", {"pol": pol})
        cal = parse_calibration_xml(safe.member_text(safe.calibration[pol]),
                                    source_file=safe.calibration[pol])
        noise = parse_noise_xml(safe.member_text(safe.noise[pol]),
                                source_file=safe.noise[pol]) if pol in safe.noise else None
        if cal.polarisation and cal.polarisation.upper() != pol.upper():
            raise GrdPreprocessError(
                f"calibration XML polarisation {cal.polarisation!r} != band {pol!r}")

        cal_dir = self._dir("calibrated")
        geo_dir = self._dir("georeferenced")
        db_dir = self._dir("model_input")

        linear_rel = f"calibrated/{pol}_sigma0_linear.tif"
        linear_path = self.root / linear_rel
        stats = BandStats()

        with rasterio.open(src_path) as src:
            width, height = src.width, src.height
            dtype = src.dtypes[0]
            src_nodata = src.nodata
            gcps, gcp_crs = src.gcps
            profile = {
                "driver": "GTiff", "width": width, "height": height,
                "count": 1, "dtype": "float32", "nodata": float("nan"),
                "compress": "deflate", "predictor": 3, "tiled": True,
                "blockxsize": 512, "blockysize": 512,
            }
            with rasterio.open(linear_path, "w", **profile) as dst:
                dst.gcps = (gcps, gcp_crs)          # preserve GCP geolocation
                dst.update_tags(
                    sar_quantity="sigma0_linear_power",
                    units="linear power (dimensionless)",
                    formula="sigma0 = DN^2 / A_sigma^2 ; A_sigma bilinear-interpolated LUT",
                    polarization=pol.upper(),
                    source_member=member,
                    thermal_noise_removed=str(self.config.apply_noise_removal),
                    label="SAR backscatter - calibrated linear sigma0",
                )
                for row0 in range(0, height, self.config.block_rows):
                    row1 = min(row0 + self.config.block_rows, height)
                    window = rasterio.windows.Window(0, row0, width, row1 - row0)
                    dn = src.read(1, window=window).astype(np.float64)
                    lut = cal.interpolate(
                        np.arange(row0, row1), np.arange(width), "sigmaNought")
                    dn2 = np.square(dn, where=dn > 0, out=np.zeros_like(dn))
                    if self.config.apply_noise_removal and noise is not None:
                        eta = noise.noise_power_block(row0, row1, width)
                        dn2 = np.maximum(dn2 - eta, 0.0)
                    sigma0 = dn2 / np.square(lut)
                    valid = (dn > 0) & np.isfinite(sigma0)   # DN==0 is nodata
                    sigma0[~valid] = np.nan
                    stats.update(sigma0, valid)
                    dst.write(sigma0.astype(np.float32), 1, window=window)

        st = stats.finalize()
        if st["valid_fraction"] is not None and st["valid_fraction"] < 0.30:
            failures.append(f"{pol}: valid pixel fraction only {st['valid_fraction']:.3f}")
        plausible = (
            st["max"] is not None
            and np.isfinite(st["max"]) and np.isfinite(st["mean"])
            and 0 < st["mean"] < 1e5
        )
        if not plausible:
            failures.append(f"{pol}: calibrated sigma0 range implausible ({st})")
        self._state("CALIBRATION_COMPLETED", {"pol": pol, "stats": st})

        # ---- georeference: GCP -> regular grid in target CRS --------------
        self._state("GEOREFERENCING_STARTED", {"pol": pol})
        geo_rel = f"georeferenced/{pol}_sigma0_{self.config.target_crs.replace(':', '').lower()}.tif"
        geo_path = self.root / geo_rel
        self._warp_to_grid(linear_path, geo_path, gcps, gcp_crs,
                           expected_bbox=expected_bbox)

        # ---- dB representation on the georeferenced grid ------------------
        db_rel = f"model_input/{pol}_sigma0_db.tif"
        db_path = self.root / db_rel
        db_stats = self._to_db(geo_path, db_path)
        self._state("GEOREFERENCING_COMPLETED", {"pol": pol})

        result = {
            "polarization": pol.upper(),
            "calibration": {
                "method": "sigma0 = DN^2 / A_sigma^2 (A_sigma bilinear-interpolated between calibration vectors)",
                "units": "linear power (dimensionless backscatter coefficient)",
                "lut_file": safe.calibration[pol],
                "lut_absolute_constant": cal.absolute_constant,
                "lut_anchors": {"lines": len(cal.lines), "pixels": len(cal.pixels)},
                "thermal_noise_removed": self.config.apply_noise_removal,
                "noise_lut_parsed": noise.describe() if noise else None,
                "reference": "ESA SNAP CalibrationOp; eopf S1 L12 ATBD eq 6.3-6.4",
            },
            "outputs": {
                "linear_gcp_referenced": linear_rel,
                "georeferenced": geo_rel,
                "db": db_rel,
                "dn_note": "DN representation remains in the immutable source ZIP "
                           "(identical values); duplicating it adds no information.",
            },
            "stats_linear": st,
            "stats_db": db_stats,
            "dimensions": {"width_px": width, "height_px": height},
            "dtype_source": dtype,
            "source_nodata": src_nodata,
        }
        self._state("CALIBRATED_GEOREFERENCED", {"pol": pol})
        return result

    def _warp_to_grid(self, src_path: Path, dst_path: Path, gcps, gcp_crs,
                      expected_bbox=None) -> None:
        """GCP-based georeferencing.

        Method:
          1. Least-squares forward/inverse polynomial fits over the product
             GCPs using coordinates NORMALIZED to [-1, 1]. (Raw pixel indices
             make an unnormalized cubic design numerically unusable: x^3
             reaches ~1.6e13 and the fit blows up at the borders.)
          2. Output grid taken from the advertised footprint when available
             (deterministic); otherwise from the fitted border. Guarded
             against pathological sizes.
          3. Blockwise bi-linear sampling of the calibrated raster through
             the inverse polynomial; NaN nodata propagates conservatively.
        """
        import numpy as np
        import rasterio
        from pyproj import Transformer
        from rasterio.transform import from_origin

        if not gcps:
            raise GrdPreprocessError("cannot georeference: product has no GCPs")
        order = self.config.gcp_poly_order

        with rasterio.open(src_path) as src_meta:
            W, H = src_meta.width, src_meta.height

        # normalized source-pixel coordinates
        def nx_src(x):
            return 2.0 * np.asarray(x, np.float64) / max(W - 1, 1) - 1.0

        def ny_src(y):
            return 2.0 * np.asarray(y, np.float64) / max(H - 1, 1) - 1.0

        def design(nx, ny):
            nx = np.asarray(nx, np.float64)
            ny = np.asarray(ny, np.float64)
            cols = [np.ones_like(nx), nx, ny]
            if order >= 2:
                cols += [nx * nx, nx * ny, ny * ny]
            if order >= 3:
                cols += [nx ** 3, nx * nx * ny, nx * ny * ny, ny ** 3]
            return np.stack(cols, axis=1)

        px = np.array([g.col for g in gcps], dtype=np.float64)
        py = np.array([g.row for g in gcps], dtype=np.float64)
        gx = np.array([g.x for g in gcps], dtype=np.float64)
        gy = np.array([g.y for g in gcps], dtype=np.float64)

        fwd_x, *_ = np.linalg.lstsq(design(nx_src(px), ny_src(py)), gx, rcond=None)
        fwd_y, *_ = np.linalg.lstsq(design(nx_src(px), ny_src(py)), gy, rcond=None)

        transformer = Transformer.from_crs(gcp_crs, self.config.target_crs, always_xy=True)
        geographic = self.config.target_crs.upper().endswith("4326")

        res_m = self.config.target_resolution_m
        mean_lat_hint = float(np.clip(np.mean(gy), -75.0, 75.0))
        xres = (res_m / (111_320.0 * max(np.cos(np.radians(mean_lat_hint)), 0.25))) if geographic else res_m
        yres = (res_m / 110_574.0) if geographic else res_m

        if expected_bbox is not None:
            w_, s_ = transformer.transform(expected_bbox[0], expected_bbox[1])
            e_, n_ = transformer.transform(expected_bbox[2], expected_bbox[3])
            west, south, east, north = min(w_, e_), min(s_, n_), max(w_, e_), max(s_, n_)
        else:
            edge = np.linspace(-1.0, 1.0, 400)
            ones = np.ones_like(edge)
            D = design(np.concatenate([edge, edge, ones, -ones]),
                       np.concatenate([-ones, ones, edge, edge]))
            out_x = D @ fwd_x
            out_y = D @ fwd_y
            tx_b, ty_b = transformer.transform(out_x, out_y)
            west, east = float(np.nanmin(tx_b)), float(np.nanmax(tx_b))
            south, north = float(np.nanmin(ty_b)), float(np.nanmax(ty_b))

        width = int(round((east - west) / xres))
        height = int(round((north - south) / yres))
        if width <= 0 or height <= 0 or width * height > 2_000_000_000:
            raise GrdPreprocessError(
                f"pathological output grid {width}x{height} - aborting")

        # normalized output-grid coordinate helpers (north-up grid)
        span_x = max((width - 1) * xres, 1e-12)
        span_y = max((height - 1) * yres, 1e-12)

        def nx_out(v):
            return 2.0 * (np.asarray(v, np.float64) - west) / span_x - 1.0

        def ny_out(v):
            return -(2.0 * (np.asarray(v, np.float64) - north) / span_y - 1.0)

        # --- inverse fits evaluated AT the GCPs -----------------------------
        gcp_tx, gcp_ty = transformer.transform(gx, gy)
        A_inv = design(nx_out(gcp_tx), ny_out(gcp_ty))
        inv_px, *_ = np.linalg.lstsq(A_inv, px, rcond=None)
        inv_py, *_ = np.linalg.lstsq(A_inv, py, rcond=None)

        dst_transform = from_origin(west, north, xres, yres)
        profile = {
            "driver": "GTiff", "width": width, "height": height,
            "count": 1, "dtype": "float32", "nodata": float("nan"),
            "crs": self.config.target_crs, "transform": dst_transform,
            "compress": "deflate", "predictor": 3, "tiled": True,
            "blockxsize": 512, "blockysize": 512,
        }

        c = [float(v) for v in inv_px]
        d = [float(v) for v in inv_py]

        with rasterio.open(src_path) as src, \
                rasterio.open(dst_path, "w", **profile) as dst:
            dst.update_tags(
                georef_method=(f"GCP least-squares polynomial order {order} "
                               "on normalized coords; inverse-mapped bilinear sampling"),
                gcp_count=str(len(gcps)),
            )
            rows_per_block = 256
            nx_row = nx_out(west + (np.arange(width) + 0.5) * xres)[None, :]
            for row0 in range(0, height, rows_per_block):
                row1 = min(row0 + rows_per_block, height)
                sub_h = row1 - row0
                ny_col = ny_out(north - ((np.arange(row0, row1) + 0.5) * yres))[:, None]
                nxp = np.broadcast_to(nx_row, (sub_h, width))
                nyp = np.broadcast_to(ny_col, (sub_h, width))
                sc = c[0] + c[1]*nxp + c[2]*nyp + c[3]*nxp*nxp + c[4]*nxp*nyp \
                     + c[5]*nyp*nyp + c[6]*nxp**3 + c[7]*nxp*nxp*nyp \
                     + c[8]*nxp*nyp*nyp + c[9]*nyp**3
                sr = d[0] + d[1]*nxp + d[2]*nyp + d[3]*nxp*nxp + d[4]*nxp*nyp \
                     + d[5]*nyp*nyp + d[6]*nxp**3 + d[7]*nxp*nxp*nyp \
                     + d[8]*nxp*nyp*nyp + d[9]*nyp**3

                valid = ((sc >= 0) & (sc <= W - 1) & (sr >= 0) & (sr <= H - 1)
                         & np.isfinite(sc) & np.isfinite(sr))
                out = np.full((sub_h, width), np.nan, dtype=np.float64)
                if valid.any():
                    c_lo = np.floor(sc[valid]).astype(np.int64)
                    r_lo = np.floor(sr[valid]).astype(np.int64)
                    fc = sc[valid] - c_lo
                    fr = sr[valid] - r_lo
                    c_hi = np.minimum(c_lo + 1, W - 1)
                    r_hi = np.minimum(r_lo + 1, H - 1)
                    win = rasterio.windows.Window(
                        int(c_lo.min()), int(r_lo.min()),
                        int(c_hi.max() - c_lo.min() + 1),
                        int(r_hi.max() - r_lo.min() + 1))
                    tile = src.read(1, window=win).astype(np.float64)
                    lc = c_lo - int(c_lo.min())
                    lr = r_lo - int(r_lo.min())
                    hc = c_hi - int(c_lo.min())
                    hr = r_hi - int(r_lo.min())
                    v00 = tile[lr, lc]; v01 = tile[lr, hc]
                    v10 = tile[hr, lc]; v11 = tile[hr, hc]
                    vals = (v00 * (1 - fr) * (1 - fc) + v01 * (1 - fr) * fc
                            + v10 * fr * (1 - fc) + v11 * fr * fc)
                    bad = np.isnan(v00) | np.isnan(v01) | np.isnan(v10) | np.isnan(v11)
                    vals[bad] = np.nan
                    out[valid] = vals
                dst.write(out.astype(np.float32), 1,
                          window=rasterio.windows.Window(0, row0, width, sub_h))

        self.report.setdefault("georeferencing", {})
        self.report["georeferencing"][dst_path.name] = {
            "method": (f"GCP least-squares polynomial order {order} on "
                       "normalized coords; output grid from advertised footprint"
                       if expected_bbox is not None else
                       f"GCP least-squares polynomial order {order} on normalized coords"),
            "gcp_count": len(gcps),
            "target_crs": self.config.target_crs,
            "resolution": {"x": round(float(xres), 9), "y": round(float(yres), 9)},
            "bounds": [float(west), float(south), float(east), float(north)],
            "dimensions": {"width_px": width, "height_px": height},
        }
        logger.info("georeferenced %s -> %dx%d %s", dst_path.name, width, height,
                    self.config.target_crs)

    def _to_db(self, src_path: Path, dst_path: Path) -> dict:
        import rasterio

        stats = BandStats()
        with rasterio.open(src_path) as src:
            profile = src.profile.copy()
            profile.update(driver="GTiff", dtype="float32", nodata=float("nan"),
                           compress="deflate", predictor=3)
            with rasterio.open(dst_path, "w", **profile) as dst:
                dst.update_tags(
                    sar_quantity="sigma0_decibel",
                    units="dB",
                    formula="10*log10(sigma0_linear)",
                    label="SAR backscatter preview/calibrated dB",
                )
                for _, window in src.block_windows(1):
                    lin = src.read(1, window=window).astype(np.float64)
                    valid = np.isfinite(lin) & (lin > 0)
                    out = np.full(lin.shape, np.nan)
                    np.log10(lin, out=out, where=valid)
                    out *= 10.0
                    out[~valid] = np.nan
                    stats.update(out, valid)
                    dst.write(out.astype(np.float32), 1, window=window)
        return stats.finalize()

    # ------------------------------------------------------------ 5. QC
    def _validate(self, products: dict, gcps_vv, expected_bbox, failures: list[str]) -> None:
        """Automatic quality gates. Any failure is FAIL-CLEAR (collected and
        raised by run()); nothing is silently ignored."""
        import numpy as np
        import rasterio

        if not products:
            failures.append("no calibrated products produced")
            return

        ref = None
        for pol, info in products.items():
            for key in ("georeferenced", "db"):
                rel = info["outputs"][key]
                path = self.root / rel
                # 1/2. exists + opens; 3/4. CRS + transform present
                if not path.exists():
                    failures.append(f"{rel}: missing")
                    continue
                try:
                    with rasterio.open(path) as ds:
                        crs = ds.crs
                        transform = ds.transform
                        w, h = ds.width, ds.height
                        arr = ds.read(1, out_shape=(max(h // 16, 1), max(w // 16, 1)))
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"{rel}: cannot open ({exc})")
                    continue
                if crs is None:
                    failures.append(f"{rel}: no CRS")
                if transform is None or transform == rasterio.transform.Affine.identity():
                    failures.append(f"{rel}: missing/identity transform")
                # 5/6/7. dimensions/resolution/bounds sanity
                if w < 100 or h < 100:
                    failures.append(f"{rel}: suspiciously small output {w}x{h}")
                res_x, res_y = transform.a, -transform.e
                if not (1e-7 < abs(res_x) < 0.01):   # ~1 m .. ~1 km in degrees
                    failures.append(f"{rel}: implausible resolution {res_x}")
                b = ds.bounds
                if expected_bbox:
                    ew, es, en_, en2 = expected_bbox[0] - 1.5, expected_bbox[1] - 1.5, \
                                       expected_bbox[2] + 1.5, expected_bbox[3] + 1.5
                    if not (ew <= b.left <= en_ and ew <= b.right <= en_
                            and es <= b.bottom <= en2 and es <= b.top <= en2):
                        failures.append(f"{rel}: bounds {list(b)} outside AOI neighbourhood")
                # 9/10. NaN/Inf + valid fraction on decimated sample
                finite = np.isfinite(arr)
                frac = float(finite.mean())
                if frac < 0.20:
                    failures.append(f"{rel}: valid fraction only {frac:.3f} (sampled)")
            # 8. VV/VH alignment via identical grid parameters
            ref = None if ref is None else ref
            geo = self.root / info["outputs"]["georeferenced"]
            if not geo.exists():
                failures.append(f"{info['outputs']['georeferenced']}: missing")
                continue
            with rasterio.open(geo) as ds:
                grid = (ds.width, ds.height, str(ds.crs), tuple(ds.transform)[:6])
                if ref is None:
                    ref = (grid, pol)
                elif grid != ref[0]:
                    failures.append(
                        f"VV/VH misalignment: {pol} grid {grid} != {ref[1]} grid {ref[0]}")

    # ------------------------------------------------------------ previews
    def generate_previews(self, products: dict) -> list[str]:
        made: list[str] = []
        prev_dir = self._dir("preview")
        for pol, info in products.items():
            rel = info["outputs"]["db"]
            out = prev_dir / f"{pol}_sigma0_db_backscatter_preview.png"
            self._png_preview(self.root / rel, out)
            made.append(str(out.relative_to(self.root)))
        # VV/VH composite: R=VV dB, G=VH dB, B=VH-VV difference (polarisation
        # contrast) — standard exploratory dual-pol visualisation.
        if {"vv", "vh"} <= set(products):
            out = prev_dir / "vv_vh_composite_backscatter_preview.png"
            self._composite_png(
                [self.root / products[p]["outputs"]["db"] for p in ("vv", "vh")], out)
            made.append(str(out.relative_to(self.root)))
        return made

    def _png_preview(self, raster_path: Path, dest: Path, max_dim: int = 1024,
                     low_pct: float = 2.0, high_pct: float = 98.0) -> None:
        import rasterio
        from rasterio.enums import Resampling

        with rasterio.open(raster_path) as src:
            scale = max(src.width, src.height) / max_dim
            oh, ow = max(int(src.height / scale), 1), max(int(src.width / scale), 1)
            data = src.read(1, out_shape=(oh, ow), resampling=Resampling.average).astype(np.float64)
        finite = data[np.isfinite(data)]
        lo, hi = np.percentile(finite, [low_pct, high_pct]) if finite.size else (0, 1)
        stretched = np.clip((data - lo) / max(hi - lo, 1e-9), 0, 1)
        gray = (np.nan_to_num(stretched) * 255).astype(np.uint8)
        import rasterio as rio
        with rio.open(dest, "w", driver="PNG", width=ow, height=oh, count=1, dtype="uint8") as dst:
            dst.write(gray, 1)
            dst.update_tags(label="SAR backscatter preview — dark regions are NOT oil")

    def _composite_png(self, db_paths: list[Path], dest: Path, max_dim: int = 1024) -> None:
        import rasterio
        from rasterio.enums import Resampling

        bands = []
        for p in db_paths:
            with rasterio.open(p) as src:
                scale = max(src.width, src.height) / max_dim
                oh, ow = max(int(src.height / scale), 1), max(int(src.width / scale), 1)
                bands.append(src.read(1, out_shape=(oh, ow), resampling=Resampling.average))
        vv, vh = bands
        ratio = vv - vh                       # dB difference == intensity ratio
        def stretch(a):
            finite = a[np.isfinite(a)]
            lo, hi = np.percentile(finite, [2, 98])
            return np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1)
        rgb = np.stack([stretch(vv), stretch(vh), stretch(ratio)])
        rgb = np.nan_to_num(rgb)
        img = (rgb.transpose(1, 2, 0) * 255).astype(np.uint8)
        import rasterio as rio
        h, w = img.shape[:2]
        with rio.open(dest, "w", driver="PNG", width=w, height=h, count=3, dtype="uint8") as dst:
            dst.write(img.transpose(2, 0, 1))
            dst.update_tags(label="SAR backscatter preview (R=VV G=VH B=VH-VV dB) — dark regions are NOT oil")

    def _write_gcp_diagnostic_image(self, vv_path: str, gcps) -> None:
        """Downsampled backscatter with GCP positions marked (human QC)."""
        import rasterio
        from rasterio.enums import Resampling

        try:
            with rasterio.open(vv_path) as src:
                factor = 64
                small = src.read(1, out_shape=(src.height // factor, src.width // factor),
                                 resampling=Resampling.average).astype(np.float64)
        except Exception as exc:  # noqa: BLE001 — diagnostic must never kill run
            logger.warning("GCP diagnostic base image unavailable: %s", exc)
            return
        canvas = np.zeros((small.shape[0] + 2, small.shape[1] + 2), dtype=np.uint8)
        finite = small[np.isfinite(small) & (small > 0)]
        lo, hi = np.percentile(finite, [2, 98]) if finite.size else (0, 1)
        canvas[1:-1, 1:-1] = (np.clip((np.nan_to_num(small) - lo) / max(hi - lo, 1e-9), 0, 1) * 255).astype(np.uint8)
        marked = np.stack([canvas, canvas, canvas]).astype(np.uint8)
        for g in gcps:
            px, py = int(g.pixel // factor), int(g.line // factor)
            if 0 <= py < marked.shape[1] - 1 and 0 <= px < marked.shape[2] - 1:
                marked[:, py + 1, px + 1] = [255, 40, 40]
        dest = self._dir("preview") / "gcp_diagnostic.png"
        import rasterio as rio
        c, h, w = marked.shape
        with rio.open(dest, "w", driver="PNG", width=w, height=h, count=c, dtype="uint8") as dst:
            dst.write(marked)
            dst.update_tags(label="Red dots: GCP pixel locations over downsampled DN")

    # ------------------------------------------------------------ 6. report
    def _write_report(self) -> None:
        self.report["software"] = {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "component": "app.satellite.grd_preprocess.GrdPreprocessor",
        }
        self.report["processing_timestamp_utc"] = datetime.now(timezone.utc).isoformat()
        path = self._dir("metadata") / "preprocessing_report.json"
        path.write_text(json.dumps(self.report, indent=2, default=str), encoding="utf-8")
