# Project Context Handoff — Satellite Oil-Spill Detection, Drift Hindcasting, and Vessel Attribution

**Purpose:** Portable project memory and technical handoff. It consolidates the supplied project brief, three supplied integrated technical reports, and externally verified context consulted on 25 August 2026. No system has been built from this document.

## 1. One-sentence problem statement

Given satellite imagery of a possible marine oil slick, detect and georeference the slick; use ocean physics to estimate where and when it likely originated and where it may drift; then use historical AIS vessel traffic to rank possible responsible vessels, with evidence and uncertainty shown on a map dashboard.

## 2. Required product outcomes

1. **Oil-slick detection and characterisation** from satellite imagery, preferably Sentinel-1 SAR: location, boundary/mask, shape, area, timestamp, confidence, and (only if defensible) age.
2. **Drift forecast and hindcast:** use winds, surface currents, tides, waves and oil properties to forecast movement and infer a probable release area/time window.
3. **Vessel attribution:** reconstruct AIS traffic around the inferred source window; filter irrelevant traffic; rank candidates rather than declare guilt.
4. **Map-first dashboard:** show SAR observation, slick polygon, backward/forward ensemble corridor, data-quality flags, vessel tracks, candidate scores, and explanations.

The correct framing is an **evidence-support and triage system**, not an automatic legal-proof or blame-assignment system.

## 3. Core end-to-end logic

```text
Sentinel-1 SAR (+ metadata) ──> potential-slick detection + segmentation
                                     │
                    wind / wave / incidence-angle quality flags
                                     │
                    georeferenced slick polygon + confidence
                                     │
INCOIS / oceanographic forcing ──> forward drift ensemble + iterative hindcast
                                     │
                 probable release distribution: place + time + uncertainty
                                     │
historic/live AIS ──> trajectory reconstruction + anomaly features + candidate filtering
                                     │
          ranked candidates + reasons + confidence limits ──> map dashboard
```

## 4. Detection layer: what is known

### Why SAR is the sensing backbone

- SAR is an active microwave sensor, so it operates day/night and is much less affected by cloud than optical imagery.
- Oil dampens short gravity/capillary waves, reducing SAR backscatter. A slick may therefore appear dark relative to surrounding water.
- Sentinel-1 SAR is the intended baseline. Keep available VV and VH polarizations and preserve acquisition geometry, especially incidence angle.

### Non-negotiable physical limitation

A dark SAR patch is **not definitive evidence of oil**. Low-wind areas, biogenic slicks/algal material, natural seeps, rain cells, internal waves/current-shear boundaries, wave shadows, sea ice/grease ice, and other phenomena can also be dark. SkyTruth/Cerulean explicitly states that SAR alone cannot definitively identify an oil slick; its detections are potential slicks, not proof. Source: https://skytruth.org/cerulean/methods

Therefore, system language should be **“potential oil slick,” “detection confidence,” “look-alike risk,”** and **“requires validation,”** not “confirmed spill.”

### Evidence from the supplied SAR report

The report `Base Papers/Oil_Spill_SAR_Deep_Learning_Integrated_Report.docx` consolidates five unique studies (seven uploads contained two duplicate pairs):

| Study | Main contribution | Takeaway for this project |
|---|---|---|
| Bianchi et al. (2020) | Large-scale OFCN/U-Net-style segmentation and slick characterisation | Segmentation can support area, morphology and visualization; whole-scene false positives remain important. |
| Shaban et al. (2021) | Patch screening followed by U-Net | Explicit imbalance handling improves precision; small/sparse slicks can be missed. |
| Huang et al. (2022) | Faster R-CNN full-image detection | Fast candidate detection is useful, but bounding boxes do not provide exact area/shape. |
| Zhang et al. (2024) | MobileNetV2 + scSE improved DeepLabV3+ | Lightweight attention-based segmentation can outperform a much larger backbone in noisy SAR. |
| Zakzouk et al. (2025) | Regional DeepLabv3+ training near the Suez Canal | Local training data can materially improve local footprint accuracy, but may transfer poorly elsewhere. |

### Important operating conditions

- **Moderate wind is generally best** for oil–water contrast. One supplied study reported useful performance around 3–10 m/s and its best precision around 7–8 m/s.
- **Very low wind:** smooth water itself becomes dark, increasing look-alike risk.
- **High wind / rough sea:** oil signatures can break up or be masked, causing false negatives. This is particularly important for Indian monsoon conditions.
- **Incidence angle, speckle/noise, spill size, narrowness, distance to coast, and sensor geometry** affect reliability.
- Sentinel-1's approximate 10–20 m-scale imagery can miss very small, thin, or early leaks. Do not promise first-hour detection.
- SAR footprint does **not** directly estimate thickness, volume, or chemical composition.

### Recommended detection design

1. Preprocess with orbit/radiometric/geometric correction, land masking, robust speckle reduction, normalization, and preservation of georeferencing.
2. Use a coarse candidate detector or patch-screening stage to reduce extreme background imbalance.
3. Use dense segmentation for the slick boundary and area.
4. Train a second stage or multiclass classifier to discriminate oil from look-alikes using SAR texture, geometry, polarization/context, and environmental metadata. This is a valuable colleague suggestion and directly addresses the main failure mode.
5. Fuse wind, sea state and incidence angle as model inputs and/or quality controls. Mark near-zero-wind or rough-sea observations as high uncertainty rather than silently treating them normally.
6. Produce calibrated confidence, look-alike risk, and data-quality flags. Confidence must be calibrated against held-out data; it should not be treated as proof.
7. Prefer local/regional fine-tuning for the intended Indian operating zones, using geographically separated event/scene test splits to avoid leakage.

### Meaningful evaluation metrics

- Segmentation: Dice/F1, IoU/mIoU, precision, recall, area error in km².
- Detection: average precision, recall, false positives per scene, confidence calibration.
- Stratify all metrics by wind regime, incidence angle, spill area/narrowness, coast distance, and geographic region.
- Pixel accuracy alone is misleading because oil pixels are rare.

## 5. Drift, forecast, and source-hindcasting layer

### Governing principle

Source localization is an **ensemble inverse problem around a credible forward physical model**. Do not simply run oil motion backward. Oil can weather, evaporate, disperse, strand, and otherwise change state in ways that make naïve reverse-time physics unreliable.

### Supplied trajectory report: key findings

The report `Base Papers/Integrated_Report_Oil_Spill_Trajectory_and_Backtracking.docx` combines:

- **BAKTRAK** (Breivik et al.): preserve a forward trajectory model, seed many possible release locations/times, run forward, retain candidates that approach the observed target, resample near the best candidates, and repeat.
- **High-resolution-current oil trajectory study** (Prasad et al.): NOAA GNOME simulations of the 2011 MV Rak spill near Mumbai; a 1/48° (~2.25 km) HOOFS current field performed materially better than the coarser 1/8° INDOFOS field for the study cases.

### BAKTRAK-style approach

- Start from observed slick geometry/time as a target area, not a single point.
- Seed a broad spatial and release-time ensemble (the paper used order-of-5,000 particles in examples).
- Run a forward trajectory/oil-fate model for every candidate.
- Score candidates by final mismatch to the observed target. BAKTRAK uses a relative-distance term, beta = D1/D0, so older/farther candidates are not unfairly penalized merely for starting farther away.
- Select promising candidates, perturb/resample them in location and release time, and iterate.
- Return a spatial/time probability distribution and trajectory corridor, not one exact origin coordinate.

### Why forcing quality is central

In the MV Rak case, switching current forcing changed predicted direction and beaching pattern. The report records HOOFS as 31% better than INDOFOS in that case and 61% better in a second pipeline-rupture case. These percentages are case-specific, not universal performance guarantees.

Required forcing/data categories:

- surface currents (high resolution near coasts where possible),
- winds,
- tides,
- wave/sea-state information,
- shoreline/coastal geometry,
- oil type, quantity, release duration, windage and weathering assumptions.

### India-specific data opportunity

INCOIS exposes forecasts/data for wind, significant wave height, wave direction/period, and currents; this makes it a strong candidate source for quality flags and drift forcing, subject to access, resolution, latency and licensing checks. Sources: https://incois.gov.in/oceanservices/LSF/index.html and https://incois.gov.in/site/dataholdings.jsp

Use this colleague suggestion: during high waves/monsoon conditions, show a **low-reliability / possible false-negative** flag. This is operationally more honest and useful than a silent no-detection.

### Hindcast outputs

- probable release-density map;
- earliest / most likely / latest release-time distribution;
- forward and backward ensemble corridor;
- predicted beaching-risk sectors;
- fit to SAR polygons and independent observations;
- uncertainty/skill scores, forcing versions and model assumptions.

### Key limitations

- A converged ensemble is not necessarily correct if current/wind forcing is biased.
- Open-ocean hindcasting is less constrained than nearshore hindcasting.
- High-resolution currents help but do not eliminate errors from atmospheric boundary forcing, river discharge/freshwater effects, limited SAR revisits, or uncertain oil properties.
- Validate against independent SAR passes, field/Coast Guard observations, tide gauges/ADCPs where possible, and historical spills with known sources.

## 6. AIS and vessel-attribution layer

### AIS is evidence, not truth

AIS may be delayed, missing, malformed, duplicated, voluntarily disabled, spoofed, or contain incorrect static vessel data. A visible track is not guilt; no nearby track is not proof that no vessel was involved.

Marine Cadastre provides useful sample AIS data and fields such as MMSI, timestamp, latitude/longitude, speed over ground, course/heading, vessel type, IMO, dimensions, draft and status. It is primarily U.S. data; synthetic AIS is permitted by the project brief for a demonstration region when suitable real data is unavailable. Sources: https://marinecadastre.gov/accessais/ and https://www.fisheries.noaa.gov/inport/item/67336

### Supplied AIS report: key findings

The report `Base Papers/AIS Maritime Surveillance Report.docx` consolidates two studies:

1. **Local dark-activity detection:** A nearby receiver predicts a vessel's next position from prior AIS signals and checks whether it should still be in reception range. Missing in-range transmission becomes a *possible* dark-activity alert, not a conclusion. In its simulated Marmara Sea experiment, rule-based R-DAD reported 0.892 accuracy and the best ML method (AdaBoost Random Forest) reported 0.961.
2. **Spaceborne-AIS behavioural classification:** A year of HY-1C/HY-2B AIS data (~62 million messages after preprocessing) was used to classify cargo, tanker, fishing, passenger and tug vessels. Random Forest accuracy rose from 73.10% using six geometry features to 92.70% with a combined 13-feature geometry-plus-behaviour vector. Behavioural/type inconsistencies can flag possible AIS misrepresentation.

### Candidate-ranking logic

Start from the hindcast release distribution, not merely the present slick location. For each candidate vessel, compute and expose:

- spatial and temporal proximity to plausible release location/time;
- trajectory compatibility with source/hindcast geometry;
- heading/speed/course continuity and manoeuvres;
- vessel class, dimensions, draft/cargo-related context when available;
- historical behavioural profile and route deviation;
- AIS quality, gaps, unexplained disappearance, or identity/type inconsistency;
- alternative explanations and all score components.

Return **ranked potential sources** with reasons, not “culprit vessel.” A human investigator must review the evidence.

### Important added requirements from colleague notes

- **AIS latency is real:** SkyTruth reports that its AIS provider can be about 72 hours behind transmission, so immediate source association may be impossible using that feed. Source: https://skytruth.org/blog/near-real-time-coming-to-cerulean and https://skytruth.org/faq
- Include a **provisional attribution** mode: use available recent/last-known tracks and clearly label the result provisional; update/re-rank as backfill arrives.
- Prioritize a lawful, licensed streaming/live AIS source for high-traffic Indian demonstration corridors if one is available. Do not assume a self-hosted receiver alone provides ocean-wide coverage.
- Treat a missing AIS match as an **investigative state**, not a failure. Specifically surface vessels with relevant historical gaps/disappearances near the inferred source window. This is useful but must account for coverage and reception limits to avoid false accusations.
- In crowded lanes, proximity alone is weak. Combine trajectory, timing, vessel-type prior, behavior and AIS continuity. Vessel type/risk weighting should be explicit, defensible, and calibrated to the target region—not an opaque or discriminatory prior.

## 7. Dashboard / user-experience requirements

The interface should be map-led and explainable:

- SAR scene and detected potential-slick polygon, timestamp, area and confidence;
- data-quality flags: low wind/look-alike risk, rough sea/false-negative risk, incidence-angle risk, small-slick sensitivity;
- forward and hindcast ensemble corridors, release-density region/time window, current/wind layers;
- AIS tracks over the relevant window, including gaps;
- ranked candidate list with numeric score *and component explanations*;
- distinction between confirmed observations, model output, missing data and assumptions;
- buttons/filters for confidence, time, vessel class and environmental scenario;
- investigation status: `potential slick`, `requires validation`, `provisional attribution`, `AIS pending`, `no attributable AIS candidate`, etc.

### Human-in-the-loop operational reality

Even highly operational systems do not make autonomous enforcement conclusions. EMSA's CleanSeaNet sends a possible-spill alert to the relevant coastal state within roughly 20 minutes of satellite acquisition, but trained operators assess imagery with supporting meteorological, oceanographic and AIS information, and authorities validate detections through their own follow-up, potentially including a patrol aircraft or vessel. Sources: https://www.emsa.europa.eu/csn-menu.html and https://emsa.europa.eu/about/financial-regulations/download/6453/4322/23.html

**Design implication:** automate prioritisation, evidence assembly and explanation—not legal determination. The dashboard should rank alerts by calibrated confidence and operational impact so analysts can focus first on the highest-value alerts, while every case remains reviewable and auditable.

## 8. What super-resolution does and does not contribute

The original project notes included super-resolution (SR). It is **optional**, not a core deliverable.

- SR can improve visual readability, edge appearance and sometimes downstream ML performance.
- SR reconstructs/invents plausible pixels; it does not reveal unobserved physical evidence, change the original ground sampling distance, prove a spill, recover oil thickness, or make a weak AIS attribution reliable.
- It should not be used as evidence for legal attribution. If demonstrated at all, label it as visualization/experimental enhancement and keep inference based on native calibrated/georeferenced SAR data.

## 9. Recommended staged scope for a prototype

### Minimum viable demonstration

1. One chosen area and a small set of SAR scenes.
2. Potential-slick segmentation from Sentinel-1 SAR with a mask, polygon, area and calibrated/illustrative confidence.
3. Simple current/wind-driven hindcast with clearly stated assumptions and an uncertainty corridor.
4. Historical or synthetic AIS for the same area/time.
5. Ranked candidates using proximity, time, track consistency and one or two behavioural/AIS-gap features.
6. Map dashboard that makes uncertainty visible.

### Strong differentiators after the baseline

- local Indian fine-tuning and Indian oceanographic forcing;
- explicit look-alike and weather blind-spot flags;
- calibrated slick confidence;
- ensemble rather than single-line hindcast;
- provisional attribution before delayed AIS backfill;
- dark-activity / AIS-gap evidence with coverage-aware safeguards;
- explainable score decomposition and human-review workflow.

### Future / validate-before-claiming ideas

- higher-resolution imagery/tasking for priority zones may complement Sentinel-1, but availability, licensing, latency and suitability (including any RISAT option) need verification before inclusion in the architecture;
- optical/thermal/multispectral fusion can help look-alike discrimination when temporally aligned, but clouds and revisit limits remain;
- full oil thickness/volume estimation requires additional science/data and should not be promised from SAR footprint alone.

## 10. Evaluation plan

### Detection

- Event/scene-level geographic holdout splits.
- Dice/F1, IoU, precision, recall, false positives per scene, area error and confidence calibration.
- Break results down by weather, wind, sea state, incidence angle, size/shape, coast distance and location.

### Drift and hindcast

- Distance/RMSE to observed slick trajectory.
- Directional error.
- Beaching-sector hit/miss and distance to observed beaching.
- Source-location and release-time error for known events.
- Coverage of true source by 50/80/95% credible regions.
- Sensitivity to current/wind ensemble members and oil assumptions.

### Attribution

- Use historical, independently investigated incidents or transparent synthetic scenarios.
- Measure whether the actual/simulated source ranks in top-k; do not use only aggregate classification accuracy.
- Evaluate score calibration and false-positive burden in dense shipping lanes.
- Test AIS gaps with realistic coverage loss, delayed data and vessel manoeuvres so “dark activity” is not overclaimed.

## 11. Risks and guardrails

| Risk | Required guardrail |
|---|---|
| SAR look-alikes | Potential-slick language, secondary discrimination, weather/context data, human validation. |
| Rough seas / monsoon false negatives | Visible low-reliability flag; do not interpret no detection as no spill. |
| Small early spills missed | State resolution/revisit limitation; avoid “real-time complete coverage” claims. |
| Physics-model error | Ensemble forcing and parameters; validate against independent observations. |
| AIS delay/unavailability | Provisional mode and update trail; clearly show data freshness. |
| AIS gaps/spoofing | Coverage-aware anomaly logic; rank evidence, do not accuse. |
| Dense vessel traffic | Multi-factor scoring and score explanations, not nearest-vessel attribution. |
| Legal/ethical harm | Human review, audit log, confidence/uncertainty display, no definitive blame language. |
| Super-resolution hallucination | Keep SR separate from evidentiary analytical input. |

## 12. Data and source register

### Provided in workspace

- `Project Context.txt` — original challenge statement and deliverables.
- `Base Papers/Oil_Spill_SAR_Deep_Learning_Integrated_Report.docx` — integrated review of five unique SAR oil-spill ML studies.
- `Base Papers/Integrated_Report_Oil_Spill_Trajectory_and_Backtracking.docx` — BAKTRAK and high-resolution ocean-current/GNOME synthesis.
- `Base Papers/AIS Maritime Surveillance Report.docx` — dark AIS activity, vessel classification and anomaly-detection synthesis.

### External sources checked

- Sentinel-1 SAR oil-spill dataset, including two-polarization Sigma0 images and masks: https://zenodo.org/records/8346860
- CSIRO Sentinel-1 oil/no-oil SAR chip dataset (5,630 originally published chips; CC BY-SA 4.0): https://data.csiro.au/collection/csiro:57430
- NOAA/Marine Cadastre AIS data/metadata: https://marinecadastre.gov/accessais/ and https://www.fisheries.noaa.gov/inport/item/67336
- SkyTruth Cerulean methods and SAR limitation: https://skytruth.org/cerulean/methods
- SkyTruth FAQ on AIS delay/attribution limits: https://skytruth.org/faq
- SkyTruth near-real-time Cerulean/AIS-delay explanation: https://skytruth.org/blog/near-real-time-coming-to-cerulean
- INCOIS location-specific ocean forecast: https://incois.gov.in/oceanservices/LSF/index.html
- INCOIS data holdings: https://incois.gov.in/site/dataholdings.jsp

## 13. Final positioning statement

This project should be presented as an **India-adaptable, physics-informed and uncertainty-aware maritime investigation platform**. Its value is not claiming certainty from an inherently uncertain SAR/AIS pipeline. Its value is reducing the time needed to turn a possible slick into an auditable investigation: identify it, explain observation quality, model plausible origin scenarios, focus the AIS search, rank evidence-backed candidates, and keep a human decision-maker in control.

It's not actually automated end-to-end anywhere that matters. EMSA's CleanSeaNet — the most operationally serious system that exists — still requires a human analyst in the loop: < cite index="25-1">an alert goes to the coastal state within 20 minutes of image acquisition,</cite> but that's a flag for a human to review, not an autonomous conclusion, and confirmation still needs a patrol vessel or aircraft sent out physically.
→ Your fix: you're not going to remove humans from a legal/enforcement chain either (nor should you claim to) — but you can shrink the human bottleneck by pre-ranking alerts by confidence so analysts triage the top 10% instead of reviewing everything equally.
