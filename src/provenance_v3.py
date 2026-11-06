"""Shared v3 provenance: config hash, git commit and date saved beside every output."""
from datetime import datetime, timezone
import hashlib
import json
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


def git_commit():
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}
    return {"commit": out.stdout.strip(), "dirty": bool(dirty.stdout.strip())}


def load_config(rel_path):
    path = ROOT / rel_path
    return json.loads(path.read_text(encoding="utf-8")), path


def provenance(config_path, sources=()):
    """Return a provenance block; config hash is computed on the exact bytes used."""
    return {"date_utc": datetime.now(timezone.utc).isoformat(),
            "git": git_commit(),
            "config": Path(config_path).resolve().relative_to(ROOT).as_posix(),
            "config_sha256": sha256_file(config_path),
            "sources_sha256": {Path(s).resolve().relative_to(ROOT).as_posix(): sha256_file(s) for s in sources}}


def write_with_config(output_path, payload, config_path, sources=()):
    """Write a JSON output, plus a copy of its config (<config stem>.config.json), both beside the output."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    config_copy = output_path.parent / f"{Path(config_path).stem}.config.json"
    if config_copy.resolve() == output_path.resolve():
        raise ValueError("Config copy would overwrite the output")
    payload = {"provenance": provenance(config_path, sources), **payload}
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(config_path, config_copy)
    return output_path
