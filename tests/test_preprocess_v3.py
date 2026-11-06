"""Synthetic tests for Step 2 preprocessing (no real EEG, no labels)."""
import copy
import json
from pathlib import Path
import sys

import mne
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from preprocess_v3 import (apply_screen, channel_exceedance, class_counts, detect_bad_channels,  # noqa: E402
                           ica_allowed, is_done, main, make_epochs, rereference_and_interpolate, run_ica,
                           subject_events, unavailable_pairs)

CFG = json.loads((ROOT / "configs/v3/preprocess.json").read_text(encoding="utf-8"))
PAIRS = CFG["channels"]["homologous_pairs"]
SF = 500.0
EEG = ["Fp1", "Fp2", "Fz", "F3", "F4", "F7", "F8", "FC3", "FC4", "Cz", "C3", "C4", "T7", "T8", "CPz",
       "CP3", "CP4", "Pz", "P3", "P4", "P7", "P8", "O1", "O2"]


def synthetic_raw(seconds=60, seed=0, eog=False):
    """Spatially smooth synthetic EEG (few dipole-like sources) with CPz as an all-zero reference."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SF)
    info = mne.create_info(EEG + (["HEOL", "HEOR"] if eog else []), SF,
                           ["eeg"] * len(EEG) + (["eog", "eog"] if eog else []))
    raw = mne.io.RawArray(np.zeros((len(info.ch_names), n)), info, verbose="ERROR")
    raw.set_montage("standard_1020", on_missing="ignore")
    pos = np.array([raw.info["chs"][i]["loc"][:3] for i in range(len(EEG))])
    sources = rng.standard_normal((6, n)).cumsum(axis=1)
    sources -= np.convolve(sources.mean(0), np.ones(250) / 250, "same")
    centres = rng.standard_normal((6, 3)) * 0.05
    gain = np.exp(-((pos[:, None, :] - centres[None]) ** 2).sum(-1) / 0.006)
    data = gain @ (sources * 2e-6) + 1e-6 * rng.standard_normal((len(EEG), n))
    data[EEG.index("CPz")] = 0.0
    raw._data[: len(EEG)] = data
    return raw


def test_unavailable_pairs():
    assert unavailable_pairs(["O1", "O2", "F3"], PAIRS) == [["O1", "O2"]]
    assert unavailable_pairs(["F3"], PAIRS) == []


def test_reference_interpolation_and_pair_rule():
    raw = synthetic_raw()
    raw, interpolated, unavailable, min_sd = rereference_and_interpolate(raw, ["F3", "O1", "O2"], PAIRS, CFG)
    assert interpolated == ["F3"]
    assert unavailable == [["O1", "O2"]]
    assert raw.info["bads"] == ["O1", "O2"]
    assert raw.get_data(picks=["CPz"]).std() > 0            # CPz carries data after re-referencing
    good = [c for c in EEG if c not in ("O1", "O2")]
    assert np.allclose(raw.get_data(picks=good).mean(axis=0), 0, atol=1e-12)  # average reference
    assert min_sd > 0


def test_zero_good_channel_is_refused():
    raw = synthetic_raw()
    raw._data[:] = 0.0  # every channel zero, so a zero channel would feed the interpolation
    with pytest.raises(RuntimeError):
        rereference_and_interpolate(raw, ["F3"], PAIRS, CFG)


def test_bad_channel_detection_ignores_reference_and_finds_flat_and_noisy():
    raw = synthetic_raw(seed=1)
    raw._data[EEG.index("C4")] = 0.0                       # flat
    raw._data[EEG.index("P7")] += 3e-4 * np.random.default_rng(2).standard_normal(raw.n_times)  # very noisy
    cfg = copy.deepcopy(CFG)
    cfg["bad_channels"]["ransac"] = False
    bads, by_type = detect_bad_channels(raw, cfg)
    assert "C4" in bads and "P7" in bads
    assert "CPz" not in bads


def test_events_and_epochs_from_marker_onsets():
    marker = pd.DataFrame({"subject_id": ["s"] * 4, "marker_index": range(4), "sidecar_trial": [0, 1, -1, 2],
                           "marker_onset": [1000, 5003, 7000, 9010], "lag_samples": [0, 3, np.nan, 10],
                           "trial_type": [1.0, 2.0, np.nan, 1.0], "usable": [True, True, False, True]})
    events, meta = subject_events(marker, "s", CFG["epochs"]["event_id"])
    assert events[:, 0].tolist() == [1000, 5003, 9010] and events[:, 2].tolist() == [1, 2, 1]
    info = mne.create_info(["Cz", "HEOL"], SF, ["eeg", "eog"])
    ramp = np.arange(20000, dtype=float) * 1e-9
    raw = mne.io.RawArray(np.vstack([ramp, ramp]), info, verbose="ERROR")
    epochs = make_epochs(raw, events, meta, CFG)
    data = epochs.get_data(picks=["Cz"])[:, 0]
    assert data.shape == (3, 2000)
    assert np.allclose(data[:, 0], np.array([1000, 5003, 9010]) * 1e-9)
    assert epochs.metadata["sidecar_trial"].tolist() == [0, 1, 2]
    assert epochs.metadata["hand"].tolist() == ["left_hand", "right_hand", "left_hand"]  # class saved per epoch
    assert class_counts(epochs, CFG["epochs"]["event_id"]) == {"total": 3, "left": 2, "right": 1}


def screen_epochs():
    """40 epochs (alternating classes) with planted 400 uV artifacts:
    Fp1 in epochs 0-5, T7 in 6-20 (37.5% of epochs), O1 and O2 together in 21-33 (32.5%)."""
    names = CFG["channels"]["analysed_channels"] + ["Fp1", "Cz", "CPz"]
    info = mne.create_info(names + ["HEOL"], SF, ["eeg"] * len(names) + ["eog"])
    rng = np.random.default_rng(5)
    data = 5e-6 * rng.standard_normal((40, len(names) + 1, 2000))
    spike = 4e-4 * np.hanning(2000)
    for chans, idx in ((["Fp1"], range(0, 6)), (["T7"], range(6, 21)), (["O1", "O2"], range(21, 34))):
        for c in chans:
            data[list(idx), names.index(c)] += spike
    events = np.column_stack([np.arange(40) * 4000, np.zeros(40, int), np.tile([1, 2], 20)])
    epochs = mne.EpochsArray(data, info, events=events, event_id=CFG["epochs"]["event_id"], verbose="ERROR")
    epochs.set_montage("standard_1020")
    return epochs


def test_screen_rules_on_planted_artifacts():
    epochs = screen_epochs()
    ids = CFG["epochs"]["event_id"]
    exceed = channel_exceedance(epochs, ["Fp1", "T7", "O1", "C3"], CFG["epochs"]["peak_to_peak_volts"])
    assert exceed == pytest.approx({"Fp1": 6 / 40, "T7": 15 / 40, "O1": 13 / 40, "C3": 0.0})
    kept_all, _ = apply_screen(epochs, "all_scalp", CFG)
    kept_analysed, _ = apply_screen(epochs, "analysed", CFG)
    kept_marked, details = apply_screen(epochs, "analysed_after_marking", CFG)
    assert class_counts(kept_all, ids)["total"] == 40 - 6 - 15 - 13
    assert class_counts(kept_analysed, ids)["total"] == 40 - 15 - 13          # Fp1 not screened
    assert details["marked"] == ["O1", "O2", "T7"]
    assert details["interpolated_on_epochs"] == ["T7"]                        # partner T8 is good
    assert details["new_unavailable_pairs"] == [["O1", "O2"]]                 # both marked -> not interpolated
    assert class_counts(kept_marked, ids) == {"total": 40, "left": 20, "right": 20}
    assert len(epochs) == 40 and epochs.info["bads"] == []                    # input epochs unchanged


def test_bad_channel_guard():
    assert ica_allowed(9, CFG) and not ica_allowed(10, CFG)


def test_final_mode_refuses_until_screen_rule_chosen():
    assert CFG["epochs"]["final_screen_rule"] not in CFG["epochs"]["screen_rules"]
    with pytest.raises(SystemExit, match="final_screen_rule"):
        main(["--mode", "final"])


def test_is_done_requires_ok_status_same_mode_and_config(tmp_path):
    path = tmp_path / "sub-01.json"
    assert not is_done(path, "diagnostic", "abc")
    path.write_text(json.dumps({"status": "ok", "mode": "diagnostic", "config_sha256": "abc"}))
    assert is_done(path, "diagnostic", "abc")
    assert not is_done(path, "final", "abc") and not is_done(path, "diagnostic", "other")
    path.write_text(json.dumps({"status": "error", "mode": "diagnostic", "config_sha256": "abc"}))
    assert not is_done(path, "diagnostic", "abc")


def test_ica_removes_component_flagged_by_eog_channel():
    rng = np.random.default_rng(3)
    raw = synthetic_raw(seconds=120, seed=3, eog=True)
    n = raw.n_times
    blinks = np.zeros(n)
    for t in rng.choice(n - 200, 60, replace=False):
        blinks[t:t + 200] += np.hanning(200)
    eog = 1e-4 * blinks
    frontal = [EEG.index(c) for c in ("Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8")]
    raw._data[frontal] += np.outer(np.linspace(0.6, 0.2, len(frontal)), eog)
    raw._data[len(EEG)] = eog + 1e-6 * rng.standard_normal(n)
    raw._data[len(EEG) + 1] = 1e-6 * rng.standard_normal(n)  # second EOG channel carries no ocular signal
    raw.filter(1, 40, picks=["eeg", "eog"], verbose="ERROR")
    raw.set_eeg_reference("average", projection=False, verbose="ERROR")
    cfg = copy.deepcopy(CFG)
    # >= 11 components needed: with n scores the largest attainable z is (n-1)/sqrt(n) (< 3 for n = 10).
    cfg["ica"]["n_components"] = 20
    before = abs(np.corrcoef(raw.get_data(picks=["Fp1"])[0], raw.get_data(picks=["HEOL"])[0])[0, 1])
    cleaned, ica, n_comp, flagged, excluded = run_ica(raw, 0, cfg)
    after = abs(np.corrcoef(cleaned.get_data(picks=["Fp1"])[0], cleaned.get_data(picks=["HEOL"])[0])[0, 1])
    assert flagged["HEOL"] and set(flagged) == {"HEOL", "HEOR"}
    assert excluded == sorted(set(flagged["HEOL"]) | set(flagged["HEOR"]))
    assert before > 0.5 and after < before / 2
