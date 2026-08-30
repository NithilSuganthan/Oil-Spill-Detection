"""Training entry point for a supervised SAR segmentation baseline."""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np

from .data import SARSegmentationDataset
from .model import TinyUNet


def dice_bce_loss(logits, target):  # type: ignore[no-untyped-def]
    import torch
    import torch.nn.functional as f
    bce = f.binary_cross_entropy_with_logits(logits, target)
    probs = torch.sigmoid(logits)
    numerator = 2 * (probs * target).sum(dim=(1, 2, 3)) + 1
    denominator = probs.sum(dim=(1, 2, 3)) + target.sum(dim=(1, 2, 3)) + 1
    return 0.5 * bce + 0.5 * (1 - numerator.div(denominator).mean())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-dir", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--out", type=Path, default=Path("artifacts/sar_unet.pt"))
    parser.add_argument("--numpy-baseline", action="store_true", help="Train the portable logistic baseline instead of PyTorch U-Net.")
    args = parser.parse_args()
    paths = sorted(args.train_dir.glob("*.npz"))
    if not paths:
        raise SystemExit("No paired .npz training samples found.")
    if args.numpy_baseline:
        _train_numpy_baseline(paths, args.out, args.epochs)
        return
    import torch
    from torch.utils.data import DataLoader
    loader = DataLoader(SARSegmentationDataset(paths), batch_size=args.batch_size, shuffle=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = TinyUNet().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    for epoch in range(args.epochs):
        model.train(); total = 0.0
        for sar, mask in loader:
            sar, mask = sar.to(device), mask.to(device)
            opt.zero_grad(); loss = dice_bce_loss(model(sar), mask); loss.backward(); opt.step(); total += float(loss)
        print(f"epoch={epoch + 1} loss={total / len(loader):.4f}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model_state": model.state_dict(), "in_channels": 2, "model_version": "tiny-unet-v1"}, args.out)


def _train_numpy_baseline(paths: list[Path], output: Path, epochs: int) -> None:
    """Portable balanced logistic baseline for environment/integration validation.

    This is intentionally not a substitute for the U-Net. It permits a complete
    training smoke test where a compatible PyTorch runtime is unavailable.
    """
    from .data import robust_normalize
    features: list[np.ndarray] = []; labels: list[np.ndarray] = []
    rng = np.random.default_rng(24)
    for path in paths:
        sample = np.load(path); x = robust_normalize(sample["sar"]).reshape(sample["sar"].shape[0], -1).T; y = sample["mask"].reshape(-1).astype(float)
        positive, negative = np.where(y > 0)[0], np.where(y == 0)[0]
        if len(positive) and len(negative):
            chosen_negative = rng.choice(negative, size=min(len(negative), len(positive) * 2), replace=False)
            chosen = np.concatenate([positive, chosen_negative]); features.append(x[chosen]); labels.append(y[chosen])
    if not features: raise SystemExit("Need samples containing both oil and background pixels for baseline training.")
    x = np.concatenate(features); y = np.concatenate(labels); mean, std = x.mean(0), np.maximum(x.std(0), 1e-6); x = (x - mean) / std
    weights = np.zeros(x.shape[1]); bias = 0.0; learning_rate = 0.1
    for epoch in range(epochs * 10):
        probs = 1 / (1 + np.exp(-np.clip(x @ weights + bias, -30, 30))); error = probs - y
        weights -= learning_rate * (x.T @ error / len(y)); bias -= learning_rate * float(error.mean())
        if (epoch + 1) % 10 == 0: print(f"epoch={(epoch + 1) // 10} logistic_loss={float(-(y*np.log(probs+1e-8)+(1-y)*np.log(1-probs+1e-8)).mean()):.4f}")
    output = output.with_suffix(".npz"); output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, weights=weights, bias=bias, mean=mean, std=std, model_version="numpy-logistic-v1")
    print(f"Saved portable baseline to {output}")


if __name__ == "__main__":
    main()
