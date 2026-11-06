"""Add reproducibility provenance to all v2 feature sidecars."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURE_ROOT = REPO_ROOT / "features" / "v2"
CONFIG_ROOT = REPO_ROOT / "configs"
CLEAN_ROOT = REPO_ROOT / "data" / "processed" / "figshare" / "clean"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_file_manifest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        relative = path.relative_to(REPO_ROOT).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def current_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()


def file_input(path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": sha256_file(path),
    }


def main() -> None:
    commit = current_commit()
    generated_at = datetime.now(timezone.utc).isoformat()
    clean_files = sorted(CLEAN_ROOT.glob("sub-*-clean-epo.fif"))
    if len(clean_files) != 50:
        raise ValueError(f"Expected 50 clean FIF files, found {len(clean_files)}")
    raw_participants = REPO_ROOT / "data" / "raw" / "figshare" / "participants.tsv"
    participants_json = REPO_ROOT / "data" / "raw" / "figshare" / "participants.json"
    source_features = REPO_ROOT / "features" / "figshare_features.csv"
    subject_meta = FEATURE_ROOT / "subject_meta.csv"

    graph_source = {
        "path": "data/processed/figshare/clean",
        "file_count": len(clean_files),
        "manifest_sha256": sha256_file_manifest(clean_files),
    }
    graph_config_hashes = {
        name: sha256_file(CONFIG_ROOT / f"graph_{name}.json")
        for name in ("g8f", "g24f")
    }

    sidecar_updates = {
        "spectral_abs": {
            "config": None,
            "config_sha256": None,
            "source_inputs": [file_input(source_features)],
        },
        "spectral_lesion": {
            "config": None,
            "config_sha256": None,
            "source_inputs": [
                file_input(source_features),
                file_input(subject_meta),
                file_input(raw_participants),
                file_input(participants_json),
            ],
        },
        "graph_g8f": {
            "config": "configs/graph_g8f.json",
            "config_sha256": graph_config_hashes["g8f"],
            "source_inputs": [graph_source],
        },
        "graph_g24f": {
            "config": "configs/graph_g24f.json",
            "config_sha256": graph_config_hashes["g24f"],
            "source_inputs": [graph_source],
        },
    }

    for table_name, update in sidecar_updates.items():
        sidecar_path = FEATURE_ROOT / f"{table_name}.meta.json"
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        sidecar.update(
            {
                "provenance_version": 1,
                "generated_at_utc": generated_at,
                "source_commit": commit,
                **update,
            }
        )
        sidecar_path.write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")
        print(f"Updated {sidecar_path}")


if __name__ == "__main__":
    main()
