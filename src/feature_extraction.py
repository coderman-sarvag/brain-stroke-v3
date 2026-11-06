"""Dataset-agnostic EEG feature extraction helpers."""

from collections.abc import Mapping

import numpy as np
from mne.time_frequency import psd_array_welch


BANDS = {
    "delta": (1.0, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
}
FEATURE_CHANNELS = ["F3", "F4", "C3", "C4", "P3", "P4", "O1", "O2"]
CHANNEL_PAIRS = [
    ("F3", "F4"),
    ("C3", "C4"),
    ("P3", "P4"),
    ("O1", "O2"),
]


def band_power(epochs, bands: Mapping[str, tuple[float, float]] = BANDS) -> dict[str, np.ndarray]:
    """Compute mean Welch power per epoch, channel, and named frequency band."""
    data = epochs.get_data()
    psds, frequencies = psd_array_welch(
        data,
        sfreq=epochs.info["sfreq"],
        fmin=min(low for low, _ in bands.values()),
        fmax=max(high for _, high in bands.values()),
        n_fft=256,
        verbose=False,
    )
    result = {}
    for band_name, (low, high) in bands.items():
        frequency_mask = (frequencies >= low) & (frequencies <= high)
        band_values = psds[:, :, frequency_mask].mean(axis=2)
        if not np.all(np.isfinite(band_values)) or not np.all(band_values > 0):
            raise ValueError(f"Invalid power values in {band_name}")
        result[band_name] = band_values
    return result


def condition_band_power(epochs) -> dict[str, dict[str, np.ndarray]]:
    """Compute band power separately for all, left-hand, and right-hand epochs."""
    feature_epochs = epochs.copy().pick(FEATURE_CHANNELS)
    return {
        "all": band_power(feature_epochs),
        "left_hand": band_power(feature_epochs["left_hand"]),
        "right_hand": band_power(feature_epochs["right_hand"]),
    }


def asymmetry_index(
    band_powers: Mapping[str, np.ndarray],
    channel_names: list[str] | tuple[str, ...],
    channel_pairs: list[tuple[str, str]] = CHANNEL_PAIRS,
) -> dict[str, np.ndarray]:
    """Compute left-right asymmetry per band, pair, and epoch."""
    results = {}
    for band_name, power_values in band_powers.items():
        for left_channel, right_channel in channel_pairs:
            left_index = channel_names.index(left_channel)
            right_index = channel_names.index(right_channel)
            left_power = power_values[:, left_index]
            right_power = power_values[:, right_index]
            denominator = left_power + right_power
            if np.any(denominator <= 0) or not np.isfinite(denominator).all():
                raise ValueError(f"Invalid denominator for {band_name}_{left_channel}{right_channel}")
            values = (left_power - right_power) / denominator
            if not np.isfinite(values).all() or not np.all((values >= -1) & (values <= 1)):
                raise ValueError(f"Invalid asymmetry values for {band_name}_{left_channel}{right_channel}")
            results[f"AI_{band_name}_{left_channel}{right_channel}"] = values
    return results