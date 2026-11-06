# v3 Analysis Registry (final text, NOT yet tagged)

**Status:** final text approved at registry review (2026-11-06). **Not tagged `registry-v3`**, and no real-label run has happened. The machine-readable twin is `configs/v3/registry_v3.json`. This file supersedes `ANALYSIS_REGISTRY_V3_DRAFT.md`, whose V1/V2 Ridge models are moved to descriptive S11.
**Features frozen:** tag `features-v3` (commit `afb52b5`), `features/v3/MANIFEST.json` (see the label-file erratum in `V3_STEP8_PREP_REPORT.md`).
**Honesty statement:** v3 was designed after the v2 null result. It fixes documented pipeline defects and completes missing flowchart stages; it is a new pre-specified exploratory analysis, not a rescue of v2. v2 and v3 are reported side by side and every registered test is reported.

## 1. Cohorts, target, labels

- **Main cohort, N = 45:** `include_v3_epochs`. Excluded: sub-04/05 (identical EEG), sub-06/27/40 (< 10 epochs per class).
- **Lesion cohort, N = 38:** main cohort with a certain lesion side. The ID lists are in the config.
- **Target:** `nihss_raw`. **Stratum:** `severity_class` (mild 1–4 / moderate 5–11). **Groups:** `split_group` (sub-11/15, sub-47/49).
- **Labels:** `features/v2/subject_meta.csv` (canonical LF sha256 `7d69a156…0e4b`), read **only** by `src/run_registry_v3.py`, after both tags exist and every manifest hash matches. The runner cross-checks NIHSS against `participants.tsv` for all 45 subjects and **refuses on any mismatch**.

## 2. Primary family (Holm, m = 4)

| ID | Statistic | Table and exact columns | N | Alternative | Expected |
|---|---|---|---|---|---|
| **V1** | Spearman with NIHSS; 1000-permutation p; 2000-bootstrap CI | `features/v3/spectral_v3b.csv`: `pdBSI` | 45 | two-sided | + |
| **V2** | Spearman with NIHSS; permutation p; bootstrap CI | `features/v3/spectral_lesion_v3b.csv`: `les_meanAI_delta` (ipsilesional − contralesional delta asymmetry) | 38 | two-sided | + (more ipsilesional slowing with higher NIHSS) |
| **V3** | Spearman with NIHSS; permutation p; bootstrap CI | `features/v3/abnormality_crosshalf_v3.csv`: `core_D2_edge_allbands` | 45 | two-sided | + |
| **V4** | Ridge → NIHSS; pooled out-of-fold Spearman (mean over 10 repeats); 1000-permutation p; bootstrap CI; fold-matched dummy | `features/v3/abnormality_crosshalf_v3.csv`: `core_delta_D2_edge`, `core_delta_D2_node`, `core_theta_D2_edge`, `core_theta_D2_node`, `core_alpha_D2_edge`, `core_alpha_D2_node`, `core_beta_D2_edge`, `core_beta_D2_node` | 45 | greater (one-sided, upper tail) | + |

All primary features are complete (no missing values) for their cohort.
**Decision rule:** signal detected only if **Holm-adjusted p < 0.05 and |ρ| ≥ 0.30**. Otherwise "no effect detected", never "no effect".
**Power (Fisher z, 80%):** minimum detectable ρ about 0.41 (N 45) and 0.44 (N 38) uncorrected; about 0.47 and 0.51 at the strictest Holm threshold; before cross-validation attenuation.

**Recorded reasons for the changes from the draft and the handoff:**
- **Draft Ridge models dropped from the primary family.** The 92-feature spectral-lesion Ridge and the 60-feature region-IC Ridge had p ≫ n at N = 38, and Step 7b showed that the signed IC direction is inconsistent across subjects. Both remain as descriptive S11.
- **V3 uses cross-half D2, not the Step 7 scalar.** The Step 7 unsigned summaries are noise-inflated (L15, D18).
- **Core stays primary.** That rule was fixed in the Steps 5–7 instruction, before Step 7b showed stronger noise-free signal in the extended set. The extended set is descriptive S8.

## 3. Engine (`src/train_regression_v3.py`; v2 logic + two changes)

- **CV:** outer `StratifiedGroupKFold(5, shuffle=True, random_state = 42 + repeat)`, 10 repeats, stratified on severity class, grouped by `split_group`. The inner alpha selection uses grouped `StratifiedGroupKFold(5, random_state = 42)` inside each outer training fold.
- **Pipeline:** `SimpleImputer(median)` → `StandardScaler` → `Ridge`, all fitted inside training folds. Alpha grid logspace(−2, 3, 20); one SVD per inner fold, as in v2.
- **Permutation:** joint permutation of (NIHSS, severity class) across subjects; groups stay attached to recordings; splits regenerated; 1000 permutations (seed base 43000); p = (1 + #exceed)/(1 + B).
- **Bootstrap:** 2000 subject-row resamples (seed base 53000), 95% CI. **Holm:** `stats_utils.holm_adjust` (unchanged v2 code).

## 4. Descriptive analyses (outside Holm; estimates only, no p-values, no claims)

| ID | Analysis |
|---|---|
| S1 | Quality adjustment: V1–V3 partial Spearman controlling `n_epochs_kept`; V4 Ridge with `n_epochs_kept` as a ninth feature |
| S2 | V1–V4 within supratentorial (N 29) and infratentorial (N 16) lesions; Ridge only if each class has ≥ 5 subjects |
| S3 | V3, V4 excluding the 10 subjects that use a core edge with one interpolated endpoint (`core_flagged_edges_used > 0`) |
| S4 | V1–V4 excluding the paper's motion-artifact subjects (11 in the cohort) |
| S5 | Mild-vs-moderate AUC (V1–V3 scalars; V4 out-of-fold predictions) |
| S6 | V1–V3 Spearman with MBI and mRS (disability, not severity) |
| S7 | v2 primary T1–T9 next to v3 V1–V4 (report table; v2 not recomputed) |
| S8 | Extended set instead of core: V3 with the mean of `extended_{delta,theta,alpha,beta}_D2_edge`; V4 with the 8 `extended_*_D2_edge/node` columns |
| S9 | V1–V4 dropping sub-15 and sub-49 (one member of each near-duplicate pair; lower ID kept) |
| S10 | Spearman(`n_epochs_kept`, NIHSS), report-only confound check |
| S11 | Draft Ridge models: all 92 `spectral_lesion_v3b` columns (N 38) and the 60 `region_*_IC` columns of `graph_region_v3` (N 38) |

Never tested: noise-inflated tables and columns (Step 3 `spectral_v3*`, Step 5–7 unsigned columns, `relational_abnormality_v3`, `naive_noiseinflated_*`).

## 5. Acceptance gates (before tagging `registry-v3`; synthetic and shuffled only)

`src/registry_gates_v3.py`:
- **A. Positive control:** planted ρ 0.6, N 45, 8 features, two near-duplicate groups. Ridge and association engines with 1000 permutations must give p < 0.01.
- **B. Null calibration:** 200 null datasets, 200 permutations, 2 repeats. The exact 95% CI of the false-positive rate at α = 0.05 must contain 0.05, for both engines.
- **C. Shuffled smoke run:** V1–V4 and both S11 models on jointly shuffled labels. No error; ρ reported.

Plus `pytest tests/test_*_v3.py`.

## 6. Run protocol

1. Gates and tests pass on Kaggle and are recorded.
2. The user approves. Then commit and **tag `registry-v3`**.
3. **One** real run: `python src/run_registry_v3.py --data-root <folder containing figshare/>`. It refuses without both tags, unchanged registry files since `registry-v3`, matching manifest hashes and a passing NIHSS cross-check. The invocation is logged in `docs/PROGRESS.md`; a rerun needs `--rerun-reason`.
4. Report all four tests (raw and Holm p, decisions, failures included), then S1–S11.
