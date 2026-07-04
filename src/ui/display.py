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
            "Новая идея",
            "в учебниках проекта такой формулировки почти нет",
        )
    return (
        "novelty-known",
        "Уже в учебнике",
        "похожая мысль есть в литературе проекта",
    )


def format_novelty_badge_html(
    *,
    similarity: float,
    snippet: str,
    snippet_limit: int = 72,
) -> str:
    css, headline, hint = novelty_badge_parts(similarity)
    sim_pct = int(round(similarity * 100))
    return (
        f'<div class="{css}">'
        f"<b>{escape_html_text(headline)}</b>. {escape_html_text(hint.capitalize())}."
        f'<br><span style="opacity:0.88;font-size:0.92em">'
        f"С учебником совпало на {sim_pct}%."
        f"</span></div>"
    )


def format_novelty_explanation(
    score: float,
    *,
    similarity: float,
    snippet: str | None,
) -> str:
    _, headline, hint = novelty_badge_parts(similarity)
    sim_pct = int(round(similarity * 100))
    return f"Новизна {score:.2f}: {headline.lower()} — {hint} ({sim_pct}% совпадения с учебником)"
