# Agent Rules

## Authority and starting point

- Read `EXECUTION_GUIDE_CURRENT.md` first. It is the authoritative operational guide.
- Use `docs/PROGRESS.md` for the active status and next subphase.
- Use `docs/CONTEXT.md` for the concise handoff context supplied to the next prompt.
- Use `docs/Ledgers/` for historical and technical context.
- `docs/archive/PROJECT_EXECUTION_GUIDE_V1.md` is the original reference plan and is stale for current v2 work.
- `docs/CONTEXT.md` is the current prompt-handoff document; all live context references must use it.

## Project contract

- The current Figshare task is binary: `0=mild` and `1=moderate`. There are 0 severe subjects.
- Legacy v1 feature files and results are frozen reference artifacts. Do not overwrite them for v2.
- v2 feature CSVs contain only `subject_id` and feature columns. Labels and metadata belong in `features/v2/subject_meta.csv`.
- Feature-building code must not read `nihss_raw` or `severity_class`. Only the explicitly approved lesion-alignment step may read verified `lesion_side`.
- Never put NIHSS, severity, subject IDs, or epoch-count columns into a model matrix.

## Leakage and evaluation

- All scaling and feature selection must be inside sklearn pipelines.
- Legacy model evaluation uses `RepeatedStratifiedKFold(n_splits=5, n_repeats=10, random_state=42)` and reports macro-F1, balanced accuracy, and binary ROC-AUC with a majority-class dummy baseline.
- Do not perform repeated label-driven tuning on the small cohort.
- Real-label v2 evaluation is allowed only through the frozen registry described in `EXECUTION_GUIDE_CURRENT.md`.

## v2 workflow rules

- v2 is new-files-only: use `src/*_v2.py`, `features/v2/`, `configs/`, `tests/`, `results/v2/`, and new docs.
- Every v2 constant belongs in a JSON config; record hashes, seeds, channels, bands, and output schemas.
- Use fixed-size epoch sampling without replacement and deterministic seeds.
- Keep engineering label-blind. Report technical failures rather than tuning them away.
- Do not claim v2 is complete until tests, QC, metadata provenance, review, manifest, and freeze tag are complete.

## Change and logging rules

- Before editing, identify the active subphase and its acceptance check.
- After each update, update `docs/PROGRESS.md`, rewrite `docs/Ledgers/project_technical_ledger_clean.md` to reflect the current technical state, and append the work to `docs/Ledgers/project_timeline_ledger_clean.md`.
- If a required input is missing or semantics are uncertain, mark the subphase `BLOCKED` and record the exact reason.
- Do not commit, tag, or create branches unless explicitly requested.
