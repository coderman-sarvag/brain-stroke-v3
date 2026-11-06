"""Load Figshare EDF recordings and their BIDS event sidecar."""

from pathlib import Path

import mne
import pandas as pd


DATA_ROOT = Path(__file__).resolve().parents[1] / "data" / "raw" / "figshare"
EDF_ROOT = DATA_ROOT / "extracted"
EVENTS_PATH = DATA_ROOT / "task-motor-imagery_events.tsv"

EVENT_ID = {"left_hand": 1, "right_hand": 2}
EVENT_VALUE_ID = {
    "instruction_beginning": 1,
    "imagery_beginning": 2,
    "break_beginning": 3,
}
EEG_CHANNELS = (
    "FP1", "FP2", "Fz", "F3", "F4", "F7", "F8", "FCz", "FC3", "FC4",
    "FT7", "FT8", "Cz", "C3", "C4", "T3", "T4", "CPz", "CP3", "CP4",
    "TP7", "TP8", "Pz", "P3", "P4", "T5", "T6", "Oz", "O1", "O2",
)


def find_subject_files(root: Path = EDF_ROOT) -> list[Path]:
    """Return sorted subject EDF files under the extracted Figshare root."""
    return sorted(root.glob("edffile/sub-*/eeg/*.edf"))


def load_raw(path: str | Path, preload: bool = False) -> mne.io.BaseRaw:
    """Load one Figshare EDF and retain the named EEG channels only."""
    raw = mne.io.read_raw_edf(path, preload=preload, verbose=False)
    missing = [channel for channel in EEG_CHANNELS if channel not in raw.ch_names]
    if missing:
        raise ValueError(f"Missing expected EEG channels: {missing}")
    return raw.pick(EEG_CHANNELS)


def load_events(
    raw: mne.io.BaseRaw,
    events_path: str | Path = EVENTS_PATH,
) -> tuple[object, dict[str, int]]:
    """Convert the official BIDS event sidecar into MNE imagery events."""
    events_table = pd.read_csv(events_path, sep="\t")
    imagery = events_table[events_table["value"] == EVENT_VALUE_ID["imagery_beginning"]]
    if imagery.empty:
        raise ValueError("The event sidecar contains no imagery-beginning events")

    event_samples = (imagery["onset"].to_numpy() * raw.info["sfreq"] / 1000).round().astype(int)
    if event_samples.max() >= raw.n_times:
        raise ValueError("An event onset falls outside the raw recording")

    trial_codes = imagery["trial_type"].astype(str).map({"1": 1, "2": 2})
    if trial_codes.isna().any():
        raise ValueError("The event sidecar contains an unknown trial type")

    events = pd.DataFrame(
        {
            "sample": event_samples,
            "previous": 0,
            "event": trial_codes.to_numpy(dtype=int),
        }
    ).to_numpy(dtype=int)
    return events, EVENT_ID.copy()


def main() -> None:
    subject_files = find_subject_files()
    if len(subject_files) != 50:
        raise RuntimeError(f"Expected 50 subject EDF files, found {len(subject_files)}")

    summaries = []
    for subject_file in subject_files:
        raw = load_raw(subject_file)
        events, _ = load_events(raw)
        summaries.append(
            f"{subject_file.stem}: sfreq={raw.info['sfreq']:.1f}, "
            f"channels={len(raw.ch_names)}, events={len(events)}, "
            f"left={int((events[:, 2] == EVENT_ID['left_hand']).sum())}, "
            f"right={int((events[:, 2] == EVENT_ID['right_hand']).sum())}"
        )

    output_path = Path(__file__).resolve().parents[1] / "results" / "metrics" / "figshare_event_inspection.txt"
    output_path.write_text(
        "Figshare event inspection\n"
        "Event source: task-motor-imagery_events.tsv (external BIDS sidecar)\n"
        f"EVENT_ID: {EVENT_ID}\n"
        f"Imagery event marker: value={EVENT_VALUE_ID['imagery_beginning']}\n"
        + "\n".join(summaries)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()