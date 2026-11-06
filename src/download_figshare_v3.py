"""Step 0: obtain the Figshare stroke EEG files and verify them against hashes stored in the config.

Three ways, chosen automatically (no network unless needed):
  1. --raw-source DIR   copy the files from DIR (e.g. a read-only Kaggle dataset) into <data-root>/figshare and
                        verify them; the Figshare API is never called. DIR may hold edffile.zip (md5-verified) or an
                        already-extracted edffile/ tree (every EDF sha256-verified), plus the small sidecar files.
  2. offline            files already in <data-root>/figshare with matching md5 are used as they are.
  3. API download       only for missing files: the Figshare API is called with a browser-style User-Agent, its
                        computed_md5 must equal the stored md5, and each download is md5-verified.

Run from the repo root: python src/download_figshare_v3.py [--raw-source DIR] [--data-root D] [--out-root O]
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import sys
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths_v3 import add_root_args, roots_from_args  # noqa: E402
from provenance_v3 import display_path, load_config, md5_file, sha256_file, write_with_config  # noqa: E402

CONFIG = "configs/v3/figshare_download.json"
EDF_ZIP = "edffile.zip"


def open_url(url, user_agent=None, timeout=120):
    headers = {"User-Agent": user_agent, "Accept": "*/*"} if user_agent else {}
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)


def fetch_metadata(api_url, user_agent=None):
    with open_url(api_url, user_agent, timeout=60) as response:
        return json.load(response)


def download(url, target, expected_md5, chunk, user_agent=None):
    """Stream to a .part file, verify md5, then move into place. Existing verified files are kept."""
    target = Path(target)
    if target.exists() and md5_file(target) == expected_md5:
        return "already_present_verified"
    part = target.with_name(target.name + ".part")
    target.parent.mkdir(parents=True, exist_ok=True)
    with open_url(url, user_agent) as response, part.open("wb") as handle:
        for block in iter(lambda: response.read(chunk), b""):
            handle.write(block)
    got = md5_file(part)
    if got != expected_md5:
        part.unlink()
        raise RuntimeError(f"md5 mismatch for {target.name}: got {got}, expected {expected_md5}")
    part.replace(target)
    return "downloaded_verified"


def copy_verified(source, target, expected, hasher):
    """Copy via a .part file and verify; an already-verified target is kept."""
    target = Path(target)
    if target.exists() and hasher(target) == expected:
        return "already_present_verified"
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    shutil.copyfile(source, part)
    got = hasher(part)
    if got != expected:
        part.unlink()
        raise RuntimeError(f"hash mismatch for {Path(source).name}: got {got}, expected {expected}")
    part.replace(target)
    return "copied_verified"


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


def find_unique(source, name):
    """Find a file by name anywhere under source; several copies are allowed only if byte-identical."""
    matches = sorted(p for p in Path(source).rglob(name) if p.is_file())
    if len(matches) > 1 and len({md5_file(p) for p in matches}) > 1:
        raise RuntimeError(f"Several different files named {name} under {source}: {[str(m) for m in matches]}")
    return matches[0] if matches else None


def edf_tree_status(root, cfg):
    """Return (missing, mismatched) subject lists for the extracted EDF tree under root."""
    missing, mismatched = [], []
    for subject, sha in cfg["edf_sha256"].items():
        path = root / cfg["edf_relative_template"].format(subject=subject)
        if not path.exists():
            missing.append(subject)
        elif sha256_file(path) != sha:
            mismatched.append(subject)
    return missing, mismatched


def stage_from_raw_source(source, root, cfg):
    """Copy every file from a local/read-only source and verify it; never touches the network."""
    records, missing = [], []
    for name, spec in cfg["files"].items():
        found = find_unique(source, name)
        if found is not None:
            status = copy_verified(found, root / spec["target"], spec["md5"], md5_file)
            records.append({"name": name, "source": str(found), "status": status})
        elif name == EDF_ZIP:
            records.extend(stage_edf_tree(source, root, cfg))
        else:
            missing.append(name)
    if missing:
        raise RuntimeError(f"Not found under --raw-source {source}: {missing}")
    return records


def stage_edf_tree(source, root, cfg):
    """Accept an already-extracted edffile/ tree (e.g. Kaggle auto-unzipped the upload): verify every EDF."""
    records, absent = [], []
    for subject, sha in cfg["edf_sha256"].items():
        rel = cfg["edf_relative_template"].format(subject=subject)
        found = find_unique(source, Path(rel).name)
        if found is None:
            absent.append(subject)
            continue
        records.append({"name": Path(rel).name, "source": str(found),
                        "status": copy_verified(found, root / rel, sha, sha256_file)})
    if absent:
        raise RuntimeError(f"{EDF_ZIP} not found and extracted EDFs missing for {absent}")
    return records


def stage_online(root, cfg):
    """Use verified local files; call the API (with User-Agent) only for files that are missing or wrong."""
    records, needed = [], []
    for name, spec in cfg["files"].items():
        target = root / spec["target"]
        if target.exists() and md5_file(target) == spec["md5"]:
            records.append({"name": name, "status": "already_present_verified"})
        elif name == EDF_ZIP and edf_tree_status(root, cfg) == ([], []):
            records.append({"name": name, "status": "extracted_tree_verified_zip_not_needed"})
        else:
            needed.append(name)
    if not needed:
        return records, False
    meta = fetch_metadata(cfg["api_url"], cfg["user_agent"])
    if meta.get("doi") != cfg["expected_doi"]:
        raise RuntimeError(f"Unexpected article DOI {meta.get('doi')}; expected {cfg['expected_doi']}")
    remote = {f["name"]: f for f in meta["files"]}
    for name in needed:
        spec, info = cfg["files"][name], remote.get(name)
        if info is None:
            raise RuntimeError(f"{name} missing from the Figshare article")
        if info["computed_md5"] != spec["md5"]:
            raise RuntimeError(f"Figshare md5 for {name} changed: {info['computed_md5']} != stored {spec['md5']}")
        status = download(info["download_url"], root / spec["target"], spec["md5"], cfg["chunk_bytes"], cfg["user_agent"])
        records.append({"name": name, "status": status})
    return records, True


def main(argv=None):
    parser = add_root_args(argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter))
    parser.add_argument("--raw-source", type=Path, default=None,
                        help="folder holding the Figshare files (read-only is fine); the API is then never called")
    args = parser.parse_args(argv)
    roots = roots_from_args(args)
    cfg, config_path = load_config(CONFIG)
    root = roots.data_path(cfg["download_root"])
    root.mkdir(parents=True, exist_ok=True)

    if args.raw_source:
        mode, api_called = "raw_source", False
        records = stage_from_raw_source(args.raw_source.resolve(), root, cfg)
    else:
        records, api_called = stage_online(root, cfg)
        mode = "api_download" if api_called else "offline_verified"

    zip_spec = cfg["files"][EDF_ZIP]
    zip_path = root / zip_spec["target"]
    extracted = None
    if edf_tree_status(root, cfg) != ([], []):
        if not (zip_path.exists() and md5_file(zip_path) == zip_spec["md5"]):
            raise RuntimeError("Extracted EDF tree incomplete and no verified edffile.zip to extract from")
        extracted = safe_extract(zip_path, root / zip_spec["extract_to"])
    missing, mismatched = edf_tree_status(root, cfg)
    if missing or mismatched:
        raise RuntimeError(f"EDF verification failed: missing={missing} sha256_mismatch={mismatched}")
    for r in records:
        print(f"{r['name']}: {r['status']}")

    write_with_config(roots.out_path(cfg["manifest_output"]),
                      {"mode": mode, "api_called": api_called, "raw_source": str(args.raw_source) if args.raw_source else None,
                       "article": {"id": cfg["article_id"], "doi": cfg["expected_doi"], "citation": cfg["citation"]},
                       "files": records, "zip_extracted_members": extracted,
                       "edf_verified": {"n": len(cfg["edf_sha256"]), "all_sha256_match": True,
                                        "root": display_path(root, roots.data)},
                       "not_downloaded": cfg["not_downloaded"]},
                      config_path, sources=[Path(__file__)], roots=roots)
    print(f"Mode {mode}; API called: {api_called}; {len(cfg['edf_sha256'])} EDFs sha256-verified")


if __name__ == "__main__":
    main()
