# Project Progress

**Updated:** 2026-10-21. Authority: [EXECUTION_GUIDE_CURRENT.md](../EXECUTION_GUIDE_CURRENT.md). Handoff: [CONTEXT.md](CONTEXT.md). Historical events: `Ledgers/project_timeline_ledger_clean.md`; current technical detail: `Ledgers/project_technical_ledger_clean.md`.

## Current status

| Work | Status | Evidence / next action |
|---|---|---|
| Legacy baseline | DONE; frozen | Preserve legacy code, features and results |
| A0-A2 metadata/spectral v2 | DONE | Authenticated side semantics and 50-subject spectral tables; contralateral lesion mapping remains an assumption |
| A3-A6 graph v2 | DONE WITH FLAGS | Corrected screen/sampling, 48-subject tables, provenance/QC; disclose residual epoch bias/instability |
| B1 registry and feature freeze | DONE | Both annotated tags at `42ff54d`; approved 42-artifact digest unchanged |
| B2/B3 evaluation and statistics | DONE | Synthetic validation passed; expanded suite 47/47; all nine real tests verified |
| Registered descriptive robustness | DONE | All 19 analyses in `robustness_20261021` completed and independently checked |
| Phase 6 Figshare evaluation/reporting | COMPLETE FOR REGISTERED SCOPE | No predictive model qualifies for promotion; results and figure saved |
| Phase 7 external NIHSS validation | BLOCKED | Establish compatible clinical labels and raw EEG/common-montage compatibility |

## v3 flowchart-compliant pipeline (branch `fix/flowchart-pipeline`)

v3 is a new pre-specified exploratory pipeline designed after the v2 null result to fix documented pipeline defects and complete missing flowchart stages. v1/v2 files, results and decisions are untouched.

| Step | Status | Evidence / next action |
|---|---|---|
| 0 Environment and Figshare data | DONE 2026-11-06 | 11 files md5-verified via API; 50/50 EDFs 500 Hz, 33 ch, 40 imagery events (20/20), CPz constant 0; 6/6 tests. [Report](V3_STEP0_REPORT.md) |
| 1 Data integrity | DONE 2026-11-06 | sub-04/05 identical → both excluded (user decision), N=48; 11/15, 47/49 grouped. Marker channel shows sidecar misaligned in 15/50 (sub-06 up to 1.66 s); 40 usable marker-matched trials per subject. Lesion side 18 L / 23 R / 7 uncertain (N=48). EOG HEOR vs sidecar VEOR unverified. Rest data absent (closed). [Report](V3_STEP1_REPORT.md) |
| 2 Preprocessing | DONE 2026-11-06 | Final Kaggle run (commit 2f28f05, 48/48 ok): rule (iii) + ≥ 10 epochs per class → **N = 45** (sub-06, sub-27, sub-40 excluded), 1,592 epochs, median 37/subject. CPz non-zero 48/48; no zero-channel interpolation; ICA halves frontal-asymmetry/EOG coupling (F3/F4–HEOL delta median abs rho .288 → .165; > .3 in 19 → 9 subjects). Missing analysed pairs: sub-13 O1–O2, sub-29/30 T7–T8, sub-31 C3–C4. Epoch files live in the Kaggle notebook output. [Report](V3_STEP2_REPORT.md), [deviations](V3_HANDOFF_DEVIATIONS.md) |
| 3 Multi-band representation | DONE 2026-11-06 | Kaggle run (commit def7d1a, 13 s, input = saved Step 2 notebook output): `spectral_v3.csv` 45 × 139, `spectral_lesion_v3.csv` 38 × 92; bins 12/16/20/68; all values finite; NaN only for the 4 unavailable pairs; no doubly-interpolated pair. QC: 11/139 features with abs rho ≥ .3 vs epoch count, all negative (DAR −.55, DTABR −.48, pdBSI −.42), to be handled in the Step 8 registry design. [Report](V3_STEP3_REPORT.md) |
| 3b Spectral fix (D15) | DONE 2026-11-06 | Kaggle (commit 9346c47): pdBSI .315–.500 (median .350) → **.149–.479 (median .222)**, above the about .10 floor; rank agreement with Step 3 rho .94. Step 3 reproduced byte-identically by the refactored code. Epoch-count features with abs rho ≥ .3: 11 → 5. What remains is a quality effect: DAR −.51, DTABR −.48, mabsAI beta −.41, FT7FT8 beta −.39, pdBSI −.30 (for the Step 8 registry). 3b synthetic tests written but not yet run. `spectral_v3b.csv` is the feature table going forward. [Report](V3_STEP3B_REPORT.md) |
| 4 Functional connectivity | CODE DONE, run pending | `src/connectivity_v3.py` + `configs/v3/connectivity.json`: 2 s segments (2 per epoch, both classes pooled, D16), wpli2_debiased multitaper (2 Hz bandwidth; bins 6/8/10/34), extended 22-channel (231 edges) and core 8 (28 edges) tables with raw values; NaN rule extends D14; one-interpolated-endpoint flags; 200-derangement surrogate noise floor for homotopic edges; segment-count correlations; resumable per subject. Not tested locally (per instruction). **Next:** Kaggle run → Step 4 report |

## Registered primary results

Completed run: [primary results CSV](../results/v2/runs/primary_20261021_continued/registry_results.csv). All tests succeeded computationally; every decision is `no_effect_detected` and every Holm-adjusted p is 1.000.

| Test | N | Rho | Raw p | Holm p |
|---|---:|---:|---:|---:|
| T1 Signed spectral Ridge | 50 | -0.1414 | 0.5455 | 1.0000 |
| T2 Absolute spectral Ridge | 50 | -0.2220 | 0.8092 | 1.0000 |
| T3 Lesion-aligned Ridge | 50 | -0.0322 | 0.3107 | 1.0000 |
| T4 Legacy graph Ridge | 50 | -0.2481 | 0.9021 | 1.0000 |
| T5 Core graph G8f Ridge | 48 | 0.1058 | 0.1249 | 1.0000 |
| T6 Expanded graph G24f Ridge | 48 | -0.0615 | 0.3706 | 1.0000 |
| T7 pdBSI association | 50 | 0.0101 | 0.9491 | 1.0000 |
| T8 DAR association | 50 | 0.1657 | 0.2677 | 1.0000 |
| T9 DTABR association | 50 | 0.2128 | 0.1499 | 1.0000 |

Every primary Ridge model has higher RMSE than its matched training-mean dummy. G8f RMSE is 2.8917 versus 2.8006 for its dummy; descriptive AUC is .5517. No model was exported. These findings provide no registered evidence of useful NIHSS prediction or the specified direct associations; they do not establish that all smaller effects are absent.

## Descriptive robustness

Completed [sensitivity results CSV](../results/v2/sensitivities/robustness_20261021/sensitivity_results.csv): six pair-grouped Ridge, six fixed SVR, six fixed random forest and one combined absolute-spectral/G8f Ridge. No p-values, confidence intervals or model promotions were generated for these analyses.

| Feature set | Primary rho | Pair-grouped rho | Primary minus grouped | Absolute delta > .05 |
|---|---:|---:|---:|---|
| T1 Signed spectral | -0.1414 | -0.0899 | -0.0515 | Yes |
| T2 Absolute spectral | -0.2220 | -0.1733 | -0.0488 | No |
| T3 Lesion-aligned | -0.0322 | -0.0274 | -0.0048 | No |
| T4 Legacy graph | -0.2481 | -0.1838 | -0.0644 | Yes |
| T5 G8f | 0.1058 | 0.0994 | 0.0064 | No |
| T6 G24f | -0.0615 | -0.0289 | -0.0326 | No |

All grouped analyses retain their primary subjects, keep known pairs together in both CV levels and have ten distinct outer partitions. Grouping does not establish recording independence or repair primary permutation exchangeability. Deltas also reflect changed folds/training composition.

All 19 sensitivity RMSE values exceed their matching dummy. Some fixed SVR/RF runs have better MAE or descriptive AUC: G8f SVR rho=.2085, AUC=.6190, MAE=2.0619 versus dummy 2.2077, but RMSE=2.8422 versus dummy 2.8006. G24f RF has AUC=.6368 and rho=.1493. Combined Ridge rho=-.1721, RMSE=2.9397 versus dummy 2.8006. These descriptive findings do not alter registered decisions.

Saved [results figure](../results/v2/figures/primary_20261021_overview.png) compares the nine registered results and pair-grouped predictions. An eight-page [explained results PDF](../results/v2/figures/figshare_v2_results_explained.pdf) adds the cohort composition, test map, metric definitions, exact T1-T9 values, Ridge-versus-dummy RMSE chart, robustness interpretation and conclusion without rerunning or changing any analysis.

## Verification and preserved execution history

- Synthetic acceptance: Gate A p=.005; Gate B 168/200 (84%; exact 95% CI 78.17-88.79%). Original failed controls remain preserved in the frozen validation evidence.
- Full suite: 47 tests passed in 29.848 seconds, including eight continuation and seven sensitivity tests.
- The 42-artifact snapshot self-check and actual freeze guards pass. Digest: `57044770c2e18c0fb31929a569cbd8523946e955c06152304d3d758d3e07f898`.
- The first job stopped after saving T1-T5. `continue_registry_v2.py` used the frozen runner to compute T6-T9 and finalize the family in a new directory. All original files and reused test files remain byte-identical; provenance is in the new run's `continuation.json`.
- Independent checks covered all nine SciPy Spearman values, permutation p-values, bootstrap limits, Holm decisions, metrics/folds and promotion eligibility; all 19 sensitivity statistics, saved input hashes, group separation, inner/outer split seeds, class/group counts and matched alternative-model folds also passed.
- Primary CSV SHA-256: `82815fc03ff71ba8131236d903e03ab68af6aeefe1b6d804b87c820a412c08dd`. Sensitivity CSV SHA-256: `0ad8c1a2eba53a9e8e75c8c72e2a1699a6be4f4892549d03b324a419b270c901`.
- Freeze commit `42ff54d`; sensitivity implementation `f6fd0c3`; recovery implementation `9c4d11b`. GPG keybox service failed for recovery, so that commit used a command-local unsigned exception. Existing tags/configuration were preserved.
- No analysis jobs remain active. Results are saved locally under the Git-ignored `results/` directory; documentation records their paths and digests.

## Fixed constraints and next major work

Agrim is the sole owner/reviewer; approvals from 2026-10-20 persist. Group A will not return. The cohort has 33 mild, 17 moderate and no severe subjects; the graph exclusions sub-13/sub-40 are both moderate. Retain 04/05, 11/15 and 47/49 as distinct IDs with the documented dependence limitation. G24f is secondary registered T6. Frozen protocol, features and findings must be preserved; no repeated tuning against this cohort.

1. Use the completed tables/figure and technical ledger for the final methods/results/limitations write-up.
2. Resolve external clinical-target availability. UCLH's public participant TSV has no NIHSS field; stroke subtype/healthy status is not a severity substitute.
3. Only after a compatible target is established, verify raw EEG duration/reference/preprocessing and define a separate common-montage contract. O1/O2 are absent and upstream extraction uses a 2 Hz high-pass. See `UCLH_AUDIT.md` and `UCLH_MONTAGE.md`.

## Invocation audit

- Registry invocation 2026-10-20T12:56:33.499416+00:00: START real run=primary_20261020; rerun_reason=None
- Registry invocation 2026-10-21T11:33:43.471806+00:00: START real run=primary_20261021_continued; rerun_reason='Previous process ended after saved T1-T5 during the session break; preserve verified prefix and complete missing T6-T9 with unchanged frozen settings.'
- Registry invocation 2026-10-21T11:42:32.077248+00:00: COMPLETE real run=primary_20261021_continued; outputs=results\v2\runs\primary_20261021_continued
