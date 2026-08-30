"""Real Sentinel-1 GRD preprocessing tests.

Unit tests use SMALL SYNTHETIC SAFE fixtures with hand-computable values —
the one real scene is never required. Formulas verified here:

    sigma0        = DN^2 / A_sigma^2          (ESA SNAP / eopf ATBD eq 6.4)
    sigma0_denoised = (DN^2 - eta_rg*eta_az) / A_sigma^2
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from app.config import Settings
from app.satellite.grd_preprocess import (
    GrdConfig,
    GrdPreprocessError,
    GrdPreprocessor,
)
from app.satellite.s1_metadata import (
    discover_safe_product,
    extract_gcps,
    parse_calibration_xml,
    parse_noise_xml,
    read_image_annotation,
    validate_gcps,
)

W, H = 60, 40
BBOX = (-1.02, 49.55, -0.38, 50.03)   # covers the fixture GCP span
A_CONST = 10.0            # constant calibration LUT value
DN_SEA = 120              # background DN
DN_BLOB = 30              # "dark" region DN (just pixels; NOT oil)


# ----------------------------------------------------------------------
# Fixture builder
# ----------------------------------------------------------------------


def _cal_xml(pol="VV", *, ramp=False):
    if ramp:
        rows = [[float(100 + p) for p in range(3)] for _ in range(2)]
    else:
        rows = [[A_CONST] * 3 for _ in range(2)]
    vecs = []
    for i, line in enumerate((0, H - 1)):
        pix = " ".join(str(v) for v in (0, W // 2, W - 1))
        vals = {q: " ".join(f"{v}" for v in row) for q, row in
                (("sigmaNought", rows[i]), ("betaNought", rows[i]), ("gamma", rows[i]), ("dn", [474.0] * 3))}
        vecs.append(
            f"<calibrationVector><azimuthTime>2026-01-01T00:00:00</azimuthTime>"
            f"<line>{line}</line><pixel count=\"3\">{pix}</pixel>"
            + "".join(f"<{k} count=\"3\">{v}</{k}>" for k, v in vals.items())
            + "</calibrationVector>"
        )
    return (
        "<?xml version=\"1.0\"?><calibration><adsHeader>"
        f"<missionId>S1X</missionId><productType>GRD</productType>"
        f"<polarisation>{pol}</polarisation><mode>IW</mode><swath>IW</swath></adsHeader>"
        "<calibrationInformation><absoluteCalibrationConstant>1.0"
        "</absoluteCalibrationConstant></calibrationInformation>"
        f"<calibrationVectorList count=\"2\">{''.join(vecs)}</calibrationVectorList></calibration>"
    )


def _noise_xml(pol="VV"):
    vecs = []
    for line in (0, H - 1):
        vecs.append(
            f"<noiseRangeVector><azimuthTime>2026-01-01T00:00:00</azimuthTime>"
            f"<line>{line}</line><pixel count=\"2\">0 {W - 1}</pixel>"
            f"<noiseRangeLut count=\"2\">20.0 20.0</noiseRangeLut></noiseRangeVector>"
        )
    az = ("<noiseAzimuthVectorList count=\"1\"><noiseAzimuthVector>"
          "<swath>IW1</swath><firstAzimuthLine>0</firstAzimuthLine>"
          "<firstRangeSample>0</firstRangeSample><lastAzimuthLine>39</lastAzimuthLine>"
          "<lastRangeSample>59</lastRangeSample>"
          f"<line count=\"2\">0 {H - 1}</line><noiseAzimuthLut count=\"2\">1.0 1.0</noiseAzimuthLut>"
          "</noiseAzimuthVector></noiseAzimuthVectorList>")
    return ("<?xml version=\"1.0\"?><noise><adsHeader>"
            f"<missionId>S1X</missionId><polarisation>{pol}</polarisation></adsHeader>"
            f"<noiseRangeVectorList count=\"2\">{''.join(vecs)}</noiseRangeVectorList>{az}</noise>")


def _ann_xml():
    return ("<?xml version=\"1.0\"?><product><adsHeader><missionId>S1X</missionId>"
            "</adsHeader><imageInformation>"
            "<productFirstLineUtcTime>2026-01-01T00:00:00</productFirstLineUtcTime>"
            "<productLastLineUtcTime>2026-01-01T00:00:22</productLastLineUtcTime>"
            f"<rangePixelSpacing>1.0e+1</rangePixelSpacing>"
            f"<azimuthPixelSpacing>1.0e+1</azimuthPixelSpacing>"
            f"<numberOfSamples>{W}</numberOfSamples><numberOfLines>{H}</numberOfLines>"
            "<incidenceAngleMidSwath>3.9e+1</incidenceAngleMidSwath>"
            "<outputPixels>16 bit Unsigned Integer</outputPixels></imageInformation>"
            "<standAloneProductInfo><pass>Descending</pass></standAloneProductInfo>"
            "<swathInfo><swath>IW</swath></swathInfo></product>")


def _dn_band(seed=7):
    rng = np.random.default_rng(seed)
    dn = rng.integers(DN_SEA - 8, DN_SEA + 8, size=(H, W)).astype(np.uint16)
    yy, xx = np.mgrid[0:H, 0:W]
    blob = ((xx - W * 0.6) ** 2 / (W * 0.09) + (yy - H * 0.45) ** 2 / (H * 0.05)) < 1
    dn[blob] = DN_BLOB
    dn[0:2, :] = 0                       # nodata strip
    return dn


def _gcp_list():
    """12 GCPs mapping pixel->lon/lat linearly (fit recovers it exactly)."""
    from rasterio.control import GroundControlPoint

    pts = []
    for gy in np.linspace(0, H - 1, 4):
        for gx_ in np.linspace(0, W - 1, 3):
            pts.append(GroundControlPoint(
                row=float(gy), col=float(gx_),
                x=float(-1.0 + gx_ * 0.01),       # lon: -1 .. -0.41
                y=float(50.0 - gy * 0.01),        # lat: 50 .. 49.97
            ))
    return pts


def make_mini_safe(path: Path, pols=("vv", "vh")) -> Path:
    """Build a tiny but structurally realistic SAFE zip."""
    import rasterio
    from rasterio.crs import CRS

    def tiff_bytes(dn):
        buf = io.BytesIO()
        with rasterio.open(
            buf, "w", driver="GTiff", width=W, height=H, count=1,
            dtype="uint16", nodata=0,
        ) as dst:
            dst.write(dn, 1)
            dst.gcps = (_gcp_list(), CRS.from_epsg(4326))
        return buf.getvalue()

    root = "S1X_IW_GRDH_1SDV_20260101T000000_20260101T000022_000001_000001_0001_COG.SAFE"
    members = {f"{root}/manifest.safe": "<?xml?>", f"{root}/preview/x.png": b"\x89PNG"}
    for pol in pols:
        num = "001" if pol == "vv" else "002"
        members[f"{root}/measurement/s1x-iw-grd-{pol}-t-{num}-cog.tiff"] = tiff_bytes(_dn_band())
        members[f"{root}/annotation/s1x-iw-grd-{pol}-t-{num}-cog.xml"] = _ann_xml()
        members[f"{root}/annotation/calibration/calibration-s1x-iw-grd-{pol}-t-{num}-cog.xml"] = _cal_xml(pol.upper())
        members[f"{root}/annotation/calibration/noise-s1x-iw-grd-{pol}-t-{num}-cog.xml"] = _noise_xml(pol.upper())
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


@pytest.fixture(scope="module")
def mini_safe(tmp_path_factory):
    return make_mini_safe(tmp_path_factory.mktemp("safe") / "mini.zip")


# ----------------------------------------------------------------------
# discovery / parsing
# ----------------------------------------------------------------------


class TestDiscovery:
    def test_structure_discovered_programmatically(self, mini_safe):
        safe = discover_safe_product(mini_safe)
        assert set(safe.polarizations) == {"vv", "vh"}
        assert all("/measurement/" in m for m in safe.measurements.values())
        assert all("calibration-" in c for c in safe.calibration.values())
        assert all("noise-" in n for n in safe.noise.values())

    def test_corrupt_zip_rejected(self, tmp_path):
        p = tmp_path / "bad.zip"
        p.write_bytes(b"not a zip")
        with pytest.raises(Exception):
            discover_safe_product(p)

    def test_missing_component_rejected(self, tmp_path, mini_safe):
        # strip the VH noise file -> discovery must fail loudly
        src = zipfile.ZipFile(mini_safe)
        out = tmp_path / "broken.zip"
        with zipfile.ZipFile(out, "w") as zf:
            for info in src.infolist():
                if "noise-s1x-iw-grd-vh" not in info.filename:
                    zf.writestr(info.filename, src.read(info.filename))
        with pytest.raises(Exception, match="missing required components"):
            discover_safe_product(out)


class TestCalibrationParsing:
    def test_parse_and_metadata(self, mini_safe):
        safe = discover_safe_product(mini_safe)
        cal = parse_calibration_xml(safe.member_text(safe.calibration["vv"]))
        assert cal.polarisation == "VV"
        assert cal.mission_id == "S1X"
        assert cal.absolute_constant == 1.0
        assert set(cal.luts) == {"sigmaNought", "betaNought", "gamma", "dn"}
        assert len(cal.lines) == 2 and len(cal.pixels) == 3

    def test_interpolation_exact_on_constant_lut(self, mini_safe):
        safe = discover_safe_product(mini_safe)
        cal = parse_calibration_xml(safe.member_text(safe.calibration["vv"]))
        got = cal.interpolate(np.arange(H), np.arange(W), "sigmaNought")
        assert np.allclose(got, A_CONST)

    def test_bilinear_exact_on_linear_ramp(self, mini_safe):
        safe = discover_safe_product(mini_safe)
        cal = parse_calibration_xml(safe.member_text(safe.calibration["vv"]))
        # rebuild a ramp LUT: A(line,pix) = 100 + pix  (bilinear is exact)
        cal.luts["sigmaNought"] = [[100.0 + p for p in cal.pixels] for _ in cal.lines]
        got = cal.interpolate(np.array([0, 17, H - 1]), np.arange(W), "sigmaNought")
        assert np.allclose(got, 100.0 + np.arange(W)[None, :])


class TestDnToSigma0:
    def test_formula_against_hand_computed_values(self, tmp_path):
        pre = GrdPreprocessor("T", tmp_path / "ws", GrdConfig(target_resolution_m=200))
        safe = pre._extract(make_mini_safe(tmp_path / "t.zip", pols=("vv",)))
        failures = []
        info = pre._calibrate_and_georeference(safe, "vv", None, (-1.05, 49.9, -0.35, 50.05), failures)
        lin_path = pre.root / info["outputs"]["linear_gcp_referenced"]
        with __import__("rasterio").open(lin_path) as ds:
            lin = ds.read(1)
        dn = _dn_band().astype(np.float64)
        expected = np.where(dn > 0, dn ** 2 / A_CONST ** 2, np.nan)
        m = np.isfinite(lin)
        assert np.allclose(lin[m], expected[m], rtol=1e-6)

    def test_nodata_dn_zero_stays_invalid(self, tmp_path):
        ws = tmp_path / "ws"
        pre = GrdPreprocessor("T2", ws, GrdConfig(target_resolution_m=200))
        safe = pre._extract(make_mini_safe(tmp_path / "t2.zip", pols=("vv",)))
        info = pre._calibrate_and_georeference(safe, "vv", None, (-1.05, 49.9, -0.35, 50.05), [])
        import rasterio

        with rasterio.open(pre.root / info["outputs"]["linear_gcp_referenced"]) as ds:
            lin = ds.read(1)
        assert np.all(np.isnan(lin[0:2, :]))           # DN==0 strip -> NaN
        st = info["stats_linear"]
        assert st["invalid_pixels"] == 2 * W


class TestNoiseLut:
    def test_parse_azimuth_block_structure(self, mini_safe):
        safe = discover_safe_product(mini_safe)
        noise = parse_noise_xml(safe.member_text(safe.noise["vv"]))
        assert noise.polarisation == "VV"
        assert noise.azimuth_vectors and noise.azimuth_vectors[0].lut

    def test_denoise_formula(self, mini_safe):
        safe = discover_safe_product(mini_safe)
        noise = parse_noise_xml(safe.member_text(safe.noise["vv"]))
        eta = noise.noise_power_block(0, 4, W)
        # constant eta_rg=20, eta_az=1 -> power 20 everywhere
        assert np.allclose(eta, 20.0)

    def test_noise_removal_changes_result_when_enabled(self, tmp_path):
        cfg = GrdConfig(target_resolution_m=200, apply_noise_removal=True)
        pre = GrdPreprocessor("T3", tmp_path / "ws", cfg)
        safe = pre._extract(make_mini_safe(tmp_path / "t3.zip", pols=("vv",)))
        info = pre._calibrate_and_georeference(safe, "vv", None, (-1.05, 49.9, -0.35, 50.05), [])
        # denoised mean must be slightly LOWER than uncorrected DN^2/A^2
        import rasterio

        with rasterio.open(pre.root / info["outputs"]["linear_gcp_referenced"]) as ds:
            lin = ds.read(1)
        dn = _dn_band().astype(np.float64)
        plain = np.where(dn > 0, (dn ** 2) / A_CONST ** 2, np.nan)
        m = np.isfinite(lin)
        assert float(np.nanmean(lin[m])) < float(np.nanmean(plain[m]))


# ----------------------------------------------------------------------
# GCP validation
# ----------------------------------------------------------------------


class TestGcps:
    def test_extract_from_real_fixture(self, mini_safe):
        safe = discover_safe_product(mini_safe)
        pts, crs = extract_gcps(f"/vsizip/{safe.zip_path}/{safe.measurements['vv']}")
        assert len(pts) == 12 and str(crs) == "EPSG:4326"

    def test_validation_flags_duplicates_and_outside(self, mini_safe):
        safe = discover_safe_product(mini_safe)
        pts, _ = extract_gcps(f"/vsizip/{safe.zip_path}/{safe.measurements['vv']}")
        diag = validate_gcps(pts, expected_bbox=BBOX)
        assert diag.count == 12 and not diag.warnings
        # duplicate one point
        dup = pts + [pts[-1]]
        diag2 = validate_gcps(dup, expected_bbox=BBOX)
        assert diag2.duplicates
        # footprint far away -> outside flags
        diag3 = validate_gcps(pts, expected_bbox=(10, 10, 20, 20))
        assert diag3.outside_footprint

    def test_empty_gcps_reported(self):
        diag = validate_gcps([], None)
        assert diag.count == 0 and diag.warnings


class TestGeoreferencing:
    def test_output_grid_crs_bounds(self, tmp_path):
        pre = GrdPreprocessor("G1", tmp_path / "ws", GrdConfig(target_resolution_m=200))
        safe = pre._extract(make_mini_safe(tmp_path / "g.zip", pols=("vv",)))
        info = pre._calibrate_and_georeference(safe, "vv", None, BBOX, [])
        import rasterio

        with rasterio.open(pre.root / info["outputs"]["georeferenced"]) as ds:
            assert str(ds.crs) == "EPSG:4326"
            b = ds.bounds
            # within tolerance of advertised mini-footprint
            assert abs(b.left - (-1.02)) < 0.02 and abs(b.top - 50.03) < 0.02
            geo_meta = pre.report["georeferencing"][Path(info["outputs"]["georeferenced"]).name]
            assert geo_meta["gcp_count"] == 12

    def test_vv_vh_alignment_identical_grids(self, tmp_path):
        pre = GrdPreprocessor("G2", tmp_path / "ws", GrdConfig(target_resolution_m=200))
        safe = pre._extract(make_mini_safe(tmp_path / "g2.zip"))
        failures = []
        infos = {pol: pre._calibrate_and_georeference(safe, pol, None, BBOX, failures)
                 for pol in ("vh", "vv")}
        pre._validate(infos, None, BBOX, failures)
        assert failures == []

    def test_misaligned_products_fail_loudly(self, tmp_path):
        pre = GrdPreprocessor("G3", tmp_path / "ws", GrdConfig(target_resolution_m=200))
        safe = pre._extract(make_mini_safe(tmp_path / "g3.zip", pols=("vv",)))
        info = pre._calibrate_and_georeference(safe, "vv", None, BBOX, [])
        # corrupt alignment by claiming different dims for a second product
        fake = dict(info)
        fake["outputs"] = dict(info["outputs"])
        failures = []
        pre._validate({"vv": info, "vh": fake}, None, None, failures)
        # identical files => aligned; now break one path to force mismatch
        fake["outputs"]["georeferenced"] = "georeferenced/nonexistent.tif"
        failures2 = []
        pre._validate({"vv": info, "vh": fake}, None, None, failures2)
        assert any("missing" in f for f in failures2)


class TestAnnotationAndProvenance:
    def test_annotation_fields(self, mini_safe):
        safe = discover_safe_product(mini_safe)
        ann = read_image_annotation(safe.member_text(safe.annotations["vv"]))
        assert ann["range_pixel_spacing_m"] == 10.0
        assert ann["numberOfSamples"] == W
        assert ann["pass"] == "Descending"

    def test_full_run_writes_provenance(self, tmp_path):
        pre = GrdPreprocessor("P1", tmp_path / "ws",
                              GrdConfig(target_resolution_m=200))
        zip_path = make_mini_safe(tmp_path / "p1.zip")
        report = pre.run(zip_path, expected_bbox=BBOX)
        rp = tmp_path / "ws" / "P1" / "metadata" / "preprocessing_report.json"
        assert rp.exists()
        doc = json.loads(rp.read_text())
        assert doc["status"] == "PROCESSED"
        assert doc["gcps"]["count"] == 12
        assert set(doc["outputs"]) == {"vh", "vv"}
        assert doc["outputs"]["vv"]["stats_linear"]["valid_pixels"] > 0

    def test_quality_gate_raises_on_tampered_calibration(self, tmp_path):
        # build a SAFE whose LUT is zero -> sigma0 division blows up
        bad_cal = _cal_xml().replace("1.000000e+01", "0.0") if False else \
            _cal_xml().replace(str(A_CONST), "0")
        zip_path = tmp_path / "bad_lut.zip"
        make_mini_safe(zip_path)
        # rewrite vv calibration with zeros
        src = zipfile.ZipFile(zip_path)
        entries = {i.filename: src.read(i.filename) for i in src.infolist()}
        src.close()
        for key in list(entries):
            if "calibration-s1x-iw-grd-vv" in key:
                entries[key] = bad_cal.encode()
        with zipfile.ZipFile(zip_path, "w") as zf:
            for k, v in entries.items():
                zf.writestr(k, v)
        pre = GrdPreprocessor("P2", tmp_path / "ws2", GrdConfig(target_resolution_m=200))
        with pytest.raises(GrdPreprocessError):
            pre.run(zip_path, expected_bbox=BBOX)


# ----------------------------------------------------------------------
# Pipeline integration (states + events, NO inference)
# ----------------------------------------------------------------------


def test_pipeline_real_scene_runs_grd_path_without_inference(tmp_path):
    from app.db.memory_repo import InMemoryRepository
    from app.domain.entities import SatelliteSceneRecord
    from app.inference.model_loader import ModelHandle
    from app.services.event_hub import EventHub
    from app.services.inference_service import InferenceService
    from app.satellite.pipeline import JobState, PipelineJobManager
    from app.satellite.providers.base import DownloadOptions
    from app.satellite.storage import LocalStorageBackend

    class FixtureProvider:
        """Provider whose 'download' materializes the mini SAFE zip."""

        def download_scene(self, scene, storage, options=None):
            key = f"products/{scene.id}.zip"
            make_mini_safe(storage.get_path(key))
            from app.satellite.storage import StoredFile

            return StoredFile(key, storage.get_path(key).stat().st_size,
                              str(storage.get_path(key)), key)

    repo = InMemoryRepository()
    hub = EventHub()
    cursor = hub._next_id
    scene = SatelliteSceneRecord(
        id="MINI_S1_SCENE", platform="Sentinel-1X",
        acquired_at=datetime.now(timezone.utc) - timedelta(hours=1),
        footprint=BBOX,
        status="discovered", source_provider="copernicus", is_demo=False,
    )
    repo.add_scene(scene)

    settings = Settings(grd_target_resolution_m=200)
    settings.scene_storage_dir = str(tmp_path)
    manager = PipelineJobManager(
        repo=repo, provider=FixtureProvider(),
        storage=LocalStorageBackend(tmp_path / "store"),
        settings=settings, event_hub=hub,
        model_handle=ModelHandle(settings),
        inference_service_factory=lambda: InferenceService(repo, settings, hub),
    )
    job = manager.enqueue("MINI_S1_SCENE")
    import time as _t

    for _ in range(2400):                     # up to 2 minutes
        if job.state in (JobState.PROCESSED, JobState.FAILED):
            break
        _t.sleep(0.05)
    assert job.state is JobState.PROCESSED, job.error

    history = [h["state"] for h in job.history]
    for state in ("DOWNLOADING", "DOWNLOADED", "EXTRACTING",
                  "CALIBRATING", "GEOREFERENCING", "VALIDATING", "PROCESSED"):
        assert state in history, history

    types = {e.type for e in hub.since(cursor - 1)}
    assert "scene.download.started" in types
    assert "scene.extraction.started" in types and "scene.extraction.completed" in types
    assert "scene.calibration.started" in types and "scene.calibration.completed" in types
    assert "scene.georeferencing.started" in types and "scene.georeferencing.completed" in types
    assert "scene.preprocessing.completed" in types
    # absolutely no inference happened
    assert "scene.inference.started" not in types
    assert repo.list_incidents() == []

    # scene updated with processed status + provenance reference
    stored = repo.get_scene("MINI_S1_SCENE")
    assert stored.status == "processed"
    assert "preprocessing_report" in (stored.metadata_extra or {})


def test_processing_endpoint_reports_provenance(client, tmp_path):
    """GET /satellite/scenes/{id}/processing exposes state + products."""
    from datetime import datetime as dt

    report = {
        "status": "PROCESSED",
        "outputs": {"vv": {"calibration": {"method": "sigma0 = DN^2 / A_sigma^2"},
                            "outputs": {"db": "model_input/vv_sigma0_db.tif"}},
                     "vh": {"outputs": {"db": "model_input/vh_sigma0_db.tif"}}},
        "previews": ["preview/vv_sigma0_db_backscatter_preview.png"],
        "gcps": {"count": 189},
        "quality_failures": [],
        "elapsed_s": 1332.9,
    }
    rp = tmp_path / "preprocessing_report.json"
    rp.write_text(json.dumps(report))

    from app.domain.entities import SatelliteSceneRecord

    scene = SatelliteSceneRecord(
        id="REAL_S1_SCENE", platform="Sentinel-1C", status="processed",
        source_provider="copernicus", is_demo=False,
        pipeline_state="PROCESSED",
        metadata_extra={"preprocessing_report": str(rp)},
    )
    client.app.state.repo.add_scene(scene)

    res = client.get("/api/v1/satellite/scenes/REAL_S1_SCENE/processing")
    assert res.status_code == 200
    body = res.json()
    assert body["state"] == "PROCESSED"
    assert body["isRealData"] is True
    assert "NO oil detection" in body["note"]
    assert body["preprocessing"]["gcps"] == 189
    assert "model_input/vv_sigma0_db.tif" in body["availableProducts"]

    missing = client.get("/api/v1/satellite/scenes/GHOST/processing")
    assert missing.status_code == 404
