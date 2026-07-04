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


def novelty_badge_parts(similarity: float) -> tuple[str, str, str]:
    """Return (css_class, headline, hint) for the prior-art badge."""
    if similarity < 0.5:
        return (
            "novelty-new",
            "Свежая идея",
            "формулировка почти не повторяет тексты учебников из базы",
        )
    return (
        "novelty-known",
        "Похоже на учебник",
        "близкая мысль уже встречается в литературе из базы",
    )


def format_novelty_badge_html(
    *,
    similarity: float,
    snippet: str,
    snippet_limit: int = 90,
) -> str:
    css, headline, hint = novelty_badge_parts(similarity)
    sim_pct = int(round(similarity * 100))
    short = snippet.strip()
    if len(short) > snippet_limit:
        short = short[: snippet_limit - 1].rstrip() + "…"
    short = escape_html_text(short)
    return (
        f'<div class="{css}">'
        f"<b>📚 {escape_html_text(headline)}</b> — {escape_html_text(hint)}.<br>"
        f'<span style="opacity:0.92">Совпадение с ближайшим фрагментом PDF: <b>{sim_pct}%</b>'
        f'{f" · «{short}»" if short else ""}</span>'
        f"</div>"
    )


def format_novelty_explanation(
    score: float,
    *,
    similarity: float,
    snippet: str | None,
) -> str:
    _, headline, hint = novelty_badge_parts(similarity)
    text = f"Новизна {score:.2f}: {headline.lower()} — {hint}"
    if snippet:
        text += f"; совпадение с PDF ~{similarity:.0%}"
    return text
