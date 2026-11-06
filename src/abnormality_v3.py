"""Step 7: relational abnormality representation (label-free, no external data).

The patient's contralesional hemisphere is the reference. From the Step 5-6 tables (--prev-root), the per-patient
vector is the primary-set (core) ipsilesional-minus-contralesional difference at node, edge and network level for
every band (rel_IC_*, NaN when the lesion side is uncertain), plus the frame-invariant absolute differences
(rel_abs_*, all subjects: the absolute L/R version used for uncertain-side subjects). Summary scalars: mean
absolute difference per level (overall and per band; extended set as secondary) and an unscaled overall magnitude.
The registered overall magnitude (z-scored level summaries) is computed in Step 8 inside cross-validation.

Run from the repo root: python src/abnormality_v3.py --prev-root <Steps 5-6 out> [--out-root O]
"""
import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths_v3 import add_root_args, roots_from_args  # noqa: E402
from provenance_v3 import ROOT, display_path, load_config, sha256_file, write_with_config  # noqa: E402

CONFIG = "configs/v3/abnormality.json"
GRAPH_CONFIG = "configs/v3/graph.json"
FORBIDDEN = {"nihss_raw", "severity_class", "nihss", "mbi", "mrs"}
LEVELS = ("node", "edge", "network")


def element_names(gcfg, set_name):
    sc = gcfg["sets"][set_name]
    left, n = sc["left"], len(sc["left"])
    pairs = [f"{l}{r}" for l, r in zip(sc["left"], sc["right"])]
    edges = [f"{left[i]}-{left[j]}" for i in range(n) for j in range(i + 1, n)]
    return pairs, edges


def level_columns(cfg, gcfg, level, set_name, kind, bands):
    """Step 5-6 column names for one level, set, kind (IC or abs) and list of bands."""
    pairs, edges = element_names(gcfg, set_name)
    lv = cfg["levels"][level]
    if level == "node":
        return [f"{set_name}_{b}_{p}_{m}_{kind}" for b in bands for p in pairs for m in lv["metrics"]]
    if level == "edge":
        return [f"{set_name}_{b}_{e}_{lv['kinds_map'][kind]}" for b in bands for e in edges]
    return [f"{set_name}_{b}_{m}_{kind}" for b in bands for m in lv["measures"]]


def build(tables, cfg, gcfg):
    """Return the relational abnormality table (subject_id + features) and its column list."""
    merged = tables["node"]
    for name in ("edge", "network"):
        merged = merged.merge(tables[name], on="subject_id", how="inner", validate="one_to_one")
    if len(merged) != len(tables["node"]):
        raise RuntimeError("Step 5-6 tables do not cover the same subjects")
    prim, sec, bands = cfg["primary_set"], cfg["secondary_set"], cfg["bands"]
    out = pd.DataFrame({"subject_id": merged["subject_id"]})
    vector_cols = {}
    for kind in ("IC", "abs"):
        for level in LEVELS:
            for c in level_columns(cfg, gcfg, level, prim, kind, bands):
                vector_cols[f"rel_{kind}_{c}"] = merged[c]
    out = pd.concat([out, pd.DataFrame(vector_cols)], axis=1)
    summaries = {}
    for level in LEVELS:
        summaries[f"mean_abs_{level}"] = merged[level_columns(cfg, gcfg, level, prim, "abs", bands)].abs().mean(axis=1)
    for level in LEVELS:
        for band in bands:
            summaries[f"mean_abs_{level}_{band}"] = merged[level_columns(cfg, gcfg, level, prim, "abs", [band])].abs().mean(axis=1)
    for level in LEVELS:
        summaries[f"ext_mean_abs_{level}"] = merged[level_columns(cfg, gcfg, level, sec, "abs", bands)].abs().mean(axis=1)
    summaries["overall_magnitude_unscaled"] = pd.concat([summaries[f"mean_abs_{lv}"] for lv in LEVELS], axis=1).mean(axis=1)
    out = pd.concat([out, pd.DataFrame(summaries)], axis=1)
    cols = [c for c in out.columns if c != "subject_id"]
    return out, cols


def check_table(df, cols):
    if list(df.columns) != ["subject_id", *cols]:
        raise RuntimeError("Feature table columns do not match the declared contract")
    if FORBIDDEN & {c.casefold() for c in df.columns}:
        raise RuntimeError("Outcome column in a feature table")
    if np.isinf(df[cols].to_numpy(dtype=float)).any():
        raise RuntimeError("Infinite relational abnormality values")


def main(argv=None):
    args = add_root_args(argparse.ArgumentParser(description=__doc__)).parse_args(argv)
    roots = roots_from_args(args)
    cfg, config_path = load_config(CONFIG)
    gcfg, graph_config_path = load_config(GRAPH_CONFIG)
    inp = cfg["inputs"]
    tables = {k: pd.read_csv(roots.prev_path(inp[k])) for k in ("node", "edge", "network")}
    out, cols = build(tables, cfg, gcfg)
    check_table(out, cols)

    outs = {k: roots.out_path(v) for k, v in cfg["outputs"].items()}
    outs["csv"].parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(outs["csv"], index=False)
    ic_cols = [c for c in cols if c.startswith("rel_IC_")]
    n_ic = int(out[ic_cols].notna().any(axis=1).sum())
    write_with_config(outs["meta"], {"table": display_path(outs["csv"], roots.out), "table_sha256": sha256_file(outs["csv"]),
                                     "n_rows": len(out), "columns": ["subject_id", *cols], "definition": cfg["definition"],
                                     "summaries": cfg["summaries"], "graph_config_sha256": sha256_file(graph_config_path),
                                     "n_rel_IC_columns": len(ic_cols), "n_subjects_with_IC": n_ic,
                                     "inputs": {k: sha256_file(roots.prev_path(inp[k])) for k in ("node", "edge", "network")}},
                      config_path, sources=[Path(__file__)], roots=roots)
    summary_cols = [c for c in cols if c.startswith(("mean_abs_", "ext_mean_abs_", "overall_"))]
    summary = {"n_subjects": len(out), "n_subjects_with_IC": n_ic, "n_vector_columns_per_kind": len(ic_cols),
               "n_summary_columns": len(summary_cols), "graph_config": display_path(graph_config_path, ROOT),
               "summary_medians": {c: float(out[c].median()) for c in summary_cols if "_" not in c[len("mean_abs_"):] or c.startswith(("ext_", "overall_"))},
               "nan_cells_abs_vector": int(out[[c for c in cols if c.startswith("rel_abs_")]].isna().sum().sum()),
               "no_outcome_read": True}
    write_with_config(outs["summary_json"], {"summary": summary}, config_path, sources=[Path(__file__)], roots=roots)
    print(f"Step 7: {len(out)} subjects ({n_ic} lesion-aligned), {len(ic_cols)} IC + {len(ic_cols)} abs vector columns, "
          f"{len(summary_cols)} summaries")
    print("median summaries: " + ", ".join(f"{k} {v:.3f}" for k, v in summary["summary_medians"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
