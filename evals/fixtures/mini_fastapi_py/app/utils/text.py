"""Standalone string formatting helpers."""


def slugify_label(raw: str) -> str:
    """Return a clean lowercase hyphenated label."""
    cleaned = raw.strip().lower()
    return cleaned.replace(" ", "-")
