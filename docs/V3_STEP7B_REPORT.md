# V3 Step 7b Report: Cross-Half Deformation Estimator (D18)

**Date:** 2026-11-06. **Branch:** `fix/flowchart-pipeline`. **Status:** DONE, label-free, pre-freeze. This resolves L15 (noise-inflated unsigned measures, `V3_STEP5_7_REPORT.md` section 5).

**Run:** Kaggle, commit `a8acc35` (clean), Python 3.13, 4 workers: **45/45 subjects in 110 s** (8.1 s median per subject), with no non-finite half values. The input was the saved notebook `brain-stroke-v3-step2-final` (epochs, epoch_qc, subject_meta), and the config hash equals the committed `configs/v3/crosshalf.json`.
**Tests:** `pytest tests/test_*_v3.py` in the same notebook at `a8acc35`: **72 passed** in 31.45 s (pasted by the user). The 32 warnings were the expected undefined Spearman on the 2-subject end-to-end test.
- The 6 new tests cover: stratified, seeded split; **symmetric noise gives a mean D2 near 0** while the naive estimate is near the noise variance; a **0.1 asymmetry is recovered** (D2_edge ≈ 0.01, D2_node ≈ 0.09); frame invariance; lesion frames; an end-to-end run.
- First attempt: it failed in 1.9 s because the Step 2 notebook was not attached when the setup cell ran (empty `--prev-root`). It ran unchanged once the input was attached.
**Label blindness:** no outcome column read. Lesion side is read once (`graph_v3.lesion_signs`), only for the IC sign of the signed columns.

## 1. Method

- Per subject: **10 splits** of the clean 4 s **epochs** (not segments) into two equal, class-stratified halves (seed 2000 + subject index). There are **12–20 epochs per half** (median 18), i.e. 24–40 segments.
- In each half, Step 4 connectivity is recomputed unchanged (wpli2_debiased, multitaper, same bands and edge rules). Steps 5–6 symmetric masking (computed once from the full data, shared by both halves) and clipping at 0 are applied.
- **D2 = mean over mirrored intra-hemispheric edges of (L1 − R1)(L2 − R2)** on raw clipped weights. Likewise for node strength (mean over kept nodes) and 4 network summaries on raw weights (mean weight, mean strength, global efficiency, mean clustering). Values are averaged over the 10 splits.
- Halves are independent, so the expected D2 is the squared true difference with **no noise term**. D2 can be negative; it is not truncated. This is not observed-minus-floor.
- **D2 is frame-invariant:** (I1−C1)(I2−C2) = (L1−R1)(L2−R2). One value serves the L/R frame (45) and the I/C frame (38). The direction is given by the signed cross-half network differences `_LR` (45) and `_IC` (38).
- Full-data squares are kept as `naive_noiseinflated_*`, descriptive only.

**Output:** `features/v3/abnormality_crosshalf_v3.csv`, 45 × 162, with sidecar (columns and table sha256 verified). 224 NaN cells, exactly the 4 signed IC column groups × 2 sets × 4 bands for the 7 uncertain-side subjects. **D2 has no NaN**, including subjects with dropped pairs, because masking handles them.

## 2. D2 per band: edges and node strength

Under no true asymmetry, D2 scatters symmetrically around 0, so about **50%** of subjects would have D2 > 0.

| Set | Band | D2_edge median [q1, q3] | **share > 0** | naive median | cross/naive (median ratio) | D2_node **share > 0** |
|---|---|---|---|---|---|---|
| Core | delta | 2.4e-3 [−1.8e-4, 1.3e-2] | **0.71** | 9.5e-3 | 0.33 | 0.60 |
| | theta | 9.1e-4 [−1.6e-4, 2.1e-3] | **0.69** | 2.7e-3 | 0.29 | 0.62 |
| | alpha | 1.7e-3 [3.9e-4, 5.7e-3] | **0.82** | 6.5e-3 | 0.49 | 0.73 |
| | beta | 2.3e-4 [−2.0e-5, 9.8e-4] | **0.71** | 6.6e-4 | 0.33 | 0.67 |
| Extended | delta | 8.1e-3 [2.7e-3, 1.5e-2] | **0.96** | 1.6e-2 | 0.56 | 0.91 |
| | theta | 1.4e-3 [7.6e-4, 3.4e-3] | **0.96** | 4.4e-3 | 0.41 | 0.82 |
| | alpha | 2.8e-3 [8.6e-4, 1.2e-2] | **0.96** | 6.1e-3 | 0.43 | 0.87 |
| | beta | 7.7e-4 [2.9e-4, 1.7e-3] | **0.98** | 1.6e-3 | 0.53 | 0.84 |

Core, all bands averaged: `core_D2_edge_allbands` median 2.8e-3, > 0 in **89%** of subjects; `core_D2_node_allbands` median 7.5e-3, > 0 in **78%**.

## 3. Network-level summaries (D2, share > 0)

| Set | Band | mean weight | mean strength | global efficiency | mean clustering |
|---|---|---|---|---|---|
| Core | delta | 0.56 | 0.56 | 0.58 | 0.49 (median exactly 0) |
| | theta | 0.56 | 0.56 | 0.53 | 0.49 (median exactly 0) |
| | alpha | 0.64 | 0.64 | 0.62 | 0.60 |
| | beta | 0.69 | 0.69 | 0.67 | 0.62 |
| Extended | delta | 0.73 | 0.73 | 0.73 | 0.60 |
| | theta | 0.60 | 0.60 | 0.62 | 0.56 |
| | alpha | 0.64 | 0.64 | 0.60 | 0.67 |
| | beta | 0.60 | 0.60 | 0.56 | 0.62 |

The naive network-level squares are 2–25 times larger than the cross-half values.

## 4. Naive vs cross-half

- **Most of the naive asymmetry was noise.** The median cross/naive ratio is 0.26–0.62, so roughly 40–75% of each naive squared difference was estimation noise. The Step 7 unsigned summaries are therefore correctly labelled noise-inflated, descriptive only.
- **Subject ranking is largely preserved** for edges and nodes: Spearman(cross, naive) is 0.79–0.97 per set and band. Against the Step 7 summaries, `core_D2_edge_allbands` vs `mean_abs_edge` gives ρ = 0.85, but `core_D2_node_allbands` vs `mean_abs_node` only **0.41**, and vs `overall_magnitude_unscaled` 0.49. The Step 7 node and overall summaries ranked subjects quite differently from the noise-free estimate.

## 5. Interpretation (label-free)

1. **Hemispheric deformation beyond estimation noise is present in most subjects.** Edge-level D2 > 0 in 69–82% of subjects (core) and **96–98%** (extended), against about 50% expected with no true asymmetry. The extended set, with 55 edges per hemisphere, averages out more noise and gives the clearest evidence.
2. **Network-level summaries are weak.** Share > 0 is 0.49–0.73. Core mean clustering in delta and theta is indistinguishable from no asymmetry (median 0). Single scalar summaries of 4-node graphs carry little noise-free asymmetry; edge- and node-level D2 are the informative features.
3. **There is no consistent direction across subjects.** The signed IC mean-weight difference is near 0, with ipsilesional > contralesional in 45–61% of the 38 certain-side subjects per band. Deformation is present but its direction varies, so unsigned (D2) rather than signed features capture it. This is descriptive; no outcome was examined.

## 6. Segment-count dependence (label-free)

| | ρ (cross-half) | ρ (naive) |
|---|---|---|
| core_D2_edge_allbands / core_D2_node_allbands | −0.13 / −0.10 | — |
| core delta edge | −0.02 | −0.20 |
| **core alpha edge / node** | **−0.49 / −0.34** | −0.42 / −0.38 |
| extended delta edge / node | −0.28 / −0.21 | −0.31 / −0.29 |
| extended theta edge / node | +0.22 / +0.23 | +0.06 / −0.03 |
| other bands | \|ρ\| ≤ 0.25 | |

Cross-half estimation removes the noise-related part of the count dependence (for example core delta −0.20 → −0.02, and the all-band summaries are near 0). **Core alpha remains at −0.49.** Splitting cannot remove a recording-quality effect, so this is carried to Step 8 alongside DAR, DTABR, beta |AI| and delta connectivity.

## 7. Deviations, limitations, implications for Step 8

- **D18** (`V3_HANDOFF_DEVIATIONS.md`): the cross-half estimator; D2 frame-invariant; naive columns kept, labelled noise-inflated.
- **L15: resolved** for the deformation features. Use `abnormality_crosshalf_v3.csv` D2 columns; the Step 5–7 unsigned columns are descriptive only.
- **L17 (new):** D2 per subject is noisy. Halves hold only 12–20 epochs, and the core quartile ranges include negative values, so single-subject D2 has wide uncertainty, especially in the core set. Values are not truncated at 0, by design.
- **L18 (new):** network-level D2 (especially core mean clustering) is close to the null; Step 8 should prefer edge- and node-level D2.
- **L14 / L10 extended:** alpha D2 carries a recording-quality (segment-count) component.
- **Step 8 candidates (for your decision):** the original V3 ("relational abnormality summary scalar") would be better served by a cross-half summary such as `core_D2_edge_allbands` (or its extended equivalent) than by the noise-inflated Step 7 scalar. The choice and its pre-specified quality sensitivity analysis belong to the Step 8 registry approval.
