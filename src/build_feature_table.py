"""Build the final Figshare modeling table."""

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PATIENT_FEATURES_PATH = PROJECT_ROOT / "features" / "figshare_patient_features.csv"
LABELS_PATH = PROJECT_ROOT / "data" / "processed" / "figshare" / "labels.csv"
OUTPUT_PATH = PROJECT_ROOT / "features" / "figshare_features.csv"


def main() -> None:
    patient_features = pd.read_csv(PATIENT_FEATURES_PATH)
    labels = pd.read_csv(LABELS_PATH)
    final = patient_features.merge(labels, on="subject_id", how="inner", validate="one_to_one")
    if len(final) != len(patient_features) or len(final) != 50:
        raise ValueError("Final table does not contain exactly one row for each of 50 subjects")
    if final.isna().any().any():
        missing = final.columns[final.isna().any()].tolist()
        raise ValueError(f"Final table contains missing values in: {missing}")
    numeric = final.select_dtypes(include="number")
    if not np.isfinite(numeric.to_numpy()).all():
        raise ValueError("Final table contains infinite numeric values")
    if final["subject_id"].duplicated().any():
        raise ValueError("Final table contains duplicate subject IDs")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    final.sort_values("subject_id").to_csv(OUTPUT_PATH, index=False)

    report_path = PROJECT_ROOT / "results" / "metrics" / "figshare_final_table_summary.txt"
    report_path.write_text(
        "Final Figshare feature table\n"
        f"Rows: {len(final)}\n"
        f"Columns: {len(final.columns)}\n"
        "Feature design: 57 condition-aware features (19 each for all, left_hand, right_hand)\n"
        "Bookkeeping: three condition-specific epoch-count columns\n"
        f"Severity distribution: {final['severity_class'].value_counts().to_dict()}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()