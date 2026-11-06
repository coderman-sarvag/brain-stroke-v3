# V3 Step 0 Report: Environment and Data

**Date:** 2026-11-06. **Branch:** `fix/flowchart-pipeline`. **Spec:** V3 audit handoff, Step 0.
**Status:** PASSED.

## What was done

| Item | Detail |
|---|---|
| Environment | `.venv` (Python 3.12.10, Windows 11), `requirements.txt` pins + `python-picard` 0.8.2 (ICA for Step 2) + `pytest` 9.2.0. Versions in `configs/v3/environment.json` (`src/record_environment_v3.py`). Key: mne 1.13.2, mne-connectivity 0.9.0, moabb 1.7.2, numpy 2.5.3, scipy 1.18.1, pandas 3.0.6, scikit-learn 1.9.1. `mne-icalabel` not installed (optional). |
| Download | `src/download_figshare_v3.py` + `configs/v3/figshare_download.json`. Figshare API article 21679035, DOI `10.6084/m9.figshare.21679035.v5`. 11 files fetched, each verified against the API `computed_md5` before being moved into place. `sourcedata.zip`, `stimuli.zip`, `code.zip` deliberately not downloaded. `edffile.zip` (462,843,633 B, md5 `aa4f96a0…be40`) extracted with a path-traversal guard into `data/raw/figshare/extracted/edffile/sub-*/eeg/*.edf`. Manifest with md5 + sha256: `results/v3/step0/download_manifest.json`. |
| Acceptance check | `src/check_data_v3.py` + `configs/v3/data_check.json` → `results/v3/step0/data_check.json` / `.csv` (per-subject EDF sha256, config hash, git commit, date). Reads no clinical fields. |
| Tests | `tests/test_data_v3.py`: 6 passed (ms→sample event conversion, unknown trial type rejected, constant-signal check, zip traversal rejected, normal extraction, md5 mismatch rejected and no partial file left). |

## Acceptance results

| Criterion | Result |
|---|---|
| 50 EDFs open | 50/50 |
| 500 Hz | 50/50 |
| 33 channels | 50/50; identical order in every file: 30 EEG (`FP1 … O2`, CPz included), `HEOL`, `HEOR`, one blank-named channel |
| 40 imagery events, 20 left / 20 right | 50/50 (shared `task-motor-imagery_events.tsv`, 120 rows, `value == 2`) |
| Events inside the recording | 50/50; every recording is exactly 320.0 s; last imagery window ends at 318.0 s |
| CPz constant | 50/50, value exactly 0.0 (flat reference, as expected) |
| Other flat channels | none in any subject |

## Observations recorded for later steps (no action taken)

- **Blank-named channel is not empty.** In sub-01 it takes 4 distinct values (range 3 units). It is probably the marker/trigger channel. Step 1 will test whether its transitions line up with the shared imagery onsets (event-timing check).
- **HEOL/HEOR.** sub-01 peak-to-peak 277 / 257 µV, correlation −0.44 (anti-correlated, as expected for a horizontal pair). No vertical EOG channel is visible by name. The paper's VEOG claim must be checked in Step 2.
- **Rest data.** The first event onset is at 1 ms and the task block fills 0–318 s of a 320 s file. There is no room for a 1 min eyes-open/closed segment in these EDFs. Step 1 will report this formally.
- **Version drift.** The v2 ledger records that v2 was actually run on NumPy 2.2.5 / pandas 2.2.3 / matplotlib 3.10.1, not on the `requirements.txt` pins used here. The Step 8 synthetic acceptance gates must therefore be re-run in this environment (already in the handoff plan).
- **First install attempt failed** with "no matching distribution for matplotlib==3.11.2". A cp312 wheel exists, and the retry succeeded with no changes. The cause was transient.

## Not committed

`.venv/`, `data/raw/` (EDFs, zip) and `results/v3/` are git-ignored. The outputs live locally only, so the key numbers are copied above. The handoff file and the flowchart image are not in the repo.
