# V3 Steps 5–7 Report: Hemispheric Networks, Differences, Relational Abnormality

**Date:** 2026-11-06. **Branch:** `fix/flowchart-pipeline`. **Status:** computed and integrity-checked, label-free. **Open issue (section 5):** the unsigned asymmetry measures are of the size expected from estimation noise, so a noise-floor check is recommended before freezing.

**Run (Kaggle):** commit `9916056` (clean), Python 3.13. One notebook ran Step 4, then Steps 5–6, then Step 7; Steps 5–7 took about 8 s in total. Input was the saved notebook `brain-stroke-v3-step2-final`. **Step 4 was re-run and reproduced the earlier Step 4 tables byte for byte** (`connectivity_core_v3.csv`, `connectivity_ext_v3.csv`). The config hashes (`graph.json`, `abnormality.json`) equal the committed files.
**Tests:** **66 passed in 21.24 s** (`pytest tests/test_*_v3.py` in the same Kaggle notebook at commit `9916056`, before the pipeline run; output pasted by the user). This covers all v3 test files, including the new `test_connectivity_v3.py` (7) and `test_graph_v3.py` (8):
- **Step 5–6 checks:** a symmetric graph gives zeros; a 2:1 asymmetry gives exactly 1/3 in every measure; masking is symmetric; clipping is counted correctly; the lesion sign is correct; an end-to-end Steps 5 → 7 run.
- **Step 4 checks:** segment split, derangement, edge rules, wPLI on lagged vs independent signals, and surrogate exceedance.
- **Earlier checks:** this was also the first execution of the Step 3b tests that were written without running.
**Label blindness:** no outcome column read. Lesion side is read once (`graph_v3.lesion_signs`), only to set the IC sign.

## Step 5: hemispheric graphs, pairing, masking, deformation

| Item | Result |
|---|---|
| Graphs | Left graph and mirror-aligned right graph (pair order) per subject × band. **Core** (primary): 4 nodes per side, 6 intra edges, 4 homotopic. **Extended** (secondary): 11 nodes, 55 intra edges, 11 homotopic |
| Clipping (negative wPLI → 0) | Median fraction of available intra and homotopic values clipped: core 0.19 in every band; extended 0.18 / 0.25 / 0.23 / 0.18 (delta / theta / alpha / beta). Maximum per subject 0.39–0.69 |
| Frames | L/R for all **45**; lesion-aligned I/C for **38** (uncertain side: sub-03, 20, 21, 33, 35, 38, 48) |

**Symmetric masking (D17)**: a pair is dropped from both hemispheres if unavailable; a mirrored edge missing in either hemisphere is masked in both. No imputation.

| | Core | Extended |
|---|---|---|
| Pairs dropped (both hemispheres) | sub-13 O1O2, sub-31 C3C4 | sub-13 O1O2, sub-29 T7T8, sub-30 T7T8, sub-31 C3C4 |
| Mirrored edges masked (both hemispheres, same in every band) | sub-32: 1, sub-38: 1 | sub-08, 12, 19, 24, 28, 32: 1 each; sub-38: 3 |
| Subjects using ≥ 1 edge with one interpolated endpoint (flagged for Step 8) | 10 (48 edge-uses) | 26 (451) |

Every other subject keeps all pairs and edges. In the node table, NaN appears only for the dropped pairs (sub-13 and sub-31: 24 columns each; sub-29 and sub-30: 12 each).

**Deformation, label-free descriptive, median [min–max] over 45 subjects:**

| Set | Band | Normalized Frobenius | Laplacian spectral distance | \|signed mean-weight diff\| | Mean homotopic weight |
|---|---|---|---|---|---|
| Core | delta | 0.54 [0.11–0.93] | 0.32 | 0.30 | 0.065 |
| | theta | 0.59 [0.16–1.00] | 0.26 | 0.26 | 0.037 |
| | alpha | 0.57 [0.27–0.90] | 0.34 | 0.33 | 0.037 |
| | beta | 0.58 [0.22–1.00] | 0.36 | 0.41 | 0.014 |
| Extended | delta | 0.54 [0.35–0.83] | 0.24 | 0.23 | 0.073 |
| | theta | 0.58 [0.35–0.86] | 0.23 | 0.20 | 0.031 |
| | alpha | 0.56 [0.30–0.69] | 0.30 | 0.27 | 0.034 |
| | beta | 0.56 [0.31–0.88] | 0.25 | 0.19 | 0.014 |

Normalized Frobenius and Laplacian distance are frame-invariant (identical in L/R and I/C). The signed mean-weight difference is stored as LR, abs and IC.

## Step 6: node, edge, network and region measures

| Table | Shape | Content |
|---|---|---|
| `graph_node_v3.csv` | 45 × 540 | per set × band × homologous pair: strength, weighted local efficiency (Rubinov–Sporns), weighted clustering (Onnela), each as (I−C)/(I+C) in kinds LR / abs / IC |
| `graph_edge_v3.csv` | 45 × 792 | per set × band: every mirrored intra-hemispheric edge difference (diffLR, abs, diffIC; clipped weights) + clipped homotopic weights |
| `graph_network_v3.csv` | 45 × 168 | global efficiency, mean clustering, mean strength (per hemisphere L, R and asymmetry LR / abs / IC) + Frobenius, Laplacian distance, mean-weight difference, homotopic mean |
| `graph_region_v3.csv` | 45 × 200 | extended-set regions fixed in config (frontal F3F4/F7F8; central FC3FC4/C3C4; temporal FT7FT8/T7T8/TP7TP8; parietal CP3CP4/P3P4/P7P8; occipital O1O2): mean node differences (LR, abs, IC) + mean homotopic weight |

All tables: `subject_id` + features only; sidecar column lists and table sha256 verified; all non-NaN values finite; the IC columns are NaN exactly for the 7 uncertain-side subjects. Zero rule: 106 of 5,400 node clustering / local-efficiency cells equal exactly 0, where both hemispheres have equal values (typically both 0).

Global efficiency, median L / R: core 0.35–0.42 / 0.34–0.42 per band; extended 0.20–0.30 / 0.24–0.30.

## Step 7: relational abnormality representation

`relational_abnormality_v3.csv`, 45 × 195:
- `rel_IC_*` (88): the core ipsilesional − contralesional vector. Node 48 (4 bands × 4 pairs × 3 metrics), edge 24 (4 × 6), network 16 (4 × 4: global efficiency, mean clustering, mean strength, mean-weight difference). NaN for the 7 uncertain-side subjects.
- `rel_abs_*` (88): the matching absolute differences, for all 45. 56 NaN cells, all from the dropped or masked core pairs and edges of sub-13, sub-31, sub-32 and sub-38.
- Summaries (19): `mean_abs_node`, `mean_abs_edge`, `mean_abs_network` (overall and per band), `ext_mean_abs_*` (secondary set) and `overall_magnitude_unscaled` (descriptive only; the registered z-scored magnitude is computed inside CV in Step 8).

| Summary | Median [min–max] |
|---|---|
| mean_abs_node | 0.524 [0.261–0.857] |
| mean_abs_edge | 0.052 [0.016–0.142] (raw weight units) |
| mean_abs_network | 0.411 [0.146–0.718] |
| ext_mean_abs_node / edge / network | 0.406 / 0.063 / 0.249 |
| overall_magnitude_unscaled | 0.329 [0.154–0.549] |

Segment-count Spearman (label-free) of the summaries: overall summaries |ρ| ≤ 0.23. Per band: `mean_abs_node_delta` +0.45, `mean_abs_network_delta` +0.38, `mean_abs_edge_alpha` −0.36; the others are below 0.3.

## 5. Open issue: unsigned measures and the noise floor

The unsigned measures (normalized Frobenius, Laplacian distance, |node/edge/network differences|, and therefore every Step 7 `mean_abs_*` summary) are **large**: median Frobenius about 0.55, mean |node difference| about 0.52 on a −1 to 1 scale. They are also **of the size expected from estimation noise**:
- **Edges are near the noise floor.** Step 4 found that single edges often sit at the surrogate floor (median wPLI about 0.01–0.07, 30–50% of homotopic values above their own floor), and about 20% of values are clipped to 0.
- **Noise pushes unsigned measures up.** For two graphs whose weights are independent noise with equal mean and standard deviation, normalized Frobenius is about 0.5 (rough analytic approximation, not a simulation of these data). That is close to the observed 0.54–0.59. A normalized node difference of small, noisy, partly zero quantities likewise spreads towards ±1.
- **Same pattern as Step 3.** This is the pdBSI problem again: |·| of a noisy difference has a positive noise floor. **Signed measures (LR, IC) are not biased by noise** (expected value 0 under symmetric noise); unsigned ones are.

**Consequence:** as computed, the unsigned summaries (and so the planned "relational abnormality summary scalar" test V3) may mostly measure estimation noise rather than hemispheric deformation. The data cannot show otherwise yet.

**Proposed label-free fix (not done; your decision, pre-freeze):** a per-subject **split-half noise floor**.
1. Recompute Step 4 connectivity on two random halves of each subject's segments (fixed seed, several splits).
2. Compute every unsigned measure between the **same** hemisphere in the two halves (for example L_half1 vs L_half2). That is the deformation produced by estimation noise alone.
3. Report observed L-vs-R deformation against this floor per subject. Optionally define floor-corrected magnitudes (observed minus within-hemisphere floor) as the Step 7 summaries, using the same principle as the 3b fix.

This needs the epoch files (Kaggle, a few minutes) and no labels.

## 6. Deviations and limitations

- **D17:** symmetric masking; zero rule; shared-scale weights; IC by sign; IC columns NaN for uncertain side; overall magnitude z-scoring deferred to Step 8 (`V3_HANDOFF_DEVIATIONS.md`).
- **L15 (new): noise floor of unsigned measures, section 5.** **Update:** addressed by the Step 7b cross-half estimator (D18, `src/crosshalf_v3.py`). The unsigned columns of `graph_*_v3.csv` (abs, Frobenius, Laplacian distance) and the Step 7 `mean_abs_*` / `overall_magnitude_unscaled` summaries are now labelled **noise-inflated, descriptive only**, and are kept unchanged for comparison. Signed LR/IC columns are unaffected.
- **L16:** core graphs are small (4 nodes, 6 edges). Node clustering and local efficiency rest on 3 edges per neighbourhood and are volatile, especially after clipping.
- Carried over: L4 (dropped pairs), L9 (one-interpolated endpoints, flagged), L13 (edge-level noise), L14 (delta segment-count dependence), L7 (Kaggle environment).
- Outputs live in the Kaggle zip (`v3_outputs_small (4).zip`); feature CSVs are committed only at the Step 8 freeze.
