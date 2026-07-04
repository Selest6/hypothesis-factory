from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from src.models.schemas import GeneratedHypothesis

_RISK_LABELS = ("Технический", "Экономический")


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
    sim_pct = int(round(similarity * 100))
    if similarity < 0.5:
        return (
            "novelty-new",
            "💡 Своя идея",
            f"С базой знаний совпало только на {sim_pct}% — такой формулировки в материалах почти нет.",
        )
    return (
        "novelty-known",
        "📖 Похоже на известное",
        f"С базой знаний совпало на {sim_pct}% — похожая мысль уже есть в литературе проекта.",
    )


def format_novelty_badge_html(
    *,
    similarity: float,
    snippet: str,
    snippet_limit: int = 72,
) -> str:
    css, headline, hint = novelty_badge_parts(similarity)
    return (
        f'<div class="{css}">'
        f"<b>{escape_html_text(headline)}</b><br>"
        f'<span class="novelty-hint">{escape_html_text(hint)}</span>'
        f"</div>"
    )


def format_novelty_explanation(
    score: float,
    *,
    similarity: float,
    snippet: str | None,
) -> str:
    _, headline, hint = novelty_badge_parts(similarity)
    clean_headline = headline.replace("💡 ", "").replace("📖 ", "")
    return f"Новизна {score:.2f}: {clean_headline.lower()} — {hint.lower()}"


def _is_empty_section_text(value: str) -> bool:
    text = (value or "").strip()
    return not text or text in {"—", "-"}


def iter_risk_items(hypothesis: GeneratedHypothesis) -> Iterator[tuple[str, str]]:
    """Technical / economic risks as labeled pairs; skips empty placeholders."""
    risks = hypothesis.risks
    if isinstance(risks, dict):
        for key, label in (("technical", _RISK_LABELS[0]), ("economic", _RISK_LABELS[1])):
            value = str(risks.get(key) or "").strip()
            if not _is_empty_section_text(value):
                yield label, value
        return

    if isinstance(risks, list):
        for idx, item in enumerate(risks):
            value = str(item).strip()
            if _is_empty_section_text(value):
                continue
            label = _RISK_LABELS[idx] if idx < len(_RISK_LABELS) else f"Риск {idx + 1}"
            yield label, value


def format_risk_items(hypothesis: GeneratedHypothesis) -> list[tuple[str, str]]:
    return list(iter_risk_items(hypothesis))
