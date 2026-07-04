from __future__ import annotations

from typing import Any

from src.models.schemas import PipelineResult
from src.rag.web_search import filter_verified_snippets


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


def web_links_summary(snippets: list[dict[str, Any]], *, enabled: bool) -> dict[str, Any]:
    """Metadata for optional «полезные ссылки» block — not fed into LLM prompts."""
    if not enabled:
        return {"use_web": False}
    return {
        "use_web": True,
        "web_snippets": snippets,
        "web_snippet_count": len(snippets),
        "web_verified": bool(snippets),
        "web_fallback": bool(snippets and str(snippets[0].get("provider") or "") == "fallback"),
        "web_enriched": True,
    }


def enrich_result_web(result: PipelineResult) -> PipelineResult:
    """Load verified useful links for display (does not change hypotheses)."""
    snippets = (result.context_summary or {}).get("web_snippets") or []
    if not snippets:
        snippets = fetch_web_snippets(result.case_id, result.kpi_goal, case_name=result.case_name)
    else:
        snippets = filter_verified_snippets(snippets)

    summary = dict(result.context_summary or {})
    summary.update(web_links_summary(snippets, enabled=True))
    return result.model_copy(update={"context_summary": summary})
