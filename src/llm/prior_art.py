from __future__ import annotations

from difflib import SequenceMatcher

from src.models.schemas import GeneratedHypothesis


def nearest_prior_art(
    hypothesis: GeneratedHypothesis | dict,
    literature_texts: list[str],
) -> tuple[str | None, float]:
    if isinstance(hypothesis, GeneratedHypothesis):
        text = " ".join(
            part for part in [hypothesis.title, hypothesis.full_statement] if part
        )
    else:
        text = " ".join(
            part
            for part in [hypothesis.get("title"), hypothesis.get("full_statement")]
            if part
        )
    if not literature_texts or not text:
        return None, 0.0

    best_snippet = literature_texts[0]
    best_ratio = 0.0
    for snippet in literature_texts:
        ratio = SequenceMatcher(None, text.lower(), snippet.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_snippet = snippet
    preview = best_snippet.replace("\n", " ").strip()[:120]
    return preview or None, best_ratio
