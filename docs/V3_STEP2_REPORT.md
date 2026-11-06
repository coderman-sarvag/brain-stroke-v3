# V3 Step 2 Report: EEG Preprocessing and Epoching

**Date:** 2026-11-06. **Branch:** `fix/flowchart-pipeline`. **Status:** DONE. The final run passed all acceptance checks, with the limitations listed in section 7.

**Code / config:** `src/preprocess_v3.py`, `configs/v3/preprocess.json` (approved state, sha256 `dfab3c5c…0220bd`, identical in the final run's provenance), `src/paths_v3.py`, `kaggle/run_v3.py`, `kaggle/requirements_kaggle.txt`.
**Tests:** `tests/test_preprocess_v3.py`, `tests/test_paths_kaggle_v3.py`, `tests/test_data_v3.py`; full repo suite 84/84 locally. The tests were not run on Kaggle.
**Runs (both on Kaggle, 4 CPUs, Python 3.13):**

| Run | Commit | Mode | Subjects | Result |
|---|---|---|---|---|
| Diagnostic | `15e5b69` (clean) | `--mode diagnostic` | 48 | 48 ok, 0 failed |
| Final | `2f28f05` (clean) | `--mode final`, Step 0 from the uploaded Kaggle dataset (`--raw-source`) | 48 | 48 ok, 0 failed; **45 included** |

Final run timings: Step 0 614 s (copy and verification), Step 1 20 s, Step 2 429 s. In both runs, the config sha256 recorded on Kaggle equals the committed `configs/v3/preprocess.json` at that commit.

**Label blindness:** Step 2 reads only `exclude_v3` from `subject_meta_v3.csv` and the Step 1 marker events. No NIHSS, severity, MBI or mRS value was read. Every threshold was fixed in config before data were processed. The screen rule and per-class minimum were chosen from the label-free epoch-count distribution.

## 1. Pipeline (per subject, on the continuous recording; handoff Step 2 order)

1. **Load:** 30 EEG channels + HEOL/HEOR (type `eog`, each kept separately); marker channel dropped. Channels renamed to 10-10 (Fp1/Fp2, T7/T8, P7/P8) and the `standard_1020` montage set. Only the 48 included subjects (sub-04/05 excluded in Step 1).
2. **Bad channels:** `pyprep.NoisyChannels` with the PREP published defaults (deviation z > 5, correlation < 0.4 in > 1% of 1 s windows, HF-noise z > 5, SNR, RANSAC with seed 42), run on the unfiltered recording with **CPz and EOG excluded** from detection.
3. **Filter:** 1–40 Hz zero-phase FIR. No notch, because 50 Hz is beyond the stop band; the 48–52 Hz power share fell from a median of 5.9 × 10⁻⁵ to 1.3 × 10⁻⁶.
4. **Re-reference:** average reference over the good channels, **CPz included as the zero-valued online reference**.
5. **Interpolate:** spherical spline from the re-referenced good channels, **except when both channels of a homologous pair are bad**. That pair stays bad and is recorded as unavailable. Average reference applied again.
6. **ICA:** Picard (extended), 20 components, seed 97. `find_bads_eog` runs **separately on HEOL and on HEOR** (z > 3), with no bipolar channel, and the union is removed. Guard: a subject with more than 9 bad channels is flagged and ICA is not run. The guard never triggered (maximum 6 bad channels).
7. **Epochs:** 0–4 s (2000 samples) from the **per-subject marker onsets** of Step 1 (usable trials only), never from the shared sidecar.
8. **Screen, rule (iii) `analysed_after_marking`:** any of the 22 analysed channels that alone exceeds 150 µV peak-to-peak in ≥ 30% of a subject's epochs is marked and interpolated on the epochs (left bad, pair unavailable, if its homologous partner is also bad). The average reference is re-applied, then epochs over 150 µV on any available analysed channel are dropped.
9. **Classes:** **no left/right equalization**. Every clean epoch is kept with its class (event code + `hand` metadata). Later steps compute each feature per class and average the two class means.
10. **Inclusion:** a subject needs **≥ 10 clean epochs in each class**. Excluded subjects get no epoch file.

## 2. Diagnostic run: choosing the screen rule (label-free)

Epochs surviving per subject, out of 40 usable trials, N = 48:

| Rule | Total: median [min–max] | Smaller class: median [min–max] | Smaller class < 10 | < 5 | = 0 |
|---|---|---|---|---|---|
| (i) 150 µV, all scalp channels | 35.5 [3–40] | 17 [0–20] | 11 | 2 | 1 |
| (ii) 150 µV, 22 analysed channels | 37 [6–40] | 18 [1–20] | 6 | 1 | 0 |
| (iii) (ii) after marking channels ≥ 30% | 37 [15–40] | 18 [2–20] | **3** | 1 | 0 |

Across the cohort, rejections were driven mostly by Fp1/Fp2 (mean 13–14% of epochs; 7 subjects ≥ 30%), then F7, F8 and FT8. The occipital pattern seen in the first two test subjects (sub-06, sub-13) does not generalise. **User decision (2026-11-06): rule (iii) with ≥ 10 epochs per class.** The minimum was proposed before the diagnostic and kept unchanged.

## 3. Final run: cohort results

| Item | Result |
|---|---|
| Subjects processed / failed | 48 / 0 |
| **Included** | **45** (1,592 epochs) |
| **Excluded: < 10 epochs in a class** | **sub-06** (11/8), **sub-27** (8/12), **sub-40** (2/13), as the diagnostic predicted |
| Epochs per included subject | median 37 [24–40] |
| Smaller class per included subject | median 18 [10–20] |
| Subjects with ≥ 1 bad channel | 40/48. 91 bad channels in total, max 6 (sub-38, flagged > 20% bad). Detections, which overlap: RANSAC 38, correlation 29, deviation 19, HF noise 12, SNR 1 |
| Channels marked by rule (iii), included subjects | sub-08 F8, T8; sub-13 O1, O2; sub-24 P8; sub-33 F4; sub-35 F7; sub-39 TP8 |
| ICA | 20 components in every subject; 59 removed in total. 34 flagged by HEOL, 35 by HEOR, 10 by both. 5 subjects had components flagged only by HEOL, 11 only by HEOR; none removed in 12 subjects |
| **Analysed pairs unavailable (included subjects)** | **sub-13 O1–O2, sub-29 T7–T8, sub-30 T7–T8, sub-31 C3–C4.** Fp1–Fp2 (not analysed) in 8 subjects |

HEOR flags different components from HEOL in many subjects. That suggests it carries ocular activity that HEOL does not, which fits, but does not prove, the sidecar's label of it as vertical (VEOR).

## 4. HEOG vs frontal asymmetry (handoff acceptance), 45 included subjects, kept epochs

Per subject: Spearman ρ between the epoch-wise asymmetry index (L − R)/(L + R) and log EOG band power, before ICA (re-referenced, interpolated) vs after ICA, on the same epochs.

| Asymmetry vs EOG power | Median \|ρ\| before → after | Subjects with \|ρ\| > 0.3 |
|---|---|---|
| F3/F4 vs HEOL, delta | 0.288 → 0.165 | 19 → 9 |
| F3/F4 vs HEOR, delta | 0.294 → 0.130 | 22 → 10 |
| F3/F4 vs HEOL, 1–40 Hz | 0.276 → 0.189 | 20 → 10 |
| F3/F4 vs HEOR, 1–40 Hz | 0.283 → 0.144 | 21 → 11 |
| F7/F8 vs HEOL, delta | 0.196 → 0.133 | 16 → 10 |
| F7/F8 vs HEOR, delta | 0.250 → 0.188 | 19 → 11 |
| F7/F8 vs HEOL, 1–40 Hz | 0.214 → 0.154 | 12 → 9 |
| F7/F8 vs HEOR, 1–40 Hz | 0.321 → 0.170 | 23 → 10 |

ICA roughly halves the coupling, and the median |ρ| is now below 0.2 everywhere. **About 9–11 of 45 subjects still exceed 0.3.** Frontal asymmetry is no longer dominated by eye movement at the cohort level, but residual ocular influence remains in a minority of subjects (limitation L3).

## 5. Acceptance checks

| Handoff Step 2 criterion | Result |
|---|---|
| CPz non-zero after re-referencing | **PASS**: 48/48 (CPz was constant 0 before in 48/48) |
| No interpolation used an all-zero channel | **PASS**: smallest good-channel SD > 0 in 48/48; code refuses otherwise |
| Frontal asymmetry no longer dominated by HEOG (before vs after ICA) | **PASS with limitation**: section 4 |
| Unit tests on synthetic data | **PASS**: 84/84 locally (pair rule, CPz handling, zero-channel guard, marker epoching, ICA EOG removal, three screen rules, guard, resume, path roots) |
| Per subject: bad, interpolated, ICA components and flagging EOG channel, epochs kept, left/right counts | **Done**: Appendix |
| Minimum-epoch threshold from the epoch-count distribution only, reported before applying | **Done**: proposed ≥ 10 per class before the diagnostic, confirmed from the label-free distribution, approved by the user |

## 6. What failed or changed on the way (disclosed)

1. **First local full run crashed:** one subject lost every left-hand epoch under the original all-scalp screen, and equalization failed on the empty class. The stale outputs were deleted. Empty classes are now handled, and equalization was removed (reviewer change D6).
2. **The all-scalp 150 µV screen was too harsh** (60–75% of epochs lost in the first trial). This led to the label-free diagnostic and the rule choice (D7). The threshold value itself (150 µV) was never changed.
3. **Interim status PDF error:** `docs/V3_STEP2_STATUS.pdf` (uncommitted) wrongly said EOG detection becomes impossible above 9 bad channels; it is only impossible above 18. The reviewer's 9-channel guard was adopted anyway, as a stricter rule (D8). The PDF also guessed that edge channels drive rejections. Cohort-wide, Fp1/Fp2 and lateral frontal channels do, but the first two test subjects were occipital-driven.
4. **Kaggle Step 0 got HTTP 403** from the Figshare API. Fix (D13): stored md5/sha256, offline reuse, `--raw-source`, browser User-Agent. The final run staged the data from the uploaded Kaggle dataset without contacting Figshare, and all 50 EDFs matched their stored sha256.
5. An ICA unit test first used 10 components, which is too few for the z > 3 rule ((n−1)/√n = 2.85). Only the test was corrected.

All deviations from the handoff are listed in `docs/V3_HANDOFF_DEVIATIONS.md` (D5–D13 for this step).

## 7. Limitations carried forward

- **L1 Left/right order** comes from the shared sidecar via marker matching and cannot be verified per subject (Step 1).
- **L2 Second EOG channel identity** (HEOR in the EDF vs VEOR in the sidecar) remains unverified. Both channels are used separately.
- **L3 Residual ocular coupling** remains in about 10 of 45 subjects (section 4).
- **L4 Missing analysed pairs:** sub-13 O1–O2, sub-29 and sub-30 T7–T8, sub-31 C3–C4. Steps 3–6 must set those pair features to missing, not impute them. For sub-31 the core motor pair is lost.
- **L5 Epoch-level interpolation** under rule (iii) in 6 included subjects; the marked channels are listed in the Appendix.
- **L6 Near-duplicate recordings** 11/15 and 47/49 give near-identical preprocessing results (11 and 15 have identical rows). They are kept as shared split groups for Step 8.
- **L7 Environment:** the final outputs come from Kaggle (Python 3.13, numpy 2.1.3, scipy 1.16.3, pandas 2.3.3, scikit-learn 1.6.1), not the local venv (Python 3.12, numpy 2.5.3). Later steps should run in the same Kaggle environment.
- **L8 Epoch files** (`data/processed/figshare_v3/sub-XX-epo.fif`, about 1 GB) exist only in the Kaggle notebook output, not locally and not in git. Step 3 needs that saved notebook version as an input, or Step 2 re-run on Kaggle (seeded, so it should be deterministic in the same environment).

## 8. Outputs

| File | Where | Content |
|---|---|---|
| `data/processed/figshare_v3/sub-XX-epo.fif`, `sub-XX-ica.fif` | Kaggle notebook output only | 45 included subjects; class per epoch; unavailable pairs in `info['bads']` |
| `features/v3/epoch_qc_v3.csv` | Kaggle zip (git-ignored folder locally) | Per subject: `include_v3_epochs`, `excluded_reason`, bad/interpolated channels, marked channels, unavailable pairs, epochs kept per class |
| `results/v3/step2/preprocess_log.csv`, `heog_check.csv`, `preprocess_summary.json`, `subjects_final/*.json` | Kaggle zip | Full per-subject log, HEOG table, cohort summary with provenance |
| `results/v3/step2/diagnostic_*.csv/json` | Diagnostic Kaggle zip | Per-channel exceedance, per-rule counts |

## Appendix: per-subject results (final run, commit `2f28f05`)

ICA columns list the component indices flagged by each EOG channel ("-" = none). "Marked" lists channels interpolated (or made unavailable) on the epochs by rule (iii). "Unavailable pairs" are final, including Fp1–Fp2, which is not analysed.

| Subject | Incl. | Bad channels (continuous) | Interpolated | ICA removed: HEOL / HEOR | Marked (rule iii) | Unavailable pairs | Epochs kept (L/R) |
|---|---|---|---|---|---|---|---|
| sub-01 | yes | - | - | 0, 1 / 0 | - | - | 40 (20/20) |
| sub-02 | yes | FT8, P3 | FT8, P3 | 2 / 0 | - | - | 37 (19/18) |
| sub-03 | yes | Cz, FC4, O1, Oz | Cz, FC4, O1, Oz | 4 / 2 | - | - | 37 (18/19) |
| sub-06 | **no** | T8 | T8 | - / 1 | FT8, O1, O2, P7 | O1-O2 | 19 (11/8) |
| sub-07 | yes | FT8 | FT8 | - / 1 | - | - | 33 (14/19) |
| sub-08 | yes | Cz | Cz | 7, 10 / 7 | F8, T8 | - | 29 (15/14) |
| sub-09 | yes | - | - | 2 / 1 | - | - | 40 (20/20) |
| sub-10 | yes | Fp1, Fp2, P7 | P7 | 1 / 0 | - | Fp1-Fp2 | 40 (20/20) |
| sub-11 | yes | Cz | Cz | 3 / 1, 3 | - | - | 35 (17/18) |
| sub-12 | yes | C4, CP3, TP8 | C4, CP3, TP8 | 0, 1 / 0 | - | - | 38 (19/19) |
| sub-13 | yes | CP3, Cz, Fp1 | CP3, Cz, Fp1 | 17 / - | O1, O2 | O1-O2 | 30 (17/13) |
| sub-14 | yes | F8 | F8 | 1 / 0 | - | - | 40 (20/20) |
| sub-15 | yes | Cz | Cz | 3 / 1, 3 | - | - | 35 (17/18) |
| sub-16 | yes | CP3, Pz | CP3, Pz | - / - | - | - | 32 (16/16) |
| sub-17 | yes | Fp2 | Fp2 | 4 / 0 | - | - | 39 (19/20) |
| sub-18 | yes | F7, Fp1 | F7, Fp1 | - / - | - | - | 34 (18/16) |
| sub-19 | yes | F8, FT8, Fp2 | F8, FT8, Fp2 | 2 / - | - | - | 31 (14/17) |
| sub-20 | yes | Fp1 | Fp1 | 0, 3 / 0, 3 | - | - | 35 (19/16) |
| sub-21 | yes | FC3 | FC3 | - / - | - | - | 33 (16/17) |
| sub-22 | yes | F7 | F7 | - / - | - | - | 30 (12/18) |
| sub-23 | yes | Cz | Cz | 5 / - | - | - | 40 (20/20) |
| sub-24 | yes | O2 | O2 | - / - | P8 | - | 25 (12/13) |
| sub-25 | yes | Cz, Fp2 | Cz, Fp2 | 5 / - | - | - | 31 (15/16) |
| sub-26 | yes | F8, Fp2 | F8, Fp2 | 0, 1 / 0 | - | - | 39 (19/20) |
| sub-27 | **no** | C3, CP3 | C3, CP3 | - / - | FT8, T7 | - | 20 (8/12) |
| sub-28 | yes | F4, FT8, Oz, Pz, TP7 | F4, FT8, Oz, Pz, TP7 | 1, 2 / 0 | - | - | 40 (20/20) |
| sub-29 | yes | CP4, Fp1, T7, T8 | CP4, Fp1 | - / 0 | - | T7-T8 | 38 (20/18) |
| sub-30 | yes | FT8, Fp1, T7, T8, TP7 | FT8, Fp1, TP7 | 1, 4 / 0 | - | T7-T8 | 37 (18/19) |
| sub-31 | yes | C3, C4 | - | - / 4 | - | C3-C4 | 38 (20/18) |
| sub-32 | yes | C3, F3, P4 | C3, F3, P4 | - / 0 | - | - | 39 (20/19) |
| sub-33 | yes | Fp1, Fp2, Pz | Pz | - / 2 | F4 | Fp1-Fp2 | 27 (14/13) |
| sub-34 | yes | Fp1, Fp2 | - | 2 / 0 | - | Fp1-Fp2 | 34 (17/17) |
| sub-35 | yes | - | - | - / - | F7 | - | 24 (10/14) |
| sub-36 | yes | T7, TP8 | T7, TP8 | - / 0 | - | - | 40 (20/20) |
| sub-37 | yes | Fp1, Fp2 | - | 1, 2 / 0 | - | Fp1-Fp2 | 39 (20/19) |
| sub-38 | yes | C4, F4, FT8, Fp2, Pz, T7 | C4, F4, FT8, Fp2, Pz, T7 | - / - | - | - | 38 (19/19) |
| sub-39 | yes | Cz, P3, Pz | Cz, P3, Pz | - / - | TP8 | - | 30 (15/15) |
| sub-40 | **no** | - | - | - / - | F4, F8, FT7, FT8, O2 | FT7-FT8 | 15 (2/13) |
| sub-41 | yes | Fp1, Fp2 | - | - / 0 | - | Fp1-Fp2 | 39 (20/19) |
| sub-42 | yes | Fp2, Pz | Fp2, Pz | 3 / 0, 3 | - | - | 39 (20/19) |
| sub-43 | yes | Fp1 | Fp1 | 6 / - | - | - | 29 (16/13) |
| sub-44 | yes | Fp1, Fp2 | - | 3 / 1 | - | Fp1-Fp2 | 39 (19/20) |
| sub-45 | yes | FCz, FT8, Fp1, Fp2 | FCz, FT8 | - / 0 | - | Fp1-Fp2 | 36 (18/18) |
| sub-46 | yes | - | - | - / - | - | - | 37 (18/19) |
| sub-47 | yes | - | - | - / 2 | - | - | 38 (19/19) |
| sub-48 | yes | - | - | 1, 3 / 1 | - | - | 37 (19/18) |
| sub-49 | yes | - | - | - / 2 | - | - | 38 (19/19) |
| sub-50 | yes | C3, Fp1, Fp2 | C3 | - / - | - | Fp1-Fp2 | 33 (16/17) |
