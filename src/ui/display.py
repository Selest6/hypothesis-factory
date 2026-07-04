from __future__ import annotations


def short_title(title: str, max_len: int = 90) -> str:
    """One-line title for cards (full title stays in export)."""
    text = (title or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"
