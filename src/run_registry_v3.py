"""One-shot v3 registry run (real labels). Refuses unless every guard passes:

  1. git tags features-v3 and registry-v3 exist and are ancestors of HEAD;
  2. registry code/config files are unchanged since the registry-v3 tag;
  3. every file in features/v3/MANIFEST.json (tables, sidecars, config copies, QC, label file) matches its sha256;
  4. NIHSS in participants.tsv equals nihss_raw in the v2 label file for all 45 cohort subjects.

Then runs V1-V4 (permutation p, bootstrap CI, Holm, decision rule) and the descriptive S1-S11, writes
results/v3/registry/ and logs the invocation in docs/PROGRESS.md. A rerun requires --rerun-reason.

Run from the repo root: python src/run_registry_v3.py --data-root <folder containing figshare/> [--out-root O]
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import train_regression_v3 as eng  # noqa: E402
from paths_v3 import add_root_args, roots_from_args  # noqa: E402
from provenance_v3 import ROOT, git_commit, load_config, sha256_file  # noqa: E402
from stats_utils import holm_adjust  # noqa: E402

CONFIG = "configs/v3/registry_v3.json"


# ---------------------------------------------------------------- guards (pure where possible)

def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def check_tags(present, required, ancestor_ok):
    missing = [t for t in required if t not in present]
    if missing:
        raise SystemExit(f"Refusing: missing git tag(s) {missing}")
    not_ancestor = [t for t in required if not ancestor_ok(t)]
    if not_ancestor:
        raise SystemExit(f"Refusing: tag(s) {not_ancestor} are not ancestors of HEAD")


def check_unchanged_since_tag(tag, files):
    changed = [f for f in files if git("diff", "--quiet", tag, "--", f).returncode != 0]
    if changed:
        raise SystemExit(f"Refusing: {changed} changed since {tag}")


def check_manifest(manifest, root, label_sha=None):
    """Verify every manifest file; label_sha (registry config) overrides the manifest's label entry (erratum)."""
    records = []
    for t in manifest["tables"]:
        records.append((t["path"], t["sha256"]))
        for key in ("sidecar", "config_copy"):
            if key in t:
                records.append((t[key]["path"], t[key]["sha256"]))
    records += [(q["path"], q["sha256"]) for q in manifest["qc_files"]]
    records.append((manifest["label_file"]["path"], label_sha or manifest["label_file"]["sha256"]))
    bad = [p for p, s in records if not (Path(root) / p).exists() or sha256_file(Path(root) / p) != s]
    if bad:
        raise SystemExit(f"Refusing: manifest hash mismatch for {bad}")
    return len(records)


def crosscheck_labels(labels, participants, subjects, id_col, nihss_col):
    """Return mismatching subjects (empty list = consistent)."""
    a = labels.set_index("subject_id")["nihss_raw"]
    b = participants.set_index(id_col)[nihss_col]
    return [s for s in subjects if s not in b.index or s not in a.index or float(a[s]) != float(b[s])]


# ---------------------------------------------------------------- analyses

def subjects_for(cfg, cohort, drop=(), keep=None):
    ids = [s for s in cfg["cohort"][cohort] if s not in set(drop)]
    return [s for s in ids if keep is None or s in keep]


def covariate(cfg, name):
    c = cfg["covariates"][name]
    return pd.read_csv(ROOT / c["file"], usecols=["subject_id", c["column"]]).set_index("subject_id")[c["column"]]


def run_primary(cfg, settings):
    rows, nulls = [], {}
    for number, spec in enumerate(cfg["tests"], start=1):
        X, y, strata, groups, ids, feats = eng.load_test(ROOT, spec, cfg, cfg["cohort"][spec["cohort"]])
        if len(ids) != spec["expected_n"]:
            raise SystemExit(f"{spec['id']}: N {len(ids)} != expected {spec['expected_n']}")
        res = eng.evaluate(X, y, strata, groups, settings, number, kind=spec["kind"], alternative=spec["alternative"])
        nulls[spec["id"]] = res["null"]
        rows.append({"test": spec["id"], "kind": spec["kind"], "features": ";".join(feats), **res["summary"]})
    table = pd.DataFrame(rows)
    table["p_holm"] = holm_adjust(table["p_raw"].to_numpy())
    table["decision"] = np.where((table["p_holm"] < settings["holm_alpha"]) & (table["rho"].abs() >= settings["rho_threshold"]),
                                 "signal_detected", "no_effect_detected")
    return table, nulls


def safe_describe(cfg, settings, spec, subjects, extra=None, derive=None):
    try:
        X, y, strata, groups, ids, _ = eng.load_test(ROOT, spec, cfg, subjects, derive=derive)
        if extra is not None:
            X = np.column_stack([X, extra.reindex(ids).to_numpy(float)])
        return {"status": "ok", **eng.describe(X, y, strata, groups, settings, spec["kind"])}
    except (ValueError, SystemExit) as exc:
        return {"status": "not_computable", "reason": str(exc), "n": len(subjects)}


def run_sensitivities(cfg, settings, data_root):
    s, tests = cfg["sensitivities"], {t["id"]: t for t in cfg["tests"]}
    out = []
    n_ep = covariate(cfg, "n_epochs")
    # S1 quality adjustment
    for tid in ("V1", "V2", "V3"):
        X, y, _, _, ids, _ = eng.load_test(ROOT, tests[tid], cfg, cfg["cohort"][tests[tid]["cohort"]])
        out.append({"id": "S1", "test": tid, "rho": eng.partial_spearman(X[:, 0], y, n_ep.reindex(ids)), "n": len(ids),
                    "what": "partial Spearman | n_epochs"})
    out.append({"id": "S1", "test": "V4", "what": "Ridge + n_epochs feature",
                **safe_describe(cfg, settings, tests["V4"], cfg["cohort"]["main"], extra=n_ep)})
    # S2 site subgroups
    site = covariate(cfg, "site_class")
    for name, classes in cfg["covariates"]["site_class"]["groups"].items():
        keep = set(site[site.isin(classes)].index)
        for tid in s["S2"]["applies"]:
            out.append({"id": "S2", "test": tid, "what": name,
                        **safe_describe(cfg, settings, tests[tid], subjects_for(cfg, tests[tid]["cohort"], keep=keep))})
    # S3 core-flagged exclusion; S4 motion exclusion; S9 near-duplicate drop
    flagged = covariate(cfg, "core_flagged")
    motion = covariate(cfg, "motion")
    for sid, drop, applies in (("S3", set(flagged[flagged > 0].index), s["S3"]["applies"]),
                               ("S4", set(motion[motion.astype(str) == "True"].index), s["S4"]["applies"]),
                               ("S9", set(s["S9"]["drop"]), s["S9"]["applies"])):
        for tid in applies:
            out.append({"id": sid, "test": tid, **safe_describe(cfg, settings, tests[tid], subjects_for(cfg, tests[tid]["cohort"], drop=drop))})
    # S5 AUC is reported inside every describe/evaluate result; restated for the main cohort
    for tid in s["S5"]["applies"]:
        out.append({"id": "S5", "test": tid, **safe_describe(cfg, settings, tests[tid], cfg["cohort"][tests[tid]["cohort"]])})
    # S6 MBI / mRS (disability), descriptive
    lab = cfg["labels"]["secondary_scores"]
    part = pd.read_csv(Path(data_root) / lab["file"], sep="\t", usecols=["Participant_ID", *lab["columns"]]).set_index("Participant_ID")
    for tid in s["S6"]["applies"]:
        X, _, _, _, ids, _ = eng.load_test(ROOT, tests[tid], cfg, cfg["cohort"][tests[tid]["cohort"]])
        for score in lab["columns"]:
            v = pd.to_numeric(part[score].reindex(ids), errors="coerce").to_numpy(float)
            ok = np.isfinite(v)
            out.append({"id": "S6", "test": tid, "what": score, "n": int(ok.sum()),
                        "rho": float(spearmanr(X[ok, 0], v[ok]).statistic) if ok.sum() > 3 else float("nan")})
    # S8 extended instead of core
    out.append({"id": "S8", "test": "V3", **safe_describe(cfg, settings, tests["V3"], cfg["cohort"]["main"],
                                                          derive={"name": s["S8"]["V3"]["derived_feature"], "mean_of": s["S8"]["V3"]["mean_of"]})})
    v4_ext = {**tests["V4"], "features": s["S8"]["V4"]["features"]}
    out.append({"id": "S8", "test": "V4", **safe_describe(cfg, settings, v4_ext, cfg["cohort"]["main"])})
    # S10 confound check
    X, y, _, _, ids, _ = eng.load_test(ROOT, tests["V1"], cfg, cfg["cohort"]["main"])
    out.append({"id": "S10", "test": "n_epochs vs NIHSS", "rho": float(spearmanr(n_ep.reindex(ids), y).statistic), "n": len(ids)})
    # S11 draft Ridge models, descriptive
    for key, feats in (("spectral_lesion", "all_sidecar"), ("region_ic", "all_ic")):
        spec = {"kind": "ridge", "table": s["S11"][key]["table"], "sidecar": s["S11"][key]["sidecar"], "features": feats}
        out.append({"id": "S11", "test": key, **safe_describe(cfg, settings, spec, cfg["cohort"][s["S11"][key]["cohort"]])})
    return pd.DataFrame(out)


# ---------------------------------------------------------------- main

def log_progress(line):
    path = ROOT / "docs/PROGRESS.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.rstrip("\n") + "\n- " + line + "\n", encoding="utf-8")


def main(argv=None):
    parser = add_root_args(argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter))
    parser.add_argument("--rerun-reason", default=None)
    args = parser.parse_args(argv)
    roots = roots_from_args(args)
    cfg, config_path = load_config(CONFIG)
    guards = cfg["guards"]
    present = set(git("tag", "-l").stdout.split())
    check_tags(present, guards["tags"], lambda t: git("merge-base", "--is-ancestor", t, "HEAD").returncode == 0)
    check_unchanged_since_tag("registry-v3", guards["frozen_at_registry_tag"])
    manifest = json.loads((ROOT / guards["manifest"]).read_text(encoding="utf-8"))
    n_checked = check_manifest(manifest, ROOT, label_sha=cfg["labels"]["sha256_lf"])

    lab = cfg["labels"]
    labels = pd.read_csv(ROOT / lab["file"], usecols=lab["columns"])
    cc = lab["crosscheck"]
    participants = pd.read_csv(roots.data_path(cc["file"]), sep="\t", usecols=[cc["id_column"], cc["nihss_column"]])
    mismatch = crosscheck_labels(labels, participants, cfg["cohort"]["main"], cc["id_column"], cc["nihss_column"])
    if mismatch:
        raise SystemExit(f"Refusing: NIHSS mismatch between {lab['file']} and participants.tsv for {mismatch}")

    out_dir = roots.out_path(cfg["outputs"]["dir"]) / datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    log_progress(f"Registry v3 invocation {started}: START (rerun_reason={args.rerun_reason!r}); out={out_dir}")
    settings = cfg["settings"]
    primary, nulls = run_primary(cfg, settings)
    primary.to_csv(out_dir / "registry_v3_results.csv", index=False)
    np.savez(out_dir / "null_distributions.npz", **nulls)
    sens = run_sensitivities(cfg, settings, roots.data)
    sens.to_csv(out_dir / "sensitivity_results.csv", index=False)
    record = {"started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(), "git": git_commit(),
              "rerun_reason": args.rerun_reason, "manifest_files_checked": n_checked,
              "config_sha256": sha256_file(config_path),
              "source_sha256": {f: sha256_file(ROOT / f) for f in guards["frozen_at_registry_tag"]},
              "manifest_sha256": hashlib.sha256((ROOT / guards["manifest"]).read_bytes()).hexdigest(),
              "primary": primary.to_dict("records")}
    (out_dir / "run_record.json").write_text(json.dumps(record, indent=1, default=str) + "\n", encoding="utf-8")
    log_progress(f"Registry v3 invocation {record['finished_utc']}: COMPLETE; out={out_dir}")
    print(primary[["test", "n", "rho", "p_raw", "p_holm", "decision"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
