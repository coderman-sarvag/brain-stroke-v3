"""Extract condition-separated interhemispheric asymmetry indices."""

from pathlib import Path

import numpy as np

from feature_extraction import BANDS, CHANNEL_PAIRS, FEATURE_CHANNELS, asymmetry_index


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = PROJECT_ROOT / "data" / "processed" / "figshare" / "bandpower"
OUTPUT_ROOT = PROJECT_ROOT / "data" / "processed" / "figshare" / "asymmetry"
CONDITIONS = ("all", "left_hand", "right_hand")


def save_subject_asymmetry(input_path: Path) -> Path:
    """Compute and save asymmetry arrays for one subject."""
    output_path = OUTPUT_ROOT / input_path.name.replace("-bandpower.npz", "-asymmetry.npz")
    with np.load(input_path) as source:
        channel_names = source["channel_names"].tolist()
        results = {}
        for condition in CONDITIONS:
            band_powers = {
                band_name: source[f"{condition}_{band_name}"]
                for band_name in BANDS
            }
            results.update(
                {
                    f"{condition}_{feature_name}": values
                    for feature_name, values in asymmetry_index(
                        band_powers, channel_names, CHANNEL_PAIRS
                    ).items()
                }
            )

    np.savez_compressed(
        output_path,
        **results,
        channel_names=np.asarray(FEATURE_CHANNELS),
        channel_pairs=np.asarray([f"{left}{right}" for left, right in CHANNEL_PAIRS]),
        bands=np.asarray(list(BANDS.keys())),
        conditions=np.asarray(CONDITIONS),
    )
    return output_path


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    input_files = sorted(INPUT_ROOT.glob("sub-*-bandpower.npz"))
    if len(input_files) != 50:
        raise RuntimeError(f"Expected 50 band-power files, found {len(input_files)}")
    for input_path in input_files:
        save_subject_asymmetry(input_path)

    report_path = PROJECT_ROOT / "results" / "metrics" / "figshare_asymmetry_summary.txt"
    report_path.write_text(
        "Figshare asymmetry-index extraction\n"
        f"Channel pairs: {CHANNEL_PAIRS}\n"
        f"Bands: {BANDS}\n"
        f"Conditions saved separately: {list(CONDITIONS)}\n"
        f"Subjects processed: {len(input_files)}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()