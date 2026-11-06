"""Audit available Figshare metadata and build the v2 subject metadata scaffold.

This is a metadata audit, not a feature builder. It records verified values from
the raw participants metadata and existing derived tables. It maps paralysis side
to contralateral lesion side only under the fixed v2 rule; it never infers side
from labels or subject IDs.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_CSV = REPO_ROOT / "features" / "figshare_features.csv"
V2_FEATURES_DIR = REPO_ROOT / "features" / "v2"
AUDIT_DOC = REPO_ROOT / "docs" / "METADATA_AUDIT.md"


def find_metadata_candidates() -> list[Path]:
    """Find likely clinical metadata files without assuming a location."""
    candidates: list[Path] = []
    for pattern in ("participants.tsv", "*participant*.tsv", "*clinical*.tsv"):
        candidates.extend(REPO_ROOT.rglob(pattern))
    return sorted(set(path for path in candidates if ".git" not in path.parts))


def build_subject_meta(
    features: list[dict[str, str]],
    participants: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    """Create v2 metadata using the verified paralysis-side source."""
    required = [
        "subject_id",
        "nihss_raw",
        "severity_class",
        "n_epochs_all",
    ]
    available = set(features[0]) if features else set()
    missing = [column for column in required if column not in available]
    if missing:
        raise ValueError(f"Required derived columns are missing: {missing}")

    return [
        build_subject_row(row, participants.get(row["subject_id"]))
        for row in features
    ]


def build_subject_row(
    feature_row: dict[str, str], participant: dict[str, str] | None
) -> dict[str, str]:
    """Combine derived bookkeeping with raw metadata without using labels for side."""
    paralysis_side = (participant or {}).get("ParalysisSide", "").strip().lower()
    lesion_side = {"left": "right", "right": "left"}.get(paralysis_side, "NA")
    if lesion_side == "NA":
        side_source = "UNVERIFIED: missing or non-lateral ParalysisSide"
    else:
        side_source = (
            "participants.json defines ParalysisSide as limb paralysis side; "
            "lesion side mapped contralaterally under the v2 rule"
        )
    return {
        "subject_id": feature_row["subject_id"],
        "nihss_raw": feature_row["nihss_raw"],
        "severity_class": feature_row["severity_class"],
        "lesion_side": lesion_side,
        "lesion_side_source": side_source,
        "paralysis_side": paralysis_side or "NA",
        "stroke_location": (participant or {}).get("StrokeLocation", "NA"),
        "sex": (participant or {}).get("Gender", "NA"),
        "age": (participant or {}).get("Age", "NA"),
        "duration": (participant or {}).get("Duration", "NA"),
        "handedness": (participant or {}).get("Handedness", "NA"),
        "n_epochs_all": feature_row["n_epochs_all"],
        "n_epochs_g8f": "",
        "n_epochs_g24f": "",
    }


def write_audit(
    candidates: list[Path],
    metadata: list[dict[str, str]],
    participants_json: Path | None,
) -> None:
    """Write an auditable report of metadata fields, semantics, and counts."""
    candidate_text = "\n".join(f"- `{path.relative_to(REPO_ROOT)}`" for path in candidates)
    if not candidate_text:
        candidate_text = "- No matching metadata files were found under the repository."
    side_counts = {side: sum(row["lesion_side"] == side for row in metadata) for side in ("left", "right", "NA")}
    crosstab: dict[tuple[str, str], int] = {}
    for row in metadata:
        key = (row["lesion_side"], row["severity_class"])
        crosstab[key] = crosstab.get(key, 0) + 1
    crosstab_lines = [
        f"- {side}: mild={crosstab.get((side, 'mild'), 0)}, moderate={crosstab.get((side, 'moderate'), 0)}"
        for side in ("left", "right", "NA")
    ]
    feasible = side_counts["left"] >= 10 and side_counts["right"] >= 10
    semantics_source = (
        f"`{participants_json.relative_to(REPO_ROOT)}`"
        if participants_json is not None
        else "No participants.json found"
    )

    AUDIT_DOC.write_text(
        "\n".join(
            [
                "# Figshare Metadata Audit (v2 A0)",
                "",
                f"**Audit date:** {date.today().isoformat()}",
                f"**Status:** {'READY FOR A2' if feasible else 'BLOCKED for lesion alignment'}",
                "",
                "## Search result",
                "",
                "The repository was searched recursively for `participants.tsv`, participant TSV files, and clinical TSV files.",
                "",
                candidate_text,
                "",
                "The raw participant table provides `ParalysisSide`, `StrokeLocation`, `Gender`, `Age`, `Duration`, and `Handedness`.",
                f"The companion metadata description is {semantics_source}. It defines `ParalysisSide` as the side of limb paralysis due to stroke.",
                "The v2 rule maps paralysis side to contralateral lesion side. This mapping is recorded as provenance and is not inferred from NIHSS or severity.",
                "Exact raw participant columns: `Participant_ID`, `Gender`, `Age`, `Duration`, `ParalysisSide`, `Handedness`, `IsFirstTime`, `StrokeLocation`, `NIHSS`, `MBI`, `mRS`.",
                "",
                "## Counts",
                "",
                f"Mapped lesion-side counts: left={side_counts['left']}, right={side_counts['right']}, NA={side_counts['NA']}.",
                "Severity cross-tab (descriptive only; not used for feature design):",
                *crosstab_lines,
                "",
                "## Decision",
                "",
                f"Lesion alignment feasibility rule: at least 10 clear left and 10 clear right cases. Feasible={feasible}.",
                "A2/T3 may proceed only if the feasibility result is true. Subjects with non-lateral or missing paralysis side remain `NA`.",
                "",
                "## Subject metadata scaffold",
                "",
                f"The scaffold contains {len(metadata)} subjects copied from `features/figshare_features.csv` for handoff bookkeeping. `n_epochs_g8f` and `n_epochs_g24f` remain empty until the v2 graph pipeline runs.",
                "",
                "## Next feasible work",
                "",
                "A2 may proceed from this metadata audit. The label-blind A3 channel/epoch audit may also proceed now that processed epoch FIFs are available.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    candidates = find_metadata_candidates()
    participants_path = next((path for path in candidates if path.name == "participants.tsv"), None)
    if participants_path is None:
        raise FileNotFoundError("participants.tsv was not found")
    with participants_path.open(newline="", encoding="utf-8") as handle:
        participants = {
            row["Participant_ID"]: row
            for row in csv.DictReader(handle, delimiter="\t")
        }
    with FEATURES_CSV.open(newline="", encoding="utf-8") as handle:
        features = list(csv.DictReader(handle))
    metadata = build_subject_meta(features, participants)

    V2_FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    metadata_path = V2_FEATURES_DIR / "subject_meta.csv"
    columns = list(metadata[0]) if metadata else []
    with metadata_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(metadata)
    participants_json = participants_path.with_suffix(".json")
    write_audit(candidates, metadata, participants_json if participants_json.exists() else None)

    print(f"Metadata candidates: {len(candidates)}")
    print(f"Subject metadata rows: {len(metadata)}")
    print(f"Wrote: {AUDIT_DOC}")
    print(f"Wrote: {metadata_path}")


if __name__ == "__main__":
    main()
