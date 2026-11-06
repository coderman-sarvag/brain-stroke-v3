"""Aggregate condition-separated Figshare epoch features to one row per patient."""

from pathlib import Path

import numpy as np
import pandas as pd

from feature_extraction import BANDS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASYMMETRY_ROOT = PROJECT_ROOT / "data" / "processed" / "figshare" / "asymmetry"
BANDPOWER_ROOT = PROJECT_ROOT / "data" / "processed" / "figshare" / "bandpower"
OUTPUT_PATH = PROJECT_ROOT / "features" / "figshare_patient_features.csv"
CONDITIONS = ("all", "left_hand", "right_hand")


def aggregate_condition(asymmetry: dict[str, np.ndarray], bandpower: dict[str, np.ndarray]) -> dict[str, float]:
    """Aggregate one condition's epoch-level asymmetry and power values."""
    row = {
        key: float(np.mean(values))
        for key, values in asymmetry.items()
    }
    all_asymmetry = np.stack(list(asymmetry.values()), axis=1)
    row["pdBSI"] = float(np.mean(np.abs(all_asymmetry)))

    total_power = {
        band: np.sum(values, axis=1)
        for band, values in bandpower.items()
    }
    dar = total_power["delta"] / total_power["alpha"]
    dtabr = (total_power["delta"] + total_power["theta"]) / (
        total_power["alpha"] + total_power["beta"]
    )
    row["DAR"] = float(np.mean(dar))
    row["DTABR"] = float(np.mean(dtabr))
    return row


def aggregate_subject(asymmetry_path: Path, bandpower_path: Path) -> dict[str, float | str]:
    """Build one condition-aware patient feature row."""
    row: dict[str, float | str] = {
        "subject_id": asymmetry_path.name.replace("-asymmetry.npz", "")
    }
    with np.load(asymmetry_path) as asymmetry_source, np.load(bandpower_path) as bandpower_source:
        for condition in CONDITIONS:
            asymmetry = {
                key.removeprefix(f"{condition}_"): asymmetry_source[key]
                for key in asymmetry_source.files
                if key.startswith(f"{condition}_AI_")
            }
            bandpower = {
                band: bandpower_source[f"{condition}_{band}"]
                for band in BANDS
            }
            condition_features = aggregate_condition(asymmetry, bandpower)
            for feature_name, value in condition_features.items():
                row[f"{condition}_{feature_name}"] = value
            row[f"n_epochs_{condition}"] = int(next(iter(bandpower.values())).shape[0])
    return row


def main() -> None:
    asymmetry_files = sorted(ASYMMETRY_ROOT.glob("sub-*-asymmetry.npz"))
    bandpower_files = {path.name.replace("-bandpower.npz", ""): path for path in BANDPOWER_ROOT.glob("sub-*-bandpower.npz")}
    if len(asymmetry_files) != 50 or len(bandpower_files) != 50:
        raise RuntimeError("Expected 50 asymmetry and 50 band-power files")

    rows = []
    for asymmetry_path in asymmetry_files:
        subject_key = asymmetry_path.name.replace("-asymmetry.npz", "")
        rows.append(aggregate_subject(asymmetry_path, bandpower_files[subject_key]))

    features = pd.DataFrame(rows).sort_values("subject_id")
    numeric = features.drop(columns=["subject_id"])
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy()).all():
        raise ValueError("Aggregated patient features contain NaN or infinite values")
    if features["subject_id"].duplicated().any():
        raise ValueError("Patient feature table contains duplicate subjects")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(OUTPUT_PATH, index=False)

    report_path = PROJECT_ROOT / "results" / "metrics" / "figshare_patient_feature_summary.txt"
    report_path.write_text(
        "Figshare patient-level feature aggregation\n"
        "Aggregation: mean epoch-level features, with all/left_hand/right_hand retained separately\n"
        f"Bands: {BANDS}\n"
        "Global ratios: DAR and DTABR computed from total power across the 8 feature channels\n"
        f"Rows: {len(features)}\n"
        f"Columns: {len(features.columns)}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()