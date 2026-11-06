"""Step 0: download the Figshare stroke EEG files via the API and verify computed_md5.

Run from the repo root: python src/download_figshare_v3.py [--data-root D] [--out-root O]
Files go to <data-root>/figshare/; the manifest goes under <out-root>.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import sys
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths_v3 import add_root_args, roots_from_args  # noqa: E402
from provenance_v3 import display_path, load_config, md5_file, sha256_file, write_with_config  # noqa: E402

CONFIG = "configs/v3/figshare_download.json"


def fetch_metadata(api_url):
    with urllib.request.urlopen(api_url, timeout=60) as response:
        return json.load(response)


def download(url, target, expected_md5, chunk):
    """Stream to a .part file, verify md5, then move into place. Existing verified files are kept."""
    target = Path(target)
    if target.exists() and md5_file(target) == expected_md5:
        return "already_present_verified"
    part = target.with_name(target.name + ".part")
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response, part.open("wb") as handle:
        for block in iter(lambda: response.read(chunk), b""):
            handle.write(block)
    got = md5_file(part)
    if got != expected_md5:
        part.unlink()
        raise RuntimeError(f"md5 mismatch for {target.name}: got {got}, expected {expected_md5}")
    part.replace(target)
    return "downloaded_verified"


def safe_extract(zip_path, dest):
    """Extract a zip, refusing absolute paths and '..' members."""
    dest = Path(dest).resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            parts = PurePosixPath(member.filename.replace("\\", "/")).parts
            if member.filename.startswith(("/", "\\")) or ".." in parts or (parts and ":" in parts[0]):
                raise ValueError(f"Unsafe zip member: {member.filename}")
            if not (dest / Path(*parts)).resolve().is_relative_to(dest):
                raise ValueError(f"Zip member escapes destination: {member.filename}")
        archive.extractall(dest)
        return len(archive.infolist())


def main(argv=None):
    roots = roots_from_args(add_root_args(argparse.ArgumentParser(description=__doc__)).parse_args(argv))
    config, config_path = load_config(CONFIG)
    meta = fetch_metadata(config["api_url"])
    if meta.get("doi") != config["expected_doi"]:
        raise RuntimeError(f"Unexpected article DOI {meta.get('doi')}; expected {config['expected_doi']}")
    remote = {f["name"]: f for f in meta["files"]}
    missing = sorted(set(config["files"]) - set(remote))
    if missing:
        raise RuntimeError(f"Files missing from the Figshare article: {missing}")

    root = roots.data_path(config["download_root"])
    records = []
    for name, spec in config["files"].items():
        info = remote[name]
        target = root / spec["target"]
        status = download(info["download_url"], target, info["computed_md5"], config["chunk_bytes"])
        record = {"name": name, "figshare_file_id": info["id"], "size": info["size"],
                  "computed_md5": info["computed_md5"], "local_md5": md5_file(target),
                  "local_sha256": sha256_file(target), "path": display_path(target, roots.data), "status": status}
        if "extract_to" in spec:
            record["extracted_members"] = safe_extract(target, root / spec["extract_to"])
            record["extracted_to"] = display_path(root / spec["extract_to"], roots.data)
        records.append(record)
        print(f"{name}: {status}")

    write_with_config(roots.out_path(config["manifest_output"]),
                      {"article": {"id": meta["id"], "title": meta["title"], "doi": meta["doi"], "version": meta.get("version"),
                                   "license": (meta.get("license") or {}).get("name")},
                       "files": records, "not_downloaded": config["not_downloaded"]},
                      config_path, sources=[Path(__file__)], roots=roots)
    print(f"All {len(records)} files verified against computed_md5")


if __name__ == "__main__":
    main()
