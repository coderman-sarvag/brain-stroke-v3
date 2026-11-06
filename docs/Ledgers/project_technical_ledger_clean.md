# Project Technical Ledger

**Current state:** 2026-10-21. Registered Figshare evaluation and all 19 descriptive sensitivities are complete and independently verified. No model qualifies for promotion. External NIHSS validation is blocked on compatible clinical targets and raw EEG/montage prerequisites.

## Authority, ownership and documentation

`EXECUTION_GUIDE_CURRENT.md` is operational authority, `AGENTS.md` contains repository rules, `docs/PROGRESS.md` contains current status/results and `docs/CONTEXT.md` is the concise AI handoff. This ledger describes current technical state; the timeline is append-only history. The original plan is archived at `docs/archive/PROJECT_EXECUTION_GUIDE_V1.md`; Group A's assignment remains unchanged.

Agrim is the sole owner and only required reviewer. His 2026-10-20 approval covers the final digest, freeze commit/tags and registered execution. No AI-family, other-group or multiple-review dependency remains. One owner record, `docs/reviews/registry_review.json`, binds identity/date/status/scope and limitation acknowledgements to the exact digest and tagged bytes. Historical supplied reviews preserve amendment rationale; they do not block ongoing development.

Redundant implementation/readiness/planning MD files were consolidated earlier. Current findings belong in existing progress/context/ledgers; distinct audit/QC/metadata/UCLH evidence and machine-consumed JSON retain specific purposes. No new planning MD was created for this work.

## Cohort, metadata and recording integrity

Figshare has 50 IDs: 33 mild (NIHSS 1-4), 17 moderate (5-11), no severe. Labels/metadata remain in `features/v2/subject_meta.csv` and never enter X. TSV asset 42345150 is version 5; JSON asset 38516579 occurs in versions 3-5 and matches the version 1 JSON checksum. All 50 version 1/version 5 paralysis sides agree. The dictionary establishes limb-paralysis side; prescribed contralateral mapping yields 22 left/28 right derived lesion sides. This is an assumption, not imaging confirmation. All 800 aligned AI values and three unchanged global features match construction; T3 was eligible. Sources/hashes are in `METADATA_AUDIT.md`.

Graph exclusions sub-13 (NIHSS 9) and sub-40 (NIHSS 6) are both moderate. Graph cohorts have 33 mild/15 moderate (68.75%/31.25%) versus 66%/34% in N=50: moderate prevalence decreases by 2.75 percentage points. This disclosure did not alter eligibility/features.

The label-blind raw audit checked all 33 EDF channels and every one of 160,000 samples/channel at 500 Hz for 04/05, 11/15 and 47/49. All 32 named channels for 04/05 are exactly identical; the unnamed channel differs. Other pairs have only constant CPz exactly equal; nonconstant named-channel correlations are approximately .99937-.999997 and .99955-.999997. No complete EDF pair has identical all-channel values or file hashes.

Age/location differ within all pairs; sex also differs for 04/05. Stored age/sex/location/duration/handedness agree with source metadata, so this is not a local transcription discrepancy. IDs were retained by owner decision. Source identity, independence and individual-level permutation exchangeability remain unresolved. The audit did not inspect pair outcomes. Source/config/per-channel evidence is in `RECORDING_INTEGRITY_AUDIT_V2.md`/`.json`.

## Feature state and limitations

Legacy v1 source/features/results remain frozen. Legacy spectral classification was weak near dummy; v1 graph features had epoch-count dependence. No legacy feature was overwritten.

- Spectral absolute and lesion-aligned: 50 subjects, 19 features plus ID.
- G8f: primary, eight core channels, four homologous pairs, 15 fixed epochs, 16 features.
- G24f: secondary T6, 22 channels/11 pairs despite the historical name, six fixed epochs, 16 features.
- Both graph tables contain 48 subjects.
- Bands: delta 1-4, theta 4-8, alpha 8-13, beta 13-30 Hz.
- Graph metrics: absolute efficiency/clustering asymmetry, homotopic wPLI and normalized aligned Frobenius distance.
- The corrected 150-microvolt screen restricts the sampling pool before spectra/subsampling. Fixed-size sampling is without replacement, with 100 deterministic draws and median adjacency.
- All nine graph/lesion tests pass; residual epoch-count correlation and second-seed instability remain disclosed.
- Four sidecars, feature manifest/changelog/handoff exist; all 19 original Group A byte hashes remain bound. Full EEG feature regeneration was not repeated locally.

The owner confirms the local processed epochs and other computer's clean folder are the same data stored at different paths. Reproduction still needs explicit local path mapping; an aggregate hash is not individual cross-computer reconciliation.

## Registered statistical specification

The frozen nine-test family is T1 signed spectral Ridge, T2 absolute spectral, T3 lesion-aligned spectral, T4 legacy graph, T5 G8f, T6 G24f, and T7-T9 direct pdBSI/DAR/DTABR associations with NIHSS. T1-T4/T7-T9 have N=50; T5/T6 have N=48. Feature whitelists and exact membership are in `configs/registry_v1.json`.

Standardized Ridge uses 20 ascending alphas from .01 to 1000, inner five-fold shuffled KFold seed 42 with fold-local scaling, and outer five-fold/ten-repeat stratified CV. NIHSS is the target; severity only stratifies and supplies descriptive binary AUC. The optimized SVD alpha path is equivalent to full-pipeline GridSearchCV. The statistic averages ten pooled OOF Spearman values; repeat predictions are not treated as independent people.

Each test uses 1,000 permutations with plus-one/tie-inclusive p-values. Predictive tests are upper-tail; direct associations are two-sided. Predictive permutations jointly shuffle target/class, regenerate folds and refit the complete nested procedure. Seeds are 42000+test number; bootstrap seeds 52000+test number. Holm spans all nine tests. Signal requires adjusted p<.05 plus rho>=.30 (absolute rho for direct associations). Required failures withhold family decisions. Only qualifying T1-T6 can promote a full-cohort refit.

The 2,000-draw subject-row percentile bootstrap is descriptive and conditions on saved OOF predictions for predictive tests; it omits model-refitting uncertainty. Undefined draws are counted without redraw; above 1% invalid makes the interval unavailable. All actual primary intervals are available with zero invalid draws.

## Synthetic validation and immutable freeze

The supplied independent review attributed the original moderate positive-control p=.011988 (rho=.333647) to a sensitivity/power mismatch, not a found result-changing code defect. The user adopted Option 3 before new simulations and real evaluation. Failed reduced/full controls and the prior strong diagnostic remain preserved.

Gate A: population Pearson r=.95, seed 81000, 199 permutations, two outer repeats; observed Spearman .829916, p=.005, PASS. Gate B: 200 r=.65 datasets, seeds 83000-83199, 200 permutations/two repeats each, operational acceptance 50-95% raw-p<.05 detection; 168/200=.84, exact binomial 95% CI [78.1701%,88.7913%], PASS. All 201 p-values were recomputed from saved nulls. These diagnostics do not estimate ten-repeat Holm power; the 95% upper bound is an adopted operational criterion, not a theoretical limit.

Prior null calibration: 3/100 detections, passed; all nine shuffled smoke tests passed. Frozen `REGISTRY_VALIDATION_RESULTS.json` retains acceptance=true and its freeze-time 32-test evidence. The full Option 3 report hash is `99793e1bf69909388dc6987488d1bea8f03ca33224e6c8a783a6b6c0178ff27c`; dataset/null/checkpoint evidence remains under `results/v2/validation/`.

Current expanded suite: **47 tests passed in 29.848 seconds**. This adds seven sensitivity and eight continuation tests; no frozen validation evidence was edited to update counts. Tests cover fold-local fitting/GridSearch equivalence, full-family failure handling, dirty source/staged/untracked files, CRLF portability, tampering, grouped split isolation and deterministic continuation equivalence.

Current snapshot: 42 artifacts, digest `57044770c2e18c0fb31929a569cbd8523946e955c06152304d3d758d3e07f898`. It binds the frozen registry/config, evaluation code/tests, validation/amendment/review evidence, legacy inputs, and Group A manifest/all 19 artifacts with original `source_sha256` bindings. Both annotated `registry-v1` and `features-v2` point to `42ff54d`. Snapshot self-check and actual execution guards pass.

The guard requires a clean committed src/config/tests tree and verifies tagged content and owner approval before labels. Schema 2 normalizes only UTF-8 CRLF to LF; no content/whitespace/value change is exempt. Later sensitivity/recovery files are separate, committed and provenance-bound; no frozen scientific artifact changed.

## Interruption recovery and completed primary results

The first job `primary_20261020` saved T1-T5 before its process/session ended. Its running status is stale; original files are preserved. The continuation adapter at `src/continue_registry_v2.py` checks original settings, package versions, source/input identity, contracts, OOF folds/coverage, targets/classes, metrics/alphas, nulls and bootstrap arrays. Initial interrupted metadata mixes canonical legacy and byte-hashed feature entries; recovery honors the existing LF-normalization rule.

It copies the validated ordered prefix byte-for-byte into a new directory and invokes the unchanged frozen runner for missing tests, full Holm correction and the original promotion rule. Synthetic interrupted/uninterrupted outputs are identical; corruption/settings/version/input changes fail. Original hashes are checked before/after and saved in `continuation.json`; temporary function bindings are restored even after errors.

Recovery commit: `9c4d11b`; Git's configured GPG keybox service failed, so this commit used a command-local unsigned exception without changing configuration/tags. Completed primary: `results/v2/runs/primary_20261021_continued`, 2026-10-21T11:33:48.707216Z through 11:42:32.071276Z. All original files and reused T1-T5 files remain byte-identical.

| Test | N | Rho | Raw p | Holm p |
|---|---:|---:|---:|---:|
| T1 | 50 | -.141440 | .545455 | 1.000 |
| T2 | 50 | -.222041 | .809191 | 1.000 |
| T3 | 50 | -.032221 | .310689 | 1.000 |
| T4 | 50 | -.248141 | .902098 | 1.000 |
| T5 | 48 | .105778 | .124875 | 1.000 |
| T6 | 48 | -.061517 | .370629 | 1.000 |
| T7 | 50 | .010129 | .949051 | 1.000 |
| T8 | 50 | .165713 | .267732 | 1.000 |
| T9 | 50 | .212802 | .149850 | 1.000 |

All nine decisions are `no_effect_detected`; no computational failure and no promoted model. All adjusted p-values cap at one because even the smallest raw p multiplied by nine exceeds one. All six Ridge RMSE values exceed their matched dummy. T1-T4 model RMSE: 2.888705, 2.885206, 2.986104, 2.858342 versus dummy 2.843249; T5/T6: 2.891687/2.856732 versus dummy 2.800602. G8f descriptive AUC=.551717.

Independent checks recomputed all nine Spearman values using SciPy, null-distribution p-values, bootstrap limits, full Holm decisions, saved metrics/folds and model eligibility. Negative predictive rhos are performance findings, not inverse clinical effects. Different N prevents inferential feature-set improvement claims. No effect detected does not establish all effects are zero.

## Completed descriptive sensitivities

Implementation `src/run_sensitivities_v2.py`, config `configs/sensitivities_v2.json`, tests `tests/test_sensitivities_v2.py`, committed at `f6fd0c3`. Completed run: `results/v2/sensitivities/robustness_20261021`, 2026-10-21T11:43:45.465237Z through 11:47:38.392863Z. All 19 analyses completed without failures after primary verification.

Six grouped Ridge analyses retain all subjects/features and group 04/05, 11/15, 47/49 in both CV levels. Groups never enter X. There are 47 groups at N=50 and 45 at N=48. Outer five-fold seeds are 42+r for ten repeats; inner five-fold seeds are 10042+5*r+f. Explicit Pipeline/GridSearchCV preserves the original alpha grid and fold-local scaling. Exact class balance is not guaranteed; saved counts and all ten distinct partitions were verified. No seed search or rejection sampling occurred.

| Test | Primary rho | Grouped rho | Primary minus grouped | Absolute delta > .05 |
|---|---:|---:|---:|---|
| T1 | -.141440 | -.089932 | -.051508 | Yes |
| T2 | -.222041 | -.173280 | -.048760 | No |
| T3 | -.032221 | -.027410 | -.004811 | No |
| T4 | -.248141 | -.183784 | -.064357 | Yes |
| T5 | .105778 | .099367 | .006411 | No |
| T6 | -.061517 | -.028931 | -.032586 | No |

The descriptive materiality flags affect T1/T4, whose negative rhos become less negative. G8f changes little. These differences reflect both grouping and training-fold changes; they do not isolate leakage bias, prove independence or validate individual-level permutation exchangeability.

The other 13 sensitivities are fixed RBF SVR (C=1, epsilon=.1, gamma=scale) and shallow RF (300 trees, depth=3, seed42) for all six predictive sets, plus combined absolute spectral/G8f Ridge (N=48, 35 features). Alternative models use exact primary subject sets/folds; combined inputs join by ID. All 19 sensitivity RMSE values exceed their matched dummy. Some MAE/AUC improve: G8f SVR rho=.208508, AUC=.618990, MAE=2.061930 versus dummy 2.207692, but RMSE=2.842243 versus 2.800602. G24f RF AUC=.636768, rho=.149340. Combined Ridge rho=-.172080, RMSE=2.939705 versus 2.800602.

Independent checks verified all 19 rhos, primary/input/source hashes, OOF coverage, matching alternative folds/dummy predictions, all grouped inner/outer seeded partitions, class/group counts and materiality calculations. These analyses have no p-values/CIs/significance claims and cannot change primary decisions or promote a model.

## Outputs and runtime reproducibility

- Primary CSV: `results/v2/runs/primary_20261021_continued/registry_results.csv`; SHA-256 `82815fc03ff71ba8131236d903e03ab68af6aeefe1b6d804b87c820a412c08dd`.
- Sensitivity CSV: `results/v2/sensitivities/robustness_20261021/sensitivity_results.csv`; SHA-256 `0ad8c1a2eba53a9e8e75c8c72e2a1699a6be4f4892549d03b324a419b270c901`.
- Figure: `results/v2/figures/primary_20261021_overview.png`; SHA-256 `6a951dd4db87461b0062d8699aac0c10db6e2bede9700385659bd9bc5ee5e5bb`.
- Explained report: `results/v2/figures/figshare_v2_results_explained.pdf`; eight pages, 184,207 bytes; SHA-256 `4652b678130b9c5e6c51ff98ab5a5a147555c2b35154a093f015ec6512f53168`. It is generated entirely from the frozen primary/sensitivity CSVs and existing overview PNG. It defines NIHSS, T1-T9, OOF/nested CV, Spearman rho, permutation and Holm p-values, bootstrap intervals, RMSE, MAE, R-squared, ROC-AUC and the dummy comparator, then connects each definition to the observed values. No analysis or model was rerun.
- Per-test null/bootstrap arrays, OOF predictions/folds/targets, metrics, alpha selections, contracts and grouped audits remain saved. No jobs remain active and no model was exported.
- Results are local and Git-ignored. Preserve these directories; tracked documentation records their paths/digests.

Actual execution: Python 3.13.2, NumPy 2.2.5, SciPy 1.18.1, pandas 2.2.3, sklearn 1.9.1, joblib 1.6.0, threadpoolctl 3.7.0, matplotlib 3.10.1. OPENBLAS_NUM_THREADS, MKL_NUM_THREADS and OMP_NUM_THREADS were one. `requirements.txt` lists different NumPy/pandas/matplotlib versions; the recorded runtime above and run metadata describe the actual analysis environment. No environment upgrade was performed during evaluation.

## UCLH prerequisites and next scientific decision

Upstream source audit is pinned to `52ad25a8cb8ecae867cd8fb9984b4fbe703585c4`; hashes/sources are in the existing UCLH docs. Zenodo concept DOI 836841 describes volunteers, version 1199523; patient archives are 1199529/1199630, radiology 1215676, code release 1035910. Checked records return CC BY 4.0.

Source verification establishes 32 EEG channels plus STATUS, 33 electrode entries including NFpz, 16384 Hz/common-CMS metadata, and no O1/O2. Exact G8f overlap is three pairs/six channels; I1/O9 and I2/O10 are distinct labels. CMS is NFpz; DRL NFp2. The extractor uses trigger-derived pre/post-injection portions, 2-200 Hz filtering and a 49-51 Hz stop band without explicit rereferencing. A 2 Hz high-pass is incompatible with assuming unchanged 1-4 Hz delta features. Publication MF/TD durations concern EIT, not guaranteed usable EEG seconds. Eye condition, effective reference and actual clean epoch counts remain unverified.

External NIHSS validation is BLOCKED: the public participant table has ID/age/sex/group, not NIHSS; compatible clinical-target availability is not established. No local raw BDF, common-montage config or UCLH implementation was found. A different clinical task or montage requires a separate explicit contract; subtype/healthy labels cannot substitute for severity. No raw archive or EEG was downloaded/evaluated.

Next work is final scientific write-up using the existing evidence, then resolution of a compatible externally labelled cohort before any new common-montage pipeline/validation. Small sample/no severe class, unresolved dependence, assumed lesion mapping, graph instability/epoch bias and transfer mismatches must accompany the findings. Further outcome-driven tuning on these 50 subjects is not authorized by a null result.
