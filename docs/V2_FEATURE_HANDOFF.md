# v2 Feature Handoff Decision

**Status:** Ready for project-owner review; not yet tagged `features-v2`
**Date:** 2026-10-18

## Final design decision

- **Primary graph representation:** G8f, the audited 8-channel core with `N_fixed=15`.
- **Secondary registered representation (T6):** G24f, the expanded 22-channel symmetric set with `N_fixed=6`, included in Group B's nine-test Holm family (decision finalized 2026-10-19).
- **Spectral tables:** `spectral_abs.csv` and `spectral_lesion.csv` remain registered feature alternatives.
- **Excluded subjects:** `sub-13` and `sub-40` are absent from both graph tables because they do not meet the relevant fixed-epoch minimum.
- **Exclusion class disclosure (2026-10-19, explicitly authorized):** `sub-13` NIHSS 9 and `sub-40` NIHSS 6 are both moderate. The graph subsets therefore have 33 mild / 15 moderate (68.75% / 31.25%), compared with 33 / 17 (66% / 34%) in the full cohort. The moderate proportion decreases by 2.75 percentage points; the locked epoch rule and feature values are unchanged.
- **No representation is claimed to improve prediction before the registry run.**

## Why G8f is primary

G8f uses the established clean channel core and supports 15 fixed usable epochs. G24f retains more channels but the expanded screen reduces the feasible fixed count to 6, making it less stable and more vulnerable to sampling variability. G24f is retained as secondary registered test T6. Its secondary status does not remove it from multiplicity correction or change the registered decision rule.

## Fixed graph contract

- Bands: delta 1-4 Hz, theta 4-8 Hz, alpha 8-13 Hz, beta 13-30 Hz.
- Artifact screen: 150 uV peak-to-peak on every configured channel.
- The artifact screen is applied to the actual sampling pool before cross-spectra and subsampling.
- Subsampling: 100 draws without replacement per subject, with seed `42 + zero-based subject index`.
- Aggregation: median adjacency across subsamples.
- Metrics: absolute efficiency asymmetry, absolute clustering asymmetry, mean homotopic wPLI, and aligned normalized Frobenius distance.

## QC limitations to report

- The 2026-10-19 all-channel integrity audit found exact equality across all 32 named channels for sub-04/05, despite different age, sex and stroke location; the unnamed channel differs. No pair is byte-identical as a complete EDF. Source and stored metadata agree for the audited fields. See `RECORDING_INTEGRITY_AUDIT_V2.md` and `.json`; retain the existing subject policy and explicitly review the unresolved recording dependence.

- G8f retains residual epoch-count correlations for some features, including alpha Frobenius distance (approximately -0.36).
- G24f has stronger residual epoch-count correlations for several features.
- Several graph features have second-seed stability below 0.9, especially in G24f.
- No feature was tuned or removed using NIHSS or severity labels.
- These findings are limitations to report, not reasons to select a more favorable configuration.

## Handoff contents

- `features/v2/spectral_abs.csv`
- `features/v2/spectral_lesion.csv`
- `features/v2/graph_g8f.csv`
- `features/v2/graph_g24f.csv`
- `features/v2/subject_meta.csv`
- `features/v2/MANIFEST.json`
- All feature sidecars and graph configs
- `docs/FEATURE_QC_V2.md`
- `docs/GRAPH_DESIGN_LOCK.md`
- `docs/METADATA_AUDIT.md`

## Group B boundary

The current project may use the frozen schemas and sidecars to build the registry and evaluation harness. It must not alter feature values, channel sets, epoch counts, or registered feature definitions after registry freeze. Real-label evaluation remains prohibited until Agrim's latest owner review, registry freeze, and `features-v2` tag are complete.
