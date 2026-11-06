# V3 Step 8 Preparation Report: Freeze, Registry Text, Engine, Gates

**Date:** 2026-11-06. **Status:** features frozen and tagged `features-v3`; registry text final (`ANALYSIS_REGISTRY_V3.md`, `configs/v3/registry_v3.json`); engine, runner and gates implemented. **Not done, by instruction:** no `registry-v3` tag, no real-label run, no local test runs. All tests and gates run on Kaggle.

## 1. Pre-freeze check (label-free)

See `V3_STEP8_PREFREEZE.md`. The share of subjects with D2 > 0 is similar with and without one-sided interpolated analysed channels:
- core edges: 0.69–0.83 without vs 0.60–0.80 with;
- extended edges: 0.89–1.00 without vs 0.92–1.00 with.

The direction of the difference varies by band, so there is no systematic inflation. S3 remains registered.

## 2. Freeze (`features-v3`, commit `afb52b5`)

`src/freeze_features_v3.py` + `configs/v3/freeze.json` copied 14 tables (+ 12 sidecars, 12 config copies) and 11 QC/summary files from the five Kaggle output zips into `features/v3/` (QC into `features/v3/qc/`), and wrote `features/v3/MANIFEST.json`. Verified for every table:
- its sha256 equals its sidecar's `table_sha256`;
- the sidecar's config hash equals the shipped config copy **and** the committed config at the Kaggle commit;
- every Kaggle run was clean (`dirty: false`);
- `subject_meta_v3.csv` equals the committed file.

| Role | Tables |
|---|---|
| Registry inputs | `spectral_v3b.csv`, `spectral_lesion_v3b.csv`, `abnormality_crosshalf_v3.csv` |
| Descriptive S11 | `graph_region_v3.csv` (+ `spectral_lesion_v3b.csv`) |
| Cohort / QC | `epoch_qc_v3.csv`, `subject_meta_v3.csv`, `qc/*` |
| Intermediate / descriptive | connectivity core/ext, graph node/edge/network |
| Noise-inflated, never tested | `spectral_v3.csv`, `spectral_lesion_v3.csv`, `relational_abnormality_v3.csv` |

**Disclosed bugs found while freezing:**
1. **Comparison order.** The first freeze run compared `subject_meta_v3.csv` with the committed file *after* writing it, so the check could not fail. It was fixed to compare against the committed git blob before writing. The re-run confirmed the files are byte-identical.
2. **Manifest erratum (label file hash).** `MANIFEST.json` records `features/v2/subject_meta.csv` as `951ee16b…`. That hash was computed from a CRLF Windows working copy; the committed (LF) file, which every Kaggle clone gets, hashes to `7d69a156…0e4b`. The content is identical apart from line endings.
   - The published `features-v3` tag was **not** rewritten. Instead, the canonical hash is pinned in `configs/v3/registry_v3.json` (`labels.sha256_lf`, to be frozen by `registry-v3`), and `run_registry_v3.py` verifies the label file against it.
   - `freeze_features_v3.py` now hashes the committed blob.
   - **No feature table is affected.**

## 3. Registry (final text, not tagged)

| | Feature | N | Test |
|---|---|---|---|
| V1 | `pdBSI` | 45 | Spearman, two-sided |
| V2 | `les_meanAI_delta` | 38 | Spearman, two-sided |
| V3 | `core_D2_edge_allbands` | 45 | Spearman, two-sided |
| V4 | Ridge on 8 core D2 | 45 | one-sided |

Holm m = 4; signal = Holm p < 0.05 and |ρ| ≥ 0.30. Descriptive S1–S11. Labels: the v2 label file, read only by the runner after both tags, with the NIHSS cross-check against `participants.tsv`.

## 4. Code (byte-compiled only; tests and gates on Kaggle)

| File | Content |
|---|---|
| `src/train_regression_v3.py` | v2 engine + grouped stratified CV (outer and inner) + in-fold median imputation; association and ridge kinds; joint permutation with regenerated splits; bootstrap; partial Spearman (S1); whitelist loader with sidecar contract, banned-column check, label/class consistency, joint shuffling for smoke runs |
| `src/run_registry_v3.py` | one-shot runner. Refuses without both tags (ancestors of HEAD), if registry files changed since `registry-v3`, on any manifest hash mismatch (label file via `sha256_lf`), or on any NIHSS mismatch with `participants.tsv`. Writes `results/v3/registry/run_*/` and logs START/COMPLETE in `docs/PROGRESS.md` |
| `src/registry_gates_v3.py` | Gate A positive control, Gate B null calibration (exact binomial CI must contain 0.05), Gate C shuffled smoke on V1–V4 and S11; writes `results/v3/registry_gates/gates_v3.json` |
| `tests/test_registry_v3.py` | 8 synthetic tests: grouped splits, in-fold imputation, permutation bounds and alternatives, partial Spearman, tag guard, manifest guard, label cross-check, loader whitelist and joint shuffle, plus config ↔ frozen-table consistency (no labels read) |

Expected Kaggle test count: 72 (previous) + 8 = **80**.

## 5. Kaggle test runs and the splitter fix

| Run | Commit | Result |
|---|---|---|
| 1 | `026cc79` | 79 passed, **1 failed**: grouped-split test (required both classes in every fold). Gates not reached |
| 2 | `59dea01` | 79 passed, **1 failed**: relaxed test, class share off by 0.44 |
| Diagnostic | `59dea01` | sklearn `StratifiedGroupKFold(shuffle=True)` on the synthetic data (20/25 classes, two near-duplicate groups): one 8-subject validation fold was **100% moderate**; other folds 0.25–0.67 against 0.56 overall. Groups were never split |

**Fix:** `grouped_splits` now applies `StratifiedKFold` to the unique recording groups (group stratum = class of the lowest-ID member) and expands folds to members. Near-duplicates stay together and stratification is as exact as group sizes allow. The test is strict again: both classes in every fold, share within 0.20, groups intact, every subject validated once, checked over 5 synthetic datasets × 3 seeds.

- **The engine changed** (only the splitter), so **the gates must run on the fixed engine**. A gate run already in progress on `59dea01` used the old splitter and does not count.
- **Your confirmation is needed:** the registry text named `StratifiedGroupKFold`, so the change is recorded in `ANALYSIS_REGISTRY_V3.md` §3, `registry_v3.json` (`split_rule_change`) and D19, for you to confirm at the `registry-v3` tag.
