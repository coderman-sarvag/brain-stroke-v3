"""Synthetic tests for Step 1 integrity rules (no real labels, no EEG files)."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from integrity_v3 import (classify_pairs, imagery_trials, lesion_table, location_side, marker_events,  # noqa: E402
                          match_to_sidecar, pairwise_similarity, site_class, split_groups)

LESION = json.loads((ROOT / "configs/v3/integrity.json").read_text(encoding="utf-8"))["lesion"]
SIDES = LESION["side_words"]


def test_location_side_rules():
    assert location_side("Left pons", SIDES) == "left"
    assert location_side("Right temporo-parietal occipital lobe and insula, Right basal ganglia", SIDES) == "right"
    assert location_side("Pons", SIDES) == "unclear"
    assert location_side("Left paraventricular, Right temporal lobe", SIDES) == "mixed"
    assert location_side("Right cerebellum,bilateral occipital lobes", SIDES) == "bilateral"


def test_site_class_rules():
    assert site_class("Left pons", LESION) == ("infratentorial", True)
    assert site_class("Right basal ganglia", LESION) == ("subcortical_supratentorial", False)
    assert site_class("Right subfrontal cortex, Right basal ganglia", LESION) == ("cortical_involving", False)
    assert site_class("Left cerebellum, Right corona radiata", LESION) == ("subcortical_supratentorial", True)


def test_final_side_only_when_location_agrees():
    meta = pd.DataFrame({"subject_id": ["a", "b", "c"], "paralysis_side": ["right", "left", "right"],
                         "stroke_location": ["Left pons", "Left pons", "Pons"]})
    out = lesion_table(meta, LESION).set_index("subject_id")["lesion_side_final"]
    assert out.to_dict() == {"a": "left", "b": "uncertain", "c": "uncertain"}


def test_pairwise_detects_identical_and_near_duplicates():
    rng = np.random.default_rng(0)
    base = rng.standard_normal((3, 2000))
    data = {"s1": base, "s2": base.copy(), "s3": base + 0.001 * rng.standard_normal(base.shape),
            "s4": rng.standard_normal((3, 2000))}
    subjects = list(data)
    hashes = {s: [hashlib.sha256(x.tobytes()).hexdigest() for x in v] for s, v in data.items()}
    constant = {s: [False] * 3 for s in subjects}
    z = np.stack([(v - v.mean(1, keepdims=True)) / v.std(1, keepdims=True) for v in data.values()]).astype(np.float32)
    pairs = classify_pairs(pairwise_similarity(subjects, ["A", "B", "C"], hashes, constant, z), 0.99).set_index(["subject_a", "subject_b"])
    assert pairs.loc[("s1", "s2"), "identical"]
    assert pairs.loc[("s1", "s3"), "near_duplicate"] and not pairs.loc[("s1", "s3"), "identical"]
    assert not pairs.loc[("s1", "s4"), "identical"] and not pairs.loc[("s1", "s4"), "near_duplicate"]


def test_split_groups_union():
    groups = split_groups(["a", "b", "c", "d"], [("a", "b"), ("b", "c")])
    assert groups["a"] == groups["b"] == groups["c"] != groups["d"]


def test_marker_decoding_splits_merged_pulses_and_measures_imagery():
    marker = np.zeros(100)
    marker[[0, 10, 30, 50]] = [1, 2, 3, 1]
    marker[51] = 2          # merged [1, 2] pulse -> instruction + imagery
    marker[90] = 3
    samples, codes = marker_events(marker * 1e-6, 1e-6)
    assert samples.tolist() == [0, 10, 30, 50, 51, 90] and codes.tolist() == [1, 2, 3, 1, 2, 3]
    onsets, lengths = imagery_trials(samples, codes, 100)
    assert onsets.tolist() == [10, 51] and lengths.tolist() == [20, 39]


def test_match_to_sidecar_one_to_one_and_window():
    sidecar = np.array([1000, 5000, 9000])
    onsets = np.array([1005, 4001, 5830, 9002, 15000])
    match = match_to_sidecar(onsets, sidecar, 2000)
    # 4001 and 5830 both near 5000: the closer (5830, lag 830) wins; 4001 is unmatched; 15000 out of window.
    assert match.tolist() == [0, -1, 1, 2, -1]
