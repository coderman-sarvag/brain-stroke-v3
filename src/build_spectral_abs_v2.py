"""Build the label-free v2 absolute spectral feature table."""

from __future__ import annotations

import csv
import json
import math
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = REPO_ROOT / "features" / "figshare_features.csv"
OUTPUT_DIR = REPO_ROOT / "features" / "v2"
OUTPUT_CSV = OUTPUT_DIR / "spectral_abs.csv"
SIDECAR_JSON = OUTPUT_DIR / "spectral_abs.meta.json"

AI_COLUMNS = [
    f"all_AI_{band}_{pair}"
    for band in ("delta", "theta", "alpha", "beta")
    for pair in ("F3F4", "C3C4", "P3P4", "O1O2")
]
GLOBAL_COLUMNS = ["all_pdBSI", "all_DAR", "all_DTABR"]
OUTPUT_FEATURES = [
    column.replace("all_AI_", "abs_AI_", 1) for column in AI_COLUMNS
] + GLOBAL_COLUMNS


def finite_float(value: str, column: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Non-finite value in {column}")
    return number


def main() -> None:
    with SOURCE_CSV.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    if len(rows) != 50:
        raise ValueError(f"Expected 50 source rows, got {len(rows)}")
    source_columns = set(rows[0])
    missing = [column for column in AI_COLUMNS + GLOBAL_COLUMNS if column not in source_columns]
    if missing:
        raise ValueError(f"Missing source feature columns: {missing}")

    output_rows: list[dict[str, str]] = []
    pd_bsi_differences: list[float] = []
    for row in rows:
        output: dict[str, str] = {"subject_id": row["subject_id"]}
        absolute_values: list[float] = []
        for source_column, output_column in zip(AI_COLUMNS, OUTPUT_FEATURES[:16]):
            value = abs(finite_float(row[source_column], source_column))
            absolute_values.append(value)
            output[output_column] = f"{value:.17g}"
        for column in GLOBAL_COLUMNS:
            output[column] = f"{finite_float(row[column], column):.17g}"
        pd_bsi_differences.append(abs(sum(absolute_values) / 16.0 - float(row["all_pdBSI"])))
        output_rows.append(output)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    columns = ["subject_id"] + OUTPUT_FEATURES
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(output_rows)

    sidecar = {
        "table": str(OUTPUT_CSV.relative_to(REPO_ROOT)),
        "created": date.today().isoformat(),
        "source": str(SOURCE_CSV.relative_to(REPO_ROOT)),
        "rows": len(output_rows),
        "columns": columns,
        "feature_definition": "Absolute value of the 16 existing all_AI subject-level features; global features copied unchanged.",
        "label_free": True,
        "label_columns_excluded": ["nihss_raw", "severity_class"],
        "epoch_count_columns_excluded": ["n_epochs_all", "n_epochs_left_hand", "n_epochs_right_hand"],
        "max_abs_mean_ai_minus_pdBSI": max(pd_bsi_differences),
    }
    SIDECAR_JSON.write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")

    if len(columns) != 20 or len(output_rows) != 50:
        raise AssertionError("Unexpected spectral_abs shape")
    print(f"Wrote {OUTPUT_CSV} with shape ({len(output_rows)}, {len(columns)})")
    print(f"Maximum mean(|AI|)-pdBSI difference: {sidecar['max_abs_mean_ai_minus_pdBSI']:.12g}")


if __name__ == "__main__":
    main()
