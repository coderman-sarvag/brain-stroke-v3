# Project Timeline Ledger

## Purpose

This ledger records the project's evolution in chronological order. It preserves major states, decisions, milestones, discoveries, and changes in direction. It is historical: later changes do not rewrite earlier states.

---

## State 0 — Initial Project State

**Project:** EEG-based machine-learning study for stroke-severity classification.

**Research objective:** Predict stroke severity from EEG patterns. The initial target framework was NIHSS-derived severity classes: mild, moderate, and severe. The central hypothesis was that interhemispheric asymmetry in EEG spectral power could act as a biomarker of clinically assessed stroke severity.

**Initial pipeline state:**
- Figshare stroke EEG dataset was the primary dataset.
- UCLH stroke EEG data was planned for later external validation.
- Data acquisition, preprocessing/epoching, spectral feature extraction, patient-level aggregation, and NIHSS label merging were already completed for Figshare.
- `features/figshare_features.csv` existed as the modeling-ready table.
- Modeling and evaluation had not yet been performed.

The project was therefore a research/analysis pipeline rather than a finished model or deployed application.

---

## State 1 — Pre-Phase-5 Dataset Audit

The Figshare feature tables were audited before modeling.

**Verified dataset state:**
- `features/figshare_features.csv`: 50 rows × 63 columns, 50 unique subjects.
- `features/figshare_patient_features.csv`: 50 rows × 61 columns, 50 unique subjects.
- No missing values, infinite values, duplicate subjects, or constant columns were found.
- The modeling table was identified as `figshare_features.csv` because it contains the merged labels.

**Feature-scope decision:** The Phase 5 model input was fixed to exactly 19 `all_*` engineered features:
16 interhemispheric spectral asymmetry features across four bands and four homologous channel pairs, plus `all_pdBSI`, `all_DAR`, and `all_DTABR`. Hand-specific feature groups and epoch-count columns were excluded.

A leakage concern around epoch-count features was identified and resolved by excluding them from the model input.

---

## State 2 — Phase 5 Model Design and Implementation

`src/train_models.py` was created as the Phase 5 modeling pipeline.

The benchmark was expanded to include logistic regression alongside SVM, KNN, and Random Forest models. The candidate set became 20 variants including the dummy baseline.

Key implementation decisions were fixed before the canonical run:
- repeated stratified 5-fold cross-validation;
- seed 42 and 10 repeats for the canonical experiment;
- preprocessing and feature selection inside sklearn pipelines;
- binary ROC-AUC scoring;
- both KBest-selected and all-19-feature variants;
- a separate 3-feature global representation;
- explicit model/feature-set naming;
- model export and metadata generation;
- exploratory confusion-matrix and feature-importance outputs.

---

## State 3 — Phase 5 Review and Data Validation

Independent review identified several implementation and scientific safeguards that needed to be addressed before trusting the experiment.

The project adopted the following corrections:
- saved SVC configuration should match the CV-evaluated configuration;
- CV should fail explicitly on invalid folds/configurations;
- class-count and KNN fold-size checks should be performed before CV;
- non-canonical runs should be clearly identified;
- post-selection confusion matrices and full-data importance plots should be treated as exploratory/descriptive;
- saved-model metadata should include a feature-construction contract sufficient for later UCLH reuse.

The NIHSS audit was then completed:

| Severity class | Subjects | NIHSS range |
|---|---:|---:|
| mild | 33 | 1–4 |
| moderate | 17 | 5–11 |
| severe | 0 | none |

The observed data therefore supports a binary mild-vs-moderate Phase 5 problem. No severe subjects are present in the Figshare cohort.

---

## State 4 — Canonical Spectral Benchmark Completed

The canonical Phase 5 experiment was run using 5-fold repeated stratified CV with 10 repeats and seed 42.

**Dummy baseline:**
- macro-F1: 0.397059
- balanced accuracy: 0.500000
- ROC-AUC: 0.500000

**Best macro-F1 result:** `knn5_kbest8`
- macro-F1: 0.499927 ± 0.157864
- balanced accuracy: 0.520476 ± 0.142947
- ROC-AUC: 0.492738 ± 0.210890

**Highest ROC-AUC result:** `logreg_l2_global3`
- macro-F1: 0.477291 ± 0.137659
- balanced accuracy: 0.487619 ± 0.139610
- ROC-AUC: 0.584405 ± 0.173687

The spectral feature family therefore did not demonstrate strong or stable classification performance. The scores remain close to the dummy baseline and have high fold-to-fold variability.

This result established spectral asymmetry as the baseline to beat rather than motivating additional post-hoc hyperparameter tuning.

---

## State 5 — Second Feature Family Added: Graph/Connectivity Branch

The research scope was expanded with a second EEG feature family based on functional connectivity and hemispheric graph structure.

A read-only dataset audit established:
- 30 EEG channels are present in the preprocessed epochs.
- The montage contains 12 left-hemisphere, 12 right-hemisphere, and 6 midline channels.
- 12 homologous left/right channel pairs are available.
- Stored `*-epo.fif` files retain full-channel time-domain epoch signals, so graph connectivity can operate on those epochs without re-epoching.

A major artifact-quality risk was identified: the existing feature workflow is centered on eight core channels, so previously unused peripheral channels may not have equivalent artifact validation.

The graph branch was therefore deliberately restricted to the same eight core channels:
F3, C3, P3, O1 and F4, C4, P4, O2.

The approved graph pipeline is:

**band-limited epochs → wPLI connectivity → left/right hemispheric graphs → homologous pairing/deformation → compact network-level features**

The planned graph representation contains 16 subject-level features across delta, theta, alpha, and beta:
- global-efficiency asymmetry;
- mean clustering-coefficient asymmetry;
- mean homotopic connectivity;
- normalized left/right Frobenius-distance.

The intended later ablation is:
1. spectral-only (19 features);
2. graph-only (16 features);
3. combined spectral + graph (35 features).

External UCLH validation remains downstream of this comparison.

---

## State 6 — Current Project Position

The project has moved from the completed spectral baseline into the graph/connectivity branch.

The current research progression is:

**Figshare preprocessing and spectral features → spectral ML benchmark completed → graph feature branch designed/audited → graph feature extractor implemented → execution and ablation next → UCLH external validation later.**

No claim has yet been made that graph features improve classification; that is the purpose of the next experiment.

---

## State 7 — Graph Feature Extractor Implemented

`src/graph_features.py` was created as the Phase 3b graph feature pipeline.

**Implementation decisions fixed:**

- Node set restricted to the same 8 channels used by the spectral pipeline (F3, C3, P3, O1 | F4, C4, P4, O2), matching the channels with established artifact quality and maximising UCLH montage compatibility.
- wPLI computed with `mne_connectivity.spectral_connectivity_epochs`, `method='wpli'`, `mode='multitaper'`, `faverage=True` (band-averaged scalar per channel pair).
- Adjacency matrices (8×8) are symmetrised and diagonal-zeroed before sub-matrix extraction.
- Left sub-matrix: rows/cols 0–3; right sub-matrix: rows/cols 4–7; homotopic block: cross-hemisphere off-diagonal elements.
- Graph metrics use NetworkX: global efficiency (Dijkstra on 1/weight distances), mean weighted clustering coefficient (Onnela et al. 2005 geometric-mean formulation).
- All asymmetry features use the same AI formula as the spectral pipeline: (L − R) / (L + R), with a safe-divide fallback of 0.0.
- Frobenius distance is normalised: ‖A_L − A_R‖_F / (‖A_L‖_F + ‖A_R‖_F).
- Sampling-rate guard: raises if sfreq deviates more than 1 Hz from 500 Hz.
- Per-subject failures are logged and reported without aborting the batch.
- The 16 canonical feature names are defined in the module constant `GRAPH_FEATURE_NAMES` (deterministic order: delta/theta/alpha/beta × GlobalEff_AI/ClustCoeff_AI/MeanHomotopic/FrobeniusDist).

**Outputs (written at runtime):**

- `features/figshare_graph_features.csv` — 50 rows × 17 columns (subject_id + 16 features).
- `features/figshare_combined_features.csv` — inner join of spectral CSV and graph CSV on subject_id; retains all spectral columns (including severity_class) plus the 16 graph features.

The script has not yet been executed. Execution and output verification are the next step.

---

## State 8 — Graph CSV Validation and Bias Discovery

An independent read-only audit of the generated graph features revealed the following:
- **Graph CSV Sanity:** Zero NaN/inf counts, no constant columns, and plausible feature value ranges.
- **Epoch-count Bias:** `MeanHomotopic` features are strongly negatively correlated (up to -0.58) with `n_epochs_all`. `graph_features.py` utilizes the standard `wpli` method without addressing the epoch-count bias (no epoch balancing/sub-sampling was implemented).
- **Metadata Availability:** `participants.tsv` is missing from the repository, so patient lesion side, stroke type, and lesion location metadata cannot be verified.
- **UCLH Labels:** External UCLH labels available are verified as Stroke vs Control and NIHSS, while lesion side remains unverified.

---

## State 9 — Group A v2 Completion and Documentation Reconciliation

**Date:** 2026-10-17

Group A completed A0-A6 of the label-blind v2 feature track:

- located `data/raw/figshare/participants.tsv` and its metadata description;
- documented paralysis-side semantics and the contralateral lesion-side mapping (22 left, 28 right);
- generated the 50-subject absolute and lesion-aligned spectral tables with sidecars;
- locked G8f at `N_fixed=15` and secondary G24f at `N_fixed=6` using channel quality and epoch counts only;
- implemented and synthetically tested `src/graph_features_v2.py`;
- generated 48-subject G8f and G24f tables after excluding `sub-13` and `sub-40` for insufficient usable epochs;
- documented finite-value, range, collinearity, epoch-bias, and second-seed stability checks in `docs/FEATURE_QC_V2.md`.

The active work moved to Phase 6: Group B registry, review, freeze, and one-shot evaluation preparation. Real-label v2 evaluation remains prohibited until its prerequisites are complete.

The documentation hierarchy was also reconciled:

- `EXECUTION_GUIDE_CURRENT.md` remains the main source of truth;
- `docs/CONTEXT.md` is the prompt-handoff document and now contains only the current context;
- duplicated obsolete sections were removed from `AGENTS.md`, `docs/CONTEXT.md`, and `docs/PROGRESS.md`;
- the original plan was moved to `docs/archive/PROJECT_EXECUTION_GUIDE_V1.md` as a historical artifact;
- `EXECUTION_GUIDE_GROUP_A_FEATURES.md` was retained unchanged by explicit instruction;
- the technical ledger was rewritten to reflect the current v2 state.

---

## State 10 — Participant Metadata Provenance Reopened

**Date:** 2026-10-17

Review found that the file named `data/raw/figshare/participants.tsv` contains 120 event records, not the participant columns claimed in the prior audit. The user reported that the event file had been renamed to `participants.tsv`; the rename history was not independently verified. The cited `participants.json` is absent, and the audit script does not read it to check field semantics. Earlier timeline entries include conflicting claims about metadata availability; State 9's assertion of verified semantics is superseded by this finding.

The derived subject metadata and lesion-aligned table remain in place, but their source and lesion-side semantics are unverified. A0 and A2/T3 eligibility are blocked pending recovery of source metadata, a data dictionary, and reconciliation of derived values. The current guide, metadata audit, progress, handoff, and technical ledger were corrected. No feature files or labels were changed or evaluated.

---

## State 11 — UCLH Handoff Documents Imported

**Date:** 2026-10-17

The user supplied B4 UCLH audit and montage documents and reported that their channel information had been sent to Group A, followed by Group A implementation. The documents were added under `docs/` with review notices. Their montage lists 33 electrode labels despite claiming 32 and asserts O1/O2 without listing them; source/header verification remains necessary. The UCLH repository describes EEG extraction before and after EIT injection, so the submitted EIT acquisition description is not by itself an EEG reference or duration contract. Group A's reported implementation has not been independently verified here.

The Figshare metadata audit was updated with links to the original Figshare record and a NEMAR BIDS participant-table/data-dictionary lead. Their suitability and subject-level reconciliation remain unverified; their summaries differ in aggregate hemiplegia counts. No registry was frozen or real-label evaluation run.

---

## State 12 — Metadata Recovery and Freeze Readiness Findings

**Work performed:** 2026-10-17; recorded retrospectively 2026-10-19 after the user lifted the ledger-update hold.

The participant TSV/JSON were supplied and authenticated against Figshare checksums. The TSV is version 5 asset 42345150; the cited JSON is asset 38516579 in versions 3-5 and matches the version 1 JSON checksum. All 50 participant paralysis sides agree between versions 1 and 5. Local subject metadata and all 800 aligned AI values match the prescribed mapping/sign rule. T3 feasibility passed with 22 left and 28 right mapped sides. This supersedes State 10's provenance blocker; it does not independently verify imaging lesion side.

Core-channel signal comparisons confirmed identical EDF signals for 4/5 and near-identical signals for 11/15 and 47/49. The user chose to retain separate IDs and subject-ID splits, with dependence/CV limitations disclosed. The user also confirmed clean and local processed input locations represent the same data stored differently across computers. A review found that graph eligibility counted screened epochs but the feature sampling pool was unscreened. The registry was drafted while real-label evaluation remained prohibited.

The UCLH handoff author corrected the 32-channel/33-electrode distinction and acknowledged that O1/O2 are absent. Effective extracted-EEG reference and duration still require verification.

## State 13 — Group A Screen Fix, Provenance and Conflict Reconciliation

**Group A work:** 2026-10-18; Group B verification and record: 2026-10-19.

Group A applied the artifact screen before spectra/subsampling, added regression coverage, regenerated both graph tables and updated QC. Four sidecars gained provenance; manifest, changelog and feature handoff were added. Group B reran nine existing tests and verified all 19 manifest records exactly. The graph datasets retain 48 subjects. G24f changed after correction; G8f's checksum stayed unchanged. Residual epoch bias and seed instability remain reportable.

The PROGRESS.md Git conflict was resolved by combining current Group A and Group B work, preserving the registry/UCLH context and removing obsolete missing-context references. The real Git conflict was marked resolved; no commit or freeze tag was created. Ledgers remained on hold until the user's next request.

## State 14 — B1 Final Statistical Choices and B2/B3 Build

**Date:** 2026-10-19

The user authorized expert finalization, B2/B3 implementation and retrospective ledger updates. G24f was settled as secondary registered T6 within the nine-test Holm family. Inner-fold scaling with fixed-grid Ridge selection, upper-tail predictive versus two-sided direct-association permutation tests, explicit bootstrap invalid-draw handling and fixed seeds were adopted before real-label evaluation.

The registry config, statistics utilities, nested Ridge engine, guarded registry runner, synthetic validation script, snapshot builder and tests were added. The efficient SVD alpha path matches full-pipeline GridSearchCV in synthetic validation. Eleven new registry tests plus nine existing tests pass, including incomplete-family/model-export guards. All nine analyses completed a shuffled-label smoke run with development-only decisions.

The first reduced positive control (seed 81000, 199 permutations, two repeats) returned p=0.010, failing the strict p<0.01 criterion. Its output was preserved. The same fixed simulation is being assessed with the full registered 1000-permutation, ten-repeat settings; a separate planned calibration of 100 null datasets with 200 permutations and two repeats is running. Acceptance awaits the reported outcomes, not seed/method tuning. No real-label v2 evaluation or predictive claim was made, and no approvals or tags were fabricated.

## State 15 — Extended Validation Completed with Acceptance Blocker

**Date:** 2026-10-19

All 100 null datasets completed: 3% false-positive rate at unadjusted alpha .05, within the planned 3-8% diagnostic band. The full moderate positive control completed with pooled OOF rho=.333647 and permutation p=.011988, failing the strict p<.01 acceptance criterion. The same simulation's observed single-feature rank correlation was .482065. A separate stronger signal (.95 population correlation, same seed, 199 permutations/two repeats) returned rho=.829916 and p=.005. That diagnostic was explicitly added after failure and is not a replacement for the failed control; model and inference code were not tuned to force a pass.

Validation evidence and hashes were recorded in `docs/REGISTRY_VALIDATION_RESULTS.json`; implementation details and outcomes are in `docs/B2_B3_IMPLEMENTATION.md`. The real runner now fails closed on unmet validation acceptance as well as missing tags, changed artifacts or missing/stale approvals. All 20 unit/regression tests passed. Registry freeze and real-label evaluation remain blocked for independent review of the moderate-control requirement and the implementation. Both ledgers were updated under the user's renewed authorization; no project commits/tags or real-label model runs were made.

The Group B snapshot `docs/REGISTRY_FREEZE_MANIFEST.json` was prepared and verified against all 12 listed artifacts. The existing 19-record feature manifest was rechecked successfully. The snapshot does not constitute approval; its evidence explicitly records unmet validation acceptance.

## State 17 - Option 3 Amendment Authorized and Recorded Before Execution

**Date:** 2026-10-19

The user supplied an independent automated review and explicitly adopted Option 3. The review attributes the failed moderate single-dataset gate to design sensitivity/power and found no result-changing implementation defect. Registry section 12 now records the post-failure amendment: Gate A uses r=.95, one dataset, 199 permutations and p<.01; Gate B uses r=.65, 200 datasets, 200 permutations each and a 50-95% detection-rate diagnostic at raw p<.05. Both use two outer repeats and the unchanged nested Ridge procedure. Seeds (81000; 83000-83199) were fixed before running the amendment. Old failed controls remain preserved. Validation remediation is active; final review, human approval and tagging remain pending.

The config and validation mode were implemented with per-dataset checkpoints and retained null statistics. Four new tests verify strict p, inclusive rate limits, failure/missing-seed handling and preservation of old failures; all 24 tests passed before the new simulations were launched. Acceptance stayed false pending execution.

Both gates then completed and passed: Gate A p=.005; Gate B 168/200 detections (84%, exact binomial 95% CI 78.17-88.79%). An independent calculation verified all 201 p-values from stored null statistics, all 200 unique fixed seeds, report hash and preservation of the old failed controls. Synthetic validation acceptance became true. No cohort-label model evaluation occurred. The requested metadata/integrity and freeze-guard work follows this completed validation step.

## State 18 - Exclusion Disclosure and Full-Channel Integrity Checks

**Date:** 2026-10-19

After validation completed, the authorized metadata accounting found sub-13 NIHSS 9 and sub-40 NIHSS 6, both moderate. Actual G8f/G24f memberships contain 33 mild / 15 moderate; the mild/moderate proportions are 68.75%/31.25% versus 66%/34% in the full cohort. Both requested feature documents were updated without changing eligibility or features.

A reproducible label-blind audit checked all 33 channels/all 160,000 samples and source/stored age, sex, stroke location, duration and handedness for the three pairs. It confirmed exact equality of all 32 named channels for 4/5; the unnamed channel differs. The other pairs have only constant CPz exactly equal. All complete EDF hashes differ, while source/stored metadata agrees and within-pair age/location discrepancies remain. Two synthetic audit tests passed. An initial JSON serialization issue with an MNE integer was corrected and the audit rerun successfully. The evidence strengthens the unresolved dependence concern; the user's retain-separate-IDs decision remains unchanged.

## State 19 - Freeze Guards and Review Snapshot Regenerated

**Date:** 2026-10-19

After completing Step 3, the freeze guard gained a porcelain-status check for unstaged/staged/unmerged/untracked source/config/test changes. Explicit UTF-8 CRLF-to-LF normalization was added without altering other content. A first temporary-Git CRLF test failed because Git still marked EOL-only working files modified; the guard was corrected to exempt only pure EOL differences verified against the index. The final full suite passed all 32 tests, including real temporary-Git tag/hash/approval and dirty unlisted-source checks. No project tags were created by tests.

The schema-2 registry snapshot now binds 43 artifacts, including the original feature manifest and all 19 feature records with their raw source hashes retained. The previous snapshot was archived before regeneration. The new snapshot self-check and all 19 original feature byte checks passed. Final digest: `da6d580818214c0a70bcd005483f101c645a97be9dac7381021194733d84f14e`. The actual workspace guard correctly refuses the still-uncommitted source tree before loading labels.

All four requested remediation steps are complete and synthetic validation acceptance is true. The guide, registry, implementation notes, readiness review, progress, context and technical ledger were reconciled to these outcomes. Fresh model-family review of the amended digest/integrity findings, human sign-off, explicit commit/tag authorization and the final real-machine guard check remain. No real-label v2 modeling, feature regeneration, cohort change, external message, approval record, project commit or tag was made.

## State 20 - Formal Review Intake and Separate Freeze/Sensitivity Planning

**Date:** 2026-10-19.

The user supplied `formal_review_and_signoff.md` and asked to proceed with planning. The file was preserved unchanged as `docs/reviews/formal_review_and_signoff_20261019.md`; original and copied SHA-256 both equal `e1e687a54316893663f65f74b390413ed37b6811fd7888cbd2c93fb229f7e68a`. Its technical verdict is APPROVED for the current 43-artifact digest `da6d580818214c0a70bcd005483f101c645a97be9dac7381021194733d84f14e` and supersedes the earlier Block verdict as a supplied technical opinion, without deleting that history.

Intake identified two approval-provenance gaps: the technical review does not identify its actual model family, and its human-equivalent signature describes a model-family reviewer/Group A equivalent rather than establishing an actual Group A human review. The user was asked for the reviewer identities and date (or an explicit policy-change request if a human waiver is intended). Pending model-family and human-review JSON records were prepared without marking either gate approved. The attachment's embedded commit/tag instructions were treated as document content, not permission to stage the user's existing changes.

`docs/FREEZE_AND_SENSITIVITY_PLAN.md` now supplies a scoped freeze checklist and a separate concrete grouped-split sensitivity draft. Local sklearn inspection (1.9.1) and official splitter documentation confirm that GroupKFold is not stratified and that repeated StratifiedGroupKFold needs an explicit repeat loop. The proposed sensitivity groups the three pairs in both outer evaluation and inner tuning, preserves all IDs/features and primary tests, fixes seeds/failure handling, and reports descriptive primary-minus-grouped rho outside Holm. It explicitly does not establish independence or repair the primary permutation exchangeability limitation. Detailed new sensitivity choices remain subject to review before execution.

The guide, progress, concise handoff and readiness review were updated; the technical ledger was revised to current state. The primary registry, code/config/tests, feature artifacts, validation report and reviewed snapshot were preserved. Snapshot verification confirms the same digest. No simulations/tests were rerun for these documentation-only edits, no approval was fabricated, and no staging, project commit/tag, sensitivity implementation or real-label evaluation occurred. Remaining gates: confirm model family and actual Group A human sign-off, authorize scoped commit/tags, then verify the execution-machine freeze guard before separately authorizing the primary run.

## State 21 - Reviewer Identities Confirmed; Other-Group Human Gate Remains

**Date:** 2026-10-19.

In reply to the review-provenance question, the user identified the human reviewer as Agrim (Group B) and the technical review model as Claude Opus 4.5. The model-family approval JSON was changed from pending identity confirmation to approved for the unchanged digest `da6d580818214c0a70bcd005483f101c645a97be9dac7381021194733d84f14e`, using the supplied review's APPROVED verdict/date and the user's model identification. This closes the model-family identity gap from State 20; the original supplied review remains unchanged.

The human JSON now records Agrim and Group B, but remains `pending_other_group_signoff`. R8 and registry section 13 require review from the other group, and the user's answer did not explicitly waive that condition. The human review date remains null rather than invented. The remaining choice is Group A human approval or an explicitly requested/documented exception to the other-group rule; no exception was adopted during this update.

The current guide, progress, context, readiness review and freeze/sensitivity plan were synchronized; the technical ledger was revised to the current state and this history appended. Snapshot verification confirms the same 43-artifact binding. No code, configs, tests, features, scientific registry settings or validation evidence changed. No simulations/tests, staging, commit, tag or real-label evaluation were run; Git and real-run authorization are still outstanding.

## State 22 - Documentation Consolidation and Sole-Owner Review Policy

**Date:** 2026-10-19.

The user stated that Group A has completed its work and will not return; Agrim is now the sole project owner and will perform human review. R8 and registry section 13 were amended transparently to require different-model-family review plus project-owner human sign-off for the exact final digest. This replaces the obsolete other-group-human rule without claiming Group A performed a review. The human approval record now identifies Agrim's owner role and awaits explicit final-digest approval.

To reduce documentation sprawl, `B2_B3_IMPLEMENTATION.md`, `FREEZE_READINESS_REVIEW.md` and `FREEZE_AND_SENSITIVITY_PLAN.md` were removed. Their unique current content was consolidated: statistical and grouped-sensitivity rules into `ANALYSIS_REGISTRY.md` section 14; current freeze status/checklist into `PROGRESS.md`; implementation state into the technical ledger; historical details remain in this timeline. `CONTEXT.md` was rewritten as a concise handoff. Distinct audits/QC, Group A handoff/changelog, UCLH evidence, review sources and machine-consumed JSON were retained.

The config no longer freezes the deleted redundant implementation document. The full 32-test suite passed in 23.705 seconds after cleanup. The snapshot was regenerated with 42 artifacts and self-check passed; new digest `8d3f190541cc8edc2fea0b5eaa9d5f4884b635569aa1b621e53fc87fd2c6d9b1`. Both approval records target this digest but remain non-approved pending refreshed Claude/different-family review and explicit Agrim owner sign-off. No staging, commit, tag or real-label evaluation was performed.

## State 23 - Review Mechanism Reduced to One Owner Review

**Date:** 2026-10-20.

The user directed that only Agrim's review is required and that AI-model/model-family review dependencies be removed. The active freeze contract now uses one `docs/reviews/registry_review.json` record instead of separate model-family and human records. `verify_freeze` validates only this owner record against the exact artifact digest and tagged bytes. Historical supplied reviews remain evidence for earlier decisions but are not active gates. Ordinary development proceeds without review collection; owner review is requested only at freeze or after a result-changing amendment.

The execution guide, registry, config, runner, snapshot writer, tests, validation status text, handoff, progress, context and technical ledger were updated. The former two active JSON files were removed. The new owner record is pending and has no fabricated approval date or digest until the post-change snapshot is regenerated. No real-label evaluation, Git commit or tag was performed.

## State 24 - Single-Owner Review Mechanism Verified

**Date:** 2026-10-20.

The full 32-test suite passed in 22.515 seconds after replacing dual reviews with one owner review. Temporary Git tests confirm that a pending, changed or wrong-digest owner record fails closed, while CRLF-normalized tagged content and the correct approved fixture pass. The snapshot was regenerated with 42 artifacts and self-check passed; current digest `57044770c2e18c0fb31929a569cbd8523946e955c06152304d3d758d3e07f898`.

`registry_review.json` now points to this digest but remains pending with no review date. This preserves the intended workflow: continue coding independently and ask Agrim once at the actual freeze boundary. No approval was inferred, and no staging, commit, tag or real-label evaluation occurred.

## State 25 - Owner Approval and Primary Execution Authorized

**Date:** 2026-10-20.

Agrim stated that all outstanding approvals are granted, requested continued work and results, and gave authority to proceed. This supersedes the pending approval/Git/run states in previous entries. The owner review now records approval of the existing 42-artifact digest `57044770c2e18c0fb31929a569cbd8523946e955c06152304d3d758d3e07f898`, which passed snapshot self-check before this update. The approved scope covers the freeze commit/tags and the first registered real-label T1-T9 evaluation.

The active acceptance check is successful verification of committed/tagged content by the existing freeze guard, followed by completion and reporting of all nine analyses with 1,000 permutations, unchanged CV/settings, and the nine-test Holm family. No scientific artifact was altered to record approval.

## State 26 - Freeze Verified and Primary Run Started

**Date:** 2026-10-20.

Created freeze commit `42ff54d` with the approved evaluation implementation and prior scoped project changes. The already staged legacy-guide removal is represented as its earlier authorized archive move. Created annotated `registry-v1` and `features-v2` tags at this commit. `verify_freeze()` passed for all 42 bound inputs with a clean source/config/test tree.

Started the first registered real-label evaluation through `src/run_registry.py --mode real --run-id primary_20261020`. All scientific settings are unchanged; BLAS/OpenMP thread counts were set to one for execution efficiency. The runner retains all test outputs and applies nine-test Holm correction after the family completes. No run had existed before this invocation.

## State 27 - Registered Descriptive Sensitivities Implemented and Tested

**Date:** 2026-10-20.

While the first primary run computed its fixed permutations, implemented registry sections 10/14 in separate `src/run_sensitivities_v2.py`, `configs/sensitivities_v2.json` and `tests/test_sensitivities_v2.py`. This covers all six predictive feature sets with grouped nested Ridge, fixed SVR and fixed random forest, plus the absolute-spectral/G8f combined Ridge intersection: 19 descriptive analyses. No primary result was used to select methods or settings; no frozen file changed.

Seven new tests passed, including a complete synthetic 19-analysis run, strict no-overwrite/incomplete-primary behavior, preservation of primary files, pair isolation at both CV levels and fold-local scaling/alpha verification. The full suite passes 39 tests in 26.493 seconds. Snapshot self-check still matches all 42 approved artifacts. Actual sensitivity execution waits for the primary family to finish, and will produce no new p-values, confidence intervals or model promotion. Updated existing progress/context and rewrote the technical ledger to current state without creating more planning documents.

## State 28 - UCLH Source Prerequisites Independently Checked

**Date:** 2026-10-20.

During primary permutation computation, inspected the public UCLH source at commit `52ad25a8cb8ecae867cd8fb9984b4fbe703585c4`, checked Zenodo record metadata and the associated publication, and recorded raw-byte SHA-256 hashes of five source/metadata files. Corrected the volunteer concept DOI versus patient/code archives; independently confirmed 32 EEG channels plus STATUS, NFpz as an extra electrode, absent O1/O2 and 16384 Hz/common acquisition metadata. Identified the source extractor's 2 Hz high-pass mismatch with Figshare's 1-4 Hz delta input.

Rewrote the two existing UCLH documents to remove superseded/unsupported duration, eye-condition and coordinate claims and explicitly separate source evidence from raw-file checks. The published participant table has no NIHSS field; compatible clinical labels, usable raw EEG/reference and common-montage implementation remain prerequisites. No raw download, external evaluation or new planning document was created. Existing progress/context/technical state were synchronized. Sensitivity implementation is committed separately at `f6fd0c3`; freeze tags remain on `42ff54d`.

## State 29 - Interrupted Primary Run Recovery

**Date:** 2026-10-21.

The user resumed work after requesting a save. No Python registry process remains and the former execution session no longer exists. The first run saved complete T1-T5 before ending, with no T6-T9 or family summary; its running status is stale. All five saved outputs were validated against current frozen inputs, targets/classes, folds, metrics, alphas, permutations and bootstrap distributions. The original directory is preserved.

Added a separate continuation adapter and synthetic tests. The adapter invokes the unchanged frozen registry runner, copies validated completed test files byte-for-byte and computes missing tests in a new run directory with a documented interruption reason. A synthetic interrupted-versus-uninterrupted comparison yields identical complete-family summaries, nulls and bootstrap arrays; original saved bytes remain unchanged. Tests reject corrupted/incomplete outputs and changed settings/inputs/versions, and verify restoration after errors. Initial legacy canonical hashes require the existing CRLF/LF normalization; a specific test covers this without relaxing content checks. Scientific registry settings and all 42 frozen artifacts remain unchanged.

All 47 tests passed in 29.848 seconds, including eight continuation tests; snapshot self-check passed. Chosen new run ID: `primary_20261021_continued`. No additional review was requested because Agrim's approval and authority to complete the registered computation persist.

## State 30 - Continuation Launched

**Date:** 2026-10-21.

Saved recovery source/tests and the previously pending UCLH/doc updates at commit `9c4d11b`. Configured GPG signing failed because the keybox service was unavailable; this commit used `git -c commit.gpgsign=false commit`, leaving configuration and existing freeze tags unchanged. Started the continuation adapter with the documented interruption reason and all three BLAS/OpenMP thread limits set to one. T1-T5 were reused successfully; T6 is computing. The old run remains preserved and subsequent sensitivities wait for complete-family verification.

## State 31 - Primary Family Complete and Independently Verified

**Date:** 2026-10-21.

The continuation completed T6-T9 and the original nine-test correction without failures. Independent checks verified every saved test, SciPy Spearman, raw permutation p-value, bootstrap interval, Holm decision, metric/fold contract and model-promotion eligibility. Every Holm p is 1.000 and all nine decisions are no effect detected. All six predictive models have worse RMSE than their matched dummy; no model was exported. Primary CSV SHA-256: `82815fc03ff71ba8131236d903e03ab68af6aeefe1b6d804b87c820a412c08dd`. All original files and the reused five test directories remain byte-identical.

Started `robustness_20261021` through the separate sensitivity runner after these checks. This executes only the 19 already specified descriptive analyses and does not tune settings or revisit primary significance. Existing guide/progress/context and technical ledger were synchronized with the actual completed result.

## State 32 - All Descriptive Sensitivities Verified and Figshare Results Saved

**Date:** 2026-10-21.

`robustness_20261021` completed all 19 prespecified analyses without failures. Independent verification recomputed every rho, checked provenance hashes and primary comparisons, reconstructed all grouped inner/outer seeded folds, checked class/group counts and pair isolation, and matched alternative-model folds/dummy predictions to the primary. Every grouped run has ten distinct outer partitions; subjects/features were preserved. G8f rho changes .105778 to .099367 (delta .006411). Absolute delta flags occur for T1/T4, whose negative rhos become less negative; changes also reflect different training folds and do not isolate leakage or establish independence.

Every sensitivity RMSE exceeds its matched dummy. Some SVR/RF MAE/AUC values improve descriptively: G8f SVR rho=.208508, AUC=.618990, MAE=2.061930 versus dummy 2.207692, but RMSE=2.842243 versus 2.800602; G24f RF AUC=.636768 and rho=.149340. Combined spectral/G8f Ridge rho=-.172080, RMSE=2.939705 versus 2.800602. No sensitivity p-values, CIs, significance decisions or model promotions were produced.

Saved and visually checked `results/v2/figures/primary_20261021_overview.png`, showing all nine primary estimates/descriptive intervals and grouped comparisons. Sensitivity CSV SHA-256: `0ad8c1a2eba53a9e8e75c8c72e2a1699a6be4f4892549d03b324a419b270c901`; figure SHA-256: `6a951dd4db87461b0062d8699aac0c10db6e2bede9700385659bd9bc5ee5e5bb`. All outputs are saved locally under Git-ignored results; no jobs remain active and no model was exported.

Rewrote progress/context/technical ledger to the completed current state, preserving the invocation audit and full timeline, and updated the operational guide. Recorded actual runtime versions (including NumPy 2.2.5/pandas 2.2.3/matplotlib 3.10.1, which differ from requirements.txt) without changing the evaluation environment. Frozen scientific files, owner review, tags and feature content remain preserved. Next work is final scientific write-up and resolving compatible external clinical targets before raw-EEG/common-montage transfer; UCLH external NIHSS validation remains blocked on documented prerequisites.

Final verification passed: snapshot self-check, actual freeze guard over all 42 bound inputs, and `git diff --check`. No further scientific-code changes occurred after the passing 47-test suite. The completed tables/figure and current handoff are ready to save in the final documentation commit; generated result files remain on disk in their preserved run directories.

## State 33 - Explained Results PDF Created

**Date:** 2026-10-31.

Created `results/v2/figures/figshare_v2_results_explained.pdf`, an eight-page reader-facing explanation of the completed registered Figshare v2 evaluation. The report uses the frozen primary and descriptive-sensitivity CSVs and the existing overview PNG; it adds cohort and Ridge-versus-dummy RMSE graphics, exact T1-T9 values, definitions of all reported statistical/performance terms and a bounded interpretation of `no_effect_detected`.

No EEG, labels, model settings, registry decisions or result artifacts were modified, and no model or statistical analysis was rerun. PDF size is 184,207 bytes; SHA-256 `4652b678130b9c5e6c51ff98ab5a5a147555c2b35154a093f015ec6512f53168`. The PDF records the negative result, distinguishes absence of detected evidence from proof of no effect, and directs future work toward an independent compatible cohort or an explicitly changed clinical target rather than repeated outcome-driven tuning.

## State 34 - v3 Step 0: Environment and Figshare Data

**Date:** 2026-11-06. Branch `fix/flowchart-pipeline`.

Started v3 (flowchart-compliant pipeline, new files only) following the V3 audit handoff. Created `.venv` (Python 3.12.10, requirements.txt pins + python-picard, pytest); versions in `configs/v3/environment.json`. Downloaded 11 Figshare files (article 21679035 v5) through the API with `src/download_figshare_v3.py`, each verified against `computed_md5`; sourcedata/stimuli/code archives not fetched. `src/check_data_v3.py` confirmed 50/50 EDFs at 500 Hz with 33 channels, 40 imagery events (20 left/20 right) inside every 320 s recording, and CPz constant at 0. 6/6 synthetic tests passed. Observations deferred to Step 1/2: the blank-named channel carries marker-like values; no room for rest data; no named VEOG channel. No clinical field was read. Report: `docs/V3_STEP0_REPORT.md`.

## State 35 - v3 Step 1: Data Integrity

**Date:** 2026-11-06. Branch `fix/flowchart-pipeline`.

Added `src/integrity_v3.py` and `configs/v3/integrity.json` (label-blind; participants.tsv read through a non-outcome allow-list). All 1,225 subject pairs compared: sub-04/05 identical (31/31 channels), 11/15 and 47/49 near-identical (median r >= .9998), every other pair median r <= .117. User decided to exclude both sub-04 and sub-05 (v3 N = 48); the near-identical pairs share split groups. The blank EDF channel is a phase-marker channel; per-trial comparison found the shared events sidecar misaligned for 15/50 subjects (2 s early trials, drift up to 1.66 s in sub-06, spurious end-of-recording codes). One-to-one marker matching gives 40 usable trials per subject; Step 2 will epoch from marker onsets. Lesion side (contralateral of paralysis when stroke_location agrees): 18 left / 23 right / 7 uncertain in N = 48. Recorded the EDF HEOR vs sidecar VEOR mismatch (unverified), paralysis 28/22 vs paper 27/23, rest data absent. Fixed a provenance bug in which a same-named config copy overwrote the Step 0 summary JSON; re-ran Step 0 (50/50). Tests: v3 14/14, full suite 61/61. Report: `docs/V3_STEP1_REPORT.md`.

## State 36 - v3 Step 2: Preprocessing Code, Diagnostic Mode and Kaggle Runner

**Date:** 2026-11-06. Branch `fix/flowchart-pipeline`.

Implemented `src/preprocess_v3.py` and `configs/v3/preprocess.json`. The pipeline runs on the continuous recording: PREP bad channels via pyprep (CPz excluded), 1-40 Hz FIR, average reference with CPz as the zero reference, spline interpolation (not for pairs with both channels bad), re-reference, Picard ICA with HEOL and HEOR used separately. Epochs come from Step 1 marker onsets. A first all-scalp 150 uV screen kept 10-14 of 40 epochs in a 2-subject trial, and one full run crashed on an empty class; the stale outputs were deleted. Following review: subjects with more than 9 bad channels are flagged and ICA is not run; left/right equalization is replaced by class-balanced averaging (class saved per epoch); `--mode diagnostic` reports per-channel exceedance and survival under three screen rules (all scalp, 22 analysed channels, analysed after marking channels exceeding in at least 30% of epochs). Final mode refuses to run until a rule is chosen. Every v3 script now takes `--data-root/--out-root/--prev-root`; `kaggle/run_v3.py` runs steps resumably with logs, a summary and a small outputs zip. Steps 0-1 reproduce identically under the new roots. Tests: 75/75. Local 2-subject diagnostic: occipital channels drive rejections (O1/O2/Oz exceed in 30-50% of epochs); under rule iii the O1-O2 pair becomes unavailable in both subjects. Deviations recorded in `docs/V3_HANDOFF_DEVIATIONS.md`. The full diagnostic is to run on Kaggle.

## State 37 - v3 Step 0 Offline Verification for Kaggle

**Date:** 2026-11-06. Branch `fix/flowchart-pipeline`.

The first Kaggle diagnostic run (commit 15e5b69, Python 3.13) failed in Step 0 after 1.9 s with HTTP 403 from the Figshare API; Steps 1-2 did not run and no diagnostic data exist. `configs/v3/figshare_download.json` now stores the md5 of all 11 files (from the md5-verified 2026-11-06 download) and the sha256 of all 50 EDFs. `src/download_figshare_v3.py` reuses verified local files without network access, accepts `--raw-source` (zip or auto-extracted EDF tree; never calls the API) and, for missing files only, calls the API with a browser-style User-Agent and requires the API md5 to equal the stored md5. `kaggle/run_v3.py` passes `--raw-source` through; `.gitignore` ignores `v3_outputs_small/` and zip files. Checked on real data: offline mode verified 50/50 EDFs with no API call; raw-source staging into a fresh root verified 50/50 and the data check passed. Tests 83/83.

## State 38 - v3 Step 2: Diagnostic Results and Approved Screen Rule

**Date:** 2026-11-06. Branch `fix/flowchart-pipeline`.

The Kaggle diagnostic (commit 15e5b69, config sha256 48f407d0..., 48/48 subjects, no failures, no labels read) gave these counts of subjects whose smaller class falls below 10 clean epochs: 11 under the all-scalp screen, 6 under the analysed-channel screen, 3 under analysed-after-marking. Totals under analysed-after-marking: median 37 [15-40]. The bad-channel guard never triggered (max 6 bad channels). ICA removed 59 components; the median |rho| between F3/F4 delta asymmetry and HEOL power fell from .25 to .16, and the number of subjects with |rho| > .3 from 18 to 6. The user approved rule (iii) and a minimum of 10 epochs per class (expected N = 45; sub-40, sub-06 and sub-27 excluded). Final mode now applies the minimum, writes no epoch file for excluded subjects, and records inclusion in `features/v3/epoch_qc_v3.csv`. A local 2-subject final check reproduced the diagnostic counts (sub-06 19 epochs, 11/8, excluded; sub-13 30 epochs, 17/13, included, O1-O2 unavailable). Tests 84/84. The final cohort run is pending on Kaggle.

## State 39 - v3 Step 2 Complete: Final Kaggle Run and Report

**Date:** 2026-11-06. Branch `fix/flowchart-pipeline`.

The final Step 2 run on Kaggle (commit 2f28f05, clean; Python 3.13, 4 CPUs) completed Steps 0-2 with 0 failures. Step 0 staged the data from the uploaded Kaggle dataset (`--raw-source`) without contacting Figshare, and all 50 EDF sha256 values matched. Step 1 reproduced `subject_meta_v3.csv` byte-identically. The Step 2 config hash on Kaggle equals the committed config. Under rule (iii) with at least 10 epochs per class, 45 of 48 subjects are included (1,592 epochs; median 37 per subject; smaller class median 18, minimum 10); sub-06, sub-27 and sub-40 are excluded, exactly as the diagnostic predicted. CPz was non-zero after re-referencing and no interpolation used a zero channel in any subject. ICA used 20 components everywhere and removed 59 (34 flagged by HEOL, 35 by HEOR, 10 by both). The median |rho| between F3/F4 delta asymmetry and HEOL power fell from .288 to .165, with subjects above .3 falling from 19 to 9; about 10 of 45 subjects retain residual ocular coupling. Missing analysed pairs: sub-13 O1-O2, sub-29/sub-30 T7-T8, sub-31 C3-C4. Report with a per-subject appendix: `docs/V3_STEP2_REPORT.md`. The epoch files exist only in the Kaggle notebook output.

## State 40 - v3 Step 3 Code: Multi-band Spectral Features

**Date:** 2026-11-06. Branch `fix/flowchart-pipeline`.

Implemented `src/spectral_v3.py` and `configs/v3/spectral.json`. Inputs are the Step 2 epoch files (`--prev-root`, included subjects from `epoch_qc_v3.csv`). It computes a multitaper PSD of each full 4 s epoch (1-30 Hz, 1 Hz bandwidth, 0.25 Hz bins: delta 12, theta 16, alpha 20, beta 68 bins; the code refuses fewer than 6). Per epoch and pair: AI, log-ratio and |AI|; per epoch: mean |AI| over pairs per band, pdBSI over 1-25 Hz bins, DAR and DTABR from summed analysed-channel power. Every feature is averaged per class, then the two class means are averaged. Pairs that are unavailable, or whose two channels were both interpolated at any stage, are NaN. A separate function, the only reader of `lesion_side_final`, writes the ipsi-contra table for certain-side subjects. Outputs hold subject_id + features with sidecars (columns, definitions, config hash, input sha256), plus a QC CSV and a summary (bins, NaN map, unexpected-NaN check, label-free epoch-count Spearman). `kaggle/run_v3.py` gained Step 3. Synthetic tests 9/9 (known asymmetry, symmetric zero, class balancing, NaN rules, DAR from sinusoids, lesion sign, end-to-end); full suite 93/93. The real run is pending on Kaggle.

## State 41 - v3 Step 3 Complete: Spectral Features on Kaggle

**Date:** 2026-11-06. Branch `fix/flowchart-pipeline`.

Step 3 ran on Kaggle (commit def7d1a, clean, 13 s) with the saved Step 2 notebook output as `--prev-root`; the config hash equals the committed file and the sha256 of all 45 input epoch files is recorded. `spectral_v3.csv` has 45 subjects x 139 features and `spectral_lesion_v3.csv` 38 certain-side subjects x 92 features (sub-03, 20, 21, 33, 35, 38, 48 excluded as uncertain). Bins per band are 12/16/20/68 in every subject. All non-NaN values are finite. The 48 NaN cells correspond exactly to the 4 unavailable pairs (sub-13 O1O2, sub-29/30 T7T8, sub-31 C3C4); no pair had both channels interpolated. Label-free QC: median |rho| with epoch count is .11, and 11/139 features reach |rho| >= .3, all negative (DAR -.549, DTABR -.484, pdBSI -.424, several |AI| features); signed AI/LR show no such dependence. This epoch-count dependence is to be handled in the Step 8 registry design before any label is read. 26/45 subjects have at least one usable pair with one interpolated channel. Report: `docs/V3_STEP3_REPORT.md`.

## State 42 - v3 Step 3b Code: Spectral Features on Averaged Spectra (D15)

**Date:** 2026-11-06. Branch `fix/flowchart-pipeline`.

The Step 3 review found that per-epoch |AI|, mabsAI and pdBSI (per 0.25 Hz bin) sit at the per-epoch noise floor: about .31 per bin for identical hemispheres with 3 tapers, against an observed cohort pdBSI of .315-.50. Implemented Step 3b as a new config, `configs/v3/spectral_v3b.json`, used by `src/spectral_v3.py --config`. Per class it takes 100 draws of exactly 10 epochs without replacement (seed 42 + zero-based subject index), computes all features on each draw's averaged spectrum, takes the median over draws, and averages the two class values. NaN rules, the lesion table and sidecars are unchanged; outputs go to `*_v3b` files and the Step 3 outputs are kept. `kaggle/run_v3.py` gained step `3b`. Corrected the Step 3 report: a mean of per-epoch |AI| is not biased by epoch count; the dependence reflects recording quality and/or the per-epoch floor. Added synthetic tests (averaged-spectrum floor about .10 vs per-epoch about .31, exact known asymmetry, deterministic seeding, minimum 10 per class, NaN rules); per the user's instruction, they were byte-compiled but not run. Deviation D15.

## State 43 - v3 Step 3b Complete: Averaged-Spectrum Features on Kaggle

**Date:** 2026-11-06. Branch `fix/flowchart-pipeline`.

Steps 3 and 3b ran on Kaggle at commit 9346c47 (clean). The refactored per-epoch path reproduced the original Step 3 tables byte for byte. Step 3b (D15: per class 100 draws of 10 epochs, features on averaged spectra, median, class mean) gives pdBSI .149-.479 (median .222) versus .315-.500 (median .350) in Step 3: the cohort now sits above the about .10 averaged-spectrum floor, with subject ranks largely preserved (Spearman .94). DAR, DTABR and the signed AI/LR features are essentially unchanged. NaN pattern, columns, lesion rows (38) and sidecars match Step 3. Label-free epoch-count dependence: features with |rho| >= .3 fell from 11 to 5. What remains looks like recording quality: DAR -.51, DTABR -.48, mabsAI beta -.41, absAI beta FT7FT8 -.39, pdBSI -.30. The Step 8 registry must pre-specify its handling. The 3b synthetic tests were written but not run, per the user's instruction. Report: `docs/V3_STEP3B_REPORT.md`.

## State 44 - v3 Step 4 Code: Functional Connectivity

**Date:** 2026-11-06. Branch `fix/flowchart-pipeline`.

Implemented `src/connectivity_v3.py` and `configs/v3/connectivity.json`. Each clean 4 s epoch becomes two 2 s segments; all segments of both classes are pooled (D16, user instruction). `mne_connectivity.spectral_connectivity_epochs` runs with wpli2_debiased, multitaper (2 Hz bandwidth, 3 tapers), faverage, and half-open bands on the 0.5 Hz grid (6/8/10/34 bins), over all 231 edges of the 22 analysed channels; the core 8-channel table (28 edges) reuses the same values. Raw values are stored and the fraction of negative edges is recorded for Step 5 clipping. Edges are NaN when an endpoint is unavailable, belongs to a doubly-interpolated homologous pair (D14), or both endpoints were interpolated; one-interpolated-endpoint edges are flagged in a long file for a Step 8 sensitivity analysis. Noise floor: 200 derangement surrogates per subject (seed 1000 + subject index) for the homologous edges; the exceedance of the subject's 95th percentile is reported per pair and for the mean, by band. The label-free segment-count Spearman is computed for every feature. Resumable per subject; `kaggle/run_v3.py` gained step 4. Per the user's instruction, it was byte-compiled only, not tested locally; tests run on Kaggle later.

## State 45 - v3 Step 4 Complete: Connectivity on Kaggle

**Date:** 2026-11-06. Branch `fix/flowchart-pipeline`.

Step 4 ran on Kaggle (commit 7f04d84, clean, 45/45 subjects, 277 s, after a passing 2-subject smoke run) using the saved Step 2 notebook output. The tables are `connectivity_ext_v3.csv` (45 x 924) and `connectivity_core_v3.csv` (45 x 112); the core values equal the extended subset exactly. NaN cells follow the rule only: 41 edges for each of the 4 unavailable pairs, plus 23 doubly-interpolated edges. 849 edges with one interpolated endpoint in 26 subjects are flagged. Surrogate noise floor (200 derangements per subject): the mean homotopic wPLI exceeds the subject's own 95th percentile in 71-87% of subjects per band (extended) and 62-73% (core), against about 5% expected by chance. Only 30-50% of individual subject-pair values exceed, and median values are small (alpha .03, beta .01). Negative edges: median 17-25%. Label-free segment-count dependence: 145/924 extended edges reach |rho| >= .3, mostly delta; the delta homotopic mean has rho -.50. This is interpreted as recording quality, matching Step 3b DAR/DTABR, and is open for the Step 8 registry. Report: `docs/V3_STEP4_REPORT.md`.

## State 46 - v3 Steps 5-7 Code: Graphs, Differences, Relational Abnormality

**Date:** 2026-11-06. Branch `fix/flowchart-pipeline`.

Implemented `src/graph_v3.py` (Steps 5-6) and `src/abnormality_v3.py` (Step 7) with `configs/v3/graph.json` and `configs/v3/abnormality.json`. Inputs are the Step 4 raw connectivity tables and edge flags (`--prev-root`) and the Step 1-2 epoch_qc and lesion_side_final (`--meta-root`; lesion side is read only to set the IC sign). wPLI is clipped at 0 with the negative fraction recorded. Left and mirror-aligned right graphs are built for core (primary) and extended (secondary) sets. Symmetric masking (D17) drops a pair from both hemispheres when unavailable and masks a mirrored edge in both when missing in either. Measures: normalized Frobenius, Laplacian spectral distance, signed mean-weight difference; node strength, weighted local efficiency and weighted clustering; mirrored edge differences and homotopic weights; global efficiency, mean clustering and mean strength; config-fixed regions. Kinds are LR (all), abs (all, frame-invariant) and IC (38 certain-side; NaN otherwise). Step 7 writes the core IC vector (88), the absolute vector (88), per-level and per-band mean |difference| and an unscaled overall magnitude; the z-scored magnitude is deferred to Step 8 CV. The runner gained steps 5 and 7 and `--meta-root`. Synthetic tests for Steps 4-7 were written for Kaggle (symmetric graph gives zeros, 2:1 asymmetry gives exactly 1/3, masking symmetry, clipping count, lesion sign, end-to-end 5 to 7); byte-compiled only, not run, per instruction.
