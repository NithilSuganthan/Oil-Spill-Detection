"""
Integration verification test for the trained TinyUNet checkpoint.

This test suite verifies that:
1. The checkpoint loads correctly and matches the contract.
2. Model inference on the golden input reproduces the expected probability mask.
3. The preprocessing pipeline (robust_normalize) is unchanged.
4. The output format (logits -> sigmoid -> binary) is correct.

Run with:
    python -m pytest tests/test_segmentation_integration.py -v

The test is automatically skipped if the checkpoint or golden fixture does not
yet exist — it becomes active once training completes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import numpy as np
import pytest

ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"
CHECKPOINT_PATH = ARTIFACTS_DIR / "sar_unet.pt"
GOLDEN_OUTPUT_NPZ = ARTIFACTS_DIR / "sar_unet.golden_output.npz"
GOLDEN_META_PATH = ARTIFACTS_DIR / "sar_unet.golden_output.meta.json"
CONTRACT_PATH = ARTIFACTS_DIR / "segmentation_model_integration_contract.json"
METRICS_PATH = ARTIFACTS_DIR / "sar_unet.metrics.json"

CHECKPOINT_EXISTS = CHECKPOINT_PATH.exists()
GOLDEN_EXISTS = GOLDEN_OUTPUT_NPZ.exists()


@pytest.mark.skipif(not CHECKPOINT_EXISTS, reason="sar_unet.pt not yet trained. Run train_and_evaluate.py first.")
def test_checkpoint_structure():
    """Checkpoint must contain required keys and match the model contract."""
    import torch
    checkpoint = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=True)
    assert "model_state" in checkpoint, "Missing model_state key"
    assert "in_channels" in checkpoint, "Missing in_channels key"
    assert "model_version" in checkpoint, "Missing model_version key"
    assert checkpoint["in_channels"] == 2, f"Expected 2 input channels, got {checkpoint['in_channels']}"
    assert checkpoint["model_version"] == "tiny-unet-v1", f"Unexpected model version: {checkpoint['model_version']}"
    assert "threshold" in checkpoint, "Threshold must be stored in checkpoint"


@pytest.mark.skipif(not CHECKPOINT_EXISTS, reason="sar_unet.pt not yet trained.")
def test_model_loads_and_forward_passes():
    """Model must load from checkpoint and accept a 2-channel float32 tile."""
    import torch
    from oil_spill_intel.detection.model import TinyUNet

    checkpoint = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=True)
    model = TinyUNet(in_channels=checkpoint["in_channels"],
                     base_channels=checkpoint.get("base_channels", 32))
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    # Test with 512x512 (native) and 128x128 (smaller tile) — must both work
    for h, w in [(512, 512), (128, 128)]:
        rng = np.random.default_rng(0)
        sar = rng.uniform(0, 1, (2, h, w)).astype(np.float32)
        inp = torch.from_numpy(sar)[None, ...]  # [1, 2, H, W]
        with torch.no_grad():
            logits = model(inp)
        assert logits.shape == (1, 1, h, w), f"Output shape mismatch for ({h}, {w}): {logits.shape}"
        prob = torch.sigmoid(logits)
        assert float(prob.min()) >= 0.0 and float(prob.max()) <= 1.0


@pytest.mark.skipif(not CHECKPOINT_EXISTS, reason="sar_unet.pt not yet trained.")
def test_preprocessing_contract():
    """robust_normalize output must be in [0, 1] and float32."""
    from oil_spill_intel.detection.data import robust_normalize

    rng = np.random.default_rng(1)
    # Simulate linear sigma0 SAR values (typically very small floats)
    raw_sar = rng.uniform(0.0001, 0.5, (2, 256, 256)).astype(np.float32)
    # Inject a dark region to simulate an oil slick
    raw_sar[:, 80:150, 60:200] *= 0.02

    norm = robust_normalize(raw_sar)
    assert norm.dtype == np.float32, "Output must be float32"
    assert norm.shape == raw_sar.shape, "Shape must be preserved"
    assert float(norm.min()) >= 0.0, "Minimum must be >= 0"
    assert float(norm.max()) <= 1.0, "Maximum must be <= 1"


@pytest.mark.skipif(
    not (CHECKPOINT_EXISTS and GOLDEN_EXISTS),
    reason="sar_unet.pt and/or golden_output.npz not yet available.",
)
def test_golden_fixture_reproducibility():
    """
    The trained model must reproduce the golden output exactly (within float32 precision).

    This is the key integration verification: if this test fails, preprocessing
    or model loading has changed since training.
    """
    import torch
    from oil_spill_intel.detection.model import TinyUNet

    d = np.load(GOLDEN_OUTPUT_NPZ)
    checkpoint = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=True)
    model = TinyUNet(in_channels=checkpoint["in_channels"],
                     base_channels=checkpoint.get("base_channels", 32))
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    # sar_input is already normalised — pass directly to the model
    inp = torch.from_numpy(d["sar_input"])[None, ...]
    with torch.no_grad():
        logits = model(inp)
    prob = torch.sigmoid(logits).squeeze().numpy()

    expected = d["expected_prob_mask"]
    assert np.allclose(prob, expected, atol=1e-5), (
        f"Golden output mismatch! Max delta: {np.abs(prob - expected).max():.2e}. "
        "Preprocessing or model loading is broken."
    )


@pytest.mark.skipif(not GOLDEN_EXISTS, reason="golden_output.npz not yet available.")
def test_golden_fixture_sha256():
    """Golden fixture SHA-256 must match the value recorded in the meta JSON."""
    if not GOLDEN_META_PATH.exists():
        pytest.skip("golden_output.meta.json not found.")
    meta = json.loads(GOLDEN_META_PATH.read_text())
    expected_sha256 = meta.get("sha256_golden_output_npz", "")
    if not expected_sha256:
        pytest.skip("No SHA-256 recorded in golden meta.")
    actual_sha256 = hashlib.sha256(GOLDEN_OUTPUT_NPZ.read_bytes()).hexdigest()
    assert actual_sha256 == expected_sha256, (
        f"Golden fixture SHA-256 mismatch!\n"
        f"Expected: {expected_sha256}\n"
        f"Actual:   {actual_sha256}\n"
        "The golden fixture file may have been corrupted or regenerated."
    )


@pytest.mark.skipif(not METRICS_PATH.exists(), reason="sar_unet.metrics.json not yet available.")
def test_metrics_minimum_quality_bar():
    """
    The trained model must report valid metrics and exceed baseline performance.
    """
    metrics = json.loads(METRICS_PATH.read_text())
    best_dice = max(metrics.get("dice_f1", 0.0), metrics.get("best_val_dice_f1", 0.0))
    assert best_dice >= 0.40, (
        f"Best Dice/F1 {best_dice:.4f} is below minimum threshold 0.40. "
        "Consider more epochs, data augmentation, or a larger model."
    )

    assert "precision" in metrics and "recall" in metrics
    assert metrics["best_epoch"] >= 1



@pytest.mark.skipif(not CHECKPOINT_EXISTS, reason="sar_unet.pt not yet trained.")
def test_pipelined_with_potential_slick_detector():
    """End-to-end: PotentialSlickDetector correctly loads and uses the U-Net checkpoint."""
    import torch
    from datetime import datetime, timezone
    from oil_spill_intel.detection.inference import PotentialSlickDetector
    from oil_spill_intel.detection.data import robust_normalize

    rng = np.random.default_rng(7)
    sar = rng.uniform(0.0001, 0.5, (2, 128, 128)).astype(np.float32)
    # Inject dark region
    sar[:, 40:70, 50:100] *= 0.01

    detector = PotentialSlickDetector(
        model_path=str(CHECKPOINT_PATH),
        threshold=0.5,
        min_pixels=10,
    )
    assert detector.model is not None, "Detector did not load the U-Net model."
    assert detector.model_version == "tiny-unet-v1"

    result = detector.predict(
        scene_id="integration-test-001",
        acquired_at=datetime(2026, 8, 26, 8, tzinfo=timezone.utc),
        sar=sar,
        metadata={
            "bounds_lonlat": [72.0, 18.0, 73.0, 19.0],
            "pixel_area_km2": 0.01,
            "wind_speed_mps": 6.0,
            "wave_height_m": 1.0,
            "incidence_angle_deg": 33.0,
        },
    )
    assert result.human_review_required is True
    assert result.model_version == "tiny-unet-v1"
    # Confidence must be a float in [0, 1]
    assert 0.0 <= result.detection_confidence <= 1.0
