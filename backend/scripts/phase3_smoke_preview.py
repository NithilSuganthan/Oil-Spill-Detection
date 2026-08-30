"""Generate visual QC preview for smoke test outputs."""
import numpy as np
import rasterio
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(r"D:\Oil spill detection")
PROCESSED = ROOT / "data" / "scenes" / "processed" / "S1C_IW_GRDH_1SDV_20260826T005736_20260826T005758_009159_012318_7B48_COG"
SMOKE_DIR = PROCESSED / "inference" / "smoke_test"

# Load smoke test probability
prob_path = SMOKE_DIR / "prediction_smoke_probability.tif"
mask_path = SMOKE_DIR / "prediction_smoke_mask.tif"

with rasterio.open(prob_path) as src:
    prob = src.read(1)
    transform = src.transform
    crs = src.crs
    h, w = prob.shape

with rasterio.open(mask_path) as src:
    mask = src.read(1)

# Load corresponding VV data (same region)
VV_PATH = PROCESSED / "georeferenced" / "vv_sigma0_epsg4326.tif"
with rasterio.open(VV_PATH) as src:
    vv = src.read(1).astype(np.float32)

# Crop VV to match probability region
vv_crop = vv[:h, :w]

# Convert VV to dB for display (clip nodata)
vv_db = np.where(vv_crop > 0, 10 * np.log10(np.clip(vv_crop, 1e-10, None)), -30)
vv_db = np.clip(vv_db, -30, 0)

# Stats
print(f"Probability shape: {prob.shape}")
print(f"Prob range: [{prob.min():.6f}, {prob.max():.6f}]")
print(f"Prob mean: {prob.mean():.6f}")
print(f"Pixels above 0.5: {(mask == 1).sum()}")
print(f"VV dB range: [{vv_db.min():.1f}, {vv_db.max():.1f}]")

# Create figure
fig, axes = plt.subplots(1, 3, figsize=(18, 6))

# Panel 1: VV dB
ax = axes[0]
im0 = ax.imshow(vv_db, cmap="gray", vmin=-25, vmax=-5, aspect="auto")
ax.set_title("VV (dB) — Input", fontsize=11)
ax.set_xlabel("Column (pixel)")
ax.set_ylabel("Row (pixel)")
plt.colorbar(im0, ax=ax, label="dB", shrink=0.8)

# Panel 2: Probability
ax = axes[1]
im1 = ax.imshow(prob, cmap="hot", vmin=0, vmax=1, aspect="auto")
ax.set_title("Probability — Model Output", fontsize=11)
ax.set_xlabel("Column (pixel)")
plt.colorbar(im1, ax=ax, label="Probability", shrink=0.8)

# Panel 3: Binary mask overlay on VV
ax = axes[2]
ax.imshow(vv_db, cmap="gray", vmin=-25, vmax=-5, aspect="auto")
mask_overlay = np.ma.masked_where(mask == 0, mask)
ax.imshow(mask_overlay, cmap="autumn", alpha=0.6, vmin=0, vmax=1, aspect="auto")
n_det = (mask == 1).sum()
ax.set_title(f"Binary Mask (n={n_det}) — Overlay", fontsize=11)
ax.set_xlabel("Column (pixel)")

# Suptitle
fig.suptitle(
    "MODEL PREDICTION — DEVELOPMENT SMOKE TEST\n"
    f"32 tiles, TinyUNet, threshold=0.5 | "
    f"Prob max={prob.max():.4f}, mean={prob.mean():.4f}, "
    f"Above 0.5: {n_det} pixels",
    fontsize=12, fontweight="bold", y=0.98
)
plt.tight_layout(rect=[0, 0, 1, 0.92])

out_path = SMOKE_DIR / "smoke_test_preview.png"
fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
plt.close()
print(f"Saved: {out_path}")
