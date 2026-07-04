from __future__ import annotations

import os
import re
from typing import Any

DEFAULT_MAX_QUERIES = 3
DEFAULT_RESULTS_PER_QUERY = 5

_RELEVANCE_KEYWORDS = (
    "флота",
    "обога",
    "хвост",
    "мельниц",
    "руды",
    "минерал",
    "мед",
    "никел",
    "измельч",
    "концентрат",
    "реагент",
    "гидроцикл",
    "классиф",
)


def _is_relevant(title: str, snippet: str) -> bool:
    text = f"{title} {snippet}".lower()
    return any(kw in text for kw in _RELEVANCE_KEYWORDS)


def _tokenize(text: str) -> list[str]:
    return [
        t
        for t in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", text.lower())
        if len(t) >= 3
    ]


def build_web_queries(
    kpi_goal: str,
    top_losses: list[dict[str, Any]],
    *,
    case_name: str = "",
) -> list[str]:
    """Build Russian search queries from KPI and Excel loss nodes."""
    queries: list[str] = []
    seen: set[str] = set()

    def add(q: str) -> None:
        q = " ".join(q.split())
        key = q.lower()
        if q and key not in seen:
            seen.add(key)
            queries.append(q)

    add(
        "обогащение полезных ископаемых флотация снижение потерь меди никеля в хвостах"
    )
    add(f"{kpi_goal} обогатительная фабрика флотация хвосты")

    for row in top_losses[:3]:
        subject = str(row.get("subject") or "").strip()
        element = str(row.get("element") or "").strip()
        if subject and subject.lower() not in ("отвальные хвосты",):
            add(
                f"флотация {subject} {element} потери металла хвосты обогащение руды"
            )

    return queries[:DEFAULT_MAX_QUERIES]


def search_web_snippets(
    queries: list[str],
    *,
    max_results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
) -> list[dict[str, Any]]:
    """
    Search the web via DuckDuckGo (no API key).
    Returns list of {title, snippet, url, query}.
    """
    if os.getenv("ENABLE_WEB_SEARCH", "").strip().lower() in ("0", "false", "no"):
        return []

    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return []

    snippets: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    try:
        with DDGS() as ddgs:
            for query in queries:
                for item in ddgs.text(query, max_results=max_results_per_query, region="ru-ru"):
                    url = str(item.get("href") or item.get("link") or "").strip()
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    title = str(item.get("title") or "").strip()
                    snippet = str(item.get("body") or item.get("snippet") or "").strip()
                    if not _is_relevant(title, snippet):
                        continue
                    snippets.append(
                        {
                            "title": title,
                            "snippet": snippet,
                            "url": url,
                            "query": query,
                        }
                    )
                    if len(snippets) >= max_results_per_query * len(queries):
                        return snippets
    except Exception:
        return snippets

    return snippets


def format_web_context(snippets: list[dict[str, Any]]) -> str:
    if not snippets:
        return ""
    lines = [
        "Дополнительный контекст из интернета (открытые источники, требует верификации):"
    ]
    for i, item in enumerate(snippets, 1):
        title = item.get("title") or "без названия"
        url = item.get("url") or ""
        snippet = (item.get("snippet") or "")[:500]
        lines.append(f"[web-{i}] {title}\nURL: {url}\n{snippet}")
    return "\n\n".join(lines)
