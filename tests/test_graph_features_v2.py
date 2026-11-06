"""Synthetic acceptance tests for graph_features_v2."""

from __future__ import annotations

import copy
import unittest

import mne
import numpy as np

from src.graph_features_v2 import (
    _feature_from_adjacency,
    _weighted_clustering,
    _weighted_global_efficiency,
    _wpli_adjacency,
    compute_graph_features,
    screen_epochs,
)


CONFIG = {
    "name": "g8f",
    "channels": ["F3", "C3", "P3", "O1", "F4", "C4", "P4", "O2"],
    "left_nodes": ["F3", "C3", "P3", "O1"],
    "right_nodes": ["F4", "C4", "P4", "O2"],
    "pair_map": [0, 1, 2, 3],
    "n_fixed": 6,
    "subsamples": 3,
    "subject_index": 0,
}


class GraphFeaturesV2Tests(unittest.TestCase):
    def test_symmetric_network_has_zero_asymmetry(self) -> None:
        block = np.array(
            [[0.0, 0.8, 0.6, 0.4], [0.8, 0.0, 0.5, 0.3], [0.6, 0.5, 0.0, 0.7], [0.4, 0.3, 0.7, 0.0]]
        )
        adjacency = np.block([[block, block], [block, block]])
        features = _feature_from_adjacency(adjacency, CONFIG, "alpha")
        self.assertAlmostEqual(features["g8f_alpha_GlobalEff_absAI"], 0.0)
        self.assertAlmostEqual(features["g8f_alpha_ClustCoeff_absAI"], 0.0)
        self.assertAlmostEqual(features["g8f_alpha_FrobeniusDist"], 0.0)

    def test_swapping_hemispheres_preserves_sign_invariant_features(self) -> None:
        left = np.array(
            [[0.0, 0.8, 0.4, 0.2], [0.8, 0.0, 0.6, 0.3], [0.4, 0.6, 0.0, 0.5], [0.2, 0.3, 0.5, 0.0]]
        )
        right = np.array(
            [[0.0, 0.3, 0.5, 0.7], [0.3, 0.0, 0.4, 0.6], [0.5, 0.4, 0.0, 0.2], [0.7, 0.6, 0.2, 0.0]]
        )
        cross = np.full((4, 4), 0.4)
        original = _feature_from_adjacency(np.block([[left, cross], [cross.T, right]]), CONFIG, "alpha")
        swapped = _feature_from_adjacency(np.block([[right, cross.T], [cross, left]]), CONFIG, "alpha")
        self.assertEqual(original, swapped)

    def test_known_graph_metrics(self) -> None:
        complete = np.ones((4, 4), dtype=float) - np.eye(4)
        self.assertAlmostEqual(_weighted_global_efficiency(complete), 1.0)
        self.assertAlmostEqual(_weighted_clustering(complete), 1.0)

    def test_wpli_matches_direct_formula(self) -> None:
        rng = np.random.default_rng(7)
        spectra = rng.normal(size=(9, 2, 10)) + 1j * rng.normal(size=(9, 2, 10))
        frequencies = np.arange(10, dtype=float)
        result = _wpli_adjacency(spectra, frequencies, np.arange(9), 2.0, 7.0)
        imaginary = np.imag(spectra[:, 0, 2:8] * np.conj(spectra[:, 1, 2:8]))
        expected = np.mean(
            np.divide(
                abs(imaginary.sum(axis=0)),
                np.abs(imaginary).sum(axis=0),
                out=np.zeros(imaginary.shape[1]),
                where=np.abs(imaginary).sum(axis=0) > 0,
            )
        )
        self.assertAlmostEqual(result[0, 1], expected)

    def test_epoch_order_is_invariant_and_n_fixed_is_enforced(self) -> None:
        rng = np.random.default_rng(12)
        data = rng.normal(scale=1e-6, size=(8, 8, 2000))
        info = mne.create_info(CONFIG["channels"], sfreq=500.0, ch_types="eeg")
        epochs = mne.EpochsArray(data, info, verbose=False)
        permuted = epochs[np.array([5, 0, 7, 2, 1, 6, 3, 4])]
        first = compute_graph_features(epochs, CONFIG)
        second = compute_graph_features(permuted, CONFIG)
        self.assertEqual(first, second)
        too_large = copy.deepcopy(CONFIG)
        too_large["n_fixed"] = 9
        with self.assertRaises(ValueError):
            compute_graph_features(epochs, too_large)

    def test_artifact_screen_is_applied_to_sampling_pool(self) -> None:
        rng = np.random.default_rng(21)
        data = rng.normal(scale=1e-6, size=(7, 8, 2000))
        data[0, 0, 0] = 200e-6
        data[0, 0, 1] = -200e-6
        info = mne.create_info(CONFIG["channels"], sfreq=500.0, ch_types="eeg")
        epochs = mne.EpochsArray(data, info, verbose=False)
        screened = screen_epochs(epochs, CONFIG["channels"], 150.0)
        self.assertEqual(len(screened), 6)
        from_full = compute_graph_features(epochs, CONFIG)
        from_screened = compute_graph_features(screened, CONFIG)
        self.assertEqual(from_full, from_screened)


if __name__ == "__main__":
    unittest.main()
