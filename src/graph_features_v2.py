"""Fixed-epoch, sign-invariant graph features for the v2 analysis.

This module is label-blind. It accepts an MNE Epochs object and a JSON-like
configuration, computes FFT-based per-epoch cross-spectra, samples a fixed
number of epochs without replacement, and returns median graph features.
"""

from __future__ import annotations

import hashlib
from typing import Any

import networkx as nx
import numpy as np


BANDS: dict[str, tuple[float, float]] = {
    "delta": (1.0, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
}


def _safe_ratio_difference(left: float, right: float) -> float:
    denominator = left + right
    if denominator <= 0.0 or not np.isfinite(denominator):
        return 0.0
    return float(abs(left - right) / denominator)


def _weighted_global_efficiency(adjacency: np.ndarray) -> float:
    """Calculate weighted efficiency using distance=1/weight."""
    size = adjacency.shape[0]
    if size < 2:
        return 0.0
    graph = nx.from_numpy_array(adjacency, create_using=nx.Graph())
    for left, right, data in graph.edges(data=True):
        weight = float(data.get("weight", 0.0))
        data["distance"] = 1.0 / max(weight, np.finfo(float).eps)
    total = 0.0
    for source in graph.nodes:
        distances = nx.single_source_dijkstra_path_length(graph, source, weight="distance")
        for target, distance in distances.items():
            if target != source and np.isfinite(distance) and distance > 0.0:
                total += 1.0 / distance
    return float(total / (size * (size - 1)))


def _weighted_clustering(adjacency: np.ndarray) -> float:
    """Calculate the mean Onnela weighted clustering coefficient."""
    if adjacency.shape[0] < 3:
        return 0.0
    graph = nx.from_numpy_array(adjacency, create_using=nx.Graph())
    graph.remove_edges_from(nx.selfloop_edges(graph))
    values = list(nx.clustering(graph, weight="weight").values())
    return float(np.mean(values)) if values else 0.0


def _epoch_fingerprint(epoch: np.ndarray) -> bytes:
    """Return an order-independent fingerprint for deterministic sampling."""
    contiguous = np.ascontiguousarray(epoch, dtype=np.float64)
    return hashlib.blake2b(contiguous.tobytes(), digest_size=16).digest()


def screen_epochs(epochs: Any, channels: list[str], threshold_uv: float) -> Any:
    """Return only epochs passing the configured peak-to-peak screen."""
    missing = [channel for channel in channels if channel not in epochs.ch_names]
    if missing:
        raise ValueError(f"Missing screening channels: {missing}")
    indices = [epochs.ch_names.index(channel) for channel in channels]
    threshold_v = float(threshold_uv) * 1e-6
    peak_to_peak = np.ptp(epochs.get_data()[:, indices, :], axis=2)
    keep = ~(peak_to_peak > threshold_v).any(axis=1)
    return epochs[keep]


def _cross_spectra(data: np.ndarray, sfreq: float) -> tuple[np.ndarray, np.ndarray]:
    """Compute windowed FFT coefficients after canonicalizing epoch order."""
    if data.ndim != 3:
        raise ValueError(f"Expected (epochs, channels, samples), got {data.shape}")
    order = sorted(range(data.shape[0]), key=lambda index: _epoch_fingerprint(data[index]))
    canonical = data[order].astype(float, copy=False)
    centered = canonical - canonical.mean(axis=2, keepdims=True)
    window = np.hanning(canonical.shape[2])
    coefficients = np.fft.rfft(centered * window[None, None, :], axis=2)
    frequencies = np.fft.rfftfreq(canonical.shape[2], d=1.0 / sfreq)
    return coefficients, frequencies


def _wpli_adjacency(
    spectra: np.ndarray,
    frequencies: np.ndarray,
    epoch_indices: np.ndarray,
    fmin: float,
    fmax: float,
) -> np.ndarray:
    """Compute band-averaged wPLI from a fixed epoch subset."""
    selected = spectra[epoch_indices]
    frequency_mask = (frequencies >= fmin) & (frequencies <= fmax)
    if not np.any(frequency_mask):
        raise ValueError(f"No FFT bins in band {fmin}-{fmax} Hz")
    selected = selected[:, :, frequency_mask]
    cross_spectrum = selected[:, :, None, :] * np.conj(selected[:, None, :, :])
    imaginary = np.imag(cross_spectrum)
    numerator = np.abs(np.sum(imaginary, axis=0))
    denominator = np.sum(np.abs(imaginary), axis=0)
    adjacency = np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator, dtype=float),
        where=denominator > 0.0,
    )
    adjacency = np.mean(adjacency, axis=2)
    adjacency = np.maximum(adjacency, adjacency.T)
    np.fill_diagonal(adjacency, 0.0)
    return np.clip(adjacency, 0.0, 1.0)


def _feature_from_adjacency(adjacency: np.ndarray, config: dict[str, Any], band: str) -> dict[str, float]:
    """Calculate the four canonical features for one median adjacency."""
    left_nodes = list(config["left_nodes"])
    right_nodes = list(config["right_nodes"])
    node_count = len(left_nodes)
    left = adjacency[:node_count, :node_count]
    right = adjacency[node_count:, node_count:]
    pair_map = list(config["pair_map"])
    aligned_right = right[np.ix_(pair_map, pair_map)]
    global_eff_left = _weighted_global_efficiency(left)
    global_eff_right = _weighted_global_efficiency(right)
    clustering_left = _weighted_clustering(left)
    clustering_right = _weighted_clustering(right)
    homotopic = [adjacency[index, node_count + pair_map[index]] for index in range(node_count)]
    frobenius_denominator = np.linalg.norm(left, "fro") + np.linalg.norm(aligned_right, "fro")
    frobenius = 0.0 if frobenius_denominator == 0.0 else float(
        np.linalg.norm(left - aligned_right, "fro") / frobenius_denominator
    )
    prefix = str(config["name"])
    return {
        f"{prefix}_{band}_GlobalEff_absAI": _safe_ratio_difference(global_eff_left, global_eff_right),
        f"{prefix}_{band}_ClustCoeff_absAI": _safe_ratio_difference(clustering_left, clustering_right),
        f"{prefix}_{band}_MeanHomotopic": float(np.mean(homotopic)),
        f"{prefix}_{band}_FrobeniusDist": frobenius,
    }


def compute_graph_features(epochs: Any, config: dict[str, Any]) -> dict[str, float]:
    """Compute fixed-epoch median graph features for one subject."""
    sfreq = float(epochs.info["sfreq"])
    if abs(sfreq - 500.0) > 1.0:
        raise ValueError(f"Expected approximately 500 Hz, got {sfreq}")
    channels = list(config["channels"])
    screened_epochs = screen_epochs(
        epochs,
        channels,
        float(config.get("artifact_threshold_uv", 150.0)),
    )
    n_fixed = int(config["n_fixed"])
    subsamples = int(config["subsamples"])
    if n_fixed < 1 or len(screened_epochs) < n_fixed:
        raise ValueError(f"Need {n_fixed} screened epochs, got {len(screened_epochs)}")
    if subsamples < 1:
        raise ValueError("subsamples must be positive")

    ordered_epochs = screened_epochs.copy().pick(channels).reorder_channels(channels)
    data = ordered_epochs.get_data()
    spectra, frequencies = _cross_spectra(data, sfreq)
    rng = np.random.default_rng(
        int(config.get("seed_base", 42)) + int(config.get("subject_index", 0))
    )
    feature_values: dict[str, list[float]] = {}
    for band, (fmin, fmax) in BANDS.items():
        band_adjacencies = []
        for _ in range(subsamples):
            indices = rng.choice(len(spectra), size=n_fixed, replace=False)
            band_adjacencies.append(_wpli_adjacency(spectra, frequencies, indices, fmin, fmax))
        median_adjacency = np.median(np.stack(band_adjacencies), axis=0)
        feature_values.update(
            {name: [value] for name, value in _feature_from_adjacency(median_adjacency, config, band).items()}
        )

    return {name: values[0] for name, values in feature_values.items()}
