# Phase 8: Intelligence, False-Positive Mitigation and Explainable Attribution

**Status**: Implemented
**Date**: August 2026

## Overview

Phase 8 adds intelligence layers to reduce false positives and provide transparent, explainable attribution for oil spill detections. Every confidence score has a traceable breakdown.

## Architecture

```
Detection → LookAlikeClassifier → EnvironmentalReliability → SmallDetectionAssessor
         → ConfidenceCalibrator → SeasonalPrior → ExplainableAttribution
         → AISGapDetector → StaticSpacingDetector
```

## Components

### 1. Look-Alike Classification (`look_alike_classifier.py`)

Distinguishes true oil spills from natural SAR look-alikes:
- **Biogenic surface slicks** (natural surfactants)
- **Low-wind areas** (reduced backscatter)
- **Current shear zones**
- **Rain cells** (volume scattering)
- **Natural wind shadows** near coastlines

**Features extracted:**
- Intensity anomaly (mean, std, min dB)
- Texture (local contrast, edge density)
- Shape (aspect ratio, elongation, compactness)
- Context (distance to coast, shipping lanes, water depth)
- Wind conditions
- SAR imaging geometry

**Output:** P(look-alike) ∈ [0, 1]

### 2. Environmental Reliability (`environmental_reliability.py`)

Assesses detection reliability based on wind/wave conditions:

| Band | Wind (knots) | Penalty | Notes |
|------|-------------|---------|-------|
| IDEAL | 6-20 | 0.0 | Oil spills produce strong damping |
| GOOD | 4-6 or 20-25 | 0.05 | Slightly outside ideal |
| MARGINAL | 2-4 or 25-30 | 0.15 | Degraded detectability |
| POOR | < 2 or > 30 | 0.30 | Very poor reliability |

### 3. Confidence Calibration (`confidence_calibrator.py`)

Platt scaling converts raw model scores to calibrated probabilities:
- P(y=1|s) = 1 / (1 + exp(-(A*s + B)))
- Parameters A, B fitted on labeled validation data
- Identity mapping when not fitted

### 4. AIS Gap Detection (`ais_gap_detector.py`)

Detects suspicious AIS transmission patterns:
- **Temporal gaps**: Periods where AIS stops, then resumes
- **Sentinel values**: lat/lon = 91.0 (transponder manipulation indicator)
- **Static spacing**: Suspiciously regular intervals (spoofing indicator)

### 5. Small Detection Assessment (`small_detection_assessor.py`)

Evaluates reliability of small-area detections:

| Risk | Area (km²) | Pixels | Action |
|------|-----------|--------|--------|
| HIGH | < 0.005 | < 50 | Manual review required |
| MEDIUM | 0.005-0.05 | 50-500 | Cross-reference with AIS |
| LOW | > 0.05 | > 500 | Standard processing |

### 6. Explainable Attribution (`explainable_attribution.py`)

Combines all components into transparent confidence breakdown:

```
adjusted_confidence = raw_confidence
    - look_alike_penalty
    - environmental_penalty
    - small_detection_penalty
    + calibration_shift
    + seasonal_prior_adjustment
```

### 7. Seasonal Prior (`seasonal_prior.py`)

Time-of-year adjustment for Indian maritime region:
- Monsoon (Jun-Sep): +0.05 (higher activity)
- Winter (Dec-Feb): -0.05 (lower activity)

### 8. False Positive Review (`false_positive_review.py`)

Tracks review status for flagged detections:
- pending → confirmed_true_oil / confirmed_false_positive / uncertain

## API Changes

### Attribution Response (enhanced)

```json
{
  "incidentId": "INC-001",
  "confidenceBreakdown": {
    "rawModelConfidence": 0.75,
    "lookLikePenalty": 0.02,
    "environmentalPenalty": 0.0,
    "smallDetectionPenalty": 0.0,
    "calibrationShift": 0.0,
    "seasonalPriorAdjustment": 0.03,
    "adjustedConfidence": 0.76,
    "confidenceBand": "MEDIUM",
    "explanations": {
      "lookLike": "Look-alike probability: 5.2%...",
      "environmental": "Ideal conditions...",
      "smallDetection": "Above threshold..."
    }
  },
  "smallDetection": null,
  "environmentalBand": "IDEAL",
  "candidates": [{
    "gapSignals": [...],
    "staticSpacing": null
  }]
}
```

## Files Created

- `backend/app/domain/entities.py` — LookAlikeFeatures, ConfidenceBreakdown, AISGapSignal, StaticSpacingDetection, SmallDetectionAssessment, FalsePositiveReview
- `backend/app/services/look_alike_classifier.py` — LookAlikeClassifier + extract_look_alike_features
- `backend/app/services/environmental_reliability.py` — EnvironmentalReliability
- `backend/app/services/confidence_calibrator.py` — ConfidenceCalibrator
- `backend/app/services/ais_gap_detector.py` — AISGapDetector + StaticSpacingDetector
- `backend/app/services/small_detection_assessor.py` — SmallDetectionAssessor
- `backend/app/services/explainable_attribution.py` — ExplainableAttribution
- `backend/app/services/seasonal_prior.py` — SeasonalPriorService
- `backend/app/services/false_positive_review.py` — FalsePositiveReviewManager
- `backend/tests/test_phase8_intelligence.py` — 41 tests
- `docs/phase8-intelligence-attribution.md` — This file

## Test Results

41 new tests covering all components:
- LookAlikeClassifier: 5 tests
- EnvironmentalReliability: 5 tests
- ConfidenceCalibrator: 5 tests
- AISGapDetector: 4 tests
- StaticSpacingDetector: 3 tests
- SmallDetectionAssessor: 4 tests
- ExplainableAttribution: 4 tests
- SeasonalPriorService: 4 tests
- FalsePositiveReviewManager: 4 tests
- Feature extraction: 3 tests

Total: 277 tests passing (41 new + 236 existing)
