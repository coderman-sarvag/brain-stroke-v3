# V3 Step 8 Pre-freeze Check: Cross-half D2 by Interpolation Status (label-free)

**Date:** 2026-11-06. Requested at registry review, before the `features-v3` freeze. No label read.
**Data:** `abnormality_crosshalf_v3.csv` (Step 7b, Kaggle `a8acc35`) and `spectral_v3b` QC `pairs_one_interpolated` (Step 3b, Kaggle `9346c47`).
**Definition:** a subject has **one-sided interpolated analysed channels** when at least one homologous pair of the set (core: F3F4, C3C4, P3P4, O1O2; extended: the 11 pairs) has exactly one interpolated channel, at either the continuous stage or the rule (iii) stage.
- **Core:** 10 subjects (sub-02, 03, 12, 24, 28, 32, 33, 38, 39, 50); 35 without. This matches the Step 5 `core_flagged_edges_used` count.
- **Extended:** 26 subjects; 19 without.

## Share of subjects with D2 > 0 (about 0.50 expected if there were no true asymmetry)

| Set | Level | Band | Without one-sided interpolation | With one-sided interpolation |
|---|---|---|---|---|
| Core | edge | delta | 0.69 (n 35) | 0.80 (n 10) |
| | | theta | 0.69 | 0.70 |
| | | alpha | 0.83 | 0.80 |
| | | beta | 0.74 | 0.60 |
| | node | delta | 0.57 | 0.70 |
| | | theta | 0.63 | 0.60 |
| | | alpha | 0.74 | 0.70 |
| | | beta | 0.71 | 0.50 |
| Extended | edge | delta | 0.89 (n 19) | 1.00 (n 26) |
| | | theta | 0.95 | 0.96 |
| | | alpha | 1.00 | 0.92 |
| | | beta | 1.00 | 0.96 |
| | node | delta | 0.79 | 1.00 |
| | | theta | 0.79 | 0.85 |
| | | alpha | 0.95 | 0.81 |
| | | beta | 0.89 | 0.81 |

## Reading

- **No systematic inflation.** One-sided interpolation would be expected to manufacture asymmetry, which would raise the share of D2 > 0. Instead, the differences go in both directions by band (higher in delta, lower in beta and alpha). The interpolated core group is small (n = 10, so one subject moves the share by 0.10).
- **Not driven by interpolation.** The high extended-set shares (0.81–1.00) hold in both groups.
- **Planned check stays.** The registered S3 sensitivity analysis (V3/V4 excluding the 10 core-flagged subjects) remains in the registry as planned.
