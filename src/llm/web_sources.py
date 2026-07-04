from __future__ import annotations

from typing import Any

from src.models.schemas import GeneratedHypothesis, PipelineResult, SourceRef


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


def fetch_web_snippets(case_id: str, kpi_goal: str, *, case_name: str = "") -> list[dict[str, Any]]:
    from src.rag.context import retrieve_context
    from src.rag.web_search import build_web_queries, search_web_snippets

    ctx = retrieve_context(case_id, kpi_goal, use_chroma=False, use_web=False)
    queries = build_web_queries(
        kpi_goal,
        ctx.top_losses,
        case_name=case_name or ctx.case_name,
    )
    return search_web_snippets(queries)


def enrich_result_web(result: PipelineResult) -> PipelineResult:
    """Load web snippets if missing and attach URL sources to every hypothesis."""
    snippets = (result.context_summary or {}).get("web_snippets") or []
    if not snippets:
        snippets = fetch_web_snippets(result.case_id, result.kpi_goal, case_name=result.case_name)

    hypotheses = attach_web_sources(list(result.hypotheses), snippets)
    summary = dict(result.context_summary or {})
    summary["web_snippets"] = snippets
    summary["web_snippet_count"] = len(snippets)
    summary["use_web"] = True
    if snippets and str(snippets[0].get("provider") or "") == "fallback":
        summary["web_fallback"] = True
    summary["web_enriched"] = True

    return result.model_copy(update={"hypotheses": hypotheses, "context_summary": summary})
