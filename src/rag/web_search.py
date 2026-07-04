from __future__ import annotations

import os
import re
import subprocess
from functools import lru_cache
from html import unescape
from typing import Any
from urllib.parse import urlparse

import httpx

DEFAULT_MAX_QUERIES = 3
DEFAULT_RESULTS_PER_QUERY = 5
DEFAULT_VERIFIED_LIMIT = 5
_VERIFY_TIMEOUT = 10.0
_MAX_BODY_BYTES = 150_000

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

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
    "flotation",
    "concentrat",
    "tailings",
    "ore",
)

_BAD_PAGE_MARKERS = (
    "404",
    "not found",
    "page not found",
    "страница не найдена",
    "страница не существует",
    "ошибка 404",
    "file not found",
)

_SKIP_URL_PREFIXES = (
    "https://duckduckgo.com/",
    "http://duckduckgo.com/",
    "https://www.google.com/",
)


def _is_relevant(title: str, snippet: str) -> bool:
    text = f"{title} {snippet}".lower()
    return any(kw in text for kw in _RELEVANCE_KEYWORDS)


def _relevance_hits(text: str) -> int:
    lowered = text.lower()
    return sum(1 for kw in _RELEVANCE_KEYWORDS if kw in lowered)


def _looks_like_error_page(title: str, body_text: str) -> bool:
    probe = f"{title} {body_text[:800]}".lower()
    return any(marker in probe for marker in _BAD_PAGE_MARKERS)


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return unescape(re.sub(r"\s+", " ", text)).strip()


def _url_is_allowed(url: str) -> bool:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.netloc:
        return False
    normalized = url.strip().lower()
    return not any(normalized.startswith(prefix) for prefix in _SKIP_URL_PREFIXES)


def _curl_fetch(url: str) -> tuple[int, str, str]:
    """Fallback fetch when httpx is blocked (common for Wikipedia)."""
    try:
        proc = subprocess.run(
            [
                "curl",
                "-sL",
                "--max-time",
                str(int(_VERIFY_TIMEOUT)),
                "-A",
                _USER_AGENT,
                "-H",
                "Accept-Language: ru-RU,ru;q=0.9",
                "-w",
                "\n__HTTP_STATUS__%{http_code}",
                url,
            ],
            capture_output=True,
            timeout=_VERIFY_TIMEOUT + 5,
            check=False,
        )
        raw = proc.stdout
        marker = b"\n__HTTP_STATUS__"
        if marker in raw:
            body_bytes, status_bytes = raw.rsplit(marker, 1)
            status = int(status_bytes.decode("ascii", errors="ignore") or "0")
        else:
            body_bytes, status = raw, 0
        body = body_bytes[:_MAX_BODY_BYTES].decode("utf-8", errors="ignore")
        content_type = "text/html"
        if body.lstrip().startswith("%PDF"):
            content_type = "application/pdf"
        return status, content_type, body
    except Exception:
        return 0, "", ""


@lru_cache(maxsize=64)
def _fetch_page_sample(url: str) -> tuple[int, str, str]:
    """Return (status_code, content_type, body_sample)."""
    status, content_type, body = 0, "", ""
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=_VERIFY_TIMEOUT,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9",
            },
        ) as client:
            response = client.get(url)
            status = response.status_code
            content_type = response.headers.get("content-type", "")
            body = response.content[:_MAX_BODY_BYTES].decode("utf-8", errors="ignore")
    except Exception:
        pass

    if status < 200 or status >= 400 or (status == 403 and not body):
        curl_status, curl_type, curl_body = _curl_fetch(url)
        if curl_status >= 200 and curl_status < 400:
            return curl_status, curl_type, curl_body
        if curl_status:
            return curl_status, curl_type, curl_body
    return status, content_type, body


def verify_web_snippet(item: dict[str, Any]) -> dict[str, Any] | None:
    """
    Check that URL responds and page body looks relevant.
    Returns enriched snippet dict or None if link should be hidden.
    """
    url = str(item.get("url") or "").strip()
    title = str(item.get("title") or "").strip()
    snippet = str(item.get("snippet") or "").strip()
    if not url or not _url_is_allowed(url):
        return None
    if not _is_relevant(title, snippet):
        return None

    status, content_type, body = _fetch_page_sample(url)
    if status < 200 or status >= 400:
        return None

    lowered_type = content_type.lower()
    if "pdf" in lowered_type or url.lower().endswith(".pdf"):
        if not body.lstrip().startswith("%PDF"):
            return None
        preview = snippet or title
        if _relevance_hits(preview) < 1:
            return None
    else:
        text = _strip_html(body)
        if len(text) < 200:
            return None
        if _looks_like_error_page(title, text):
            return None
        combined = f"{title} {snippet} {text[:4000]}"
        if _relevance_hits(combined) < 2:
            return None
        if snippet:
            preview = snippet
        else:
            preview = text[:240]

    verified = dict(item)
    verified["verified"] = True
    verified["http_status"] = status
    if preview and not verified.get("snippet"):
        verified["snippet"] = preview
    return verified


def filter_verified_snippets(
    snippets: list[dict[str, Any]],
    *,
    max_items: int = DEFAULT_VERIFIED_LIMIT,
) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for item in snippets:
        url = str(item.get("url") or "").strip().lower()
        if not url or url in seen_urls:
            continue
        ok = verify_web_snippet(item)
        if not ok:
            continue
        seen_urls.add(url)
        verified.append(ok)
        if len(verified) >= max_items:
            break
    return verified


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


def fallback_web_snippets(*, kpi_goal: str = "") -> list[dict[str, Any]]:
    """Stable open sources when DuckDuckGo is unavailable (e.g. Streamlit Cloud)."""
    return [
        {
            "title": "Флотация — Википедия",
            "url": "https://ru.wikipedia.org/wiki/Флотация",
            "snippet": "Обзор флотации как метода обогащения полезных ископаемых.",
            "query": kpi_goal or "флотация",
            "provider": "fallback",
        },
        {
            "title": "Обогащение полезных ископаемых — Википедия",
            "url": "https://ru.wikipedia.org/wiki/Обогащение_полезных_ископаемых",
            "snippet": "Методы обогащения руд, включая флотацию и снижение потерь в хвостах.",
            "query": kpi_goal or "обогащение",
            "provider": "fallback",
        },
        {
            "title": "Флотационная машина — Википедия",
            "url": "https://ru.wikipedia.org/wiki/Флотационная_машина",
            "snippet": "Устройство и принцип работы флотационных машин на обогатительных фабриках.",
            "query": kpi_goal or "флотация",
            "provider": "fallback",
        },
    ]


def search_web_snippets(
    queries: list[str],
    *,
    max_results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
    verified_limit: int = DEFAULT_VERIFIED_LIMIT,
) -> list[dict[str, Any]]:
    """
    Free web search via DuckDuckGo (no API key).
    Returns only URLs that respond and contain relevant text on the page.
    """
    if os.getenv("ENABLE_WEB_SEARCH", "").strip().lower() in ("0", "false", "no"):
        return []

    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None  # type: ignore[misc, assignment]

    if DDGS is not None:
        try:
            with DDGS() as ddgs:
                for query in queries:
                    for item in ddgs.text(
                        query,
                        max_results=max_results_per_query * 2,
                        region="ru-ru",
                    ):
                        url = str(item.get("href") or item.get("link") or "").strip()
                        if not url or url in seen_urls or not _url_is_allowed(url):
                            continue
                        seen_urls.add(url)
                        title = str(item.get("title") or "").strip()
                        snippet = str(item.get("body") or item.get("snippet") or "").strip()
                        if not _is_relevant(title, snippet):
                            continue
                        candidates.append(
                            {
                                "title": title,
                                "snippet": snippet,
                                "url": url,
                                "query": query,
                                "provider": "web",
                            }
                        )
        except Exception:
            candidates = []

    verified = filter_verified_snippets(candidates, max_items=verified_limit)
    if verified:
        return verified

    fallback_verified = filter_verified_snippets(
        fallback_web_snippets(),
        max_items=min(3, verified_limit),
    )
    return fallback_verified


def format_web_context(snippets: list[dict[str, Any]]) -> str:
    if not snippets:
        return ""
    provider = str(snippets[0].get("provider") or "web")
    if provider == "fallback":
        provider_label = "проверенные открытые источники (DuckDuckGo недоступен)"
    else:
        provider_label = "DuckDuckGo (проверенные ссылки)"
    lines = [
        f"Дополнительные полезные ссылки ({provider_label}, только для чтения):"
    ]
    for i, item in enumerate(snippets, 1):
        title = item.get("title") or "без названия"
        url = item.get("url") or ""
        snippet = (item.get("snippet") or "")[:500]
        lines.append(f"[web-{i}] {title}\nURL: {url}\n{snippet}")
    return "\n\n".join(lines)
