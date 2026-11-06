"""Step 7b: cross-half estimator of hemispheric deformation (label-free; deviation D18).

Unsigned asymmetry measures are inflated by estimation noise (Steps 5-7 report, L15). Here each subject's clean
4 s EPOCHS are split into two independent halves (stratified by class; 10 splits, fixed seed); connectivity is
recomputed in each half exactly as in Step 4, and graphs are built, masked and clipped exactly as in Steps 5-6
(symmetric mask from the full data, shared by both halves). The cross-half squared deformation

    D2 = mean over mirrored intra edges of (w_L1 - w_R1) * (w_L2 - w_R2)

uses RAW clipped weights and has no noise term in expectation (independent halves); the same is done for node
strength differences and for network summaries. D2 is frame-invariant (I/C = L/R); signed cross-half network
differences carry the LR and IC frames. Full-data squared differences are kept as naive_noiseinflated_* columns.

Resumable per subject. Label-free: reads epochs, epoch_qc and (only in lesion_signs) lesion_side_final.
Run from the repo root: python src/crosshalf_v3.py --prev-root <Step 2 out> [--out-root O] [--subjects ...]
"""
import argparse
import json
from pathlib import Path
import sys
import time
import traceback

import mne
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import connectivity_v3 as cv  # noqa: E402
import graph_v3 as gr  # noqa: E402
from paths_v3 import add_root_args, roots_from_args  # noqa: E402
from provenance_v3 import display_path, load_config, sha256_file, write_with_config  # noqa: E402

CONFIG = "configs/v3/crosshalf.json"
FORBIDDEN = {"nihss_raw", "severity_class", "nihss", "mbi", "mrs"}


# ---------------------------------------------------------------- building blocks

def split_halves(classes, rng):
    """Two disjoint, equal-size, class-stratified sets of epoch indices."""
    half1, half2 = [], []
    for label in np.unique(classes):
        idx = rng.permutation(np.flatnonzero(classes == label))
        h = len(idx) // 2
        half1 += idx[:h].tolist()
        half2 += idx[h:2 * h].tolist()
    return np.sort(half1), np.sort(half2)


def edge_status_map(ext, bads, interpolated, ccfg):
    """Step 4 edge rules: None = usable."""
    unavailable = {c for a, b in ccfg["homologous_pairs"] if a in interpolated and b in interpolated for c in (a, b)}
    return {e: cv.edge_status(*e, bads, unavailable, interpolated)[0] for e in cv.edge_list(ext)}


def connectivity_row(data, sfreq, ext, usable, ccfg):
    """Step 4 connectivity for the given epochs -> {wpli_<band>_<A>-<B>: value} (NaN for unusable edges)."""
    bands = list(ccfg["bands"])
    row = {f"wpli_{b}_{a}-{c}": float("nan") for a, c in cv.edge_list(ext) for b in bands}
    if usable:
        idx = {ch: i for i, ch in enumerate(ext)}
        values = cv.wpli(cv.make_segments(data, ccfg), sfreq, [idx[a] for a, _ in usable],
                         [idx[c] for _, c in usable], ccfg)
        for (a, c), v in zip(usable, values):
            for j, b in enumerate(bands):
                row[f"wpli_{b}_{a}-{c}"] = float(v[j])
    return row


def half_differences(row, band, set_cfg, node_ok, avail, summaries):
    """Raw L - R differences on clipped, masked weights: edge vector, node-strength vector, network summaries."""
    wl, wr, _ = gr.hemisphere_matrices(row, band, set_cfg)
    a, b = gr.masked_clipped(wl, avail), gr.masked_clipped(wr, avail)
    iu = np.triu_indices(len(a), 1)
    sel = avail[iu]
    d_edge = (a - b)[iu][sel]
    ma, mb = gr.node_metrics(a, a, avail, node_ok), gr.node_metrics(b, b, avail, node_ok)
    d_node = (ma["strength"] - mb["strength"])[node_ok]
    net = {"mean_weight": float(a[iu][sel].mean() - b[iu][sel].mean()) if sel.any() else float("nan"),
           "mean_strength": gr.safe_nanmean(ma["strength"][node_ok]) - gr.safe_nanmean(mb["strength"][node_ok]),
           "glob_eff": gr.global_efficiency(a, avail, node_ok) - gr.global_efficiency(b, avail, node_ok),
           "mean_clust": gr.safe_nanmean(ma["clustering"][node_ok]) - gr.safe_nanmean(mb["clustering"][node_ok])}
    return d_edge, d_node, {m: net[m] for m in summaries}


def cross_products(h1, h2):
    """Cross-half products (no noise term in expectation) and signed means for one split."""
    (e1, n1, m1), (e2, n2, m2) = h1, h2
    out = {"D2_edge": float(np.mean(e1 * e2)) if len(e1) else float("nan"),
           "D2_node": float(np.mean(n1 * n2)) if len(n1) else float("nan")}
    for k in m1:
        out[f"D2_{k}"] = m1[k] * m2[k]
        out[f"signed_{k}"] = (m1[k] + m2[k]) / 2
    return out


def naive_products(h):
    """Full-data squared differences (include the estimation-noise variance)."""
    e, n, m = h
    out = {"D2_edge": float(np.mean(e ** 2)) if len(e) else float("nan"),
           "D2_node": float(np.mean(n ** 2)) if len(n) else float("nan")}
    out.update({f"D2_{k}": v ** 2 for k, v in m.items()})
    return out


def subject_seed(subject, cfg):
    return cfg["splits"]["seed_base"] + int(subject.split("-")[1]) - 1


# ---------------------------------------------------------------- per subject

def split_names(value):
    return [x for x in str(value if isinstance(value, str) else "").split(";") if x]


def process_subject(subject, epochs_path, qc_row, cfg, ccfg, gcfg):
    ext = ccfg["channel_sets"]["extended"]
    epochs = mne.read_epochs(epochs_path, preload=True, verbose="ERROR")
    missing = [c for c in ext if c not in epochs.ch_names]
    if missing:
        raise ValueError(f"Channels missing from epochs: {missing}")
    data = epochs.get_data(picks=[epochs.ch_names.index(c) for c in ext])  # integer picks keep bad channels
    sfreq, classes = epochs.info["sfreq"], epochs.events[:, 2]
    interpolated = set(split_names(qc_row.get("interpolated"))) | set(split_names(qc_row.get("screen_interpolated")))
    status = edge_status_map(ext, set(epochs.info["bads"]), interpolated, ccfg)
    usable = [e for e, s in status.items() if s is None]

    full_row = connectivity_row(data, sfreq, ext, usable, ccfg)
    rng = np.random.default_rng(subject_seed(subject, cfg))
    splits = [split_halves(classes, rng) for _ in range(cfg["splits"]["n_splits"])]
    halves = [(connectivity_row(data[h1], sfreq, ext, usable, ccfg), connectivity_row(data[h2], sfreq, ext, usable, ccfg))
              for h1, h2 in splits]
    usable_keys = [f"wpli_{b}_{a}-{c}" for a, c in usable for b in ccfg["bands"]]
    nonfinite = sum(int(not np.isfinite(r[k])) for pair in halves for r in pair for k in usable_keys)

    summaries = cfg["network_summaries"]
    values = {}
    for s, sc in gcfg["sets"].items():
        for band in gcfg["bands"]:
            node_ok, avail = gr.symmetric_mask(*gr.hemisphere_matrices(full_row, band, sc))
            naive = naive_products(half_differences(full_row, band, sc, node_ok, avail, summaries))
            per_split = [cross_products(half_differences(r1, band, sc, node_ok, avail, summaries),
                                        half_differences(r2, band, sc, node_ok, avail, summaries)) for r1, r2 in halves]
            for k in per_split[0]:
                vals = [p[k] for p in per_split]
                values[f"{s}_{band}_{k}"] = float(np.nanmean(vals)) if np.isfinite(vals).any() else float("nan")
            for k, v in naive.items():
                values[f"{s}_{band}_naive_noiseinflated_{k}"] = v
    return {"values": values, "n_epochs": len(epochs), "n_segments": int(len(epochs) * ccfg["segments"]["per_epoch"]),
            "half_epochs": int(len(splits[0][0])), "n_nonfinite_half_values": nonfinite,
            "epochs_sha256": sha256_file(epochs_path)}


def run_subject(subject, epochs_path, qc_row, cfg, ccfg, gcfg, config_sha, result_path):
    start = time.time()
    try:
        result = {"status": "ok", **process_subject(subject, epochs_path, qc_row, cfg, ccfg, gcfg)}
    except Exception as exc:  # recorded per subject; the cohort run continues
        result = {"status": "error", "error": repr(exc), "traceback": traceback.format_exc()}
    result.update(subject_id=subject, config_sha256=config_sha, seconds=round(time.time() - start, 1))
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result) + "\n", encoding="utf-8")
    return result


def is_done(path, config_sha):
    if not path.exists():
        return False
    r = json.loads(path.read_text(encoding="utf-8"))
    return r.get("status") == "ok" and r.get("config_sha256") == config_sha


# ---------------------------------------------------------------- table

def columns(cfg, gcfg):
    ms = cfg["network_summaries"]
    cols = []
    for s in gcfg["sets"]:
        for b in gcfg["bands"]:
            cols += [f"{s}_{b}_D2_edge", f"{s}_{b}_D2_node"] + [f"{s}_{b}_D2_{m}" for m in ms]
            cols += [f"{s}_{b}_signed_{m}_{k}" for m in ms for k in ("LR", "IC")]
            cols += [f"{s}_{b}_naive_noiseinflated_D2_edge", f"{s}_{b}_naive_noiseinflated_D2_node"]
            cols += [f"{s}_{b}_naive_noiseinflated_D2_{m}" for m in ms]
    return cols + ["core_D2_edge_allbands", "core_D2_node_allbands"]


def build_table(results, signs, cfg, gcfg):
    rows = []
    for r in results:
        v, sign = dict(r["values"]), signs.get(r["subject_id"])
        row = {"subject_id": r["subject_id"]}
        for s in gcfg["sets"]:
            for b in gcfg["bands"]:
                for m in cfg["network_summaries"]:
                    lr = v.pop(f"{s}_{b}_signed_{m}")
                    v[f"{s}_{b}_signed_{m}_LR"] = lr
                    v[f"{s}_{b}_signed_{m}_IC"] = sign * lr if sign is not None else float("nan")
        row.update(v)
        row["core_D2_edge_allbands"] = gr.safe_nanmean([v[f"core_{b}_D2_edge"] for b in gcfg["bands"]])
        row["core_D2_node_allbands"] = gr.safe_nanmean([v[f"core_{b}_D2_node"] for b in gcfg["bands"]])
        rows.append(row)
    cols = columns(cfg, gcfg)
    df = pd.DataFrame(rows).reindex(columns=["subject_id", *cols])
    if FORBIDDEN & {c.casefold() for c in df.columns}:
        raise RuntimeError("Outcome column in a feature table")
    if np.isinf(df[cols].to_numpy(dtype=float)).any():
        raise RuntimeError("Infinite cross-half values")
    return df, cols


def summarise(df, qc, gcfg):
    out = {}
    merged = df.merge(qc[["subject_id", "n_segments"]], on="subject_id")
    for s in gcfg["sets"]:
        for b in gcfg["bands"]:
            for level in ("edge", "node"):
                x, naive = df[f"{s}_{b}_D2_{level}"], df[f"{s}_{b}_naive_noiseinflated_D2_{level}"]
                ok = x.notna() & naive.notna()
                out[f"{s}_{b}_D2_{level}"] = {
                    "median": float(x.median()), "q1": float(x.quantile(.25)), "q3": float(x.quantile(.75)),
                    "share_gt_0": float((x > 0).mean()), "naive_median": float(naive.median()),
                    "median_ratio_cross_to_naive": float((x[ok] / naive[ok]).median()),
                    "spearman_cross_vs_naive": float(spearmanr(x[ok], naive[ok]).statistic),
                    "rho_n_segments": float(spearmanr(merged[f"{s}_{b}_D2_{level}"], merged["n_segments"], nan_policy="omit").statistic),
                    "rho_n_segments_naive": float(spearmanr(merged[f"{s}_{b}_naive_noiseinflated_D2_{level}"], merged["n_segments"], nan_policy="omit").statistic)}
    return out


# ---------------------------------------------------------------- main

def main(argv=None):
    parser = add_root_args(argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter))
    parser.add_argument("--subjects", nargs="*")
    parser.add_argument("--n-jobs", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    roots = roots_from_args(args)
    cfg, config_path = load_config(CONFIG)
    ccfg, ccfg_path = load_config(cfg["reuse"]["connectivity_config"])
    gcfg, gcfg_path = load_config(cfg["reuse"]["graph_config"])
    config_sha = "|".join(sha256_file(p) for p in (config_path, ccfg_path, gcfg_path))
    inp = cfg["inputs"]

    qc_in = pd.read_csv(roots.prev_path(inp["epoch_qc"]), usecols=inp["epoch_qc_columns"])
    included = qc_in[qc_in["include_v3_epochs"].astype(str) == "True"]
    if args.subjects:
        included = included[included["subject_id"].isin(args.subjects)]
    rows = {r["subject_id"]: r.to_dict() for _, r in included.iterrows()}
    paths = {s: roots.prev_path(inp["epochs_dir"]) / inp["epoch_template"].format(subject=s) for s in rows}
    missing = [s for s, p in paths.items() if not p.exists()]
    if missing:
        raise SystemExit(f"Epoch files missing under {roots.prev_path(inp['epochs_dir'])}: {missing}")
    subject_dir = roots.out_path(cfg["outputs"]["subject_dir"])
    result_paths = {s: subject_dir / f"{s}.json" for s in rows}
    todo = [s for s in rows if args.force or not is_done(result_paths[s], config_sha)]
    print(f"Step 7b: {len(rows)} subjects, {len(rows) - len(todo)} already done, {len(todo)} to run", flush=True)
    Parallel(n_jobs=args.n_jobs or cfg["n_jobs"], verbose=5)(
        delayed(run_subject)(s, paths[s], rows[s], cfg, ccfg, gcfg, config_sha, result_paths[s]) for s in todo)

    results = [json.loads(result_paths[s].read_text(encoding="utf-8")) for s in sorted(rows)]
    failed = [{"subject_id": r["subject_id"], "error": r["error"]} for r in results if r["status"] != "ok"]
    ok = [r for r in results if r["status"] == "ok"]
    if not ok:
        raise SystemExit(f"No subject succeeded: {failed}")

    signs = gr.lesion_signs(roots.prev_path(inp["subject_meta"]), gcfg)
    df, cols = build_table(ok, signs, cfg, gcfg)
    outs = {k: roots.out_path(v) for k, v in cfg["outputs"].items()}
    outs["csv"].parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(outs["csv"], index=False)
    qc = pd.DataFrame([{"subject_id": r["subject_id"], "n_epochs": r["n_epochs"], "n_segments": r["n_segments"],
                        "half_epochs": r["half_epochs"], "n_nonfinite_half_values": r["n_nonfinite_half_values"],
                        "seconds": r["seconds"]} for r in ok])
    outs["qc_csv"].parent.mkdir(parents=True, exist_ok=True)
    qc.to_csv(outs["qc_csv"], index=False)
    hashes = {"crosshalf": sha256_file(config_path), "connectivity": sha256_file(ccfg_path), "graph": sha256_file(gcfg_path)}
    write_with_config(outs["meta"], {"table": display_path(outs["csv"], roots.out), "table_sha256": sha256_file(outs["csv"]),
                                     "n_rows": len(df), "columns": ["subject_id", *cols], "estimator": cfg["estimator"],
                                     "splits": cfg["splits"], "mask_rule": cfg["mask_rule"],
                                     "network_summary_rule": cfg["network_summary_rule"],
                                     "label_note": "naive_noiseinflated_* columns and the Step 7 unsigned summaries are noise-inflated, descriptive only",
                                     "config_sha256_all": hashes,
                                     "inputs": {"epochs_sha256": {r["subject_id"]: r["epochs_sha256"] for r in ok},
                                                "subject_meta_sha256": sha256_file(roots.prev_path(inp["subject_meta"]))}},
                      config_path, sources=[Path(__file__)], roots=roots)
    summary = {"n_subjects_ok": len(ok), "failed_subjects": failed, "n_columns": len(cols),
               "n_lesion_aligned": int(sum(signs.get(r["subject_id"]) is not None for r in ok)),
               "half_epochs": {"min": int(qc["half_epochs"].min()), "median": float(qc["half_epochs"].median()),
                               "max": int(qc["half_epochs"].max())},
               "n_nonfinite_half_values_total": int(qc["n_nonfinite_half_values"].sum()),
               "seconds_per_subject_median": float(qc["seconds"].median()),
               "D2": summarise(df, qc, gcfg), "no_outcome_read": True}
    write_with_config(outs["summary_json"], {"summary": summary}, config_path, sources=[Path(__file__)], roots=roots)
    print(f"Step 7b: {len(ok)} ok, failed: {failed or 'none'}; epochs per half {summary['half_epochs']}")
    for b in gcfg["bands"]:
        d = summary["D2"][f"core_{b}_D2_edge"]
        print(f"  core {b:6s} D2_edge median {d['median']:.2e} (naive {d['naive_median']:.2e}), share>0 {d['share_gt_0']:.2f}, "
              f"rho_segments {d['rho_n_segments']:.2f} (naive {d['rho_n_segments_naive']:.2f})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
