"""Sentinel-1 SAFE product metadata parsing and validation.

Everything here is derived from the ACTUAL product structure (verified on a
real S1C IW GRDH COG product) and official ESA documentation:

* Radiometric calibration formula (ESA Sentinel-1 Technical Guide /
  SNAP CalibrationOp / Copernicus eopf ATBD eq. 6.4):

      sigma0(i,j) = DN(i,j)^2 / A_sigma(i,j)^2

  where A_sigma is the calibration LUT value bilinearly interpolated between
  calibration vectors (anchored every N lines, sub-sampled across range).
  betaNought/gamma LUTs follow the identical form. The LUT already includes
  the absolute calibration constant and range-dependent gain.

* Thermal noise removal (ESA noise LUT):
      noise_power(i,j) = eta_range * eta_azimuth   (LUT^2 convention,
      interpolated like A_sigma)
      sigma0_denoised  = (DN^2 - noise_power) / A_sigma^2
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from zipfile import ZipFile


class SafeProductError(RuntimeError):
    """Raised when the SAFE package does not match the expected structure."""


# ----------------------------------------------------------------------
# SAFE package discovery
# ----------------------------------------------------------------------


@dataclass
class SafeProduct:
    """Programmatically discovered layout of one Sentinel-1 SAFE package."""

    zip_path: Path
    safe_root: str                      # top-level <PRODUCT>.SAFE entry
    manifest_name: str | None
    measurements: dict[str, str]        # pol -> archive member path
    annotations: dict[str, str]         # pol -> image annotation xml
    calibration: dict[str, str]         # pol -> calibration xml
    noise: dict[str, str]               # pol -> noise xml
    extra_members: list[str] = field(default_factory=list)

    @property
    def polarizations(self) -> list[str]:
        return sorted(self.measurements)

    def member_text(self, member: str) -> str:
        with ZipFile(self.zip_path) as zf:
            return zf.read(member).decode("utf-8", errors="replace")


def discover_safe_product(zip_path: str | Path) -> SafeProduct:
    """Discover the actual SAFE structure. Never assumes filenames beyond
    directory conventions (annotation/, measurement/) and content markers."""
    zip_path = Path(zip_path)
    if not zip_path.exists():
        raise SafeProductError(f"product not found: {zip_path}")

    with ZipFile(zip_path) as zf:
        bad = zf.testzip()
        if bad is not None:
            raise SafeProductError(f"corrupt archive member: {bad}")
        names = zf.namelist()

    roots = sorted({n.split("/")[0] for n in names if n.strip()})
    if len(roots) != 1 or not roots[0].upper().endswith(".SAFE"):
        raise SafeProductError(f"unexpected SAFE layout, roots={roots}")
    safe_root = roots[0]

    def classify(member: str) -> tuple[str, str] | None:
        low = member.lower()
        if "/measurement/" not in low and not low.endswith(".tiff"):
            return None
        m = re.search(r"-grd-(vv|vh|hh|hv)-", low)
        return (m.group(1), member) if m else None

    measurements: dict[str, str] = {}
    annotations: dict[str, str] = {}
    calibration: dict[str, str] = {}
    noise: dict[str, str] = {}
    manifest: str | None = None
    extra: list[str] = []

    for n in names:
        if n.endswith("/"):
            continue
        low = n.lower()
        if low.endswith("manifest.safe"):
            manifest = n
        elif "/measurement/" in low:
            got = classify(n)
            if got:
                measurements.setdefault(got[0], n)
            else:
                extra.append(n)
        elif "/annotation/" in low:
            pol_match = re.search(r"-grd-(vv|vh|hh|hv)-", low)
            pol = pol_match.group(1) if pol_match else None
            fname = low.rsplit("/", 1)[-1]
            if pol is None:
                continue
            if fname.startswith("calibration-"):
                calibration.setdefault(pol, n)
            elif fname.startswith("noise-"):
                noise.setdefault(pol, n)
            elif fname.startswith("rfi-"):
                continue
            else:
                annotations.setdefault(pol, n)
        else:
            extra.append(n)

    missing = [
        label for label, ok in [
            ("manifest.safe", manifest),
            ("measurement", measurements),
            ("image annotation", annotations),
            ("calibration LUT", calibration),
            ("noise LUT", noise),
        ] if not ok
    ]
    # every polarization present in measurement/ must have its full metadata set
    incomplete = [
        f"{pol}" for pol in measurements
        if pol not in annotations or pol not in calibration or pol not in noise
    ]
    if incomplete:
        missing.append(f"incomplete metadata for polarizations: {incomplete}")
    if missing:
        raise SafeProductError(f"{safe_root}: missing required components: {missing}")

    return SafeProduct(
        zip_path=zip_path,
        safe_root=safe_root,
        manifest_name=manifest,
        measurements=measurements,
        annotations=annotations,
        calibration=calibration,
        noise=noise,
        extra_members=extra,
    )


# ----------------------------------------------------------------------
# Calibration LUT
# ----------------------------------------------------------------------


def _text_list(element) -> list[float]:
    return [float(v) for v in element.text.split()]


@dataclass
class CalibrationLut:
    """Parsed calibration XML: vectors of A values anchored at image lines."""

    polarisation: str
    mission_id: str
    product_type: str
    acquisition_mode: str
    swath: str
    absolute_constant: float
    lines: list[int]                       # anchor line per vector
    pixels: list[int]                      # range anchor pixels (shared grid)
    luts: dict[str, list[list[float]]]     # quantity -> [per-vector values]
    source_file: str = ""

    def interpolate(self, lines_block, pixels_block, quantity: str = "sigmaNought"):
        """Separable bi-linear interpolation of the LUT over a block.

        `lines_block`/`pixels_block` are 1-D arrays of integer coordinates.
        Returns a (len(lines_block), len(pixels_block)) float64 array.

        Bi-linear interpolation between LUT anchors is the officially
        prescribed method (SNAP/eopf ATBD): the LUT is smooth in range, so
        interpolating first along the shared pixel grid, then along lines,
        is exact bilinear interpolation on the anchor lattice.
        """
        import numpy as np

        table = np.asarray(self.luts[quantity], dtype=np.float64)  # (n_vec, n_pix)
        anchor_pixels = np.asarray(self.pixels, dtype=np.float64)
        anchor_lines = np.asarray(self.lines, dtype=np.float64)

        rows = np.asarray(lines_block, dtype=np.float64)
        cols = np.asarray(pixels_block, dtype=np.float64)

        # --- interpolate along pixel axis for every anchor line ----------
        lo = np.clip(np.searchsorted(anchor_pixels, cols) - 1, 0, len(anchor_pixels) - 2)
        span = anchor_pixels[lo + 1] - anchor_pixels[lo]
        w_col = ((cols - anchor_pixels[lo]) / span)[None, :]              # (1, nc)
        # gather bracketing columns per block-column for all anchor lines
        c0 = table[:, lo]                                                 # (nv, nc)
        c1 = table[:, lo + 1]
        per_line = c0 + (c1 - c0) * w_col                                 # (nv, nc)

        # --- interpolate along line axis ---------------------------------
        r_lo = np.clip(np.searchsorted(anchor_lines, rows) - 1, 0, len(anchor_lines) - 2)
        r_span = anchor_lines[r_lo + 1] - anchor_lines[r_lo]
        w_row = (rows - anchor_lines[r_lo]) / r_span                      # (nr,)
        r0 = per_line[r_lo, :]                                            # (nr, nc)
        r1 = per_line[r_lo + 1, :]
        return r0 + (r1 - r0) * w_row[:, None]

    def describe(self) -> dict:
        return {
            "polarisation": self.polarisation,
            "mission_id": self.mission_id,
            "product_type": self.product_type,
            "mode": self.acquisition_mode,
            "swath": self.swath,
            "absolute_constant": self.absolute_constant,
            "anchor_lines": {"count": len(self.lines), "first": self.lines[0], "last": self.lines[-1]},
            "range_anchor_pixels": {"count": len(self.pixels), "first": self.pixels[0], "last": self.pixels[-1]},
            "quantities": sorted(self.luts),
            "source_file": self.source_file,
        }


_CALIB_QTY = ("sigmaNought", "betaNought", "gamma", "dn")


def parse_calibration_xml(xml_text: str, source_file: str = "") -> CalibrationLut:
    root = ET.fromstring(xml_text)
    ads = root.find("adsHeader")
    if ads is None:
        raise SafeProductError("calibration XML missing adsHeader")

    vectors = root.findall(".//calibrationVector")
    if not vectors:
        raise SafeProductError("calibration XML contains no calibrationVector")

    lines: list[int] = []
    pixels: list[int] = []
    luts: dict[str, list[list[float]]] = {}

    first_pixels = vectors[0].find("pixel")
    if first_pixels is None:
        raise SafeProductError("calibrationVector missing pixel list")
    pixel_count = int(first_pixels.attrib.get("count", len(first_pixels.text.split())))

    quantities_present = {
        q for q in _CALIB_QTY if vectors[0].find(q) is not None
    }
    for q in quantities_present:
        luts[q] = []

    for vec in vectors:
        line_el = vec.find("line")
        if line_el is None:
            raise SafeProductError("calibrationVector missing <line>")
        lines.append(int(line_el.text))
        pix = vec.find("pixel")
        vals = _text_list(pix)
        if len(vals) != pixel_count:
            raise SafeProductError("inconsistent pixel anchor counts across vectors")
        if not pixels:
            pixels = [int(v) for v in vals]
        for q in quantities_present:
            el = vec.find(q)
            q_vals = _text_list(el)
            if len(q_vals) != pixel_count:
                raise SafeProductError(f"{q} length != pixel count on line {line_el.text}")
            luts[q].append(q_vals)

    const_el = root.find(".//absoluteCalibrationConstant")
    return CalibrationLut(
        polarisation=(ads.findtext("polarisation") or "").strip(),
        mission_id=(ads.findtext("missionId") or "").strip(),
        product_type=(ads.findtext("productType") or "").strip(),
        acquisition_mode=(ads.findtext("mode") or "").strip(),
        swath=(ads.findtext("swath") or "").strip(),
        absolute_constant=float(const_el.text) if const_el is not None else float("nan"),
        lines=lines,
        pixels=pixels,
        luts=luts,
        source_file=source_file,
    )


# ----------------------------------------------------------------------
# Noise LUT
# ----------------------------------------------------------------------


@dataclass
class AzimuthNoiseVector:
    """One <noiseAzimuthVector>: azimuth noise LUT over a swath block.

    Actual product structure (verified on S1C IW GRDH COG):
        <noiseAzimuthVector>
          <swath>IW1</swath>
          <firstAzimuthLine/> <firstRangeSample/>
          <lastAzimuthLine/>  <lastRangeSample/>
          <line count="N">line0 line1 ...</line>
          <noiseAzimuthLut>v0 v1 ...</noiseAzimuthLut>
        </noiseAzimuthVector>
    """

    swath: str
    first_azimuth_line: int
    last_azimuth_line: int
    first_range_sample: int
    last_range_sample: int
    lines: list[int]
    lut: list[float]


@dataclass
class NoiseLut:
    """Parsed thermal-noise XML (range vectors + azimuth vectors)."""

    polarisation: str
    lines: list[int]
    pixels: list[int]
    range_luts: list[list[float]]          # eta_range per vector
    azimuth_vectors: list[AzimuthNoiseVector] = field(default_factory=list)
    source_file: str = ""

    def describe(self) -> dict:
        return {
            "polarisation": self.polarisation,
            "range_vectors": len(self.lines),
            "range_anchor_pixels": len(self.pixels),
            "azimuth_vectors": [
                {
                    "swath": v.swath,
                    "azimuth_lines": [v.first_azimuth_line, v.last_azimuth_line],
                    "range_samples": [v.first_range_sample, v.last_range_sample],
                    "lut_len": len(v.lut),
                }
                for v in self.azimuth_vectors
            ],
            "source_file": self.source_file,
        }

    def noise_power_block(self, line0: int, line1: int, width: int):
        """Calibrated thermal-noise power eta_rg * eta_az for a row block.

        Convention (ESA noise LUT / Ifremer processor note): range and
        azimuth LUTs share the DN^2 scale of the calibration vectors, so the
        calibrated noise power is the product of both interpolated LUTs.
        The azimuth component is evaluated per line from the swath-block
        vector covering that line (linear interp on its anchors); its range
        dependence is second-order and folded out (documented approximation).
        """
        import numpy as np

        table = np.asarray(self.range_luts, dtype=np.float64)
        anchor_pixels = np.asarray(self.pixels, dtype=np.float64)
        anchor_lines = np.asarray(self.lines, dtype=np.float64)
        cols = np.arange(width, dtype=np.float64)

        lo = np.clip(np.searchsorted(anchor_pixels, cols) - 1, 0, len(anchor_pixels) - 2)
        span = anchor_pixels[lo + 1] - anchor_pixels[lo]
        w_col = ((cols - anchor_pixels[lo]) / span)[None, :]
        per_line = table[:, lo] + (table[:, lo + 1] - table[:, lo]) * w_col

        rows = np.arange(line0, line1, dtype=np.float64)
        r_lo = np.clip(np.searchsorted(anchor_lines, rows) - 1, 0, len(anchor_lines) - 2)
        r_span = anchor_lines[r_lo + 1] - anchor_lines[r_lo]
        w_row = ((rows - anchor_lines[r_lo]) / r_span)[:, None]
        eta_rg = per_line[r_lo, :] + (per_line[r_lo + 1, :] - per_line[r_lo, :]) * w_row

        if not self.azimuth_vectors:
            return eta_rg
        ordered = sorted(self.azimuth_vectors, key=lambda v: v.first_azimuth_line)
        eta_az_rows = np.ones_like(rows)
        for i, row in enumerate(rows):
            chosen = next((v for v in ordered
                           if v.first_azimuth_line <= row <= v.last_azimuth_line), None)
            if chosen is None or not chosen.lines:
                continue
            va = np.asarray(chosen.lut, dtype=np.float64)
            la = np.asarray(chosen.lines, dtype=np.float64)
            eta_az_rows[i] = float(np.interp(row, la, va))
        return eta_rg * eta_az_rows[:, None]


def parse_noise_xml(xml_text: str, source_file: str = "") -> NoiseLut:
    root = ET.fromstring(xml_text)
    ads = root.find("adsHeader")
    vectors = root.findall(".//noiseRangeVector")
    if not vectors:
        raise SafeProductError("noise XML contains no noiseRangeVector")
    lines: list[int] = []
    range_luts: list[list[float]] = []
    pixels: list[int] = []
    for vec in vectors:
        lines.append(int(vec.findtext("line")))
        pixels = [int(v) for v in _text_list(vec.find("pixel"))]
        range_luts.append(_text_list(vec.find("noiseRangeLut")))

    az_vectors: list[AzimuthNoiseVector] = []
    for el in root.findall(".//noiseAzimuthVector"):
        line_el = el.find("line")
        lut_el = el.find("noiseAzimuthLut")
        if line_el is None or lut_el is None:
            continue
        az_lines = [int(v) for v in _text_list(line_el)]
        az_lut = _text_list(lut_el)
        if len(az_lines) != len(az_lut):
            raise SafeProductError("noiseAzimuthVector line/LUT length mismatch")
        az_vectors.append(AzimuthNoiseVector(
            swath=el.findtext("swath") or "",
            first_azimuth_line=int(el.findtext("firstAzimuthLine") or 0),
            last_azimuth_line=int(el.findtext("lastAzimuthLine") or 0),
            first_range_sample=int(el.findtext("firstRangeSample") or 0),
            last_range_sample=int(el.findtext("lastRangeSample") or 0),
            lines=az_lines,
            lut=az_lut,
        ))
    return NoiseLut(
        polarisation=(ads.findtext("polarisation") or "").strip() if ads is not None else "",
        lines=lines,
        pixels=pixels,
        range_luts=range_luts,
        azimuth_vectors=az_vectors,
        source_file=source_file,
    )


# ----------------------------------------------------------------------
# GCP extraction & validation
# ----------------------------------------------------------------------


@dataclass
class GcpPoint:
    pixel: int
    line: int
    longitude: float
    latitude: float


@dataclass
class GcpDiagnostics:
    count: int
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    duplicates: list[tuple[int, int]]
    invalid: list[tuple[int, int]]
    outside_footprint: list[tuple[int, int]]
    coverage_cells_hit: int
    coverage_grid: tuple[int, int]
    warnings: list[str]

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        return d


def extract_gcps(raster_source) -> tuple[list[GcpPoint], object | None]:
    """Read the GCP table from a raster (e.g. /vsizip/ measurement TIFF)."""
    import rasterio

    with rasterio.open(raster_source) as ds:
        gcps, crs = ds.gcps
        points = [
            GcpPoint(pixel=int(g.col), line=int(g.row),
                     longitude=float(g.x), latitude=float(g.y))
            for g in (gcps or [])
        ]
        return points, crs


def validate_gcps(
    points: list[GcpPoint],
    expected_bbox: tuple[float, float, float, float] | None,
    *,
    coverage_grid: tuple[int, int] = (4, 4),
    outlier_std: float = 4.0,
) -> GcpDiagnostics:
    """Validate a GCP table. Suspicious points are REPORTED, never dropped."""
    import numpy as np

    if not points:
        return GcpDiagnostics(0, 0, 0, 0, 0, [], [], [], 0, coverage_grid,
                              ["NO GCPs FOUND — georeferencing impossible"])

    lats = np.array([p.latitude for p in points])
    lons = np.array([p.longitude for p in points])
    warnings: list[str] = []

    invalid = [
        (p.pixel, p.line) for p in points
        if not (-90 <= p.latitude <= 90) or not (-180 <= p.longitude <= 180)
    ]
    if invalid:
        warnings.append(f"{len(invalid)} GCP(s) outside valid lat/lon domain")

    seen: dict[tuple[float, float], tuple[int, int]] = {}
    duplicates = []
    for p in points:
        key = (round(p.longitude, 6), round(p.latitude, 6))
        if key in seen:
            duplicates.append((p.pixel, p.line))
        else:
            seen[key] = (p.pixel, p.line)
    if duplicates:
        warnings.append(f"{len(duplicates)} duplicate GCP location(s)")

    outside = []
    if expected_bbox is not None:
        w, s, e, n = expected_bbox
        tol = 0.05  # degrees tolerance around advertised footprint
        outside = [
            (p.pixel, p.line) for p in points
            if not (w - tol <= p.longitude <= e + tol and s - tol <= p.latitude <= n + tol)
        ]
        if outside:
            warnings.append(f"{len(outside)} GCP(s) fall outside advertised footprint (+/-0.05deg)")

    # spatial-outlier scan on lat/lon scatter (median absolute deviation)
    for name, arr in (("latitude", lats), ("longitude", lons)):
        med = np.median(arr)
        mad = np.median(np.abs(arr - med)) or 1e-12
        z = np.abs(arr - med) / (1.4826 * mad)
        bad = int((z > outlier_std).sum())
        if bad:
            warnings.append(f"{bad} potential {name} outlier(s) (MAD>{outlier_std}) — reported, not removed")

    gx, gy = coverage_grid
    cells = set()
    for p in points:
        cx = min(int((p.longitude - lons.min()) / max((lons.max() - lons.min()) or 1, 1e-12) * gx), gx - 1)
        cy = min(int((p.latitude - lats.min()) / max((lats.max() - lats.min()) or 1, 1e-12) * gy), gy - 1)
        cells.add((cx, cy))
    empty_ratio = 1.0 - len(cells) / (gx * gy)
    if empty_ratio > 0.5:
        warnings.append(f"GCP coverage gaps: only {len(cells)}/{gx * gy} grid cells populated")

    return GcpDiagnostics(
        count=len(points),
        lat_min=float(lats.min()), lat_max=float(lats.max()),
        lon_min=float(lons.min()), lon_max=float(lons.max()),
        duplicates=duplicates, invalid=invalid, outside_footprint=outside,
        coverage_cells_hit=len(cells), coverage_grid=coverage_grid,
        warnings=warnings,
    )


def read_image_annotation(xml_text: str) -> dict:
    """Extract key facts from the image annotation XML."""
    root = ET.fromstring(xml_text)
    img = root.find(".//imageInformation")

    def f(tag: str) -> float | None:
        el = root.find(f".//{tag}") if img is None else img.find(tag)
        try:
            return float(el.text) if el is not None else None
        except (TypeError, ValueError):
            return None

    return {
        "first_line_utc": (img.findtext("productFirstLineUtcTime") if img is not None else None),
        "last_line_utc": (img.findtext("productLastLineUtcTime") if img is not None else None),
        "range_pixel_spacing_m": f("rangePixelSpacing"),
        "azimuth_pixel_spacing_m": f("azimuthPixelSpacing"),
        "incidence_angle_mid_swath_deg": f("incidenceAngleMidSwath"),
        "numberOfSamples": int(f("numberOfSamples") or 0) or None,
        "numberOfLines": int(f("numberOfLines") or 0) or None,
        "output_pixels": (img.findtext("outputPixels") if img is not None else None),
        "pass": root.findtext(".//pass"),
        "swath": root.findtext(".//swath"),
    }
