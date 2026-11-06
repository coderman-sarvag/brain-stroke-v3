# v2 Feature Changelog

## v2 compared with legacy v1

### Metadata and spectral features

- Added `features/v2/spectral_abs.csv`, using absolute values of the 16 existing subject-level spectral AI features.
- Added `features/v2/spectral_lesion.csv`, mapping verified paralysis side to contralateral lesion side under the documented v2 rule.
- Kept labels and clinical metadata in `features/v2/subject_meta.csv`; v2 feature tables remain label-free.
- Preserved the legacy v1 files unchanged.

### Graph features

- Added fixed-epoch graph representations `graph_g8f.csv` and `graph_g24f.csv`.
- G8f uses the clean 8-channel core and `N_fixed=15`.
- G24f uses the retained 22-channel symmetric set and `N_fixed=6`.
- Both use 100 without-replacement subsamples per subject and median adjacency aggregation.
- Added absolute efficiency and clustering asymmetry, mean homotopic wPLI, and aligned Frobenius distance features.

### Artifact-screen correction

- The graph runner previously counted epochs passing the 150 uV screen but passed the unscreened Epochs object to the graph calculator.
- The shared `screen_epochs` function now applies the same screen to the actual sampling pool before cross-spectra and subsampling.
- Both graph tables were regenerated after this correction.

### Quality and reproducibility

- Added channel/epoch design audit and locked JSON configs.
- Added label-free QC for finite values, epoch-count bias, collinearity, and second-seed stability.
- Added sidecar provenance, source/config hashes, and `features/v2/MANIFEST.json`.
- Added synthetic and regression tests for graph symmetry, wPLI calculation, reproducibility, fixed-epoch behavior, and artifact screening.

## Known limitations

- Some residual epoch-count correlations remain after fixed-epoch sampling.
- Several features have seed stability below 0.9, particularly in G24f.
- G24f is secondary because its expanded channel screen supports only six fixed epochs.
- No real-label v2 evaluation has been performed; no predictive improvement is claimed.
