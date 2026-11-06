# Execution Guide: GROUP A, Feature Track (v2)

**Project:** Brain Hemispheric Asymmetry for Stroke Severity Assessment
**Stage:** Post-Phase-5 "v2" work. Phase 5 binary classification is **frozen** (clean null result).
**Your mission:** Build the improved feature tables (sign-invariant, lesion-aligned, epoch-balanced graph features) and hand them to Group B **without ever looking at how they relate to the labels.**
**Effort share:** 27 of 54 points (50%). Group B holds the other 27.

---

## 1. Shared Contract (identical in both groups' guides)

### 1.1 What is established and what is hypothesis

| Established (Phase 5) | Still a hypothesis (v2 tests it) |
|---|---|
| Spectral, graph and combined features gave balanced accuracy 0.46-0.50, permutation p 0.53-0.73, for mild vs moderate. | Left/right sign cancellation (left- and right-sided strokes push signed AI in opposite directions) hides signal. |
| The harness works (Dummy = exactly 0.50 balanced accuracy and AUC). | Binary bucketing at NIHSS 4/5 throws away power; a continuous NIHSS target is more sensitive. |
| Labels are sound (mild NIHSS 1-4, moderate 5-11, severe none). | Variable epoch counts bias wPLI (r = -0.58 was reported by the audit; reproduce it, don't assume it). |
| N = 50 (33 mild / 17 moderate) only detects large effects. | An 8-channel graph (4 nodes per side) is too coarse. |

v2 is a **pre-specified exploratory** analysis. The Phase 5 result is never reopened or overwritten.

### 1.2 Corrections to the source proposal (do not copy these claims into the report)

1. **"Hemiplegia side" is not lesion side.** Weakness is *contralateral* to the lesion: left hemiplegia means a right-hemisphere lesion. Whatever the metadata column means, record its semantics explicitly and map it to lesion hemisphere before flipping any sign.
2. **pdBSI is already mean |AI|.** The sign-invariant hypothesis was partly tested already: the 3 global features (pdBSI, DAR, DTABR) are sign-invariant and still scored AUC about 0.58 (p not significant). So the |AI| set is a cheap check, not an expected fix.
3. **"Mathematical guarantee" of removing epoch bias is overclaimed.** Fixed-count subsampling removes the *count* dependence by construction, but you must verify empirically (correlation with epoch count after the fix). The "10 to 40 epochs" range is unverified: 2000 epochs / 50 subjects = 40 maximum, 1731 retained means about 34.6 on average.
4. **24-channel expansion has two conflicts.** (a) Artifact rejection ran on only 8 channels, so peripheral channels (Fp1/Fp2, F7/F8, T3/T4, FT7/FT8, TP7/TP8) may be dirty. (b) UCLH may lack some of them. Hence QC first and a common-montage version for Phase 9. Also, an unthresholded dense wPLI graph makes efficiency and clustering largely redundant with mean connectivity; check collinearity.
5. **Regression adds sensitivity, not signal.** At N = 50, a rank correlation of about 0.39 is needed for 80% power uncorrected, and about 0.48 after Holm with 9 tests. Cross-validation attenuates observed correlations further.
6. **Do not modify `feature_extraction.py`.** |AI| is computed from existing columns (`abs()` of subject-level means). v1 files stay untouched so Phase 5 stays reproducible.
7. **Only Ridge is inferential.** SVR/RF and any "cleanly separate" claims are sensitivity checks with no significance claims.

### 1.3 Rules (all binding)

- **R1 Blind feature engineering.** Group A never computes any association between a candidate feature and `nihss_raw`, `severity_class`, or `lesion_side` (except A2 *using* lesion_side to flip signs). Design choices (N_fixed, channel set, number of subsamples) come only from epoch counts and channel quality. Allowed diagnostic, report-only: correlation of epoch counts with NIHSS (confound check; it must not change any design choice).
- **R2 Registry frozen.** `docs/ANALYSIS_REGISTRY.md` is git-tagged `registry-v1` before any v2 table is evaluated against real labels. No test is added afterwards.
- **R3 One shot.** The registry runs on tables tagged `features-v2` via `src/run_registry.py`. Plumbing tests use **shuffled labels or simulated data only**. A rerun after a bug is allowed but every run is logged in `docs/PROGRESS.md`.
- **R4 Report everything.** All m registered tests are reported with Holm-adjusted p, failures included. Anything extra goes in a "post-registry" section outside Holm, with no claims.
- **R5 Labels never live in feature files.** Feature CSVs hold `subject_id` + features only. Labels and metadata live in `features/v2/subject_meta.csv`.
- **R6 New files only** for v2 (no edits to Phase 0-4 files or v1 results).
- **R7 Config-driven.** Every constant lives in a config JSON saved next to its output.
- **R8 Review.** Every PR is reviewed by (a) a different AI model family (Codex) and (b) a human from the *other* group.
- **R9 Language.** Say "pre-specified exploratory", not "pre-registered". Say "no effect detected", not "no effect".

`AGENTS.md` additions (both groups paste this):

```
## v2 amendments
- v2 work = new files only: src/*_v2.py or new names, features/v2/, results/v2/, configs/, docs/.
- No src/ feature-building script reads nihss_raw / severity_class. Only A2 reads lesion_side (to flip signs).
- Feature CSVs contain subject_id + features only. Labels live in features/v2/subject_meta.csv.
- Real-label evaluation only through src/run_registry.py on tables tagged features-v2. Dev/tests use shuffled labels or simulated data.
```

### 1.4 File layout and schemas

```
features/v2/
  spectral_abs.csv        # subject_id + 16 abs_AI_{band}_{pair} + all_pdBSI, all_DAR, all_DTABR  (19)
  spectral_lesion.csv     # subject_id + 16 les_AI_{band}_{pair} + the 3 globals (19)  [conditional on A0]
  graph_g8f.csv           # subject_id + 16 g8f_{band}_{metric}
  graph_g24f.csv          # subject_id + 16 g24f_{band}_{metric}
  subject_meta.csv        # subject_id, nihss_raw, severity_class, lesion_side, lesion_side_source,
                          # n_epochs_all, n_epochs_g8f, n_epochs_g24f (+ age/sex/onset if present)
  *.meta.json             # sidecar per table: column list, definition, config hash, git commit, date
  MANIFEST.json           # sha256 of every table
configs/  graph_g8f.json  graph_g24f.json  graph_common.json
```

- band ∈ {delta, theta, alpha, beta}; pair ∈ {F3F4, C3C4, P3P4, O1O2}
- metric ∈ {GlobalEff_absAI, ClustCoeff_absAI, MeanHomotopic, FrobeniusDist}
- Existing v1 tables (`features/figshare_features.csv` `all_*` columns, `features/figshare_graph_features.csv`) are used as they are for registry tests T1 and T4.

### 1.5 Pre-specified registry (summary; Group B owns the full file)

| ID | Test | Feature table | Owner of table |
|---|---|---|---|
| T1 | Ridge regression to NIHSS, spectral signed (baseline) | v1 `all_*` 19 columns | existing |
| T2 | same, spectral absolute | `spectral_abs.csv` | A |
| T3 | same, spectral lesion-aligned (conditional) | `spectral_lesion.csv` | A |
| T4 | same, graph v1 | `figshare_graph_features.csv` | existing |
| T5 | same, graph 8-channel fixed-epoch | `graph_g8f.csv` | A |
| T6 | same, graph up-to-24-channel fixed-epoch | `graph_g24f.csv` | A |
| T7-T9 | Spearman of pdBSI / DAR / DTABR vs NIHSS | v1 columns | existing |

m = 9 tests (8 if A0 finds lesion alignment infeasible). Holm correction across all. **Decision rule:** a test counts as signal only if Holm-adjusted p < 0.05 **and** rank correlation ≥ 0.30. Everything else (SVR, RF regressor, combined A + G8f) is sensitivity only.

### 1.6 Milestones

| Milestone | Group A delivers | Group B delivers |
|---|---|---|
| **M0** kickoff (under 1 h, both) | Agree schema, branches, AGENTS.md amendments | same |
| **M1** | A0 audit, `subject_meta.csv`, `spectral_abs.csv` | Registry draft, harness skeleton, **UCLH channel list** |
| **M2** | A3 audit + `GRAPH_DESIGN_LOCK.md` (frozen configs) | Harness complete and tested, UCLH downloaded and preprocessed |
| **M3** freeze and run | Tag `features-v2` + MANIFEST | Tag `registry-v1`, run registry once, UCLH features |
| **M4** | Common-montage module, report sections | Phase 9, figures, report |

### 1.7 Effort split (relative points, not hours)

| Group A | pts | Group B | pts |
|---|---|---|---|
| A0 Metadata audit | 2 | B1 Registry and plan | 2 |
| A1 Absolute-AI table | 1 | B2 Regression harness and run | 5 |
| A2 Lesion-aligned table | 3 | B3 Stats utilities and validation | 4 |
| A3 Channel and epoch audit, design lock | 5 | B4 UCLH acquisition and audit | 3 |
| A4 Graph v2 library and tests | 5 | B5 UCLH preprocessing and features | 5 |
| A5 Run G8f and G24f | 4 | B6 Phase 9 script | 3 |
| A6 Feature QC report | 3 | B7 Report figures and tables | 3 |
| A7 Freeze, manifest, changelog | 1 | B8 Report sections | 2 |
| A8 Common-montage config for UCLH | 2 | | |
| A9 Report sections (features) | 1 | | |
| **Total** | **27** | **Total** | **27** |

---

## 2. Your Tasks

### A0. Metadata audit (2 pts, first, gates A2 and the registry size)

**Goal:** Learn what clinical metadata exists. This has never been verified.

**Steps**
1. Print the exact column list of the raw `participants.tsv` (location unverified; search the repo/data folder).
2. Look for lesion side, hemiplegia/paralysis side, stroke location, hand dominance, age, sex, days since onset.
3. For any side column: write its **exact semantics** (lesion hemisphere or paralysed body side?) citing the file or dataset README. If only paralysis side exists, lesion hemisphere = opposite. If semantics cannot be verified, mark "UNVERIFIED" and stop A2 until a teammate checks the dataset paper.
4. Value counts overall and crosstabbed with `severity_class`.
5. Build `features/v2/subject_meta.csv` (schema in 1.4). Lesion side vocabulary: `left`, `right`, `bilateral`, `unclear`, `NA`.

**Feasibility rule for A2 (fixed now):** lesion alignment is feasible iff semantics are verified **and** at least 10 subjects have a clear left lesion **and** at least 10 a clear right lesion. Otherwise T3 is dropped (m = 8) and logged.

**Output:** `docs/METADATA_AUDIT.md`, `features/v2/subject_meta.csv`. Tell Group B within the hour.

**Prompt (Gemini 3.1 Pro High, Antigravity, read-only)**
```
Read @AGENTS.md, @docs/PROGRESS.md. READ-ONLY. No edits.
1. Locate participants.tsv (and any dataset README/metadata). Print its exact columns.
2. List every column about lesion/hemiplegia/paralysis side, stroke location, handedness, age, sex, onset time.
3. For each, quote the file and line that defines its meaning. If undefined, say "UNVERIFIED".
4. Show value counts overall and crosstab with severity_class from features/figshare_features.csv.
5. State whether the side column describes the LESION hemisphere or the PARALYSED SIDE. Do not infer; quote or say unverified.
Findings only, no code.
```

### A1. Absolute-AI table (1 pt)

- Read the 16 `all_AI_*` columns from `features/figshare_features.csv` and take `abs()`. Rename to `abs_AI_{band}_{pair}`. Append `all_pdBSI`, `all_DAR`, `all_DTABR`. Write `features/v2/spectral_abs.csv` plus sidecar.
- **Acceptance tests**
  - Shape is (50, 20) including `subject_id`; no NaN/inf.
  - `mean(16 abs_AI columns)` vs `all_pdBSI`: compute the max difference. If about 0, pdBSI is the mean of subject-level |AI|. If not, pdBSI was averaged per epoch before the mean: document this in the sidecar (it matters for how redundant this table is).
  - No label column present.

### A2. Lesion-aligned spectral table (3 pts, conditional on A0)

- `les_AI = s * all_AI` where `s = +1` for left-hemisphere lesion, `-1` for right-hemisphere lesion (ipsilesional minus contralesional, because AI = (L - R) / (L + R)).
- Exclude `bilateral`, `unclear`, `NA`. Log the excluded subjects, the remaining N and counts per severity class. Keep the 3 globals unchanged (already sign-invariant).
- **Acceptance tests** (put in `tests/test_lesion_align.py`)
  - `abs(les_AI) == abs(all_AI)` for every kept subject.
  - Swapping lesion side flips the sign of all 16 columns and nothing else.
  - The script reads `lesion_side` only, never `nihss_raw` or `severity_class` (grep test).
- Output: `features/v2/spectral_lesion.csv` and sidecar listing excluded subjects.

### A3. Channel and epoch audit, then design lock (5 pts)

**Questions to answer from the `*-epo.fif` files** (no label access):
1. Full channel list (the earlier audit said 30), left/right/midline assignment, full homologous pair list, and which pairs are **also** standard 10-20 names (candidates for UCLH transfer).
2. Per-subject clean epoch count (v1 epoch set): min, median, max.
3. Per-channel peak-to-peak (150 uV) rejection rates over **all non-midline channels**, and flat or high-variance channels.
4. How many epochs would additionally be lost under a 24-channel screen.
5. Reproduce the reported r = -0.58: which v1 graph feature, and its Spearman correlation with `n_epochs_all`.
6. Report-only confound check: Spearman of `n_epochs_all` vs `nihss_raw`. It must not change any design choice.
7. Sampling rate from the file headers and the epoch window (the handoff says "2 s buffer + 4 s data + 2 s buffer", the code uses 4.0 s epochs; confirm which is true).

**Design decisions (rules fixed now, applied to the data)**
- **Epoch set for graphs** = v1 clean epochs intersected with passing the 150 uV screen on every channel in the set.
- **N_fixed** = minimum clean-epoch count across subjects if that minimum is at least 15. Otherwise the largest N such that at most 2 subjects must be excluded (report class counts of excluded subjects).
- **Channels (G24f):** keep every symmetric pair. If a channel's overall rejection rate exceeds 25%, drop its **whole pair** (pairs stay symmetric). The final list may be fewer than 24 channels; the name G24f stays and the actual list goes in the sidecar.
- **G8f** = F3, C3, P3, O1 / F4, C4, P4, O2 (the clean core).
- **Subsamples B** = 100, seeds fixed per subject (`42 + subject_index`), draw **without** replacement.

**Output:** `docs/GRAPH_DESIGN_LOCK.md` and `configs/graph_g8f.json`, `configs/graph_g24f.json`. Commit, then **lock**: no changes after M2 without telling Group B.

**Prompt (Gemini 3.1 Pro High, read-only)**
```
Read @AGENTS.md, @docs/PROGRESS.md, @src/preprocessing.py, @src/graph_features.py, @src/load_figshare.py. READ-ONLY, no edits. Do NOT open nihss_raw or severity_class anywhere.
Open the *-epo.fif files (read via a short throwaway python -c, nothing saved).
Report: (1) channel names, left/right/midline, all homologous pairs; (2) clean epoch count per subject (min/median/max); (3) per-channel peak-to-peak rejection rate at 150 uV over all non-midline channels; (4) epochs lost if all those channels must pass; (5) sampling rate from the header and the actual epoch window; (6) which v1 graph feature correlates with n_epochs_all (Spearman) and the value; (7) which wPLI method string and fmin/fmax graph_features.py used.
Findings only. Then propose N_fixed and the channel list using ONLY this rule: [paste the design rules from A3].
```

### A4. Graph v2 library and tests (5 pts)

Create `src/graph_features_v2.py`. **Do not edit** `src/graph_features.py`.

**Method**
1. Per epoch, compute complex cross-spectra for all channel pairs in the band (once per subject; cache in memory). Vectorize wPLI from a subset: `wPLI = |sum(Im S)| / sum(|Im S|)`, computed per frequency, then averaged over the band.
2. For b in 1..B: sample N_fixed epochs without replacement, compute the adjacency matrix. Take the **median** adjacency over b.
3. Weighted graph measures per hemisphere, clipping weights at 0: weighted global efficiency (distance = 1 / w, with an epsilon), weighted clustering (Onnela). Document the library used.
4. Pairing: a `pair_map` from the config reorders A_R to align with A_L.
5. Features per band:
   - `GlobalEff_absAI = |E_L - E_R| / (E_L + E_R)`
   - `ClustCoeff_absAI = |C_L - C_R| / (C_L + C_R)`
   - `MeanHomotopic` = mean wPLI over the homologous cross-hemisphere edges (i, pair(i))
   - `FrobeniusDist = ||A_L - A_R'||_F / (||A_L||_F + ||A_R'||_F)` where A_R' is the aligned A_R
6. Optional signed extras (`GlobalEff_AI`, `ClustCoeff_AI`) are written to `features/v2/extra/` for transparency only; they are not in any registry test.
7. Expose `compute_graph_features(epochs, cfg) -> dict`, which Group B calls on UCLH.

**Unit tests** (`tests/test_graph_features_v2.py`) must pass:
- Perfectly symmetric synthetic network gives Frobenius = 0 and abs asymmetries = 0.
- Swapping left and right leaves all 16 features unchanged (they are sign-invariant).
- With all epochs used, vectorized wPLI matches `mne_connectivity` within 1e-6, or the tolerance is documented.
- Epoch order permutation leaves the output unchanged given the seed; a different seed changes it only slightly.
- Toy graphs with known efficiency and clustering match hand-computed values.
- Output depends on N_fixed, not on the total epoch count.

### A5. Run G8f and G24f (4 pts)

- Run `graph_features_v2` over all 50 subjects with the locked configs. Write `graph_g8f.csv`, `graph_g24f.csv` plus sidecars and `n_epochs_g8f`, `n_epochs_g24f` into `subject_meta.csv`.
- Log runtime, any excluded subject and the reason.
- If a subject cannot meet N_fixed, apply the A3 exclusion rule exactly. Do not improvise.

### A6. Feature QC report (3 pts)

Write `docs/FEATURE_QC_V2.md`. All checks are label-free (R1):
- NaN/inf, constant or near-constant columns, ranges, per table.
- **Epoch-bias check:** Spearman of every feature in v1 graph, G8f and G24f against `n_epochs_all`. Target: |r| < 0.3 after the fix. If some still fail, **report them, don't tune to remove them against the labels.**
- **Stability:** rerun with a second subsample seed. Spearman between runs per feature; flag those below 0.9.
- **Collinearity:** correlation matrices; flag pairs with |r| > 0.95; report the correlation of efficiency/clustering asymmetry with `MeanHomotopic` (dense-graph redundancy).
- Confirm no label column in any feature file.

### A7. Freeze, manifest, changelog (1 pt)

- Write `features/v2/MANIFEST.json` (sha256 per table) and `docs/FEATURE_CHANGELOG.md` (what changed vs v1 and why).
- Open a PR, get both reviews (R8), merge, then `git tag features-v2`.
- Tell Group B in writing: "tables frozen, hash list attached".

### A8. Common-montage config for UCLH (2 pts, after Group B's montage list)

- Intersect Figshare's symmetric pairs with the UCLH channel list from `docs/UCLH_MONTAGE.md`.
- Write `configs/graph_common.json`. Rerun the library on Figshare with that config for later comparison. This set is **not** a registry test and is used only in Phase 9 (descriptive).
- If the intersection is only the 8-channel core, say so; the expansion then offers nothing transferable.
- Fallback if the list is late: use the 10-20 pairs (Fp1/Fp2, F3/F4, F7/F8, C3/C4, T3-T7/T4-T8, P3/P4, T5-P7/T6-P8, O1/O2), clearly labelled as an assumption.

### A9. Report sections (1 pt)

Write the Methods (feature definitions, graph construction, fixed-count subsampling) and the feature-related Limitations: coarse delta resolution (n_fft = 256 at 500 Hz is about 1.95 Hz per bin), motor imagery vs resting state, unthresholded dense graphs, label noise at the NIHSS 4/5 boundary, reference scheme differences.

---

## 3. Handoff Interface to Group B

- B reads tables only through the sidecar column lists, never by dropping columns.
- A promises: frozen tables + MANIFEST, `compute_graph_features(epochs, cfg)`, configs, and a plain-language definition per column in the sidecars.
- B promises: the UCLH channel list by M1, no edits to A's files.
- Disagreements go to `docs/PROGRESS.md` under "Open issues", resolved before M3.

## 4. Risks (yours)

| Risk | Mitigation |
|---|---|
| Temptation to peek at feature-NIHSS relations "just to check the fix worked" | R1. Judge fixes only by epoch-count correlations and stability. |
| Lesion semantics wrong, so signs flipped the wrong way | A0 requires a quote or "UNVERIFIED"; the sign-flip test is written to be reversible and documented. |
| Fixed-N too small, so noisy wPLI | The A3 rule uses the largest feasible N; stability check in A6. |
| Different epoch sets across tables confuse comparisons | Record epochs used per table in `subject_meta.csv`. |
| Library mismatch with MNE | The A4 equivalence test. |

## 5. Definition of Done

- All 4 v2 tables (3 if T3 dropped) + `subject_meta.csv` + sidecars + MANIFEST committed and tagged `features-v2`.
- `GRAPH_DESIGN_LOCK.md`, `METADATA_AUDIT.md`, `FEATURE_QC_V2.md`, `FEATURE_CHANGELOG.md` written.
- All tests green; both reviews done; PROGRESS.md updated.
- Nothing in the repo associates a v2 feature with a label.

## 6. AI Tool Plan for This Track

| Task | Tool |
|---|---|
| A0, A3 audits | Gemini 3.1 Pro (High), read-only |
| A1, A2 | Copilot (Haiku 4.5 or GPT-5 mini), small and well-specified |
| A4 library and tests | Claude Sonnet 4.6 (Thinking), Planning mode |
| Reviews | Codex GPT-5.5 High (different family) |
| Stuck twice on the same bug | Opus 4.6 |
| Quota exhausted | Gemini for reasoning, Codex for building; use the handoff prompt from before |

**Build prompt for A4 (Sonnet)**
```
Read @AGENTS.md, @docs/GRAPH_DESIGN_LOCK.md, @configs/graph_g8f.json. Create src/graph_features_v2.py and tests/test_graph_features_v2.py. Do not modify any existing file. Do not read nihss_raw or severity_class. Do not run on real subjects yet.
Implement: per-epoch cross-spectra cache; vectorized wPLI from an epoch subset; B fixed-size subsamples WITHOUT replacement with per-subject seed; median adjacency; weighted global efficiency (distance=1/w) and Onnela clustering; pair_map alignment; the 4 metrics per band with these exact definitions: [paste step 5]. Expose compute_graph_features(epochs, cfg)->dict with names {set}_{band}_{metric}.
Tests: [paste the six unit tests]. Give a short plan first (under 15 lines), then implement. Show a summary of assumptions at the end.
```

**Review prompt (Codex, read-only)**
```
Read @AGENTS.md. REVIEW ONLY. Audit src/graph_features_v2.py and its tests. PASS/FAIL with line numbers: (1) any access to label columns; (2) subsampling without replacement and seed reproducibility; (3) wPLI formula correctness and equivalence test; (4) weighted metrics definitions; (5) pair alignment of A_R; (6) behaviour when a subject has fewer than N_fixed epochs; (7) output column names match the schema. Numbered findings: severity, file:line, problem, exact fix. End with "Safe to run" or "Fix first".
```
