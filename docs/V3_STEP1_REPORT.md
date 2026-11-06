# V3 Step 1 Report: Data Integrity (label-blind)

**Date:** 2026-11-06. **Branch:** `fix/flowchart-pipeline`. **Status:** PASSED, with one user decision recorded and a major event-timing finding that Step 2 must use.

**Code / config:** `src/integrity_v3.py`, `configs/v3/integrity.json`. **Tests:** `tests/test_integrity_v3.py` (7) + `tests/test_provenance_v3.py` (1). All v3 tests 14/14; full repo suite 61/61.
**Outputs:** `features/v3/subject_meta_v3.csv` (tracked; metadata only). Local only (git-ignored): `results/v3/step1/integrity.json`, `pairwise_similarity.csv`, `event_timing.csv`, `marker_events.csv`.

**Label blindness:** `participants.tsv` is read through an explicit `usecols` allow-list (ID, sex, age, duration, paralysis side, handedness, first-stroke, stroke location). NIHSS, MBI and mRS are never loaded, and a guard refuses to write the meta file if any outcome column appears. `subject_meta_v3.csv` therefore holds **no labels yet**. NIHSS and severity class will be attached in Step 8 by a separate label-join step after the freeze, so that no pre-freeze code touches outcomes. Every rule below is written in the config and was fixed from signal or metadata only.

## 1. Duplicate recordings (all 1,225 pairs)

Zero-lag raw comparison of the 32 named channels. CPz is constant and excluded per pair, leaving 31 compared.

| Pair | Result | Median r | Min r |
|---|---|---:|---:|
| sub-04 / sub-05 | **identical**: 31/31 channels sample-for-sample equal | 1.0 | 1.0 |
| sub-11 / sub-15 | near-duplicate | 0.99986 | 0.99937 |
| sub-47 / sub-49 | near-duplicate | 0.99989 | 0.99955 |
| every other pair | unrelated; highest median r = **0.117** | | |

There are no new duplicates beyond the three known from v2, and the separation is very wide (0.117 vs ≥ 0.9994).

**Decision (user, 2026-11-06): exclude both sub-04 and sub-05** from all v3 analyses (`exclude_v3 = True`). The correct label for that EEG cannot be known. Supporting facts: 56 M left fronto-parietal cortex vs 44 F left pons; sub-05's own record is internally inconsistent (left pons with left paralysis); both are on the paper's motion list. **sub-11/15 and sub-47/49 are kept**, each pair sharing one `split_group` for `StratifiedGroupKFold`. **v3 cohort: N = 48, 46 split groups.**

## 2. Event timing (major finding)

The blank-named EDF channel is the **marker channel**. It carries one-sample codes 1/2/3 (instruction / imagery / break) and no left/right code. I decoded every change to a non-zero code and compared it with the shared sidecar trial by trial.

- **Imagery markers per subject:** 46 subjects have exactly 40. sub-13, sub-18 and sub-20 have 41: a spurious imagery code ~0.5 s before the recording ends, cut off at 198–269 samples. sub-43 has 42: two extra codes between trials.
- **Agreement with the sidecar** (all trials within 50 ms, 40 matched, no extras): **35/50**. With the originally pre-set 20 ms tolerance: 11/50. Typical lag is 2–11 samples (median 9; 4–22 ms), a constant recording latency. The tolerance was widened to 50 ms after seeing this label-independent latency; both counts are reported.
- **Real misalignments in 15 subjects:**
  - **Trial started 2 s early** (lag −999 samples; the instruction phase was skipped, but imagery still lasted 4 s): sub-08 (1 trial), 13 (1), 14 (2), 20 (together with drift; 6 trials outside 50 ms in total), 22 (2), 24 (1), 25 (1), 29 (3), 30 (1), 40 (3), 43 (5), 48 (2). Epoching from the sidecar would capture 2 s of imagery + 2 s of break for these trials.
  - **Drift:** **sub-06 is late on 39/40 trials, by up to 830 samples (1.66 s)**. sub-40 is late by 150 samples (0.3 s) on 10 trials. sub-20 is late by up to 200 samples. sub-10 is 28 samples late on one trial.
- **Fix:** each marker imagery onset is matched one-to-one (closest first) to a sidecar trial within ±2000 samples (half the 8 s trial period). A trial is usable when it is matched and has full 4 s imagery. Result: **all 50 subjects have exactly 40 usable trials (20 left / 20 right), 2,000 in total.** The spurious end-of-recording codes and sub-43's two extras are unmatched and dropped.
- **Consequence for Step 2:** epoch from `marker_onset` (per subject) in `results/v3/step1/marker_events.csv`, not from the shared sidecar. The v1/v2 pipelines used the sidecar for every subject, so sub-06 in particular was mis-epoched there (documented, not changed).
- **Limitation (unverifiable):** left/right comes from the matched sidecar trial; the marker channel cannot confirm the per-subject order. Primary features use the pooled `all` condition, so this affects only left/right count equalization.

## 3. Rest data: CLOSED

Absent. 40 trials × 8 s = 320 s equals every recording's length, and the first event is at 1 ms.

## 4. Channel labels: EDF vs BIDS sidecar mismatch

`task-motor-imagery_channels.tsv` lists 31 channels: 29 EEG + `HEOL` (EOG) + **`VEOR`** (EOG, vertical). The EDF has 30 EEG (including **CPz**) + `HEOL` + **`HEOR`** + the marker channel.
- CPz is absent from the sidecar, which is consistent with CPz being the reference.
- The second EOG channel is `HEOR` in the EDF and `VEOR` in the sidecar. **Treated as UNVERIFIED (possibly vertical).** In Step 2 each EOG channel goes to `find_bads_eog` separately, with no bipolar HEOL−HEOR derivation. Step 0 found HEOL/HEOR anti-correlated (r = −0.44 in sub-01), which does not settle the question.

## 5. Paralysis side: paper vs data discrepancy

`participants.tsv`: **28 left / 22 right**. Paper: 27 left / 23 right. The source TSV is authoritative, so this is recorded as a paper-vs-data discrepancy, not an error.

## 6. Motion-artifact subjects

`motion_artifact_paper = True` for the paper's 13 subjects (4, 5, 13, 14, 18, 24, 28, 33, 42, 43, 47, 48, 49); 11 remain after the 04/05 exclusion. Not excluded; the flag is for a Step 8 sensitivity analysis.

## 7. Lesion side and site class

The final side is the contralateral side of the paralysis, kept only when the side parsed from `stroke_location` agrees. Otherwise it is `uncertain`, and the subject is excluded from lesion-aligned analyses only.

| | All 50 | v3 cohort (48) |
|---|---:|---:|
| Final left lesion | 19 | 18 |
| Final right lesion | 23 | 23 |
| Uncertain | 8 | 7 |

Uncertain subjects and reasons:

| Subject | Reason |
|---|---|
| sub-21, sub-33 | "Pons", no side |
| sub-38 | Right pons with right paralysis (conflict) |
| sub-05 | Left pons with left paralysis (conflict; excluded anyway) |
| sub-03, sub-35 | Bilateral component |
| sub-20, sub-48 | Left and right components |

The handoff's flagged set (21, 33, 38, plus 03 and 05 for review) is fully contained in this set. 20, 35 and 48 are added by the same pre-set rule.

**Rule correction (disclosed):** the first run split `stroke_location` on "and" as well as commas, which wrongly made sub-22 ("Right temporo-parietal occipital lobe and insula, …") unclear. The rule now splits on commas only. It was corrected before any outcome was read.

**Site class (cohort of 48):** subcortical supratentorial 21, infratentorial 18, cortical-involving 9. Twenty of 50 have an infratentorial component. This supports the handoff's caveat that scalp-EEG asymmetry may be weak for many of these lesions.

## 8. Fix to Step 0 output (disclosed)

`provenance_v3.write_with_config` copied the config beside the output under the config's own filename. When the output had the same name (`data_check.json`), the copy overwrote the result. The Step 0 numbers were unaffected (the CSV and console output were correct), but `results/v3/step0/data_check.json` held the config. The fix saves the copy as `<config>.config.json` and refuses to overwrite the output; there is a new regression test. Step 0's check was re-run and still accepts 50/50.

## Acceptance

| Criterion | Result |
|---|---|
| Every decision listed with its rule | Yes: config `rule` fields plus this report |
| Rules fixed before any outcome is read | Yes; no outcome column is ever loaded |
| Meta file has no feature columns | Yes: 23 metadata/QC columns, no features, no labels |

## `subject_meta_v3.csv` columns

`subject_id, sex, age, duration_days, paralysis_side, handedness, is_first_stroke, stroke_location, location_side, lesion_side_paralysis, lesion_side_agree, lesion_side_final, site_class, has_infratentorial, motion_artifact_paper, split_group, duplicate_status, exclude_v3, exclude_reason, sidecar_agrees, n_usable_trials, n_usable_left, n_usable_right`
