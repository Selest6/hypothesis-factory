from __future__ import annotations

from html import escape


def escape_html_text(text: str) -> str:
    return escape(text or "", quote=True)


def short_title(title: str, max_len: int = 90) -> str:
    """One-line title for compact views (export tables). Cards show the full title."""
    text = (title or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"
