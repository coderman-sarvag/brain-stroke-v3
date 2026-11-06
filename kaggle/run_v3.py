"""Run v3 pipeline steps on Kaggle (or locally), resumably, with per-step log files.

Examples (Kaggle notebook):
  # download from Figshare (internet on)
  python kaggle/run_v3.py --steps 0 1 2 --step2-mode diagnostic \
      --data-root /kaggle/working/data --out-root /kaggle/working/v3_out
  # use an uploaded Kaggle dataset (no API call; md5/sha256 verified)
  python kaggle/run_v3.py --steps 0 1 2 --step2-mode diagnostic --raw-source /kaggle/input/<dataset> \
      --data-root /kaggle/working/data --out-root /kaggle/working/v3_out

Steps: 0 = Figshare download + data check, 1 = integrity, 2 = preprocessing (--step2-mode diagnostic|final).
A step is skipped when out-root/kaggle_state/<step>.json shows it completed with the same config and source hashes
(--force reruns it); step 2 additionally resumes per subject. Writes out-root/kaggle_summary.json and
out-root/v3_outputs_small.zip (CSV/JSON/MD and configs only; never FIF/EDF or raw data).
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import zipfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from provenance_v3 import git_commit, sha256_file  # noqa: E402

STEPS = {
    "0": {"name": "step0_data", "scripts": [["src/download_figshare_v3.py"], ["src/check_data_v3.py"]],
          "configs": ["configs/v3/figshare_download.json", "configs/v3/data_check.json"]},
    "1": {"name": "step1_integrity", "scripts": [["src/integrity_v3.py"]], "configs": ["configs/v3/integrity.json"]},
    "2": {"name": "step2_preprocess", "scripts": [["src/preprocess_v3.py", "--mode", "{mode}"]],
          "configs": ["configs/v3/preprocess.json"]},
    "3": {"name": "step3_spectral", "scripts": [["src/spectral_v3.py"]], "configs": ["configs/v3/spectral.json"]},
}
SMALL_SUFFIXES = {".csv", ".json", ".md"}
MAX_SMALL_BYTES = 50 * 1024 * 1024


def fingerprint(step, mode, subjects=None):
    spec = STEPS[step]
    files = spec["configs"] + [s[0] for s in spec["scripts"]] + ["src/provenance_v3.py", "src/paths_v3.py"]
    return {"mode": mode if step == "2" else None, "subjects": sorted(subjects) if step == "2" and subjects else None,
            "sha256": {f: sha256_file(REPO / f) for f in files}}


def state_path(out_root, step, mode):
    suffix = f"_{mode}" if step == "2" else ""
    return out_root / "kaggle_state" / f"{STEPS[step]['name']}{suffix}.json"


def tail(path, n=40):
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError:
        return []


def run_script(cmd, log_path, env):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n===== {datetime.now(timezone.utc).isoformat()} :: {' '.join(cmd)}\n")
        log.flush()
        return subprocess.run(cmd, cwd=REPO, stdout=log, stderr=subprocess.STDOUT, env=env).returncode


def small_outputs_zip(out_root, data_root, zip_path):
    """Zip CSV/JSON/MD files and configs under out-root; skip raw data, processed EEG, FIF/EDF and large files."""
    skip_dirs = [data_root.resolve(), (out_root / "data").resolve()]
    added = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(out_root.rglob("*")):
            if not path.is_file() or path.resolve() == zip_path.resolve():
                continue
            if any(path.resolve().is_relative_to(d) for d in skip_dirs):
                continue
            if path.suffix.lower() not in SMALL_SUFFIXES or path.stat().st_size > MAX_SMALL_BYTES:
                continue
            arc = path.relative_to(out_root).as_posix()
            zf.write(path, arc)
            added.append(arc)
        for cfg in sorted((REPO / "configs" / "v3").glob("*.json")):
            arc = f"repo_configs/v3/{cfg.name}"
            zf.write(cfg, arc)
            added.append(arc)
    return added


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--steps", nargs="+", choices=sorted(STEPS), required=True)
    p.add_argument("--step2-mode", choices=["diagnostic", "final"], default="diagnostic")
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--out-root", type=Path, required=True)
    p.add_argument("--prev-root", type=Path, default=None, help="earlier-step outputs (default: out-root)")
    p.add_argument("--n-jobs", type=int, default=None, help="step 2 parallel subjects (default: config)")
    p.add_argument("--subjects", nargs="+", default=None, help="step 2 only: subset of subjects (smoke tests)")
    p.add_argument("--raw-source", type=Path, default=None,
                   help="step 0 only: folder with the Figshare files (e.g. /kaggle/input/...); no API call")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    data_root, out_root = args.data_root.resolve(), args.out_root.resolve()
    prev_root = (args.prev_root or args.out_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)
    git = git_commit()
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "MPLBACKEND": "Agg", "V3_GIT_COMMIT": git["commit"] or ""}
    roots = ["--data-root", str(data_root), "--out-root", str(out_root), "--prev-root", str(prev_root)]
    logs = out_root / "kaggle_logs"

    env_rc = run_script([sys.executable, "src/record_environment_v3.py", *roots], logs / "environment.log", env)
    env_json = out_root / "configs" / "v3" / "environment.json"
    environment = json.loads(env_json.read_text(encoding="utf-8")) if env_json.exists() else {}

    summary = {"started_utc": datetime.now(timezone.utc).isoformat(), "git": git, "python": sys.version.split()[0],
               "platform": platform.platform(), "cpu_count": os.cpu_count(),
               "roots": {"data": str(data_root), "out": str(out_root), "prev": str(prev_root)},
               "environment_record_rc": env_rc, "key_packages": environment.get("key_packages"), "steps": []}
    overall = 0
    for step in args.steps:
        spec, mode = STEPS[step], args.step2_mode
        fp, state = fingerprint(step, mode, args.subjects), state_path(out_root, step, mode)
        record = {"step": step, "name": spec["name"], "mode": fp["mode"]}
        if not args.force and state.exists() and json.loads(state.read_text(encoding="utf-8")).get("fingerprint") == fp:
            record.update(status="skipped_already_done")
            summary["steps"].append(record)
            print(f"[{spec['name']}] already done with identical configs/code; skipped", flush=True)
            continue
        log_path = logs / f"{spec['name']}{'_' + mode if step == '2' else ''}.log"
        start, rcs = time.time(), []
        for script in spec["scripts"]:
            cmd = [sys.executable, *[a.format(mode=mode) for a in script], *roots]
            if script[0] == "src/download_figshare_v3.py" and args.raw_source:
                cmd += ["--raw-source", str(args.raw_source.resolve())]
            if step == "2":
                cmd += (["--n-jobs", str(args.n_jobs)] if args.n_jobs else []) + (["--force"] if args.force else [])
                cmd += ["--subjects", *args.subjects] if args.subjects else []
            print(f"[{spec['name']}] running {' '.join(cmd[1:3])} ... (log: {log_path})", flush=True)
            rc = run_script(cmd, log_path, env)
            rcs.append(rc)
            if rc != 0:
                break
        ok = all(rc == 0 for rc in rcs) and len(rcs) == len(spec["scripts"])
        record.update(status="ok" if ok else "failed", return_codes=rcs, seconds=round(time.time() - start, 1),
                      log=str(log_path), log_tail=tail(log_path))
        summary["steps"].append(record)
        print(f"[{spec['name']}] {record['status']} in {record['seconds']} s", flush=True)
        if ok:
            state.parent.mkdir(parents=True, exist_ok=True)
            state.write_text(json.dumps({"fingerprint": fp, "completed_utc": datetime.now(timezone.utc).isoformat()},
                                        indent=1), encoding="utf-8")
        else:
            overall = 1
            break  # later steps depend on this one

    summary["finished_utc"] = datetime.now(timezone.utc).isoformat()
    summary_path = out_root / "kaggle_summary.json"
    summary_path.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    zip_path = out_root / "v3_outputs_small.zip"
    added = small_outputs_zip(out_root, data_root, zip_path)
    print(f"Summary: {summary_path}\nSmall outputs: {zip_path} ({len(added)} files)", flush=True)
    return overall


if __name__ == "__main__":
    raise SystemExit(main())
