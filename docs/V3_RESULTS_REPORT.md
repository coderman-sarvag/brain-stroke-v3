# V3 Results Report: Registered Evaluation of Hemispheric EEG Asymmetry vs Stroke Severity (NIHSS)

**Date:** 2026-11-06. **Branch:** `fix/flowchart-pipeline`. **Registry:** `docs/ANALYSIS_REGISTRY_V3.md`, approved and tagged `registry-v3` (`09c12dd`); features tagged `features-v3` (`afb52b5`).
**Bottom line:** **all four registered tests: no effect detected** (Holm-adjusted p = 1.000 for each). No v3 asymmetry measure, spectral or graph, showed a detectable association with NIHSS in this cohort. The descriptive analyses S1–S11 do not change this picture.

**Honesty statement:** v3 was designed after the v2 null result. It fixes documented pipeline defects and completes missing flowchart stages; it is a new pre-specified exploratory analysis, not a rescue of v2. v2 and v3 are reported side by side (section 5). "No effect detected" does not mean "no effect": effects smaller than the power limits in section 2 cannot be ruled out.

## 1. Runs and provenance

| Run | Commit | What it computed | Outcome |
|---|---|---|---|
| **Primary (one shot)** `run_20261106T163923Z` | `09c12dd` (= `registry-v3`, Kaggle, detached at the tag) | V1–V4: 1000 permutations each, bootstrap, Holm | **All guards passed**: both tags; registry files unchanged; 50/50 manifest hashes; `participants.tsv` md5; NIHSS cross-check for 45 subjects. V1–V4 saved. **Then crashed in S8-V3** (my loader bug, D20); no COMPLETE line |
| **Sensitivities only** `sensitivities_for_run_20261106T163923Z` | `6495e07` | S1–S11 (tagged `run_sensitivities()` + one adapter for derived features) | Same guards passed; START and COMPLETE logged; 37 rows, none not computable. **V1–V4 not rerun** (`primary_rerun: false`) |

There were no other real-label runs. Both invocations are logged in `docs/PROGRESS.md`. The `dirty: true` flag in the sensitivity record comes only from the script's own PROGRESS log line in the Kaggle clone.

**Cohort:** main N = 45 (**30 mild / 15 moderate**); lesion-aligned N = 38 (23 / 15). Excluded: sub-04/05 (identical EEG), sub-06/27/40 (fewer than 10 clean epochs per class). CV groups keep the near-duplicate recordings sub-11/15 and sub-47/49 together.

## 2. Primary family (Holm, m = 4): results as registered

| Test | Features | N (mild/mod) | ρ | 95% bootstrap CI | Raw p | Holm p | Alternative | Expected | **Decision** |
|---|---|---|---|---|---|---|---|---|---|
| **V1** | `pdBSI` (3b) | 45 (30/15) | **0.006** | [−0.263, 0.275] | 0.967 | **1.000** | two-sided | + | **no effect detected** |
| **V2** | `les_meanAI_delta` | 38 (23/15) | **−0.080** | [−0.407, 0.238] | 0.614 | **1.000** | two-sided | + | **no effect detected** |
| **V3** | `core_D2_edge_allbands` (cross-half) | 45 (30/15) | **0.107** | [−0.214, 0.431] | 0.476 | **1.000** | two-sided | + | **no effect detected** |
| **V4** | Ridge on 8 core cross-half D2 | 45 (30/15) | **−0.229** | [−0.399, −0.043] | 0.867 | **1.000** | greater | + | **no effect detected** |

**Decision rule:** signal detected only if Holm p < 0.05 **and** |ρ| ≥ 0.30. No test met either condition. **No test failed computationally** (bootstrap invalid draws: 0 for every test).
**Power:** at N = 45 (38), the minimum detectable ρ at 80% power is about 0.41 (0.44) uncorrected and about 0.47 (0.51) at the strictest Holm threshold, before CV attenuation. All observed |ρ| are well below these values.

### V4 against the fold-matched dummy (predict the training mean)

| Metric (mean over 10 repeats) | V4 Ridge | Dummy | Ridge − dummy |
|---|---|---|---|
| RMSE | 3.402 | 2.957 | **+0.446** (worse) |
| MAE | 2.586 | 2.404 | **+0.183** (worse) |
| R² | −0.383 | −0.011 | −0.372 |
| Mild-vs-moderate AUC of predictions | 0.401 | — | — |

**Why V4's ρ is negative:** V4's out-of-fold ρ is negative, and its CI excludes 0 on the negative side. This is **not** evidence of an inverse relation. The test's own permutation null has mean **−0.111** (SD 0.117): in small-sample CV, Ridge out-of-fold predictions are anticorrelated with the target even when there is no signal. The registered one-sided p is 0.867. V4 is worse than predicting the mean.

The permutation nulls of V1–V3 are centred at about 0 (means 0.001 / 0.013 / 0.012; SD 0.14–0.16), as expected for association tests.

## 3. Descriptive analyses S1–S11 (outside Holm; estimates only, no p-values, no claims)

| ID | Analysis | V1 pdBSI | V2 les_meanAI_delta | V3 core D2 | V4 Ridge (ρ; RMSE vs dummy) |
|---|---|---|---|---|---|
| (primary) | as registered | 0.006 (45) | −0.080 (38) | 0.107 (45) | −0.229; 3.40 vs 2.96 (45) |
| **S1** | quality-adjusted (`n_epochs`): partial Spearman / Ridge + n_epochs | 0.007 | −0.050 | 0.109 | −0.253; 3.24 vs 2.96 |
| **S2** | supratentorial (N 29 / 25) | 0.013 | −0.141 | 0.154 | −0.343; 3.63 vs 2.87 |
| **S2** | infratentorial (N 16 / 13) | −0.046 | 0.135 | −0.018 | −0.314; 3.96 vs 3.13 |
| **S3** | excluding 10 core-interpolation-flagged subjects (N 35) | — | — | −0.037 | −0.247; 3.13 vs 2.97 |
| **S4** | excluding motion-artifact subjects (N 34 / 29) | 0.097 | −0.034 | 0.065 | −0.324; 3.27 vs 2.86 |
| **S9** | dropping sub-15, sub-49 (N 43 / 36) | −0.059 | −0.142 | 0.037 | −0.248; 3.22 vs 2.96 |
| **S8** | extended set instead of core (N 45) | — | — | **0.264** (mean of 4 extended D2_edge) | −0.129; 3.07 vs 2.96 |

| ID | Analysis | Result |
|---|---|---|
| **S5** | Mild-vs-moderate AUC (N 45 / 38) | V1 0.476, V2 0.467, V3 0.489, V4 0.401: all near or below chance |
| **S6** | Spearman with MBI / mRS (disability, not severity) | V1: MBI 0.159, mRS 0.057. V2: MBI −0.028, mRS −0.155. V3: MBI −0.103, mRS 0.205 |
| **S10** | Spearman(n_epochs, NIHSS): confound check | **0.004** (N 45). The number of clean epochs is unrelated to severity, so the recording-quality dependences found in Steps 3–7b are not a route by which severity could have been confounded |
| **S11** | Draft Ridge models (N 38) | spectral-lesion, 92 features: ρ −0.035, RMSE 3.18 vs dummy 3.10. Region-IC, 60 features: ρ −0.263, RMSE 3.16 vs 3.10 |

**Reading S1–S11 (descriptive, no claims):**
- **The null is robust.** No sensitivity analysis moves any association to the decision threshold (|ρ| ≥ 0.30), except Ridge models with negative out-of-fold ρ; that negativity is the CV artifact explained in section 2.
- **Every Ridge variant is worse than the dummy** (S1, S2, S3, S4, S8, S9, S11).
- **Quality adjustment changes nothing** (S1 ≈ primary). Excluding interpolation-flagged (S3) or motion-affected (S4) subjects changes nothing, nor does removing the near-duplicates (S9).
- **Lesion-site subgroups** (S2) show no consistent sign; infratentorial Ns of 13–16 are too small to interpret.
- **The largest descriptive association** is S8-V3 (extended-set D2 vs NIHSS, ρ = 0.264). It is below the 0.30 threshold, outside Holm, with no p-value, and it is one of many descriptive estimates. **It is not a finding** and must not be reported as one.

## 4. Interpretation (bounded)

1. **The registered result.** The pre-specified v3 tests detected no association between hemispheric EEG asymmetry and NIHSS: spectral asymmetry (pdBSI), lesion-aligned delta asymmetry, and noise-corrected hemispheric graph deformation (cross-half D2, as a scalar and as a Ridge model). This holds after the v3 pipeline fixes: re-referencing, ICA, marker-based epoching, averaged-spectrum features, debiased connectivity, cross-half deformation.
2. **What v3 established beyond v2 (label-free):** hemispheric deformation above estimation noise **is present** in most patients (Step 7b: edge D2 > 0 in 69–82% core / 96–98% extended), and connectivity exceeds the surrogate floor in most subjects (Step 4). The asymmetry is measurable, but its magnitude **does not track NIHSS** at detectable strength in this cohort.
3. **What is not ruled out:**
   - effects smaller than about ρ 0.41–0.51;
   - associations specific to subgroups the sample cannot resolve (for example cortical lesions, N 9);
   - associations with severity on a wider NIHSS range (this cohort has NIHSS 1–11, no severe cases);
   - associations with other outcomes.
4. **Limits carried forward:**
   - small N;
   - about 40% infratentorial lesions, where scalp asymmetry is expected to be weak;
   - lesion side from paralysis (7 uncertain);
   - unverifiable per-subject left/right trial order;
   - an EOG channel of uncertain type;
   - recording-quality dependence of some features (unrelated to NIHSS, S10).

## 5. v2 vs v3 side by side (S7)

v2 = frozen Phase 6 registry (`docs/PROGRESS.md`, v2 primary run; N 50 / 48). v3 = this report. Both families: Holm, signal = Holm p < 0.05 and |ρ| ≥ 0.30.

| v2 test | N | ρ | Raw p | Holm p | Decision | | v3 test | N | ρ | Raw p | Holm p | Decision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 signed spectral Ridge | 50 | −0.141 | 0.546 | 1.000 | no effect detected | | V1 pdBSI (3b, averaged spectra) | 45 | 0.006 | 0.967 | 1.000 | no effect detected |
| T2 absolute spectral Ridge | 50 | −0.222 | 0.809 | 1.000 | no effect detected | | V2 lesion-aligned delta asymmetry | 38 | −0.080 | 0.614 | 1.000 | no effect detected |
| T3 lesion-aligned spectral Ridge | 50 | −0.032 | 0.311 | 1.000 | no effect detected | | V3 cross-half core D2 (scalar) | 45 | 0.107 | 0.476 | 1.000 | no effect detected |
| T4 legacy graph Ridge | 50 | −0.248 | 0.902 | 1.000 | no effect detected | | V4 Ridge on 8 core cross-half D2 | 45 | −0.229 | 0.867 | 1.000 | no effect detected |
| T5 core graph G8f Ridge | 48 | 0.106 | 0.125 | 1.000 | no effect detected | | | | | | | |
| T6 expanded graph G24f Ridge | 48 | −0.062 | 0.371 | 1.000 | no effect detected | | | | | | | |
| T7 pdBSI association | 50 | 0.010 | 0.949 | 1.000 | no effect detected | | | | | | | |
| T8 DAR association | 50 | 0.166 | 0.268 | 1.000 | no effect detected | | | | | | | |
| T9 DTABR association | 50 | 0.213 | 0.150 | 1.000 | no effect detected | | | | | | | |

**Comparison:**
- **pdBSI** was tested in both (v2 T7 ρ 0.010; v3 V1 ρ 0.006). v3's pdBSI is computed from averaged spectra above the per-epoch noise floor (median 0.22 vs 0.35), yet the association with NIHSS is still about 0.
- **Graph tests** moved from plain wPLI at the noise floor (v2) to debiased connectivity with noise-free cross-half deformation (v3). Both are null.
- **v2 and v3 agree:** no hemispheric-asymmetry measure, before or after the pipeline corrections, showed a detectable association with NIHSS in the Figshare cohort.

## 6. Outputs

- **Kaggle zips** (`registry_v3_run.zip`, `sensitivities_v3_run.zip`): `registry_v3_results.csv`, `null_distributions.npz`, `sensitivity_results.csv`, `sensitivity_record.json`, run logs, and the PROGRESS lines.
- **Not committed:** these sit under the git-ignored `results/`. Committing small result summaries under a tracked `reports/v3/` folder is handoff Step 9 (reproducibility), not yet done.
