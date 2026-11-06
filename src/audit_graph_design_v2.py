"""Run the label-blind A3 channel and epoch audit for graph v2."""

from __future__ import annotations

import json
from pathlib import Path

import mne
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
CLEAN_ROOT = REPO_ROOT / "data" / "processed" / "figshare" / "clean"
CONFIG_ROOT = REPO_ROOT / "configs"
DOC_PATH = REPO_ROOT / "docs" / "GRAPH_DESIGN_LOCK.md"
AUDIT_JSON = REPO_ROOT / "docs" / "graph_design_audit_v2.json"
THRESHOLD_UV = 150.0
THRESHOLD_V = THRESHOLD_UV * 1e-6
SUBSAMPLES = 100
CORE_NODES = ["F3", "C3", "P3", "O1", "F4", "C4", "P4", "O2"]
PAIRS = [
    ("FP1", "FP2"),
    ("F3", "F4"),
    ("F7", "F8"),
    ("FC3", "FC4"),
    ("FT7", "FT8"),
    ("C3", "C4"),
    ("T3", "T4"),
    ("CP3", "CP4"),
    ("TP7", "TP8"),
    ("P3", "P4"),
    ("T5", "T6"),
    ("O1", "O2"),
]
EXPANDED_NODES = [channel for pair in PAIRS for channel in pair]
MIDLINE_NODES = ["Fz", "FCz", "Cz", "CPz", "Pz", "Oz"]


def choose_n_fixed(counts: list[int]) -> tuple[int, list[str]]:
    """Apply the guide rule: minimum if >=15, else third-smallest count."""
    minimum = min(counts)
    if minimum >= 15:
        return minimum, []
    ordered = sorted(counts)
    selected = ordered[2] if len(ordered) > 2 else minimum
    return selected, [str(count) for count in counts if count < selected]


def main() -> None:
    paths = sorted(CLEAN_ROOT.glob("sub-*-clean-epo.fif"))
    if len(paths) != 50:
        raise ValueError(f"Expected 50 clean epoch files, found {len(paths)}")

    first_channels: list[str] = []
    sfreqs: set[float] = set()
    epoch_windows: set[tuple[float, float, int]] = set()
    epoch_counts: dict[str, int] = {}
    core_counts: dict[str, int] = {}
    expanded_counts: dict[str, int] = {}
    channel_rejected: dict[str, int] = {}
    channel_total: dict[str, int] = {}
    channel_variance: dict[str, list[float]] = {}
    expanded_loss: dict[str, int] = {}
    all_epoch_total = 0

    for path in paths:
        epochs = mne.read_epochs(path, preload=True, verbose=False)
        if not first_channels:
            first_channels = list(epochs.ch_names)
        sfreqs.add(float(epochs.info["sfreq"]))
        epoch_windows.add((float(epochs.times[0]), float(epochs.times[-1]), len(epochs.times)))
        data = epochs.get_data()
        epoch_counts[path.stem.replace("-clean-epo", "")] = len(epochs)
        all_epoch_total += len(epochs)

        missing = [channel for channel in EXPANDED_NODES if channel not in epochs.ch_names]
        if missing:
            raise ValueError(f"{path.name} missing expanded channels: {missing}")
        indices = {channel: epochs.ch_names.index(channel) for channel in EXPANDED_NODES}
        expanded_data = data[:, [indices[channel] for channel in EXPANDED_NODES], :]
        peak_to_peak = np.ptp(expanded_data, axis=2)
        rejected = peak_to_peak > THRESHOLD_V
        for index, channel in enumerate(EXPANDED_NODES):
            channel_rejected[channel] = channel_rejected.get(channel, 0) + int(rejected[:, index].sum())
            channel_total[channel] = channel_total.get(channel, 0) + len(epochs)
            channel_variance.setdefault(channel, []).extend(
                np.var(expanded_data[:, index, :], axis=1).tolist()
            )
        expanded_loss[path.stem.replace("-clean-epo", "")] = int(rejected.any(axis=1).sum())

        core_indices = [epochs.ch_names.index(channel) for channel in CORE_NODES]
        core_rejected = np.ptp(data[:, core_indices, :], axis=2) > THRESHOLD_V
        core_counts[path.stem.replace("-clean-epo", "")] = int((~core_rejected.any(axis=1)).sum())

    rejection_rate = {
        channel: channel_rejected[channel] / channel_total[channel]
        for channel in EXPANDED_NODES
    }
    kept_pairs = [
        pair for pair in PAIRS
        if max(rejection_rate[pair[0]], rejection_rate[pair[1]]) <= 0.25
    ]
    expanded_kept_nodes = [channel for pair in kept_pairs for channel in pair]
    expanded_kept_counts: dict[str, int] = {}
    for path in paths:
        epochs = mne.read_epochs(path, preload=True, verbose=False)
        data = epochs.get_data()
        indices = [epochs.ch_names.index(channel) for channel in expanded_kept_nodes]
        rejected = np.ptp(data[:, indices, :], axis=2) > THRESHOLD_V
        subject = path.stem.replace("-clean-epo", "")
        expanded_kept_counts[subject] = int((~rejected.any(axis=1)).sum())

    core_n_fixed, core_below = choose_n_fixed(list(core_counts.values()))
    expanded_n_fixed, expanded_below = choose_n_fixed(list(expanded_kept_counts.values()))
    selected_n_fixed = core_n_fixed

    config_common = {
        "bands": {"delta": [1.0, 4.0], "theta": [4.0, 8.0], "alpha": [8.0, 13.0], "beta": [13.0, 30.0]},
        "artifact_threshold_uv": THRESHOLD_UV,
        "n_fixed": selected_n_fixed,
        "subsamples": SUBSAMPLES,
        "seed_rule": "42 + zero-based subject index",
        "sampling_without_replacement": True,
        "sfreq_hz": sorted(sfreqs),
    }
    core_pairs = [("F3", "F4"), ("C3", "C4"), ("P3", "P4"), ("O1", "O2")]
    g8_config = {
        **config_common,
        "name": "g8f",
        "left_nodes": [pair[0] for pair in core_pairs],
        "right_nodes": [pair[1] for pair in core_pairs],
        "channels": [*CORE_NODES[:4], *CORE_NODES[4:]],
        "pairs": core_pairs,
        "pair_map": [0, 1, 2, 3],
    }
    g24_config = {
        **config_common,
        "name": "g24f",
        "left_nodes": [pair[0] for pair in kept_pairs],
        "right_nodes": [pair[1] for pair in kept_pairs],
        "channels": [*[pair[0] for pair in kept_pairs], *[pair[1] for pair in kept_pairs]],
        "pairs": kept_pairs,
        "pair_map": list(range(len(kept_pairs))),
        "n_fixed": expanded_n_fixed,
        "n_fixed_basis": "largest value with at most two subjects below it",
    }
    CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
    (CONFIG_ROOT / "graph_g8f.json").write_text(json.dumps(g8_config, indent=2) + "\n", encoding="utf-8")
    (CONFIG_ROOT / "graph_g24f.json").write_text(json.dumps(g24_config, indent=2) + "\n", encoding="utf-8")

    audit = {
        "clean_epoch_files": len(paths),
        "channels": first_channels,
        "midline_channels": MIDLINE_NODES,
        "sfreq_hz": sorted(sfreqs),
        "epoch_windows": [list(window) for window in sorted(epoch_windows)],
        "clean_epoch_count_min": min(epoch_counts.values()),
        "clean_epoch_count_median": float(np.median(list(epoch_counts.values()))),
        "clean_epoch_count_max": max(epoch_counts.values()),
        "total_clean_epochs": all_epoch_total,
        "channel_rejection_rate_at_150uv": rejection_rate,
        "expanded_epoch_losses_before_pair_filter": expanded_loss,
        "kept_pairs": kept_pairs,
        "dropped_pairs": [pair for pair in PAIRS if pair not in kept_pairs],
        "core_counts_after_150uv_screen": core_counts,
        "expanded_counts_after_pair_filter": expanded_kept_counts,
        "core_n_fixed": core_n_fixed,
        "expanded_n_fixed_audit_value": expanded_n_fixed,
        "selected_n_fixed": selected_n_fixed,
        "core_subjects_below_selected_n": [subject for subject, count in core_counts.items() if count < selected_n_fixed],
        "expanded_subjects_below_selected_n": [subject for subject, count in expanded_kept_counts.items() if count < selected_n_fixed],
        "top_channel_variance": {
            channel: float(np.median(values))
            for channel, values in sorted(
                channel_variance.items(), key=lambda item: float(np.median(item[1])), reverse=True
            )[:10]
        },
        "design_basis": "label-blind epoch and channel quality only",
    }
    AUDIT_JSON.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")

    DOC_PATH.write_text(
        "\n".join(
            [
                "# Graph v2 Design Lock",
                "",
                "**Status:** PROVISIONAL LOCK after A3 label-blind audit",
                "",
                "## Input audit",
                "",
                f"- Files audited: {len(paths)} clean FIF files from `data/processed/figshare/clean/`.",
                f"- Sampling rate: {sorted(sfreqs)} Hz.",
                f"- Epoch window: {sorted(epoch_windows)} (time start, time end, samples).",
                f"- Clean epoch counts: min={min(epoch_counts.values())}, median={np.median(list(epoch_counts.values()))}, max={max(epoch_counts.values())}.",
                f"- Artifact screen: peak-to-peak threshold {THRESHOLD_UV} uV.",
                "- The same artifact screen is applied to the graph sampling pool by `screen_epochs` before feature computation.",
                "- Design decisions used only channel quality and epoch counts; no clinical labels were read.",
                "",
                "## Channel sets",
                "",
                f"- G8f: {', '.join(CORE_NODES)}.",
                f"- G24f retained pairs: {', '.join(f'{left}/{right}' for left, right in kept_pairs)}.",
                f"- Dropped pairs: {', '.join(f'{left}/{right}' for left, right in PAIRS if (left, right) not in kept_pairs) or 'none'}.",
                "- The full channel rejection rates and counts are recorded in `docs/graph_design_audit_v2.json`.",
                "",
                "## Fixed epoch rule",
                "",
                f"- G8f audit value: N_fixed={core_n_fixed}.",
                f"- G24f feasible value: N_fixed={expanded_n_fixed}; the expanded set is secondary because the larger channel screen leaves fewer usable epochs.",
                f"- G8f primary value: N_fixed={selected_n_fixed}.",
                f"- Subjects below selected N in G8f: {audit['core_subjects_below_selected_n'] or 'none'}.",
                f"- Subjects below G24f N_fixed in the expanded set: {[subject for subject, count in expanded_kept_counts.items() if count < expanded_n_fixed] or 'none'}.",
                "- Each subsample is drawn without replacement; 100 subsamples are planned; per-subject seed is 42 plus the zero-based subject index.",
                "",
                "## Locked graph contract",
                "",
                "- Bands: delta 1-4 Hz, theta 4-8 Hz, alpha 8-13 Hz, beta 13-30 Hz.",
                "- Graph metrics: absolute efficiency asymmetry, absolute clustering asymmetry, mean homotopic wPLI, and aligned normalized Frobenius distance.",
                "- Pair orientation and channel order are load-bearing and must not change without reopening this lock and documenting the reason.",
                "",
                "## Reproducibility",
                "",
                "- Configs: `configs/graph_g8f.json` and `configs/graph_g24f.json`.",
                "- Full audit: `docs/graph_design_audit_v2.json`.",
                "- This is a technical design lock, not evidence of label-related improvement.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Audited {len(paths)} clean FIF files")
    print(f"G8f N_fixed={core_n_fixed}; G24f audit N_fixed={expanded_n_fixed}; selected={selected_n_fixed}")
    print(f"Retained expanded pairs: {kept_pairs}")


if __name__ == "__main__":
    main()
