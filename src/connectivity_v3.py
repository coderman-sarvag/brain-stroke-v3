"""Step 4: functional connectivity (wpli2_debiased) between all channel pairs, with a surrogate noise-floor check.

Per included subject (features/v3/epoch_qc_v3.csv): every clean 4 s epoch is split into two 2 s segments; all
segments (both classes pooled, D16) feed mne_connectivity.spectral_connectivity_epochs(method="wpli2_debiased",
mode="multitaper", faverage=True) per band, for all edges of the 22-channel extended set (the core 8-channel edges
are the same values). Edges touching an unavailable channel, a doubly-interpolated homologous pair (D14), or two
interpolated channels are NaN; edges with one interpolated endpoint are flagged. Raw (possibly negative) values are
stored; Step 5 clips negatives for graph metrics and the negative fraction is recorded here.

Noise floor: per subject, 200 surrogates pair left-hemisphere segments with deranged right-hemisphere segments and
recompute the homologous edges; the observed homotopic values are compared with the subject's 95th percentile.

Resumable per subject (results/v3/step4/subjects/*.json, keyed by config hash). Label-free: reads only epoch_qc.
Run from the repo root: python src/connectivity_v3.py --prev-root <Step 2 out-root> [--out-root O] [--subjects ...]
"""
import argparse
import json
from pathlib import Path
import sys
import time
import traceback
import warnings

import mne
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths_v3 import add_root_args, roots_from_args  # noqa: E402
from provenance_v3 import display_path, load_config, sha256_file, write_with_config  # noqa: E402

CONFIG = "configs/v3/connectivity.json"
FORBIDDEN = {"nihss_raw", "severity_class", "nihss", "mbi", "mrs"}


# ---------------------------------------------------------------- building blocks

def subject_index(subject):
    return int(subject.split("-")[1]) - 1


def split_names(value):
    return [x for x in str(value if isinstance(value, str) else "").split(";") if x]


def make_segments(data, cfg):
    """(n_epochs, n_channels, 2000) -> (n_epochs * 2, n_channels, 1000), segments of one epoch kept adjacent."""
    seg = cfg["segments"]
    n_ep, n_ch, n_t = data.shape
    if n_t != seg["length_samples"] * seg["per_epoch"]:
        raise ValueError(f"Epoch length {n_t} is not {seg['per_epoch']} x {seg['length_samples']} samples")
    parts = data.reshape(n_ep, n_ch, seg["per_epoch"], seg["length_samples"]).transpose(0, 2, 1, 3)
    return parts.reshape(n_ep * seg["per_epoch"], n_ch, seg["length_samples"])


def band_limits(cfg):
    off = cfg["band_upper_offset_hz"]
    return (tuple(lo for lo, _ in cfg["bands"].values()), tuple(hi - off for _, hi in cfg["bands"].values()))


def bins_per_band(sfreq, n_times, cfg):
    freqs = np.fft.rfftfreq(n_times, 1.0 / sfreq)
    fmin, fmax = band_limits(cfg)
    return {b: int(((freqs >= lo) & (freqs <= hi)).sum()) for b, lo, hi in zip(cfg["bands"], fmin, fmax)}


def wpli(segments, sfreq, rows, cols, cfg):
    """wpli2_debiased per band for the given edges -> (n_edges, n_bands)."""
    from mne_connectivity import spectral_connectivity_epochs
    c = cfg["connectivity"]
    fmin, fmax = band_limits(cfg)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # 5-cycle warning for delta on 2 s segments (documented)
        con = spectral_connectivity_epochs(
            segments, method=c["method"], indices=(np.asarray(rows), np.asarray(cols)), sfreq=sfreq, mode=c["mode"],
            fmin=fmin, fmax=fmax, faverage=c["faverage"], mt_bandwidth=c["mt_bandwidth_hz"],
            mt_adaptive=c["mt_adaptive"], mt_low_bias=c["mt_low_bias"], n_jobs=1, verbose="ERROR")
    values = np.asarray(con.get_data())
    if values.shape != (len(rows), len(cfg["bands"])):
        raise RuntimeError(f"Unexpected connectivity shape {values.shape}")
    return values


def edge_list(channels):
    return [(a, b) for i, a in enumerate(channels) for b in channels[i + 1:]]


def edge_name(a, b):
    return f"{a}-{b}"


def edge_status(a, b, bads, unavailable, interpolated):
    """(status, n_interpolated_endpoints); status None means usable."""
    if a in bads or b in bads:
        return "unavailable_channel", None
    if a in unavailable or b in unavailable:
        return "pair_both_interpolated", None
    n_interp = int(a in interpolated) + int(b in interpolated)
    if n_interp == 2:
        return "both_endpoints_interpolated", 2
    return None, n_interp


def derangement(rng, n):
    """Random permutation with no fixed point (n >= 2)."""
    while True:
        perm = rng.permutation(n)
        if not np.any(perm == np.arange(n)):
            return perm


def surrogate_homotopic(segments, sfreq, idx, pairs, cfg, seed):
    """(n_surrogates, n_pairs, n_bands) wpli2_debiased with right-channel segments deranged."""
    s = cfg["surrogates"]
    rng = np.random.default_rng(seed)
    left = [idx[a] for a, _ in pairs]
    right = [idx[b] for _, b in pairs]
    compact = segments[:, left + right, :]
    k = len(pairs)
    rows, cols = list(range(k)), list(range(k, 2 * k))
    out = np.empty((s["n"], k, len(cfg["bands"])))
    for i in range(s["n"]):
        perm = derangement(rng, compact.shape[0])
        surr = compact.copy()
        surr[:, k:, :] = compact[perm][:, k:, :]
        out[i] = wpli(surr, sfreq, rows, cols, cfg)
    return out


def homotopic_summary(observed, surr, pair_names, bands, percentile):
    """Per pair and for the mean over pairs: observed value, subject's surrogate percentile, exceedance."""
    rows = []
    p_pair = np.percentile(surr, percentile, axis=0)              # (n_pairs, n_bands)
    p_mean = np.percentile(surr.mean(axis=1), percentile, axis=0)  # (n_bands,)
    obs_mean = observed.mean(axis=0)
    for j, band in enumerate(bands):
        for i, name in enumerate(pair_names):
            rows.append({"pair": name, "band": band, "observed": float(observed[i, j]),
                         "surrogate_p": float(p_pair[i, j]), "exceeds": bool(observed[i, j] > p_pair[i, j])})
        rows.append({"pair": "MEAN", "band": band, "observed": float(obs_mean[j]),
                     "surrogate_p": float(p_mean[j]), "exceeds": bool(obs_mean[j] > p_mean[j])})
    return rows


# ---------------------------------------------------------------- per subject

def process_subject(subject, epochs_path, qc_row, cfg):
    sets = cfg["channel_sets"]
    ext, core = sets["extended"], set(sets["core"])
    epochs = mne.read_epochs(epochs_path, preload=True, verbose="ERROR")
    missing = [c for c in ext if c not in epochs.ch_names]
    if missing:
        raise ValueError(f"Channels missing from epochs: {missing}")
    data = epochs.get_data(picks=[epochs.ch_names.index(c) for c in ext])  # integer picks keep bad channels
    segments = make_segments(data, cfg)
    sfreq = epochs.info["sfreq"]
    bands = list(cfg["bands"])

    bads = set(epochs.info["bads"])
    interpolated = set(split_names(qc_row.get("interpolated"))) | set(split_names(qc_row.get("screen_interpolated")))
    unavailable = {c for a, b in cfg["homologous_pairs"] if a in interpolated and b in interpolated for c in (a, b)}
    idx = {c: i for i, c in enumerate(ext)}

    edges = edge_list(ext)
    status = {e: edge_status(*e, bads, unavailable, interpolated) for e in edges}
    usable = [e for e in edges if status[e][0] is None]
    values = {e: [float("nan")] * len(bands) for e in edges}
    if usable:
        con = wpli(segments, sfreq, [idx[a] for a, _ in usable], [idx[b] for _, b in usable], cfg)
        for e, v in zip(usable, con):
            values[e] = [float(x) for x in v]

    flags = [{"subject_id": subject, "edge": edge_name(*e), "in_core": e[0] in core and e[1] in core,
              "status": status[e][0] or "ok", "n_interpolated_endpoints": status[e][1]} for e in edges]

    negative = {}
    for set_name, members in (("ext", set(ext)), ("core", core)):
        arr = np.array([values[e] for e in usable if e[0] in members and e[1] in members])
        for j, band in enumerate(bands):
            negative[f"{set_name}_{band}"] = float((arr[:, j] < 0).mean()) if len(arr) else float("nan")

    homotopic = {}
    pairs_ok = [tuple(p) for p in cfg["homologous_pairs"] if status[tuple(p)][0] is None]
    if pairs_ok:
        surr = surrogate_homotopic(segments, sfreq, idx, pairs_ok, cfg,
                                   cfg["surrogates"]["seed_base"] + subject_index(subject))
        observed = np.array([values[p] for p in pairs_ok])
        names = [edge_name(*p) for p in pairs_ok]
        homotopic["ext"] = homotopic_summary(observed, surr, names, bands, cfg["surrogates"]["percentile"])
        core_sel = [i for i, p in enumerate(pairs_ok) if list(p) in cfg["core_pairs"]]
        if core_sel:
            homotopic["core"] = homotopic_summary(observed[core_sel], surr[:, core_sel], [names[i] for i in core_sel],
                                                  bands, cfg["surrogates"]["percentile"])
    classes = epochs.events[:, 2]
    return {"n_epochs": len(epochs), "n_segments": int(segments.shape[0]),
            "n_left": int((classes == epochs.event_id["left_hand"]).sum()),
            "n_right": int((classes == epochs.event_id["right_hand"]).sum()),
            "bins_per_band": bins_per_band(sfreq, segments.shape[-1], cfg),
            "edges": {edge_name(*e): values[e] for e in edges}, "flags": flags, "negative_fraction": negative,
            "homotopic": homotopic, "n_edges_nan": len(edges) - len(usable),
            "n_edges_one_interpolated": sum(1 for e in usable if status[e][1] == 1),
            "epochs_sha256": sha256_file(epochs_path)}


def run_subject(subject, epochs_path, qc_row, cfg, config_sha, result_path):
    start = time.time()
    try:
        result = {"status": "ok", **process_subject(subject, epochs_path, qc_row, cfg)}
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


# ---------------------------------------------------------------- aggregation

def feature_columns(channels, bands):
    return [f"wpli_{band}_{edge_name(*e)}" for band in bands for e in edge_list(channels)]


def feature_table(results, channels, bands):
    cols = feature_columns(channels, bands)
    rows = []
    for r in results:
        row = {"subject_id": r["subject_id"]}
        for j, band in enumerate(bands):
            for e in edge_list(channels):
                row[f"wpli_{band}_{edge_name(*e)}"] = r["edges"][edge_name(*e)][j]
        rows.append(row)
    return pd.DataFrame(rows)[["subject_id", *cols]], cols


def check_table(df, cols):
    if list(df.columns) != ["subject_id", *cols]:
        raise RuntimeError("Feature table columns do not match the declared contract")
    if FORBIDDEN & {c.casefold() for c in df.columns}:
        raise RuntimeError("Outcome column in a feature table")
    if np.isinf(df[cols].to_numpy(dtype=float)).any():
        raise RuntimeError("Infinite connectivity values")


def write_table(df, cols, csv_path, meta_path, description, cfg, config_path, roots, inputs):
    check_table(df, cols)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    nan_by_subject = {r["subject_id"]: int(pd.isna(r[cols]).sum()) for _, r in df.iterrows() if pd.isna(r[cols]).any()}
    write_with_config(meta_path, {"table": display_path(csv_path, roots.out), "table_sha256": sha256_file(csv_path),
                                  "n_rows": len(df), "columns": ["subject_id", *cols], "description": description,
                                  "estimator": cfg["connectivity"], "segments": cfg["segments"]["rule"],
                                  "missing_rule": cfg["missing_rule"], "clipping": cfg["clipping"],
                                  "nan_cells_by_subject": nan_by_subject, "inputs": inputs},
                      config_path, sources=[Path(__file__)], roots=roots)


def correlation_summary(table, cols, n_segments):
    merged = table.merge(n_segments, on="subject_id")
    rhos = {}
    for c in cols:
        ok = merged[c].notna()
        if ok.sum() >= 5 and merged.loc[ok, c].nunique() > 1:
            rhos[c] = float(spearmanr(merged.loc[ok, c], merged.loc[ok, "n_segments"]).statistic)
    a = pd.Series(rhos).abs()
    return {"n_features": int(len(a)), "median_abs_rho": float(a.median()) if len(a) else None,
            "max_abs_rho": float(a.max()) if len(a) else None, "feature_max": a.idxmax() if len(a) else None,
            "n_abs_ge_0.3": int((a >= 0.3).sum())}


def aggregate(results, cfg, config_path, roots, failed):
    bands = list(cfg["bands"])
    outs = {k: roots.out_path(v) for k, v in cfg["outputs"].items()}
    inputs = {"epochs_sha256": {r["subject_id"]: r["epochs_sha256"] for r in results}}
    core, core_cols = feature_table(results, cfg["channel_sets"]["core"], bands)
    ext, ext_cols = feature_table(results, cfg["channel_sets"]["extended"], bands)
    write_table(core, core_cols, outs["core_csv"], outs["core_meta"], "wpli2_debiased, core 8 channels (28 edges) x 4 bands",
                cfg, config_path, roots, inputs)
    write_table(ext, ext_cols, outs["ext_csv"], outs["ext_meta"], "wpli2_debiased, extended 22 channels (231 edges) x 4 bands",
                cfg, config_path, roots, inputs)

    pd.DataFrame([f for r in results for f in r["flags"]]).to_csv(outs["edge_flags_csv"], index=False)
    qc = pd.DataFrame([{"subject_id": r["subject_id"], "n_epochs": r["n_epochs"], "n_segments": r["n_segments"],
                        "n_left": r["n_left"], "n_right": r["n_right"], "n_edges_nan": r["n_edges_nan"],
                        "n_edges_one_interpolated": r["n_edges_one_interpolated"], "seconds": r["seconds"],
                        **{f"negfrac_{k}": v for k, v in r["negative_fraction"].items()}} for r in results])
    qc.to_csv(outs["qc_csv"], index=False)
    surr = pd.DataFrame([{"subject_id": r["subject_id"], "set": s, **row}
                         for r in results for s, rows in r["homotopic"].items() for row in rows])
    surr.to_csv(outs["surrogate_csv"], index=False)

    floor = {}
    for s in ("ext", "core"):
        means = surr[(surr["set"] == s) & (surr["pair"] == "MEAN")]
        pairs = surr[(surr["set"] == s) & (surr["pair"] != "MEAN")]
        floor[s] = {band: {"n_subjects": int((means["band"] == band).sum()),
                           "frac_subjects_mean_homotopic_exceeds_p95": float(means.loc[means["band"] == band, "exceeds"].mean()),
                           "frac_subject_pairs_exceeding_p95": float(pairs.loc[pairs["band"] == band, "exceeds"].mean()),
                           "median_observed_mean_homotopic": float(means.loc[means["band"] == band, "observed"].median()),
                           "median_subject_p95_of_mean": float(means.loc[means["band"] == band, "surrogate_p"].median())}
                    for band in bands}
    nseg = qc[["subject_id", "n_segments"]]
    homo = surr[surr["pair"] == "MEAN"].pivot_table(index="subject_id", columns=["set", "band"], values="observed")
    homo.columns = [f"homotopic_mean_{s}_{b}" for s, b in homo.columns]
    homo = homo.reset_index()
    summary = {"n_subjects_ok": len(results), "failed_subjects": failed, "no_labels_read": True,
               "bins_per_band": results[0]["bins_per_band"],
               "n_segments": {"min": int(qc["n_segments"].min()), "median": float(qc["n_segments"].median()),
                              "max": int(qc["n_segments"].max())},
               "subjects_with_nan_edges": qc.loc[qc["n_edges_nan"] > 0, ["subject_id", "n_edges_nan"]].values.tolist(),
               "n_subjects_with_one_interpolated_edges": int((qc["n_edges_one_interpolated"] > 0).sum()),
               "negative_fraction_median": {c[len("negfrac_"):]: float(qc[c].median()) for c in qc.columns if c.startswith("negfrac_")},
               "negative_fraction_max": {c[len("negfrac_"):]: float(qc[c].max()) for c in qc.columns if c.startswith("negfrac_")},
               "noise_floor": floor,
               "segment_count_correlation": {
                   "core_edges": correlation_summary(core, core_cols, nseg),
                   "ext_edges": correlation_summary(ext, ext_cols, nseg),
                   "homotopic_means": {c: float(spearmanr(m[c], m["n_segments"], nan_policy="omit").statistic)
                                       for m in [homo.merge(nseg, on="subject_id")] for c in homo.columns if c != "subject_id"}},
               "seconds_per_subject_median": float(qc["seconds"].median())}
    write_with_config(outs["summary_json"], {"summary": summary}, config_path, sources=[Path(__file__)], roots=roots)
    return summary


def short_summary(summary):
    lines = [f"Step 4: {summary['n_subjects_ok']} subjects ok, failed: {summary['failed_subjects'] or 'none'}",
             f"segments per subject: {summary['n_segments']}; bins per band: {summary['bins_per_band']}",
             "noise floor (fraction of subjects whose mean homotopic wPLI > own 95th-pct surrogate):"]
    for s in ("ext", "core"):
        lines.append(f"  {s}: " + ", ".join(f"{b} {v['frac_subjects_mean_homotopic_exceeds_p95']:.2f}"
                                            for b, v in summary["noise_floor"][s].items()))
    lines.append("negative-edge fraction (median, ext): " + ", ".join(
        f"{k.split('_')[1]} {v:.2f}" for k, v in summary["negative_fraction_median"].items() if k.startswith("ext_")))
    sc = summary["segment_count_correlation"]
    lines.append(f"segment-count |rho| >= .3: core {sc['core_edges']['n_abs_ge_0.3']}/{sc['core_edges']['n_features']}, "
                 f"ext {sc['ext_edges']['n_abs_ge_0.3']}/{sc['ext_edges']['n_features']}")
    return "\n".join(lines)


# ---------------------------------------------------------------- main

def main(argv=None):
    parser = add_root_args(argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter))
    parser.add_argument("--subjects", nargs="*")
    parser.add_argument("--n-jobs", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="recompute subjects that already have results")
    args = parser.parse_args(argv)
    roots = roots_from_args(args)
    cfg, config_path = load_config(CONFIG)
    config_sha = sha256_file(config_path)
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
    print(f"Step 4: {len(rows)} subjects, {len(rows) - len(todo)} already done, {len(todo)} to run", flush=True)
    Parallel(n_jobs=args.n_jobs or cfg["n_jobs"], verbose=5)(
        delayed(run_subject)(s, paths[s], rows[s], cfg, config_sha, result_paths[s]) for s in todo)

    results = [json.loads(result_paths[s].read_text(encoding="utf-8")) for s in sorted(rows)]
    failed = [{"subject_id": r["subject_id"], "error": r["error"]} for r in results if r["status"] != "ok"]
    ok = [r for r in results if r["status"] == "ok"]
    if not ok:
        raise SystemExit(f"No subject succeeded: {failed}")
    summary = aggregate(ok, cfg, config_path, roots, failed)
    print(short_summary(summary), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
