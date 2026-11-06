"""Step 0 acceptance: every EDF opens at 500 Hz with 33 channels, the shared events file
yields 40 imagery events (20 left / 20 right) inside each recording, and CPz is constant.

Run from the repo root: python src/check_data_v3.py
Reads no clinical fields.
"""
from pathlib import Path
import sys

import mne
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provenance_v3 import ROOT, load_config, sha256_file, write_with_config  # noqa: E402

CONFIG = "configs/v3/data_check.json"


def imagery_events(events_table, sfreq, cfg):
    """Return (sample, trial_name) for imagery onsets of the shared BIDS events table."""
    imagery = events_table[events_table["value"] == cfg["imagery_event_value"]]
    samples = (imagery["onset"].to_numpy(float) * sfreq / cfg["events_onset_unit_divisor"]).round().astype(int)
    names = imagery["trial_type"].astype(str).map(cfg["trial_type_codes"])
    if names.isna().any():
        raise ValueError("Unknown trial_type in events table")
    return samples, names.to_numpy()


def is_constant(signal, tol):
    return bool(np.ptp(signal) <= tol)


def check_subject(path, events_table, cfg):
    raw = mne.io.read_raw_edf(path, preload=False, verbose="ERROR")
    exp = cfg["expected"]
    samples, names = imagery_events(events_table, raw.info["sfreq"], cfg)
    ref = cfg["reference_channel"]
    ref_data = raw.get_data(picks=[ref])[0] if ref in raw.ch_names else None
    eeg_ptp = {ch: float(np.ptp(x)) for ch, x in zip(raw.ch_names, raw.get_data())}
    flat_other = sorted(ch for ch, v in eeg_ptp.items() if v <= cfg["constant_tolerance_volts"] and ch != ref)
    row = {"subject_id": path.parts[-3], "file": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path),
           "sfreq": float(raw.info["sfreq"]), "n_channels": len(raw.ch_names), "n_times": int(raw.n_times),
           "duration_s": float(raw.n_times / raw.info["sfreq"]),
           "n_imagery_events": int(len(samples)), "n_left": int((names == "left_hand").sum()),
           "n_right": int((names == "right_hand").sum()),
           "last_event_end_s": float((samples.max() + 4 * raw.info["sfreq"]) / raw.info["sfreq"]),
           "events_inside_recording": bool(samples.max() + 4 * raw.info["sfreq"] <= raw.n_times),
           "cpz_present": ref_data is not None,
           "cpz_constant": None if ref_data is None else is_constant(ref_data, cfg["constant_tolerance_volts"]),
           "cpz_value": None if ref_data is None else float(ref_data[0]),
           "other_flat_channels": flat_other,
           "channels": raw.ch_names}
    row["pass"] = (row["sfreq"] == exp["sfreq"] and row["n_channels"] == exp["n_channels"]
                   and row["n_imagery_events"] == exp["n_imagery_events"] and row["n_left"] == exp["n_left"]
                   and row["n_right"] == exp["n_right"] and row["events_inside_recording"] and bool(row["cpz_constant"]))
    return row


def main():
    cfg, config_path = load_config(CONFIG)
    events_path = ROOT / cfg["events_tsv"]
    events_table = pd.read_csv(events_path, sep="\t")
    paths = sorted(ROOT.glob(cfg["edf_glob"]))
    rows = [check_subject(p, events_table, cfg) for p in paths]
    channel_sets = {tuple(r["channels"]) for r in rows}
    summary = {"n_edf_files": len(paths), "n_expected": cfg["expected"]["n_subjects"],
               "n_pass": sum(r["pass"] for r in rows), "failed": [r["subject_id"] for r in rows if not r["pass"]],
               "identical_channel_list_across_subjects": len(channel_sets) == 1,
               "channel_list": rows[0]["channels"] if rows else [],
               "duration_s_min_max": [min(r["duration_s"] for r in rows), max(r["duration_s"] for r in rows)] if rows else None,
               "subjects_with_other_flat_channels": {r["subject_id"]: r["other_flat_channels"] for r in rows if r["other_flat_channels"]}}
    summary["accepted"] = summary["n_edf_files"] == summary["n_expected"] and summary["n_pass"] == summary["n_expected"]
    out = write_with_config(ROOT / cfg["output"], {"summary": summary, "subjects": rows}, config_path,
                            sources=[Path(__file__), events_path])
    pd.DataFrame(rows).drop(columns=["channels"]).to_csv(out.with_suffix(".csv"), index=False)
    print({k: v for k, v in summary.items() if k != "channel_list"})
    print("channels:", summary["channel_list"])
    return 0 if summary["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
