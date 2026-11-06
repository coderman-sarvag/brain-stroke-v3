"""Synthetic tests for the v3 registry engine, guards and loader (no real labels are read)."""
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import registry_gates_v3 as gates  # noqa: E402
import run_registry_v3 as runner  # noqa: E402
import train_regression_v3 as eng  # noqa: E402

CFG = json.loads((ROOT / "configs/v3/registry_v3.json").read_text(encoding="utf-8"))
FAST = {**CFG["settings"], "permutations": 20, "outer_repeats": 2, "bootstrap_resamples": 50}


def synthetic(seed=0, n=45, signal=True):
    return gates.simulate(np.random.default_rng(seed), n=n, p=8, rho=0.6, signal=signal)


def test_grouped_splits_keep_groups_and_both_classes():
    _, _, strata, groups, _ = synthetic()
    for seed in (42, 43):
        for train, valid in eng.grouped_splits(strata, groups, 5, seed):
            assert not set(groups[train]) & set(groups[valid])
            assert set(strata[valid]) == {0, 1}
    assert groups[0] == groups[1] and groups[2] == groups[3]


def test_ridge_pipeline_imputes_inside_folds_and_predicts_finite():
    X, y, strata, groups, _ = synthetic(1)
    X = X.copy()
    X[[4, 9, 20], 2] = np.nan
    model, alpha = eng.fit_ridge(X, y, strata, groups, FAST)
    assert [name for name, _ in model.steps] == ["impute", "scale", "ridge"] and alpha in FAST["alphas"]
    out = eng.cross_validated_predictions(X, y, strata, groups, FAST)
    assert np.isfinite(out["predictions"]).all() and out["predictions"].shape == (45, 2)
    with pytest.raises(ValueError):
        eng.validate_arrays(X, y, strata, groups, FAST, "association")


def test_evaluate_kinds_alternatives_and_permutation_bounds():
    X, y, strata, groups, w = synthetic(2)
    a = eng.evaluate(w, y, strata, groups, FAST, 1, kind="association")["summary"]
    r = eng.evaluate(X, y, strata, groups, FAST, 2, kind="ridge")["summary"]
    assert a["alternative"] == "two-sided" and r["alternative"] == "greater"
    assert 1 / 21 <= a["p_raw"] <= 1 and 1 / 21 <= r["p_raw"] <= 1
    assert a["rho"] > 0.3 and {"rmse", "dummy_rmse", "auc"} <= set(r)


def test_partial_spearman():
    rng = np.random.default_rng(3)
    z = rng.standard_normal(200)
    x, y = z + 0.1 * rng.standard_normal(200), z + 0.1 * rng.standard_normal(200)
    assert abs(eng.partial_spearman(x, y, z)) < 0.3          # association explained by z
    assert eng.partial_spearman(x, x, rng.standard_normal(200)) == pytest.approx(1.0, abs=1e-9)


def test_guards_refuse():
    with pytest.raises(SystemExit, match="missing git tag"):
        runner.check_tags({"features-v3"}, ["features-v3", "registry-v3"], lambda t: True)
    with pytest.raises(SystemExit, match="not ancestors"):
        runner.check_tags({"features-v3", "registry-v3"}, ["features-v3", "registry-v3"], lambda t: t != "registry-v3")
    runner.check_tags({"features-v3", "registry-v3"}, ["features-v3", "registry-v3"], lambda t: True)
    labels = pd.DataFrame({"subject_id": ["sub-01", "sub-02"], "nihss_raw": [3, 7]})
    part = pd.DataFrame({"Participant_ID": ["sub-01", "sub-02"], "NIHSS": [3, 8]})
    assert runner.crosscheck_labels(labels, part, ["sub-01", "sub-02"], "Participant_ID", "NIHSS") == ["sub-02"]


def test_manifest_guard_detects_change(tmp_path):
    (tmp_path / "a.csv").write_text("x\n1\n")
    (tmp_path / "lab.csv").write_text("y\n")
    good = {"tables": [{"path": "a.csv", "sha256": runner.sha256_file(tmp_path / "a.csv")}], "qc_files": [],
            "label_file": {"path": "lab.csv", "sha256": runner.sha256_file(tmp_path / "lab.csv")}}
    assert runner.check_manifest(good, tmp_path) == 2
    (tmp_path / "a.csv").write_text("x\n2\n")
    with pytest.raises(SystemExit, match="mismatch"):
        runner.check_manifest(good, tmp_path)


def test_loader_whitelist_shuffle_and_encoding(tmp_path):
    ids = [f"sub-{i:02d}" for i in range(1, 13)]
    nihss = [1, 2, 3, 4, 5, 6, 7, 8, 2, 3, 9, 10]
    (tmp_path / "f").mkdir()
    pd.DataFrame({"subject_id": ids, "pdBSI": np.linspace(0.1, 0.5, 12)}).to_csv(tmp_path / "f/t.csv", index=False)
    (tmp_path / "f/t.meta.json").write_text(json.dumps({"columns": ["subject_id", "pdBSI"]}))
    pd.DataFrame({"subject_id": ids, "nihss_raw": nihss, "severity_class": ["mild" if v < 5 else "moderate" for v in nihss]}).to_csv(tmp_path / "f/lab.csv", index=False)
    pd.DataFrame({"subject_id": ids, "split_group": ids[:1] + ids[:1] + ids[2:]}).to_csv(tmp_path / "f/meta.csv", index=False)
    cfg = {"labels": {"file": "f/lab.csv", "columns": ["subject_id", "nihss_raw", "severity_class"]},
           "groups": {"file": "f/meta.csv", "column": "split_group"}}
    spec = {"table": "f/t.csv", "sidecar": "f/t.meta.json", "features": ["pdBSI"]}
    X, y, strata, groups, got, feats = eng.load_test(tmp_path, spec, cfg, ids)
    assert got == ids and feats == ["pdBSI"] and groups[0] == groups[1] != groups[2]
    _, ys, ss, gs, _, _ = eng.load_test(tmp_path, spec, cfg, ids, shuffle_seed=7)
    assert sorted(ys) == sorted(y) and not np.array_equal(ys, y)
    assert np.array_equal(ss, (ys >= 5).astype(int)) and np.array_equal(gs, groups)     # joint shuffle, groups stay
    with pytest.raises(ValueError, match="not in sidecar"):
        eng.load_test(tmp_path, {**spec, "features": ["nihss_raw"]}, cfg, ids)


def test_registry_config_matches_frozen_tables_without_labels():
    qc = pd.read_csv(ROOT / "features/v3/epoch_qc_v3.csv", usecols=["subject_id", "include_v3_epochs"])
    main = sorted(qc.loc[qc["include_v3_epochs"].astype(str) == "True", "subject_id"])
    meta = pd.read_csv(ROOT / "features/v3/subject_meta_v3.csv", usecols=["subject_id", "lesion_side_final"])
    lesion = sorted(meta.loc[meta["subject_id"].isin(main) & meta["lesion_side_final"].isin(["left", "right"]), "subject_id"])
    assert CFG["cohort"]["main"] == main and CFG["cohort"]["lesion"] == lesion
    assert len(main) == 45 and len(lesion) == 38
    for spec in CFG["tests"]:
        feats = eng.feature_list(ROOT, spec)
        table = pd.read_csv(ROOT / spec["table"], usecols=["subject_id", *feats]).set_index("subject_id")
        cohort = CFG["cohort"][spec["cohort"]]
        assert set(cohort) <= set(table.index) and not table.loc[cohort].isna().any().any()
        assert len(cohort) == spec["expected_n"]
    assert [t["id"] for t in CFG["tests"]] == ["V1", "V2", "V3", "V4"] and len(CFG["tests"][3]["features"]) == 8
    manifest = json.loads((ROOT / "features/v3/MANIFEST.json").read_text())
    assert runner.check_manifest(manifest, ROOT, label_sha=CFG["labels"]["sha256_lf"]) == 50   # 14 tables + 12 sidecars + 12 config copies + 11 QC + label
