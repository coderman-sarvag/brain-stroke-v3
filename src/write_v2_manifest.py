"""Create the reproducibility manifest for the frozen v2 feature artifacts."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURE_ROOT = REPO_ROOT / "features" / "v2"
MANIFEST_PATH = FEATURE_ROOT / "MANIFEST.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record(path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": sha256_file(path),
    }


def git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()


def main() -> None:
    table_names = [
        "spectral_abs.csv",
        "spectral_lesion.csv",
        "graph_g8f.csv",
        "graph_g24f.csv",
        "subject_meta.csv",
    ]
    sidecar_names = [
        "spectral_abs.meta.json",
        "spectral_lesion.meta.json",
        "graph_g8f.meta.json",
        "graph_g24f.meta.json",
    ]
    config_paths = sorted((REPO_ROOT / "configs").glob("graph_*.json"))
    source_paths = [
        REPO_ROOT / "src" / "graph_features_v2.py",
        REPO_ROOT / "src" / "run_graph_features_v2.py",
        REPO_ROOT / "src" / "audit_graph_design_v2.py",
        REPO_ROOT / "src" / "qc_graph_features_v2.py",
        REPO_ROOT / "src" / "build_spectral_abs_v2.py",
        REPO_ROOT / "src" / "build_spectral_lesion_v2.py",
        REPO_ROOT / "src" / "write_v2_provenance.py",
        REPO_ROOT / "src" / "write_v2_manifest.py",
    ]

    table_records = []
    for name in table_names:
        path = FEATURE_ROOT / name
        table_record = record(path)
        sidecar_path = FEATURE_ROOT / name.replace(".csv", ".meta.json")
        if sidecar_path.exists():
            table_record["sidecar"] = record(sidecar_path)
        else:
            table_record["sidecar"] = "not applicable; metadata schema is documented in the guide"
        table_records.append(table_record)

    manifest = {
        "manifest_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": git_commit(),
        "label_free_feature_tables": table_records,
        "configs": [record(path) for path in config_paths],
        "implementation_sources": [record(path) for path in source_paths],
        "raw_and_processed_data": "Excluded from Git; input hashes are recorded in graph sidecars.",
        "freeze_status": "READY FOR REVIEW; not tagged features-v2",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
