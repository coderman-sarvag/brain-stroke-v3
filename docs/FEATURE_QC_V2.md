# v2 Graph Feature QC

Feature-engineering checks below are label-free. The explicitly authorized exclusion-class disclosure is separate descriptive metadata accounting and did not alter feature engineering or eligibility.

## Exclusion class balance - 2026-10-19

The user authorized reading `subject_meta.csv` for this disclosure. `sub-13` has NIHSS 9 (moderate) and `sub-40` NIHSS 6 (moderate). Both exclusions are therefore moderate. The 50-subject cohort has 33 mild / 17 moderate (66% / 34%); both 48-subject graph subsets have 33 mild / 15 moderate (68.75% / 31.25%). The moderate fraction decreases by 2.75 percentage points. The epoch eligibility rule was fixed before this inspection; no feature, subject selection or threshold was changed. Spectral tests retain all 50 subjects. Between-table comparisons remain descriptive because membership differs.

## g8f

Paired-recording integrity was additionally checked across all 33 raw channels on 2026-10-19. Sub-04/05 are identical on all 32 named channels but differ on the unnamed channel and in age/sex/stroke-location metadata. The other two pairs remain highly similar without exact all-channel equality. Every audited metadata field agrees with its source TSV. See `RECORDING_INTEGRITY_AUDIT_V2.md` and `.json`; the user-approved separate-ID policy is unchanged and its dependence limitation remains.

- Rows: 48; features: 16.
- Finite values: True.
- Banned label/count column names: none.
- Constant features: none.

### Feature ranges

- `g8f_alpha_ClustCoeff_absAI`: min=0.000141762, max=0.155324
- `g8f_alpha_FrobeniusDist`: min=0.0242602, max=0.211901
- `g8f_alpha_GlobalEff_absAI`: min=0.000211714, max=0.133991
- `g8f_alpha_MeanHomotopic`: min=0.283466, max=0.412856
- `g8f_beta_ClustCoeff_absAI`: min=0.000651039, max=0.0714665
- `g8f_beta_FrobeniusDist`: min=0.0105658, max=0.113897
- `g8f_beta_GlobalEff_absAI`: min=0.000641991, max=0.062792
- `g8f_beta_MeanHomotopic`: min=0.282442, max=0.34757
- `g8f_delta_ClustCoeff_absAI`: min=0.000913633, max=0.188661
- `g8f_delta_FrobeniusDist`: min=0.0385722, max=0.212639
- `g8f_delta_GlobalEff_absAI`: min=0.000662256, max=0.17429
- `g8f_delta_MeanHomotopic`: min=0.26837, max=0.444593
- `g8f_theta_ClustCoeff_absAI`: min=0.000173179, max=0.279371
- `g8f_theta_FrobeniusDist`: min=0.0275, max=0.232422
- `g8f_theta_GlobalEff_absAI`: min=9.94847e-05, max=0.126793
- `g8f_theta_MeanHomotopic`: min=0.275474, max=0.433335

### Epoch-count bias

- `g8f_alpha_ClustCoeff_absAI` vs `n_epochs_all`: Spearman r=-0.212877
- `g8f_alpha_FrobeniusDist` vs `n_epochs_all`: Spearman r=-0.359296
- `g8f_alpha_GlobalEff_absAI` vs `n_epochs_all`: Spearman r=-0.255843
- `g8f_alpha_MeanHomotopic` vs `n_epochs_all`: Spearman r=-0.303608
- `g8f_beta_ClustCoeff_absAI` vs `n_epochs_all`: Spearman r=-0.110149
- `g8f_beta_FrobeniusDist` vs `n_epochs_all`: Spearman r=-0.14229
- `g8f_beta_GlobalEff_absAI` vs `n_epochs_all`: Spearman r=0.123932
- `g8f_beta_MeanHomotopic` vs `n_epochs_all`: Spearman r=0.0603756
- `g8f_delta_ClustCoeff_absAI` vs `n_epochs_all`: Spearman r=-0.0884988
- `g8f_delta_FrobeniusDist` vs `n_epochs_all`: Spearman r=-0.070308
- `g8f_delta_GlobalEff_absAI` vs `n_epochs_all`: Spearman r=-0.044082
- `g8f_delta_MeanHomotopic` vs `n_epochs_all`: Spearman r=-0.104179
- `g8f_theta_ClustCoeff_absAI` vs `n_epochs_all`: Spearman r=-0.141286
- `g8f_theta_FrobeniusDist` vs `n_epochs_all`: Spearman r=-0.208636
- `g8f_theta_GlobalEff_absAI` vs `n_epochs_all`: Spearman r=-0.273755
- `g8f_theta_MeanHomotopic` vs `n_epochs_all`: Spearman r=-0.175379

### Collinearity

- Pairs with |r| > 0.95: none

### Second-seed stability

- Alternate seed base: 1042.
- `g8f_alpha_ClustCoeff_absAI` between seed runs: Spearman r=0.774859
- `g8f_alpha_FrobeniusDist` between seed runs: Spearman r=0.972102
- `g8f_alpha_GlobalEff_absAI` between seed runs: Spearman r=0.892749
- `g8f_alpha_MeanHomotopic` between seed runs: Spearman r=0.979483
- `g8f_beta_ClustCoeff_absAI` between seed runs: Spearman r=0.794073
- `g8f_beta_FrobeniusDist` between seed runs: Spearman r=0.886018
- `g8f_beta_GlobalEff_absAI` between seed runs: Spearman r=0.910334
- `g8f_beta_MeanHomotopic` between seed runs: Spearman r=0.92944
- `g8f_delta_ClustCoeff_absAI` between seed runs: Spearman r=0.848784
- `g8f_delta_FrobeniusDist` between seed runs: Spearman r=0.87614
- `g8f_delta_GlobalEff_absAI` between seed runs: Spearman r=0.827508
- `g8f_delta_MeanHomotopic` between seed runs: Spearman r=0.965371
- `g8f_theta_ClustCoeff_absAI` between seed runs: Spearman r=0.721884
- `g8f_theta_FrobeniusDist` between seed runs: Spearman r=0.918693
- `g8f_theta_GlobalEff_absAI` between seed runs: Spearman r=0.910877
- `g8f_theta_MeanHomotopic` between seed runs: Spearman r=0.948545

## g24f

- Rows: 48; features: 16.
- Finite values: True.
- Banned label/count column names: none.
- Constant features: none.

### Feature ranges

- `g24f_alpha_ClustCoeff_absAI`: min=9.87105e-05, max=0.0740839
- `g24f_alpha_FrobeniusDist`: min=0.0189278, max=0.103511
- `g24f_alpha_GlobalEff_absAI`: min=4.82045e-05, max=0.0603396
- `g24f_alpha_MeanHomotopic`: min=0.449983, max=0.579152
- `g24f_beta_ClustCoeff_absAI`: min=0.000519227, max=0.0616236
- `g24f_beta_FrobeniusDist`: min=0.011285, max=0.0605011
- `g24f_beta_GlobalEff_absAI`: min=0.000134343, max=0.0420273
- `g24f_beta_MeanHomotopic`: min=0.449195, max=0.491318
- `g24f_delta_ClustCoeff_absAI`: min=0.000867025, max=0.146527
- `g24f_delta_FrobeniusDist`: min=0.0220369, max=0.126716
- `g24f_delta_GlobalEff_absAI`: min=0.000463055, max=0.0598563
- `g24f_delta_MeanHomotopic`: min=0.453304, max=0.574011
- `g24f_theta_ClustCoeff_absAI`: min=0.00201358, max=0.15284
- `g24f_theta_FrobeniusDist`: min=0.0181396, max=0.147763
- `g24f_theta_GlobalEff_absAI`: min=0.000762302, max=0.081495
- `g24f_theta_MeanHomotopic`: min=0.444204, max=0.539137

### Epoch-count bias

- `g24f_alpha_ClustCoeff_absAI` vs `n_epochs_all`: Spearman r=-0.450529
- `g24f_alpha_FrobeniusDist` vs `n_epochs_all`: Spearman r=-0.530881
- `g24f_alpha_GlobalEff_absAI` vs `n_epochs_all`: Spearman r=-0.169744
- `g24f_alpha_MeanHomotopic` vs `n_epochs_all`: Spearman r=-0.416715
- `g24f_beta_ClustCoeff_absAI` vs `n_epochs_all`: Spearman r=0.178727
- `g24f_beta_FrobeniusDist` vs `n_epochs_all`: Spearman r=-0.412027
- `g24f_beta_GlobalEff_absAI` vs `n_epochs_all`: Spearman r=-0.226883
- `g24f_beta_MeanHomotopic` vs `n_epochs_all`: Spearman r=-0.17644
- `g24f_delta_ClustCoeff_absAI` vs `n_epochs_all`: Spearman r=0.277605
- `g24f_delta_FrobeniusDist` vs `n_epochs_all`: Spearman r=-0.347578
- `g24f_delta_GlobalEff_absAI` vs `n_epochs_all`: Spearman r=0.00976501
- `g24f_delta_MeanHomotopic` vs `n_epochs_all`: Spearman r=0.0774504
- `g24f_theta_ClustCoeff_absAI` vs `n_epochs_all`: Spearman r=0.223535
- `g24f_theta_FrobeniusDist` vs `n_epochs_all`: Spearman r=-0.389707
- `g24f_theta_GlobalEff_absAI` vs `n_epochs_all`: Spearman r=-0.070866
- `g24f_theta_MeanHomotopic` vs `n_epochs_all`: Spearman r=-0.179732

### Collinearity

- Pairs with |r| > 0.95: none

### Second-seed stability

- Alternate seed base: 1042.
- `g24f_alpha_ClustCoeff_absAI` between seed runs: Spearman r=0.567846
- `g24f_alpha_FrobeniusDist` between seed runs: Spearman r=0.854863
- `g24f_alpha_GlobalEff_absAI` between seed runs: Spearman r=0.76954
- `g24f_alpha_MeanHomotopic` between seed runs: Spearman r=0.919887
- `g24f_beta_ClustCoeff_absAI` between seed runs: Spearman r=0.723947
- `g24f_beta_FrobeniusDist` between seed runs: Spearman r=0.937473
- `g24f_beta_GlobalEff_absAI` between seed runs: Spearman r=0.797547
- `g24f_beta_MeanHomotopic` between seed runs: Spearman r=0.92271
- `g24f_delta_ClustCoeff_absAI` between seed runs: Spearman r=0.711572
- `g24f_delta_FrobeniusDist` between seed runs: Spearman r=0.90762
- `g24f_delta_GlobalEff_absAI` between seed runs: Spearman r=0.840643
- `g24f_delta_MeanHomotopic` between seed runs: Spearman r=0.92944
- `g24f_theta_ClustCoeff_absAI` between seed runs: Spearman r=0.531915
- `g24f_theta_FrobeniusDist` between seed runs: Spearman r=0.865176
- `g24f_theta_GlobalEff_absAI` between seed runs: Spearman r=0.749132
- `g24f_theta_MeanHomotopic` between seed runs: Spearman r=0.924446

