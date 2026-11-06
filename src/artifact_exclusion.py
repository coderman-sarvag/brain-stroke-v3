"""Apply amplitude-based epoch exclusion to Figshare epochs."""

from pathlib import Path

import mne
import pandas as pd

from load_figshare import find_subject_files, load_events, load_raw


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = PROJECT_ROOT / "data" / "processed" / "figshare"
OUTPUT_ROOT = INPUT_ROOT / "clean"
LOG_PATH = INPUT_ROOT / "exclusion_log.csv"
REJECT_THRESHOLD_UV = 150e-6
MIN_EPOCHS_PER_CONDITION = 10
FEATURE_CHANNELS = ["F3", "F4", "C3", "C4", "P3", "P4", "O1", "O2"]
MIN_BAD_EPOCHS_FOR_INTERPOLATION = 20
MONTAGE_CHANNEL_RENAMES = {
    "FP1": "Fp1",
    "FP2": "Fp2",
    "T3": "T7",
    "T4": "T8",
    "T5": "P7",
    "T6": "P8",
}


def channel_rejection_counts(epochs: mne.Epochs) -> dict[str, int]:
    """Count threshold failures for each feature channel without changing epochs."""
    feature_epochs = epochs.copy().pick(FEATURE_CHANNELS)
    feature_epochs.drop_bad(reject={"eeg": REJECT_THRESHOLD_UV}, verbose=False)
    return {
        channel: sum(channel in drop_log for drop_log in feature_epochs.drop_log)
        for channel in FEATURE_CHANNELS
    }


def interpolate_consistently_bad_channels(
    subject_id: str,
    counts: dict[str, int],
    raw_files: dict[str, Path],
) -> mne.Epochs | None:
    """Reprocess a subject after interpolating persistently bad feature channels."""
    bad_channels = [
        channel
        for channel, count in counts.items()
        if count >= MIN_BAD_EPOCHS_FOR_INTERPOLATION
    ]
    if not bad_channels:
        return None

    raw = load_raw(raw_files[subject_id], preload=True)
    reverse_renames = {new: old for old, new in MONTAGE_CHANNEL_RENAMES.items()}
    raw.rename_channels(MONTAGE_CHANNEL_RENAMES)
    montage = mne.channels.make_standard_montage("standard_1020")
    raw.set_montage(montage, on_missing="ignore", verbose=False)
    raw.info["bads"] = [MONTAGE_CHANNEL_RENAMES.get(channel, channel) for channel in bad_channels]
    raw.interpolate_bads(reset_bads=True, verbose=False)
    raw.rename_channels(reverse_renames)
    raw.filter(1.0, 40.0, fir_design="firwin", verbose=False)
    raw.notch_filter(freqs=50.0, verbose=False)
    events, event_id = load_events(raw)
    tmax = 4.0 - (1.0 / raw.info["sfreq"])
    return mne.Epochs(
        raw,
        events,
        event_id=event_id,
        tmin=0.0,
        tmax=tmax,
        baseline=None,
        preload=True,
        reject_by_annotation=False,
        verbose=False,
    )


def clean_subject(input_path: str | Path) -> tuple[mne.Epochs, dict[str, object]]:
    """Reject high-amplitude epochs and return the cleaned epochs plus a log row."""
    epochs = mne.read_epochs(input_path, preload=True, verbose=False)
    subject_id = Path(input_path).name.split("-")[0] + "-" + Path(input_path).name.split("-")[1]
    counts = channel_rejection_counts(epochs)
    initial_count = len(epochs)
    feature_epochs = epochs.copy().pick(FEATURE_CHANNELS)
    feature_epochs.drop_bad(reject={"eeg": REJECT_THRESHOLD_UV}, verbose=False)
    bad_indices = [index for index, drop_log in enumerate(feature_epochs.drop_log) if drop_log]
    epochs.drop(bad_indices, reason="feature_channel_amplitude", verbose=False)
    left_count = len(epochs["left_hand"])
    right_count = len(epochs["right_hand"])
    clean_count = len(epochs)
    return epochs, {
        "subject_id": subject_id,
        "initial_epochs": initial_count,
        "dropped_epochs": initial_count - clean_count,
        "clean_epochs": clean_count,
        "left_clean_epochs": left_count,
        "right_clean_epochs": right_count,
        "feature_channel_rejection_counts": ";".join(
            f"{channel}:{counts[channel]}" for channel in FEATURE_CHANNELS
        ),
        "interpolated_channels": "",
        "documented_exclusion": False,
        "fully_excluded": clean_count == 0,
        "review_flag": left_count < MIN_EPOCHS_PER_CONDITION or right_count < MIN_EPOCHS_PER_CONDITION,
        "reason": "Feature-channel amplitude rejection applied",
    }


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    input_files = sorted(INPUT_ROOT.glob("sub-*-epo.fif"))
    if len(input_files) != 50:
        raise RuntimeError(f"Expected 50 input FIF files, found {len(input_files)}")

    raw_files = {
        path.name.split("_")[0]: path for path in find_subject_files()
    }
    rows = []
    for input_path in input_files:
        subject_id = input_path.name.split("-")[0] + "-" + input_path.name.split("-")[1]
        source_epochs = mne.read_epochs(input_path, preload=True, verbose=False)
        counts = channel_rejection_counts(source_epochs)
        epochs = interpolate_consistently_bad_channels(subject_id, counts, raw_files)
        if epochs is None:
            epochs, row = clean_subject(input_path)
        else:
            initial_count = len(epochs)
            feature_epochs = epochs.copy().pick(FEATURE_CHANNELS)
            feature_epochs.drop_bad(reject={"eeg": REJECT_THRESHOLD_UV}, verbose=False)
            bad_indices = [index for index, drop_log in enumerate(feature_epochs.drop_log) if drop_log]
            epochs.drop(bad_indices, reason="feature_channel_amplitude", verbose=False)
            left_count = len(epochs["left_hand"])
            right_count = len(epochs["right_hand"])
            interpolated = [channel for channel, count in counts.items() if count >= MIN_BAD_EPOCHS_FOR_INTERPOLATION]
            row = {
                "subject_id": subject_id,
                "initial_epochs": initial_count,
                "dropped_epochs": initial_count - len(epochs),
                "clean_epochs": len(epochs),
                "left_clean_epochs": left_count,
                "right_clean_epochs": right_count,
                "feature_channel_rejection_counts": ";".join(f"{channel}:{counts[channel]}" for channel in FEATURE_CHANNELS),
                "interpolated_channels": ";".join(interpolated),
                "documented_exclusion": False,
                "fully_excluded": len(epochs) == 0,
                "review_flag": left_count < MIN_EPOCHS_PER_CONDITION or right_count < MIN_EPOCHS_PER_CONDITION,
                "reason": "Interpolated persistent feature channels, then applied feature-channel rejection",
            }
        output_path = OUTPUT_ROOT / input_path.name.replace("-epo.fif", "-clean-epo.fif")
        epochs.save(output_path, overwrite=True, verbose=False)
        rows.append(row)

    pd.DataFrame(rows).sort_values("subject_id").to_csv(LOG_PATH, index=False)


if __name__ == "__main__":
    main()