"""Step 0: record the Python/package environment to <out-root>/configs/v3/environment.json.

Run from the repo root with the venv interpreter: .venv/Scripts/python src/record_environment_v3.py [--out-root O]
"""
import argparse
from datetime import datetime, timezone
from importlib import metadata
import json
from pathlib import Path
import platform
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths_v3 import add_root_args, roots_from_args  # noqa: E402

KEY_PACKAGES = ("mne", "mne-connectivity", "python-picard", "pyprep", "mne-icalabel", "moabb", "numpy", "scipy",
                "pandas", "scikit-learn", "networkx", "matplotlib", "joblib", "edfio", "pytest")


def version(name):
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def environment():
    return {"date_utc": datetime.now(timezone.utc).isoformat(),
            "python": sys.version.split()[0], "implementation": platform.python_implementation(),
            "platform": platform.platform(), "venv": sys.prefix != sys.base_prefix,
            "requirements_file": "requirements.txt",
            "key_packages": {name: version(name) for name in KEY_PACKAGES},
            "all_packages": dict(sorted((d.metadata["Name"], d.version) for d in metadata.distributions()
                                        if d.metadata["Name"]))}


def main(argv=None):
    roots = roots_from_args(add_root_args(argparse.ArgumentParser(description=__doc__)).parse_args(argv))
    env = environment()
    out = roots.out_path("configs/v3/environment.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(env, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(env["key_packages"], indent=2))


if __name__ == "__main__":
    main()
