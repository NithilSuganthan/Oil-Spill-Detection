"""Portable Sentinel-1 SAR chip verifier trained from labelled oil/no-oil chips.

This model verifies whether an extracted candidate region resembles a labelled
oil feature. It complements—but cannot replace—pixel-level segmentation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import json
import numpy as np
from PIL import Image


def sar_chip_features(image: np.ndarray) -> np.ndarray:
    """Intensity, darkness and texture features from one grayscale SAR chip."""
    x = image.astype(np.float32) / 255.0
    gx, gy = np.diff(x, axis=1), np.diff(x, axis=0)
    quantiles = np.quantile(x, [0.02, 0.1, 0.25, 0.5, 0.75, 0.9, 0.98])
    return np.asarray([
        x.mean(), x.std(), *quantiles,
        (x < 0.15).mean(), (x < 0.3).mean(), (x > 0.8).mean(),
        np.abs(gx).mean(), np.abs(gx).std(), np.abs(gy).mean(), np.abs(gy).std(),
    ], dtype=np.float32)


def read_chip(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("L").resize((128, 128)), dtype=np.uint8)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def _binary_metrics(y: np.ndarray, score: np.ndarray) -> dict[str, float]:
    pred = score >= 0.5; tp = int(((pred == 1) & (y == 1)).sum()); fp = int(((pred == 1) & (y == 0)).sum()); fn = int(((pred == 0) & (y == 1)).sum()); tn = int(((pred == 0) & (y == 0)).sum())
    precision = tp / max(tp + fp, 1); recall = tp / max(tp + fn, 1); f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    # Mann-Whitney rank AUC; no sklearn dependency.
    ranks = np.empty_like(score, dtype=float); ranks[np.argsort(score, kind="stable")] = np.arange(1, len(score) + 1)
    positives = int(y.sum()); negatives = len(y) - positives; auc = (ranks[y == 1].sum() - positives * (positives + 1) / 2) / max(positives * negatives, 1)
    return {"accuracy": (tp + tn) / len(y), "precision": precision, "recall": recall, "f1": f1, "roc_auc_rank": float(auc), "tp": tp, "fp": fp, "fn": fn, "tn": tn}


@dataclass(slots=True)
class SARChipVerifier:
    weights: np.ndarray | None = None
    bias: float = 0.0
    mean: np.ndarray | None = None
    std: np.ndarray | None = None
    model_version: str = "csiro-s1-logistic-v1"
    estimator: object | None = None

    @classmethod
    def load(cls, path: str | Path) -> "SARChipVerifier":
        path = Path(path)
        if path.suffix == ".joblib":
            import joblib
            saved = joblib.load(path)
            return cls(model_version=saved["model_version"], estimator=saved["estimator"])
        saved = np.load(path); return cls(saved["weights"], float(saved["bias"]), saved["mean"], saved["std"], str(saved["model_version"]))

    def predict_proba(self, chip: np.ndarray) -> float:
        feature = sar_chip_features(chip)
        if self.estimator is not None:
            return float(self.estimator.predict_proba(feature[None, :])[0, 1])  # type: ignore[attr-defined]
        assert self.mean is not None and self.std is not None and self.weights is not None
        feature = (feature - self.mean) / self.std
        return float(_sigmoid(np.asarray([feature @ self.weights + self.bias]))[0])


def train_csiro_verifier(data_dir: Path, output: Path, epochs: int = 200, learning_rate: float = 0.1, seed: int = 24, model: str = "random_forest") -> dict[str, float]:
    """Train/test split at chip level; reports held-out metrics for a baseline."""
    zero = sorted((data_dir / "Class_0").glob("*.jpg")); one = sorted((data_dir / "Class_1").glob("*.jpg"))
    if not zero or not one: raise ValueError("Expected data_dir/Class_0 and data_dir/Class_1 JPEG files.")
    paths = zero + one; labels = np.asarray([0] * len(zero) + [1] * len(one), dtype=np.float32)
    x = np.vstack([sar_chip_features(read_chip(path)) for path in paths])
    rng = np.random.default_rng(seed); train_indices: list[int] = []; test_indices: list[int] = []
    for label in (0, 1):
        indices = np.where(labels == label)[0]; rng.shuffle(indices); split = int(len(indices) * 0.8); train_indices.extend(indices[:split]); test_indices.extend(indices[split:])
    train_idx, test_idx = np.asarray(train_indices), np.asarray(test_indices); rng.shuffle(train_idx)
    mean, std = x[train_idx].mean(0), np.maximum(x[train_idx].std(0), 1e-6); train_x, test_x = (x[train_idx] - mean) / std, (x[test_idx] - mean) / std; train_y, test_y = labels[train_idx], labels[test_idx]
    if model == "random_forest":
        from sklearn.ensemble import RandomForestClassifier
        estimator = RandomForestClassifier(n_estimators=500, min_samples_leaf=2, class_weight="balanced", max_features="sqrt", n_jobs=-1, random_state=seed).fit(x[train_idx], train_y)
        probability = estimator.predict_proba(x[test_idx])[:, 1]
        metrics = _binary_metrics(test_y, probability); metrics.update({"model": "random_forest", "train_samples": int(len(train_y)), "test_samples": int(len(test_y)), "class_0": int(len(zero)), "class_1": int(len(one))})
        import joblib
        output = output.with_suffix(".joblib"); output.parent.mkdir(parents=True, exist_ok=True); joblib.dump({"estimator": estimator, "model_version": "csiro-s1-random-forest-v1"}, output)
        output.with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        return metrics
    weights = np.zeros(train_x.shape[1], dtype=float); bias = 0.0; positive_weight = (train_y == 0).sum() / max((train_y == 1).sum(), 1)
    for _ in range(epochs):
        probability = _sigmoid(train_x @ weights + bias); error = (probability - train_y) * np.where(train_y == 1, positive_weight, 1.0)
        weights -= learning_rate * (train_x.T @ error / len(train_y)); bias -= learning_rate * float(error.mean())
    metrics = _binary_metrics(test_y, _sigmoid(test_x @ weights + bias)); metrics.update({"train_samples": int(len(train_y)), "test_samples": int(len(test_y)), "class_0": int(len(zero)), "class_1": int(len(one))})
    output = output.with_suffix(".npz"); output.parent.mkdir(parents=True, exist_ok=True); np.savez_compressed(output, weights=weights, bias=bias, mean=mean, std=std, model_version="csiro-s1-logistic-v1")
    output.with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train real-SAR candidate verifier on the CSIRO Sentinel-1 chip dataset.")
    parser.add_argument("--data-dir", type=Path, required=True); parser.add_argument("--out", type=Path, default=Path("artifacts/csiro_s1_verifier.joblib")); parser.add_argument("--epochs", type=int, default=200); parser.add_argument("--model", choices=["random_forest", "logistic"], default="random_forest")
    args = parser.parse_args(); print(json.dumps(train_csiro_verifier(args.data_dir, args.out, args.epochs, model=args.model), indent=2))


if __name__ == "__main__":
    main()
