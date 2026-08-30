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

### Critical limitations

- This is a **chip-level verifier**, not a pixel-mask segmentation model. It cannot itself produce a slick boundary, area, or georeferenced polygon.
- The current segmentation architecture (`TinyUNet`) is implemented but not trained on a real mask-labelled corpus. Pair it with a proper Sentinel-1 imagery-plus-mask dataset before claiming segmenter performance.
- The split is by chip, not independent SAR scene/event/geography. It is a baseline result; a scene-level geographically separated test is required before operational use.
- A positive score means “resembles a labelled oil feature,” not “confirmed oil spill.”

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
SAR image -> segmentation candidate -> real-SAR verifier + quality flags
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

See `README.md` and `INTEGRATION.md` for exact input fields and commands. `artifacts/csiro_s1_verifier.metrics.json` is the machine-readable training report.

## Dataset attribution

CSIRO Sentinel-1 SAR image dataset of oil- and non-oil features for machine learning: Blondeau-Patissier, D., Schroeder, T., Diakogiannis, F., & Li, Z. (2022), DOI 10.25919/4V55-DN16. Licence: CC BY-SA 4.0.

The raw downloaded images are intentionally not included in the handoff ZIP. They are separately documented in `data/DATASET_NOTICE.md` and should be downloaded by a team member only if the licence terms are understood and retained.
