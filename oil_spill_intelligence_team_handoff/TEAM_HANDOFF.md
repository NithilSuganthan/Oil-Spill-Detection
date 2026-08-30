# Team Handoff — Oil Spill Intelligence Models

## What is included

This package contains three integration-ready analytical modules:

1. **SAR potential-slick detection and verification**
2. **Forward-ensemble drift hindcasting**
3. **Explainable AIS vessel candidate ranking**

All outputs are advisory and carry a human-review requirement. They must never be displayed as a legal attribution or confirmation of pollution.

## 1. SAR potential-slick model

### Real trained model

- Artifact: `artifacts/csiro_s1_verifier.joblib`
- Type: Random Forest binary classifier (500 trees, balanced class weighting)
- Input: a grayscale Sentinel-1 SAR candidate chip; the integration wrapper resizes candidate regions to 128×128.
- Output: probability that a candidate resembles an oil-feature chip. This is combined with segmentation confidence and environmental quality flags.
- Training data: CSIRO Sentinel-1 oil/no-oil chip dataset, redistributed via Kaggle under CC BY-SA 4.0. The downloaded copy used 5,538 JPEG chips: 3,695 no-oil/look-alike and 1,843 oil-feature chips.

### Held-out evaluation

An 80/20 stratified chip-level split, fixed random seed 24:

| Metric | Value |
|---|---:|
| Test chips | 1,108 |
| Accuracy | 88.81% |
| Oil precision | 83.20% |
| Oil recall | 83.20% |
| Oil F1 | 83.20% |
| ROC-AUC | 95.75% |
| True positives / false positives / false negatives / true negatives | 307 / 62 / 62 / 677 |

### Critical limitations & Segmentation Handoff

- The CSIRO model is a **chip-level verifier**, not a pixel-mask segmentation model. It cannot itself produce a slick boundary, area, or georeferenced polygon.
- To produce the real pixel-level U-Net model, we have prepared:
  - `scripts/prepare_zenodo_segmentation_dataset.py`: automated script to download and format the Zenodo Sentinel-1 SAR Oil Spill dataset (Record 8346860, CC BY 4.0, ~1.5 GB).
  - `src/oil_spill_intel/detection/train_and_evaluate.py`: full training + validation + held-out test evaluation + golden fixture export + model card generation.
  - `artifacts/segmentation_model_integration_contract.json`: locked API and tensor specification for backend integration partners.
  - `tests/test_segmentation_integration.py`: automated verification tests that validate the checkpoint and golden fixture outputs once trained.

## 2. Drift / hindcast model

- Module: `oil_spill_intel.drift.EnsembleHindcaster`
- Method: BAKTRAK-inspired iterative forward particle ensemble. Candidate release locations and times are run forward to the observed slick; the best-fitting states are resampled over several iterations.
- Inputs: observed slick centroid/time, release-time window, and a forcing provider.
- Outputs: probable source centroid, release-time window, particle ensemble, uncertainty radius, and hindcast-derived age estimate.
- Current forcing adapter: `ConstantForcing`, intended only for tests and demonstrations.

**Integration requirement:** Replace the constant adapter with validated gridded current/wind/tide data (for example an INCOIS-compatible adapter) before presenting real-world output.

## 3. AIS attribution engine

- Module: `oil_spill_intel.attribution.rank_vessels`
- Inputs: standardized AIS CSV/DataFrame and the hindcast source region/time window.
- Candidate score factors: source proximity, time alignment, declared vessel context, and AIS continuity gaps.
- AIS gap contribution is deliberately zero unless coverage/latency is independently known (`coverage_known=True`).
- Output: ordered candidate vessels with component-level explanations.

**Interpretation:** Scores are prioritisation signals, not probabilities of culpability. Future work should add trained long-term behavioural anomalies and validate against investigated historical incidents.

## How components connect

```text
SAR image -> segmentation candidate (TinyUNet) -> real-SAR verifier + quality flags
         -> reviewed slick centroid/time -> hindcast source/time ensemble
         -> source/time window + AIS tracks -> candidate ranking
         -> map UI + human analyst review
```

## Quick integration

```python
from oil_spill_intel.detection import PotentialSlickDetector
from oil_spill_intel.drift import ConstantForcing, EnsembleHindcaster
from oil_spill_intel.attribution import rank_vessels

detector = PotentialSlickDetector(
    verifier_model_path="artifacts/csiro_s1_verifier.joblib"
)
# detection = detector.predict(scene_id, acquired_at, sar_array, metadata)
# hindcast = EnsembleHindcaster(real_forcing).infer(...)
# candidates = rank_vessels(ais_dataframe, source_lonlat, release_start, release_end)
```

See `README.md` and `INTEGRATION.md` for exact input fields and commands.
- `artifacts/csiro_s1_verifier.metrics.json` is the machine-readable classifier training report.
- `artifacts/segmentation_model_integration_contract.json` is the locked segmentation integration contract.

## Dataset attribution

1. CSIRO Sentinel-1 SAR image dataset of oil- and non-oil features for machine learning: Blondeau-Patissier, D., Schroeder, T., Diakogiannis, F., & Li, Z. (2022), DOI 10.25919/4V55-DN16. Licence: CC BY-SA 4.0.
2. Zenodo Sentinel-1 SAR Oil Spill Detection Dataset: Record 8346860 (2023). Licence: CC BY 4.0.

The raw downloaded images are intentionally not included in the handoff ZIP. They are separately documented in `data/DATASET_NOTICE.md` and can be downloaded using `scripts/prepare_zenodo_segmentation_dataset.py`.
