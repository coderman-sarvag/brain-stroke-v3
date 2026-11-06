"""Synthetic tests for the Step 0 download and data-check helpers."""
import json
from pathlib import Path
import shutil
import sys
import zipfile

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import download_figshare_v3 as dl  # noqa: E402
from check_data_v3 import imagery_events, is_constant  # noqa: E402
from download_figshare_v3 import download, safe_extract  # noqa: E402
from provenance_v3 import md5_file, sha256_file  # noqa: E402

CFG = {"imagery_event_value": 2, "events_onset_unit_divisor": 1000,
       "trial_type_codes": {"1": "left_hand", "2": "right_hand"}}


def test_imagery_events_converts_ms_to_samples_and_names():
    table = pd.DataFrame({"onset": [0, 2000, 6000, 8000], "value": [1, 2, 1, 2], "trial_type": [1, 1, 2, 2]})
    samples, names = imagery_events(table, 500.0, CFG)
    assert samples.tolist() == [1000, 4000]
    assert names.tolist() == ["left_hand", "right_hand"]


def test_imagery_events_rejects_unknown_trial_type():
    table = pd.DataFrame({"onset": [0], "value": [2], "trial_type": [9]})
    with pytest.raises(ValueError):
        imagery_events(table, 500.0, CFG)


def test_is_constant():
    assert is_constant(np.zeros(100), 1e-12)
    assert not is_constant(np.r_[np.zeros(99), 1e-6], 1e-12)


def test_safe_extract_rejects_traversal(tmp_path):
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("../evil.txt", "x")
    with pytest.raises(ValueError):
        safe_extract(bad, tmp_path / "out")
    assert not (tmp_path / "evil.txt").exists()


def test_safe_extract_extracts_normal_members(tmp_path):
    good = tmp_path / "good.zip"
    with zipfile.ZipFile(good, "w") as z:
        z.writestr("edffile/sub-01/eeg/a.txt", "x")
    assert safe_extract(good, tmp_path / "out") == 1
    assert (tmp_path / "out/edffile/sub-01/eeg/a.txt").read_text() == "x"


def test_download_rejects_md5_mismatch(tmp_path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"payload")
    target = tmp_path / "dst.bin"
    with pytest.raises(RuntimeError):
        download(src.as_uri(), target, "0" * 32, 4)
    assert not target.exists() and not target.with_name("dst.bin.part").exists()
    assert download(src.as_uri(), target, md5_file(src), 4) == "downloaded_verified"
    assert download(src.as_uri(), target, md5_file(src), 4) == "already_present_verified"


# ---------------------------------------------------------------- offline / raw-source staging

EDF_REL = "extracted/edffile/{subject}/eeg/{subject}_task-motor-imagery_eeg.edf"


def fake_dataset(tmp_path):
    """A tiny stand-in for the Figshare files: a zip with one EDF, plus participants.tsv."""
    build = tmp_path / "build"
    edf = build / "edffile" / "sub-01" / "eeg" / "sub-01_task-motor-imagery_eeg.edf"
    edf.parent.mkdir(parents=True)
    edf.write_bytes(b"EDF-bytes-sub-01")
    zpath = build / "edffile.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.write(edf, "edffile/sub-01/eeg/sub-01_task-motor-imagery_eeg.edf")
    tsv = build / "participants.tsv"
    tsv.write_text("Participant_ID\nsub-01\n")
    cfg = {"files": {"edffile.zip": {"target": "edffile.zip", "extract_to": "extracted", "md5": md5_file(zpath)},
                     "participants.tsv": {"target": "participants.tsv", "md5": md5_file(tsv)}},
           "edf_sha256": {"sub-01": sha256_file(edf)}, "edf_relative_template": EDF_REL,
           "api_url": "https://example.invalid/api", "expected_doi": "x", "chunk_bytes": 8, "user_agent": "UA-test",
           "download_root": "figshare", "manifest_output": "results/v3/step0/download_manifest.json",
           "article_id": 1, "citation": "c", "not_downloaded": {}}
    return build, edf, zpath, tsv, cfg


def no_network(*args, **kwargs):
    raise AssertionError("network must not be used")


def test_open_url_sends_browser_user_agent(monkeypatch):
    seen = {}
    monkeypatch.setattr(dl.urllib.request, "urlopen", lambda req, timeout: seen.setdefault("req", req))
    dl.open_url("https://api.figshare.com/v2/articles/1", "Mozilla/5.0 test")
    assert seen["req"].get_header("User-agent") == "Mozilla/5.0 test"


def test_real_config_stores_all_hashes():
    cfg = json.loads((Path(__file__).resolve().parents[1] / "configs/v3/figshare_download.json").read_text(encoding="utf-8"))
    assert all(len(spec["md5"]) == 32 for spec in cfg["files"].values()) and len(cfg["files"]) == 11
    assert len(cfg["edf_sha256"]) == 50 and cfg["user_agent"].startswith("Mozilla/5.0")


def test_raw_source_zip_is_copied_verified_and_never_calls_api(tmp_path, monkeypatch):
    build, _, _, _, cfg = fake_dataset(tmp_path)
    source = tmp_path / "kaggle_input" / "nested"
    source.mkdir(parents=True)
    for f in ("edffile.zip", "participants.tsv"):
        shutil.copy(build / f, source / f)
    monkeypatch.setattr(dl, "fetch_metadata", no_network)
    root = tmp_path / "data" / "figshare"
    records = dl.stage_from_raw_source(tmp_path / "kaggle_input", root, cfg)
    assert {r["status"] for r in records} == {"copied_verified"}
    dl.safe_extract(root / "edffile.zip", root / "extracted")
    assert dl.edf_tree_status(root, cfg) == ([], [])


def test_raw_source_accepts_already_extracted_tree(tmp_path, monkeypatch):
    build, edf, _, tsv, cfg = fake_dataset(tmp_path)
    source = tmp_path / "kaggle_input"          # Kaggle auto-unzipped the upload: no edffile.zip
    shutil.copytree(build / "edffile", source / "edffile")
    shutil.copy(tsv, source / "participants.tsv")
    monkeypatch.setattr(dl, "fetch_metadata", no_network)
    root = tmp_path / "data" / "figshare"
    dl.stage_from_raw_source(source, root, cfg)
    assert dl.edf_tree_status(root, cfg) == ([], [])


def test_raw_source_rejects_wrong_hash_and_missing_files(tmp_path):
    build, _, _, tsv, cfg = fake_dataset(tmp_path)
    source = tmp_path / "src"
    source.mkdir()
    shutil.copy(build / "edffile.zip", source / "edffile.zip")
    (source / "participants.tsv").write_text("tampered\n")
    root = tmp_path / "data" / "figshare"
    with pytest.raises(RuntimeError, match="hash mismatch"):
        dl.stage_from_raw_source(source, root, cfg)
    assert not (root / "participants.tsv").exists() and not (root / "participants.tsv.part").exists()
    (source / "participants.tsv").unlink()
    with pytest.raises(RuntimeError, match="Not found"):
        dl.stage_from_raw_source(source, root, cfg)


def test_offline_verified_files_skip_the_api(tmp_path, monkeypatch):
    build, _, _, _, cfg = fake_dataset(tmp_path)
    root = tmp_path / "figshare"
    root.mkdir()
    for f in ("edffile.zip", "participants.tsv"):
        shutil.copy(build / f, root / f)
    monkeypatch.setattr(dl, "fetch_metadata", no_network)
    records, api_called = dl.stage_online(root, cfg)
    assert api_called is False and {r["status"] for r in records} == {"already_present_verified"}


def test_api_md5_must_match_stored_md5(tmp_path, monkeypatch):
    _, _, _, _, cfg = fake_dataset(tmp_path)
    meta = {"doi": "x", "files": [{"name": n, "computed_md5": "0" * 32, "download_url": "u"} for n in cfg["files"]]}
    monkeypatch.setattr(dl, "fetch_metadata", lambda url, ua: meta)
    with pytest.raises(RuntimeError, match="changed"):
        dl.stage_online(tmp_path / "empty", cfg)


def test_main_with_raw_source_end_to_end(tmp_path, monkeypatch):
    build, _, _, _, cfg = fake_dataset(tmp_path)
    cfg_path = tmp_path / "figshare_download.json"
    cfg_path.write_text(json.dumps(cfg))
    monkeypatch.setattr(dl, "load_config", lambda rel: (cfg, cfg_path))
    monkeypatch.setattr(dl, "fetch_metadata", no_network)
    out = tmp_path / "out"
    dl.main(["--raw-source", str(build), "--data-root", str(tmp_path / "data"), "--out-root", str(out)])
    manifest = json.loads((out / "results/v3/step0/download_manifest.json").read_text())
    assert manifest["mode"] == "raw_source" and manifest["api_called"] is False
    assert manifest["edf_verified"]["all_sha256_match"] and manifest["zip_extracted_members"] == 1
