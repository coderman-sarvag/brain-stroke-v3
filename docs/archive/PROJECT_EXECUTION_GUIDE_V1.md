# EEG-Based Stroke Severity Classification via Interhemispheric Asymmetry
## Technical Execution Guide for Agent Handoff

---

## 0. How to use this document (read this first, every time)

This guide is split into numbered **Phases**, each split into numbered **Sub-phases**. Every sub-phase has:
- **Objective** — what "done" means
- **Inputs** — what must already exist before starting
- **Steps** — exact actions to take
- **Outputs** — exact files/artifacts this sub-phase must produce
- **Validation** — how to confirm it actually worked before moving on
- **Debug notes** — known failure modes and how to fix them

### Mandatory protocol for every agent picking this up

1. Scroll to **Section 1: PROGRESS LEDGER** below. It tells you exactly which sub-phase is next.
2. Before doing anything, verify the **Outputs** of the last completed sub-phase actually exist on disk and pass their **Validation** check. If they don't, STOP and fix that sub-phase first — do not proceed on an assumption that prior work is correct.
3. Do only the current sub-phase. Do not skip ahead, even if it looks quick to combine steps.
4. When a sub-phase's outputs are produced and validated, update the PROGRESS LEDGER row: set status to `DONE`, fill in the date, and write 1–2 lines in "Notes" describing anything the next agent needs to know (e.g. "used 4 electrode pairs instead of 5, see note in 3.2").
5. If you hit an error you cannot resolve, set status to `BLOCKED`, describe the exact error and what you tried in "Notes", and stop. Do not guess past a blocker silently.
6. Never modify a sub-phase's already-`DONE` outputs without also changing its ledger status back to `IN PROGRESS` and explaining why in Notes.

---

## 1. PROGRESS LEDGER (update this every session)

| Phase | Sub-phase | Description | Status | Date | Notes |
|---|---|---|---|---|---|
| 0 | 0.1 | Environment setup | DONE | 2026-09-18 | Created `venv` with Python 3.13 and installed the required scientific, EEG, ML, plotting, and download packages. Import validation passed. |
| 0 | 0.2 | Repo structure setup | DONE | 2026-09-18 | Created the documented data, features, src, notebooks, results, and tests directories. Frozen environment saved to `requirements.txt`. |
| 1 | 1.1 | Acquire Figshare dataset | DONE | 2026-09-18 | Downloaded and checksum-validated the official Figshare EDF archive (50 subjects), plus `participants.tsv` with NIHSS, MBI, mRS, and paralysis-side fields. The 1.87 GB sourcedata archive was not needed for the EDF pipeline. |
| 1 | 1.2 | Verify Figshare data integrity | DONE | 2026-09-18 | All 50 EDFs opened successfully at 500 Hz. MNE exposes 33 channels consistently: 30 named EEG channels plus HEOL, HEOR, and one blank label; downstream code selects the 30 EEG channels explicitly. Full log saved to `results/metrics/figshare_integrity_check.txt`. |
| 2 | 2.1 | Load & inspect Figshare raw EEG | DONE | 2026-09-18 | EDFs contain no embedded annotations or stim channel. The official external BIDS sidecar defines 40 imagery events per subject, split 20 left-hand/20 right-hand; mapping and loader are in `src/load_figshare.py`, with report in `results/metrics/figshare_event_inspection.txt`. |
| 2 | 2.2 | Filter + epoch Figshare EEG | DONE | 2026-09-18 | Applied 1-40 Hz band-pass and 50 Hz notch filters, then saved 4-second imagery epochs for all 50 subjects. Each output has shape `(40, 30, 2000)` with 20 left-hand and 20 right-hand epochs; artifact rejection is deferred to 2.3. |
| 2 | 2.3 | Artifact/subject exclusion | DONE | 2026-09-18 | Rejection is restricted to the 8 feature channels at 150 µV. Channels rejected in at least 20/40 epochs were interpolated from a normalized standard 10-20 montage for `sub-06` (O1/O2), `sub-13` (O1/O2), `sub-33` (F4), and `sub-40` (O1/O2). Final retention is 1,731/2,000 epochs; 4 subjects remain flagged, including `sub-13` with 4 epochs. |
| 3 | 3.1 | Band power extraction (Figshare) | DONE | 2026-09-19 | Computed Welch PSD power for delta, theta, alpha, and beta across the 8 approved feature channels. Saved 50 NPZ files with `all`, `left_hand`, and `right_hand` arrays separately; 1,731 total retained epochs validated positive and finite. CPz was excluded because its saved signal produced zero PSD values and it is not used by the asymmetry features. |
| 3 | 3.2 | Asymmetry index computation (Figshare) | DONE | 2026-09-19 | Computed AI = (P_left-P_right)/(P_left+P_right) for F3/F4, C3/C4, P3/P4, and O1/O2 across all four bands. Saved 50 NPZ files with 16 AI features each for `all`, `left_hand`, and `right_hand`; all values validated in [-1, 1]. |
| 3 | 3.3 | Patient-level feature aggregation (Figshare) | DONE | 2026-09-19 | Created `features/figshare_patient_features.csv` with one row per subject and 57 condition-aware mean features: 19 each for `all`, `left_hand`, and `right_hand` (16 AI means + pdBSI + DAR + DTABR). Epoch counts are retained separately; all 50 rows passed finite/no-missing and count-consistency checks. |
| 4 | 4.1 | NIHSS label extraction & bucketing (Figshare) | DONE | 2026-09-19 | Extracted numeric NIHSS for all 50 subjects and applied fixed buckets: mild <=4, moderate 5-15, severe >15. Distribution is 33 mild, 17 moderate, 0 severe; no class is below five subjects. Labels saved to `data/processed/figshare/labels.csv`. |
| 4 | 4.2 | Build final Figshare feature table | DONE | 2026-09-19 | Merged labels with the condition-aware patient features into `features/figshare_features.csv`: 50 rows and 63 columns (57 features, 3 epoch-count columns, subject ID, NIHSS, severity). No missing or infinite values; severity classes are mild/moderate only. |
| 5 | 5.1 | Baseline single-feature model | NOT STARTED | | |
| 5 | 5.2 | Full-feature classical ML models (RF/SVM/KNN) | NOT STARTED | | |
| 5 | 5.3 | Cross-validation + metrics | NOT STARTED | | |
| 5 | 5.4 | Feature importance analysis | NOT STARTED | | |
| 6 | 6.1 | Acquire UCLH dataset | NOT STARTED | | |
| 6 | 6.2 | Verify UCLH data integrity | NOT STARTED | | |
| 7 | 7.1 | Extract EEG-only segments from UCLH raw files | NOT STARTED | | |
| 7 | 7.2 | Filter + epoch UCLH EEG | NOT STARTED | | |
| 8 | 8.1 | Band power + asymmetry index (UCLH) | NOT STARTED | | |
| 8 | 8.2 | Patient-level feature aggregation (UCLH) | NOT STARTED | | |
| 8 | 8.3 | NIHSS label bucketing (UCLH) | NOT STARTED | | |
| 9 | 9.1 | Channel alignment between datasets | NOT STARTED | | |
| 9 | 9.2 | External validation (train on Figshare, test on UCLH) | NOT STARTED | | |
| 10 | 10.1 | Benchmark comparison table (optional) | NOT STARTED | | |
| 11 | 11.1 | Results export for presentation | NOT STARTED | | |
| 11 | 11.2 | Final report/README | NOT STARTED | | |

**Status values:** `NOT STARTED` / `IN PROGRESS` / `DONE` / `BLOCKED`

---

## 2. Project summary (for context, do not re-derive this)

**Goal:** Classify stroke severity (mild / moderate / severe) from EEG, using interhemispheric spectral asymmetry as the core engineered feature, evaluated with classical ML (not deep learning — sample sizes are too small: 50 and 23 patients respectively).

**Primary dataset:** Figshare "EEG datasets of stroke patients" (Liu et al.), 50 patients, task-based motor imagery, includes NIHSS/MBI/mRS scores per patient.

**Secondary/validation dataset:** UCLH Stroke EIT/EEG Dataset, ~23 stroke patients + 10 healthy controls, resting-state, EEG embedded in raw multi-frequency EIT recordings, includes NIHSS scores.

**Core hypothesis being tested:** EEG-derived interhemispheric asymmetry can serve as an EEG-based proxy for clinically-assessed NIHSS severity.

**Explicitly out of scope for this project:** deep learning / CNNs on raw waveforms, real-time inference, more than 3 severity classes, any dataset not listed above.

---

## PHASE 0 — Environment & Repository Setup

### 0.1 Environment setup

**Objective:** A working Python environment with all required libraries installed.

**Tech stack:**
- Python 3.10+
- `numpy`, `scipy` — signal processing, numerics
- `mne` — EEG loading, filtering, epoching, PSD (Welch's method built in)
- `moabb` — provides a ready-made loader for the Figshare dataset (`moabb.datasets.Liu2024`)
- `pandas` — feature tables
- `scikit-learn` — RF, SVM, KNN, cross-validation, metrics
- `matplotlib`, `seaborn` — plots for the report/PPT
- `requests` or `zenodo_get` — UCLH dataset download from Zenodo

**Steps:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install numpy scipy mne moabb pandas scikit-learn matplotlib seaborn requests zenodo_get
```

**Outputs:** A `venv/` with the above packages installed. Run `pip freeze > requirements.txt` and save it at repo root.

**Validation:** `python -c "import mne, moabb, sklearn; print('ok')"` prints `ok` with no errors.

**Debug notes:**
- `mne` install failures are usually a missing C compiler dependency on Linux — install `build-essential` first if using apt.
- If `moabb` pulls an incompatible `mne` version, pin `mne>=1.5,<1.7` and reinstall.

---

### 0.2 Repository structure setup

**Objective:** A consistent folder layout so every later phase writes to a predictable path.

**Steps:** Create this structure at repo root:
```
project/
├── PROJECT_EXECUTION_GUIDE.md      (this file)
├── requirements.txt
├── data/
│   ├── raw/
│   │   ├── figshare/
│   │   └── uclh/
│   └── processed/
│       ├── figshare/
│       └── uclh/
├── features/
│   ├── figshare_features.csv
│   └── uclh_features.csv
├── src/
│   ├── load_figshare.py
│   ├── load_uclh.py
│   ├── preprocessing.py
│   ├── feature_extraction.py       (shared between both datasets — see Phase 3)
│   ├── labels.py
│   ├── train_models.py
│   └── validate_cross_dataset.py
├── notebooks/                       (optional, for exploratory sanity checks)
├── results/
│   ├── metrics/
│   ├── plots/
│   └── models/
└── tests/
    └── test_feature_extraction.py
```

**Outputs:** All folders above exist (empty is fine at this stage, except this guide file and requirements.txt).

**Validation:** `find project -type d` shows the full tree above.

---

## PHASE 1 — Acquire Figshare Dataset

### 1.1 Acquire Figshare dataset

**Objective:** Raw Figshare EEG data downloaded and accessible locally.

**Dataset details:**
- **Name:** "EEG datasets of stroke patients"
- **Source:** Figshare, article ID `21679035`
- **URL:** `https://figshare.com/articles/dataset/EEG_datasets_of_stroke_patients/21679035`
- **Size:** ~2.18 GB total
- **Contents:** 50 acute ischemic stroke patients, 29-channel EEG (10-20 montage), 500 Hz sampling rate, motor imagery paradigm (2s cue + 4s imagery, left-hand/right-hand trials), plus a patient characteristics file containing per-patient **NIHSS**, **Modified Barthel Index (MBI)**, and **modified Rankin Scale (mRS)** scores, and documented hemiplegia side (left/right).
- **Known data quality note:** the dataset descriptor documents that some subjects have flagged motion artifacts — check the descriptor/readme for the exact subject IDs when you get there (do not assume all 50 are clean).

**Steps — preferred method (MOABB loader, handles download + caching automatically):**
```python
from moabb.datasets import Liu2024
dataset = Liu2024()
dataset.download(path="data/raw/figshare/")
```

**Steps — fallback method (manual download, use only if MOABB loader fails or is unavailable):**
1. Go to the Figshare URL above.
2. Download all files/versions listed for the article into `data/raw/figshare/`.
3. Unzip everything so raw EEG files and the patient-characteristics file are both present under `data/raw/figshare/`.

**Outputs:** `data/raw/figshare/` populated with per-subject EEG files and the patient characteristics file (NIHSS/MBI/mRS + hemiplegia side).

**Validation:**
- `du -sh data/raw/figshare/` reports a size in the ~2 GB range (if it's under a few hundred MB, the download is incomplete).
- Confirm exactly 50 subjects' worth of EEG files are present (however the dataset names them — check the descriptor for the exact naming convention, e.g. `sub-01` through `sub-50`).
- Open the patient characteristics file and confirm it has a row per subject with NIHSS, MBI, mRS, and hemiplegia-side columns.

**Debug notes:**
- If the MOABB loader silently fails with no error, check your internet connection allowlist — some sandboxed environments block Figshare's CDN. Fall back to manual download.
- If subject count doesn't match 50, re-check whether some files are split across multiple archive parts that need combining before unzip.

---

### 1.2 Verify Figshare data integrity

**Objective:** Confirm every downloaded EEG file actually opens and has the expected structure, before building anything on top of it.

**Steps:**
```python
import mne
import glob

files = glob.glob("data/raw/figshare/**/*.set", recursive=True)  # or .edf/.mat — confirm actual extension from what you downloaded
assert len(files) == 50, f"Expected 50 subject files, found {len(files)}"

for f in files:
    raw = mne.io.read_raw(f, preload=False, verbose=False)
    assert raw.info['sfreq'] == 500, f"{f} has unexpected sampling rate {raw.info['sfreq']}"
    assert len(raw.ch_names) == 29, f"{f} has unexpected channel count {len(raw.ch_names)}"
```

**Outputs:** No file assertions fail. Log the result to `results/metrics/figshare_integrity_check.txt`.

**Validation:** The script above runs to completion with no `AssertionError`.

**Debug notes:**
- If file extension/format differs from what's assumed here (EEGLAB `.set`, raw `.edf`, or MATLAB `.mat`), inspect one file manually first (`file data/raw/figshare/<name>`) and adjust the loader call accordingly (`mne.io.read_raw_eeglab`, `mne.io.read_raw_edf`, or a custom `scipy.io.loadmat` reader for `.mat`).
- If sampling rate or channel count don't match across subjects, do not force-fix silently — flag it in the ledger Notes, since it affects every downstream phase (feature vectors must be same length across all patients).

---

## PHASE 2 — Figshare Preprocessing

### 2.1 Load & inspect Figshare raw EEG

**Objective:** Confirm you can programmatically load each subject's EEG plus its trial/event structure (cue vs imagery windows, left-hand vs right-hand trials).

**Steps:**
```python
raw = mne.io.read_raw(<subject_file>, preload=True)
events, event_id = mne.events_from_annotations(raw)
print(event_id)  # confirm labels exist for cue-start, imagery-start, left-hand, right-hand
```

**Outputs:** A confirmed mapping of event codes to trial types, documented in `src/load_figshare.py` as a constant dict (e.g. `EVENT_ID = {...}`).

**Validation:** `event_id` printed output is non-empty and each subject has a plausible number of trials (motor imagery datasets of this kind typically run dozens of trials per subject — flag any subject with a suspiciously low trial count for exclusion review in 2.3).

**Debug notes:** If `events_from_annotations` returns nothing, the events may be stored in a separate stim channel or metadata file instead of annotations — check the dataset descriptor for exact event storage format.

---

### 2.2 Filter + epoch Figshare EEG

**Objective:** Produce clean, epoched EEG restricted to the motor-imagery window (not the instruction cue).

**Steps:**
```python
raw.filter(l_freq=1., h_freq=40., fir_design='firwin')
raw.notch_filter(freqs=50)  # or 60 depending on recording site; confirm from dataset descriptor

epochs = mne.Epochs(
    raw, events, event_id=<imagery_event_codes_only>,
    tmin=0.0, tmax=4.0,   # motor imagery window only, per dataset design
    baseline=None, preload=True
)
```

**Outputs:** One `epochs` object per subject, saved to `data/processed/figshare/<subject_id>-epo.fif`.

**Validation:** For each subject, `len(epochs)` > 0 and `epochs.get_data().shape` has the expected channel count (29) and a consistent number of time samples across all subjects (500 Hz × 4s = 2000 samples).

**Debug notes:**
- If filtering throws a "not enough data" error, the raw file may be shorter than expected — check for truncated downloads (re-run 1.2).
- Confirm the notch filter frequency matches the recording site's mains frequency (China-based recordings are typically 50 Hz — verify against the dataset descriptor rather than assuming).

---

### 2.3 Artifact/subject exclusion

**Objective:** Drop subjects or trials flagged as artifact-contaminated per the dataset's own documentation, plus a basic amplitude-based sanity check.

**Steps:**
1. Cross-reference the subject IDs flagged in the dataset descriptor/readme and exclude them (or exclude only their contaminated trials, if the descriptor specifies trial-level detail).
2. Additionally, apply a simple amplitude threshold per epoch: drop any epoch where any channel exceeds ±100 µV peak-to-peak (basic eye-blink/movement rejection).

```python
epochs.drop_bad(reject=dict(eeg=100e-6))
```

**Outputs:** `data/processed/figshare/exclusion_log.csv` — one row per subject, listing trials dropped, and whether the subject was fully excluded.

**Validation:** Every remaining subject has at least ~10 clean epochs left per condition (left-hand / right-hand). If a subject drops below this, flag them in the exclusion log rather than silently keeping too little data — but do not auto-exclude below a hard threshold without noting it in the ledger, since it changes your effective sample size.

**Debug notes:** If the ±100 µV threshold drops an unreasonably large fraction of epochs (e.g. >50% for many subjects), the threshold may be too strict for this dataset's recording setup — loosen to ±150 µV and re-check, documenting the change.

---

## PHASE 3 — Feature Engineering (Figshare)

> **Important:** Write this feature extraction code as a standalone, dataset-agnostic module (`src/feature_extraction.py`) that takes an `epochs` object and a list of electrode pairs as input. Phase 8 (UCLH) reuses this exact module — do not write Figshare-specific and UCLH-specific versions separately.

### 3.1 Band power extraction (Figshare)

**Objective:** Compute per-channel, per-band power for every epoch.

**Band definitions (use exactly these, do not vary across phases):**
- Delta: 1–4 Hz
- Theta: 4–8 Hz
- Alpha: 8–13 Hz
- Beta: 13–30 Hz

**Steps:**
```python
from mne.time_frequency import psd_array_welch
import numpy as np

def band_power(epochs, bands, fmin=1, fmax=30):
    data = epochs.get_data()  # shape: (n_epochs, n_channels, n_times)
    psds, freqs = psd_array_welch(data, sfreq=epochs.info['sfreq'], fmin=fmin, fmax=fmax, n_fft=256)
    band_powers = {}
    for band_name, (lo, hi) in bands.items():
        idx = np.logical_and(freqs >= lo, freqs <= hi)
        band_powers[band_name] = psds[:, :, idx].mean(axis=2)  # shape: (n_epochs, n_channels)
    return band_powers

BANDS = {"delta": (1,4), "theta": (4,8), "alpha": (8,13), "beta": (13,30)}
```

**Outputs:** A dict of arrays, one per band, shape `(n_epochs, n_channels)`, per subject. Cache to `data/processed/figshare/<subject_id>_bandpower.npz`.

**Validation:** All values in `band_powers` are strictly positive (power cannot be negative or zero for real signal) and contain no `NaN`/`inf`. Assert this explicitly:
```python
for band, arr in band_powers.items():
    assert np.all(arr > 0) and not np.any(np.isnan(arr)), f"Invalid values in {band}"
```

**Debug notes:** `NaN` values usually mean an epoch contains a flat/dead channel — cross-check against the exclusion log from 2.3; a channel that should've been dropped may have slipped through.

---

### 3.2 Asymmetry index computation (Figshare)

**Objective:** Convert per-channel band power into left-right asymmetry indices.

**Electrode pairs to use (fixed list — do not silently change this list once analysis starts; if you must change it, update this file and the ledger Notes):**
```python
CHANNEL_PAIRS = [
    ("F3", "F4"),
    ("C3", "C4"),
    ("P3", "P4"),
    ("O1", "O2"),
]
```

**Formula (apply per pair, per band, per epoch):**
```
AI = (P_left - P_right) / (P_left + P_right)
```

**Steps:**
```python
def asymmetry_index(band_powers, ch_names, pairs):
    results = {}
    for band, power_arr in band_powers.items():
        for left, right in pairs:
            i_l, i_r = ch_names.index(left), ch_names.index(right)
            p_l, p_r = power_arr[:, i_l], power_arr[:, i_r]
            ai = (p_l - p_r) / (p_l + p_r)
            results[f"AI_{band}_{left}{right}"] = ai   # shape: (n_epochs,)
    return results
```

**Outputs:** Dict of arrays keyed like `AI_delta_C3C4`, one value per epoch, per subject.

**Validation:** Every AI value is in the range `[-1, 1]` (mathematically guaranteed if band power inputs are positive — this doubles as a correctness check on Step 3.1 too):
```python
for key, arr in results.items():
    assert np.all(arr >= -1) and np.all(arr <= 1), f"{key} out of expected range"
```

**Debug notes:** If a channel name in `CHANNEL_PAIRS` isn't found in `ch_names`, the montage naming may differ slightly (e.g. lowercase, or a prefix like `EEG F3`) — print `epochs.ch_names` and adjust the pair list to match exactly what's in the data.

---

### 3.3 Patient-level feature aggregation (Figshare)

**Objective:** Collapse epoch-level asymmetry indices into one feature vector per patient.

**Steps:**
```python
import pandas as pd

def aggregate_patient_features(ai_dict):
    row = {}
    for key, arr in ai_dict.items():
        row[key] = np.mean(arr)          # mean across epochs
        row[f"{key}_std"] = np.std(arr)  # optional: keep only if feature count stays manageable
    # global summary metrics
    all_ai = np.stack(list(ai_dict.values()))
    row["pdBSI"] = np.mean(np.abs(all_ai))
    return row
```

Also compute **DAR** (delta/alpha ratio) and **DTABR** ((delta+theta)/(alpha+beta)) as global scalars per epoch, then averaged per patient, using total power summed across all channels (not per-pair).

**Outputs:** One row (Python dict / pandas Series) per patient. Do not include the `_std` columns in your first modeling pass — start with means only (~19 features), to keep feature count reasonable relative to n=50. `_std` columns are a documented stretch option for Phase 5 if time allows re-running with expanded features.

**Validation:** Row has no `NaN`, and feature count matches what's documented here (19 for means-only: 4 pairs × 4 bands = 16, + pdBSI + DAR + DTABR = 19).

**Debug notes:** If you added or removed a channel pair in 3.2, this count changes — recompute and update this section's expected count rather than leaving it stale.

---

## PHASE 4 — Labels (Figshare)

### 4.1 NIHSS label extraction & bucketing (Figshare)

**Objective:** Attach a severity class to every patient from their real NIHSS score.

**Bucketing scheme (fixed, use identically for both datasets):**
```python
def bucket_nihss(score):
    if score <= 4:
        return "mild"
    elif score <= 15:
        return "moderate"
    else:
        return "severe"
```

**Steps:** Load the patient characteristics file from `data/raw/figshare/`, extract the NIHSS column per subject ID, apply `bucket_nihss`.

**Outputs:** `data/processed/figshare/labels.csv` with columns `subject_id, nihss_raw, severity_class`.

**Validation:** Every one of the 50 (minus any excluded in 2.3) subjects has a non-null `severity_class`. Print the class distribution — if one class has fewer than ~5 patients, flag this in the ledger Notes, since it affects which cross-validation strategy is viable in Phase 5 (very small classes may need leave-one-out rather than k-fold).

**Debug notes:** If NIHSS values are missing for some subjects in the characteristics file, do not silently drop them without logging — record exactly which subject IDs and why in the exclusion log.

---

### 4.2 Build final Figshare feature table

**Objective:** Merge Phase 3 features with Phase 4 labels into one modeling-ready table.

**Steps:**
```python
features_df = pd.DataFrame([aggregate_patient_features(...) for each subject])
labels_df = pd.read_csv("data/processed/figshare/labels.csv")
final_df = features_df.merge(labels_df, on="subject_id")
final_df.to_csv("features/figshare_features.csv", index=False)
```

**Outputs:** `features/figshare_features.csv` — this is the single source of truth for all Figshare modeling in Phase 5.

**Validation:** Row count matches the number of non-excluded subjects. Column count matches 19 features + `subject_id` + `nihss_raw` + `severity_class`. No missing values anywhere in the table.

---

## PHASE 5 — Modeling & Evaluation (Figshare)

### 5.1 Baseline single-feature model

**Objective:** Establish a simple, honest floor before the full feature set — useful both as a sanity check and as a "before/after" slide.

**Steps:**
```python
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score

X_baseline = final_df[["pdBSI"]]
y = final_df["severity_class"]
model = LogisticRegression(max_iter=1000)
scores = cross_val_score(model, X_baseline, y, cv=5, scoring="f1_macro")
```

**Outputs:** `results/metrics/baseline_single_feature.json` with the cross-validated F1-macro score.

**Validation:** Score is computed without error. Do not expect this to be strong — that's expected and worth stating explicitly in the report.

---

### 5.2 Full-feature classical ML models (RF/SVM/KNN)

**Objective:** Train and compare three classical models on the full feature set.

**Steps:**
```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

X = final_df.drop(columns=["subject_id", "nihss_raw", "severity_class"])
y = final_df["severity_class"]

models = {
    "random_forest": RandomForestClassifier(n_estimators=200, random_state=42),
    "svm": Pipeline([("scale", StandardScaler()), ("svc", SVC(kernel="rbf"))]),
    "knn": Pipeline([("scale", StandardScaler()), ("knn", KNeighborsClassifier(n_neighbors=5))]),
}
```

**Important:** SVM and KNN MUST be wrapped with `StandardScaler` as shown — both are distance/margin-based and will produce misleading results on unscaled features. Random Forest does not need scaling; do not scale its input (it's harmless but unnecessary and can obscure feature-importance interpretation later).

**Outputs:** Trained model objects (not necessarily persisted to disk unless needed for a demo — metrics are the real output here, saved in 5.3).

**Debug notes:** If SVM/KNN perform suspiciously worse than expected even after scaling, double check `StandardScaler` is fit only on training folds, not the full dataset, to avoid data leakage (use it inside the `Pipeline`/`cross_val_score` call, never fit it once on all data beforehand).

---

### 5.3 Cross-validation + metrics

**Objective:** Get an honest, leakage-free performance estimate given the small sample size.

**Steps:**
```python
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
# If any severity class has fewer than 5 members (per 4.1 validation note), switch to:
# from sklearn.model_selection import LeaveOneOut
# cv = LeaveOneOut()

for name, model in models.items():
    scores = cross_val_score(model, X, y, cv=cv, scoring="f1_macro")
    print(name, scores.mean(), scores.std())
```

Also generate a confusion matrix using `cross_val_predict` for the best-performing model, and save it as a plot.

**Outputs:**
- `results/metrics/model_comparison.csv` — one row per model, with mean/std F1-macro and accuracy.
- `results/plots/confusion_matrix_<best_model>.png`

**Validation:** All three models produce a score. Compare against the 5.1 baseline — full-feature models should outperform the single-feature baseline; if they don't, something in feature extraction (Phase 3) likely needs review before proceeding.

**Debug notes — critical data leakage check:** Confirm the cross-validation split is done **by patient**, not by epoch. Since Phase 3.3 already collapsed each patient to one row before this phase, this is naturally satisfied here — but explicitly verify `final_df` has exactly one row per patient before running any CV, since accidentally having multiple rows per patient (e.g. from a bug in 3.3) would leak patient identity across folds and silently inflate scores.

---

### 5.4 Feature importance analysis

**Objective:** Identify which asymmetry features actually drove the predictions — this is a key result for the report/PPT.

**Steps:**
```python
rf = models["random_forest"]
rf.fit(X, y)
importances = pd.Series(rf.feature_importances_, index=X.columns).sort_values(ascending=False)
```

**Outputs:** `results/plots/feature_importance.png` (bar chart, top 10 features), `results/metrics/feature_importance.csv`.

**Validation:** Importances sum to ~1.0 (RF property) and the top features are interpretable band/pair combinations, not an unexplainable ranking.

---

## PHASE 6 — Acquire UCLH Dataset

### 6.1 Acquire UCLH dataset

**Objective:** Raw UCLH stroke EIT/EEG data downloaded.

**Dataset details:**
- **Name:** UCLH Stroke EIT/EEG Dataset
- **Source repo (code + pointers to data):** `https://github.com/EIT-team/Stroke_EIT_Dataset`
- **Data hosted on:** Zenodo (multiple linked records — Patient Data Part 1, Patient Data Part 2, radiology data, etc.)
- **Cohort:** ~23 stroke patients + 10 healthy controls (33 total), inclusion criteria required lesion size >1.5cm OR NIHSS ≥5
- **Recording:** 32-channel 10-20 EEG montage via BioSemi, embedded in multi-frequency EIT recordings (17 frequencies, 31 current injection patterns); EEG-only intervals exist in ~1-minute windows before/after EIT current injection bursts
- **Total size:** ~150 GB across all files — **only download Patient Data Part 1 + Part 2 (~70GB combined)**; skip the radiology/imaging bundle (~11GB) unless a later phase explicitly requires CT/MRI correlation

**Steps:**
1. Clone the GitHub repo for the processing code: `git clone https://github.com/EIT-team/Stroke_EIT_Dataset data/raw/uclh_code/`
2. Follow the repo's README/links to the Zenodo records for Patient Data Part 1 and Part 2.
3. Download only those two parts into `data/raw/uclh/`.
4. Confirm NIHSS scores are present in the accompanying patient metadata (per the dataset descriptor) — if not bundled with Part 1/2, check whether a separate clinical metadata file exists on the same Zenodo record set.

**Outputs:** `data/raw/uclh/` populated with raw patient recordings, `data/raw/uclh_code/` with the official extraction scripts.

**Validation:** `du -sh data/raw/uclh/` reports a size in the ~60-80 GB range. Patient count in the metadata matches ~23 stroke + 10 control.

**Debug notes:**
- This download is large — budget real wall-clock time (likely several hours depending on connection) and do not assume a timeout mid-download means corruption; resume and re-verify checksums if the source provides them.
- If storage is constrained, download and fully process one patient at a time (Phase 7) rather than holding all raw files simultaneously, deleting each patient's raw file after its EEG segment is successfully extracted and validated.

---

### 6.2 Verify UCLH data integrity

**Objective:** Confirm the raw files are complete and the official extraction code loads them.

**Steps:** Use the repo's own loading function (do not write a custom loader from scratch — the raw format is nonstandard and the official code already handles it):
```python
# from within data/raw/uclh_code/, following its own documented API
# exact function names come from the repo's Load_data module — inspect it directly
```

**Outputs:** Confirmation log per patient: file loads without error, expected number of EIT frames/current injections present.

**Validation:** No load errors across all downloaded patients.

**Debug notes:** If the repo's code depends on an old MATLAB/Python version, check its own requirements file first before assuming your Phase 0 environment is sufficient — UCLH's processing code may need additional or different dependencies than what Phase 0 installed. Document any extra dependencies needed in this section.

---

## PHASE 7 — UCLH Extraction & Preprocessing

### 7.1 Extract EEG-only segments from UCLH raw files

**Objective:** Pull out the EEG-only voltage windows (no concurrent EIT current injection) from each patient's raw recording.

**Steps:** Use the repo's `Extract_EEG` function (from the `EIT-team/Load_data` module) per patient. Do not attempt to re-derive this extraction logic manually — the raw format's structure (frame timing relative to injection bursts) is nonobvious and already solved in the official code.

**Outputs:** `data/processed/uclh/<patient_id>_eeg_raw.npy` (or whatever format the extraction function natively outputs) — one file per patient, containing just the EEG-only voltage segments and their timestamps.

**Validation:** Each patient's extracted segment has a non-zero duration and 32 channels.

**Debug notes:** If a patient's extracted segment is suspiciously short (a few seconds), check whether the EIT recording for that patient had unusually frequent injection bursts, leaving little EEG-only window — this is a legitimate per-patient limitation, not necessarily a bug; document it rather than forcing a fix.

---

### 7.2 Filter + epoch UCLH EEG

**Objective:** Apply the same style of preprocessing as Figshare (Phase 2.2), adapted for resting-state (no task events).

**Steps:**
```python
raw.filter(l_freq=2., h_freq=200., fir_design='firwin')  # per UCLH's own documented pipeline range
raw.filter(l_freq=1., h_freq=40.)  # re-tighten to the same clinical band range used for Figshare, for feature comparability
raw.notch_filter(freqs=50)  # UK recording site — 50Hz mains

# no task events — fixed-length epoching instead
epochs = mne.make_fixed_length_epochs(raw, duration=4.0, overlap=0.0)  # match Figshare's 4s window
```

**Outputs:** `data/processed/uclh/<patient_id>-epo.fif`

**Validation:** Consistent epoch length (in samples) — resample if UCLH's native sampling rate differs from Figshare's 500 Hz, so that band power computations (Phase 3, reused module) behave identically across datasets.

**Debug notes:** Apply the same amplitude-threshold artifact rejection as Figshare (2.3) — resting-state clinical recordings are often noisier than controlled lab recordings, so expect a higher rejected-epoch fraction and document it rather than being alarmed by it.

---

## PHASE 8 — Feature Engineering & Labels (UCLH)

### 8.1 Band power + asymmetry index (UCLH)

**Objective:** Reuse the exact `src/feature_extraction.py` module from Phase 3 — do not rewrite it.

**Steps:** Call the same `band_power()` and `asymmetry_index()` functions from Phase 3.1/3.2, using the **intersection** of `CHANNEL_PAIRS` actually present in UCLH's 32-channel montage. If all four pairs (F3/F4, C3/C4, P3/P4, O1/O2) exist in UCLH's montage (likely, since both are 10-20 based), the pair list is identical — confirm this explicitly rather than assuming.

**Outputs:** Same structure as Figshare's 3.1/3.2 outputs, cached per patient.

**Validation:** Same range checks as 3.1 (`>0`, no `NaN`) and 3.2 (`[-1,1]`).

---

### 8.2 Patient-level feature aggregation (UCLH)

**Objective:** Same as Figshare 3.3 — reuse `aggregate_patient_features()`.

**Outputs:** One row per UCLH patient, same 19-column structure as Figshare (column names must match exactly for Phase 9 to work).

**Validation:** Column names in the UCLH feature table are identical to `features/figshare_features.csv`'s feature columns (excluding subject_id/labels). If they don't match exactly, Phase 9's model can't be applied across datasets — fix here before proceeding.

---

### 8.3 NIHSS label bucketing (UCLH)

**Objective:** Reuse `bucket_nihss()` from Phase 4.1 on UCLH's NIHSS scores.

**Outputs:** `features/uclh_features.csv` — same schema as `figshare_features.csv`.

**Validation:** Every stroke patient has a `severity_class`. Decide explicitly whether the 10 healthy controls are included (as a 4th "none" class) or excluded — document the decision here, since it changes what Phase 9 is actually testing.

---

## PHASE 9 — Cross-Dataset Validation

### 9.1 Channel alignment between datasets

**Objective:** Final confirmation that Figshare and UCLH feature tables are directly comparable before combining them in any way.

**Steps:** Diff the column lists of `features/figshare_features.csv` and `features/uclh_features.csv` (excluding identifier/label columns).

**Validation:** Column sets are identical. If not, resolve in Phase 8.1/8.2 before continuing — do not patch around a mismatch here with renaming hacks.

---

### 9.2 External validation (train on Figshare, test on UCLH)

**Objective:** Test whether a model trained only on Figshare generalizes to the independent UCLH cohort — the core "bigger dataset" validation goal of this project.

**Steps:**
```python
X_train, y_train = figshare_df[feature_cols], figshare_df["severity_class"]
X_test, y_test = uclh_df[feature_cols], uclh_df["severity_class"]

best_model = models["random_forest"]  # or whichever won in 5.3
best_model.fit(X_train, y_train)
y_pred = best_model.predict(X_test)

from sklearn.metrics import classification_report
print(classification_report(y_test, y_pred))
```

**Outputs:** `results/metrics/external_validation_report.json`, confusion matrix plot.

**Validation:** Report is generated without error. A drop in performance versus the Figshare-internal cross-validation score (Phase 5.3) is expected and should be reported honestly, not treated as a failure — frame it in the writeup as the realistic generalization gap between a curated task-based cohort and a real clinical resting-state cohort.

**Debug notes:** If performance on UCLH is at or below chance level for all classes, first check for a units/scaling mismatch introduced somewhere in Phase 7-8 (e.g. sampling rate not actually resampled to match Figshare) before concluding the approach doesn't generalize.

---

## PHASE 10 — Benchmark Comparison (Optional)

### 10.1 Benchmark comparison table (optional)

**Objective:** Contextualize your results against trivial baselines, to demonstrate the model is learning something real.

**Steps:** Compute and report:
- **Majority-class baseline:** always predict the most common severity class in the training set; report its accuracy/F1 as a floor.
- **Random baseline:** predict severity uniformly at random across classes; report expected accuracy/F1.

```python
from sklearn.dummy import DummyClassifier
dummy_majority = DummyClassifier(strategy="most_frequent")
dummy_random = DummyClassifier(strategy="uniform")
```

**Outputs:** `results/metrics/benchmark_baselines.csv`, appended to the model comparison table from 5.3 for a unified results table.

**Validation:** Your best model (Phase 5/9) should outperform both dummy baselines by a meaningful margin — if it doesn't, this is a critical signal to revisit feature engineering (Phase 3) before finalizing results.

---

## PHASE 11 — Reporting & Artifacts

### 11.1 Results export for presentation

**Objective:** Produce all figures/tables needed for the PPT in one pass.

**Required outputs, all saved to `results/plots/` and `results/metrics/`:**
1. Pipeline diagram data (reuse the phase structure of this document as the "methods" slide outline)
2. Model comparison table (RF vs SVM vs KNN vs baselines) — from 5.3 and 10.1
3. Confusion matrix for the best model — from 5.3
4. Feature importance bar chart — from 5.4
5. External validation report (Figshare→UCLH) — from 9.2
6. A scatter/box plot of pdBSI vs severity class, for both datasets — a simple, intuitive "does the core idea even show a trend" visual, good for an early results slide

**Validation:** All six artifacts exist as files and open correctly.

---

### 11.2 Final report/README

**Objective:** A short written summary tying everything together, for anyone (human or agent) who wants the outcome without re-running the pipeline.

**Steps:** Write `RESULTS_SUMMARY.md` at repo root covering: final dataset sizes after exclusions, best model + its cross-validated metrics, external validation results, top predictive features, and known limitations (small n, resting-state vs task-based paradigm mismatch, NIHSS bucket imbalance if any).

**Outputs:** `RESULTS_SUMMARY.md`

**Validation:** Every numeric claim in this file traces back to a specific file in `results/metrics/` — do not state a number here that isn't backed by a saved artifact.

---

## Appendix A — Common Pitfalls Checklist (check before declaring any phase DONE)

- [ ] Did I split cross-validation by **patient**, never by epoch/trial?
- [ ] Did I fit `StandardScaler` only inside the CV pipeline, never on the full dataset beforehand?
- [ ] Do Figshare and UCLH feature tables have **identical column names** before Phase 9?
- [ ] Are all asymmetry index values within `[-1, 1]`?
- [ ] Are all band power values strictly positive with no `NaN`?
- [ ] Did I document every subject/patient exclusion with a reason, not just silently drop them?
- [ ] Did I use the exact same band definitions and channel pairs across both datasets?
- [ ] Did I update the PROGRESS LEDGER before ending the session?

## Appendix B — Key Fixed Constants (do not redefine differently elsewhere in the codebase)

```python
BANDS = {"delta": (1,4), "theta": (4,8), "alpha": (8,13), "beta": (13,30)}
CHANNEL_PAIRS = [("F3","F4"), ("C3","C4"), ("P3","P4"), ("O1","O2")]
SEVERITY_BUCKETS = {"mild": (0,4), "moderate": (5,15), "severe": (16, 42)}
EPOCH_LENGTH_SECONDS = 4.0
TARGET_SAMPLING_RATE_HZ = 500
NOTCH_FREQ_HZ = 50
BANDPASS_RANGE_HZ = (1, 40)
ARTIFACT_REJECT_THRESHOLD_UV = 100e-6
```
