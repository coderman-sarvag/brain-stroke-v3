# V3 Step 3 Report: Multi-band Spectral Representation

**Date:** 2026-11-06. **Branch:** `fix/flowchart-pipeline`. **Status:** DONE. All acceptance checks pass; one QC finding (epoch-count dependence) is carried forward to the Step 8 design.

**Code / config:** `src/spectral_v3.py`, `configs/v3/spectral.json` (Kaggle provenance hash equals the committed file).
**Tests:** `tests/test_spectral_v3.py`, 9 synthetic tests; full repo suite 93/93 locally.
**Run:** Kaggle, commit `def7d1a` (clean), Python 3.13, 13 s. Input (`--prev-root`) is the saved Step 2 notebook output `/kaggle/input/notebooks/sarvagyajainhello/brain-stroke-v3-step2-final/v3_out`. The sha256 of all 45 input epoch files is recorded in the sidecar.
**Label blindness:** reads `epoch_qc_v3.csv` (inclusion, interpolation and pair columns) and, in the lesion-alignment function only, `lesion_side_final`. No outcome column is read.

## 1. Method

| Item | Setting |
|---|---|
| PSD | Multitaper on the full 4 s epoch (2000 samples), 1–30 Hz, 1 Hz full bandwidth (NW = 2, 3 tapers), `normalization="full"` |
| Resolution | 0.25 Hz. **Bins per band: delta 12, theta 16, alpha 20, beta 68** (minimum required: 6; identical for all subjects) |
| Bands | delta [1, 4), theta [4, 8), alpha [8, 13), beta [13, 30) Hz, half-open; band power = sum of PSD bins × bin width |
| Pairs | 11 analysed homologous pairs: F3F4, F7F8, FC3FC4, FT7FT8, C3C4, T7T8, CP3CP4, TP7TP8, P3P4, P7P8, O1O2 |
| Per epoch, per pair and band | AI = (L − R)/(L + R); LR = ln L − ln R; absAI = \|AI\| |
| Per epoch, global | mabsAI per band (mean absAI over available pairs); pdBSI = mean over pairs and 1–25 Hz bins of \|(R − L)/(R + L)\|; DAR = delta/alpha and DTABR = (delta + theta)/(alpha + beta) of power summed over available analysed channels |
| Aggregation | Per-epoch values → mean within each class → **mean of the two class means** (D6) |
| Missing | NaN, no imputation, when a pair is unavailable (in `info['bads']`) or both of its channels were interpolated at any stage (D14) |
| Lesion-aligned | ipsi − contra (AI and LR sign-flipped for right lesions) + les_meanAI per band, certain-side subjects only, in a separate table (D14) |

## 2. Outputs

| File | Rows × features | Content |
|---|---|---|
| `features/v3/spectral_v3.csv` + `.meta.json` | **45 × 139** | AI, LR and absAI for 4 bands × 11 pairs (132), mabsAI × 4, pdBSI, DAR, DTABR |
| `features/v3/spectral_lesion_v3.csv` + `.meta.json` | **38 × 92** | les_AI and les_LR for 4 × 11 (88), les_meanAI × 4 |
| `results/v3/step3/spectral_qc.csv`, `spectral_summary.json` | per subject / cohort | epochs per class, pairs used, interpolation per pair, bins, NaN map, epoch-count correlations |

Both feature tables hold `subject_id` + features only. The sidecars list the columns (matching the CSVs), definitions, config hash, git commit, the table's own sha256 (verified), and the input hashes. The tables and sidecars live in the Kaggle output zip; the `features/v3/` copies are not committed (see section 6).

The lesion table excludes 7 included subjects with an uncertain side: sub-03, sub-20, sub-21, sub-33, sub-35, sub-38, sub-48.

## 3. Acceptance checks (handoff Step 3)

| Criterion | Result |
|---|---|
| Values finite | **PASS**: every non-NaN value finite; the writer refuses infinite values |
| No subject has a pair computed from interpolated data on both sides | **PASS**: 0 such pairs, checked across both interpolation stages |
| Epoch-count correlation reported | **Reported** (section 4) |
| ≥ 6 bins per band | **PASS**: 12 / 16 / 20 / 68 |
| NaN only where expected | **PASS**: 48 NaN cells = 4 subject-pairs × 4 bands × 3 kinds (sub-13 O1O2, sub-29 T7T8, sub-30 T7T8, sub-31 C3C4); `unexpected_nan` is empty; the unavailable pairs match `epoch_qc_v3.csv` exactly |
| Synthetic tests | **PASS**: 9/9 (known asymmetry → AI 0.6 and LR ln 4 exactly; symmetric montage → 0; class balancing gives 0.3, not the epoch-weighted 0.45; NaN rules; DAR/DTABR from known sinusoids within 2%; too-short epochs refused; lesion sign flip; end-to-end run) |

## 4. QC finding: dependence on epoch count (label-free)

Spearman ρ of each feature with the number of epochs kept, across the 45 subjects: median |ρ| = 0.11. **11 of 139 features reach |ρ| ≥ 0.3, all negative**:

| Feature | ρ with n_epochs |
|---|---|
| DAR | −0.549 |
| DTABR | −0.484 |
| pdBSI | −0.424 |
| absAI delta P7P8 | −0.413 |
| absAI beta FT7FT8 | −0.375 |
| absAI delta T7T8 | −0.356 |
| mabsAI beta | −0.345 |
| absAI beta TP7TP8 | −0.317 |
| absAI delta F7F8 | −0.309 |
| mabsAI delta | −0.308 |
| absAI delta P3P4 | −0.304 |

Subjects who kept fewer clean epochs show more slowing (DAR, DTABR) and more absolute asymmetry. Two explanations are possible and cannot be separated here:
1. **Recording quality:** noisier recordings both lose more epochs and keep more residual low-frequency or artifact power.
2. **Estimator bias:** a mean of |AI| over fewer epochs is biased upward.

The signed AI and LR features show no such dependence (none reach |ρ| ≥ 0.3).

**Implication (no action taken):** pdBSI (planned registry test V4), DAR and DTABR carry a measurable data-quality component. Step 8's frozen registry should pre-specify how this is handled before any label is read, for example a sensitivity analysis adjusting for epoch count or restricted to well-recorded subjects. This report proposes nothing further; the decision belongs to Step 8 approval.

## 5. Descriptive ranges (label-free, N = 45)

| Feature | min | median | max |
|---|---|---|---|
| pdBSI | 0.315 | 0.350 | 0.500 |
| DAR | 0.64 | 4.26 | 16.92 |
| DTABR | 0.65 | 1.76 | 7.44 |
| mabsAI delta / theta / alpha / beta | 0.20 / 0.16 / 0.15 / 0.12 | 0.30 / 0.23 / 0.21 / 0.22 | 0.43 / 0.40 / 0.39 / 0.61 |
| AI (all 44 columns) | −0.85 | 0.01 | 0.84 |
| LR (all 44 columns) | −2.68 | 0.02 | 2.57 |

The cohort-median signed AI per pair is close to 0 (|median| ≤ 0.13; largest delta FT7FT8 −0.13 and T7T8 −0.11). Left- and right-sided lesions are mixed in this L/R frame, so near-zero medians are expected. The lesion-aligned les_meanAI medians are delta 0.003, theta 0.03, alpha 0.05, beta 0.07.

## 6. Limitations and notes carried forward

- **L9 Single-sided interpolation:** 26 of 45 subjects have at least one usable pair with one interpolated channel (for example sub-12: C3C4, CP3CP4, TP7TP8; sub-38: F3F4, FT7FT8, C3C4, T7T8). Spline interpolation draws on neighbouring channels, which can pull that pair's asymmetry toward 0. These pairs are kept by rule and listed per subject in `spectral_qc.csv`.
- **L10 Epoch-count dependence:** section 4.
- **L4 (from Step 2) Missing pairs** are NaN in both tables. Steps 5–7 and the Step 8 models must handle NaN explicitly; the feature tables impute nothing.
- **Not committed:** the feature CSVs are run outputs from Kaggle (in `v3_outputs_small.zip`), not committed, consistent with Step 2's outputs. They will be frozen with sha256 values in `features/v3/MANIFEST.json` at Step 8 (`features-v3` tag), as the handoff specifies.
- Kaggle environment as in Step 2 (L7).
