"""Registered descriptive analyses S1-S11 only, after the one real run crashed in S8 (deviation D20).

The registry-v3 run (run_20261106T163923Z) completed and saved the primary family V1-V4, then stopped at S8-V3:
train_regression_v3.load_test only reads the spec's listed features, so a derived feature (mean of the four
extended_*_D2_edge columns) could not be built. registry-v3 freezes that engine, so it is NOT edited here.
This script repeats every guard of run_registry_v3.py, reuses its run_sensitivities() unchanged, and adds one
adapter: when a derived feature is requested, the columns it averages are passed as the features to load (the
derivation itself is the engine's own code). V1-V4 are NOT rerun.

Run from the repo root:
  python src/run_sensitivities_v3.py --data-root <folder containing figshare/> --original-run run_20261106T163923Z \
      --reason "<logged reason>" [--out-root O]
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_registry_v3 as reg  # noqa: E402
from paths_v3 import add_root_args, roots_from_args  # noqa: E402
from provenance_v3 import ROOT, git_commit, load_config, sha256_file  # noqa: E402

_original_safe_describe = reg.safe_describe


def safe_describe_with_derive_columns(cfg, settings, spec, subjects, extra=None, derive=None):
    """Adapter (D20): load the columns a derived feature averages; everything else is the tagged code."""
    if derive:
        spec = {**spec, "features": list(derive["mean_of"])}
    return _original_safe_describe(cfg, settings, spec, subjects, extra=extra, derive=derive)


def main(argv=None):
    parser = add_root_args(argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter))
    parser.add_argument("--original-run", required=True, help="folder name of the registry-v3 run whose S1-S11 crashed")
    parser.add_argument("--reason", required=True, help="logged reason for running the sensitivities separately")
    args = parser.parse_args(argv)
    roots = roots_from_args(args)
    cfg, config_path = load_config(reg.CONFIG)
    guards = cfg["guards"]

    present = set(reg.git("tag", "-l").stdout.split())
    reg.check_tags(present, guards["tags"], lambda t: reg.git("merge-base", "--is-ancestor", t, "HEAD").returncode == 0)
    reg.check_unchanged_since_tag("registry-v3", guards["frozen_at_registry_tag"])
    manifest = json.loads((ROOT / guards["manifest"]).read_text(encoding="utf-8"))
    n_checked = reg.check_manifest(manifest, ROOT, label_sha=cfg["labels"]["sha256_lf"])
    lab = cfg["labels"]
    cc = lab["crosscheck"]
    labels = pd.read_csv(ROOT / lab["file"], usecols=lab["columns"])
    participants = pd.read_csv(roots.data_path(cc["file"]), sep="\t", usecols=[cc["id_column"], cc["nihss_column"]])
    mismatch = reg.crosscheck_labels(labels, participants, cfg["cohort"]["main"], cc["id_column"], cc["nihss_column"])
    if mismatch:
        raise SystemExit(f"Refusing: NIHSS mismatch for {mismatch}")

    out_dir = roots.out_path(cfg["outputs"]["dir"]) / f"sensitivities_for_{args.original_run}"
    out_dir.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    reg.log_progress(f"Registry v3 sensitivities-only invocation {started}: START for {args.original_run}; "
                     f"reason={args.reason!r}; out={out_dir}")
    reg.safe_describe = safe_describe_with_derive_columns
    try:
        sens = reg.run_sensitivities(cfg, cfg["settings"], roots.data)
    finally:
        reg.safe_describe = _original_safe_describe
    sens.to_csv(out_dir / "sensitivity_results.csv", index=False)
    record = {"started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(), "git": git_commit(),
              "original_run": args.original_run, "reason": args.reason, "primary_rerun": False,
              "adapter": "derived features: the averaged columns are loaded before the engine's own derivation (D20)",
              "manifest_files_checked": n_checked, "config_sha256": sha256_file(config_path),
              "source_sha256": {f: sha256_file(ROOT / f) for f in [*guards["frozen_at_registry_tag"], "src/run_sensitivities_v3.py"]},
              "n_rows": len(sens), "not_computable": sens.loc[sens.get("status", pd.Series(dtype=str)) == "not_computable", ["id", "test"]].values.tolist()
              if "status" in sens else []}
    (out_dir / "sensitivity_record.json").write_text(json.dumps(record, indent=1, default=str) + "\n", encoding="utf-8")
    reg.log_progress(f"Registry v3 sensitivities-only invocation {record['finished_utc']}: COMPLETE; out={out_dir}")
    with pd.option_context("display.width", 200, "display.max_columns", 12):
        print(sens.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
