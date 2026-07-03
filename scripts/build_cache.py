#!/usr/bin/env python3
"""Run live hypothesis pipeline for all cases and save demo cache."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from src.llm.pipeline import run_pipeline
from src.rag.context import CASE_DEFAULT_KPI

ALL_CASES = list(CASE_DEFAULT_KPI.keys())


def _load_env() -> None:
    if load_dotenv is not None:
        load_dotenv(ROOT / ".env")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build demo cache for hypothesis pipeline")
    parser.add_argument(
        "--case-id",
        action="append",
        dest="case_ids",
        help="Case to process (repeatable; default: all four cases)",
    )
    parser.add_argument("--constraints", default="")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--mode", choices=["live", "offline"], default="offline")
    args = parser.parse_args()

    _load_env()
    case_ids = args.case_ids or ALL_CASES
    cache_dir = ROOT / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    for case_id in case_ids:
        cache_path = cache_dir / f"{case_id}.json"
        if args.skip_existing and cache_path.exists():
            print(f"[skip] {case_id}: cache exists")
            continue

        print(f"[{args.mode}] {case_id} ...", flush=True)
        result = run_pipeline(
            case_id,
            kpi_goal=CASE_DEFAULT_KPI.get(case_id, ""),
            constraints=args.constraints,
            mode=args.mode,
            save_demo_cache=True,
        )
        print(
            json.dumps(
                {
                    "case_id": result.case_id,
                    "mode": result.mode,
                    "hypotheses": len(result.hypotheses),
                    "cache": str(cache_path),
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
