"""
Full training + evaluation pipeline for the TinyUNet SAR segmentation model.

Produces:
  <out>.pt                    — PyTorch checkpoint (model_state + metadata)
  <out>.metrics.json          — held-out segmentation metrics
  <out>.golden_output.npz     — golden input + expected probability mask + expected binary mask
  <out>.model_card.json       — all fields requested by integration partners

Usage (after running prepare_zenodo_segmentation_dataset.py):

    python -m oil_spill_intel.detection.train_and_evaluate \\
        --train-dir data/zenodo_s1_segmentation/npz \\
        --split-dir data/zenodo_s1_segmentation/splits \\
        --golden-dir data/zenodo_s1_segmentation/golden \\
        --out artifacts/sar_unet.pt \\
        --epochs 25 \\
        --batch-size 4

The golden output NPZ is the key integration contract artifact:
  sar_input           float32 [2, H, W]  — normalised SAR (after robust_normalize)
  expected_prob_mask  float32 [H, W]     — sigmoid of model logits at threshold=0.5
  expected_binary_mask uint8  [H, W]     — (prob >= threshold).astype(uint8)
  gt_mask             uint8  [H, W]      — ground-truth oil mask
  threshold           float              — recommended threshold (0.5 default)
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

from .data import SARSegmentationDataset, robust_normalize
from .model import TinyUNet


# ── loss ──────────────────────────────────────────────────────────────────────

def dice_bce_loss(logits, target):  # type: ignore[no-untyped-def]
    import torch
    import torch.nn.functional as f
    bce = f.binary_cross_entropy_with_logits(logits, target)
    probs = torch.sigmoid(logits)
    intersection = (probs * target).sum(dim=(1, 2, 3))
    cardinality = probs.sum(dim=(1, 2, 3)) + target.sum(dim=(1, 2, 3))
    dice = (2.0 * intersection + 1.0) / (cardinality + 1.0)
    dice_loss = 1.0 - dice.mean()
    return 0.5 * bce + 0.5 * dice_loss




# ── segmentation metrics ───────────────────────────────────────────────────────

def segmentation_metrics(
    gt_masks: list[np.ndarray],
    pred_probs: list[np.ndarray],
    threshold: float = 0.5,
) -> dict[str, float]:
    """
    Compute pixel-level segmentation metrics across all scenes.

    Returns: dice_f1, iou, precision, recall, pixel_accuracy,
             false_positive_rate, area_error_km2_mean (requires pixel_area_km2).
    """
    tp = fp = fn = tn = 0
    for gt, prob in zip(gt_masks, pred_probs):
        pred = (prob >= threshold).astype(np.uint8)
        tp += int(((pred == 1) & (gt == 1)).sum())
        fp += int(((pred == 1) & (gt == 0)).sum())
        fn += int(((pred == 0) & (gt == 1)).sum())
        tn += int(((pred == 0) & (gt == 0)).sum())
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    iou = tp / max(tp + fp + fn, 1)
    accuracy = (tp + tn) / max(tp + fp + fn + tn, 1)
    fpr = fp / max(fp + tn, 1)
    return {
        "dice_f1": round(f1, 6),
        "iou": round(iou, 6),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "pixel_accuracy": round(accuracy, 6),
        "false_positive_rate": round(fpr, 6),
        "tp_pixels": tp,
        "fp_pixels": fp,
        "fn_pixels": fn,
        "tn_pixels": tn,
        "threshold": threshold,
        "note": (
            "Pixel-level metrics. Pixel accuracy alone is misleading (oil pixels are rare). "
            "Dice/F1 and IoU are the primary indicators. "
            "Break down by wind/wave regime and scene size for production evaluation."
        ),
    }


# ── validation pass ────────────────────────────────────────────────────────────

def evaluate(model, paths: list[Path], device: str, threshold: float = 0.5) -> dict[str, float]:  # type: ignore[no-untyped-def]
    import torch
    model.eval()
    gt_masks: list[np.ndarray] = []
    pred_probs: list[np.ndarray] = []
    total_loss = 0.0
    with torch.no_grad():
        for p in paths:
            d = np.load(p)
            sar = torch.from_numpy(robust_normalize(d["sar"]))[None, ...].to(device)
            mask = torch.from_numpy(d["mask"].astype(np.float32))[None, None, ...].to(device)
            logits = model(sar)
            loss = dice_bce_loss(logits, mask)
            total_loss += float(loss)
            prob = torch.sigmoid(logits).squeeze().cpu().numpy()
            gt_masks.append(d["mask"])
            pred_probs.append(prob)
    metrics = segmentation_metrics(gt_masks, pred_probs, threshold)
    metrics["mean_val_loss"] = round(total_loss / max(len(paths), 1), 6)
    return metrics


# ── golden output fixture ─────────────────────────────────────────────────────

def export_golden_output(
    model,  # type: ignore[no-untyped-def]
    golden_input_npz: Path,
    output_path: Path,
    threshold: float = 0.5,
    checkpoint_sha256: str = "",
) -> None:
    """
    Run the trained model on the golden input and save the result.

    This is the integration contract artifact: the integration layer must
    reproduce expected_prob_mask bit-for-bit when given sar_input and the
    same model checkpoint.
    """
    import torch
    model.eval()
    d = np.load(golden_input_npz)
    raw_sar = d["sar"]  # [2, H, W] linear sigma0
    gt_mask = d["mask"]  # [H, W] uint8

    norm_sar = robust_normalize(raw_sar)  # float32 [2, H, W] in [0, 1]
    with torch.no_grad():
        inp = torch.from_numpy(norm_sar)[None, ...]
        logits = model(inp)
        prob_mask = torch.sigmoid(logits).squeeze().numpy()  # float32 [H, W]

    binary_mask = (prob_mask >= threshold).astype(np.uint8)
    np.savez_compressed(
        output_path,
        sar_input=norm_sar,           # float32 [2, H, W]  — the input AFTER normalization
        raw_sar=raw_sar,              # float32 [2, H, W]  — raw values for reference
        expected_prob_mask=prob_mask, # float32 [H, W]
        expected_binary_mask=binary_mask,  # uint8  [H, W]
        gt_mask=gt_mask,              # uint8  [H, W]  — ground truth
        threshold=np.float32(threshold),
    )

    # metrics for this one golden scene
    metrics = segmentation_metrics([gt_mask], [prob_mask], threshold)
    sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()

    meta = {
        "description": "Golden input/output pair for TinyUNet integration verification.",
        "channel_order": {
            "sar_input[0]": "VV — linear sigma0, robust_normalize applied",
            "sar_input[1]": "VH — linear sigma0, robust_normalize applied",
        },
        "preprocessing": (
            "robust_normalize(): per-channel percentile [p1, p99] clip and rescale to [0,1]. "
            "Computed per-scene at inference time. "
            "Source: oil_spill_intel.detection.data.robust_normalize()"
        ),
        "model_output": "raw logits [1, H, W]; sigmoid applied to get expected_prob_mask",
        "threshold": threshold,
        "golden_scene_metrics": metrics,
        "sha256_golden_output_npz": sha256,
        "checkpoint_sha256": checkpoint_sha256,
        "integration_check": (
            "Load sar_input (already normalised) directly into TinyUNet. "
            "Assert torch.allclose(sigmoid(model(sar_input)), expected_prob_mask, atol=1e-5). "
            "If this fails, preprocessing or model loading is broken."
        ),
    }
    output_path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"  Golden output: {output_path}")
    print(f"  Golden scene IoU: {metrics['iou']:.4f}  Dice: {metrics['dice_f1']:.4f}")


# ── main training loop ─────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate TinyUNet on paired SAR/mask NPZ files.")
    parser.add_argument("--train-dir", type=Path, required=True,
                        help="Directory containing all scene .npz files.")
    parser.add_argument("--split-dir", type=Path, default=None,
                        help="Directory with train.txt/val.txt/test.txt from the prepare script. "
                             "If not given, an 80/10/10 split is generated automatically.")
    parser.add_argument("--golden-dir", type=Path, default=None,
                        help="Directory containing golden_input.npz from the prepare script.")
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--out", type=Path, default=Path("artifacts/sar_unet.pt"))
    args = parser.parse_args()

    import torch
    from torch.utils.data import DataLoader

    # ── resolve file paths ────────────────────────────────────────────────────
    all_npz = sorted(args.train_dir.glob("*.npz"))
    if not all_npz:
        raise SystemExit(f"No .npz files found in {args.train_dir}")

    if args.split_dir and (args.split_dir / "train.txt").exists():
        def _load_split(name: str) -> list[Path]:
            ids = (args.split_dir / f"{name}.txt").read_text().splitlines()
            return [args.train_dir / f"{sid}.npz" for sid in ids if (args.train_dir / f"{sid}.npz").exists()]
        train_paths = _load_split("train")
        val_paths = _load_split("val")
        test_paths = _load_split("test")
    else:
        print("No split files found; generating 80/10/10 scene-level split.")
        rng = np.random.default_rng(42)
        indices = np.arange(len(all_npz))
        rng.shuffle(indices)
        n_test = max(1, len(all_npz) // 10)
        n_val = max(1, len(all_npz) // 10)
        test_paths = [all_npz[i] for i in indices[:n_test]]
        val_paths = [all_npz[i] for i in indices[n_test: n_test + n_val]]
        train_paths = [all_npz[i] for i in indices[n_test + n_val:]]

    print(f"Train: {len(train_paths)}  Val: {len(val_paths)}  Test: {len(test_paths)} scenes")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    model = TinyUNet(in_channels=2, base_channels=32).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs, eta_min=1e-5)

    loader = DataLoader(
        SARSegmentationDataset(train_paths),
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,  # 0 for Windows compatibility
    )

    best_val_dice = 0.0
    best_epoch = 0

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        for sar, mask in loader:
            sar, mask = sar.to(device), mask.to(device)
            opt.zero_grad()
            loss = dice_bce_loss(model(sar), mask)
            loss.backward()
            opt.step()
            total_loss += float(loss.detach())
        scheduler.step()

        train_loss = total_loss / max(len(loader), 1)
        val_metrics = evaluate(model, val_paths, device, args.threshold)
        val_dice = val_metrics["dice_f1"]
        lr = scheduler.get_last_lr()[0]
        print(f"epoch={epoch:3d}/{args.epochs}  train_loss={train_loss:.4f}  val_dice={val_dice:.4f}  val_iou={val_metrics['iou']:.4f}  lr={lr:.2e}")

        if epoch == 1 or val_dice >= best_val_dice:
            best_val_dice = val_dice
            best_epoch = epoch
            args.out.parent.mkdir(parents=True, exist_ok=True)
            torch.save({
                "model_state": model.state_dict(),
                "in_channels": 2,
                "base_channels": 32,
                "model_version": "tiny-unet-v1",
                "epoch": epoch,
                "val_dice_f1": val_dice,
                "val_iou": val_metrics["iou"],
                "threshold": args.threshold,
                "dataset": "zenodo_sentinel1_8346860",
                "sar_channels": ["VV_linear_sigma0", "VH_linear_sigma0"],
                "preprocessing": "robust_normalize_per_scene_p1_p99",
            }, args.out)

    print(f"\nBest checkpoint: epoch={best_epoch}  val_dice={best_val_dice:.4f}")


    # ── load best checkpoint for evaluation ───────────────────────────────────
    checkpoint = torch.load(args.out, map_location="cpu", weights_only=True)
    model.load_state_dict(checkpoint["model_state"])
    model.to(device)

    # Compute SHA-256 of the checkpoint file
    checkpoint_sha256 = hashlib.sha256(args.out.read_bytes()).hexdigest()

    # ── held-out test evaluation ───────────────────────────────────────────────
    print("\nEvaluating on held-out test set ...")
    test_metrics = evaluate(model, test_paths, device, args.threshold)
    test_metrics["n_test_scenes"] = len(test_paths)
    test_metrics["n_train_scenes"] = len(train_paths)
    test_metrics["n_val_scenes"] = len(val_paths)
    test_metrics["best_epoch"] = best_epoch
    test_metrics["best_val_dice_f1"] = best_val_dice
    test_metrics["checkpoint_sha256"] = checkpoint_sha256

    metrics_path = args.out.with_suffix(".metrics.json")
    metrics_path.write_text(json.dumps(test_metrics, indent=2), encoding="utf-8")
    print(f"Test metrics -> {metrics_path}")
    print(f"  Dice/F1: {test_metrics['dice_f1']:.4f}")
    print(f"  IoU:     {test_metrics['iou']:.4f}")
    print(f"  Prec:    {test_metrics['precision']:.4f}")
    print(f"  Recall:  {test_metrics['recall']:.4f}")

    # ── golden output fixture ──────────────────────────────────────────────────
    if args.golden_dir and (args.golden_dir / "golden_input.npz").exists():
        print("\nExporting golden output fixture ...")
        model.cpu()
        export_golden_output(
            model,
            args.golden_dir / "golden_input.npz",
            args.out.with_suffix(".golden_output.npz"),
            threshold=args.threshold,
            checkpoint_sha256=checkpoint_sha256,
        )
    else:
        print("\nNo golden_input.npz found; skipping golden output export.")
        print("  Run prepare_zenodo_segmentation_dataset.py first, or pass --golden-dir.")

    # ── model card ────────────────────────────────────────────────────────────
    model_card = {
        "model_name": "TinyUNet SAR Oil Spill Segmentation",
        "model_version": "tiny-unet-v1",
        "checkpoint_file": str(args.out.name),
        "checkpoint_sha256": checkpoint_sha256,
        "architecture": {
            "class": "oil_spill_intel.detection.model.TinyUNet",
            "in_channels": 2,
            "base_channels": 32,
            "depth": "2-level encoder + bottleneck + 2-level decoder",
            "head": "Conv2d(32, 1, kernel=1) — raw logits",
            "total_parameters": sum(p.numel() for p in model.parameters()),
        },
        "input_contract": {
            "tensor_shape": "[2, H, W]  (no fixed H, W)",
            "dtype": "float32",
            "channel_0": "VV polarization — linear sigma0, robust_normalize applied",
            "channel_1": "VH polarization — linear sigma0, robust_normalize applied",
            "sar_scale_before_normalization": "linear_sigma0_raw_from_geotiff (NOT dB)",
            "preprocessing_function": "oil_spill_intel.detection.data.robust_normalize()",
            "preprocessing_detail": (
                "Per-channel: lo, hi = np.nanpercentile(channel, [1, 99]); "
                "output = np.clip((channel - lo) / max(hi - lo, 1e-6), 0, 1). "
                "Computed per-inference tile — NOT a fixed global mean/std."
            ),
        },
        "output_contract": {
            "tensor_shape": "[1, H, W]",
            "dtype": "float32",
            "semantics": "raw logits — apply torch.sigmoid() to get oil probability in [0, 1]",
            "recommended_threshold": args.threshold,
            "threshold_note": (
                "Default 0.5 is a starting point. "
                "Calibrate on held-out scenes for your target geography and vessel type prior."
            ),
        },
        "training": {
            "dataset": "Zenodo Sentinel-1 SAR Oil Spill Dataset (record 8346860)",
            "dataset_url": "https://zenodo.org/records/8346860",
            "dataset_license": "CC BY 4.0",
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "optimizer": "AdamW (lr=1e-3, weight_decay=1e-4)",
            "scheduler": f"CosineAnnealingLR (T_max={args.epochs}, eta_min=1e-5)",
            "loss": "0.5 * BCE + 0.5 * (1 - Dice)",
        },
        "evaluation": test_metrics,
        "limitations": [
            "Pixel accuracy alone is misleading due to class imbalance (oil pixels are rare).",
            "SAR look-alikes (low wind, algae, internal waves, rain cells) are not eliminated by the model.",
            "Performance degrades in very low wind (<3 m/s) and very high wind (>12 m/s) conditions.",
            "Model has not been fine-tuned on Indian Ocean scenes; regional fine-tuning is recommended.",
            "Slick age cannot be estimated from SAR pixel values alone.",
            "SR (super-resolution) output must NOT be used as inference input; use native-resolution SAR.",
        ],
        "guardrails": [
            "Always output 'potential_slick' language, never 'confirmed_oil_spill'.",
            "Always expose look_alike_risk and human_review_required fields.",
            "Validate detection.confidence against held-out scenes before any operational use.",
        ],
    }
    model_card_path = args.out.with_suffix(".model_card.json")
    model_card_path.write_text(json.dumps(model_card, indent=2), encoding="utf-8")
    print(f"\nModel card -> {model_card_path}")
    print("\nTraining complete.")


if __name__ == "__main__":
    main()
