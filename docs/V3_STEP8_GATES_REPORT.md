# V3 Step 8 Gate Report: Tests, Synthetic Gates, Pre-freeze Check, Status

**Date:** 2026-11-06. **Branch:** `fix/flowchart-pipeline`. **Purpose:** the evidence needed before the `registry-v3` tag. Read with `docs/ANALYSIS_REGISTRY_V3.md` (final registry text).
**State:** features frozen (`features-v3`, `afb52b5`). Registry text final, **not tagged**. **No real-label inference has been run.**

## 1. Kaggle run

| Item | Value |
|---|---|
| Commit | `4172eaa` (clean clone; tag `features-v3` present) |
| Kaggle version | script version 366315699 ("Save & Run All") |
| Environment | Python 3.13, 4 CPUs, packages as `kaggle/requirements_kaggle.txt` |
| Total wall time | 4,287 s (about 71 min), almost all of it gates A + B |
| Source of the numbers below | the run log (each gate prints its JSON summary); the same content is in `results/v3/registry_gates/gates_v3.json` of that version |

## 2. Unit tests

`pytest tests/test_*_v3.py`: **80 passed** in 41.8 s. The 32 warnings are the expected undefined Spearman in the 2-subject cross-half end-to-end test.

This includes the 8 registry tests:
- the strict grouped-split test (both classes in every fold, class share within 0.20, groups never split, every subject validated once; 5 datasets × 3 seeds);
- in-fold imputation, permutation bounds, partial Spearman;
- the tag, manifest and label guards, and the loader whitelist with joint shuffle;
- config ↔ frozen-table consistency: the manifest check covers all 50 records, with the label file checked against its canonical LF hash.

## 3. Synthetic gates (`src/registry_gates_v3.py`): **ALL PASS**

### Gate A: positive control (N 45, 8 features, planted ρ 0.6, two near-duplicate groups; 1000 permutations)

| Engine | ρ | p | Pass rule | Result |
|---|---|---|---|---|
| Ridge (V4 path; 20 mild / 25 moderate) | 0.553 | 0.000999 (= 1/1001, the minimum) | p < 0.01 | **PASS** |
| Association (V1–V3 path) | 0.673 | 0.000999 | p < 0.01 | **PASS** |

### Gate B: null calibration (200 null datasets, 200 permutations, 2 outer repeats; α = 0.05)

| Engine | False positives | FPR | Exact 95% CI | Pass rule (CI contains 0.05) | Null p quantiles (10/25/50/75/90%) |
|---|---|---|---|---|---|
| Ridge (one-sided) | 5 / 200 | 0.025 | [0.008, 0.057] | **PASS** | 0.12 / 0.25 / 0.51 / 0.73 / 0.90 |
| Association (two-sided) | 14 / 200 | 0.070 | [0.039, 0.115] | **PASS** | 0.11 / 0.26 / 0.57 / 0.78 / 0.87 |

The null p-values are close to uniform (median about 0.5). The Ridge point estimate is on the conservative side; the association point estimate is slightly above 0.05, but both CIs contain the nominal rate.

### Gate C: shuffled-label smoke run (labels jointly shuffled before use; 100 permutations, 2 repeats)

| Analysis | N | Features | Missing cells (imputed in-fold) | ρ (shuffled) | p (shuffled) | Result |
|---|---|---|---|---|---|---|
| V1 pdBSI | 45 | 1 | 0 | 0.145 | 0.34 | ran |
| V2 les_meanAI_delta | 38 | 1 | 0 | 0.308 | 0.040 | ran |
| V3 core_D2_edge_allbands | 45 | 1 | 0 | −0.007 | 0.98 | ran |
| V4 Ridge, 8 core D2 | 45 | 8 | 0 | −0.039 | 0.24 | ran |
| S11 spectral-lesion Ridge | 38 | 92 | 32 | 0.278 | 0.040 | ran |
| S11 region-IC Ridge | 38 | 60 | 12 | −0.048 | 0.40 | ran |

**Pass rule:** runs without error on every registry table. **PASS.**
- **Reading the ρ column:** each row is a **single** random shuffle, so ρ values of about ±0.3 and occasional p ≈ 0.04 are expected by chance across 6 analyses (Gate B is the calibration check, and it passed). These shuffled numbers carry no information about the real labels.
- **Missing values:** the S11 models confirm that missing values are handled inside the folds.

## 4. Pre-freeze check: cross-half D2 > 0 by one-sided interpolation (label-free)

A subject counts as "one-sided interpolated" if any homologous pair of the set has exactly one interpolated channel (continuous stage or rule iii).
- **Core:** 10 subjects with, 35 without.
- **Extended:** 26 with, 19 without.

About 0.50 of subjects would have D2 > 0 if there were no true asymmetry.

| Set | Level | Band | Without | With |
|---|---|---|---|---|
| Core | edge | delta / theta / alpha / beta | 0.69 / 0.69 / 0.83 / 0.74 | 0.80 / 0.70 / 0.80 / 0.60 |
| Core | node | delta / theta / alpha / beta | 0.57 / 0.63 / 0.74 / 0.71 | 0.70 / 0.60 / 0.70 / 0.50 |
| Extended | edge | delta / theta / alpha / beta | 0.89 / 0.95 / 1.00 / 1.00 | 1.00 / 0.96 / 0.92 / 0.96 |
| Extended | node | delta / theta / alpha / beta | 0.79 / 0.79 / 0.95 / 0.89 | 1.00 / 0.85 / 0.81 / 0.81 |

The differences go in both directions by band, so interpolation shows no systematic inflation. S3 (excluding the 10 core-flagged subjects) remains a registered descriptive check. Full version: `V3_STEP8_PREFREEZE.md`.

## 5. Engine history relevant to approval

| Run | Commit | Outcome |
|---|---|---|
| Tests 1 | `026cc79` | 79/80: grouped-split test failed; gates not reached |
| Tests 2 | `59dea01` | 79/80: diagnostic showed sklearn `StratifiedGroupKFold(shuffle=True)` producing an 8-subject all-moderate fold |
| Fix | `4172eaa` | `grouped_splits` = `StratifiedKFold` over recording groups (stratum = lowest-ID member's class); groups never split |
| Tests + gates | `4172eaa` | **80/80; Gates A, B, C pass** (this report) |

## 6. What needs your approval before `registry-v3`

1. **The registry as written** (`ANALYSIS_REGISTRY_V3.md`): V1 pdBSI, V2 `les_meanAI_delta` (N 38), V3 `core_D2_edge_allbands`, V4 Ridge on 8 core D2 features; Holm m = 4; signal = Holm p < 0.05 and |ρ| ≥ 0.30; descriptive S1–S11.
2. **The splitter change:** group-level `StratifiedKFold` instead of `StratifiedGroupKFold`, made after the review on synthetic evidence only.
3. **The label-file erratum handling:** the canonical LF hash is pinned in `registry_v3.json` (`labels.sha256_lf`) instead of rewriting the published `features-v3` tag.

After approval: commit, tag `registry-v3`, push the tag, then **one** real run with `src/run_registry_v3.py`. That needs a Kaggle notebook with the Figshare dataset attached for the NIHSS cross-check; expect a runtime similar to Gate A × 4 plus sensitivities, about 1–2 h. No label has been read so far.
