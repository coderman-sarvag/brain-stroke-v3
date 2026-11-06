"""Filter and epoch Figshare EEG recordings for the motor-imagery task."""

from pathlib import Path

import mne

from load_figshare import EVENT_ID, find_subject_files, load_events, load_raw


OUTPUT_ROOT = Path(__file__).resolve().parents[1] / "data" / "processed" / "figshare"
BANDPASS_RANGE_HZ = (1.0, 40.0)
NOTCH_FREQ_HZ = 50.0
EPOCH_LENGTH_SECONDS = 4.0


def preprocess_subject(subject_file: str | Path) -> mne.Epochs:
    """Filter one recording and return its clean, un-rejected task epochs."""
    raw = load_raw(subject_file, preload=True)
    raw.filter(*BANDPASS_RANGE_HZ, fir_design="firwin", verbose=False)
    raw.notch_filter(freqs=NOTCH_FREQ_HZ, verbose=False)
    events, event_id = load_events(raw)
    tmax = EPOCH_LENGTH_SECONDS - (1.0 / raw.info["sfreq"])
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


def output_path(subject_file: str | Path) -> Path:
    """Return the processed FIF path for one subject EDF."""
    subject_id = Path(subject_file).name.split("_")[0]
    return OUTPUT_ROOT / f"{subject_id}-epo.fif"


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    subject_files = find_subject_files()
    if len(subject_files) != 50:
        raise RuntimeError(f"Expected 50 subject EDF files, found {len(subject_files)}")

    summaries = []
    for subject_file in subject_files:
        epochs = preprocess_subject(subject_file)
        destination = output_path(subject_file)
        epochs.save(destination, overwrite=True, verbose=False)
        summaries.append(
            f"{destination.stem}: epochs={len(epochs)}, "
            f"shape={epochs.get_data().shape}, "
            f"left={len(epochs['left_hand'])}, right={len(epochs['right_hand'])}"
        )

    report_path = Path(__file__).resolve().parents[1] / "results" / "metrics" / "figshare_preprocessing_summary.txt"
    report_path.write_text(
        "Figshare preprocessing summary\n"
        f"Band-pass: {BANDPASS_RANGE_HZ[0]}-{BANDPASS_RANGE_HZ[1]} Hz\n"
        f"Notch: {NOTCH_FREQ_HZ} Hz\n"
        f"Epoch length: {EPOCH_LENGTH_SECONDS} s; endpoint adjusted for 2000 samples\n"
        f"Event mapping: {EVENT_ID}\n"
        "Artifact rejection: deferred to Phase 2.3\n"
        + "\n".join(summaries)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()