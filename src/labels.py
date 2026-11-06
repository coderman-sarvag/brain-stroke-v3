"""Shared clinical label utilities."""


def bucket_nihss(score: float) -> str:
    """Map an NIHSS score to the project's fixed severity class."""
    if score <= 4:
        return "mild"
    if score <= 15:
        return "moderate"
    return "severe"