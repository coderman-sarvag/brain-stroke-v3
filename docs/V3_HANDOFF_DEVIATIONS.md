# V3 Handoff Deviation Log

Every place where v3 differs from the V3 audit handoff (2026-11-06), or fills a choice the handoff left open. Each entry gives the reason and who decided. No entry was chosen from outcome data: no NIHSS, severity, MBI or mRS value has been read by any v3 step.

| ID | Step | Handoff said | v3 does | Reason | Decided by |
|---|---|---|---|---|---|
| D1 | 1 | Check that the shared events file fits each recording | Epochs come from per-subject **marker-channel onsets**, matched one-to-one to sidecar trials (±2000 samples); left/right comes from the matched sidecar trial | The marker channel shows the sidecar is misaligned for 15/50 subjects (2 s early trials, drift up to 1.66 s in sub-06, spurious end codes) | Evidence (Step 1); user approved, Step 1 review |
| D2 | 1 | Sidecar timing tolerance not specified | 50 ms agreement tolerance (pre-set 20 ms also reported) | Typical lag is a constant 4–22 ms recording latency | Engineering, disclosed in Step 1 report |
| D3 | 1 | Parse `stroke_location` into side | Split on commas only (not "and") | The first rule wrongly made sub-22 unclear; corrected before any outcome was read | Engineering, disclosed |
| D4 | 1 | Default proposal: exclude both sub-04/05 | Both excluded (N = 48) | Identical EEG, label unknowable | User decision |
| D5 | 2 | Bipolar HEOG (HEOL − HEOR) for `find_bads_eog` | Each EOG channel used **separately**; no bipolar channel | The second channel is HEOR in the EDF but VEOR (vertical) in the BIDS sidecar: unverified | User (Step 0 review) |
| D6 | 2 | Equalize left/right counts (`equalize_event_counts`) | **Class-balanced averaging**: keep all clean epochs, save each epoch's class; later features are computed per class and the two class means averaged | Equalization discards clean data; balancing at the feature level gives equal class weight without losing epochs | Reviewer (Step 2 review) |
| D7 | 2 | Peak-to-peak screen on all scalp channels (or autoreject) | Screen rule **pending**: a label-free diagnostic compares (i) all scalp, (ii) the 22 analysed channels, (iii) (ii) after marking channels that exceed in ≥ 30% of epochs; final mode refuses to run until one is chosen | The all-scalp screen removed 60–75% of epochs in a 2-subject trial and emptied a class in one subject | Reviewer (Step 2 review); final choice pending the user |
| D8 | 2 | Not specified | Subjects with **> 9 bad channels** are flagged and ICA is not run (excluded in final mode) | Avoids running ICA with fewer than the configured 20 components | Reviewer (Step 2 review) |
| D9 | 2 | Minimum clean epochs, e.g. ≥ 20 total | Proposed **≥ 10 per class** (consistent with D6); pending the diagnostic distribution | The class-balanced design needs a per-class minimum | Pending the user |
| D10 | 2 | Bad-channel detection, e.g. RANSAC-style or pyprep | pyprep `NoisyChannels` with PREP published defaults | Within the handoff's options; recorded for completeness | Engineering |
| D11 | 2 | Notch only if mains residue remains | No notch; 48–52 Hz residue measured before/after filtering | 50 Hz is beyond the 40 Hz stop band | Within the handoff's options |
| D12 | all | Windows, run from repo root | All v3 scripts also take `--data-root/--out-root/--prev-root`; `kaggle/run_v3.py` runs steps resumably on Kaggle | Full runs move to Kaggle (reviewer) | Reviewer (Step 2 review) |
