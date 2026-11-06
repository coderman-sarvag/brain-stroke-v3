"""Synthetic tests for the Step 0 download and data-check helpers."""
from pathlib import Path
import sys
import zipfile

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from check_data_v3 import imagery_events, is_constant  # noqa: E402
from download_figshare_v3 import download, safe_extract  # noqa: E402
from provenance_v3 import md5_file  # noqa: E402

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
