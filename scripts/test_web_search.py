#!/usr/bin/env python3
"""Test web search by keywords (DuckDuckGo, no API key)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rag.context import retrieve_context
from src.rag.web_search import build_web_queries, format_web_context, search_web_snippets


def main() -> None:
    parser = argparse.ArgumentParser(description="Test keyword web search for hypothesis context")
    parser.add_argument("--case-id", default="nof_med")
    parser.add_argument("--kpi", default="")
    args = parser.parse_args()

    ctx = retrieve_context(args.case_id, args.kpi, use_web=False)
    queries = build_web_queries(ctx.kpi_goal, ctx.top_losses, case_name=ctx.case_name)
    print("Запросы:", *queries, sep="\n  - ")

    snippets = search_web_snippets(queries)
    print(f"\nНайдено фрагментов: {len(snippets)}")
    print(format_web_context(snippets) or "(пусто — проверьте интернет и pip install duckduckgo-search)")


if __name__ == "__main__":
    main()
