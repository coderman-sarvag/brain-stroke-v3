"""Step 2: preprocessing of the continuous Figshare recordings, then marker-based epoching.

Order (handoff Step 2): load -> 10-10 names/montage -> bad-channel detection (CPz excluded)
-> 1-40 Hz FIR -> average reference with CPz as the zero-valued reference -> spline interpolation
(not when both channels of a homologous pair are bad) -> average reference again -> ICA with each
EOG channel used separately (skipped and flagged when > 9 bad channels) -> epochs 0-4 s from marker onsets
-> epoch screen. No left/right equalization: every clean epoch is kept with its class (class-balanced averaging
happens in the feature steps).

Modes
  diagnostic  run everything except the final screen; per subject and channel, the fraction of epochs over
              150 uV peak-to-peak, and the epochs (total/left/right) surviving each candidate screen rule.
  final       apply configs/v3/preprocess.json epochs.final_screen_rule and save epochs (refuses while pending).

Resumable: each subject writes its own result JSON; a rerun skips subjects already done with the same config
hash and mode (use --force to recompute). Label-blind: reads only the exclusion flag and Step 1 marker events.

Run from the repo root:
  python src/preprocess_v3.py --mode diagnostic [--subjects sub-01 ...] [--data-root D --out-root O --prev-root P]
"""
import argparse
import json
from pathlib import Path
import sys
import time
import traceback

import mne
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths_v3 import add_root_args, roots_from_args  # noqa: E402
from provenance_v3 import load_config, sha256_file, write_with_config  # noqa: E402

CONFIG = "configs/v3/preprocess.json"
MODES = ("diagnostic", "final")


# ---------------------------------------------------------------- loading

def load_raw(subject, cfg, roots):
    ch = cfg["channels"]
    path = roots.data_path(cfg["inputs"]["edf_template"].format(subject=subject))
    raw = mne.io.read_raw_edf(path, preload=True, verbose="ERROR")
    raw.drop_channels([c for c in ch["drop"] if c in raw.ch_names])
    raw.pick(ch["eeg"] + ch["eog"])
    raw.set_channel_types({c: "eog" for c in ch["eog"]})
    return prepare_names(raw, cfg)


def prepare_names(raw, cfg):
    ch = cfg["channels"]
    raw.rename_channels({k: v for k, v in ch["rename_10_10"].items() if k in raw.ch_names})
    raw.set_montage(ch["montage"], on_missing="raise")
    return raw


# ---------------------------------------------------------------- bad channels

def detect_bad_channels(raw, cfg):
    """PREP bad-channel detection on EEG channels with the reference channel removed."""
    from pyprep import NoisyChannels
    bc, ref = cfg["bad_channels"], cfg["channels"]["reference_channel"]
    eeg = raw.copy().pick("eeg").drop_channels([ref])
    nc = NoisyChannels(eeg, do_detrend=True, random_state=bc["random_state"], ransac=bc["ransac"])
    nc.find_bad_by_nan_flat()
    nc.find_bad_by_deviation(deviation_threshold=bc["deviation_threshold"])
    nc.find_bad_by_hfnoise(HF_zscore_threshold=bc["hf_zscore_threshold"])
    nc.find_bad_by_correlation(correlation_secs=bc["correlation_secs"], correlation_threshold=bc["correlation_threshold"],
                               frac_bad=bc["correlation_frac_bad"])
    nc.find_bad_by_SNR()
    if bc["ransac"]:
        nc.find_bad_by_ransac(n_samples=bc["ransac_n_samples"], sample_prop=bc["ransac_sample_prop"],
                              corr_thresh=bc["ransac_corr_thresh"], frac_bad=bc["ransac_frac_bad"],
                              corr_window_secs=bc["ransac_corr_window_secs"])
    by_type = {k: sorted(v) for k, v in nc.get_bads(as_dict=True).items() if k != "bad_all" and v}
    return sorted(nc.get_bads()), by_type


def unavailable_pairs(bads, pairs):
    """Homologous pairs whose two channels are both bad; these are not interpolated."""
    return [p for p in pairs if p[0] in bads and p[1] in bads]


def ica_allowed(n_bad, cfg):
    """Bad-channel guard: no ICA (and the subject is flagged) above the configured number of bad channels."""
    return n_bad <= cfg["bad_channels"]["max_bad_channels_for_ica"]


# ---------------------------------------------------------------- reference + interpolation

def rereference_and_interpolate(raw, bads, pairs, cfg):
    """Average reference (CPz = zero reference included), interpolate, average reference again."""
    unavailable = unavailable_pairs(bads, pairs)
    keep_bad = sorted({c for p in unavailable for c in p})
    raw.info["bads"] = list(bads)
    raw.set_eeg_reference("average", projection=False, verbose="ERROR")
    good = [c for c in raw.copy().pick("eeg").ch_names if c not in bads]
    good_sd = raw.get_data(picks=good).std(axis=1)
    if np.any(good_sd == 0):
        raise RuntimeError(f"All-zero good channel before interpolation: {np.array(good)[good_sd == 0].tolist()}")
    to_interp = [c for c in bads if c not in keep_bad]
    if to_interp:
        ic = cfg["interpolation"]
        raw.interpolate_bads(reset_bads=True, mode=ic["mode"], origin=ic["origin"], method={"eeg": ic["method"]},
                             exclude=keep_bad, verbose="ERROR")
    raw.info["bads"] = keep_bad
    raw.set_eeg_reference("average", projection=False, verbose="ERROR")
    return raw, to_interp, unavailable, float(good_sd.min())


# ---------------------------------------------------------------- ICA

def run_ica(raw, n_bad, cfg):
    ic = cfg["ica"]
    n_comp = int(min(ic["n_components"], 29 - n_bad))
    ica = mne.preprocessing.ICA(n_components=n_comp, method=ic["method"], fit_params=ic["fit_params"],
                                random_state=ic["random_state"], max_iter=ic["max_iter"])
    ica.fit(raw, picks="eeg", decim=ic["decim"], reject={"eeg": ic["fit_reject_eeg_volts"]},
            tstep=ic["fit_reject_tstep_s"], verbose="ERROR")
    ed = ic["eog_detection"]
    flagged = {}
    for ch in ed["per_channel"]:
        idx, _ = ica.find_bads_eog(raw, ch_name=ch, threshold=ed["threshold"], measure=ed["measure"],
                                   l_freq=ed["l_freq"], h_freq=ed["h_freq"], verbose="ERROR")
        flagged[ch] = sorted(int(i) for i in idx)
    exclude = sorted({i for v in flagged.values() for i in v})
    cleaned = ica.apply(raw.copy(), exclude=exclude, verbose="ERROR")
    return cleaned, ica, n_comp, flagged, exclude


# ---------------------------------------------------------------- epochs

def subject_events(marker_events, subject, event_id):
    """MNE events from usable marker-matched trials; left/right from the matched sidecar trial."""
    t = marker_events[(marker_events["subject_id"] == subject) & marker_events["usable"]].sort_values("marker_onset")
    codes = t["trial_type"].astype(float).astype(int).map({1: event_id["left_hand"], 2: event_id["right_hand"]})
    if codes.isna().any():
        raise ValueError(f"{subject}: usable trial without left/right type")
    events = np.column_stack([t["marker_onset"].to_numpy(int), np.zeros(len(t), int), codes.to_numpy(int)])
    names = {v: k for k, v in event_id.items()}
    meta = t[["marker_index", "sidecar_trial", "marker_onset", "lag_samples"]].reset_index(drop=True)
    meta["hand"] = [names[c] for c in events[:, 2]]
    return events, meta


def make_epochs(raw, events, meta, cfg):
    """Unscreened 0-4 s epochs (EEG + EOG) at the given events."""
    ep = cfg["epochs"]
    epochs = mne.Epochs(raw, events, event_id=ep["event_id"], tmin=ep["tmin"],
                        tmax=(ep["tmax_samples"] - 1) / raw.info["sfreq"], baseline=ep["baseline"],
                        picks=["eeg", "eog"], metadata=meta, preload=True, reject_by_annotation=False, verbose="ERROR")
    if len(epochs) != len(events):
        raise RuntimeError("Epochs dropped at creation (event outside recording?)")
    return epochs


def class_counts(epochs, event_id):
    codes = epochs.events[:, 2]
    return {"total": int(len(codes)), "left": int((codes == event_id["left_hand"]).sum()),
            "right": int((codes == event_id["right_hand"]).sum())}


# ---------------------------------------------------------------- screening

def peak_to_peak(epochs, picks):
    data = epochs.get_data(picks=picks)
    return data.max(axis=-1) - data.min(axis=-1)  # (epoch, channel)


def available(epochs, channels):
    return [c for c in channels if c in epochs.ch_names and c not in epochs.info["bads"]]


def screen_channels(epochs, rule, cfg):
    if rule == "all_scalp":
        return available(epochs, epochs.copy().pick("eeg").ch_names)
    if rule in ("analysed", "analysed_after_marking"):
        return available(epochs, cfg["channels"]["analysed_channels"])
    raise ValueError(f"Unknown screen rule {rule!r}")


def channel_exceedance(epochs, channels, threshold):
    """Fraction of epochs in which each channel alone exceeds the peak-to-peak threshold."""
    if not len(epochs):
        return {c: float("nan") for c in channels}
    over = peak_to_peak(epochs, channels) > threshold
    return dict(zip(channels, over.mean(axis=0).astype(float)))


def mark_and_interpolate(epochs, cfg):
    """Rule (iii) pre-step: mark analysed channels exceeding the threshold in >= marking_fraction of epochs,
    interpolate them unless the homologous partner is also bad, then re-apply the average reference."""
    ep, pairs = cfg["epochs"], cfg["channels"]["homologous_pairs"]
    cands = available(epochs, cfg["channels"]["analysed_channels"])
    exceed = channel_exceedance(epochs, cands, ep["peak_to_peak_volts"])
    marked = sorted(c for c, f in exceed.items() if f >= ep["marking_fraction"])
    out = epochs.copy()
    if not marked:
        return out, [], [], []
    bads = sorted(set(out.info["bads"]) | set(marked))
    unavailable = unavailable_pairs(bads, pairs)
    keep_bad = sorted({c for p in unavailable for c in p})
    out.info["bads"] = bads
    to_interp = [c for c in marked if c not in keep_bad]
    if to_interp:
        ic = cfg["interpolation"]
        out.interpolate_bads(reset_bads=True, mode=ic["mode"], origin=ic["origin"], method={"eeg": ic["method"]},
                             exclude=keep_bad, verbose="ERROR")
    out.info["bads"] = keep_bad
    out.set_eeg_reference("average", projection=False, verbose="ERROR")
    new_unavailable = [p for p in unavailable if not set(p) <= set(epochs.info["bads"])]
    return out, marked, to_interp, new_unavailable


def apply_screen(epochs, rule, cfg):
    """Return (screened epochs, details) for one screen rule; epochs are not modified."""
    details = {"rule": rule, "marked": [], "interpolated_on_epochs": [], "new_unavailable_pairs": []}
    work = epochs
    if rule == "analysed_after_marking":
        work, marked, interp, new_unav = mark_and_interpolate(epochs, cfg)
        details.update(marked=marked, interpolated_on_epochs=interp, new_unavailable_pairs=new_unav)
    channels = screen_channels(work, rule, cfg)
    keep = (peak_to_peak(work, channels) <= cfg["epochs"]["peak_to_peak_volts"]).all(axis=1)
    details["screened_channels"] = channels
    screened = work.copy().drop(np.flatnonzero(~keep), reason="P2P", verbose="ERROR")
    return screened, details


# ---------------------------------------------------------------- HEOG check

def band_power(epochs, chs, band, psd_cfg):
    data = epochs.get_data(picks=chs)
    psd, _ = mne.time_frequency.psd_array_welch(data, epochs.info["sfreq"], fmin=band[0], fmax=band[1],
                                                n_fft=psd_cfg["n_fft"], n_per_seg=psd_cfg["n_per_seg"], verbose="ERROR")
    return psd.mean(axis=-1)  # (epoch, channel)


def heog_asymmetry(epochs, cfg):
    hc = cfg["heog_check"]
    rows = {}
    if len(epochs) < hc["min_epochs"]:
        return rows
    for band_name, band in hc["bands"].items():
        eog = np.log(band_power(epochs, hc["eog"], band, hc["psd"]))
        for left, right in hc["channels_asymmetry"]:
            if left in epochs.info["bads"] or right in epochs.info["bads"]:
                continue
            p = band_power(epochs, [left, right], band, hc["psd"])
            ai = (p[:, 0] - p[:, 1]) / (p[:, 0] + p[:, 1])
            for j, e in enumerate(hc["eog"]):
                rows[f"rho_{left}{right}_{e}_{band_name}"] = float(spearmanr(ai, eog[:, j]).statistic)
    return rows


def summarize_heog(heog, threshold):
    out = {}
    for col in [c for c in heog.columns if c.startswith("before_")]:
        key = col[len("before_"):]
        before, after = heog[col].abs(), heog[f"after_{key}"].abs()
        out[key] = {"n": int(before.notna().sum()), "median_abs_rho_before": float(before.median()),
                    "median_abs_rho_after": float(after.median()),
                    "n_dominated_before": int((before > threshold).sum()), "n_dominated_after": int((after > threshold).sum())}
    return out


# ---------------------------------------------------------------- mains residue

def mains_fraction(raw, mains, picks="eeg"):
    psd, freqs = raw.compute_psd(fmin=1, fmax=100, picks=picks, n_fft=2048, verbose="ERROR").get_data(return_freqs=True)
    band = (freqs >= mains - 2) & (freqs <= mains + 2)
    total = psd.sum(1)
    return float(np.median(psd[total > 0][:, band].sum(1) / total[total > 0]))  # flat reference channel skipped


# ---------------------------------------------------------------- per subject

def continuous_stage(subject, cfg, roots):
    """Load -> detect bads -> filter -> reference/interpolate -> ICA (guarded). Shared by both modes."""
    raw = load_raw(subject, cfg, roots)
    ref = cfg["channels"]["reference_channel"]
    cpz_before = float(np.ptp(raw.get_data(picks=[ref])))
    mains_before = mains_fraction(raw, cfg["filter"]["mains_hz"])
    bads, bads_by_type = detect_bad_channels(raw, cfg)

    f = cfg["filter"]
    raw.filter(f["l_freq"], f["h_freq"], method=f["method"], fir_design=f["fir_design"], phase=f["phase"],
               picks=["eeg", "eog"], verbose="ERROR")
    mains_after = mains_fraction(raw, f["mains_hz"])
    raw, interpolated, unavailable, min_good_sd = rereference_and_interpolate(raw, bads, cfg["channels"]["homologous_pairs"], cfg)

    pre_ica = raw.copy()
    log = {"subject_id": subject, "bad_channels": ";".join(bads), "bad_by_type": json.dumps(bads_by_type),
           "n_bad": len(bads), "bad_fraction_flag": len(bads) / 29 > cfg["bad_channels"]["flag_subject_if_bad_fraction_above"],
           "interpolated": ";".join(interpolated), "unavailable_pairs": ";".join("-".join(p) for p in unavailable),
           "cpz_ptp_before_volts": cpz_before, "cpz_sd_after_volts": float(raw.get_data(picks=[ref]).std()),
           "min_good_sd_before_interp_volts": min_good_sd, "mains_frac_before": mains_before, "mains_frac_after": mains_after}
    if ica_allowed(len(bads), cfg):
        cleaned, ica, n_comp, flagged, excluded = run_ica(raw, len(bads), cfg)
        log.update(ica_status="ok", ica_n_components=n_comp)
    else:
        cleaned, ica, flagged, excluded = raw, None, {}, []
        log.update(ica_status="skipped_too_many_bad_channels", ica_n_components=0)
    log.update({f"ica_flagged_{ch}": ";".join(map(str, flagged.get(ch, []))) for ch in cfg["ica"]["eog_detection"]["per_channel"]})
    log.update(ica_removed=";".join(map(str, excluded)), n_ica_removed=len(excluded))
    return pre_ica, cleaned, ica, log


def diagnostic_subject(subject, cfg, roots, marker_events):
    pre_ica, cleaned, _, log = continuous_stage(subject, cfg, roots)
    ids = cfg["epochs"]["event_id"]
    events, meta = subject_events(marker_events, subject, ids)
    epochs = make_epochs(cleaned, events, meta, cfg)
    scalp = epochs.copy().pick("eeg").ch_names
    exceed = channel_exceedance(epochs, scalp, cfg["epochs"]["peak_to_peak_volts"])
    channels = [{"subject_id": subject, "channel": c, "available": c not in epochs.info["bads"],
                 "analysed": c in cfg["channels"]["analysed_channels"],
                 "frac_epochs_over_threshold": float("nan") if c in epochs.info["bads"] else exceed[c]} for c in scalp]
    rules = {}
    for rule in cfg["epochs"]["screen_rules"]:
        screened, details = apply_screen(epochs, rule, cfg)
        counts = class_counts(screened, ids)
        rules[rule] = {**{f"n_{k}": v for k, v in counts.items()}, "n_min_class": min(counts["left"], counts["right"]),
                       "marked": details["marked"], "interpolated_on_epochs": details["interpolated_on_epochs"],
                       "new_unavailable_pairs": details["new_unavailable_pairs"]}
    log.update(n_usable_trials=len(events), **{f"usable_{k}": v for k, v in class_counts(epochs, ids).items()})
    heog = {"subject_id": subject,
            **{f"before_{k}": v for k, v in heog_asymmetry(make_epochs(pre_ica, events, meta, cfg), cfg).items()},
            **{f"after_{k}": v for k, v in heog_asymmetry(epochs, cfg).items()}}
    return {"log": log, "rules": rules, "channels": channels, "heog": heog}


def final_subject(subject, cfg, roots, marker_events):
    rule = cfg["epochs"]["final_screen_rule"]
    pre_ica, cleaned, ica, log = continuous_stage(subject, cfg, roots)
    ids = cfg["epochs"]["event_id"]
    if log["ica_status"] != "ok":
        log.update(screen_rule=rule, n_epochs_kept=0, n_left_kept=0, n_right_kept=0, excluded_reason="too_many_bad_channels")
        return {"log": log, "heog": {"subject_id": subject}}
    events, meta = subject_events(marker_events, subject, ids)
    epochs = make_epochs(cleaned, events, meta, cfg)
    screened, details = apply_screen(epochs, rule, cfg)
    counts = class_counts(screened, ids)
    out_dir = roots.out_path(cfg["outputs"]["epochs_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    screened.save(out_dir / f"{subject}-epo.fif", overwrite=True, verbose="ERROR")
    ica.save(out_dir / f"{subject}-ica.fif", overwrite=True, verbose="ERROR")
    kept = screened.selection
    pre = make_epochs(pre_ica, events[kept], meta.iloc[kept].reset_index(drop=True), cfg)
    log.update(screen_rule=rule, screen_marked=";".join(details["marked"]),
               screen_interpolated=";".join(details["interpolated_on_epochs"]),
               screen_new_unavailable_pairs=";".join("-".join(p) for p in details["new_unavailable_pairs"]),
               n_usable_trials=len(events), n_epochs_kept=counts["total"], n_left_kept=counts["left"],
               n_right_kept=counts["right"], excluded_reason="")
    heog = {"subject_id": subject, **{f"before_{k}": v for k, v in heog_asymmetry(pre, cfg).items()},
            **{f"after_{k}": v for k, v in heog_asymmetry(screened, cfg).items()}}
    return {"log": log, "heog": heog}


def run_subject(subject, mode, cfg, config_sha, roots, marker_events, result_path):
    """Run one subject and write its result JSON (status ok or error) immediately."""
    start = time.time()
    try:
        body = (diagnostic_subject if mode == "diagnostic" else final_subject)(subject, cfg, roots, marker_events)
        result = {"status": "ok", **body}
    except Exception as exc:  # recorded per subject so one failure does not lose the cohort run
        result = {"status": "error", "error": repr(exc), "traceback": traceback.format_exc()}
    result.update(subject_id=subject, mode=mode, config_sha256=config_sha, seconds=round(time.time() - start, 1))
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")
    return result


def is_done(path, mode, config_sha):
    if not path.exists():
        return False
    r = json.loads(path.read_text(encoding="utf-8"))
    return r.get("status") == "ok" and r.get("mode") == mode and r.get("config_sha256") == config_sha


# ---------------------------------------------------------------- aggregation

def distribution(series):
    s = pd.Series(series).astype(float)
    return {"min": float(s.min()), "q1": float(s.quantile(.25)), "median": float(s.median()),
            "q3": float(s.quantile(.75)), "max": float(s.max()), "sorted": sorted(s.astype(int).tolist())}


def aggregate_diagnostic(results, cfg, config_path, roots, failed):
    rows, channels, heog = [], [], []
    for r in results:
        row = dict(r["log"])
        for rule, v in r["rules"].items():
            row.update({f"{rule}__{k}": (";".join("-".join(p) if isinstance(p, list) else p for p in x) if isinstance(x, list) else x)
                        for k, x in v.items()})
        rows.append(row)
        channels.extend(r["channels"])
        heog.append(r["heog"])
    subj, chan, heog = pd.DataFrame(rows), pd.DataFrame(channels), pd.DataFrame(heog)
    outs = {k: roots.out_path(v) for k, v in cfg["outputs"].items()}
    outs["diagnostic_subjects_csv"].parent.mkdir(parents=True, exist_ok=True)
    subj.to_csv(outs["diagnostic_subjects_csv"], index=False)
    chan.to_csv(outs["diagnostic_channels_csv"], index=False)
    heog.to_csv(outs["diagnostic_heog_csv"], index=False)
    marking = cfg["epochs"]["marking_fraction"]
    avail = chan[chan["available"]]
    per_channel = avail.groupby("channel")["frac_epochs_over_threshold"].agg(["median", "mean"]).join(
        avail.assign(m=avail["frac_epochs_over_threshold"] >= marking).groupby("channel")["m"].sum().rename("n_subjects_ge_marking"))
    summary = {"mode": "diagnostic", "n_subjects_ok": len(subj), "failed_subjects": failed,
               "no_labels_read": True,
               "cpz_constant_before_all": bool((subj["cpz_ptp_before_volts"] == 0).all()),
               "cpz_nonzero_after_all": bool((subj["cpz_sd_after_volts"] > 0).all()),
               "no_zero_channel_used_for_interpolation": bool((subj["min_good_sd_before_interp_volts"] > 0).all()),
               "bad_channels": {"n_subjects_with_bads": int((subj["n_bad"] > 0).sum()), "n_bad": distribution(subj["n_bad"]),
                                "subjects_bad_fraction_flag": subj.loc[subj["bad_fraction_flag"], "subject_id"].tolist(),
                                "subjects_ica_skipped_guard": subj.loc[subj["ica_status"] != "ok", "subject_id"].tolist(),
                                "subjects_with_unavailable_pairs": subj.loc[subj["unavailable_pairs"].fillna("") != "", ["subject_id", "unavailable_pairs"]].values.tolist()},
               "ica": {"removed_total": int(subj["n_ica_removed"].sum()),
                       "subjects_with_none_removed": subj.loc[subj["n_ica_removed"] == 0, "subject_id"].tolist()},
               "mains_frac_median": {"before": float(subj["mains_frac_before"].median()), "after": float(subj["mains_frac_after"].median())},
               "per_rule": {}, "channels_ranked_by_median_exceedance": per_channel.sort_values("median", ascending=False).round(3).reset_index().to_dict("records"),
               "heog": summarize_heog(heog, cfg["heog_check"]["dominated_abs_rho"]) if len(heog.columns) > 1 else {},
               "seconds_per_subject": distribution(pd.Series([r["seconds"] for r in results]))}
    for rule in cfg["epochs"]["screen_rules"]:
        summary["per_rule"][rule] = {"n_total": distribution(subj[f"{rule}__n_total"]),
                                     "n_min_class": distribution(subj[f"{rule}__n_min_class"]),
                                     "n_subjects_min_class_lt_10": int((subj[f"{rule}__n_min_class"] < 10).sum()),
                                     "n_subjects_min_class_lt_5": int((subj[f"{rule}__n_min_class"] < 5).sum()),
                                     "n_subjects_min_class_0": int((subj[f"{rule}__n_min_class"] == 0).sum())}
    summary["per_rule"]["analysed_after_marking"]["n_channels_marked"] = int(
        subj["analysed_after_marking__marked"].fillna("").map(lambda s: len([x for x in str(s).split(";") if x])).sum())
    write_with_config(outs["diagnostic_summary_json"], {"summary": summary}, config_path, sources=[Path(__file__)], roots=roots)
    return summary


def aggregate_final(results, cfg, config_path, roots, failed):
    log = pd.DataFrame([r["log"] for r in results])
    heog = pd.DataFrame([r["heog"] for r in results])
    outs = {k: roots.out_path(v) for k, v in cfg["outputs"].items()}
    outs["log_csv"].parent.mkdir(parents=True, exist_ok=True)
    log.to_csv(outs["log_csv"], index=False)
    heog.to_csv(outs["heog_csv"], index=False)
    qc_cols = ["subject_id", "n_bad", "bad_channels", "interpolated", "unavailable_pairs", "ica_status", "screen_rule",
               "screen_marked", "screen_new_unavailable_pairs", "n_epochs_kept", "n_left_kept", "n_right_kept", "excluded_reason"]
    outs["epoch_qc"].parent.mkdir(parents=True, exist_ok=True)
    log.reindex(columns=qc_cols).to_csv(outs["epoch_qc"], index=False)
    summary = {"mode": "final", "screen_rule": cfg["epochs"]["final_screen_rule"], "n_subjects_ok": len(log),
               "failed_subjects": failed, "epochs_kept": distribution(log["n_epochs_kept"]),
               "min_class": distribution(log[["n_left_kept", "n_right_kept"]].min(axis=1)),
               "heog": summarize_heog(heog, cfg["heog_check"]["dominated_abs_rho"]) if len(heog.columns) > 1 else {}}
    write_with_config(outs["summary_json"], {"summary": summary}, config_path, sources=[Path(__file__)], roots=roots)
    return summary


# ---------------------------------------------------------------- main

def main(argv=None):
    parser = add_root_args(argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter))
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--subjects", nargs="*")
    parser.add_argument("--n-jobs", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="recompute subjects that already have results")
    args = parser.parse_args(argv)
    roots = roots_from_args(args)
    cfg, config_path = load_config(CONFIG)
    config_sha = sha256_file(config_path)
    if args.mode == "final" and cfg["epochs"]["final_screen_rule"] not in cfg["epochs"]["screen_rules"]:
        raise SystemExit(f"final_screen_rule is {cfg['epochs']['final_screen_rule']!r}: choose a rule from the diagnostic run first")

    meta = pd.read_csv(roots.prev_path(cfg["inputs"]["subject_meta"]), usecols=["subject_id", "exclude_v3"])
    subjects = args.subjects or meta.loc[~meta["exclude_v3"].astype(bool), "subject_id"].tolist()
    marker_events = pd.read_csv(roots.prev_path(cfg["inputs"]["marker_events"]))
    subject_dir = roots.out_path(cfg["outputs"][f"subject_dir_{args.mode}"])
    paths = {s: subject_dir / f"{s}.json" for s in subjects}
    todo = [s for s in subjects if args.force or not is_done(paths[s], args.mode, config_sha)]
    print(f"{args.mode}: {len(subjects)} subjects, {len(subjects) - len(todo)} already done, {len(todo)} to run", flush=True)
    Parallel(n_jobs=args.n_jobs or cfg["n_jobs"], verbose=5)(
        delayed(run_subject)(s, args.mode, cfg, config_sha, roots, marker_events, paths[s]) for s in todo)

    results = [json.loads(paths[s].read_text(encoding="utf-8")) for s in subjects]
    failed = [{"subject_id": r["subject_id"], "error": r["error"]} for r in results if r["status"] != "ok"]
    ok = [r for r in results if r["status"] == "ok"]
    if not ok:
        raise SystemExit(f"No subject succeeded: {failed}")
    aggregate = aggregate_diagnostic if args.mode == "diagnostic" else aggregate_final
    summary = aggregate(ok, cfg, config_path, roots, failed)
    print(json.dumps({k: v for k, v in summary.items() if k != "channels_ranked_by_median_exceedance"}, indent=1, default=str))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
