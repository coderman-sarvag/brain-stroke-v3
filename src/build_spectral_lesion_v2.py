"""Build the v2 lesion-aligned spectral table from verified subject metadata."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = REPO_ROOT / "features" / "figshare_features.csv"
META_CSV = REPO_ROOT / "features" / "v2" / "subject_meta.csv"
OUTPUT_DIR = REPO_ROOT / "features" / "v2"
OUTPUT_CSV = OUTPUT_DIR / "spectral_lesion.csv"
SIDECAR_JSON = OUTPUT_DIR / "spectral_lesion.meta.json"

AI_COLUMNS = [
    f"all_AI_{band}_{pair}"
    for band in ("delta", "theta", "alpha", "beta")
    for pair in ("F3F4", "C3C4", "P3P4", "O1O2")
]
GLOBAL_COLUMNS = ["all_pdBSI", "all_DAR", "all_DTABR"]
OUTPUT_FEATURES = [
    column.replace("all_AI_", "les_AI_", 1) for column in AI_COLUMNS
] + GLOBAL_COLUMNS


def main() -> None:
    with META_CSV.open(newline="", encoding="utf-8") as handle:
        metadata = {row["subject_id"]: row for row in csv.DictReader(handle)}
    with SOURCE_CSV.open(newline="", encoding="utf-8") as handle:
        source_rows = list(csv.DictReader(handle))

    if len(source_rows) != 50:
        raise ValueError(f"Expected 50 source rows, got {len(source_rows)}")
    output_rows: list[dict[str, str]] = []
    excluded: list[str] = []
    for row in source_rows:
        subject_id = row["subject_id"]
        subject_meta = metadata.get(subject_id)
        if subject_meta is None:
            raise ValueError(f"Missing subject metadata for {subject_id}")
        lesion_side = subject_meta["lesion_side"]
        if lesion_side not in {"left", "right"}:
            excluded.append(subject_id)
            continue

        sign = 1.0 if lesion_side == "left" else -1.0
        output: dict[str, str] = {"subject_id": subject_id}
        for source_column, output_column in zip(AI_COLUMNS, OUTPUT_FEATURES[:16]):
            output[output_column] = f"{sign * float(row[source_column]):.17g}"
        for column in GLOBAL_COLUMNS:
            output[column] = row[column]
        output_rows.append(output)

    if not output_rows:
        raise ValueError("No subjects have verified lesion-side values")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    columns = ["subject_id"] + OUTPUT_FEATURES
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(output_rows)

    sidecar = {
        "table": str(OUTPUT_CSV.relative_to(REPO_ROOT)),
        "created": date.today().isoformat(),
        "source_features": str(SOURCE_CSV.relative_to(REPO_ROOT)),
        "source_metadata": str(META_CSV.relative_to(REPO_ROOT)),
        "rows": len(output_rows),
        "columns": columns,
        "feature_definition": "Lesion-aligned AI = +AI for left lesion and -AI for right lesion; global features copied unchanged.",
        "alignment_provenance": "ParalysisSide from participants.json mapped to contralateral lesion side under the v2 rule.",
        "excluded_subjects": excluded,
        "label_free": True,
        "clinical_columns_used": ["lesion_side"],
    }
    SIDECAR_JSON.write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_CSV} with shape ({len(output_rows)}, {len(columns)})")
    print(f"Excluded subjects: {excluded}")


if __name__ == "__main__":
    main()
