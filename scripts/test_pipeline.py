#!/usr/bin/env python3
"""Test Yandex GPT connection or run full hypothesis pipeline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm.pipeline import run_pipeline
from src.llm.yandex_client import YandexGPTClient
from src.rag.context import retrieve_context


def main() -> None:
    parser = argparse.ArgumentParser(description="Test LLM pipeline for hypothesis-factory")
    parser.add_argument("--case-id", default="nof_med")
    parser.add_argument("--kpi", default="")
    parser.add_argument("--constraints", default="")
    parser.add_argument("--mode", choices=["live", "demo"], default="live")
    parser.add_argument("--ping", action="store_true", help="Only test Yandex API connectivity")
    args = parser.parse_args()

    if args.ping:
        client = YandexGPTClient()
        print("configured:", client.configured)
        print("response:", client.ping())
        return

    ctx = retrieve_context(args.case_id, args.kpi)
    print(f"Case: {ctx.case_name}")
    print(f"KPI: {ctx.kpi_goal}")
    print(f"Top loss: {ctx.top_losses[0] if ctx.top_losses else 'n/a'}")
    print(f"References: {len(ctx.reference_hypotheses)}")

    result = run_pipeline(
        args.case_id,
        kpi_goal=ctx.kpi_goal,
        constraints=args.constraints,
        mode=args.mode,
    )
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
