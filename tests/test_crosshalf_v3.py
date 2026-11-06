"""Synthetic tests for Step 7b, the cross-half deformation estimator (no real EEG, no labels)."""
import copy
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
import connectivity_v3 as cv  # noqa: E402
import crosshalf_v3 as ch  # noqa: E402
import graph_v3 as gr  # noqa: E402

CFG = json.loads((ROOT / "configs/v3/crosshalf.json").read_text(encoding="utf-8"))
GCFG = json.loads((ROOT / "configs/v3/graph.json").read_text(encoding="utf-8"))
CORE = GCFG["sets"]["core"]
SUMS = CFG["network_summaries"]


def row_from(wl, wr, homo, band="alpha"):
    """Connectivity row (Step 4 column names) for the core set in one band."""
    left, right = CORE["left"], CORE["right"]
    row = {}
    for a, b in cv.edge_list(CORE["channel_order"]):
        if a in left and b in left:
            v = wl[left.index(a), left.index(b)]
        elif a in right and b in right:
            v = wr[right.index(a), right.index(b)]
        elif a in left and b in right and left.index(a) == right.index(b):
            v = homo[left.index(a)]
        else:
            v = 0.02
        row[f"wpli_{band}_{a}-{b}"] = v
    return row


def noisy(base, sd, rng):
    n = base.shape[0]
    e = rng.normal(0, sd, (n, n))
    e = (e + e.T) / np.sqrt(2)
    w = base + e
    np.fill_diagonal(w, 0.0)
    return w


def simulate(asym, reps=400, sd=0.05, seed=0):
    """Mean cross-half and naive (single-half) D2 for core graphs with true L - R difference `asym` per edge."""
    rng = np.random.default_rng(seed)
    base = np.full((4, 4), 0.3)
    np.fill_diagonal(base, 0.0)
    true_l = base + asym * (1 - np.eye(4))
    homo = np.full(4, 0.1)
    node_ok, avail = gr.symmetric_mask(true_l, base, homo)
    cross, naive = [], []
    for _ in range(reps):
        h1 = ch.half_differences(row_from(noisy(true_l, sd, rng), noisy(base, sd, rng), homo), "alpha", CORE, node_ok, avail, SUMS)
        h2 = ch.half_differences(row_from(noisy(true_l, sd, rng), noisy(base, sd, rng), homo), "alpha", CORE, node_ok, avail, SUMS)
        cross.append(ch.cross_products(h1, h2))
        naive.append(ch.naive_products(h1))
    mean = lambda rows, k: float(np.mean([r[k] for r in rows]))  # noqa: E731
    return {k: mean(cross, k) for k in cross[0]}, {k: mean(naive, k) for k in naive[0]}


def test_split_halves_disjoint_stratified_equal_and_seeded():
    classes = np.array([1] * 13 + [2] * 10)
    a1, b1 = ch.split_halves(classes, np.random.default_rng(5))
    a2, b2 = ch.split_halves(classes, np.random.default_rng(5))
    assert np.array_equal(a1, a2) and np.array_equal(b1, b2)
    assert not set(a1) & set(b1) and len(a1) == len(b1) == 6 + 5
    for label, h in ((1, 6), (2, 5)):
        assert (classes[a1] == label).sum() == h and (classes[b1] == label).sum() == h
    assert ch.subject_seed("sub-01", CFG) == 2000 and ch.subject_seed("sub-10", CFG) == 2009


def test_symmetric_noise_gives_cross_half_d2_about_zero():
    cross, naive = simulate(asym=0.0)
    assert abs(cross["D2_edge"]) < 5e-4                  # unbiased: about 0
    assert naive["D2_edge"] > 4e-3                       # single-half square = noise variance (2 * 0.05^2 = 0.005)
    assert abs(cross["D2_node"]) < 5e-3 and naive["D2_node"] > 5 * abs(cross["D2_node"])
    assert abs(cross["D2_mean_weight"]) < 5e-4


def test_known_asymmetry_is_recovered():
    cross, naive = simulate(asym=0.1)
    assert cross["D2_edge"] == pytest.approx(0.01, abs=1.5e-3)          # a^2
    assert cross["D2_node"] == pytest.approx(0.09, abs=1e-2)            # (3a)^2, 3 neighbours per node
    assert cross["D2_mean_weight"] == pytest.approx(0.01, abs=1.5e-3)
    assert cross["signed_mean_weight"] == pytest.approx(0.1, abs=5e-3)  # signed L - R
    assert naive["D2_edge"] > cross["D2_edge"]                          # naive adds the noise variance


def test_d2_is_frame_invariant_and_signed_flips():
    e1, e2 = np.array([0.1, -0.2]), np.array([0.3, 0.1])
    m1, m2 = {"mean_weight": 0.2}, {"mean_weight": 0.1}
    a = ch.cross_products((e1, e1, m1), (e2, e2, m2))
    b = ch.cross_products((-e1, -e1, {"mean_weight": -0.2}), (-e2, -e2, {"mean_weight": -0.1}))
    assert a["D2_edge"] == b["D2_edge"] and a["D2_mean_weight"] == b["D2_mean_weight"]
    assert a["signed_mean_weight"] == -b["signed_mean_weight"]


def test_build_table_lesion_frames():
    values = {}
    for s in GCFG["sets"]:
        for band in GCFG["bands"]:
            values.update({f"{s}_{band}_D2_edge": 0.01, f"{s}_{band}_D2_node": 0.05})
            for m in SUMS:
                values.update({f"{s}_{band}_D2_{m}": 0.02, f"{s}_{band}_signed_{m}": 0.3,
                               f"{s}_{band}_naive_noiseinflated_D2_{m}": 0.5})
            values.update({f"{s}_{band}_naive_noiseinflated_D2_edge": 0.4, f"{s}_{band}_naive_noiseinflated_D2_node": 0.6})
    results = [{"subject_id": s, "values": values} for s in ("sub-01", "sub-02", "sub-03")]
    df, cols = ch.build_table(results, {"sub-01": 1.0, "sub-02": -1.0, "sub-03": None}, CFG, GCFG)
    d = df.set_index("subject_id")
    assert list(df.columns) == ["subject_id", *ch.columns(CFG, GCFG)]
    assert d.loc["sub-01", "core_alpha_signed_mean_weight_IC"] == 0.3 and d.loc["sub-02", "core_alpha_signed_mean_weight_IC"] == -0.3
    assert np.isnan(d.loc["sub-03", "core_alpha_signed_mean_weight_IC"]) and d.loc["sub-03", "core_alpha_signed_mean_weight_LR"] == 0.3
    assert d.loc["sub-02", "core_D2_edge_allbands"] == pytest.approx(0.01)


def test_main_end_to_end_on_synthetic_epochs(tmp_path, monkeypatch):
    from test_spectral_v3 import make_epochs, scaled_pairs
    prev, out = tmp_path / "step2", tmp_path / "out"
    edir = prev / "data/processed/figshare_v3"
    edir.mkdir(parents=True)
    for i, s in enumerate(("sub-01", "sub-02")):
        make_epochs([1, 2] * 12, scaled_pairs({("F3", "F4"): 1.5}), seed=10 + i).save(edir / f"{s}-epo.fif", verbose="ERROR")
    (prev / "features/v3").mkdir(parents=True)
    pd.DataFrame({"subject_id": ["sub-01", "sub-02"], "include_v3_epochs": [True, True],
                  "interpolated": ["", ""], "screen_interpolated": ["", ""]}).to_csv(prev / "features/v3/epoch_qc_v3.csv", index=False)
    pd.DataFrame({"subject_id": ["sub-01", "sub-02"], "lesion_side_final": ["left", "uncertain"]}).to_csv(
        prev / "features/v3/subject_meta_v3.csv", index=False)
    original = ch.load_config

    def small(rel):
        cfg, path = original(rel)
        if rel == ch.CONFIG:
            cfg = copy.deepcopy(cfg)
            cfg["splits"]["n_splits"], cfg["n_jobs"] = 2, 1
        return cfg, path

    monkeypatch.setattr(ch, "load_config", small)
    assert ch.main(["--prev-root", str(prev), "--out-root", str(out), "--data-root", str(tmp_path / "unused"), "--n-jobs", "1"]) == 0
    df = pd.read_csv(out / "features/v3/abnormality_crosshalf_v3.csv").set_index("subject_id")
    assert list(df.columns) == ch.columns(CFG, GCFG)
    assert np.isfinite(df[[c for c in df.columns if "_D2_" in c and "naive" not in c]].to_numpy()).all()
    assert np.isnan(df.loc["sub-02", "core_alpha_signed_mean_weight_IC"]) and np.isfinite(df.loc["sub-01", "core_alpha_signed_mean_weight_IC"])
    meta = json.loads((out / "features/v3/abnormality_crosshalf_v3.meta.json").read_text())
    assert meta["columns"] == ["subject_id", *ch.columns(CFG, GCFG)] and "noise-inflated" in meta["label_note"]
    qc = pd.read_csv(out / "results/v3/step7b/crosshalf_qc.csv")
    assert (qc["half_epochs"] == 12).all() and (qc["n_nonfinite_half_values"] == 0).all()
