"""Acceptance tests for the v2 lesion-aligned spectral table."""

from __future__ import annotations

import csv
import math
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "features" / "figshare_features.csv"
META = ROOT / "features" / "v2" / "subject_meta.csv"
OUTPUT = ROOT / "features" / "v2" / "spectral_lesion.csv"
SCRIPT = ROOT / "src" / "build_spectral_lesion_v2.py"
AI_COLUMNS = [
    f"all_AI_{band}_{pair}"
    for band in ("delta", "theta", "alpha", "beta")
    for pair in ("F3F4", "C3C4", "P3P4", "O1O2")
]
GLOBAL_COLUMNS = ["all_pdBSI", "all_DAR", "all_DTABR"]


class LesionAlignmentTests(unittest.TestCase):
    @staticmethod
    def read_rows(path: Path) -> list[dict[str, str]]:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_absolute_values_are_preserved(self) -> None:
        source = {row["subject_id"]: row for row in self.read_rows(SOURCE)}
        output = {row["subject_id"]: row for row in self.read_rows(OUTPUT)}
        for subject_id, source_row in source.items():
            result = output[subject_id]
            for source_column in AI_COLUMNS:
                result_column = source_column.replace("all_AI_", "les_AI_", 1)
                self.assertTrue(
                    math.isclose(
                        abs(float(source_row[source_column])),
                        abs(float(result[result_column])),
                        rel_tol=0.0,
                        abs_tol=1e-15,
                    )
                )

    def test_side_swap_changes_only_ai_sign(self) -> None:
        source = {row["subject_id"]: row for row in self.read_rows(SOURCE)}
        metadata = {row["subject_id"]: row for row in self.read_rows(META)}
        output = {row["subject_id"]: row for row in self.read_rows(OUTPUT)}
        for subject_id, source_row in source.items():
            sign = 1.0 if metadata[subject_id]["lesion_side"] == "left" else -1.0
            result = output[subject_id]
            for source_column in AI_COLUMNS:
                result_column = source_column.replace("all_AI_", "les_AI_", 1)
                self.assertAlmostEqual(
                    float(result[result_column]), sign * float(source_row[source_column])
                )
            for column in GLOBAL_COLUMNS:
                self.assertEqual(result[column], source_row[column])

    def test_builder_does_not_access_labels(self) -> None:
        source_text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("nihss_raw", source_text)
        self.assertNotIn("severity_class", source_text)
        self.assertIn('subject_meta["lesion_side"]', source_text)


if __name__ == "__main__":
    unittest.main()
