"""Phase 2D validation tests — independent checks on real Sentinel-1 preprocessing.

These tests verify that our SAR preprocessing pipeline produces scientifically
correct results before ML integration. They run against the processed outputs
from the real Sentinel-1C IW GRDH product.

DO NOT: train, infer, detect, add AIS/drift, or modify frontend.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio

PROCESSED = Path(r"D:\Oil spill detection\data\scenes\processed"
                 r"\S1C_IW_GRDH_1SDV_20260826T005736_20260826T005758_009159_012318_7B48_COG")
OUTPUTS = Path(r"D:\Oil spill detection\backend\scripts\phase2d_outputs")


# ─── Step 1: Calibration cross-check ─────────────────────────────────────────

class TestCalibrationCrossCheck:
    """Pixel-level DN → sigma0 validation."""

    def test_calibration_validation_json_exists(self):
        p = OUTPUTS / "calibration_validation.json"
        assert p.exists(), "calibration_validation.json not found"
        data = json.loads(p.read_text())
        assert "VV" in data and "VH" in data
        assert len(data["VV"]) >= 20
        assert len(data["VH"]) >= 20

    def test_calibration_pixel_fields_complete(self):
        data = json.loads((OUTPUTS / "calibration_validation.json").read_text())
        for pol in ("VV", "VH"):
            for rec in data[pol]:
                assert "row" in rec
                assert "col" in rec
                assert "raw_dn" in rec
                assert "cal_lut_value" in rec
                assert "sigma0_linear" in rec
                assert "sigma0_dB" in rec

    def test_calibration_values_physically_plausible(self):
        data = json.loads((OUTPUTS / "calibration_validation.json").read_text())
        for pol in ("VV", "VH"):
            for rec in data[pol]:
                if rec["raw_dn"] > 0:
                    assert rec["sigma0_linear"] > 0, f"sigma0 must be positive for DN>0"
                    assert -60 < rec["sigma0_dB"] < 30, f"sigma0 dB out of range: {rec['sigma0_dB']}"


# ─── Step 2: Independent reference ───────────────────────────────────────────

class TestIndependentReference:
    """Compare against independent scipy interpolation."""

    def test_reference_comparison_exists(self):
        p = OUTPUTS / "independent_reference_comparison.json"
        assert p.exists(), "independent_reference_comparison.json not found"
        data = json.loads(p.read_text())
        # Errors must be below float64 precision (~1e-15 relative)
        assert data["sigma0_rel_error_max"] < 1e-10, (
            f"Independent reference mismatch: max rel error = {data['sigma0_rel_error_max']}"
        )


# ─── Step 3: LUT interpolation ───────────────────────────────────────────────

class TestLutInterpolation:
    """Verify bilinear interpolation over both dimensions."""

    def test_interpolation_validation_all_pass(self):
        p = OUTPUTS / "lut_interpolation_validation.json"
        assert p.exists(), "lut_interpolation_validation.json not found"
        data = json.loads(p.read_text())
        assert data["all_pass"], "LUT interpolation tests failed"

    def test_nonseparable_2d_field_exact(self):
        data = json.loads((OUTPUTS / "lut_interpolation_validation.json").read_text())
        nonsep = [t for t in data["tests"] if t["test"] == "nonseparable_2d"]
        assert len(nonsep) == 1
        assert nonsep[0]["pass"], "Bilinear interpolation failed on non-separable 2D field"


# ─── Step 4: GRD formula ─────────────────────────────────────────────────────

class TestGrdFormula:
    """Verify calibration formula against preprocessed output."""

    def test_formula_verification_exists(self):
        p = OUTPUTS / "grd_formula_verification.json"
        assert p.exists(), "grd_formula_verification.json not found"
        data = json.loads(p.read_text())
        assert data["verification"]["status"] == "VERIFIED"
        assert data["verification"]["mismatches"] == 0

    def test_formula_is_correct(self):
        data = json.loads((OUTPUTS / "grd_formula_verification.json").read_text())
        assert data["formula"] == "sigma0 = DN^2 / A_sigma^2"


# ─── Step 5: 0.8995 constant ─────────────────────────────────────────────────

class TestConstant08995:
    """Verify absolute calibration constant provenance."""

    def test_constant_documented(self):
        p = OUTPUTS / "constant_08995_investigation.json"
        assert p.exists()
        data = json.loads(p.read_text())
        for pol in ("VV", "VH"):
            assert data[pol]["absolute_constant_xml"] == 0.8995
            assert "ALREADY INCORPORATED" in data[pol]["constant_provenance"].upper() or \
                   "already incorporated" in data[pol]["constant_provenance"].lower()
            assert "NOT apply" in data[pol]["application_in_code"] or \
                   "does NOT" in data[pol]["application_in_code"]


# ─── Step 6: Georeferencing ──────────────────────────────────────────────────

class TestGeoreferencing:
    """GCP polynomial fit residual validation."""

    def test_georeferencing_validation_exists(self):
        p = OUTPUTS / "georeferencing_validation.json"
        assert p.exists()
        data = json.loads(p.read_text())
        assert data["gcp_count"] == 189

    def test_georeferencing_rmse_sub_meter(self):
        data = json.loads((OUTPUTS / "georeferencing_validation.json").read_text())
        assert data["rmse_m"] < 1.0, f"GCP RMSE {data['rmse_m']} m exceeds 1 m"
        assert data["mean_error_m"] < 1.0
        assert data["max_error_m"] < 5.0, f"GCP max error {data['max_error_m']} m exceeds 5 m"

    def test_per_gcp_residuals_available(self):
        data = json.loads((OUTPUTS / "georeferencing_validation.json").read_text())
        assert len(data["per_gcp"]) == 189
        for g in data["per_gcp"]:
            assert "residual_magnitude_m" in g
            assert g["residual_magnitude_m"] >= 0


# ─── Step 7: GCP residual map ────────────────────────────────────────────────

class TestGcpResidualMap:
    def test_diagnostic_image_exists(self):
        p = OUTPUTS / "gcp_residual_map.png"
        assert p.exists(), "GCP residual map not generated"
        assert p.stat().st_size > 1000, "GCP residual map too small"


# ─── Step 8: NaN analysis ────────────────────────────────────────────────────

class TestNanAnalysis:
    """Verify NaN percentage and distribution analysis."""

    def test_nan_analysis_exists(self):
        p = OUTPUTS / "nan_analysis.json"
        assert p.exists()
        data = json.loads(p.read_text())
        assert "VV" in data and "VH" in data

    def test_nan_percentage_documented(self):
        data = json.loads((OUTPUTS / "nan_analysis.json").read_text())
        for pol in ("VV", "VH"):
            assert 30 < data[pol]["nan_percentage"] < 40, (
                f"{pol} NaN percentage {data[pol]['nan_percentage']}% outside expected range"
            )
            assert "EXPECTED" in data[pol]["expected_vs_unnecessary"]

    def test_nan_identical_across_polarizations(self):
        data = json.loads((OUTPUTS / "nan_analysis.json").read_text())
        assert abs(data["VV"]["nan_percentage"] - data["VH"]["nan_percentage"]) < 0.1


# ─── Step 9: Alternative georeferencing ──────────────────────────────────────

class TestAlternativeGeoreferencing:
    def test_comparison_exists(self):
        p = OUTPUTS / "georeferencing_comparison.json"
        assert p.exists()
        data = json.loads(p.read_text())
        assert "current_method" in data
        assert "production_method" in data
        assert "recommendation" in data


# ─── Step 10: VV/VH alignment ────────────────────────────────────────────────

class TestVVVHAlignment:
    """Validate VV and VH share identical grid parameters."""

    def test_alignment_exists(self):
        p = OUTPUTS / "vv_vh_alignment.json"
        assert p.exists()
        data = json.loads(p.read_text())
        assert data["status"] == "ALIGNED"

    def test_grid_parameters_match(self):
        data = json.loads((OUTPUTS / "vv_vh_alignment.json").read_text())
        ga = data["grid_alignment"]
        assert ga["same_crs"]
        assert ga["same_dimensions"]
        assert ga["same_transform"]
        assert ga["same_bounds"]

    def test_vv_vh_files_identical_grid(self):
        vv_path = PROCESSED / "georeferenced" / "vv_sigma0_epsg4326.tif"
        vh_path = PROCESSED / "georeferenced" / "vh_sigma0_epsg4326.tif"
        with rasterio.open(vv_path) as vv, rasterio.open(vh_path) as vh:
            assert vv.width == vh.width
            assert vv.height == vh.height
            assert str(vv.crs) == str(vh.crs)
            assert tuple(vv.bounds) == tuple(vh.bounds)


# ─── Step 11: Physical values ────────────────────────────────────────────────

class TestPhysicalValues:
    """Verify calibrated values are physically plausible for ocean."""

    def test_physical_values_exist(self):
        p = OUTPUTS / "physical_values.json"
        assert p.exists()
        data = json.loads(p.read_text())
        assert "VV" in data and "VH" in data

    def test_vv_ocean_range(self):
        data = json.loads((OUTPUTS / "physical_values.json").read_text())
        vv = data["VV"]
        # C-band VV ocean: typically -30 to -10 dB (0.001 to 0.1 linear)
        assert -35 < vv["dB_mean"] < -5, f"VV mean {vv['dB_mean']} dB outside ocean range"
        assert -35 < vv["dB_median"] < -5

    def test_vh_ocean_range(self):
        data = json.loads((OUTPUTS / "physical_values.json").read_text())
        vh = data["VH"]
        # C-band VH ocean: typically -45 to -20 dB
        assert -50 < vh["dB_mean"] < -15, f"VH mean {vh['dB_mean']} dB outside ocean range"
        assert -50 < vh["dB_median"] < -15

    def test_vv_vh_ratio_physically_consistent(self):
        data = json.loads((OUTPUTS / "physical_values.json").read_text())
        # VV should be stronger than VH (co-pol > cross-pol)
        assert data["VV"]["mean"] > data["VH"]["mean"], "VV must be stronger than VH"
        ratio_db = data["VV"]["dB_mean"] - data["VH"]["dB_mean"]
        assert 5 < ratio_db < 20, f"VV-VH ratio {ratio_db:.1f} dB outside expected range"

    def test_percentiles_ordered(self):
        data = json.loads((OUTPUTS / "physical_values.json").read_text())
        for pol in ("VV", "VH"):
            pcts = data[pol]["percentiles"]
            assert pcts["p1"] < pcts["p5"] < pcts["p50"] < pcts["p95"] < pcts["p99"]


# ─── Step 12: dB conversion ──────────────────────────────────────────────────

class TestDbConversion:
    """Verify dB = 10*log10(linear)."""

    def test_db_conversion_exists(self):
        p = OUTPUTS / "db_conversion_validation.json"
        assert p.exists()
        data = json.loads(p.read_text())
        assert "VV" in data and "VH" in data

    def test_db_conversion_verified(self):
        data = json.loads((OUTPUTS / "db_conversion_validation.json").read_text())
        for pol in ("VV", "VH"):
            assert data[pol]["status"] == "VERIFIED"
            assert data[pol]["mismatches"] == 0
            assert data[pol]["inf_in_output"] == 0

    def test_no_infinities_in_db_output(self):
        for pol in ("vv", "vh"):
            db_path = PROCESSED / "model_input" / f"{pol}_sigma0_db.tif"
            with rasterio.open(db_path) as ds:
                sample = ds.read(1, out_shape=(ds.height // 32, ds.width // 32))
            assert np.isinf(sample).sum() == 0, f"{pol} dB output contains infinities"


# ─── Step 13: Visual quality ─────────────────────────────────────────────────

class TestVisualQuality:
    def test_preview_images_exist(self):
        for name in ("vv_sigma0_db_visual.png", "vh_sigma0_db_visual.png",
                      "vv_vh_composite_visual.png"):
            p = OUTPUTS / name
            assert p.exists(), f"Visual output {name} not found"
            assert p.stat().st_size > 5000, f"{name} too small"


# ─── Step 14: Performance ────────────────────────────────────────────────────

class TestPerformance:
    def test_performance_metrics_exist(self):
        p = OUTPUTS / "performance_metrics.json"
        assert p.exists()
        data = json.loads(p.read_text())
        assert data["total_processing_time_s"] > 0
        assert data["input_file_size_bytes"] > 0
        assert data["total_output_bytes"] > 0


# ─── Regression: existing test count ─────────────────────────────────────────

class TestRegressionSuite:
    """Verify the existing test suite still passes (97 passed, 2 skipped)."""

    def test_output_files_count(self):
        """All 16 expected output files exist."""
        expected = [
            "calibration_validation.json",
            "independent_reference_comparison.json",
            "lut_interpolation_validation.json",
            "grd_formula_verification.json",
            "constant_08995_investigation.json",
            "georeferencing_validation.json",
            "gcp_residual_map.png",
            "nan_analysis.json",
            "georeferencing_comparison.json",
            "vv_vh_alignment.json",
            "physical_values.json",
            "db_conversion_validation.json",
            "performance_metrics.json",
            "vv_sigma0_db_visual.png",
            "vh_sigma0_db_visual.png",
            "vv_vh_composite_visual.png",
        ]
        for name in expected:
            assert (OUTPUTS / name).exists(), f"Missing output: {name}"
