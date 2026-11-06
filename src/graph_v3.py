"""Steps 5-6: hemispheric networks, homologous pairing, deformation, and node / edge / network differences.

Inputs: Step 4 raw connectivity tables (core = primary, 4 nodes per side; extended = secondary, 11 nodes per side)
and edge flags (--prev-root); epoch_qc and lesion_side_final from Steps 1-2 (--meta-root). Lesion side is read only
in lesion_signs(), to set the sign of the ipsilesional-minus-contralesional (IC) frame.

Per subject, set and band: clip wPLI at 0, build the left graph and the mirror-aligned right graph (pair order),
apply SYMMETRIC masking (configs/v3/graph.json masking_rule), then compute node (strength, weighted local
efficiency, weighted clustering), edge (mirrored differences, homotopic weights), network (global efficiency, mean
clustering, mean strength) and deformation measures (normalized Frobenius, Laplacian spectral distance, signed
mean-weight difference). Kinds: LR (signed left/right), abs (|LR| = |IC|), IC (signed lesion-aligned; NaN when the
lesion side is uncertain). Region summaries use the extended set. Outputs hold subject_id + features only.

Run from the repo root: python src/graph_v3.py --prev-root <Step 4 out> --meta-root <Step 2 out> [--out-root O]
"""
import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.sparse.csgraph import shortest_path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths_v3 import add_root_args, roots_from_args  # noqa: E402
from provenance_v3 import display_path, load_config, sha256_file, write_with_config  # noqa: E402

CONFIG = "configs/v3/graph.json"
FORBIDDEN = {"nihss_raw", "severity_class", "nihss", "mbi", "mrs"}
NODE_METRICS = ("strength", "local_eff", "clustering")
NET_METRICS = ("glob_eff", "mean_clust", "mean_strength")
KINDS = ("LR", "abs", "IC")


# ---------------------------------------------------------------- small helpers

def norm_diff(a, b):
    """(a - b) / (a + b); 0 when a = b = 0; NaN when either is NaN."""
    a, b = float(a), float(b)
    if np.isnan(a) or np.isnan(b):
        return float("nan")
    if a == 0 and b == 0:
        return 0.0
    return (a - b) / (a + b)


def safe_nanmean(values):
    values = np.asarray(values, dtype=float)
    return float(np.nanmean(values)) if np.isfinite(values).any() else float("nan")


def pair_name(left, right):
    return f"{left}{right}"


def edge_value(row, band, a, b):
    """Raw wPLI for the undirected edge a-b, whichever order Step 4 used in the column name."""
    for x, y in ((a, b), (b, a)):
        key = f"wpli_{band}_{x}-{y}"
        if key in row:
            return float(row[key])
    raise KeyError(f"No connectivity column for edge {a}-{b} in band {band}")


# ---------------------------------------------------------------- Step 5: graphs, pairing, masking

def hemisphere_matrices(row, band, set_cfg):
    """Left graph, mirror-aligned right graph (pair order) and homotopic weights; raw values, NaN kept."""
    left, right = set_cfg["left"], set_cfg["right"]
    n = len(left)
    wl, wr = np.zeros((n, n)), np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            wl[i, j] = wl[j, i] = edge_value(row, band, left[i], left[j])
            wr[i, j] = wr[j, i] = edge_value(row, band, right[i], right[j])
    homo = np.array([edge_value(row, band, left[i], right[i]) for i in range(n)])
    return wl, wr, homo


def symmetric_mask(wl, wr, homo):
    """node_ok (pairs kept in both hemispheres) and E (mirrored edges available in both hemispheres)."""
    n = len(homo)
    off = ~np.eye(n, dtype=bool)
    has_l = np.array([np.any(~np.isnan(wl[i][off[i]])) for i in range(n)])
    has_r = np.array([np.any(~np.isnan(wr[i][off[i]])) for i in range(n)])
    node_ok = ~np.isnan(homo) & has_l & has_r
    avail = np.zeros((n, n), dtype=bool)
    for i in np.flatnonzero(node_ok):
        for j in np.flatnonzero(node_ok):
            if i != j:
                avail[i, j] = not (np.isnan(wl[i, j]) or np.isnan(wr[i, j]))
    return node_ok, avail


def masked_clipped(w, avail):
    return np.where(avail, np.clip(np.nan_to_num(w, nan=0.0), 0.0, None), 0.0)


# ---------------------------------------------------------------- Step 6: graph measures

def inverse_path_lengths(wn, avail, nodes):
    """1 / shortest path length (lengths 1/w) within the subgraph of `nodes`; 0 on the diagonal and if unreachable."""
    nodes = list(nodes)
    if len(nodes) < 2:
        return np.zeros((len(nodes), len(nodes)))
    sub = wn[np.ix_(nodes, nodes)]
    usable = avail[np.ix_(nodes, nodes)] & (sub > 0)
    lengths = np.zeros_like(sub)
    lengths[usable] = 1.0 / sub[usable]
    dist = shortest_path(lengths, method="D", directed=False)  # dense input: zeros are non-edges
    with np.errstate(divide="ignore"):
        inv = 1.0 / dist
    np.fill_diagonal(inv, 0.0)
    inv[~np.isfinite(inv)] = 0.0
    return inv


def node_metrics(w, wn, avail, node_ok):
    """Strength (raw clipped weights), weighted clustering and local efficiency (shared-scale weights)."""
    n = len(w)
    strength, clustering, local_eff = (np.full(n, np.nan) for _ in range(3))
    cube = np.cbrt(wn)
    for i in np.flatnonzero(node_ok):
        nb = np.flatnonzero(avail[i])
        strength[i] = w[i, nb].sum()
        k = len(nb)
        if k < 2:
            continue
        tot_c, tot_e = 0.0, 0.0
        inv = inverse_path_lengths(wn, avail, nb)
        for x, a in enumerate(nb):
            for y, b in enumerate(nb):
                if a != b:
                    tot_c += cube[i, a] * cube[i, b] * cube[a, b]
                    tot_e += np.cbrt(wn[i, a] * wn[i, b] * inv[x, y])
        clustering[i] = tot_c / (k * (k - 1))
        local_eff[i] = tot_e / (k * (k - 1))
    return {"strength": strength, "clustering": clustering, "local_eff": local_eff}


def global_efficiency(wn, avail, node_ok):
    keep = np.flatnonzero(node_ok)
    m = len(keep)
    if m < 2:
        return float("nan")
    return float(inverse_path_lengths(wn, avail, keep).sum() / (m * (m - 1)))


def normalized_frobenius(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return 0.0 if na + nb == 0 else float(np.linalg.norm(a - b) / (na + nb))


def laplacian_distance(a, b, node_ok):
    keep = np.flatnonzero(node_ok)
    a, b = a[np.ix_(keep, keep)], b[np.ix_(keep, keep)]
    la = np.sort(np.linalg.eigvalsh(np.diag(a.sum(axis=1)) - a))
    lb = np.sort(np.linalg.eigvalsh(np.diag(b.sum(axis=1)) - b))
    na, nb = np.linalg.norm(la), np.linalg.norm(lb)
    return 0.0 if na + nb == 0 else float(np.linalg.norm(la - lb) / (na + nb))


def mean_weight(w, avail):
    iu = np.triu_indices(len(w), 1)
    sel = avail[iu]
    return float(w[iu][sel].mean()) if sel.any() else float("nan")


def analyse(row, band, set_cfg):
    """All Step 5-6 quantities for one subject, set and band in the L/R frame."""
    wl, wr, homo = hemisphere_matrices(row, band, set_cfg)
    node_ok, avail = symmetric_mask(wl, wr, homo)
    n = len(homo)
    iu = np.triu_indices(n, 1)
    raw = np.concatenate([wl[iu][avail[iu]], wr[iu][avail[iu]], homo[node_ok]])
    a, b = masked_clipped(wl, avail), masked_clipped(wr, avail)
    homo_c = np.where(node_ok, np.clip(np.nan_to_num(homo, nan=0.0), 0.0, None), np.nan)
    scale = max(a.max(), b.max())
    an, bn = (a / scale, b / scale) if scale > 0 else (a, b)
    na, nb = node_metrics(a, an, avail, node_ok), node_metrics(b, bn, avail, node_ok)
    net = {"glob_eff": (global_efficiency(an, avail, node_ok), global_efficiency(bn, avail, node_ok)),
           "mean_clust": (safe_nanmean(na["clustering"][node_ok]), safe_nanmean(nb["clustering"][node_ok])),
           "mean_strength": (safe_nanmean(na["strength"][node_ok]), safe_nanmean(nb["strength"][node_ok]))}
    edges = {f"{set_cfg['left'][i]}-{set_cfg['left'][j]}": (a[i, j] - b[i, j]) if avail[i, j] else float("nan")
             for i, j in zip(*iu)}
    kept = int(node_ok.sum())
    return {"node_ok": node_ok, "nodes": {m: (na[m], nb[m]) for m in NODE_METRICS}, "net": net, "edges": edges,
            "homo": homo_c, "frob": normalized_frobenius(a, b), "lapdist": laplacian_distance(a, b, node_ok),
            "mwd": norm_diff(mean_weight(a, avail), mean_weight(b, avail)),
            "homo_mean": safe_nanmean(homo_c[node_ok]),
            "qc": {"negative_fraction": float((raw < 0).mean()) if len(raw) else float("nan"),
                   "pairs_dropped": [pair_name(set_cfg["left"][i], set_cfg["right"][i]) for i in np.flatnonzero(~node_ok)],
                   "edges_masked": int(kept * (kept - 1) / 2 - avail[iu].sum())}}


def kinds(lr, sign):
    """LR, abs and IC values from a signed L/R value; IC is NaN without a certain lesion side."""
    return {"LR": lr, "abs": abs(lr) if not np.isnan(lr) else float("nan"),
            "IC": sign * lr if sign is not None else float("nan")}


# ---------------------------------------------------------------- columns (declared contracts)

def node_columns(cfg):
    return [f"{s}_{band}_{pair_name(l, r)}_{m}_{k}" for s, sc in cfg["sets"].items() for band in cfg["bands"]
            for l, r in zip(sc["left"], sc["right"]) for m in NODE_METRICS for k in KINDS]


def edge_columns(cfg):
    cols = []
    for s, sc in cfg["sets"].items():
        left, n = sc["left"], len(sc["left"])
        for band in cfg["bands"]:
            cols += [f"{s}_{band}_{left[i]}-{left[j]}_{k}" for i in range(n) for j in range(i + 1, n)
                     for k in ("diffLR", "abs", "diffIC")]
            cols += [f"{s}_{band}_homo_{pair_name(l, r)}" for l, r in zip(sc["left"], sc["right"])]
    return cols


def network_columns(cfg):
    cols = []
    for s in cfg["sets"]:
        for band in cfg["bands"]:
            for m in NET_METRICS:
                cols += [f"{s}_{band}_{m}_{k}" for k in ("L", "R", *KINDS)]
            cols += [f"{s}_{band}_frob", f"{s}_{band}_lapdist"]
            cols += [f"{s}_{band}_mwd_{k}" for k in KINDS]
            cols += [f"{s}_{band}_homo_mean"]
    return cols


def region_names(cfg):
    return [r for r in cfg["regions"] if r not in ("set", "rule")]


def region_columns(cfg):
    cols = []
    for r in region_names(cfg):
        for band in cfg["bands"]:
            cols += [f"region_{r}_{band}_{m}_{k}" for m in NODE_METRICS for k in KINDS]
            cols.append(f"region_{r}_{band}_homo")
    return cols


# ---------------------------------------------------------------- per subject rows

def subject_rows(subject, rows_by_set, cfg, sign):
    node, edge, net = {"subject_id": subject}, {"subject_id": subject}, {"subject_id": subject}
    qc = {"subject_id": subject}
    ext_nodes = {}
    for s, sc in cfg["sets"].items():
        for band in cfg["bands"]:
            res = analyse(rows_by_set[s], band, sc)
            for i, (l, r) in enumerate(zip(sc["left"], sc["right"])):
                for m in NODE_METRICS:
                    x, y = res["nodes"][m][0][i], res["nodes"][m][1][i]
                    vals = kinds(norm_diff(x, y), sign)
                    for k in KINDS:
                        node[f"{s}_{band}_{pair_name(l, r)}_{m}_{k}"] = vals[k]
                    if s == cfg["regions"]["set"]:
                        ext_nodes[(band, pair_name(l, r), m)] = vals
                edge[f"{s}_{band}_homo_{pair_name(l, r)}"] = float(res["homo"][i])
                if s == cfg["regions"]["set"]:
                    ext_nodes[(band, pair_name(l, r), "homo")] = float(res["homo"][i])
            for e, d in res["edges"].items():
                vals = kinds(d, sign)
                edge[f"{s}_{band}_{e}_diffLR"], edge[f"{s}_{band}_{e}_abs"], edge[f"{s}_{band}_{e}_diffIC"] = \
                    vals["LR"], vals["abs"], vals["IC"]
            for m in NET_METRICS:
                x, y = res["net"][m]
                vals = kinds(norm_diff(x, y), sign)
                net.update({f"{s}_{band}_{m}_L": x, f"{s}_{band}_{m}_R": y,
                            **{f"{s}_{band}_{m}_{k}": vals[k] for k in KINDS}})
            vals = kinds(res["mwd"], sign)
            net.update({f"{s}_{band}_frob": res["frob"], f"{s}_{band}_lapdist": res["lapdist"],
                        **{f"{s}_{band}_mwd_{k}": vals[k] for k in KINDS}, f"{s}_{band}_homo_mean": res["homo_mean"]})
            qc[f"{s}_{band}_negative_fraction"] = res["qc"]["negative_fraction"]
            qc[f"{s}_{band}_edges_masked"] = res["qc"]["edges_masked"]
            qc[f"{s}_pairs_dropped"] = ";".join(res["qc"]["pairs_dropped"])
    region = {"subject_id": subject}
    for r in region_names(cfg):
        pairs = cfg["regions"][r]
        for band in cfg["bands"]:
            for m in NODE_METRICS:
                for k in KINDS:
                    region[f"region_{r}_{band}_{m}_{k}"] = safe_nanmean([ext_nodes[(band, p, m)][k] for p in pairs])
            region[f"region_{r}_{band}_homo"] = safe_nanmean([ext_nodes[(band, p, "homo")] for p in pairs])
    return node, edge, net, region, qc


# ---------------------------------------------------------------- lesion (only reader of lesion side)

def lesion_signs(meta_path, cfg):
    les = cfg["lesion"]
    meta = pd.read_csv(meta_path, usecols=cfg["inputs"]["subject_meta_columns_lesion_step_only"])
    side = meta.set_index("subject_id")[les["column"]]
    return {s: (1.0 if v == "left" else -1.0) if v in les["certain_sides"] else None for s, v in side.items()}


# ---------------------------------------------------------------- outputs

def check_table(df, cols):
    if list(df.columns) != ["subject_id", *cols]:
        raise RuntimeError("Feature table columns do not match the declared contract")
    if FORBIDDEN & {c.casefold() for c in df.columns}:
        raise RuntimeError("Outcome column in a feature table")
    if np.isinf(df[cols].to_numpy(dtype=float)).any():
        raise RuntimeError("Infinite graph feature values")


def write_table(rows, cols, csv_path, meta_path, description, cfg, config_path, roots, inputs):
    df = pd.DataFrame(rows).reindex(columns=["subject_id", *cols])
    check_table(df, cols)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    write_with_config(meta_path, {"table": display_path(csv_path, roots.out), "table_sha256": sha256_file(csv_path),
                                  "n_rows": len(df), "columns": ["subject_id", *cols], "description": description,
                                  "kinds": cfg["kinds"], "masking_rule": cfg["masking_rule"], "clip": cfg["clip"],
                                  "zero_rule": cfg["zero_rule"], "nan_cells": int(df[cols].isna().sum().sum()),
                                  "inputs": inputs},
                      config_path, sources=[Path(__file__)], roots=roots)
    return df


def flagged_edges_used(flags, cfg):
    """Per subject and set: available (ok) edges with one interpolated endpoint that enter the L/R graphs."""
    one = flags[(flags["status"] == "ok") & (flags["n_interpolated_endpoints"] == 1)]
    out = {}
    for s, sc in cfg["sets"].items():
        left, right = set(sc["left"]), set(sc["right"])
        homos = {frozenset(p) for p in zip(sc["left"], sc["right"])}
        for subject, g in one.groupby("subject_id"):
            n = 0
            for e in g["edge"]:
                a, b = e.split("-")
                if {a, b} <= left or {a, b} <= right or frozenset((a, b)) in homos:
                    n += 1
            out[(subject, s)] = n
    return out


def main(argv=None):
    parser = add_root_args(argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter))
    parser.add_argument("--meta-root", type=Path, default=None, help="Steps 1-2 outputs (default: --prev-root)")
    args = parser.parse_args(argv)
    roots = roots_from_args(args)
    meta_root = Path(args.meta_root).resolve() if args.meta_root else roots.prev
    cfg, config_path = load_config(CONFIG)
    inp = cfg["inputs"]

    tables = {s: pd.read_csv(roots.prev_path(p)) for s, p in inp["connectivity"].items()}
    flags = pd.read_csv(roots.prev_path(inp["edge_flags"]))
    qc_in = pd.read_csv(meta_root / inp["epoch_qc"], usecols=inp["epoch_qc_columns"])
    included = sorted(qc_in.loc[qc_in["include_v3_epochs"].astype(str) == "True", "subject_id"])
    for s, t in tables.items():
        if sorted(t["subject_id"]) != included:
            raise RuntimeError(f"{s} connectivity subjects differ from the included epoch_qc subjects")
    signs = lesion_signs(meta_root / inp["subject_meta"], cfg)
    records = {s: t.set_index("subject_id").to_dict("index") for s, t in tables.items()}

    results = [subject_rows(subj, {s: records[s][subj] for s in tables}, cfg, signs.get(subj)) for subj in included]
    outs = {k: roots.out_path(v) for k, v in cfg["outputs"].items()}
    inputs = {**{f"connectivity_{s}_sha256": sha256_file(roots.prev_path(p)) for s, p in inp["connectivity"].items()},
              "edge_flags_sha256": sha256_file(roots.prev_path(inp["edge_flags"])),
              "subject_meta_sha256": sha256_file(meta_root / inp["subject_meta"])}
    write_table([r[0] for r in results], node_columns(cfg), outs["node_csv"], outs["node_meta"],
                "Node level: per homologous pair and band, (L-R)/(L+R) of strength, local efficiency, clustering", cfg, config_path, roots, inputs)
    write_table([r[1] for r in results], edge_columns(cfg), outs["edge_csv"], outs["edge_meta"],
                "Edge level: mirrored intra-hemispheric edge differences w_L - w_R (clipped) and clipped homotopic weights", cfg, config_path, roots, inputs)
    write_table([r[2] for r in results], network_columns(cfg), outs["network_csv"], outs["network_meta"],
                "Network level: global efficiency, mean clustering, mean strength (per hemisphere and asymmetries) and deformation measures", cfg, config_path, roots, inputs)
    write_table([r[3] for r in results], region_columns(cfg), outs["region_csv"], outs["region_meta"],
                "Region level (extended set, regions fixed in config): mean node differences and homotopic weights", cfg, config_path, roots, inputs)

    used = flagged_edges_used(flags, cfg)
    qc = pd.DataFrame([r[4] for r in results])
    for s in cfg["sets"]:
        qc[f"{s}_flagged_edges_used"] = [used.get((subj, s), 0) for subj in qc["subject_id"]]
    qc["lesion_frame"] = ["IC" if signs.get(s) is not None else "abs_only" for s in qc["subject_id"]]
    outs["qc_csv"].parent.mkdir(parents=True, exist_ok=True)
    qc.to_csv(outs["qc_csv"], index=False)

    neg_cols = [c for c in qc.columns if c.endswith("_negative_fraction")]
    summary = {"n_subjects": len(included), "n_lesion_aligned": int(sum(signs.get(s) is not None for s in included)),
               "uncertain_side_subjects": [s for s in included if signs.get(s) is None],
               "pairs_dropped": {s: qc.loc[qc[f"{s}_pairs_dropped"] != "", ["subject_id", f"{s}_pairs_dropped"]].values.tolist()
                                 for s in cfg["sets"]},
               "edges_masked": {c: qc.loc[qc[c] > 0, ["subject_id", c]].values.tolist()
                                for c in qc.columns if c.endswith("_edges_masked") and (qc[c] > 0).any()},
               "negative_fraction_median": {c.replace("_negative_fraction", ""): float(qc[c].median()) for c in neg_cols},
               "subjects_with_flagged_edges_used": {s: int((qc[f"{s}_flagged_edges_used"] > 0).sum()) for s in cfg["sets"]},
               "n_columns": {"node": len(node_columns(cfg)), "edge": len(edge_columns(cfg)),
                             "network": len(network_columns(cfg)), "region": len(region_columns(cfg))},
               "no_outcome_read": True}
    write_with_config(outs["summary_json"], {"summary": summary}, config_path, sources=[Path(__file__)], roots=roots)
    print(f"Steps 5-6: {summary['n_subjects']} subjects ({summary['n_lesion_aligned']} lesion-aligned); "
          f"columns {summary['n_columns']}")
    print(f"pairs dropped (symmetric): {summary['pairs_dropped']}")
    print(f"masked mirrored edges: {summary['edges_masked'] or 'none'}")
    print("median negative fraction clipped: " + ", ".join(f"{k} {v:.2f}" for k, v in summary["negative_fraction_median"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
