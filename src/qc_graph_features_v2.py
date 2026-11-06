"""Run label-free QC for the v2 graph feature tables."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import mne
import numpy as np

from graph_features_v2 import compute_graph_features


REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURE_ROOT = REPO_ROOT / "features" / "v2"
CLEAN_ROOT = REPO_ROOT / "data" / "processed" / "figshare" / "clean"
CONFIG_ROOT = REPO_ROOT / "configs"
REPORT_PATH = REPO_ROOT / "docs" / "FEATURE_QC_V2.md"


def rank_values(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    position = 0
    while position < len(values):
        end = position + 1
        while end < len(values) and values[order[end]] == values[order[position]]:
            end += 1
        ranks[order[position:end]] = (position + end - 1) / 2.0 + 1.0
        position = end
    return ranks


def spearman(left: np.ndarray, right: np.ndarray) -> float:
    if len(left) < 3 or np.ptp(left) == 0 or np.ptp(right) == 0:
        return float("nan")
    return float(np.corrcoef(rank_values(left), rank_values(right))[0, 1])


def read_table(path: Path) -> tuple[list[str], dict[str, dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return list(rows[0]), {row["subject_id"]: row for row in rows}


def main() -> None:
    with (FEATURE_ROOT / "subject_meta.csv").open(newline="", encoding="utf-8") as handle:
        meta = {row["subject_id"]: row for row in csv.DictReader(handle)}
    report: list[str] = ["# v2 Graph Feature QC", "", "All checks below are label-free.", ""]
    table_values: dict[str, dict[str, np.ndarray]] = {}
    stability_values: dict[str, dict[str, np.ndarray]] = {}

    for config_name in ("g8f", "g24f"):
        table_path = FEATURE_ROOT / f"graph_{config_name}.csv"
        columns, rows = read_table(table_path)
        feature_columns = [column for column in columns if column != "subject_id"]
        values = {
            column: np.array([float(row[column]) for row in rows.values()], dtype=float)
            for column in feature_columns
        }
        table_values[config_name] = values
        banned = [column for column in columns if any(token in column.lower() for token in ("nihss", "severity", "epoch_count"))]
        finite = all(np.isfinite(value).all() for value in values.values())
        constants = [column for column, value in values.items() if np.ptp(value) == 0]
        report.extend(
            [
                f"## {config_name}",
                "",
                f"- Rows: {len(rows)}; features: {len(feature_columns)}.",
                f"- Finite values: {finite}.",
                f"- Banned label/count column names: {banned or 'none'}.",
                f"- Constant features: {constants or 'none'}.",
                "",
                "### Feature ranges",
                "",
            ]
        )
        for column, value in values.items():
            report.append(f"- `{column}`: min={value.min():.6g}, max={value.max():.6g}")

        epoch_counts = np.array([float(meta[subject]["n_epochs_all"]) for subject in rows], dtype=float)
        report.extend(["", "### Epoch-count bias", ""])
        for column, value in values.items():
            correlation = spearman(epoch_counts, value)
            report.append(f"- `{column}` vs `n_epochs_all`: Spearman r={correlation:.6g}")

        matrix = np.array([values[column] for column in feature_columns])
        correlation_matrix = np.corrcoef(matrix)
        high_pairs: list[str] = []
        for left_index in range(len(feature_columns)):
            for right_index in range(left_index + 1, len(feature_columns)):
                correlation = correlation_matrix[left_index, right_index]
                if np.isfinite(correlation) and abs(correlation) > 0.95:
                    high_pairs.append(f"{feature_columns[left_index]} / {feature_columns[right_index]}: r={correlation:.6g}")
        report.extend(["", "### Collinearity", "", f"- Pairs with |r| > 0.95: {high_pairs or 'none'}", ""])

        config = json.loads((CONFIG_ROOT / f"graph_{config_name}.json").read_text(encoding="utf-8"))
        config["seed_base"] = 1042
        second_run: dict[str, dict[str, float]] = {}
        paths = sorted(CLEAN_ROOT.glob("sub-*-clean-epo.fif"))
        included = set(rows)
        for index, path in enumerate(paths):
            subject = path.name.replace("-clean-epo.fif", "")
            if subject not in included:
                continue
            epochs = mne.read_epochs(path, preload=True, verbose=False)
            second_run[subject] = compute_graph_features(epochs, {**config, "subject_index": index})
        stability_values[config_name] = {
            column: np.array([second_run[subject][column] for subject in rows], dtype=float)
            for column in feature_columns
        }
        report.extend(["### Second-seed stability", "", "- Alternate seed base: 1042."])
        for column, value in values.items():
            correlation = spearman(value, stability_values[config_name][column])
            report.append(f"- `{column}` between seed runs: Spearman r={correlation:.6g}")
        report.append("")

    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
