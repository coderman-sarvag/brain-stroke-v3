"""Synthetic acceptance gates for the v3 registry engine (no real-label inference).

Gate A  positive control: N 45 with two near-duplicate groups, 8 features carrying a planted signal (correlation
        0.6 between the true linear predictor and the target); ridge (1000 permutations) and association engines
        must both give p < 0.01.
Gate B  null calibration: 200 null datasets (200 permutations, 2 outer repeats); the exact 95% binomial CI of the
        false-positive rate at alpha 0.05 must contain 0.05, for both engines.
Gate C  shuffled smoke: every registry table (V1-V4, S11) on labels jointly shuffled before use (reduced
        settings); must run without error; rho reported.

Run from the repo root: python src/registry_gates_v3.py [--out-root O] [--n-jobs 4] [--only A B C]
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import numpy as np
from joblib import Parallel, delayed
from scipy.stats import binomtest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import train_regression_v3 as eng  # noqa: E402
from paths_v3 import add_root_args, roots_from_args  # noqa: E402
from provenance_v3 import ROOT, git_commit, load_config, sha256_file  # noqa: E402

CONFIG = "configs/v3/registry_v3.json"


def simulate(rng, n=45, p=8, rho=0.6, signal=True):
    """Synthetic NIHSS-like target (1-11, classes by >= 5), groups with two near-duplicate pairs, features."""
    X = rng.standard_normal((n, p))
    beta = rng.standard_normal(p)
    w = X @ beta
    w = (w - w.mean()) / w.std()
    latent = rho * w + np.sqrt(1 - rho ** 2) * rng.standard_normal(n) if signal else rng.standard_normal(n)
    y = np.clip(np.round(5 + 2.5 * latent), 1, 11)
    strata = (y >= 5).astype(int)
    groups = np.arange(n)
    groups[1], groups[3] = groups[0], groups[2]          # two near-duplicate pairs share a group
    X[1], X[3] = X[0] + 0.01 * rng.standard_normal(p), X[2] + 0.01 * rng.standard_normal(p)
    w = X @ beta                                          # planted predictor, recomputed after the near-duplicates
    return X, y, strata, groups, ((w - w.mean()) / w.std())[:, None]


def gate_a(settings, gcfg):
    rng = np.random.default_rng(gcfg["seed"])
    for _ in range(100):                                  # redraw until both classes allow 5 folds (label-free)
        X, y, strata, groups, w = simulate(rng, p=gcfg["n_features"], rho=gcfg["planted_rho"])
        if np.bincount(strata, minlength=2).min() >= settings["outer_splits"]:
            break
    s = {**settings, "permutations": gcfg["permutations"]}
    ridge = eng.evaluate(X, y, strata, groups, s, 901, kind="ridge")["summary"]
    assoc = eng.evaluate(w, y, strata, groups, s, 902, kind="association")["summary"]
    ok = ridge["p_raw"] < 0.01 and assoc["p_raw"] < 0.01
    return {"pass": bool(ok), "ridge": {k: ridge[k] for k in ("rho", "p_raw", "n", "mild", "moderate")},
            "association": {k: assoc[k] for k in ("rho", "p_raw", "n")}}


def null_once(i, settings, gcfg):
    rng = np.random.default_rng(gcfg["seed"] + i)
    while True:
        X, y, strata, groups, _ = simulate(rng, signal=False)
        if np.bincount(strata, minlength=2).min() >= settings["outer_splits"]:
            break
    s = {**settings, "permutations": gcfg["permutations"], "outer_repeats": gcfg["outer_repeats"], "bootstrap_resamples": 50}
    ridge = eng.evaluate(X, y, strata, groups, s, 1000 + i, kind="ridge")["summary"]["p_raw"]
    assoc = eng.evaluate(X[:, [0]], y, strata, groups, s, 5000 + i, kind="association")["summary"]["p_raw"]
    return ridge, assoc


def gate_b(settings, gcfg, n_jobs):
    pvals = Parallel(n_jobs=n_jobs)(delayed(null_once)(i, settings, gcfg) for i in range(gcfg["datasets"]))
    out, ok = {}, True
    for j, name in enumerate(("ridge", "association")):
        p = np.array([v[j] for v in pvals])
        k = int((p <= gcfg["alpha"]).sum())
        ci = binomtest(k, len(p)).proportion_ci(confidence_level=0.95, method="exact")
        passed = ci.low <= gcfg["alpha"] <= ci.high
        ok &= passed
        out[name] = {"false_positives": k, "datasets": len(p), "fpr": k / len(p), "ci95": [float(ci.low), float(ci.high)],
                     "pass": bool(passed), "p_quantiles": np.quantile(p, [0.1, 0.25, 0.5, 0.75, 0.9]).round(3).tolist()}
    return {"pass": bool(ok), **out}


def gate_c(settings, gcfg, cfg):
    s = {**settings, "permutations": gcfg["permutations"], "outer_repeats": gcfg["outer_repeats"], "bootstrap_resamples": 200}
    tests = {t["id"]: t for t in cfg["tests"]}
    s11 = cfg["sensitivities"]["S11"]
    specs = {**tests,
             "S11.spectral_lesion": {"kind": "ridge", "cohort": s11["spectral_lesion"]["cohort"], "table": s11["spectral_lesion"]["table"],
                                     "sidecar": s11["spectral_lesion"]["sidecar"], "features": "all_sidecar", "alternative": "greater"},
             "S11.region_ic": {"kind": "ridge", "cohort": s11["region_ic"]["cohort"], "table": s11["region_ic"]["table"],
                               "sidecar": s11["region_ic"]["sidecar"], "features": "all_ic", "alternative": "greater"}}
    out, ok = {}, True
    for i, name in enumerate(gcfg["tables"]):
        spec = specs[name]
        try:
            X, y, strata, groups, ids, feats = eng.load_test(ROOT, spec, cfg, cfg["cohort"][spec["cohort"]],
                                                            shuffle_seed=gcfg["seed_base"] + i)
            res = eng.evaluate(X, y, strata, groups, s, 9500 + i, kind=spec["kind"], alternative=spec.get("alternative"))["summary"]
            out[name] = {"pass": True, "n": len(ids), "n_features": len(feats), "rho_shuffled": res["rho"], "p_shuffled": res["p_raw"],
                         "missing_cells": int(np.isnan(X).sum())}
        except Exception as exc:  # report, do not hide
            ok = False
            out[name] = {"pass": False, "error": repr(exc)}
    return {"pass": bool(ok), **out}


def main(argv=None):
    parser = add_root_args(argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter))
    parser.add_argument("--n-jobs", type=int, default=4)
    parser.add_argument("--only", nargs="+", choices=["A", "B", "C"], default=["A", "B", "C"])
    args = parser.parse_args(argv)
    roots = roots_from_args(args)
    cfg, config_path = load_config(CONFIG)
    settings, g = cfg["settings"], cfg["gates"]
    results, timing = {}, {}
    for gate in args.only:
        start = time.time()
        if gate == "A":
            results["A_positive_control"] = gate_a(settings, g["positive_control"])
        elif gate == "B":
            results["B_null_calibration"] = gate_b(settings, g["null_calibration"], args.n_jobs)
        else:
            results["C_shuffled_smoke"] = gate_c(settings, g["shuffled_smoke"], cfg)
        timing[gate] = round(time.time() - start, 1)
        print(f"Gate {gate}: {json.dumps(list(results.values())[-1], default=str)}", flush=True)
    record = {"date_utc": datetime.now(timezone.utc).isoformat(), "git": git_commit(), "config_sha256": sha256_file(config_path),
              "engine_sha256": sha256_file(ROOT / "src/train_regression_v3.py"), "seconds": timing,
              "all_pass": all(r["pass"] for r in results.values()), "results": results,
              "note": "synthetic data and shuffled labels only; no real-label inference"}
    out = roots.out_path(cfg["outputs"]["gates_dir"]) / "gates_v3.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=1, default=str) + "\n", encoding="utf-8")
    print(f"ALL GATES PASS: {record['all_pass']}  ->  {out}")
    return 0 if record["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
