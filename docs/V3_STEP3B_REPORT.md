# V3 Step 3b Report: Spectral Features on Subsampled Averaged Spectra (D15)

**Date:** 2026-11-06. **Branch:** `fix/flowchart-pipeline`. **Status:** DONE. Step 3b's tables are the spectral features for all later steps; the Step 3 tables are kept for comparison only.

**Why:** Step 3 computed |AI|, mabsAI and pdBSI per epoch (pdBSI per 0.25 Hz bin) and then averaged. With 3 tapers, the per-bin |BSI| for statistically identical hemispheres is about 0.31, and the Step 3 cohort pdBSI (0.315–0.50, median 0.35) sat at that floor (review finding; see the corrected `V3_STEP3_REPORT.md`).
**Method (config `configs/v3/spectral_v3b.json`):**
- For each subject and class: 100 draws of exactly 10 epochs (the per-class minimum) without replacement, seed = 42 + zero-based subject index (sub-01 → 42, verified in the QC file).
- Each draw's multitaper PSDs are averaged. AI, LR, |AI|, mabsAI, pdBSI (per bin on the averaged spectrum, 1–25 Hz), DAR and DTABR are computed on that averaged spectrum.
- Each class takes the median over draws, and the subject value is the mean of the two class values (D6).
- NaN rules, lesion alignment, sidecars and provenance are unchanged from Step 3.

**Run:** Kaggle, commit `9346c47` (clean), Python 3.13; Step 3 13.6 s, Step 3b 10.3 s. Input is the saved Step 2 notebook output. The config hash equals the committed `spectral_v3b.json`.
**Tests:** the new synthetic tests were written and byte-compiled but **not run** (user instruction for that commit). They were offered as Cell 2 in the Kaggle notebook; no result has been reported.

## 1. Integrity checks

| Check | Result |
|---|---|
| Refactored per-epoch path reproduces Step 3 | **Byte-identical**: `spectral_v3.csv` and `spectral_lesion_v3.csv` rerun at `9346c47` equal the original Step 3 outputs from `def7d1a` |
| Table shape and columns | `spectral_v3b.csv` 45 × 139, same columns as Step 3; lesion table 38 × 92, same subjects; sidecar column lists and table sha256 match |
| Bins per band | 12 / 16 / 20 / 68 |
| NaN | 48 cells, **pattern identical to Step 3** (sub-13 O1O2, sub-29/30 T7T8, sub-31 C3C4); no unexpected NaN; unavailable pairs match `epoch_qc_v3.csv` |
| Finite | all non-NaN values finite |

## 2. Old vs new, N = 45

| Feature | Step 3 [min, median, max] | Step 3b [min, median, max] | Spearman (3 vs 3b) |
|---|---|---|---|
| **pdBSI** | 0.315, 0.350, 0.500 | **0.149, 0.222, 0.479** | 0.940 |
| mabsAI delta | 0.203, 0.300, 0.434 | 0.121, 0.255, 0.433 | 0.943 |
| mabsAI theta | 0.160, 0.233, 0.396 | 0.091, 0.188, 0.388 | 0.944 |
| mabsAI alpha | 0.152, 0.207, 0.390 | 0.055, 0.165, 0.406 | 0.938 |
| mabsAI beta | 0.120, 0.224, 0.607 | 0.084, 0.201, 0.659 | 0.970 |
| DAR | 0.636, 4.256, 16.92 | 0.655, 4.279, 15.98 | 0.979 |
| DTABR | 0.651, 1.762, 7.439 | 0.612, 1.820, 7.199 | 0.987 |

Per-pair features: signed AI and LR barely change (median Spearman across the 44 columns 0.977 and 0.979; mean |change| 0.03 and 0.06). Per-pair |AI| drops (cohort median 0.211 → 0.160; median Spearman 0.893).

**Interpretation:** pdBSI and |AI| fall the way removing the per-epoch floor predicts (pdBSI median 0.35 → 0.22). The new minimum, 0.149, is above the 10-epoch averaged floor of about 0.10, so the cohort is no longer floor-bound. Subject ranks are largely preserved (ρ ≈ 0.94), meaning Step 3 differences between subjects were real but sat on top of an inflated floor. The ratio features (DAR, DTABR) and the signed features, which never depended on the floor, are essentially unchanged.

## 3. Epoch-count dependence, re-reported (label-free)

Spearman ρ of each feature with the number of epochs kept in Step 2, N = 45:

| | Step 3 | Step 3b |
|---|---|---|
| Median \|ρ\| | 0.114 | 0.104 |
| Features with \|ρ\| ≥ 0.3 (vs total epochs) | **11 / 139** | **5 / 139** |
| Features with \|ρ\| ≥ 0.3 (vs smaller class count) | 11 / 139 | 7 / 139 |

| Feature | ρ, Step 3 | ρ, Step 3b |
|---|---|---|
| DAR | −0.549 | −0.511 |
| DTABR | −0.484 | −0.481 |
| pdBSI | −0.424 | −0.300 |
| mabsAI beta | −0.345 | **−0.410** |
| absAI beta FT7FT8 | −0.375 | **−0.390** |
| absAI delta P7P8 | −0.413 | −0.255 |
| absAI delta T7T8 | −0.356 | −0.287 |
| absAI beta TP7TP8 | −0.317 | −0.282 |
| absAI delta F7F8 | −0.309 | −0.202 |
| mabsAI delta | −0.308 | −0.208 |
| absAI delta P3P4 | −0.304 | −0.078 |

**What changed:** equalising the noise floor (10 epochs per class for everyone) removed most of the floor-driven dependence in the delta-band |AI| features, and pdBSI fell from −0.42 to −0.30.

**What remains is a recording-quality signal, not a floor effect:**
- **DAR and DTABR (about −0.5)** do not change. Subjects with fewer clean epochs have more low-frequency power.
- **Beta-band asymmetry (mabsAI beta −0.41, FT7FT8 −0.39) slightly increases.** Beta at temporal sites (FT7/FT8) is where muscle activity shows up, so asymmetric residual muscle activity in noisier recordings is the likely source. That is plausible, not proven.

**Implication for Step 8 (no action here):** pdBSI (V4), DAR, DTABR and the beta |AI| features carry a recording-quality component. The frozen registry should pre-specify the handling before labels are read, for example an epoch-count or quality covariate sensitivity analysis, or a beta-excluded variant of the |AI| summaries. The choice is the user's at Step 8 approval.

## 4. Outputs (Kaggle zip, not committed until the Step 8 freeze)

- `features/v3/spectral_v3b.csv` + `.meta.json`: 45 × 139, the spectral features for later steps.
- `features/v3/spectral_lesion_v3b.csv` + `.meta.json`: 38 × 92 (uncertain side: sub-03, 20, 21, 33, 35, 38, 48).
- `results/v3/step3b/spectral_qc.csv`: per subject, with seed and aggregation method. `spectral_summary.json`: config, pdBSI range, NaN map, correlations.
- The Step 3 tables (`spectral_v3*.csv`) are retained unchanged for comparison.

## 5. Limitations

- L9 (single-sided interpolated pairs), L4 (missing pairs as NaN) and L7 (Kaggle environment) carry over unchanged.
- **L10 updated:** the remaining epoch-count dependence is a recording-quality effect concentrated in DAR, DTABR and beta asymmetry (section 3).
- **L11:** the synthetic tests for Step 3b have not been executed yet (byte-compiled only). The byte-identical reproduction of Step 3 and the integrity checks above are the only evidence about correctness so far.
