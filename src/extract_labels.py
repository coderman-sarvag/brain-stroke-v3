"""Extract and bucket Figshare NIHSS labels."""

from pathlib import Path

import pandas as pd

from labels import bucket_nihss


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARTICIPANTS_PATH = PROJECT_ROOT / "data" / "raw" / "figshare" / "participants.tsv"
FEATURES_PATH = PROJECT_ROOT / "features" / "figshare_patient_features.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "figshare" / "labels.csv"


def main() -> None:
    participants = pd.read_csv(PARTICIPANTS_PATH, sep="\t")
    features = pd.read_csv(FEATURES_PATH, usecols=["subject_id"])
    labels = participants[["Participant_ID", "NIHSS"]].rename(
        columns={"Participant_ID": "subject_id", "NIHSS": "nihss_raw"}
    )
    labels["nihss_raw"] = pd.to_numeric(labels["nihss_raw"], errors="coerce")
    missing = labels.loc[labels["nihss_raw"].isna(), "subject_id"].tolist()
    if missing:
        raise ValueError(f"Missing or non-numeric NIHSS values for: {missing}")
    labels["severity_class"] = labels["nihss_raw"].map(bucket_nihss)
    labels = features.merge(labels, on="subject_id", how="left", validate="one_to_one")
    if labels["severity_class"].isna().any():
        missing_subjects = labels.loc[labels["severity_class"].isna(), "subject_id"].tolist()
        raise ValueError(f"Feature subjects missing clinical labels: {missing_subjects}")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    labels.to_csv(OUTPUT_PATH, index=False)

    distribution = labels["severity_class"].value_counts().to_dict()
    report_path = PROJECT_ROOT / "results" / "metrics" / "figshare_label_summary.txt"
    report_path.write_text(
        "Figshare NIHSS labels\n"
        "Buckets: mild <=4; moderate 5-15; severe >15\n"
        f"Rows: {len(labels)}\n"
        f"Class distribution: {distribution}\n"
        f"Classes below five subjects: {[name for name, count in distribution.items() if count < 5]}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()