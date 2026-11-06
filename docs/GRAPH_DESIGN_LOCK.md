# Graph v2 Design Lock

**Status:** PROVISIONAL LOCK after A3 label-blind audit

## Input audit

- Files audited: 50 clean FIF files from `data/processed/figshare/clean/`.
- Sampling rate: [500.0] Hz.
- Epoch window: [(0.0, 3.998, 2000)] (time start, time end, samples).
- Clean epoch counts: min=4, median=39.0, max=40.
- Artifact screen: peak-to-peak threshold 150.0 uV.
- The same 150 uV screen is applied to the graph sampling pool by `screen_epochs` before feature computation.
- Design decisions used only channel quality and epoch counts; no clinical labels were read.

## Channel sets

- G8f: F3, C3, P3, O1, F4, C4, P4, O2.
- G24f retained pairs: F3/F4, F7/F8, FC3/FC4, FT7/FT8, C3/C4, T3/T4, CP3/CP4, TP7/TP8, P3/P4, T5/T6, O1/O2.
- Dropped pairs: FP1/FP2.
- The full channel rejection rates and counts are recorded in `docs/graph_design_audit_v2.json`.

## Fixed epoch rule

- G8f audit value: N_fixed=15.
- G24f feasible value: N_fixed=6; the expanded set is secondary because the larger channel screen leaves fewer usable epochs.
- G8f primary value: N_fixed=15.
- Subjects below selected N in G8f: ['sub-13', 'sub-40'].
- Subjects below G24f N_fixed in the expanded set: ['sub-13', 'sub-40'].
- Each subsample is drawn without replacement; 100 subsamples are planned; per-subject seed is 42 plus the zero-based subject index.

## Locked graph contract

- Bands: delta 1-4 Hz, theta 4-8 Hz, alpha 8-13 Hz, beta 13-30 Hz.
- Graph metrics: absolute efficiency asymmetry, absolute clustering asymmetry, mean homotopic wPLI, and aligned normalized Frobenius distance.
- Pair orientation and channel order are load-bearing and must not change without reopening this lock and documenting the reason.

## Reproducibility

- Configs: `configs/graph_g8f.json` and `configs/graph_g24f.json`.
- Full audit: `docs/graph_design_audit_v2.json`.
- This is a technical design lock, not evidence of label-related improvement.
