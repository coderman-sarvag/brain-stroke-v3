"""Shared v3 provenance: config hash, git commit and date saved beside every output."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path, chunk=1 << 20):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def md5_file(path, chunk=1 << 20):
    digest = hashlib.md5()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def display_path(path, base=ROOT):
    """POSIX path relative to base when inside it, otherwise absolute (e.g. Kaggle input mounts)."""
    path = Path(path).resolve()
    try:
        return path.relative_to(Path(base).resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def git_commit():
    """Commit of the code checkout; falls back to $V3_GIT_COMMIT when git is unavailable (e.g. a copied repo)."""
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return {"commit": os.environ.get("V3_GIT_COMMIT"), "dirty": None}
    return {"commit": out.stdout.strip(), "dirty": bool(dirty.stdout.strip())}


def load_config(rel_path):
    path = ROOT / rel_path
    return json.loads(path.read_text(encoding="utf-8")), path


def provenance(config_path, sources=(), roots=None):
    """Return a provenance block; config hash is computed on the exact bytes used."""
    block = {"date_utc": datetime.now(timezone.utc).isoformat(),
             "git": git_commit(),
             "config": display_path(config_path),
             "config_sha256": sha256_file(config_path),
             "sources_sha256": {display_path(s): sha256_file(s) for s in sources}}
    if roots is not None:
        block["roots"] = roots.as_dict()
    return block


def write_with_config(output_path, payload, config_path, sources=(), roots=None):
    """Write a JSON output, plus a copy of its config (<config stem>.config.json), both beside the output."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    config_copy = output_path.parent / f"{Path(config_path).stem}.config.json"
    if config_copy.resolve() == output_path.resolve():
        raise ValueError("Config copy would overwrite the output")
    payload = {"provenance": provenance(config_path, sources, roots), **payload}
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(config_path, config_copy)
    return output_path
