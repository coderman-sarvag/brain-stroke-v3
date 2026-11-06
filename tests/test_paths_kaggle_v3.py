"""Path roots (Kaggle mode) and the small-outputs zip filter."""
import argparse
import importlib.util
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from paths_v3 import add_root_args, roots_from_args  # noqa: E402
from provenance_v3 import display_path  # noqa: E402

spec = importlib.util.spec_from_file_location("run_v3", ROOT / "kaggle" / "run_v3.py")
run_v3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_v3)


def parse(argv):
    return roots_from_args(add_root_args(argparse.ArgumentParser()).parse_args(argv))


def test_default_roots_match_local_layout():
    roots = parse([])
    assert roots.data == (ROOT / "data" / "raw").resolve()
    assert roots.out == ROOT.resolve() and roots.prev == roots.out
    assert roots.data_path("figshare/participants.tsv") == ROOT.resolve() / "data/raw/figshare/participants.tsv"


def test_custom_roots_and_prev_default(tmp_path):
    roots = parse(["--data-root", str(tmp_path / "in"), "--out-root", str(tmp_path / "out")])
    assert roots.prev == (tmp_path / "out").resolve()
    assert roots.out_path("results/v3/x.csv") == (tmp_path / "out/results/v3/x.csv").resolve()
    roots = parse(["--data-root", "d", "--out-root", str(tmp_path / "o"), "--prev-root", str(tmp_path / "p")])
    assert roots.prev_path("features/v3/a.csv") == (tmp_path / "p/features/v3/a.csv").resolve()


def test_display_path_outside_repo_is_absolute(tmp_path):
    assert display_path(ROOT / "src" / "paths_v3.py") == "src/paths_v3.py"
    assert display_path(tmp_path / "a.json") == (tmp_path / "a.json").resolve().as_posix()


def test_small_outputs_zip_keeps_only_small_text_outputs(tmp_path):
    out, data = tmp_path / "out", tmp_path / "out" / "data_in"
    files = {"results/v3/step2/a.csv": "x", "results/v3/step2/b.json": "{}", "docs/r.md": "#",
             "data/processed/figshare_v3/sub-01-epo.fif": "fif", "data_in/figshare/participants.json": "{}",
             "results/v3/step2/x.edf": "edf", "kaggle_logs/step.log": "log"}
    for rel, text in files.items():
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text(text)
    zip_path = out / "v3_outputs_small.zip"
    added = run_v3.small_outputs_zip(out, data, zip_path)
    names = set(zipfile.ZipFile(zip_path).namelist())
    assert {"results/v3/step2/a.csv", "results/v3/step2/b.json", "docs/r.md"} <= names
    assert not any(n.endswith((".fif", ".edf", ".log")) for n in names)
    assert not any(n.startswith(("data/", "data_in/")) for n in names)
    assert "repo_configs/v3/preprocess.json" in names and set(added) == names
