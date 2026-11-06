"""Synthetic tests for Steps 5-7 (graphs, differences, relational abnormality); no real EEG, no labels."""
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import abnormality_v3 as ab  # noqa: E402
import connectivity_v3 as cv  # noqa: E402
import graph_v3 as gr  # noqa: E402

GCFG = json.loads((ROOT / "configs/v3/graph.json").read_text(encoding="utf-8"))
CCFG = json.loads((ROOT / "configs/v3/connectivity.json").read_text(encoding="utf-8"))
ACFG = json.loads((ROOT / "configs/v3/abnormality.json").read_text(encoding="utf-8"))
BANDS = GCFG["bands"]


def sym(n, rng, low=0.05, high=0.4):
    w = rng.uniform(low, high, (n, n))
    w = (w + w.T) / 2
    np.fill_diagonal(w, 0.0)
    return w


def make_row(set_name, wl, wr, homo, other=0.02):
    """Connectivity row with exactly the Step 4 column names for one set, same matrices in every band."""
    sc = GCFG["sets"][set_name]
    left, right = sc["left"], sc["right"]
    row = {}
    for band in BANDS:
        for a, b in cv.edge_list(sc["channel_order"]):
            if a in left and b in left:
                v = wl[left.index(a), left.index(b)]
            elif a in right and b in right:
                v = wr[right.index(a), right.index(b)]
            elif a in left and b in right and left.index(a) == right.index(b):
                v = homo[left.index(a)]
            else:
                v = other
            row[f"wpli_{band}_{a}-{b}"] = v
    return row


def test_channel_orders_match_step4():
    assert GCFG["sets"]["core"]["channel_order"] == CCFG["channel_sets"]["core"]
    assert GCFG["sets"]["extended"]["channel_order"] == CCFG["channel_sets"]["extended"]


def test_norm_diff_and_kinds():
    assert gr.norm_diff(3, 1) == 0.5 and gr.norm_diff(0, 0) == 0.0 and np.isnan(gr.norm_diff(np.nan, 1))
    k = gr.kinds(0.2, -1.0)
    assert k["LR"] == 0.2 and k["abs"] == 0.2 and k["IC"] == -0.2
    assert np.isnan(gr.kinds(0.2, None)["IC"]) and gr.kinds(-0.2, 1.0)["abs"] == 0.2


def test_symmetric_graph_gives_zero_differences():
    rng = np.random.default_rng(0)
    w = sym(4, rng)
    res = gr.analyse(make_row("core", w, w.copy(), np.full(4, 0.1)), "alpha", GCFG["sets"]["core"])
    for m in gr.NODE_METRICS:
        assert np.allclose(res["nodes"][m][0], res["nodes"][m][1])
    assert res["frob"] == 0.0 and res["lapdist"] == pytest.approx(0.0, abs=1e-12) and res["mwd"] == 0.0
    assert all(d == 0.0 for d in res["edges"].values())
    assert all(gr.norm_diff(*res["net"][m]) == 0.0 for m in gr.NET_METRICS)


def test_known_asymmetry_left_twice_right():
    rng = np.random.default_rng(1)
    w = sym(4, rng)
    res = gr.analyse(make_row("core", 2 * w, w, np.full(4, 0.1)), "beta", GCFG["sets"]["core"])
    third = 1.0 / 3.0                                   # (2 - 1) / (2 + 1) for every scale-proportional measure
    for m in gr.NODE_METRICS:
        a, b = res["nodes"][m]
        assert np.allclose([gr.norm_diff(x, y) for x, y in zip(a, b)], third)
    for m in gr.NET_METRICS:
        assert gr.norm_diff(*res["net"][m]) == pytest.approx(third)
    assert res["frob"] == pytest.approx(third) and res["lapdist"] == pytest.approx(third)
    assert res["mwd"] == pytest.approx(third)
    left = GCFG["sets"]["core"]["left"]
    assert res["edges"][f"{left[0]}-{left[1]}"] == pytest.approx(w[0, 1])   # w_L - w_R = 2w - w


def test_masking_is_symmetric_and_cannot_create_asymmetry():
    rng = np.random.default_rng(2)
    w = sym(4, rng)
    wl, wr, homo = w.copy(), w.copy(), np.full(4, 0.1)
    wl[0, 1] = wl[1, 0] = np.nan                        # missing in the left hemisphere only
    homo[2] = np.nan                                    # pair 2 unavailable
    res = gr.analyse(make_row("core", wl, wr, homo), "theta", GCFG["sets"]["core"])
    assert res["node_ok"].tolist() == [True, True, False, True]
    left = GCFG["sets"]["core"]["left"]
    assert np.isnan(res["edges"][f"{left[0]}-{left[1]}"])
    assert all(d == 0.0 for e, d in res["edges"].items() if not np.isnan(d))
    for m in gr.NODE_METRICS:
        a, b = res["nodes"][m]
        assert np.isnan(a[2]) and np.isnan(b[2])
        assert np.allclose(np.delete(a, 2), np.delete(b, 2), equal_nan=True)
    assert res["frob"] == 0.0 and res["mwd"] == 0.0 and res["qc"]["pairs_dropped"] == ["P3P4"]


def test_negative_weights_are_clipped_and_counted():
    w = np.array([[0, -0.1, 0.2, 0.3], [-0.1, 0, 0.2, 0.1], [0.2, 0.2, 0, -0.05], [0.3, 0.1, -0.05, 0]])
    res = gr.analyse(make_row("core", w, w.copy(), np.array([0.1, -0.2, 0.1, 0.1])), "delta", GCFG["sets"]["core"])
    assert res["qc"]["negative_fraction"] == pytest.approx(5 / 16)    # 2+2 intra (both hemis) + 1 homotopic of 16
    assert res["frob"] == 0.0 and np.isnan(res["homo"]).sum() == 0 and res["homo"][1] == 0.0


def test_column_counts():
    assert len(gr.node_columns(GCFG)) == 4 * (4 + 11) * 3 * 3
    assert len(gr.edge_columns(GCFG)) == 4 * ((6 + 55) * 3 + (4 + 11))
    assert len(gr.network_columns(GCFG)) == 2 * 4 * (3 * 5 + 2 + 3 + 1)
    assert len(gr.region_columns(GCFG)) == 5 * 4 * (3 * 3 + 1)


def test_steps_5_to_7_end_to_end(tmp_path):
    rng = np.random.default_rng(3)
    prev, meta, out = tmp_path / "step4", tmp_path / "step2", tmp_path / "out"
    subjects = ["sub-01", "sub-02", "sub-03"]
    rows = {"core": [], "extended": []}
    for k, subj in enumerate(subjects):
        for s, n in (("core", 4), ("extended", 11)):
            w = sym(n, rng)
            scale = 1.0 if k == 0 else 2.0                  # sub-01 symmetric; sub-02/03 left = 2 x right
            rows[s].append({"subject_id": subj, **make_row(s, scale * w, w, np.full(n, 0.1))})
    (prev / "features/v3").mkdir(parents=True)
    pd.DataFrame(rows["core"]).to_csv(prev / "features/v3/connectivity_core_v3.csv", index=False)
    pd.DataFrame(rows["extended"]).to_csv(prev / "features/v3/connectivity_ext_v3.csv", index=False)
    (prev / "results/v3/step4").mkdir(parents=True)
    pd.DataFrame({"subject_id": ["sub-02"], "edge": ["F3-C3"], "in_core": [True], "status": ["ok"],
                  "n_interpolated_endpoints": [1]}).to_csv(prev / "results/v3/step4/connectivity_edge_flags.csv", index=False)
    (meta / "features/v3").mkdir(parents=True)
    pd.DataFrame({"subject_id": subjects + ["sub-04"], "include_v3_epochs": [True, True, True, False]}).to_csv(
        meta / "features/v3/epoch_qc_v3.csv", index=False)
    pd.DataFrame({"subject_id": subjects, "lesion_side_final": ["left", "right", "uncertain"], "sex": ["m", "f", "m"]}).to_csv(
        meta / "features/v3/subject_meta_v3.csv", index=False)

    assert gr.main(["--prev-root", str(prev), "--meta-root", str(meta), "--out-root", str(out),
                    "--data-root", str(tmp_path / "unused")]) == 0
    node = pd.read_csv(out / "features/v3/graph_node_v3.csv").set_index("subject_id")
    net = pd.read_csv(out / "features/v3/graph_network_v3.csv").set_index("subject_id")
    region = pd.read_csv(out / "features/v3/graph_region_v3.csv").set_index("subject_id")
    assert list(node.columns) == gr.node_columns(GCFG)
    assert node.loc["sub-01", "core_alpha_C3C4_strength_LR"] == 0.0
    assert node.loc["sub-02", "core_alpha_C3C4_strength_LR"] == pytest.approx(1 / 3)
    assert node.loc["sub-02", "core_alpha_C3C4_strength_IC"] == pytest.approx(-1 / 3)    # right lesion: I = R
    assert np.isnan(node.loc["sub-03", "core_alpha_C3C4_strength_IC"])                   # uncertain side
    assert node.loc["sub-03", "core_alpha_C3C4_strength_abs"] == pytest.approx(1 / 3)
    assert net.loc["sub-02", "core_beta_frob"] == pytest.approx(1 / 3)
    assert region.loc["sub-02", "region_temporal_delta_strength_LR"] == pytest.approx(1 / 3)
    qc = pd.read_csv(out / "results/v3/step5/graph_qc.csv").set_index("subject_id")
    assert qc.loc["sub-02", "core_flagged_edges_used"] == 1 and qc.loc["sub-03", "lesion_frame"] == "abs_only"
    sidecar = json.loads((out / "features/v3/graph_node_v3.meta.json").read_text())
    assert sidecar["columns"] == ["subject_id", *gr.node_columns(GCFG)] and sidecar["provenance"]["config_sha256"]

    assert ab.main(["--prev-root", str(out), "--out-root", str(out), "--data-root", str(tmp_path / "unused")]) == 0
    rel = pd.read_csv(out / "features/v3/relational_abnormality_v3.csv").set_index("subject_id")
    assert rel.loc["sub-01", "mean_abs_node"] == 0.0 and rel.loc["sub-01", "overall_magnitude_unscaled"] == 0.0
    ic_cols = [c for c in rel.columns if c.startswith("rel_IC_")]
    abs_cols = [c for c in rel.columns if c.startswith("rel_abs_")]
    assert len(ic_cols) == len(abs_cols) == 4 * (4 * 3) + 4 * 6 + 4 * 4      # node 48 + edge 24 + network 16
    assert rel.loc["sub-03", ic_cols].isna().all() and rel.loc["sub-03", abs_cols].notna().all()
    node_abs = [c for c in abs_cols if c.startswith("rel_abs_core_") and c.endswith(("_strength_abs", "_local_eff_abs", "_clustering_abs"))]
    assert rel.loc["sub-02", "mean_abs_node"] == pytest.approx(rel.loc["sub-02", node_abs].mean())
    assert not ({"nihss_raw", "severity_class"} & set(rel.columns))
