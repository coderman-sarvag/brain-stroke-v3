# V3 Step 4 Report: Functional Connectivity (wpli2_debiased)

**Date:** 2026-11-06. **Branch:** `fix/flowchart-pipeline`. **Status:** DONE.
- **Noise floor:** connectivity is above the surrogate floor for most subjects in every band, but individual edges are often at noise level.
- **Segment count:** the check fails for delta: delta connectivity correlates with the number of segments (carried to Step 8).

**Code / config:** `src/connectivity_v3.py`, `configs/v3/connectivity.json` (Kaggle provenance hash equals the committed file).
**Run:** Kaggle, commit `7f04d84` (clean), Python 3.13, 4 workers: **277 s for 45 subjects** (24 s median per subject), after a 2-subject smoke run (sub-01, sub-13) that passed. The input is the saved Step 2 notebook output; all 45 epoch files are sha256-recorded in the sidecars.
**Tests:** none run locally (user instruction); the smoke run and the integrity checks below are the evidence.
**Label blindness:** reads only `epoch_qc_v3.csv` and the epoch files.

## 1. Method

| Item | Setting |
|---|---|
| Segments | Each clean 4 s epoch → two non-overlapping 2 s segments; **all segments, both classes pooled** (D16). Per subject 48–80 segments, median 74 |
| Estimator | `mne_connectivity.spectral_connectivity_epochs(method="wpli2_debiased", mode="multitaper", faverage=True)`, 2 Hz bandwidth (3 tapers) |
| Bands | delta, theta, alpha, beta, half-open on the 0.5 Hz grid: **6 / 8 / 10 / 34 bins**. Delta below 2.5 Hz is under 5 cycles per segment (documented limitation) |
| Channel sets | Extended: the 22 analysed channels, **231 edges**. Core: F3/F4, C3/C4, P3/P4, O1/O2, **28 edges**, the same values (core equals the extended subset exactly, verified) |
| Missing | NaN when an endpoint is unavailable, an endpoint's homologous pair was interpolated on both sides (D14), or both endpoints were interpolated |
| Values | Raw (unclipped) in the tables; Step 5 clips negatives to 0 |

## 2. Outputs (Kaggle zip; not committed until the Step 8 freeze)

| File | Shape / content |
|---|---|
| `features/v3/connectivity_ext_v3.csv` + `.meta.json` | **45 × 924** (231 edges × 4 bands), columns `wpli_<band>_<A>-<B>` |
| `features/v3/connectivity_core_v3.csv` + `.meta.json` | **45 × 112** (28 edges × 4 bands) |
| `results/v3/step4/connectivity_edge_flags.csv` | 10,395 rows (45 × 231): status and number of interpolated endpoints per edge |
| `results/v3/step4/surrogate_homotopic.csv` | per subject × set × band × pair (+ MEAN): observed, own 95th-percentile surrogate, exceedance |
| `results/v3/step4/connectivity_qc.csv`, `connectivity_summary.json` | segments, class counts, NaN and flag counts, negative fractions, runtime; cohort summary |

Both feature tables hold `subject_id` + features only. Sidecar column lists and table sha256 values were verified.

## 3. Integrity and missing edges

| Check | Result |
|---|---|
| Subjects processed / failed | 45 / 0 |
| Non-NaN values finite | yes |
| NaN cells (extended) | 748 = 187 edges × 4 bands |
| Unavailable channel (41 edges each: 2 channels × 21 partners − 1 shared) | sub-13 (O1–O2), sub-29 (T7–T8), sub-30 (T7–T8), sub-31 (C3–C4) |
| Both endpoints interpolated (NaN, 23 edges) | sub-02, 03, 08, 19, 24, 30, 36, 39: 1 each; sub-12, 28, 32: 3 each; sub-38: 6 |
| Endpoint in a doubly-interpolated homologous pair | none |
| **Edges with one interpolated endpoint (kept, flagged)** | **849 edges in 26 subjects**, for the Step 8 sensitivity analysis |

## 4. Noise-floor check (surrogates)

For each subject: 200 surrogates, in which the right-hemisphere channels' segments are randomly reordered so that no segment keeps its true partner (fixed seed of 1000 + subject index). "Exceeds" means the observed value is greater than the subject's own 95th-percentile surrogate. Under the null, about 5% of subjects would exceed by chance.

| Set | Band | Subjects whose **mean homotopic** wPLI exceeds own p95 | Subject × pair cells exceeding | Median observed mean | Median own p95 |
|---|---|---|---|---|---|
| Extended (11 pairs) | delta | **0.87** (39/45) | 0.49 | 0.071 | 0.015 |
| | theta | **0.80** | 0.39 | 0.028 | 0.013 |
| | alpha | **0.71** | 0.42 | 0.032 | 0.014 |
| | beta | **0.78** | 0.32 | 0.011 | 0.006 |
| Core (4 pairs) | delta | 0.69 | 0.50 | 0.053 | 0.022 |
| | theta | 0.73 | 0.46 | 0.035 | 0.017 |
| | alpha | 0.73 | 0.42 | 0.034 | 0.017 |
| | beta | 0.62 | 0.30 | 0.012 | 0.008 |

Per homologous pair (extended set, fraction of subjects exceeding): O1–O2 is the strongest (alpha 0.50, delta 0.66). C3–C4 beta is the weakest (0.18). Every other pair-band cell lies between 0.24 and 0.59.

**Interpretation:**
- **Cohort level, pass.** In every band, a large majority of subjects (62–87%, against about 5% expected by chance) have homotopic connectivity above their own surrogate floor, and the median observed value is 1.8–4.6 times the median p95. The handoff criterion ("clearly above the surrogate floor in at least alpha and beta, or report failure honestly") is met for alpha (71% / 73%) and beta (78% / 62%).
- **Edge level, weak.** Only 30–50% of individual subject × pair values exceed their floor, and the values are small: the median wpli2_debiased is 0.03 in alpha and 0.01 in beta. **13–38% of subjects** do not exceed in a given band. Single edges are noisy, so later steps should rely on aggregated graph measures rather than individual edges.
- **Compared with v2:** the v2 graph features sat at the plain-wPLI noise floor (null mean about 0.29 at 15 epochs). The debiased estimator on about 74 segments removes that positive bias, and the remaining signal is demonstrably above the floor for most subjects.

## 5. Negative values (to be clipped in Step 5)

The median fraction of available edges below 0 is 17–25% per band (extended), and up to 50–61% in individual subjects (core delta/beta max 0.61). Negative values are expected for an unbiased estimator of a near-zero quantity. Clipping will set about one in five edges to exactly 0.

## 6. Segment-count dependence (label-free)

| | Features | Median \|ρ\| | Max \|ρ\| | \|ρ\| ≥ 0.3 |
|---|---|---|---|---|
| Core edges | 112 | 0.16 | 0.53 (delta C3–F4) | **18** |
| Extended edges | 924 | 0.14 | 0.66 (delta C3–FC4) | **145** (16%) |

| Homotopic mean | delta | theta | alpha | beta |
|---|---|---|---|---|
| Extended | **−0.50** | −0.01 | −0.14 | 0.02 |
| Core | **−0.40** | −0.14 | −0.21 | 0.17 |

**The handoff check (|ρ| < 0.3, or report it) fails for delta.** Subjects with fewer clean segments show higher delta connectivity, the same direction as the spectral DAR/DTABR dependence in Step 3b.
- wpli2_debiased is designed to be unbiased with respect to the number of segments, and the other bands show no comparable dependence. So this is most plausibly **recording quality**: noisier recordings keep more slow, lagged artifact or residual activity. It is not an estimator artifact.
- It cannot be resolved without labels or external data.

**For Step 8 (no action here):** delta connectivity features carry a recording-quality component, like DAR/DTABR. The registry should pre-specify the handling before labels are read (for example a segment-count covariate sensitivity analysis, or a delta-excluded variant).

## 7. Deviations and limitations

- **D16:** segments pooled across classes (not class-balanced), and the NaN rule extended from D14 to edges.
- **L12, delta on 2 s segments:** bins below 2.5 Hz have fewer than 5 cycles per segment.
- **L13, edge-level noise:** individual edges are frequently at the surrogate floor (section 4).
- **L14, delta segment-count dependence:** section 6.
- **L9-equivalent:** 849 edges with one interpolated endpoint are flagged, not removed.
- L4 (missing pairs as NaN) and L7 (Kaggle environment) carry over.
