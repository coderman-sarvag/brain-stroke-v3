"""Synthetic tests for Step 3 spectral features (no real EEG, no labels)."""
import json
from pathlib import Path
import sys

import mne
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import spectral_v3 as sp  # noqa: E402

CFG = json.loads((ROOT / "configs/v3/spectral.json").read_text(encoding="utf-8"))
SF, N = 500.0, 2000
ANALYSED = [c for p in CFG["pairs"] for c in p]
EEG = ANALYSED + ["Fp1", "Fp2", "Cz", "CPz"]
EVENT_ID = {"left_hand": 1, "right_hand": 2}


def make_epochs(classes, builder, bads=(), seed=0):
    """EpochsArray whose EEG data come from builder(rng, n_epochs) -> dict channel -> (n_epochs, N)."""
    rng = np.random.default_rng(seed)
    n = len(classes)
    signals = builder(rng, n)
    data = np.stack([signals.get(c, 1e-6 * rng.standard_normal((n, N))) for c in EEG] +
                    [1e-6 * rng.standard_normal((n, N))], axis=1)
    info = mne.create_info(EEG + ["HEOL"], SF, ["eeg"] * len(EEG) + ["eog"])
    events = np.column_stack([np.arange(n) * 4000, np.zeros(n, int), classes])
    epochs = mne.EpochsArray(data, info, events=events, event_id=EVENT_ID, verbose="ERROR")
    epochs.info["bads"] = list(bads)
    return epochs


def run_features(epochs, interpolated=()):
    eeg = epochs.copy().pick("eeg", exclude=[])
    psd, freqs = sp.compute_psd(eeg.get_data(), SF, CFG)
    status = sp.pair_status(eeg.ch_names, set(eeg.info["bads"]), set(interpolated), CFG["pairs"])
    feats = sp.epoch_features(psd, freqs, eeg.ch_names, status, CFG)
    return {c: sp.class_balanced(v, epochs.events[:, 2]) for c, v in feats.items()}, status


def scaled_pairs(scale_by_pair):
    def builder(rng, n):
        out = {}
        for (left, right), scale in scale_by_pair.items():
            x = 1e-5 * rng.standard_normal((n, N))
            out[left], out[right] = scale * x, x
        return out
    return builder


def test_bins_per_band_meet_minimum_and_short_epochs_are_refused():
    _, freqs = sp.compute_psd(np.random.default_rng(0).standard_normal((1, 1, N)), SF, CFG)
    masks = sp.band_masks(freqs, CFG)
    assert {b: int(m.sum()) for b, m in masks.items()} == CFG["expected_bins_per_band"]
    _, short = sp.compute_psd(np.random.default_rng(0).standard_normal((1, 1, 500)), SF, CFG)  # 1 s epoch
    with pytest.raises(ValueError, match="fewer than 6"):
        sp.band_masks(short, CFG)


def test_known_asymmetry_and_symmetric_pair():
    epochs = make_epochs([1, 2] * 10, scaled_pairs({("F3", "F4"): 2.0, ("C3", "C4"): 1.0}))
    f, _ = run_features(epochs)
    for band in CFG["bands"]:
        assert f[f"AI_{band}_F3F4"] == pytest.approx(0.6, abs=1e-9)        # power ratio 4: (4-1)/(4+1)
        assert f[f"LR_{band}_F3F4"] == pytest.approx(np.log(4), abs=1e-9)
        assert f[f"absAI_{band}_F3F4"] == pytest.approx(0.6, abs=1e-9)
        assert f[f"AI_{band}_C3C4"] == pytest.approx(0.0, abs=1e-12)
        assert f[f"LR_{band}_C3C4"] == pytest.approx(0.0, abs=1e-12)


def test_fully_symmetric_montage_gives_zero_global_asymmetry():
    epochs = make_epochs([1, 2] * 5, scaled_pairs({tuple(p): 1.0 for p in CFG["pairs"]}))
    f, _ = run_features(epochs)
    assert f["pdBSI"] == pytest.approx(0.0, abs=1e-12)
    assert all(f[f"mabsAI_{b}"] == pytest.approx(0.0, abs=1e-12) for b in CFG["bands"])


def test_class_balanced_average_weights_classes_equally():
    classes = np.array([1] * 30 + [2] * 10)

    def builder(rng, n):
        x = 1e-5 * rng.standard_normal((n, N))
        scale = np.where(classes == 1, 2.0, 1.0)[:, None]   # class 1: AI 0.6, class 2: AI 0
        return {"F3": scale * x, "F4": x}

    f, _ = run_features(make_epochs(classes, builder))
    assert f["AI_alpha_F3F4"] == pytest.approx(0.3, abs=1e-9)          # not the epoch-weighted 0.45
    assert sp.class_balanced(np.array([1.0, 1.0, 1.0, 3.0]), np.array([1, 1, 1, 2])) == 2.0
    with pytest.raises(ValueError):
        sp.class_balanced(np.ones(3), np.array([1, 1, 1]))


def test_missing_pair_rules():
    epochs = make_epochs([1, 2] * 5, scaled_pairs({("F3", "F4"): 2.0}), bads=["O1", "O2"])
    f, status = run_features(epochs, interpolated={"T7", "T8", "C3"})
    assert status["O1O2"] == "unavailable" and status["T7T8"] == "both_interpolated" and status["C3C4"] is None
    for band in CFG["bands"]:
        assert np.isnan(f[f"AI_{band}_O1O2"]) and np.isnan(f[f"LR_{band}_T7T8"]) and np.isnan(f[f"absAI_{band}_T7T8"])
        assert np.isfinite(f[f"AI_{band}_C3C4"])
    assert np.isfinite([f["pdBSI"], f["DAR"], f["DTABR"], *(f[f"mabsAI_{b}"] for b in CFG["bands"])]).all()


def test_dar_and_dtabr_from_known_sinusoids():
    t = np.arange(N) / SF

    def builder(rng, n):
        s = 2e-5 * np.sin(2 * np.pi * 2.0 * t) + 1e-5 * np.sin(2 * np.pi * 10.0 * t)   # delta:alpha power 4:1
        return {c: np.tile(s, (n, 1)) + 1e-8 * rng.standard_normal((n, N)) for c in ANALYSED}

    f, _ = run_features(make_epochs([1, 2] * 3, builder))
    assert f["DAR"] == pytest.approx(4.0, rel=0.02)
    assert f["DTABR"] == pytest.approx(4.0, rel=0.02)


def test_lesion_alignment_sign_and_rows(tmp_path):
    cols = sp.feature_columns(CFG)
    feats = pd.DataFrame([{"subject_id": s, **{c: 0.0 for c in cols}} for s in ("sub-01", "sub-02", "sub-03")])
    feats.loc[:, "AI_alpha_C3C4"] = [0.2, 0.2, 0.2]
    feats.loc[:, "LR_alpha_C3C4"] = [0.5, 0.5, 0.5]
    feats.loc[1, "AI_beta_O1O2"] = np.nan
    meta = tmp_path / "meta.csv"
    pd.DataFrame({"subject_id": ["sub-01", "sub-02", "sub-03"], "lesion_side_final": ["left", "right", "uncertain"],
                  "sex": ["m", "f", "m"]}).to_csv(meta, index=False)
    les = sp.lesion_table(feats, meta, CFG).set_index("subject_id")
    assert list(les.index) == ["sub-01", "sub-02"]                     # uncertain side: no row
    assert les.loc["sub-01", "les_AI_alpha_C3C4"] == 0.2 and les.loc["sub-02", "les_AI_alpha_C3C4"] == -0.2
    assert les.loc["sub-02", "les_LR_alpha_C3C4"] == -0.5
    assert les.loc["sub-02", "les_meanAI_alpha"] == pytest.approx(-0.2 / 11)
    assert np.isnan(les.loc["sub-02", "les_AI_beta_O1O2"])             # NaN stays NaN


def test_check_table_rejects_contract_violations():
    cols = ["AI_alpha_F3F4"]
    with pytest.raises(RuntimeError):
        sp.check_table(pd.DataFrame({"subject_id": ["a"], "AI_alpha_F3F4": [0.1], "nihss_raw": [3]}), cols)
    with pytest.raises(RuntimeError):
        sp.check_table(pd.DataFrame({"subject_id": ["a"], "AI_alpha_F3F4": [np.inf]}), cols)


def test_main_end_to_end_on_synthetic_step2_output(tmp_path):
    prev, out = tmp_path / "prev", tmp_path / "out"
    edir = prev / "data/processed/figshare_v3"
    edir.mkdir(parents=True)
    make_epochs([1, 2] * 6, scaled_pairs({("F3", "F4"): 2.0}), seed=1).save(edir / "sub-01-epo.fif", verbose="ERROR")
    make_epochs([1, 1, 2] * 4, scaled_pairs({("C3", "C4"): 3.0}), bads=["O1", "O2"], seed=2).save(edir / "sub-02-epo.fif", verbose="ERROR")
    (prev / "features/v3").mkdir(parents=True)
    pd.DataFrame({"subject_id": ["sub-01", "sub-02", "sub-03"], "include_v3_epochs": [True, True, False],
                  "interpolated": ["T7", "", ""], "screen_interpolated": ["T8", "", ""],
                  "unavailable_pairs_final": ["", "O1-O2", ""], "n_epochs_kept": [12, 12, 5],
                  "n_left_kept": [6, 8, 1], "n_right_kept": [6, 4, 4]}).to_csv(prev / "features/v3/epoch_qc_v3.csv", index=False)
    pd.DataFrame({"subject_id": ["sub-01", "sub-02", "sub-03"], "lesion_side_final": ["right", "uncertain", "left"],
                  "exclude_v3": [False, False, False]}).to_csv(prev / "features/v3/subject_meta_v3.csv", index=False)

    assert sp.main(["--prev-root", str(prev), "--out-root", str(out), "--data-root", str(tmp_path / "unused"),
                    "--n-jobs", "1"]) == 0
    feats = pd.read_csv(out / "features/v3/spectral_v3.csv")
    assert list(feats.columns) == ["subject_id", *sp.feature_columns(CFG)] and list(feats["subject_id"]) == ["sub-01", "sub-02"]
    f = feats.set_index("subject_id")
    assert f.loc["sub-01", "AI_alpha_F3F4"] == pytest.approx(0.6, abs=1e-9)
    assert np.isnan(f.loc["sub-01", "AI_alpha_T7T8"])                 # T7 and T8 interpolated at different stages
    assert np.isnan(f.loc["sub-02", "AI_alpha_O1O2"])
    assert f.loc["sub-02", "AI_alpha_C3C4"] == pytest.approx(0.8, abs=1e-9)   # power ratio 9: 8/10
    les = pd.read_csv(out / "features/v3/spectral_lesion_v3.csv").set_index("subject_id")
    assert list(les.index) == ["sub-01"] and les.loc["sub-01", "les_AI_alpha_F3F4"] == pytest.approx(-0.6, abs=1e-9)
    meta = json.loads((out / "features/v3/spectral_v3.meta.json").read_text())
    assert meta["columns"] == list(feats.columns) and meta["provenance"]["config_sha256"]
    summary = json.loads((out / "results/v3/step3/spectral_summary.json").read_text())["summary"]
    assert summary["bins_per_band"] == CFG["expected_bins_per_band"] and summary["unexpected_nan"] == []
    assert summary["unavailable_cross_check_ok"] and summary["lesion_rows_excluded_uncertain_side"] == ["sub-02"]
    assert ["sub-01", "T7T8"] in summary["nan_pairs"] and ["sub-02", "O1O2"] in summary["nan_pairs"]
