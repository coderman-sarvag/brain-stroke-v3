"""Synthetic tests for Step 4 connectivity helpers (no real EEG, no labels)."""
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import connectivity_v3 as cv  # noqa: E402

CFG = json.loads((ROOT / "configs/v3/connectivity.json").read_text(encoding="utf-8"))


def test_segments_split_each_epoch_in_order():
    data = np.arange(3 * 2 * 2000, dtype=float).reshape(3, 2, 2000)
    seg = cv.make_segments(data, CFG)
    assert seg.shape == (6, 2, 1000)
    assert np.array_equal(seg[0], data[0, :, :1000]) and np.array_equal(seg[1], data[0, :, 1000:])
    assert np.array_equal(seg[5], data[2, :, 1000:])
    with pytest.raises(ValueError):
        cv.make_segments(np.zeros((2, 2, 1500)), CFG)


def test_bins_per_band_match_config():
    assert cv.bins_per_band(500.0, 1000, CFG) == CFG["expected_bins_per_band"]


def test_derangement_has_no_fixed_points():
    rng = np.random.default_rng(0)
    for n in (2, 5, 80):
        p = cv.derangement(rng, n)
        assert sorted(p) == list(range(n)) and not np.any(p == np.arange(n))


def test_edge_status_rules():
    assert cv.edge_status("O1", "C3", {"O1", "O2"}, set(), set()) == ("unavailable_channel", None)
    assert cv.edge_status("T7", "C3", set(), {"T7", "T8"}, {"T7", "T8"})[0] == "pair_both_interpolated"
    assert cv.edge_status("C3", "P4", set(), set(), {"C3", "P4"}) == ("both_endpoints_interpolated", 2)
    assert cv.edge_status("C3", "P4", set(), set(), {"C3"}) == (None, 1)
    assert cv.edge_status("C3", "P4", set(), set(), set()) == (None, 0)


def test_edge_list_and_columns():
    assert len(cv.edge_list(CFG["channel_sets"]["extended"])) == 231
    assert len(cv.feature_columns(CFG["channel_sets"]["core"], list(CFG["bands"]))) == 112
    assert ("F3", "F4") in cv.edge_list(CFG["channel_sets"]["core"])


def test_wpli_detects_lagged_coupling_and_not_independence():
    rng = np.random.default_rng(1)
    n_seg, n_t, lag = 100, 1000, 12            # 24 ms lag: phase about 1.2-1.9 rad across 8-12.5 Hz (alpha)
    x = rng.standard_normal((n_seg, n_t + lag))
    coupled = np.stack([x[:, lag:], x[:, :-lag] + 0.3 * rng.standard_normal((n_seg, n_t))], axis=1)
    independent = rng.standard_normal((n_seg, 2, n_t))
    w_c = cv.wpli(coupled, 500.0, [0], [1], CFG)[0]
    w_i = cv.wpli(independent, 500.0, [0], [1], CFG)[0]
    alpha = list(CFG["bands"]).index("alpha")
    assert w_c[alpha] > 0.3                    # consistent non-zero phase lag -> high debiased wPLI
    assert np.all(np.abs(w_i) < 0.1)           # independent signals -> about 0 in every band


def test_homotopic_summary_exceedance():
    surr = np.zeros((200, 2, 4))
    surr[:, :, :] = np.linspace(0, 0.1, 200)[:, None, None]
    observed = np.array([[0.5] * 4, [0.0] * 4])
    rows = cv.homotopic_summary(observed, surr, ["A-B", "C-D"], ["delta", "theta", "alpha", "beta"], 95)
    by = {(r["pair"], r["band"]): r for r in rows}
    assert by[("A-B", "alpha")]["exceeds"] and not by[("C-D", "alpha")]["exceeds"]
    assert by[("MEAN", "beta")]["observed"] == pytest.approx(0.25) and by[("MEAN", "beta")]["exceeds"]
