"""Generate one locked v2 graph feature table from clean Figshare epochs."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path

import mne
from graph_features_v2 import compute_graph_features, screen_epochs


REPO_ROOT = Path(__file__).resolve().parents[1]
CLEAN_ROOT = REPO_ROOT / "data" / "processed" / "figshare" / "clean"
CONFIG_ROOT = REPO_ROOT / "configs"
OUTPUT_ROOT = REPO_ROOT / "features" / "v2"
META_CSV = OUTPUT_ROOT / "subject_meta.csv"
THRESHOLD_V = 150e-6


def subject_id(path: Path) -> str:
    return path.name.replace("-clean-epo.fif", "")


def passing_epochs(epochs: mne.Epochs, config: dict) -> mne.Epochs:
    return screen_epochs(
        epochs,
        list(config["channels"]),
        float(config.get("artifact_threshold_uv", THRESHOLD_V * 1e6)),
    )


def run(config_name: str) -> None:
    config_path = CONFIG_ROOT / f"graph_{config_name}.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    output_csv = OUTPUT_ROOT / f"graph_{config_name}.csv"
    sidecar_path = OUTPUT_ROOT / f"graph_{config_name}.meta.json"
    paths = sorted(CLEAN_ROOT.glob("sub-*-clean-epo.fif"))
    records: list[dict[str, float | str]] = []
    counts: dict[str, int] = {}
    excluded: dict[str, str] = {}

    for index, path in enumerate(paths):
        subject = subject_id(path)
        epochs = mne.read_epochs(path, preload=True, verbose=False)
        screened_epochs = passing_epochs(epochs, config)
        count = len(screened_epochs)
        counts[subject] = count
        if count < int(config["n_fixed"]):
            excluded[subject] = f"{count} usable epochs below N_fixed={config['n_fixed']}"
            continue
        subject_config = {**config, "subject_index": index}
        features = compute_graph_features(screened_epochs, subject_config)
        records.append({"subject_id": subject, **features})

    if not records:
        raise RuntimeError(f"No subjects met {config['n_fixed']=}")
    columns = ["subject_id"] + sorted(key for key in records[0] if key != "subject_id")
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)

    sidecar = {
        "table": str(output_csv.relative_to(REPO_ROOT)),
        "created": date.today().isoformat(),
        "config": str(config_path.relative_to(REPO_ROOT)),
        "rows": len(records),
        "columns": columns,
        "label_free": True,
        "epoch_threshold_uv": 150.0,
        "screen_applied_to_sampling_pool": True,
        "screen_channels": config["channels"],
        "screen_implementation": "src/graph_features_v2.py:screen_epochs",
        "usable_epoch_counts": counts,
        "excluded_subjects": excluded,
        "feature_definition": "Median adjacency over fixed-size, without-replacement epoch subsamples; four graph metrics per band.",
    }
    sidecar_path.write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")

    # Update only the epoch-count metadata fields; feature columns never contain labels.
    with META_CSV.open(newline="", encoding="utf-8") as handle:
        metadata = list(csv.DictReader(handle))
    count_column = f"n_epochs_{config_name}"
    for row in metadata:
        row[count_column] = str(counts.get(row["subject_id"], ""))
    with META_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metadata[0]))
        writer.writeheader()
        writer.writerows(metadata)

    print(f"{config_name}: wrote {output_csv} with {len(records)} subjects")
    print(f"{config_name}: excluded {excluded}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", choices=("g8f", "g24f"), required=True)
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
