"""The config copy written beside an output must never overwrite that output."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import provenance_v3  # noqa: E402


def test_config_copy_does_not_overwrite_same_named_output(tmp_path, monkeypatch):
    monkeypatch.setattr(provenance_v3, "ROOT", tmp_path)
    config = tmp_path / "configs" / "data_check.json"
    config.parent.mkdir()
    config.write_text('{"a": 1}', encoding="utf-8")
    out = provenance_v3.write_with_config(tmp_path / "results" / "data_check.json", {"summary": {"ok": True}}, config)
    assert json.loads(out.read_text())["summary"] == {"ok": True}
    assert json.loads((out.parent / "data_check.config.json").read_text()) == {"a": 1}
    assert len(json.loads(out.read_text())["provenance"]["config_sha256"]) == 64
