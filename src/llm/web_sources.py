from __future__ import annotations

from typing import Any

from src.models.schemas import GeneratedHypothesis, SourceRef


def _source_file(source: SourceRef | dict[str, Any]) -> str:
    if isinstance(source, SourceRef):
        return source.file
    return str(source.get("file") or "")


def attach_web_sources(
    hypotheses: list[GeneratedHypothesis],
    web_snippets: list[dict[str, Any]],
) -> list[GeneratedHypothesis]:
    """Ensure each hypothesis has a clickable web URL when search found results."""
    if not web_snippets:
        return hypotheses

    enriched: list[GeneratedHypothesis] = []
    for index, hypothesis in enumerate(hypotheses):
        sources: list[SourceRef | dict[str, Any]] = list(hypothesis.sources or [])
        has_url = any(_source_file(src).startswith("http") for src in sources)
        if not has_url:
            item = web_snippets[index % len(web_snippets)]
            url = str(item.get("url") or "").strip()
            if url:
                title = str(item.get("title") or "Источник из интернета").strip()
                snippet = str(item.get("snippet") or "").strip()
                fragment = f"{title}: {snippet[:160]} · требует верификации".strip()
                sources.append(
                    SourceRef(
                        file=url,
                        fragment=fragment,
                    )
                )
        enriched.append(hypothesis.model_copy(update={"sources": sources}))
    return enriched
