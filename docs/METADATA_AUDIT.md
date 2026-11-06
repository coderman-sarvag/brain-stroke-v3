# Figshare Metadata Audit (v2 A0)

**Review date:** 2026-10-17

**Status:** A0 side-semantics and A2/T3 feasibility checks passed under the project's prescribed contralateral mapping.

## Follow-up verification — 2026-10-17

The user supplied `data/raw/figshare/participants.tsv` and `participants.json` after the earlier review below. The [Figshare version records](https://api.figshare.com/v2/articles/21679035/versions/1) authenticate the files by their published MD5 checksums. The supplied JSON defines `ParalysisSide` as the side of limb paralysis due to stroke. The project's explicitly prescribed contralateral mapping is an assumption for alignment, not confirmation of lesion hemisphere by imaging for every subject.

Source: Figshare dataset `10.6084/m9.figshare.21679035`, authors Haijie Liu and Xiaodong Lv. Figshare's version 1 was published on 2022-12-07. The supplied TSV is asset `42345150` in [version 5](https://api.figshare.com/v2/articles/21679035/versions/5), MD5 `d82596d5309f7d207c760918e74d4553`. The supplied JSON is asset `38516579`, present in versions 3–5, MD5 `19ff0e65b74ada4e2df468a2509a22cb`; the version 1 JSON asset `38436064` has the same published checksum. Version 1 TSV asset `38436070` has a different checksum (`10cc8617517e8929f6b7dc4757dee39e`) from the supplied version 5 TSV. An independent comparison of the 50 participant IDs and `ParalysisSide` values in the version 1 and version 5 tables found zero side mismatches. The claimed asset/version association has therefore been corrected; no claim is made that the TSV files are byte-identical.

- SHA-256 `participants.tsv`: `0367302fd7448173ebc110d21051b4a27e253e32e725cd64b5460ac32a6566f6`.
- SHA-256 `participants.json`: `d8df0c6ec1a8786835e727d70c4431ab225a3e56d59378131dc868d45941b99b`.
- SHA-256 `features/v2/subject_meta.csv`: `951ee16bb07095bfdcb448952a02731bbc8f0015fe02c937ec8c6e1f6eed7f68`.
- SHA-256 `features/v2/spectral_lesion.csv`: `0f7a9006febbfa46f2c19a67d1e2f8d7a4236c8bcea4af2d70548071e398eacb`.
- Source and subject metadata each contain 50 unique IDs; one-to-one join: 50 matched, zero missing or extra. All stored paralysis sides match the supplied table and all stored lesion sides match the prescribed opposite-side mapping. Source paralysis counts: left 28, right 22; derived lesion counts: left 22, right 28.
- All 50 lesion-feature rows and all 16 aligned AI columns were compared with the legacy source under the recorded sign convention (+ for left lesion, − for right lesion): maximum absolute difference `1.11e-16` across 800 values. The three global columns match exactly; output values are finite. No NIHSS or severity values were used.
- The supplied data pass the numerical minimum of 10 mapped cases per side. T3 is **eligible for inclusion** under the pre-specified mapping and feasibility rule. The prior blocked findings below are historical, not the current file state. Registry and feature freeze still require the separate reviews, manifest and tags.

## Earlier review (superseded by the follow-up above)

- `data/raw/figshare/participants.tsv` exists, but its 120 rows have event columns `onset`, `duration`, `trial_type`, `response_time`, `value`, and `stim_file`. It is not the participant metadata table described by the earlier audit. The user reports that `task-motor-imagery_events.tsv` was renamed to `participants.tsv`; the present file's contents are consistent with event records, though the rename history has not been independently established.
- The previously cited `data/raw/figshare/participants.json` is not present. The repository search found no alternate participant TSV or companion JSON.
- The timeline's State 8 recorded participant metadata as missing. State 9 later claimed that a participant table and description had been found; those claims cannot be corroborated from the files currently available. The archived original plan also reports an earlier download, but is not the underlying source.
- `features/v2/subject_meta.csv` contains `paralysis_side`, derived `lesion_side`, and other metadata. The prior audit reported 22 left and 28 right mapped lesion sides, but the original participant rows and source documentation are unavailable for independent comparison. These are reported derived counts, not verified source counts.
- `src/audit_metadata_v2.py` maps left/right paralysis to the opposite lesion side, but its report text and stated `ParalysisSide` definition are hard-coded. It checks whether a JSON path exists but does not read or validate its contents. The generated audit alone is therefore insufficient evidence of a semantic audit.

### Source leads identified 2026-10-17

- The [original Figshare record](https://figshare.com/articles/dataset/EEG_datasets_of_stroke_patients/21679035) describes the 50-subject dataset and reports aggregate hemiplegia counts; aggregate counts do not verify individual subject mappings.
- [NEMAR's dataset record](https://nemar.org/dataset/nm000158) identifies a BIDS version derived from the Figshare dataset and lists `participants.tsv` and `participants.json`, with a versioned direct link to the table. This is a lead, not yet a validated match to the source used in this project. Obtain the table and data dictionary, record their versions and hashes, and reconcile identifiers and rows before relying on them. The NEMAR summary and Figshare record report different aggregate hemiplegia counts; investigate this discrepancy rather than choosing a count by assumption.
