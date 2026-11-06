"""Freeze the Kaggle-produced v3 tables into features/v3 and write features/v3/MANIFEST.json.

Every table is checked before it is written: sha256 equals its sidecar's table_sha256; the sidecar's config hash
equals the config copy shipped beside it and the committed config at the Kaggle commit; subject_meta_v3 must equal
the committed file. No label is read (the v2 label file is only hashed).

Run from the repo root: python src/freeze_features_v3.py --zip-dir <folder with the v3_outputs_small zips>
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provenance_v3 import ROOT, git_commit, load_config, sha256_file  # noqa: E402

CONFIG = "configs/v3/freeze.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def committed_bytes(commit, path):
    return subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True, check=True).stdout


def write(rel, data):
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"path": rel, "sha256": sha(data), "bytes": len(data)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    cfg, config_path = load_config(CONFIG)
    zips = {k: zipfile.ZipFile(args.zip_dir / v["zip"]) for k, v in cfg["sources"].items()}
    entries, problems = [], []

    for f in cfg["files"]:
        src = cfg["sources"][f["source"]]
        z = zips[f["source"]]
        data = z.read(f["member"])
        same = committed_bytes("HEAD", f["member"]) == data if f.get("must_equal_committed") else None  # before writing
        entry = {**write(f["member"], data), "role": f["role"], "source_zip": src["zip"], "kaggle_commit": src["kaggle_commit"]}
        if f.get("must_equal_committed"):
            entry["equals_committed"] = same
        if "sidecar" in f:
            side_bytes = z.read(f["sidecar"])
            side = json.loads(side_bytes)
            entry["sidecar"] = write(f["sidecar"], side_bytes)
            entry["table_sha_matches_sidecar"] = side["table_sha256"] == entry["sha256"]
            cfg_copy = z.read(f["config_copy"])
            entry["config_copy"] = write(f["config_copy"], cfg_copy)
            cfg_sha = side["provenance"]["config_sha256"]
            at_commit = sha(committed_bytes(src["kaggle_commit"], f["config"]))
            entry["config"] = {"path": f["config"], "sidecar_config_sha256": cfg_sha,
                               "copy_matches": sha(cfg_copy) == cfg_sha, "committed_at_kaggle_commit_matches": at_commit == cfg_sha,
                               "git": side["provenance"]["git"]}
            if not (entry["table_sha_matches_sidecar"] and entry["config"]["copy_matches"]
                    and entry["config"]["committed_at_kaggle_commit_matches"] and side["provenance"]["git"]["dirty"] is False):
                problems.append(f["member"])
        if f.get("must_equal_committed") and not entry["equals_committed"]:
            problems.append(f["member"])
        entries.append(entry)

    qc = [{**write(q["to"], zips[q["source"]].read(q["member"])), "from": q["member"],
           "source_zip": cfg["sources"][q["source"]]["zip"], "kaggle_commit": cfg["sources"][q["source"]]["kaggle_commit"]}
          for q in cfg["qc_files"]]
    if problems:
        raise SystemExit(f"Freeze verification failed for: {problems}")

    label_path = ROOT / cfg["label_file_reference"]
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "git_at_freeze": git_commit(),
                "freeze_config_sha256": sha256_file(config_path), "sources": cfg["sources"],
                "tables": entries, "qc_files": qc,
                "registry_inputs": [e["path"] for e in entries if e["role"] == "registry_input"],
                "noise_inflated_not_tested": [e["path"] for e in entries if e["role"] == "noise_inflated_not_tested"],
                "label_file": {"path": cfg["label_file_reference"], "sha256": sha256_file(label_path),
                               "note": "hashed only; read solely by run_registry_v3.py after features-v3 and registry-v3 tags"},
                "verification": "every table sha256 equals its sidecar; sidecar config hash equals the shipped config copy and the committed config at the Kaggle commit; all Kaggle runs clean (dirty=false); subject_meta_v3 equals the committed file"}
    (ROOT / cfg["manifest"]).write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    print(f"Frozen {len(entries)} tables, {len(qc)} QC files; manifest {cfg['manifest']}")
    for e in entries:
        print(f"  {e['path']:48s} {e['sha256'][:12]} {e['role']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
