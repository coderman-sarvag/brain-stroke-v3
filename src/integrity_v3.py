"""Step 1: label-blind data integrity for the Figshare cohort.

Produces features/v3/subject_meta_v3.csv (metadata only, no features, no outcome labels)
plus duplicate, event-timing and lesion-side evidence under results/v3/step1/.
Reads participants.tsv through an explicit column allow-list: NIHSS, MBI and mRS are never loaded.

Run from the repo root: python src/integrity_v3.py [--data-root D] [--out-root O]
"""
import argparse
import hashlib
from itertools import combinations
import json
from pathlib import Path
import re
import sys

import mne
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths_v3 import add_root_args, roots_from_args  # noqa: E402
from provenance_v3 import load_config, write_with_config  # noqa: E402

CONFIG = "configs/v3/integrity.json"
OPPOSITE = {"left": "right", "right": "left"}


# ---------------------------------------------------------------- metadata

def load_participants(cfg, roots):
    allowed = cfg["allowed_participant_columns"]
    if set(allowed) & set(cfg["forbidden_participant_columns"]):
        raise ValueError("An outcome column is in the allow-list")
    table = pd.read_csv(roots.data_path(cfg["participants_tsv"]), sep="\t", usecols=list(allowed), dtype=str)
    table = table.rename(columns=allowed)
    for col in table.columns:
        table[col] = table[col].str.strip()
    if table["subject_id"].duplicated().any():
        raise ValueError("Duplicate subject IDs in participants.tsv")
    return table.sort_values("subject_id").reset_index(drop=True)


def split_location(text):
    return [p.strip() for p in str(text).split(",") if p.strip()]


def component_side(component, side_words):
    words = component.casefold()
    found = {side for word, side in side_words.items() if re.search(rf"\b{word}\b", words)}
    return found.pop() if len(found) == 1 else ("mixed" if found else None)


def location_side(text, side_words):
    sides = [component_side(c, side_words) for c in split_location(text)]
    if not sides or any(s is None for s in sides):
        return "unclear"
    if "bilateral" in sides:
        return "bilateral"
    unique = set(sides)
    return unique.pop() if len(unique) == 1 and unique <= {"left", "right"} else "mixed"


def site_class(text, lesion_cfg):
    text = str(text).casefold()
    has = lambda keys: any(k in text for k in keys)  # noqa: E731
    if has(lesion_cfg["cortical_keywords"]):
        cls = "cortical_involving"
    elif has(lesion_cfg["subcortical_supratentorial_keywords"]):
        cls = "subcortical_supratentorial"
    elif has(lesion_cfg["infratentorial_keywords"]):
        cls = "infratentorial"
    else:
        cls = "unclear"
    return cls, has(lesion_cfg["infratentorial_keywords"])


def lesion_table(meta, lesion_cfg):
    rows = []
    for _, r in meta.iterrows():
        loc_side = location_side(r["stroke_location"], lesion_cfg["side_words"])
        para = r["paralysis_side"].casefold()
        from_paralysis = OPPOSITE.get(para, "unclear")
        cls, infra = site_class(r["stroke_location"], lesion_cfg)
        agree = loc_side == from_paralysis and from_paralysis in OPPOSITE
        rows.append({"subject_id": r["subject_id"], "location_side": loc_side,
                     "lesion_side_paralysis": from_paralysis, "lesion_side_agree": agree,
                     "lesion_side_final": from_paralysis if agree else "uncertain",
                     "site_class": cls, "has_infratentorial": infra})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- signals

def subject_of(path):
    return Path(path).parts[-3]


def load_signals(paths, channels):
    """Return per-subject channel hashes, constant flags and z-scored float32 signals."""
    hashes, constant, z = {}, {}, None
    for i, path in enumerate(paths):
        raw = mne.io.read_raw_edf(path, preload=True, verbose="ERROR")
        data = raw.get_data(picks=channels)
        if z is None:
            z = np.zeros((len(paths), len(channels), data.shape[1]), dtype=np.float32)
        sid = subject_of(path)
        hashes[sid] = [hashlib.sha256(row.tobytes()).hexdigest() for row in data]
        sd = data.std(axis=1)
        constant[sid] = (sd == 0).tolist()
        sd[sd == 0] = 1.0
        z[i] = ((data - data.mean(axis=1, keepdims=True)) / sd[:, None]).astype(np.float32)
    return hashes, constant, z


def pairwise_similarity(subjects, channels, hashes, constant, z):
    n_times = z.shape[2]
    corr = np.stack([(z[:, c, :].astype(np.float64) @ z[:, c, :].T.astype(np.float64)) / n_times
                     for c in range(len(channels))])  # (channel, subject, subject)
    rows = []
    for a, b in combinations(range(len(subjects)), 2):
        sa, sb = subjects[a], subjects[b]
        usable = [c for c in range(len(channels)) if not constant[sa][c] and not constant[sb][c]]
        identical = [c for c in usable if hashes[sa][c] == hashes[sb][c]]
        r = corr[usable, a, b]
        rows.append({"subject_a": sa, "subject_b": sb, "n_channels_compared": len(usable),
                     "n_identical_channels": len(identical),
                     "identical_channels": ";".join(channels[c] for c in identical),
                     "median_r": float(np.median(r)), "min_r": float(r.min()), "max_r": float(r.max())})
    return pd.DataFrame(rows)


def classify_pairs(pairs, threshold):
    pairs = pairs.copy()
    pairs["identical"] = (pairs["n_identical_channels"] == pairs["n_channels_compared"]) & (pairs["n_channels_compared"] > 0)
    pairs["near_duplicate"] = ~pairs["identical"] & (pairs["median_r"] >= threshold)
    return pairs


def split_groups(subjects, flagged_pairs):
    """Union-find: subjects linked by any flagged pair share one split group."""
    parent = {s: s for s in subjects}

    def find(s):
        while parent[s] != s:
            parent[s] = parent[parent[s]]
            s = parent[s]
        return s

    for a, b in flagged_pairs:
        parent[find(b)] = find(a)
    return {s: find(s) for s in subjects}


# ---------------------------------------------------------------- events

def marker_events(marker, scale):
    """Return (samples, codes) for every change of the marker code to a non-zero value."""
    codes = np.rint(marker / scale).astype(int)
    idx = np.flatnonzero((codes != 0) & (codes != np.r_[0, codes[:-1]]))
    return idx, codes[idx]


def imagery_trials(samples, codes, n_times, imagery_code=2, break_code=3):
    """Imagery onsets and their length up to the next break event (or recording end)."""
    onsets = samples[codes == imagery_code]
    breaks = samples[codes == break_code]
    ends = [breaks[breaks > o][0] if np.any(breaks > o) else n_times for o in onsets]
    return onsets, np.asarray(ends) - onsets


def event_timing(path, events_table, ev_cfg):
    raw = mne.io.read_raw_edf(path, preload=False, verbose="ERROR")
    sf, sid = raw.info["sfreq"], subject_of(path)
    samples, codes = marker_events(raw.get_data(picks=[ev_cfg["marker_channel"]])[0], ev_cfg["marker_scale"])
    onsets, lengths = imagery_trials(samples, codes, raw.n_times, ev_cfg["imagery_value"])
    imagery = events_table[events_table["value"] == ev_cfg["imagery_value"]].reset_index(drop=True)
    sidecar = np.rint(imagery["onset"].to_numpy(float) * sf / ev_cfg["sidecar_onset_divisor"]).astype(int)
    counts = {name: int((codes == int(code)).sum()) for code, name in ev_cfg["marker_codes"].items()}
    match = match_to_sidecar(onsets, sidecar, ev_cfg["match_window_samples"])
    trial_type = imagery["trial_type"].astype(str).to_numpy()
    short = lengths < ev_cfg["imagery_samples_nominal"] - ev_cfg["imagery_short_tolerance_samples"]
    trials = pd.DataFrame({"subject_id": sid, "marker_index": np.arange(len(onsets)), "marker_onset": onsets,
                           "imagery_samples": lengths, "short_imagery": short, "sidecar_trial": match})
    matched = match >= 0
    trials["sidecar_onset"] = np.where(matched, sidecar[np.maximum(match, 0)], -1)
    trials["trial_type"] = np.where(matched, trial_type[np.maximum(match, 0)], "")
    trials["lag_samples"] = np.where(matched, onsets - trials["sidecar_onset"], np.nan)
    trials["usable"] = matched & ~short
    lag = trials["lag_samples"].abs()
    row = {"subject_id": sid, **{f"n_{k}": v for k, v in counts.items()},
           "n_imagery_markers": int(len(onsets)), "n_matched": int(matched.sum()),
           "n_unmatched_markers": int((~matched).sum()), "n_short_imagery": int(short.sum()),
           "n_usable_trials": int(trials["usable"].sum()),
           "n_usable_left": int((trials["usable"] & (trials["trial_type"] == "1")).sum()),
           "n_usable_right": int((trials["usable"] & (trials["trial_type"] == "2")).sum()),
           "lag_samples_min": float(trials["lag_samples"].min()),
           "lag_samples_median": float(trials["lag_samples"].median()),
           "lag_samples_max": float(trials["lag_samples"].max()),
           "n_trials_lag_gt_preset": int((lag > ev_cfg["max_abs_lag_samples"]).sum()),
           "n_trials_lag_gt_tolerance": int((lag > ev_cfg["sidecar_agreement_max_abs_lag_samples"]).sum())}
    row["sidecar_agrees"] = bool(row["n_usable_trials"] == ev_cfg["expected_per_code"]
                                 and row["n_unmatched_markers"] == 0 and row["n_trials_lag_gt_tolerance"] == 0)
    return row, trials


def match_to_sidecar(onsets, sidecar, window):
    """One-to-one nearest match of marker onsets to sidecar onsets within +-window; -1 = unmatched."""
    match = np.full(len(onsets), -1)
    pairs = sorted((abs(int(o) - int(s)), i, j) for i, o in enumerate(onsets) for j, s in enumerate(sidecar)
                   if abs(int(o) - int(s)) < window)
    used_i, used_j = set(), set()
    for _, i, j in pairs:
        if i not in used_i and j not in used_j:
            match[i] = j
            used_i.add(i)
            used_j.add(j)
    return match


# ---------------------------------------------------------------- sidecar labels

def channel_label_check(edf_channels, channels_tsv):
    side = pd.read_csv(channels_tsv, sep="\t")
    sidecar = side["name"].tolist()
    return {"edf_named_channels": [c for c in edf_channels if c],
            "sidecar_channels": sidecar,
            "in_edf_not_sidecar": [c for c in edf_channels if c and c not in sidecar],
            "in_sidecar_not_edf": [c for c in sidecar if c not in edf_channels],
            "sidecar_eog": side.loc[side["type"].str.upper() == "EOG", "name"].tolist()}


# ---------------------------------------------------------------- main

def main(argv=None):
    roots = roots_from_args(add_root_args(argparse.ArgumentParser(description=__doc__)).parse_args(argv))
    cfg, config_path = load_config(CONFIG)
    meta = load_participants(cfg, roots)
    subjects = meta["subject_id"].tolist()
    paths = sorted(roots.data.glob(cfg["edf_glob"]))
    if [subject_of(p) for p in paths] != subjects:
        raise RuntimeError("EDF subjects do not match participants.tsv")

    dup = cfg["duplicates"]
    print("Loading signals for pairwise comparison ...")
    hashes, constant, z = load_signals(paths, dup["channels"])
    pairs = classify_pairs(pairwise_similarity(subjects, dup["channels"], hashes, constant, z),
                           dup["near_duplicate_median_r"])
    del z
    flagged = pairs[pairs["identical"] | pairs["near_duplicate"]]
    groups = split_groups(subjects, list(zip(flagged["subject_a"], flagged["subject_b"])))

    events_table = pd.read_csv(roots.data_path(cfg["events_tsv"]), sep="\t")
    timing_results = [event_timing(p, events_table, cfg["events"]) for p in paths]
    timing = pd.DataFrame([row for row, _ in timing_results])
    trials = pd.concat([t for _, t in timing_results], ignore_index=True)

    lesion = lesion_table(meta, cfg["lesion"])
    motion = {f"sub-{n:02d}" for n in cfg["paper"]["motion_artifact_subjects"]}

    identical_members = sorted(set(flagged.loc[flagged["identical"], ["subject_a", "subject_b"]].to_numpy().ravel()))
    decision = dup["exclusion_decision"]
    out = meta.merge(lesion, on="subject_id")
    out["motion_artifact_paper"] = out["subject_id"].isin(motion)
    out["split_group"] = out["subject_id"].map(groups)
    group_size = out["split_group"].map(out["split_group"].value_counts())
    out["duplicate_status"] = np.where(out["subject_id"].isin(identical_members), "identical",
                                       np.where(group_size > 1, "near_duplicate", "unique"))
    if decision == "exclude_both_identical":
        out["exclude_v3"] = out["subject_id"].isin(identical_members)
    elif decision == "keep_both_grouped":
        out["exclude_v3"] = False
    else:
        out["exclude_v3"] = pd.NA
    out["exclude_reason"] = np.where(out["exclude_v3"].fillna(False).astype(bool), "identical_recording_label_unknowable", "")
    out = out.merge(timing[["subject_id", "sidecar_agrees", "n_usable_trials", "n_usable_left", "n_usable_right"]],
                    on="subject_id")

    forbidden = {c.casefold() for c in cfg["forbidden_participant_columns"]} | {"nihss_raw", "severity_class"}
    if forbidden & {c.casefold() for c in out.columns}:
        raise RuntimeError("Outcome column leaked into the meta table")

    paths_out = {k: roots.out_path(v) for k, v in cfg["outputs"].items()}
    paths_out["meta"].parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(paths_out["meta"], index=False)
    paths_out["pairs_csv"].parent.mkdir(parents=True, exist_ok=True)
    pairs.sort_values("median_r", ascending=False).to_csv(paths_out["pairs_csv"], index=False)
    timing.to_csv(paths_out["events_csv"], index=False)
    trials.to_csv(roots.out_path(cfg["events"]["marker_events_csv"]), index=False)

    raw0 = mne.io.read_raw_edf(paths[0], preload=False, verbose="ERROR")
    para_counts = meta["paralysis_side"].str.casefold().value_counts().to_dict()
    summary = {
        "n_subjects": len(subjects),
        "duplicates": {"n_pairs_compared": len(pairs),
                       "identical_pairs": flagged.loc[flagged["identical"], ["subject_a", "subject_b"]].values.tolist(),
                       "near_duplicate_pairs": flagged.loc[flagged["near_duplicate"], ["subject_a", "subject_b", "median_r", "min_r"]].values.tolist(),
                       "highest_unflagged_median_r": float(pairs.loc[~(pairs["identical"] | pairs["near_duplicate"]), "median_r"].max()),
                       "split_groups_with_more_than_one_member": sorted({g for g in groups.values() if list(groups.values()).count(g) > 1}),
                       "exclusion_decision": decision},
        "events": {"imagery_markers_not_40": timing.loc[timing["n_imagery_markers"] != 40, ["subject_id", "n_imagery_markers"]].values.tolist(),
                   "n_sidecar_agrees_50ms": int(timing["sidecar_agrees"].sum()),
                   "n_subjects_all_trials_within_preset_20ms": int((timing["n_trials_lag_gt_preset"] == 0).sum()),
                   "sidecar_disagrees": timing.loc[~timing["sidecar_agrees"], ["subject_id", "n_trials_lag_gt_tolerance", "lag_samples_min", "lag_samples_max", "n_unmatched_markers", "n_short_imagery"]].values.tolist(),
                   "usable_trials_not_40": timing.loc[timing["n_usable_trials"] != 40, ["subject_id", "n_usable_trials", "n_usable_left", "n_usable_right"]].values.tolist(),
                   "n_usable_trials_total": int(timing["n_usable_trials"].sum()),
                   "lag_samples_pooled_quantiles": trials["lag_samples"].quantile([0, .05, .5, .95, 1]).round(1).tolist(),
                   "left_right_order_verifiable": False},
        "rest_data": {"present": False, "status": "CLOSED",
                      "evidence": "40 trials x 8 s = 320 s equals every recording length (Step 0); first event at 1 ms."},
        "channel_labels": channel_label_check(raw0.ch_names, roots.data_path(cfg["channels_tsv"])),
        "paralysis": {"data_left": int(para_counts.get("left", 0)), "data_right": int(para_counts.get("right", 0)),
                      "paper_left": cfg["paper"]["paralysis_left"], "paper_right": cfg["paper"]["paralysis_right"],
                      "status": "paper-vs-data discrepancy; source TSV is authoritative"},
        "lesion": {"location_side_counts": lesion["location_side"].value_counts().to_dict(),
                   "final_side_counts": lesion["lesion_side_final"].value_counts().to_dict(),
                   "uncertain_subjects": lesion.loc[~lesion["lesion_side_agree"], "subject_id"].tolist(),
                   "site_class_counts": lesion["site_class"].value_counts().to_dict(),
                   "n_has_infratentorial": int(lesion["has_infratentorial"].sum())},
        "motion_artifact_flagged": sorted(motion),
    }
    write_with_config(paths_out["report_json"], {"summary": summary}, config_path,
                      sources=[Path(__file__), roots.data_path(cfg["participants_tsv"]), roots.data_path(cfg["events_tsv"])],
                      roots=roots)
    print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main()
