"""Step 3: multi-band spectral asymmetry features from the Step 2 epochs (label-free).

Per included subject (features/v3/epoch_qc_v3.csv): multitaper PSD of every full 4 s epoch, band power per
channel, then per epoch and homologous pair AI = (L-R)/(L+R), LR = ln L - ln R and |AI|; per epoch mean |AI| over
pairs, pdBSI (1-25 Hz bins), DAR and DTABR. Each feature is averaged within each class and the subject value is the
mean of the two class means (class-balanced averaging). Unavailable or doubly-interpolated pairs are NaN.

The lesion-aligned table (ipsi - contra) is built by lesion_table(), the only code here that reads lesion side.
Outputs hold subject_id + features only; sidecars record columns, definitions, config hash and input hashes.

Step 3b (configs/v3/spectral_v3b.json, deviation D15): instead of per-epoch features, each class is summarised by
100 draws of exactly 10 epochs whose PSDs are averaged before any feature is computed (median over draws), so every
subject has the same, lower noise floor. The Step 3 config and outputs remain unchanged for comparison.

Run from the repo root: python src/spectral_v3.py --prev-root <Step 2 out-root> [--config C] [--out-root O]
"""
import argparse
import json
from pathlib import Path
import sys
import warnings

import mne
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths_v3 import add_root_args, roots_from_args  # noqa: E402
from provenance_v3 import display_path, load_config, sha256_file, write_with_config  # noqa: E402

CONFIG = "configs/v3/spectral.json"
FORBIDDEN = {"nihss_raw", "severity_class", "nihss", "mbi", "mrs"}


# ---------------------------------------------------------------- spectra

def pair_name(pair):
    return f"{pair[0]}{pair[1]}"


def compute_psd(data, sfreq, cfg):
    p = cfg["psd"]
    return mne.time_frequency.psd_array_multitaper(
        data, sfreq, fmin=p["fmin"], fmax=p["fmax"], bandwidth=p["bandwidth_hz"], adaptive=p["adaptive"],
        low_bias=p["low_bias"], normalization=p["normalization"], verbose="ERROR")


def band_masks(freqs, cfg):
    """Half-open band masks; refuses to continue if any band has fewer than the minimum number of bins."""
    masks = {b: (freqs >= lo) & (freqs < hi) for b, (lo, hi) in cfg["bands"].items()}
    short = {b: int(m.sum()) for b, m in masks.items() if m.sum() < cfg["min_bins_per_band"]}
    if short:
        raise ValueError(f"Bands with fewer than {cfg['min_bins_per_band']} PSD bins: {short}")
    return masks


def band_powers(psd, freqs, masks):
    """(epoch, channel, band) power = sum of PSD over band bins x bin width."""
    df = float(np.median(np.diff(freqs)))
    return np.stack([psd[..., m].sum(axis=-1) * df for m in masks.values()], axis=-1)


def pair_status(ch_names, bads, interpolated, pairs):
    """None = usable; otherwise the reason the pair is NaN."""
    status = {}
    for left, right in pairs:
        if left not in ch_names or right not in ch_names or left in bads or right in bads:
            status[pair_name((left, right))] = "unavailable"
        elif left in interpolated and right in interpolated:
            status[pair_name((left, right))] = "both_interpolated"
        else:
            status[pair_name((left, right))] = None
    return status


def feature_columns(cfg):
    cols = [f"{kind}_{band}_{pair_name(p)}" for band in cfg["bands"] for p in cfg["pairs"] for kind in ("AI", "LR", "absAI")]
    return cols + [f"mabsAI_{band}" for band in cfg["bands"]] + ["pdBSI", "DAR", "DTABR"]


def epoch_features(psd, freqs, ch_names, status, cfg):
    """Per-epoch feature vectors {column: (n_epochs,) array}."""
    masks = band_masks(freqs, cfg)
    bp = band_powers(psd, freqs, masks)
    n_ep, bands = psd.shape[0], list(cfg["bands"])
    idx = {c: i for i, c in enumerate(ch_names)}
    feats, abs_by_band, bsi = {}, {b: [] for b in bands}, []
    lo, hi = cfg["pdbsi_range_hz"]
    bsi_mask = (freqs >= lo) & (freqs < hi)
    for left, right in cfg["pairs"]:
        name = pair_name((left, right))
        if status[name] is not None:
            for band in bands:
                for kind in ("AI", "LR", "absAI"):
                    feats[f"{kind}_{band}_{name}"] = np.full(n_ep, np.nan)
            continue
        L, R = bp[:, idx[left], :], bp[:, idx[right], :]
        ai, lr = (L - R) / (L + R), np.log(L) - np.log(R)
        for k, band in enumerate(bands):
            feats[f"AI_{band}_{name}"] = ai[:, k]
            feats[f"LR_{band}_{name}"] = lr[:, k]
            feats[f"absAI_{band}_{name}"] = np.abs(ai[:, k])
            abs_by_band[band].append(np.abs(ai[:, k]))
        pl, pr = psd[:, idx[left], bsi_mask], psd[:, idx[right], bsi_mask]
        bsi.append(np.abs((pr - pl) / (pr + pl)).mean(axis=-1))
    for band in bands:
        feats[f"mabsAI_{band}"] = np.mean(abs_by_band[band], axis=0) if abs_by_band[band] else np.full(n_ep, np.nan)
    feats["pdBSI"] = np.mean(bsi, axis=0) if bsi else np.full(n_ep, np.nan)
    chans = [idx[c] for p in cfg["pairs"] if status[pair_name(p)] != "unavailable" for c in p]
    total = bp[:, chans, :].sum(axis=1) if chans else np.full((n_ep, len(bands)), np.nan)
    b = {name: total[:, k] for k, name in enumerate(bands)}
    feats["DAR"] = b["delta"] / b["alpha"]
    feats["DTABR"] = (b["delta"] + b["theta"]) / (b["alpha"] + b["beta"])
    return {c: feats[c] for c in feature_columns(cfg)}


def class_balanced(values, classes):
    """Mean of the per-class means (each class weighted equally regardless of its epoch count)."""
    labels = np.unique(classes)
    if len(labels) != 2:
        raise ValueError(f"Expected two classes, found {labels.tolist()}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN feature (unavailable pair) stays NaN
        means = [np.nanmean(values[classes == c]) for c in labels]
    return float(np.mean(means))


def subject_seed(subject, cfg):
    """42 + zero-based Figshare subject index (sub-01 -> 42), independent of which subjects are included."""
    return cfg["subsample"]["seed_base"] + int(subject.split("-")[1]) - 1


def subsampled_features(psd, freqs, ch_names, status, classes, cfg, seed):
    """Step 3b: per class, n_draws subsets of exactly n_per_class epochs (no replacement); features on each subset's
    averaged spectrum; median over draws; subject value = mean of the two class values."""
    ss = cfg["subsample"]
    labels = np.unique(classes)
    if len(labels) != 2:
        raise ValueError(f"Expected two classes, found {labels.tolist()}")
    rng = np.random.default_rng(seed)
    class_values = []
    for label in labels:  # sorted event codes: left_hand (1) first, then right_hand (2)
        idx = np.flatnonzero(classes == label)
        if len(idx) < ss["n_per_class"]:
            raise ValueError(f"Class {label} has {len(idx)} epochs, fewer than {ss['n_per_class']}")
        draws = np.stack([psd[rng.choice(idx, ss["n_per_class"], replace=ss["replace"])].mean(axis=0)
                          for _ in range(ss["n_draws"])])
        feats = epoch_features(draws, freqs, ch_names, status, cfg)
        class_values.append({k: float(np.median(v)) for k, v in feats.items()})  # NaN pair stays NaN
    return {k: float(np.mean([cv[k] for cv in class_values])) for k in class_values[0]}


def aggregate_subject(psd, freqs, ch_names, status, classes, subject, cfg):
    """Per-epoch features + class-balanced mean (Step 3), or subsampled averaged spectra (Step 3b)."""
    if cfg.get("aggregation_method", "per_epoch") == "per_epoch":
        feats = epoch_features(psd, freqs, ch_names, status, cfg)
        return {c: class_balanced(v, classes) for c, v in feats.items()}
    if cfg["aggregation_method"] == "subsampled_average_spectrum":
        return subsampled_features(psd, freqs, ch_names, status, classes, cfg, subject_seed(subject, cfg))
    raise ValueError(f"Unknown aggregation_method {cfg['aggregation_method']!r}")


# ---------------------------------------------------------------- per subject

def split_names(value):
    return [x for x in str(value if isinstance(value, str) else "").split(";") if x]


def subject_features(subject, epochs_path, qc_row, cfg):
    epochs = mne.read_epochs(epochs_path, preload=True, verbose="ERROR")
    eeg = epochs.copy().pick("eeg", exclude=[])
    psd, freqs = compute_psd(eeg.get_data(), eeg.info["sfreq"], cfg)
    interpolated = set(split_names(qc_row.get("interpolated"))) | set(split_names(qc_row.get("screen_interpolated")))
    status = pair_status(eeg.ch_names, set(eeg.info["bads"]), interpolated, cfg["pairs"])
    classes = epochs.events[:, 2]
    row = {"subject_id": subject, **aggregate_subject(psd, freqs, eeg.ch_names, status, classes, subject, cfg)}
    masks = band_masks(freqs, cfg)
    single = [pair_name(p) for p in cfg["pairs"] if status[pair_name(p)] is None and len(set(p) & interpolated) == 1]
    unavailable_bads = sorted(pair_name(p) for p in cfg["pairs"] if status[pair_name(p)] == "unavailable")
    qc_unavailable = sorted(pair_name(p.split("-")) for p in split_names(qc_row.get("unavailable_pairs_final"))
                            if p.split("-") in [list(q) for q in cfg["pairs"]])
    qc = {"subject_id": subject, "n_epochs": len(epochs),
          "n_left": int((classes == epochs.event_id["left_hand"]).sum()),
          "n_right": int((classes == epochs.event_id["right_hand"]).sum()),
          "pairs_unavailable": ";".join(unavailable_bads),
          "pairs_both_interpolated": ";".join(n for n, s in status.items() if s == "both_interpolated"),
          "pairs_one_interpolated": ";".join(single),
          "n_pairs_used": sum(s is None for s in status.values()),
          "unavailable_matches_epoch_qc": unavailable_bads == qc_unavailable,
          "bins_per_band": json.dumps({b: int(m.sum()) for b, m in masks.items()}),
          "aggregation_method": cfg.get("aggregation_method", "per_epoch"),
          "subsample_seed": subject_seed(subject, cfg) if "subsample" in cfg else "",
          "epochs_sha256": sha256_file(epochs_path)}
    return row, qc


# ---------------------------------------------------------------- lesion alignment (only reader of lesion side)

def lesion_table(features, meta_path, cfg):
    les = cfg["lesion"]
    meta = pd.read_csv(meta_path, usecols=cfg["inputs"]["subject_meta_columns_lesion_step_only"])
    sides = meta.set_index("subject_id")[les["column"]]
    rows = []
    for _, r in features.iterrows():
        side = sides.get(r["subject_id"])
        if side not in les["certain_sides"]:
            continue
        sign = 1.0 if side == "left" else -1.0  # ipsi - contra: L - R for a left lesion, R - L for a right lesion
        row = {"subject_id": r["subject_id"]}
        for band in cfg["bands"]:
            for p in cfg["pairs"]:
                n = pair_name(p)
                row[f"les_AI_{band}_{n}"] = sign * r[f"AI_{band}_{n}"]
                row[f"les_LR_{band}_{n}"] = sign * r[f"LR_{band}_{n}"]
        for band in cfg["bands"]:
            vals = [row[f"les_AI_{band}_{pair_name(p)}"] for p in cfg["pairs"]]
            row[f"les_meanAI_{band}"] = float(np.nanmean(vals)) if np.isfinite(vals).any() else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def lesion_columns(cfg):
    cols = [f"les_{kind}_{band}_{pair_name(p)}" for band in cfg["bands"] for p in cfg["pairs"] for kind in ("AI", "LR")]
    return cols + [f"les_meanAI_{band}" for band in cfg["bands"]]


# ---------------------------------------------------------------- QC helpers

def epoch_count_correlations(features, qc):
    merged = features.merge(qc[["subject_id", "n_epochs", "n_left", "n_right"]], on="subject_id")
    merged["n_min_class"] = merged[["n_left", "n_right"]].min(axis=1)
    out = {}
    for col in [c for c in features.columns if c != "subject_id"]:
        x = merged[col]
        ok = x.notna()
        if ok.sum() < 5 or x[ok].nunique() < 2:
            continue
        out[col] = {"rho_n_epochs": float(spearmanr(x[ok], merged.loc[ok, "n_epochs"]).statistic),
                    "rho_n_min_class": float(spearmanr(x[ok], merged.loc[ok, "n_min_class"]).statistic)}
    rhos = pd.DataFrame(out).T
    if rhos.empty:
        return {"note": "not computed: fewer than 5 subjects with varying values"}, rhos
    summary = {}
    for key in ("rho_n_epochs", "rho_n_min_class"):
        a = rhos[key].abs()
        summary[key] = {"median_abs": float(a.median()), "max_abs": float(a.max()), "feature_max": a.idxmax(),
                        "n_abs_ge_0.3": int((a >= 0.3).sum()), "n_features": int(len(a))}
    return summary, rhos


def check_table(df, expected_cols):
    if list(df.columns) != ["subject_id", *expected_cols]:
        raise RuntimeError("Feature table columns do not match the declared contract")
    if FORBIDDEN & {c.casefold() for c in df.columns}:
        raise RuntimeError("Outcome column in a feature table")
    values = df[expected_cols].to_numpy(dtype=float)
    if np.isinf(values).any():
        raise RuntimeError("Infinite feature values")


def write_table(df, cols, csv_path, meta_path, definitions, cfg, config_path, roots, inputs):
    check_table(df, cols)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    write_with_config(meta_path, {"table": display_path(csv_path, roots.out), "table_sha256": sha256_file(csv_path),
                                  "n_rows": len(df), "columns": ["subject_id", *cols], "definitions": definitions,
                                  "aggregation": cfg["aggregation"], "missing_rule": cfg["missing_rule"],
                                  "nan_counts": {c: int(n) for c, n in df[cols].isna().sum().items() if n},
                                  "inputs": inputs},
                      config_path, sources=[Path(__file__)], roots=roots)


# ---------------------------------------------------------------- main

def main(argv=None):
    parser = add_root_args(argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter))
    parser.add_argument("--subjects", nargs="*")
    parser.add_argument("--n-jobs", type=int, default=None)
    parser.add_argument("--config", default=CONFIG, help="spectral config (configs/v3/spectral_v3b.json for Step 3b)")
    args = parser.parse_args(argv)
    roots = roots_from_args(args)
    cfg, config_path = load_config(args.config)
    inp = cfg["inputs"]

    qc_in = pd.read_csv(roots.prev_path(inp["epoch_qc"]), usecols=inp["epoch_qc_columns"])
    if FORBIDDEN & {c.casefold() for c in qc_in.columns}:
        raise RuntimeError("Outcome column in epoch_qc input")
    included = qc_in[qc_in["include_v3_epochs"].astype(str) == "True"]
    if args.subjects:
        included = included[included["subject_id"].isin(args.subjects)]
    paths = {s: roots.prev_path(inp["epochs_dir"]) / inp["epoch_template"].format(subject=s) for s in included["subject_id"]}
    missing = [s for s, p in paths.items() if not p.exists()]
    if missing:
        raise SystemExit(f"Epoch files missing under {roots.prev_path(inp['epochs_dir'])}: {missing}")
    print(f"Step 3: {len(paths)} included subjects", flush=True)

    results = Parallel(n_jobs=args.n_jobs or cfg["n_jobs"], verbose=5)(
        delayed(subject_features)(s, paths[s], row.to_dict(), cfg) for s, row in included.set_index("subject_id", drop=False).iterrows())
    features = pd.DataFrame([r for r, _ in results]).sort_values("subject_id").reset_index(drop=True)
    qc = pd.DataFrame([q for _, q in results]).sort_values("subject_id").reset_index(drop=True)
    cols = feature_columns(cfg)
    features = features[["subject_id", *cols]]

    lesion = lesion_table(features, roots.prev_path(inp["subject_meta"]), cfg)
    les_cols = lesion_columns(cfg)
    lesion = lesion.reindex(columns=["subject_id", *les_cols])

    outs = {k: roots.out_path(v) for k, v in cfg["outputs"].items()}
    inputs = {"epoch_qc_sha256": sha256_file(roots.prev_path(inp["epoch_qc"])),
              "epochs_sha256": dict(zip(qc["subject_id"], qc["epochs_sha256"]))}
    write_table(features, cols, outs["features_csv"], outs["features_meta"], cfg["features"], cfg, config_path, roots, inputs)
    write_table(lesion, les_cols, outs["lesion_csv"], outs["lesion_meta"], {"lesion": cfg["lesion"]["rule"]}, cfg,
                config_path, roots, {**inputs, "subject_meta_sha256": sha256_file(roots.prev_path(inp["subject_meta"]))})
    outs["qc_csv"].parent.mkdir(parents=True, exist_ok=True)
    qc.to_csv(outs["qc_csv"], index=False)

    corr_summary, _ = epoch_count_correlations(features, qc)
    nan_expected = {(r.subject_id, p) for r in qc.itertuples() for p in
                    split_names(r.pairs_unavailable) + split_names(r.pairs_both_interpolated)}
    pair_cols = {pair_name(p): [c for c in cols if c.endswith("_" + pair_name(p))] for p in cfg["pairs"]}
    unexpected_nan = [[r["subject_id"], c] for _, r in features.iterrows() for p, pc in pair_cols.items()
                      for c in pc if pd.isna(r[c]) and (r["subject_id"], p) not in nan_expected]
    unexpected_nan += [[r["subject_id"], c] for _, r in features.iterrows()
                       for c in [*(f"mabsAI_{b}" for b in cfg["bands"]), "pdBSI", "DAR", "DTABR"] if pd.isna(r[c])]
    summary = {"config": args.config, "aggregation_method": cfg.get("aggregation_method", "per_epoch"),
               "subsample": cfg.get("subsample"),
               "pdBSI_range": {"min": float(features["pdBSI"].min()), "median": float(features["pdBSI"].median()),
                               "max": float(features["pdBSI"].max())},
               "n_subjects": len(features), "n_lesion_rows": len(lesion),
               "lesion_rows_excluded_uncertain_side": sorted(set(features["subject_id"]) - set(lesion["subject_id"])),
               "bins_per_band": json.loads(qc["bins_per_band"].iloc[0]),
               "bins_identical_all_subjects": bool(qc["bins_per_band"].nunique() == 1),
               "n_feature_columns": len(cols), "n_lesion_columns": len(les_cols),
               "all_non_nan_finite": True,  # write_table refuses infinite values
               "nan_pairs": sorted([list(x) for x in nan_expected]),
               "unexpected_nan": unexpected_nan,
               "subjects_pairs_one_interpolated": qc.loc[qc["pairs_one_interpolated"] != "", ["subject_id", "pairs_one_interpolated"]].values.tolist(),
               "unavailable_cross_check_ok": bool(qc["unavailable_matches_epoch_qc"].all()),
               "epoch_count_correlation": corr_summary,
               "no_labels_read": True}
    write_with_config(outs["summary_json"], {"summary": summary}, config_path, sources=[Path(__file__)], roots=roots)
    print(json.dumps(summary, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
