# v3 Analysis Registry: DRAFT for user approval

> **SUPERSEDED (2026-11-06)** by `docs/ANALYSIS_REGISTRY_V3.md` after the registry review. The draft's V1/V2 Ridge models are now descriptive S11. Kept for the record.

**Status: DRAFT, not frozen, not tagged.** No v3 step has read NIHSS, severity class, MBI or mRS. Nothing in this file may be run against real labels until the user approves it, the features are frozen (`features-v3` tag + manifest), and this registry is finalised as `docs/ANALYSIS_REGISTRY_V3.md` and tagged `registry-v3`.
**Date:** 2026-11-06. **Basis:** handoff Step 8, Steps 0–7b reports, deviations D1–D18.

**Honesty statement (for the final report):** v3 was designed after the v2 null result. It fixes documented pipeline defects and completes missing flowchart stages; it is a new pre-specified exploratory analysis, not a rescue of v2. v2 and v3 are reported side by side, and every registered test is reported whatever its result.

## 1. Cohort and target

| Item | Proposal |
|---|---|
| Cohort | **N = 45**: the Step 2 inclusion (`epoch_qc_v3.csv`, `include_v3_epochs`). Excluded: sub-04, sub-05 (identical EEG, Step 1); sub-06, sub-27, sub-40 (< 10 clean epochs per class, Step 2) |
| Lesion-aligned cohort | **N = 38** (certain lesion side; uncertain: sub-03, 20, 21, 33, 35, 38, 48) |
| Target | `nihss_raw` (continuous NIHSS, the severity measure the topic requires) |
| Stratum | `severity_class` (mild NIHSS 1–4 / moderate 5–11), used only to stratify CV folds and for the descriptive AUC |
| Label source | `features/v2/subject_meta.csv` (the verified, frozen v2 label file; same Figshare source), read **only** by the Step 8 runner after both tags exist. No new label-reading code before the freeze |
| Groups | `split_group` from `subject_meta_v3.csv`: near-identical recordings sub-11/15 and sub-47/49 always fall in the same fold |

## 2. Frozen feature inputs (`features-v3`)

The Kaggle-produced tables below are copied into `features/v3/` and sha256-hashed in `features/v3/MANIFEST.json` together with their sidecars and generating configs:

| Table | From | Use |
|---|---|---|
| `spectral_lesion_v3b.csv` (38 × 92) | Step 3b | V1 |
| `spectral_v3b.csv` (45 × 139) | Step 3b | V4 (pdBSI) |
| `graph_region_v3.csv` (45 × 200) | Steps 5–6 | V2 (IC columns) |
| `abnormality_crosshalf_v3.csv` (45 × 162) | Step 7b | V3 |
| `epoch_qc_v3.csv`, `subject_meta_v3.csv` | Steps 1–2 | cohort, groups, sensitivity covariates (no features) |

The noise-inflated tables and columns (Step 3 `spectral_v3*.csv`, Step 5–7 unsigned columns, `relational_abnormality_v3.csv` summaries, `naive_noiseinflated_*`) are frozen for reproducibility but **never tested**.

## 3. Primary family (Holm, m = 4)

| ID | Question | Features (all columns of the listed set) | N | Model / statistic | Alternative |
|---|---|---|---|---|---|
| **V1** | Does lesion-aligned spectral asymmetry predict NIHSS? | `spectral_lesion_v3b.csv`: all 92 (les_AI and les_LR, 4 bands × 11 pairs, + les_meanAI × 4) | 38 | Ridge (Section 4); pooled out-of-fold Spearman ρ, mean over 10 repeats | greater |
| **V2** | Does lesion-aligned regional graph asymmetry predict NIHSS? | `graph_region_v3.csv`: the 60 `region_*_IC` columns (5 regions × 4 bands × strength / local efficiency / clustering) | 38 | Ridge; pooled out-of-fold ρ | greater |
| **V3** | Is noise-free hemispheric deformation associated with NIHSS? *(replaces the noise-inflated Step 7 scalar; see L15, D18)* | `abnormality_crosshalf_v3.csv`: `core_D2_edge_allbands` (single scalar, frame-invariant) | 45 | Spearman ρ with NIHSS | two-sided |
| **V4** | Is corrected spectral asymmetry (pdBSI) associated with NIHSS? | `spectral_v3b.csv`: `pdBSI` (single scalar) | 45 | Spearman ρ with NIHSS | two-sided |

**Decision rule (unchanged from v2):** a test counts as "signal detected" only if **Holm-adjusted p < 0.05 and |ρ| ≥ 0.30**. Otherwise "no effect detected", never "no effect".
**Power (Fisher z, 80%):** minimum detectable ρ is 0.41 at N = 45 and 0.44 at N = 38 uncorrected; at the strictest Holm threshold (0.05/4) it is 0.47 and 0.51, before cross-validation attenuation. Effects below these sizes cannot be excluded.

## 4. Engine (reuse of the audited v2 logic)

Copy `src/train_regression.py` and `src/stats_utils.py` to `src/train_regression_v3.py` (+ `stats_utils` reused unchanged), with **two changes only**:
1. **Grouped stratified CV:** `StratifiedGroupKFold(n_splits=5, shuffle=True)` repeated 10 times (seed 42 + repeat), stratified on `severity_class`, groups = `split_group`; the inner alpha CV is grouped the same way.
2. **Missing values for Ridge:** `SimpleImputer(strategy="median")` fitted **inside each training fold** (in the pipeline, before scaling). This affects only V1 (4 subjects with an unavailable pair) and V2 (sub-13 occipital). The feature tables themselves stay un-imputed.

Unchanged from v2: StandardScaler → Ridge, alphas logspace(−2, 3, 20) with 5-fold inner CV; 1000 permutations (seed base 42000) that jointly permute (NIHSS, class) across subjects and regenerate the splits, while groups stay attached to recordings; p = (1 + #null ≥ obs)/(1 + B); 2000-resample bootstrap CI (seed base 52000); fold-matched `DummyRegressor(mean)`; RMSE / MAE / R² reported against the dummy.
**Before the real run:** re-run the v2 synthetic acceptance gates on the v3 engine (planted-signal positive control p < 0.01; null calibration, false-positive rate about 5%; shuffled-label smoke run on every v3 table) and record them.

## 5. Pre-specified descriptive analyses (outside Holm, no claims)

| ID | Analysis | Why |
|---|---|---|
| S1 | V3 and V4 as partial Spearman adjusting for the number of clean epochs (rank-residualised); V1 and V2 with the epoch count added as a covariate inside the pipeline | Recording-quality dependence (L10, L14, 7b alpha ρ −0.49) |
| S2 | V1–V4 within supratentorial vs infratentorial lesions (`site_class`) | Handoff subgroup; scalp asymmetry is expected weaker for infratentorial lesions |
| S3 | V2 and V3 excluding subjects that use any edge with one interpolated endpoint (Step 4 flags: 10 core subjects) | Interpolation sensitivity |
| S4 | V1–V4 excluding the paper's motion-artifact subjects (11 in the cohort) | Data-quality sensitivity |
| S5 | Mild-vs-moderate AUC of the V1/V2 out-of-fold predictions and of the V3/V4 scalars | Severity-class bridge to Phase 5 |
| S6 | Spearman of the V3/V4 scalars with MBI and mRS | Disability, not severity: descriptive only |
| S7 | v2 primary results (T1–T9) next to v3 V1–V4 | Required side-by-side reporting |

## 6. Run protocol

1. Copy the frozen tables into `features/v3/`, write `MANIFEST.json`, commit, and **tag `features-v3`** (annotated).
2. Implement `train_regression_v3.py` and `run_registry_v3.py`. The runner refuses to run unless both tags exist and every input hash matches the manifest. Run the synthetic gates.
3. Finalise this file as `docs/ANALYSIS_REGISTRY_V3.md`, commit, and **tag `registry-v3`**.
4. **One real run** (Kaggle or locally; it is CPU-light but has about 4 × 1000 permutation refits). Log the invocation in `docs/PROGRESS.md`. A rerun after a bug is allowed only with a logged reason.
5. Report all four tests with raw and Holm p, failures included, then the S1–S7 descriptive analyses.

## 7. Decisions needed from you before freezing

1. **Test list:** approve V1–V4 as written. The main change from the handoff: **V3 uses the cross-half `core_D2_edge_allbands`** instead of the noise-inflated Step 7 scalar. The alternative would be the extended-set mean (stronger noise-free signal in 7b, but secondary per your Step 5 rule).
2. **Missing values in Ridge:** in-fold median imputation (recommended), or restrict V1/V2 to columns complete in all subjects.
3. **Grouped CV and the permutation scheme** as in Section 4.
4. **Label source:** the v2 label file (recommended), or a new label-join from `participants.tsv`.
5. **Descriptive list S1–S7:** keep, trim or extend. Nothing outside V1–V4 enters Holm.
